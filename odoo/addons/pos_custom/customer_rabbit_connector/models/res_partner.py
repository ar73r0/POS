# -*- coding: utf-8 -*-
import os
import time
import string
import random
import logging
import bcrypt
import pika
import xml.etree.ElementTree as ET

from dotenv import load_dotenv
from odoo import models, api

# Load .env from your module root (or project root) so os.getenv() sees it
load_dotenv()

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _send_to_rabbitmq(self, operation):
        """
        Sends customer data as XML to RabbitMQ using a direct exchange.
        operation can be 'create', 'update', or 'delete'.
        """
        if not self.email:
            _logger.debug("No email for partner %s, skipping RabbitMQ send.", self.id)
            return

        # Pull RabbitMQ connection info from env
        rabbit_host     = os.getenv("RABBITMQ_HOST")
        rabbit_port     = os.getenv("RABBITMQ_PORT")
        rabbit_user     = os.getenv("RABBITMQ_USERNAME")
        rabbit_pass     = os.getenv("RABBITMQ_PASSWORD")
        rabbit_vhost    = os.getenv("RABBITMQ_VHOST")

        # If any are missing, log and skip
        if not all([rabbit_host, rabbit_port, rabbit_user, rabbit_pass, rabbit_vhost]):
            _logger.error(
                "RabbitMQ config incomplete, skipping send: host=%r port=%r user=%r vhost=%r",
                rabbit_host, rabbit_port, rabbit_user, rabbit_vhost
            )
            return

        # Split name into first / last
        name_parts = (self.name or '').split('_')
        uid        = self.ref or ''
        first_name = name_parts[0] if name_parts else ''
        last_name  = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

        # Generate bcrypt’d random password
        chars     = string.ascii_letters + string.digits + string.punctuation
        rand_pass = ''.join(random.choices(chars, k=12))
        salt      = bcrypt.gensalt()
        hashed    = bcrypt.hashpw(rand_pass.encode('utf-8'), salt).decode('utf-8')

        xml_message = f"""
<attendify>
  <info>
    <sender>odoo</sender>
    <operation>{operation}</operation>
  </info>
  <user>
    <uid>{uid}</uid>
    <first_name>{first_name}</first_name>
    <last_name>{last_name}</last_name>
    <email>{self.email}</email>
    <password>{hashed}</password>
    <title>{self.title.name if self.title else ''}</title>
  </user>
</attendify>
"""

        credentials = pika.PlainCredentials(rabbit_user, rabbit_pass)
        params = pika.ConnectionParameters(
            host=rabbit_host,
            port=int(rabbit_port),
            virtual_host=rabbit_vhost,
            credentials=credentials,
        )
        exchange = 'user-management'
        routing_map = {
            'create': 'user.register',
            'update': 'user.update',
            'delete': 'user.delete',
        }
        routing = routing_map.get(operation, 'user.update')

        try:
            _logger.debug("Publishing to RabbitMQ [%s→%s]: %s", exchange, routing, xml_message)
            conn    = pika.BlockingConnection(params)
            channel = conn.channel()
            channel.basic_publish(exchange=exchange, routing_key=routing, body=xml_message)
            conn.close()
            _logger.info("RabbitMQ %s sent for partner %s", operation, self.id)
        except Exception as e:
            _logger.error("RabbitMQ %s failed for partner %s: %s", operation, self.id, e)

    @api.model_create_multi
    def create(self, vals_list):
        # suppress update‐hook during the internal create/write
        partners = super(ResPartner, self.with_context(skip_rabbit_update=True)).create(vals_list)
        for p in partners:
            _logger.debug("Triggering RabbitMQ create for partner %s", p.id)
            p._send_to_rabbitmq('create')
        return partners

    def write(self, vals):
        res = super(ResPartner, self).write(vals)
        if not self.env.context.get('skip_rabbit_update'):
            for p in self:
                _logger.debug("Triggering RabbitMQ update for partner %s", p.id)
                p._send_to_rabbitmq('update')
        return res

    def unlink(self):
        for p in self:
            _logger.debug("Triggering RabbitMQ delete for partner %s", p.id)
            p._send_to_rabbitmq('delete')
        return super(ResPartner, self).unlink()
