#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RabbitMQ → Odoo sync
• Events  (create / update / delete)
• Event-attendees (create / delete)
• Maakt automatisch één ticket (event.ticket) aan bij event-create
  wanneer er een entrance_fee > 0 is.
"""
import socket, pika, xmltodict, xmlrpc.client
from datetime import datetime
from dotenv import dotenv_values

# ────────────────────────────────────────────────────────────────────────
# ODOO RPC SETUP
# ────────────────────────────────────────────────────────────────────────
cfg = dotenv_values()
ODOO_HOST = cfg.get("ODOO_HOST", "web")
ODOO_PORT = int(cfg.get("ODOO_PORT", 8069))

# check reachability
socket.create_connection((ODOO_HOST, ODOO_PORT), timeout=5).close()

url    = f"http://{ODOO_HOST}:{ODOO_PORT}/xmlrpc/2/"
common = xmlrpc.client.ServerProxy(url + "common")
uid    = common.authenticate(cfg["DATABASE"], cfg["EMAIL"], cfg["API_KEY"], {})
models = xmlrpc.client.ServerProxy(url + "object")

def to_dt(date_str, time_str="00:00"):
    if not date_str:
        return False
    return f"{date_str} {time_str or '00:00'}:00"

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
def model_has_field(model, field):
    return bool(models.execute_kw(
        cfg["DATABASE"], uid, cfg["API_KEY"],
        "ir.model.fields", "search",
        [[("model", "=", model), ("name", "=", field)]],
        {"limit": 1}
    ))

HAS_FEE   = model_has_field("event.event",   "entrance_fee")
HAS_GCID  = model_has_field("event.event",   "gcid")
HAS_LOC_TXT = model_has_field("event.event", "location_text")  # optioneel char-veld

# ────────────────────────────────────────────────────────────────────────
# HELPER: ticket-product zoeken / aanmaken
# ────────────────────────────────────────────────────────────────────────
def find_or_create_ticket_product():
    """Return product_id for generic 'Event Registration' service product."""
    prod = models.execute_kw(
        cfg["DATABASE"], uid, cfg["API_KEY"],
        "product.product", "search_read",
        [[("name", "=", "Event Registration")]],
        {"limit": 1, "fields": ["id"]}
    )
    if prod:
        return prod[0]["id"]
    return models.execute_kw(
        cfg["DATABASE"], uid, cfg["API_KEY"],
        "product.product", "create",
        [{"name": "Event Registration", "type": "service"}]
    )

PRODUCT_ID = find_or_create_ticket_product()

# ────────────────────────────────────────────────────────────────────────
# MESSAGE HANDLER
# ────────────────────────────────────────────────────────────────────────
def process_message(ch, method, props, body):
    try:
        msg  = xmltodict.parse(body)
        info = msg["attendify"]["info"]
        op   = info["operation"].lower()

        if "event" in msg["attendify"]:
            handle_event(msg["attendify"]["event"], op)

        elif "event_attendee" in msg["attendify"]:
            handle_attendee(msg["attendify"]["event_attendee"], op)

        else:
            print("onbekend payload-type")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print("error processing message:", e)

# ────────────────────────────────────────────────────────────────────────
# EVENT CRUD
# ────────────────────────────────────────────────────────────────────────
def handle_event(ev, op):
    uid_in = ev.get("uid")
    print(f"\nEVENT {op.upper()}   uid={uid_in}")

    # ── map XML → vals ─────────────────────────────────────────────
    vals = {
        "external_uid": uid_in,
        "name":         ev.get("title"),
        "description":  ev.get("description") or "",
        "date_begin":   to_dt(ev.get("start_date"), ev.get("start_time")),
        "date_end":     to_dt(ev.get("end_date"),   ev.get("end_time")),
    }
    if HAS_FEE and ev.get("entrance_fee"):
        try:
            vals["entrance_fee"] = float(ev["entrance_fee"])
        except ValueError:
            print("entrance_fee parse error:", ev["entrance_fee"])
    if HAS_GCID and ev.get("gcid"):
        vals["gcid"] = ev["gcid"].strip()
    if HAS_LOC_TXT and ev.get("location"):
        vals["location_text"] = ev["location"]

    # ── lookup existing event ─────────────────────────────────────
    existing = models.execute_kw(
        cfg["DATABASE"], uid, cfg["API_KEY"],
        "event.event", "search_read",
        [[("external_uid", "=", uid_in)]],
        {"limit": 1, "fields": ["id"]}
    )
    rec_id = existing and existing[0]["id"]
    ctx = {"context": {"skip_rabbit": True}}

    # ── CREATE ────────────────────────────────────────────────────
    if op == "create":
        if rec_id:
            print("already exists (id=%s)" % rec_id)
            return

        new_id = models.execute_kw(
            cfg["DATABASE"], uid, cfg["API_KEY"],
            "event.event", "create", [vals], ctx)
        print("event created  id=%s" % new_id)

        # ticket aanmaken als entrance_fee > 0
        fee = vals.get("entrance_fee", 0.0)
        if fee and fee > 0:
            ticket_vals = {
                "event_id": new_id,
                "name":     f"Registration for {vals['name']}",
                "price":    fee,
                "product_id": PRODUCT_ID,
            }
            tkt_id = models.execute_kw(
                cfg["DATABASE"], uid, cfg["API_KEY"],
                "event.ticket", "create", [ticket_vals], ctx)
            print("      ➜ ticket created  id=%s" % tkt_id)

    # ── UPDATE ────────────────────────────────────────────────────
    elif op == "update":
        if rec_id:
            models.execute_kw(
                cfg["DATABASE"], uid, cfg["API_KEY"],
                "event.event", "write", [[rec_id], vals], ctx)
            print("event updated  id=%s" % rec_id)
        else:
            print("update skipped – uid unknown")

    # ── DELETE ────────────────────────────────────────────────────
    elif op == "delete":
        if rec_id:
            models.execute_kw(
                cfg["DATABASE"], uid, cfg["API_KEY"],
                "event.event", "unlink", [[rec_id]], ctx)
            print("event deleted  id=%s" % rec_id)
        else:
            print("delete skipped – uid unknown")

# ────────────────────────────────────────────────────────────────────────
# ATTENDEE CRUD
# ────────────────────────────────────────────────────────────────────────
def handle_attendee(ea, op):
    user_uid  = ea.get("uid")
    event_uid = ea.get("event_id")
    print(f"\nATTENDEE {op.upper()}  user={user_uid}  event={event_uid}")

    # partner zoeken
    partner = models.execute_kw(
        cfg["DATABASE"], uid, cfg["API_KEY"],
        "res.partner", "search_read",
        [[("ref", "=", user_uid)]],
        {"limit": 1, "fields": ["id"]})
    if not partner:
        print("user UID not found")
        return
    partner_id = partner[0]["id"]

    # event zoeken
    event = models.execute_kw(
        cfg["DATABASE"], uid, cfg["API_KEY"],
        "event.event", "search_read",
        [[("external_uid", "=", event_uid)]],
        {"limit": 1, "fields": ["id"]})
    if not event:
        print("event UID not found")
        return
    event_id = event[0]["id"]

    # bestaande registratie?
    existing = models.execute_kw(
        cfg["DATABASE"], uid, cfg["API_KEY"],
        "event.registration", "search_read",
        [[("event_id", "=", event_id), ("partner_id", "=", partner_id)]],
        {"limit": 1, "fields": ["id"]})
    reg_id = existing and existing[0]["id"]
    ctx = {"context": {"skip_rabbit": True}}

    if op == "create":
        if reg_id:
            print("already registered (id=%s)" % reg_id)
        else:
            new_id = models.execute_kw(
                cfg["DATABASE"], uid, cfg["API_KEY"],
                "event.registration", "create",
                [{"event_id": event_id, "partner_id": partner_id}], ctx)
            print("registered  id=%s" % new_id)

    elif op == "delete":
        if reg_id:
            models.execute_kw(
                cfg["DATABASE"], uid, cfg["API_KEY"],
                "event.registration", "unlink", [[reg_id]], ctx)
            print("unregistered  id=%s" % reg_id)
        else:
            print("nothing to delete - registration not found")

# ────────────────────────────────────────────────────────────────────────
print("Waiting for RabbitMQ messages …")
ch.basic_consume(queue=queue, on_message_callback=process_message, auto_ack=False)
ch.start_consuming()
