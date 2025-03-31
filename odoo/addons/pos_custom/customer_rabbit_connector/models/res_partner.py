from odoo import models, api
import pika
import xml.etree.ElementTree as ET
import logging
from dotenv import dotenv_values

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _send_to_rabbitmq(self, operation):
        """
        Sends customer data as XML to RabbitMQ using a direct exchange.
        """

        # Only send messages if there is an email
        if not self.email:
            _logger.debug("No email found for partner ID %s. Message not sent.", self.id)
            return

        # Split name into first and last
        name_parts = self.name.split(' ')
        first_name = name_parts[0] if name_parts else ''
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ''

        # Build the XML message
        xml_message = f"""
<attendify>
    <info>
        <sender>pos</sender>
        <operation>pos.{operation}</operation>
    </info>
    <user>
        <first_name>{first_name}</first_name>
        <last_name>{last_name}</last_name>
        <email>{self.email}</email>
        <title>{self.title.name if self.title else ''}</title>
    </user>
</attendify>
"""

        # Load RabbitMQ credentials from .en
        config = dotenv_values()
        rabbit_host = config["RABBITMQ_HOST"]
        rabbit_port = int(config["RABBITMQ_PORT"])
        rabbit_user = config["RABBITMQ_USERNAME"]
        rabbit_password = config["RABBITMQ_PASSWORD"]
        rabbit_vhost = config["RABBITMQ_VHOST"]

        # The exchange, routing key, and queue settings
        exchange_main = "user-management"
        routing_main = "user.update"
        queue_main = "pos.user"

        try:
            _logger.debug("Attempting to send RabbitMQ message for partner %s: %s", self.id, xml_message)

            # Build the connection credebtials
            credentials = pika.PlainCredentials(rabbit_user, rabbit_password)
            params = pika.ConnectionParameters(
                host=rabbit_host,
                port=rabbit_port,
                virtual_host=rabbit_vhost,
                credentials=credentials
            )
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            # Declare the direct exchange
            channel.exchange_declare(exchange=exchange_main, exchange_type='direct', durable=True)

            # Declare the queue
            channel.queue_declare(queue=queue_main, durable=True)

            # Bind queue to exchange with routing key
            channel.queue_bind(exchange=exchange_main, queue=queue_main, routing_key=routing_main)

            # Publish message to the exchange with the routing key
            channel.basic_publish(
                exchange=exchange_main,
                routing_key=routing_main,
                body=xml_message
            )
            connection.close()

            _logger.info("Message sent to RabbitMQ for partner %s: %s", self.id, xml_message)
        except Exception as e:
            _logger.error("Error sending message to RabbitMQ for partner %s: %s", self.id, e)

    @api.model_create_multi
    def create(self, vals_list):
        _logger.debug("Creating partner(s) with values: %s", vals_list)
        records = super(ResPartner, self).create(vals_list)
        return records

    def write(self, vals):
        _logger.debug("Updating partner(s) with ID(s): %s and values: %s", self.ids, vals)
        res = super(ResPartner, self).write(vals)
        for record in self:
            _logger.debug("Triggering RabbitMQ update for partner ID %s", record.id)
            record._send_to_rabbitmq('update')
        return res
