# -*- coding: utf-8 -*-
from odoo import models, api
import pika
import logging
from dotenv import load_dotenv
import bcrypt
import random
import string
import os
import time

# Load .env right away
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
            _logger.debug("No email for partner %s, skipping RabbitMQ", self.id)
            return

        # Prepare user info
        name_parts    = self.name.split('_')
        user_id       = self.ref or ''
        first_name    = name_parts[0] if name_parts else ''
        last_name     = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
        random_pass   = ''.join(random.choices(
                            string.ascii_letters + string.digits + string.punctuation, k=12))
        hashed        = bcrypt.hashpw(random_pass.encode(), bcrypt.gensalt()).decode()

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
    <password>{hashed}</password>
    <title>{self.title.name if self.title else ''}</title>
  </user>
</attendify>"""

        # RabbitMQ creds from env
        host     = os.getenv("RABBITMQ_HOST")
        port     = int(os.getenv("RABBITMQ_PORT", 5672))
        user     = os.getenv("RABBITMQ_USERNAME")
        pwd      = os.getenv("RABBITMQ_PASSWORD")
        vhost    = os.getenv("RABBITMQ_VHOST")

        routing = {
            'create': 'user.register',
            'update': 'user.update',
            'delete': 'user.delete',
        }.get(operation, 'user.update')

        try:
            _logger.debug("Publishing to RabbitMQ [%s]: %s", operation, xml_message)
            creds      = pika.PlainCredentials(user, pwd)
            params     = pika.ConnectionParameters(host, port, vhost, creds)
            conn       = pika.BlockingConnection(params)
            channel    = conn.channel()
            channel.basic_publish(
                exchange='user-management',
                routing_key=routing,
                body=xml_message,
            )
            conn.close()
            _logger.info("RabbitMQ %s sent for partner %s", operation, self.id)
        except Exception as e:
            _logger.error("RabbitMQ %s failed for partner %s: %s", operation, self.id, e)

    @api.model_create_multi
    def create(self, vals_list):
        # Suppress write() hook during internal writes
        partners = super().with_context(_skip_rabbit_update=True).create(vals_list)
        for p in partners:
            p._send_to_rabbitmq('create')
        return partners

    def write(self, vals):
        skip     = self.env.context.get('_skip_rabbit_update', False)
        important = {'name', 'email', 'ref', 'title_id'}
        changed  = bool(important & set(vals.keys()))
        res      = super().write(vals)
        if not skip and changed:
            for p in self:
                p._send_to_rabbitmq('update')
        return res

    def unlink(self):
        for p in self:
            p._send_to_rabbitmq('delete')
        return super().unlink()