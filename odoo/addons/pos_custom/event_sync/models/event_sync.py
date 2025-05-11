# -*- coding: utf-8 -*-
"""
Event → RabbitMQ bridge (Attendify format)
"""
import logging
import os
import time
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom

import pika
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class EventSync(models.Model):
    _inherit = "event.event"

    # New field to hold a stable external UID
    external_uid = fields.Char(
        string="External UID", copy=False, index=True, readonly=True
    )

    # Helpers
    @staticmethod
    def _pretty(xml_bytes: bytes) -> str:
        """Return indented XML string."""
        return minidom.parseString(xml_bytes).toprettyxml(indent="  ")

    @staticmethod
    def _event_uid(rec):
        """Return or create a stable external UID for the event."""
        if rec.external_uid:
            return rec.external_uid
        uid = f"EV{int(time.time() * 1000)}"
        # write it back once, skipping Rabbit so we don't loop
        rec.with_context(skip_rabbit=True).write({"external_uid": uid})
        return uid

    def _build_raw_xml(self, operation, rec) -> bytes:
        """Build base XML, leaving <description/> empty for later CDATA injection."""
        root = ET.Element("attendify")
        info = ET.SubElement(root, "info")
        ET.SubElement(info, "sender").text = "odoo"
        ET.SubElement(info, "operation").text = operation

        ev = ET.SubElement(root, "event")
        ET.SubElement(ev, "uid_event").text = self._event_uid(rec)
        ET.SubElement(ev, "name").text = rec.name or ""
        ET.SubElement(ev, "start_date").text = (
            rec.date_begin.isoformat() if rec.date_begin else ""
        )
        ET.SubElement(ev, "end_date").text = (
            rec.date_end.isoformat() if rec.date_end else ""
        )

        partner = rec.address_id
        addr = ET.SubElement(ev, "address")
        for tag, val in {
            "street": partner.street if partner else "",
            "street2": partner.street2 if partner else "",
            "city": partner.city if partner else "",
            "zip": partner.zip if partner else "",
            "country": partner.country_id.name
            if partner and partner.country_id
            else "",
        }.items():
            ET.SubElement(addr, tag).text = val or ""

        # empty placeholder for description
        ET.SubElement(ev, "description")
        ET.SubElement(ev, "max_attendees").text = str(rec.seats_max or 0)

        return ET.tostring(root, encoding="utf-8")

    def _build_xml(self, operation, rec) -> str:
        """Pretty-print XML and inject CDATA-wrapped description."""
        raw = self._build_raw_xml(operation, rec)
        pretty = self._pretty(raw)

        # inject the real HTML description inside CDATA
        desc = rec.description or ""
        cdata = f"<![CDATA[{desc}]]>"
        pretty = re.sub(
            r"<description>\s*</description>",
            f"<description>{cdata}</description>",
            pretty,
            count=1,
        )
        return pretty

    # Publisher
    def _send_event_to_rabbitmq(self, operation):
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

        try:
            conn = pika.BlockingConnection(params)
            ch = conn.channel()

            exchange, queue, routing = "event", "pos.event", "event.register"
            ch.exchange_declare(exchange, "direct", durable=True)
            ch.queue_declare(queue, durable=True)
            ch.queue_bind(queue=queue, exchange=exchange, routing_key=routing)

            for rec in self:
                xml_msg = self._build_xml(operation, rec)
                ch.basic_publish(
                    exchange=exchange,
                    routing_key=routing,
                    body=xml_msg.encode("utf-8"),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                _logger.info(
                    "Event %s (%s) sent to RabbitMQ as %s", rec.name, rec.id, operation
                )

            conn.close()

        except Exception:
            _logger.exception("Failed to send event to RabbitMQ")

    # ORM hooks
    @api.model_create_multi
    def create(self, vals_list):
        # run the actual create under skip_rabbit so _event_uid() won't loop
        # skip rabbit anders wordt event dat consumer aanmaakt ook nog is geplaatst op rabbit door module.
        # moet wel in consumer meegegeven worden zodat producer dit ziet.
        records = super(EventSync, self.with_context(skip_rabbit=True)).create(
            vals_list
        )
        records._send_event_to_rabbitmq("create")
        return records

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
