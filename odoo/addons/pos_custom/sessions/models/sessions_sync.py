# -*- coding: utf-8 -*-
"""
Session → RabbitMQ bridge (Attendify format)
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


class SessionSync(models.Model):
    _inherit = "event.event"

    external_uid_session = fields.Char(
        string="External UID (Session)", copy=False, index=True, readonly=True
    )

    @staticmethod
    def _pretty(xml_bytes: bytes) -> str:
        return minidom.parseString(xml_bytes).toprettyxml(indent="  ")

    @staticmethod
    def _session_uid(rec):
        if rec.external_uid_session:
            return rec.external_uid_session
        uid = f"SE{int(time.time() * 1000)}"
        rec.with_context(skip_rabbit=True).write({"external_uid_session": uid})
        return uid

    def _build_raw_xml(self, operation, rec) -> bytes:
        root = ET.Element("attendify")
        info = ET.SubElement(root, "info")
        ET.SubElement(info, "sender").text = "odoo"
        ET.SubElement(info, "operation").text = operation

        ev = ET.SubElement(root, "event")
        ET.SubElement(ev, "uid_event").text = self._session_uid(rec)
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
            "country": partner.country_id.name if partner and partner.country_id else "",
        }.items():
            ET.SubElement(addr, tag).text = val or ""

        ET.SubElement(ev, "description")
        ET.SubElement(ev, "max_attendees").text = str(rec.seats_max or 0)

        return ET.tostring(root, encoding="utf-8")

    def _build_xml(self, operation, rec) -> str:
        raw = self._build_raw_xml(operation, rec)
        pretty = self._pretty(raw)

        desc = rec.description or ""
        cdata = f"<![CDATA[{desc}]]>"
        pretty = re.sub(
            r"<description>\s*</description>",
            f"<description>{cdata}</description>",
            pretty,
            count=1,
        )
        return pretty

    def _send_session_to_rabbitmq(self, operation):
        host, user, pw = (
            os.getenv("RABBITMQ_HOST"),
            os.getenv("RABBITMQ_USERNAME"),
            os.getenv("RABBITMQ_PASSWORD"),
        )
        if not all([host, user, pw]):
            _logger.error("RabbitMQ vars missing; skipping session push.")
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

            # Gebruik nog de event exchange/queue/routing_key zoals je zei
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
                    "Session %s (%s) sent to RabbitMQ as %s", rec.name, rec.id, operation
                )

            conn.close()

        except Exception:
            _logger.exception("Failed to send session to RabbitMQ")

    @api.model_create_multi
    def create(self, vals_list):
        records = super(SessionSync, self.with_context(skip_rabbit=True)).create(
            vals_list
        )
        records._send_session_to_rabbitmq("create")
        return records

    def write(self, vals):
        if self.env.context.get("skip_rabbit"):
            return super().write(vals)
        res = super().write(vals)
        self._send_session_to_rabbitmq("update")
        return res

    def unlink(self):
        if self.env.context.get("skip_rabbit"):
            return super().unlink()
        self._send_session_to_rabbitmq("delete")
        return super().unlink()
