# -*- coding: utf-8 -*-
"""
Odoo extension for res.partner
--------------------------------
* Generates a stable UID (stored in `ref`)
* Generates **exactly once** a random bcrypt-hashed password, stored in
  `integration_pw_hash`, for use by external services
* Publishes XML messages to RabbitMQ on create / update / delete

!! Plaintext wachtwoorden worden NIET opgeslagen; alleen de bcrypt-hash.
"""

import os
import time
import string
import random
import logging
import bcrypt
import pika

from dotenv import load_dotenv
from odoo import models, fields, api

load_dotenv()
_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Eenmalige integratie‑hash (geen login voor Odoo zelf)
    integration_pw_hash = fields.Char(
        string="Integration password (bcrypt)",
        readonly=True,
        copy=False,
        help="Eenmalig gegenereerde bcrypt‑hash voor externe systemen."
    )

    # RabbitMQ helper
    def _send_to_rabbitmq(self, operation: str):
        """Bouwt en verstuurt XML naar RabbitMQ.

        * Maakt bij eerste oproep een random wachtwoord en slaat de hash op
          in ``integration_pw_hash``.
        * Hergebruikt de bestaande hash bij latere calls.
        """
        if not self.email:
            _logger.debug("No email for partner %s; skipping RabbitMQ send.", self.id)
            return

        # RabbitMQ‑config
        host = os.getenv("RABBITMQ_HOST")
        port = os.getenv("RABBITMQ_PORT")
        user = os.getenv("RABBITMQ_USERNAME")
        pw = os.getenv("RABBITMQ_PASSWORD")
        vhost = os.getenv("RABBITMQ_VHOST")
        if not all([host, port, user, pw, vhost]):
            _logger.error(
                "RabbitMQ config incomplete; skipping send: host=%r port=%r user=%r vhost=%r",
                host, port, user, vhost,
            )
            return

        # Zorg voor stabiele UID in `ref`
        uid = self.ref
        if not uid:
            uid = f"OD{int(time.time() * 1000)}"
            super(ResPartner, self.with_context(skip_rabbit=True)).write({"ref": uid})

        # Splits naam
        parts = (self.name or "").strip().split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        # Pak bestaande hash óf genereer eenmalig
        hashed = self.integration_pw_hash
        if not hashed:
            chars = string.ascii_letters + string.digits + string.punctuation
            plain = "".join(random.choices(chars, k=12))
            hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
            # Bewaar hash zonder Rabbit‑lus
            self.with_context(skip_rabbit=True).write({"integration_pw_hash": hashed})

        # Bouw XML‑payload
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

        # Publish naar RabbitMQ
        try:
            creds = pika.PlainCredentials(user, pw)
            params = pika.ConnectionParameters(
                host=host, port=int(port), virtual_host=vhost, credentials=creds
            )
            routing = {
                "create": "user.register",
                "update": "user.update",
                "delete": "user.delete",
            }.get(operation, "user.update")

            conn = pika.BlockingConnection(params)
            channel = conn.channel()
            channel.basic_publish(
                exchange="user-management",
                routing_key=routing,
                body=xml,
            )
            conn.close()
            _logger.info("RabbitMQ %s sent for partner %s", operation, self.id)
        except Exception:
            _logger.exception("RabbitMQ %s failed for partner %s", operation, self.id)

    # CRUD overrides
    @api.model_create_multi
    def create(self, vals_list):
        # Zorg dat `ref` gevuld is vóórdat super() aanmaakt, om duplicates te vermijden
        for v in vals_list:
            if not v.get("ref"):
                v["ref"] = f"OD{int(time.time() * 1000)}"

        # Maak partners zonder Rabbit‑lus
        partners = super(ResPartner, self.with_context(skip_rabbit=True)).create(vals_list)
        partners = partners.with_context(skip_rabbit=False)  # Cleanup flag

        # Eén create‑boodschap per record
        for p in partners:
            _logger.info("Triggering RabbitMQ create for partner %s", p.id)
            p._send_to_rabbitmq("create")
        return partners

    def write(self, vals):
        if self.env.context.get("skip_rabbit"):
            return super(ResPartner, self).write(vals)

        try:
            res = super(ResPartner, self).write(vals)
        except Exception as e:
            if "serialize" in str(e).lower() and not self.env.context.get("retrying"):
                _logger.warning("Serialization failure, retrying once for partner %s", self.ids)
                return self.with_context(retrying=True).write(vals)
            raise

        # Stuur update‑boodschap (niet in retry‑modus)
        if not self.env.context.get("retrying"):
            for p in self:
                _logger.info("Triggering RabbitMQ update for partner %s", p.id)
                p.with_context(skip_rabbit=True)._send_to_rabbitmq("update")
        return res

    def unlink(self):
        if self.env.context.get("skip_rabbit"):
            return super(ResPartner, self).unlink()

        for p in self:
            _logger.info("Triggering RabbitMQ delete for partner %s", p.id)
            p._send_to_rabbitmq("delete")
        return super(ResPartner, self).unlink()
