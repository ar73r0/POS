#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RabbitMQ → Odoo sync
• Events  (create / update / delete)
• Event‑attendees (create / delete)
• Maakt automatisch één ticket (event.ticket) aan bij event‑create
  wanneer er een entrance_fee > 0 is.

⚙️ Toegevoegde verbeteringen
─────────────────────────────
* Venue (Many2one naar res.partner) wordt nu correct ingevuld → `venue_id`.
* Ticket krijgt standaard UoM (Unit) zodat website_event_sale de prijs toont.
* Optionele registratielimiet via <registration_limit> of <seats_max>.
* Code cleanup (variabelen hernoemd, extra logging).
"""

import socket
import pika
import xmltodict
import xmlrpc.client
from datetime import datetime
from dotenv import dotenv_values

# ────────────────────────────────────────────────────────────────────────
# ODOO RPC SETUP
# ────────────────────────────────────────────────────────────────────────
cfg = dotenv_values()
DB       = cfg["DATABASE"]
USER     = cfg["EMAIL"]
PWD      = cfg["API_KEY"]
ODOO_HOST = cfg.get("ODOO_HOST", "web")
ODOO_PORT = int(cfg.get("ODOO_PORT", 8069))

# check reachability
socket.create_connection((ODOO_HOST, ODOO_PORT), timeout=5).close()

url    = f"http://{ODOO_HOST}:{ODOO_PORT}/xmlrpc/2/"
common = xmlrpc.client.ServerProxy(url + "common")
uid    = common.authenticate(DB, USER, PWD, {})
models = xmlrpc.client.ServerProxy(url + "object")


def to_dt(date_str: str | None, time_str: str | None = "00:00"):
    """Zet datum + tijd om naar Odoo 'YYYY‑MM‑DD HH:MM:SS' of False."""
    if not date_str:
        return False
    return f"{date_str.strip()} {time_str or '00:00'}:00"

# ────────────────────────────────────────────────────────────────────────
# RABBITMQ SETUP
# ────────────────────────────────────────────────────────────────────────
creds  = pika.PlainCredentials(cfg["RABBITMQ_USERNAME"], cfg["RABBITMQ_PASSWORD"])
params = pika.ConnectionParameters(
    host=cfg["RABBITMQ_HOST"],
    port=int(cfg.get("RABBITMQ_PORT", 5672)),
    virtual_host=cfg.get("RABBITMQ_VHOST", "/"),
    credentials=creds,
)
conn = pika.BlockingConnection(params)
ch   = conn.channel()

exchange, queue = "event", "pos.event"
routing_keys = [
    "event.create", "event.update", "event.delete",
    "attendee.create", "attendee.delete",
]

ch.exchange_declare(exchange, "direct", durable=True)
ch.queue_declare(queue, durable=True)
for rk in routing_keys:
    ch.queue_bind(queue=queue, exchange=exchange, routing_key=rk)
ch.basic_qos(prefetch_count=1)

# ────────────────────────────────────────────────────────────────────────
# HELPER: check of model veld heeft
# ────────────────────────────────────────────────────────────────────────

def model_has_field(model: str, field: str) -> bool:
    return bool(models.execute_kw(
        DB, uid, PWD,
        "ir.model.fields", "search",
        [[("model", "=", model), ("name", "=", field)]],
        {"limit": 1}
    ))

HAS_FEE      = model_has_field("event.event", "entrance_fee")
HAS_GCID     = model_has_field("event.event", "gcid")
HAS_LOC_TXT  = model_has_field("event.event", "location_text")
HAS_VENUE_ID = model_has_field("event.event", "venue_id")

# ─────────────────────────────────────────────────────────────
# HELPER: product.template aanmaken voor event
# ─────────────────────────────────────────────────────────────

def find_or_create_event_product(ev: dict) -> int:
    """Zoek of maak een product.template voor het event zelf."""
    title        = ev.get("title")
    event_uid    = ev.get("uid")
    gcid         = ev.get("gcid")
    fee          = float(ev.get("entrance_fee") or "0.0")
    default_code = event_uid or gcid or title or "event"

    existing = models.execute_kw(
        DB, uid, PWD,
        "product.template", "search_read",
        [[("default_code", "=", default_code)]],
        {"limit": 1, "fields": ["id", "name"]}
    )
    if existing:
        print(f"🔁 Product bestaat al voor event {default_code}: {existing[0]['name']}")
        return existing[0]["id"]

    new_id = models.execute_kw(
        DB, uid, PWD,
        "product.template", "create",
        [{
            "name": title or "Unnamed Event",
            "type": "service",
            "default_code": default_code,
            "list_price": fee,
            "sale_ok": True,
            "purchase_ok": False,
            "description_sale": (ev.get("description") or "") + "\nLocation: " + (ev.get("location") or "")
        }]
    )
    print(f"✅ Product gemaakt voor event {default_code}, id={new_id}")
    return new_id

# ────────────────────────────────────────────────────────────────────────
# HELPER: ticket‑product zoeken / aanmaken
# ────────────────────────────────────────────────────────────────────────

def find_or_create_ticket_product() -> int:
    """Return product_id voor generiek 'Event Registration' product."""
    prod = models.execute_kw(
        DB, uid, PWD,
        "product.product", "search_read",
        [[("name", "=", "Event Registration")]],
        {"limit": 1, "fields": ["id"]}
    )
    if prod:
        return prod[0]["id"]
    return models.execute_kw(
        DB, uid, PWD,
        "product.product", "create",
        [{"name": "Event Registration", "type": "service"}]
    )

PRODUCT_ID = find_or_create_ticket_product()

# ─────────────────────────────────────────────────────────────
# UoM opzoeken (unit)
# ─────────────────────────────────────────────────────────────

def get_unit_uom_id() -> int:
    uom_ids = models.execute_kw(
        DB, uid, PWD,
        "uom.uom", "search",
        [[("category_id.name", "=", "Unit")]],
        {"limit": 1}
    )
    if not uom_ids:
        raise RuntimeError("Geen UoM 'Unit' gevonden")
    return uom_ids[0]

UOM_UNIT_ID = get_unit_uom_id()

# ─────────────────────────────────────────────────────────────
# HELPER: venue partner zoeken / aanmaken
# ─────────────────────────────────────────────────────────────

def find_or_create_venue_partner(name: str) -> int:
    name = name.strip()
    pts = models.execute_kw(
        DB, uid, PWD,
        "res.partner", "search_read",
        [[("name", "=", name)]],
        {"limit": 1, "fields": ["id"]}
    )
    if pts:
        return pts[0]["id"]
    return models.execute_kw(
        DB, uid, PWD,
        "res.partner", "create",
        [{"name": name, "supplier_rank": 0, "customer_rank": 0}]
    )

# ────────────────────────────────────────────────────────────────────────
# MESSAGE HANDLER
# ────────────────────────────────────────────────────────────────────────

def process_message(ch, method, props, body: bytes):
    try:
        msg  = xmltodict.parse(body)
        info = msg["attendify"]["info"]
        op   = info["operation"].lower()

        if "event" in msg["attendify"]:
            handle_event(msg["attendify"]["event"], op)

        elif "event_attendee" in msg["attendify"]:
            handle_attendee(msg["attendify"]["event_attendee"], op)

        else:
            print("⚠️  Onbekend payload‑type")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print("❌  Fout bij verwerken message:", e)

# ────────────────────────────────────────────────────────────────────────
# EVENT CRUD
# ────────────────────────────────────────────────────────────────────────

def handle_event(ev: dict, op: str):
    event_uid = ev.get("uid")
    print(f"\nEVENT {op.upper()}   uid={event_uid}")

    # ── XML → vals ─────────────────────────────────────────────
    vals = {
        "external_uid": event_uid,
        "name":         ev.get("title"),
        "description":  ev.get("description") or "",
        "date_begin":   to_dt(ev.get("start_date"), ev.get("start_time")),
        "date_end":     to_dt(ev.get("end_date"),   ev.get("end_time")),
    }

    if HAS_FEE and ev.get("entrance_fee"):
        try:
            vals["entrance_fee"] = float(ev["entrance_fee"])
        except ValueError:
            print("⚠️  entrance_fee parse error:", ev["entrance_fee"])

    if HAS_GCID and ev.get("gcid"):
        vals["gcid"] = ev["gcid"].strip()

    # Venue vullen
    location = ev.get("location")
    if location and HAS_VENUE_ID:
        vals["venue_id"] = find_or_create_venue_partner(location)
    elif location and HAS_LOC_TXT:
        vals["location_text"] = location

    # Registratielimiet
    limit_val = ev.get("registration_limit") or ev.get("seats_max") or ev.get("limit")
    if limit_val:
        try:
            limit_int = int(limit_val)
            vals["seats_max"]      = limit_int
            vals["seats_limited"] = True
        except ValueError:
            print("⚠️  seats_max parse error:", limit_val)

    # ── zoek bestaande event ──────────────────────────────────
    existing = models.execute_kw(
        DB, uid, PWD,
        "event.event", "search_read",
        [[("external_uid", "=", event_uid)]],
        {"limit": 1, "fields": ["id"]}
    )
    rec_id = existing and existing[0]["id"]
    ctx = {"context": {"skip_rabbit": True}}

    # ── CREATE ────────────────────────────────────────────────
    if op == "create":
        if rec_id:
            print(f"🔁 Bestaat al (id={rec_id})")
            return

        new_id = models.execute_kw(
            DB, uid, PWD,
            "event.event", "create", [vals], ctx)
        print(f"✅ Event aangemaakt  id={new_id}")

        # product.template voor dit event
        find_or_create_event_product(ev)

        # ticket aanmaken wanneer fee > 0
        fee = vals.get("entrance_fee", 0.0)
        if fee and fee > 0:
            ticket_vals = {
                "event_id":       new_id,
                "name":           f"Registration for {vals['name']}",
                "price":          fee,
                "product_id":     PRODUCT_ID,
                "product_uom_id": UOM_UNIT_ID,
            }
            tkt_id = models.execute_kw(
                DB, uid, PWD,
                "event.ticket", "create", [ticket_vals], ctx)
            print(f"      ➜ ticket aangemaakt  id={tkt_id}")

    # ── UPDATE ────────────────────────────────────────────────
    elif op == "update":
        if rec_id:
            models.execute_kw(
                DB, uid, PWD,
                "event.event", "write", [[rec_id], vals], ctx)
            print(f"🔄 Event bijgewerkt  id={rec_id}")
        else:
            print("⚠️  update overgeslagen – uid onbekend")

    # ── DELETE ────────────────────────────────────────────────
    elif op == "delete":
        if rec_id:
            models.execute_kw(
                DB, uid, PWD,
                "event.event", "unlink", [[rec_id]], ctx)
            print(f"🗑️  Event verwijderd  id={rec_id}")
        else:
            print("⚠️  delete overgeslagen – uid onbekend")

# ────────────────────────────────────────────────────────────────────────
# ATTENDEE CRUD
# ────────────────────────────────────────────────────────────────────────

def handle_attendee(ea: dict, op: str):
    user_uid  = ea.get("uid")
    event_uid = ea.get("event_id")
    print(f"\nATTENDEE {op.upper()}  user={user_uid}  event={event_uid}")

    # partner zoeken
    partner = models.execute_kw(
        DB, uid, PWD,
        "res.partner", "search_read",
        [[("ref", "=", user_uid)]],
        {"limit": 1, "fields": ["id"]})
    if not partner:
        print("⚠️  user UID niet gevonden")
        return
    partner_id = partner[0]["id"]

    # event zoeken
    event = models.execute_kw(
        DB, uid, PWD,
        "event.event", "search_read",
        [[("external_uid", "=", event_uid)]],
        {"limit": 1, "fields": ["id"]})
    if not event:
        print("⚠️  event UID niet gevonden")
        return
    event_id = event[0]["id"]

    # bestaande registratie?
    existing = models.execute_kw(
        DB, uid, PWD,
        "event.registration", "search_read",
        [[("event_id", "=", event_id), ("partner_id", "=", partner_id)]],
        {"limit": 1, "fields": ["id"]})
    reg_id = existing and existing[0]["id"]
    ctx = {"context": {"skip_rabbit": True}}

    if op == "create":
        if reg_id:
            print(f"🔁 Reeds geregistreerd (id={reg_id})")
        else:
            new_id = models.execute_kw(
                DB, uid, PWD,
                "event.registration", "create",
                [{"event_id": event_id, "partner_id": partner_id}], ctx)
            print(f"✅ Geregistreerd  id={new_id}")

    elif op == "delete":
        if reg_id:
            models.execute_kw(
                DB, uid, PWD,
                "event.registration", "unlink", [[reg_id]], ctx)
            print(f"🗑️  Afgemeld  id={reg_id}")
        else:
            print("⚠️  niets te verwijderen – registratie niet gevonden")

# ────────────────────────────────────────────────────────────────────────
print("Waiting for RabbitMQ messages …")
ch.basic_consume(queue=queue, on_message_callback=process_message, auto_ack=False)
ch.start_consuming()
