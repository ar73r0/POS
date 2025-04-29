@ -0,0 +1,89 @@
from odoo import models, api
import logging
import pika
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom

_logger = logging.getLogger(__name__)

class EventSync(models.Model):
    _inherit = 'event.event'

    def _send_event_to_rabbitmq(self, operation):
        try:
            host = os.environ.get("RABBITMQ_HOST")
            port = int(os.environ.get("RABBITMQ_PORT", 5672))
            vhost = os.environ.get("RABBITMQ_VHOST", "/")
            username = os.environ.get("RABBITMQ_USERNAME")
            password = os.environ.get("RABBITMQ_PASSWORD")

            credentials = pika.PlainCredentials(username, password)
            parameters = pika.ConnectionParameters(
                host=host,
                port=port,
                virtual_host=vhost,
                credentials=credentials
            )

            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            exchange_name = 'event'
            routing_key = 'event.register'
            queue_name = 'pos.event'

            channel.exchange_declare(exchange=exchange_name, exchange_type='direct', durable=True)
            channel.queue_declare(queue=queue_name, durable=True)
            channel.queue_bind(exchange=exchange_name, queue=queue_name, routing_key=routing_key)

            for record in self:
                root = ET.Element("attendify")

                info = ET.SubElement(root, "info")
                ET.SubElement(info, "sender").text = "odoo"
                ET.SubElement(info, "operation").text = operation

                event = ET.SubElement(root, "event")
                ET.SubElement(event, "uid_event").text = f"Odoo{record.id}"
                ET.SubElement(event, "name").text = record.name or ""
                ET.SubElement(event, "start_date").text = record.date_begin.isoformat() if record.date_begin else ""
                ET.SubElement(event, "end_date").text = record.date_end.isoformat() if record.date_end else ""
                ET.SubElement(event, "address").text = record.location or ""
                ET.SubElement(event, "description").text = record.description or ""
                ET.SubElement(event, "max_attendees").text = str(record.seats_max or 0)

                rough_string = ET.tostring(root, 'utf-8')
                reparsed = minidom.parseString(rough_string)
                xml_message = reparsed.toprettyxml(indent="  ")

                channel.basic_publish(
                    exchange=exchange_name,
                    routing_key=routing_key,
                    body=xml_message.encode('utf-8'),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                _logger.info(" Event %s (%s) sent to RabbitMQ as %s", record.name, record.id, operation)

            connection.close()

        except Exception as e:
            _logger.error(" Failed to send event to RabbitMQ: %s", e)

    @api.model_create_multi
    def create(self, vals_list):
        records = super(EventSync, self).create(vals_list)
        for record in records:
            record._send_event_to_rabbitmq('create')
        return records

    def write(self, vals):
        res = super(EventSync, self).write(vals)
        for record in self:
            record._send_event_to_rabbitmq('update')
        return res

    def unlink(self):
        for record in self:
            record._send_event_to_rabbitmq('delete')
        return super(EventSync, self).unlink()