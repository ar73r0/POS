from odoo import models,fields, api
import pika
import xml.etree.ElementTree as ET
import logging
from dotenv import dotenv_values
try:
    import bcrypt
except ModuleNotFoundError:
    class _StubBCrypt:
        @staticmethod
        def gensalt(*_, **__): return b"salt"
        @staticmethod
        def hashpw(pwd: bytes, salt: bytes, *_, **__): return b"fakehash"
    bcrypt = _StubBCrypt()
import random
import string
import os
import time

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
        name_parts = self.name.split('_')
        #user_id = f"OD{int(time.time() * 1000)}"
        user_id = self.ref
        first_name = name_parts[0] if name_parts else ''
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ''
        is_admin = fields.Boolean(string="Is Admin", default=False)


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
        <uid>{user_id}</uid>
        <first_name>{first_name}</first_name>
        <last_name>{last_name}</last_name>
        <email>{self.email}</email>
        <password>{password}</password>
        <title>{self.title.name if self.title else ''}</title>
         <is_admin>{"true" if self.is_admin else "false"}</is_admin>
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
        _logger.debug("Creating partners: %s", vals_list)
        records = []

        for vals in vals_list:
            uid = f"OD{int(time.time() * 1000)}"
            vals["ref"] = uid 
            record = super(ResPartner, self).create([vals])[0]
            record._send_to_rabbitmq("create") 
            records.append(record)

        return self.browse([r.id for r in records])

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
