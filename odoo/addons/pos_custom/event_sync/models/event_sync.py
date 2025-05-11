# -*- coding: utf-8 -*-
"""
Event → RabbitMQ bridge (Attendify 2.0 schema)
"""
import logging, os, time, re, xml.etree.ElementTree as ET
from xml.dom import minidom

import pika
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class EventSync(models.Model):
    _inherit = "event.event"

    external_uid = fields.Char(string="External UID", copy=False, index=True, readonly=True)

    @staticmethod
    def _pretty(xml_bytes: bytes) -> str:
        return minidom.parseString(xml_bytes).toprettyxml(indent="  ")

    @staticmethod
    def _event_uid(rec):
        if rec.external_uid:
            return rec.external_uid
        uid = f"GC{int(time.time() * 1000)}"
        # write it back once, skipping Rabbit so we don't loop
        rec.with_context(skip_rabbit=True).write({"external_uid": uid})
        return uid

    def _build_raw_xml(self, operation, rec) -> bytes:
        root = ET.Element("attendify")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:noNamespaceSchemaLocation", "event.xsd")

        info = ET.SubElement(root, "info")
        ET.SubElement(info, "sender").text    = "odoo"
        ET.SubElement(info, "operation").text = operation

        ev = ET.SubElement(root, "event")
        ET.SubElement(ev, "id").text           = f"evt_{rec.id}"
        ET.SubElement(ev, "uid").text          = self._event_uid(rec)
        ET.SubElement(ev, "title").text        = rec.name or ""
        ET.SubElement(ev, "location").text     = rec.address_id.display_name or ""
        ET.SubElement(ev, "start_date").text   = rec.date_begin.strftime("%Y-%m-%d") if rec.date_begin else ""
        ET.SubElement(ev, "end_date").text     = rec.date_end.strftime("%Y-%m-%d")   if rec.date_end   else ""
        ET.SubElement(ev, "start_time").text   = rec.date_begin.strftime("%H:%M")    if rec.date_begin else ""
        ET.SubElement(ev, "end_time").text     = rec.date_end.strftime("%H:%M")      if rec.date_end   else ""
        ET.SubElement(ev, "organizer_name").text = rec.user_id.name if rec.user_id else ""
        ET.SubElement(ev, "organizer_uid").text = rec.user_id.ref or ""

        # Entrance fee derived from the cheapest ticket
        if rec.event_ticket_ids:
            fee = min(rec.event_ticket_ids.mapped("price") or [0])
        else:
            fee = 0.0
        ET.SubElement(ev, "entrance_fee").text = f"{fee:.2f}"

        # Empty <description/> – will get CDATA later
        ET.SubElement(ev, "description")

        return ET.tostring(root, encoding="utf-8")

    def _build_xml(self, operation, rec) -> str:
        pretty = self._pretty(self._build_raw_xml(operation, rec))
        cdata  = f"<![CDATA[{(rec.description or '')}]]>"
        return re.sub(
            r"<description>\s*</description>",
            f"<description>{cdata}</description>",
            pretty,
            count=1,
        )

    # ─── Publisher ───────────────────────────────────────────────────────────
    def _send_event_to_rabbitmq(self, operation):
        if self.env.context.get("skip_rabbit"):
            return

        host, user, pw = (
            os.getenv("RABBITMQ_HOST"),
            os.getenv("RABBITMQ_USERNAME"),
            os.getenv("RABBITMQ_PASSWORD"),
        )
        if not all([host, user, pw]):
            _logger.error("RabbitMQ vars missing; skipping event push.")
            return

        params = pika.ConnectionParameters(
            host=host,
            port=int(os.getenv("RABBITMQ_PORT", 5672)),
            virtual_host=os.getenv("RABBITMQ_VHOST", "/"),
            credentials=pika.PlainCredentials(user, pw),
        )
        routing = {"create": "event.register", "update": "event.update", "delete": "event.delete"}[operation]

        try:
            conn = pika.BlockingConnection(params)
            ch   = conn.channel()
            exchange, queue = "event", "pos.event"

            ch.exchange_declare(exchange=exchange, exchange_type="direct", durable=True)
            ch.queue_declare(queue=queue, durable=True)
            ch.queue_bind(queue=queue, exchange=exchange, routing_key=routing)

            for rec in self:
                xml_msg = self._build_xml(operation, rec)
                ch.basic_publish(
                    exchange=exchange,
                    routing_key=routing,
                    body=xml_msg.encode("utf-8"),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                _logger.info("Event %s (%s) sent as %s", rec.name, rec.id, operation)
            conn.close()
        except Exception:
            _logger.exception("Failed to send event to RabbitMQ")

    # ─── ORM hooks ───────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("skip_rabbit"):
            return super(EventSync, self).create(vals_list)

        recs = super(EventSync, self.with_context(skip_rabbit=True)).create(vals_list)
        recs = recs.with_context(skip_rabbit=False)
        recs._send_event_to_rabbitmq("create")
        return recs

    def write(self, vals):
        if self.env.context.get("skip_rabbit"):
            return super(EventSync, self).write(vals)
        res = super(EventSync, self).write(vals)
        self._send_event_to_rabbitmq("update")
        return res

    def unlink(self):
        if self.env.context.get("skip_rabbit"):
            return super(EventSync, self).unlink()
        self._send_event_to_rabbitmq("delete")
        return super(EventSync, self).unlink()
