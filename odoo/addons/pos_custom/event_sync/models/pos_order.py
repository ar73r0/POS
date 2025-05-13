import os
import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom
import pika
from odoo import models

_logger = logging.getLogger(__name__)


class PosOrderPublisher(models.Model):
    _inherit = "pos.order"

    def _build_raw_xml(self, order):
        root = ET.Element("attendify")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:noNamespaceSchemaLocation", "tab_item.xsd")

        info = ET.SubElement(root, "info")
        ET.SubElement(info, "sender").text = "pos"
        ET.SubElement(info, "operation").text = "create"

        tab = ET.SubElement(root, "tab")
        ET.SubElement(tab, "uid").text = f"{order.partner_id.ref}"
        ET.SubElement(tab, "event_id").text = "e5" # Temporarily hardcoded
        ET.SubElement(tab, "timestamp").text = order.date_order.isoformat()

        items = ET.SubElement(tab, "items")
        for line in order.lines:
            item = ET.SubElement(items, "tab_item")
            ET.SubElement(item, "item_name").text = line.product_id.name
            ET.SubElement(item, "quantity").text = str(line.qty)
            ET.SubElement(item, "price").text = str(line.price_unit)

        return ET.tostring(root, encoding="utf-8")

    def _pretty_xml(self, xml_bytes: bytes) -> str:
        return minidom.parseString(xml_bytes).toprettyxml(indent="  ")

    def _send_to_rabbitmq(self, xml_string: str):
        try:
            host     = os.getenv("RABBITMQ_HOST")
            port     = int(os.getenv("RABBITMQ_PORT"))
            user     = os.getenv("RABBITMQ_USERNAME")
            password = os.getenv("RABBITMQ_PASSWORD")
            vhost    = os.getenv("RABBITMQ_VHOST")
            exchange = ""
            routing_key = ""

            if not all([host, user, password]):
                _logger.error("RabbitMQ environment variables missing!")
                return

            credentials = pika.PlainCredentials(user, password)
            connection = pika.BlockingConnection(pika.ConnectionParameters(
                host=host,
                port=port,
                virtual_host=vhost,
                credentials=credentials
            ))
            channel = connection.channel()

            
            channel.exchange_declare(exchange=exchange, exchange_type='direct', durable=True)

           
            channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=xml_string.encode("utf-8"),
                properties=pika.BasicProperties(content_type="application/xml", delivery_mode=2)
            )

            _logger.info("XML message sent to RabbitMQ successfully.")

            connection.close()
        except Exception as e:
            _logger.exception("Failed to send XML to RabbitMQ: %s", str(e))

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()

        for order in self:
            try:
                raw_xml = self._build_raw_xml(order)
                pretty_xml = self._pretty_xml(raw_xml)

                
                _logger.info("🧾 [POS XML OUTPUT] Order %s:\n%s", order.name, pretty_xml)

                
                self._send_to_rabbitmq(pretty_xml)

            except Exception as e:
                _logger.exception("Failed to process POS order for RabbitMQ: %s", str(e))

        return res
