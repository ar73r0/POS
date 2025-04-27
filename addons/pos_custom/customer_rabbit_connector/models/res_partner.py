from odoo import models, api
import pika
import xml.etree.ElementTree as ET
import logging
from dotenv import dotenv_values
import bcrypt
import random
import string
import os

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _send_to_rabbitmq(self, operation):
        """
        Sends customer data as XML to RabbitMQ using a direct exchange.
        operation can be 'register', 'update', or 'delete'.
        """

        # Only send messages if there is an email
        if not self.email:
            _logger.debug("No email found for partner ID %s. Message not sent.", self.id)
            return

        # Split name into first and last
        name_parts = self.name.split(' ')
        first_name = name_parts[0] if name_parts else ''
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ''

        characters = string.ascii_letters + string.digits + string.punctuation
        random_password = ''.join(random.choices(characters, k=12))
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(random_password.encode('utf-8'), salt)


        password  = hashed.decode('utf-8')

        # Build the XML message
        xml_message = f"""
<attendify>
    <info>
        <sender>odoo</sender>
        <operation>{operation}</operation>
    </info>
    <user>
        <first_name>{first_name}</first_name>
        <last_name>{last_name}</last_name>
        <email>{self.email}</email>
        <password>{password}</password>
        <title>{self.title.name if self.title else ''}</title>
    </user>
</attendify>
"""

        # Load RabbitMQ credentials from .env
        rabbit_host     = os.getenv("RABBITMQ_HOST")
        rabbit_port     = int(os.getenv("RABBITMQ_PORT",    5672))
        rabbit_user     = os.getenv("RABBITMQ_USERNAME")
        rabbit_password = os.getenv("RABBITMQ_PASSWORD")
        rabbit_vhost    = os.getenv("RABBITMQ_VHOST")

        # exchange and queue settings
        exchange_main = "user-management"
        queue_main = "pos.user"

        # routing key mapping
        routing_key_map = {
            'create': 'user.register',
            'update': 'user.update',
            'delete': 'user.delete'
        }
        routing_key = routing_key_map.get(operation, 'user.update')

        try:
            _logger.debug("Attempting to send RabbitMQ message for partner %s: %s", self.id, xml_message)

            credentials = pika.PlainCredentials(rabbit_user, rabbit_password)
            params = pika.ConnectionParameters(
                host=rabbit_host,
                port=rabbit_port,
                virtual_host=rabbit_vhost,
                credentials=credentials
            )
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            # Publish the message
            channel.basic_publish(
                exchange=exchange_main,
                routing_key=routing_key,
                body=xml_message
            )
            connection.close()

            _logger.info("Message sent to RabbitMQ for partner %s [op=%s]: %s", self.id, operation, xml_message)
        except Exception as e:
            _logger.error("Error sending message to RabbitMQ for partner %s [op=%s]: %s", self.id, operation, e)

    @api.model_create_multi
    def create(self, vals_list):
        _logger.debug("Creating partner(s) with values: %s", vals_list)
        records = super(ResPartner, self).create(vals_list)
        # after creating, send user.register
        for record in records:
            _logger.debug("Triggering RabbitMQ register for partner ID %s", record.id)
            record._send_to_rabbitmq('create')
        return records

    def write(self, vals):
        _logger.debug("Updating partner(s) with ID(s): %s and values: %s", self.ids, vals)
        res = super(ResPartner, self).write(vals)
        for record in self:
            _logger.debug("Triggering RabbitMQ update for partner ID %s", record.id)
            record._send_to_rabbitmq('update')
        return res

    def unlink(self):
        for record in self:
            _logger.debug("Triggering RabbitMQ delete for partner ID %s", record.id)
            record._send_to_rabbitmq('delete')
        return super(ResPartner, self).unlink()
