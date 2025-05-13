# -*- coding: utf-8 -*-
"""
Producer voor Events én Attendees  →  RabbitMQ  (Attendify 2.0 schema)
"""
import logging, os, time, re, xml.etree.ElementTree as ET
from xml.dom import minidom

import pika
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Event  →  alleen update en delete, create wordt niet in odoo gedaan

class EventSync(models.Model):
    _inherit = "event.event"

    external_uid = fields.Char(string="External UID", copy=False, index=True, readonly=True)
    gcid         = fields.Char(string="Google Calendar ID", copy=False, index=True)

    # helpers
    @staticmethod
    def _pretty(xml_bytes: bytes) -> str:
        return minidom.parseString(xml_bytes).toprettyxml(indent="  ")

    @staticmethod
    def _event_uid(rec):
        if rec.external_uid:
            return rec.external_uid
        uid = f"GC{int(time.time() * 1000)}"
        rec.with_context(skip_rabbit=True).write({"external_uid": uid})
        return uid

    # XML builder
    def _build_event_xml(self, operation, rec) -> str:
        root = ET.Element("attendify")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:noNamespaceSchemaLocation", "event.xsd")

        info = ET.SubElement(root, "info")
        ET.SubElement(info, "sender").text    = "odoo"
        ET.SubElement(info, "operation").text = operation

        ev = ET.SubElement(root, "event")
        ET.SubElement(ev, "uid").text         = self._event_uid(rec)
        ET.SubElement(ev, "gcid").text        = rec.gcid or ""
        ET.SubElement(ev, "title").text       = rec.name or ""
        ET.SubElement(ev, "location").text    = rec.address_id.display_name or ""
        ET.SubElement(ev, "start_date").text  = rec.date_begin.strftime("%Y-%m-%d") if rec.date_begin else ""
        ET.SubElement(ev, "end_date").text    = rec.date_end.strftime("%Y-%m-%d")   if rec.date_end   else ""
        ET.SubElement(ev, "start_time").text  = rec.date_begin.strftime("%H:%M")    if rec.date_begin else ""
        ET.SubElement(ev, "end_time").text    = rec.date_end.strftime("%H:%M")      if rec.date_end   else ""
        ET.SubElement(ev, "organizer_name").text = rec.user_id.name if rec.user_id else ""
        ET.SubElement(ev, "organizer_uid").text = rec.user_id.ref or ""

        fee = min(rec.event_ticket_ids.mapped("price") or [0]) if rec.event_ticket_ids else 0.0
        ET.SubElement(ev, "entrance_fee").text = f"{fee:.2f}"

        ET.SubElement(ev, "description")  # CDATA later

        pretty = self._pretty(ET.tostring(root, encoding="utf-8"))
        cdata  = f"<![CDATA[{(rec.description or '')}]]>"
        return re.sub(r"<description>\s*</description>",
                      f"<description>{cdata}</description>",
                      pretty, count=1)

    # Rabbit publish helper
    def _send_event_to_rabbitmq(self, operation):
        if self.env.context.get("skip_rabbit"):
            return

        routing = {"update": "event.update", "delete": "event.delete"}[operation]
        _rabbit_publish(self, routing, lambda rec: self._build_event_xml(operation, rec))

    # ORM hooks
    def write(self, vals):
        if self.env.context.get("skip_rabbit"):
            return super().write(vals)
        res = super().write(vals)
        self._send_event_to_rabbitmq("update")
        return res

    def unlink(self):
        if self.env.context.get("skip_rabbit"):
            return super().unlink()
        self._send_event_to_rabbitmq("delete")
        return super().unlink()


# Attendee  →  synchroniseert event.registration

class AttendeeSync(models.Model):
    _inherit = "event.registration"

    # partner_id / event_id zitten al in het model

    # XML builder
    def _build_attendee_xml(self, operation, rec) -> str:
        root = ET.Element("attendify")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:noNamespaceSchemaLocation", "event_attendee.xsd")

        info = ET.SubElement(root, "info")
        ET.SubElement(info, "sender").text    = "odoo"
        ET.SubElement(info, "operation").text = operation

        ea = ET.SubElement(root, "event_attendee")
        # user UID  = partner.ref of gekoppelde user
        user_uid = rec.partner_id.ref or ""
        ET.SubElement(ea, "uid").text      = user_uid

        # event_id  = external_uid van het event
        external_id = rec.event_id.external_uid or f"evt_{rec.event_id.id}"
        ET.SubElement(ea, "event_id").text = external_id

        return minidom.parseString(ET.tostring(root, encoding="utf-8")).toprettyxml(indent="  ")

    # Rabbit publish helper
    def _send_attendee_to_rabbitmq(self, operation):
        if self.env.context.get("skip_rabbit"):
            return

        routing = {"create": "attendee.create", "delete": "attendee.delete"}[operation]
        _rabbit_publish(self, routing, lambda rec: self._build_attendee_xml(operation, rec))

    # ORM hooks
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._send_attendee_to_rabbitmq("create")
        return recs

    def unlink(self):
        self._send_attendee_to_rabbitmq("delete")
        return super().unlink()



# Shared Rabbit helper  (publisht functie)

def _rabbit_publish(records, routing_key, xml_builder):
    """Generic helper to publish one message per record."""
    host, user, pw = (
        os.getenv("RABBITMQ_HOST"),
        os.getenv("RABBITMQ_USERNAME"),
        os.getenv("RABBITMQ_PASSWORD"),
    )
    if not all([host, user, pw]):
        _logger.error("RabbitMQ vars missing; skipping push.")
        return

    params = pika.ConnectionParameters(
        host=host,
        port=int(os.getenv("RABBITMQ_PORT", 5672)),
        virtual_host=os.getenv("RABBITMQ_VHOST", "/"),
        credentials=pika.PlainCredentials(user, pw),
    )
    try:
        conn = pika.BlockingConnection(params)
        ch   = conn.channel()
        exchange, queue = "event", "pos.event"

        ch.exchange_declare(exchange=exchange, exchange_type="direct", durable=True)
        ch.queue_declare(queue=queue, durable=True)
        ch.queue_bind(queue=queue, exchange=exchange, routing_key=routing_key)

        for rec in records:
            xml_msg = xml_builder(rec)
            ch.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=xml_msg.encode("utf-8"),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            _logger.info("Sent %s for record %s", routing_key, rec.id)
        conn.close()
    except Exception:
        _logger.exception("Failed to send to RabbitMQ")
