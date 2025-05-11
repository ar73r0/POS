# -*- coding: utf-8 -*-
import os
import time
import string
import random
import logging
import bcrypt
import pika

from dotenv import load_dotenv
from odoo import models, api

load_dotenv()
_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _send_to_rabbitmq(self, operation):
        """Builds & publishes the XML, and logs the payload."""
        if not self.email:
            _logger.debug("No email for partner %s; skipping RabbitMQ send.", self.id)
            return

        # Load RabbitMQ creds
        host  = os.getenv("RABBITMQ_HOST")
        port  = os.getenv("RABBITMQ_PORT")
        user  = os.getenv("RABBITMQ_USERNAME")
        pw    = os.getenv("RABBITMQ_PASSWORD")
        vhost = os.getenv("RABBITMQ_VHOST")
        if not all([host, port, user, pw, vhost]):
            _logger.error(
                "RabbitMQ config incomplete; skipping send: host=%r port=%r user=%r vhost=%r",
                host, port, user, vhost
            )
            return

        # Ensure stable UID
        uid = self.ref
        if not uid:
            uid = f"OD{int(time.time() * 1000)}"
            super(ResPartner, self.with_context(skip_rabbit=True)).write({'ref': uid})

        # Split name on spaces
        parts      = (self.name or "").strip().split()
        first_name = parts[0] if parts else ''
        last_name  = ' '.join(parts[1:]) if len(parts) > 1 else ''

        # Random bcrypt'd password
        chars  = string.ascii_letters + string.digits + string.punctuation
        plain  = ''.join(random.choices(chars, k=12))
        hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

        # Build XML
        xml = f"""<attendify>
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
    <title>{(self.title.name or '') if self.title else ''}</title>
  </user>
</attendify>"""

        _logger.debug("RabbitMQ XML for partner %s (%s):\n%s", self.id, operation, xml)

        # Publish
        try:
            creds = pika.PlainCredentials(user, pw)
            params = pika.ConnectionParameters(
                host=host, port=int(port), virtual_host=vhost, credentials=creds
            )
            routing = {
                'create': 'user.register',
                'update': 'user.update',
                'delete': 'user.delete',
            }.get(operation, 'user.update')

            conn    = pika.BlockingConnection(params)
            channel = conn.channel()
            channel.basic_publish(
                exchange    = 'user-management',
                routing_key = routing,
                body        = xml,
            )
            conn.close()
            _logger.info("RabbitMQ %s sent for partner %s", operation, self.id)
        except Exception:
            _logger.exception("RabbitMQ %s failed for partner %s", operation, self.id)

    @api.model_create_multi
    def create(self, vals_list):
        # Populate any missing ref upfront
        for v in vals_list:
            if not v.get('ref'):
                v['ref'] = f"OD{int(time.time() * 1000)}"

        # Call base create under skip_rabbit so we don't loop back here
        partners = super(ResPartner, self.with_context(skip_rabbit=True)).create(vals_list)

        # Clear the skip flag before returning, so update/write still fire
        partners = partners.with_context(skip_rabbit=False)

        # Send exactly one "create" message per record
        for p in partners:
            _logger.info("Triggering RabbitMQ create for partner %s", p.id)
            p._send_to_rabbitmq('create')
        return partners

    def write(self, vals):
        if self.env.context.get('skip_rabbit'):
            return super(ResPartner, self).write(vals)

        try:
            res = super(ResPartner, self).write(vals)
        except Exception as e:
            if 'serialize' in str(e).lower() and not self.env.context.get('retrying'):
                # If it's a serialization error and we're not already retrying
                _logger.warning("Serialization failure, retrying once for partner %s", self.ids)
                return self.with_context(retrying=True).write(vals)
            raise

        # Only send updates if we're not in a retry
        if not self.env.context.get('retrying'):
            for p in self:
                _logger.info("Triggering RabbitMQ update for partner %s", p.id)
                p.with_context(skip_rabbit=True)._send_to_rabbitmq('update')
        return res

    def unlink(self):
        if self.env.context.get('skip_rabbit'):
            return super(ResPartner, self).unlink()

        for p in self:
            _logger.info("Triggering RabbitMQ delete for partner %s", p.id)
            p._send_to_rabbitmq('delete')
        return super(ResPartner, self).unlink()