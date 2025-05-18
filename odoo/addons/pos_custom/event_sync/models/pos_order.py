import logging
import os
import pika
import xml.etree.ElementTree as ET
from xml.dom import minidom

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = "pos.order"

    # ---------------------------------------------------------------------
    #  FIELDS
    # ---------------------------------------------------------------------
    event_id  = fields.Many2one("event.event", string="Event")
    event_uid = fields.Char(
        related="event_id.external_uid",
        string="Event External UID",
        store=True,
    )

    # ---------------------------------------------------------------------
    #  POS → backend JSON mapping
    # ---------------------------------------------------------------------
    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        # send only the internal ID; the backend related-field will look up the UID
        res["event_id"] = ui_order.get("event_id") or False
        return res

    # ---------------------------------------------------------------------
    #  XML + RabbitMQ helper exposed to the JS button
    # ---------------------------------------------------------------------
    def send_event_xml(self):
        """
        Called from JS or automatically on paid orders.
        Builds & pretty-prints the XML, then publishes to RabbitMQ.
        """
        self.ensure_one()
        raw_xml    = self._build_raw_xml(self)
        pretty_xml = self._pretty_xml(raw_xml)

        # 1) publish to RabbitMQ
        self._send_to_rabbitmq(pretty_xml)
        # 2) log success
        _logger.info(
            "POS → RabbitMQ sent for order %s (exchange=%s, routing_key=%s)",
            self.name, "sale", "sale.performed"
        )
        return True

    # ---------------------------------------------------------------------
    #  XML helpers
    # ---------------------------------------------------------------------
    def _build_raw_xml(self, order):
        root = ET.Element("attendify")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:noNamespaceSchemaLocation", "tab_item.xsd")

        info = ET.SubElement(root, "info")
        ET.SubElement(info, "sender").text    = "pos"
        ET.SubElement(info, "operation").text = "create"

        tab = ET.SubElement(root, "tab")
        ET.SubElement(tab, "uid").text       = order.partner_id.ref or ""
        ET.SubElement(tab, "event_id").text  = order.event_uid or ""
        ET.SubElement(tab, "timestamp").text = order.date_order.isoformat()

        items = ET.SubElement(tab, "items")
        for line in order.lines:
            item = ET.SubElement(items, "tab_item")
            ET.SubElement(item, "item_name").text = line.product_id.name
            ET.SubElement(item, "quantity").text  = str(line.qty)
            ET.SubElement(item, "price").text     = str(line.price_unit)

        return ET.tostring(root, encoding="utf-8")

    def _pretty_xml(self, xml_bytes: bytes) -> str:
        return minidom.parseString(xml_bytes).toprettyxml(indent="  ")

    # ---------------------------------------------------------------------
    #  Real RabbitMQ publisher
    # ---------------------------------------------------------------------
    def _send_to_rabbitmq(self, xml_string: str):
        try:
            host        = os.getenv("RABBITMQ_HOST")
            port        = int(os.getenv("RABBITMQ_PORT", 5672))
            user        = os.getenv("RABBITMQ_USERNAME")
            password    = os.getenv("RABBITMQ_PASSWORD")
            vhost       = os.getenv("RABBITMQ_VHOST", "/")

            # Target exchange & routing key
            exchange    = "sale"
            routing_key = "sale.performed"

            if not all([host, user, password]):
                _logger.error("RabbitMQ environment variables missing!")
                return

            creds      = pika.PlainCredentials(user, password)
            conn       = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=host,
                    port=port,
                    virtual_host=vhost,
                    credentials=creds,
                )
            )
            channel = conn.channel()
            channel.exchange_declare(
                exchange=exchange,
                exchange_type="direct",
                durable=True
            )
            channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=xml_string.encode("utf-8"),
                properties=pika.BasicProperties(
                    content_type="application/xml",
                    delivery_mode=2,
                ),
            )
            conn.close()
        except Exception as e:
            _logger.exception("Failed to send XML to RabbitMQ: %s", e)

    # ---------------------------------------------------------------------
    #  Automatic push for paid orders
    # ---------------------------------------------------------------------
    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        for order in self:
            try:
                order.send_event_xml()
            except Exception as e:
                _logger.exception(
                    "Failed to process POS order %s for RabbitMQ: %s",
                    order.name, e
                )
        return res
