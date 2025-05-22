# -*- coding: utf-8 -*-
"""
Odoo extension for res.partner
--------------------------------
* Genereert een stabiele UID (in `ref`)
* Genereert **exact één keer** een random bcrypt-hash in
  `integration_pw_hash`, bedoeld voor externe systemen
* Stuurt bij create / update / delete een XML-bericht naar RabbitMQ

!! Plaintext-wachtwoorden worden NIET opgeslagen; alleen de bcrypt-hash.
"""
from __future__ import annotations

# ────────────────────────────────────────────────────────────────────
# 1) bcrypt – echte lib in productie, stub in tests/CI
# ────────────────────────────────────────────────────────────────────
try:
    import bcrypt                          
except ModuleNotFoundError:                  
    class _StubBCrypt:
        @staticmethod
        def gensalt(*_, **__) -> bytes:
            return b"salt"

        @staticmethod
        def hashpw(pwd: bytes, salt: bytes, *_, **__) -> bytes:
            return b"fakehash"

    bcrypt = _StubBCrypt()                           

# ────────────────────────────────────────────────────────────────────
# 2) stdlib / extern
# ────────────────────────────────────────────────────────────────────
import os
import time
import string
import random
import logging
import pika
from dotenv import load_dotenv, dotenv_values           # fallback voor tests

from odoo import models, fields, api

load_dotenv()
_logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
# 3) Helper: RabbitMQ-config ophalen (prod + unit-tests)
# ────────────────────────────────────────────────────────────────────
def _get_rmq_cfg() -> dict[str, str | None]:
    """
    Geeft een dict met RabbitMQ-parameters terug.  Eerst wordt de echte
    omgeving (`os.getenv`) geraadpleegd; ontbrekende keys worden
    opgevuld met waarden uit `.env` (of – in de unit-tests – het stub-
    dict `GOOD_ENV`).
    """
    env_fallback = dotenv_values()
    return {
        "host":  os.getenv("RABBITMQ_HOST")     or env_fallback.get("RABBITMQ_HOST"),
        "port":  os.getenv("RABBITMQ_PORT")     or env_fallback.get("RABBITMQ_PORT"),
        "user":  os.getenv("RABBITMQ_USERNAME") or env_fallback.get("RABBITMQ_USERNAME"),
        "pw":    os.getenv("RABBITMQ_PASSWORD") or env_fallback.get("RABBITMQ_PASSWORD"),
        "vhost": os.getenv("RABBITMQ_VHOST")    or env_fallback.get("RABBITMQ_VHOST"),
    }

# ────────────────────────────────────────────────────────────────────
# 4) Het eigenlijke model
# ────────────────────────────────────────────────────────────────────
class ResPartner(models.Model):
    _inherit = "res.partner"

    # Eenmalige integratie-hash (wordt niet gebruikt voor Odoo-login)
    integration_pw_hash = fields.Char(
        string="Integration password (bcrypt)",
        readonly=True,
        copy=False,
        help="Eenmalig gegenereerde bcrypt-hash voor externe systemen.",
    )

    # ────────────────────────────────────────────────────────────
    # RabbitMQ helper
    # ────────────────────────────────────────────────────────────
    def _send_to_rabbitmq(self, operation: str) -> None:
        """
        Bouwt en verstuurt een Attendify-compatibel XML-bericht.

        • Genereert bij de eerste oproep een random wachtwoord en slaat
          de bcrypt-hash op in `integration_pw_hash`.
        • Bij volgende oproepen wordt precies diezelfde hash hergebruikt.
        """
        if not self.email:                          # geen e-mail → overslaan
            _logger.debug(
                "No email for partner %s; skipping RabbitMQ send.", self.id
            )
            return

        # ------------------------------------------------------------------
        # RabbitMQ-config ophalen
        # ------------------------------------------------------------------
        cfg = _get_rmq_cfg()
        host, port, user, pw, vhost = cfg.values()
        if not all([host, port, user, pw, vhost]):
            _logger.error(
                "RabbitMQ config incomplete; skipping send: host=%r port=%r "
                "user=%r vhost=%r",
                host, port, user, vhost,
            )
            return

        # ------------------------------------------------------------------
        # Stabiele UID in `ref`
        # ------------------------------------------------------------------
        uid = self.ref
        if not uid:
            uid = f"OD{int(time.time() * 1000)}"
            self.with_context(skip_rabbit=True).write({"ref": uid})

        # ------------------------------------------------------------------
        # Naam opsplitsen in voor- en achternaam
        # ------------------------------------------------------------------
        parts = (self.name or "").strip().split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        # ------------------------------------------------------------------
        # Bestaande hash hergebruiken of éénmalig genereren
        # ------------------------------------------------------------------
        hashed = self.integration_pw_hash
        if not hashed:
            chars = string.ascii_letters + string.digits + string.punctuation
            plain = "".join(random.choices(chars, k=12))
            hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
            # Hash opslaan zonder Rabbit-lus
            self.with_context(skip_rabbit=True).write({"integration_pw_hash": hashed})

        # ------------------------------------------------------------------
        # XML-payload bouwen
        # ------------------------------------------------------------------
        title_txt = (self.title.name or "") if self.title else ""
        xml = f"""<attendify>
  <info><sender>odoo</sender><operation>{operation}</operation></info>
  <user>
    <uid>{uid}</uid>
    <first_name>{first_name}</first_name>
    <last_name>{last_name}</last_name>
    <email>{self.email}</email>
    <password>{hashed}</password>
    <title>{title_txt}</title>
    <is_admin>{"true" if getattr(self, "is_admin", False) else "false"}</is_admin>
  </user>
</attendify>"""

        _logger.debug(
            "RabbitMQ XML for partner %s (%s):\n%s", self.id, operation, xml
        )

        # ------------------------------------------------------------------
        # Publish naar RabbitMQ
        # ------------------------------------------------------------------
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

    # ────────────────────────────────────────────────────────────
    # CRUD-overrides
    # ────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("skip_rabbit"):
            return super().create(vals_list)

        # Voeg ref toe voor eventuele duplicates
        for v in vals_list:
            v.setdefault("ref", f"OD{int(time.time() * 1000)}")

        partners = super(
            ResPartner, self.with_context(skip_rabbit=True)
        ).create(vals_list)

        for p in partners:
            _logger.info("Triggering RabbitMQ create for partner %s", p.id)
            p._send_to_rabbitmq("create")
        return partners

    def write(self, vals):
        if self.env.context.get("skip_rabbit"):
            return super().write(vals)

        try:
            res = super().write(vals)
        except Exception as e:
            # Eén retry bij serialization-conflict
            if "serialize" in str(e).lower() and not self.env.context.get("retrying"):
                _logger.warning(
                    "Serialization failure, retrying once for partner %s", self.ids
                )
                return self.with_context(retrying=True).write(vals)
            raise

        if not self.env.context.get("retrying"):
            for p in self:
                _logger.info("Triggering RabbitMQ update for partner %s", p.id)
                p.with_context(skip_rabbit=True)._send_to_rabbitmq("update")
        return res

    def unlink(self):
        if self.env.context.get("skip_rabbit"):
            return super().unlink()

        for p in self:
            _logger.info("Triggering RabbitMQ delete for partner %s", p.id)
            p._send_to_rabbitmq("delete")
        return super().unlink()
