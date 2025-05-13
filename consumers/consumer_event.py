import socket
import pika, xmltodict, xmlrpc.client
from datetime import datetime
from dotenv import dotenv_values

# ── Odoo RPC
cfg = dotenv_values()
ODOO_HOST = cfg.get("ODOO_HOST", "web")
ODOO_PORT = int(cfg.get("ODOO_PORT", 8069))
socket.create_connection((ODOO_HOST, ODOO_PORT), timeout=5).close()

url    = f"http://{ODOO_HOST}:{ODOO_PORT}/xmlrpc/2/"
common = xmlrpc.client.ServerProxy(url + "common")
uid    = common.authenticate(cfg["DATABASE"], cfg["EMAIL"], cfg["API_KEY"], {})
models = xmlrpc.client.ServerProxy(url + "object")

def to_dt(date_str, time_str="00:00"):
    if not date_str:
        return False
    return f"{date_str} {time_str or '00:00'}:00"

# ── RabbitMQ setup
creds = pika.PlainCredentials(cfg["RABBITMQ_USERNAME"], cfg["RABBITMQ_PASSWORD"])
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

# ── Helpers for optional Odoo fields
def model_has_field(model, field):
    return bool(models.execute_kw(
        cfg["DATABASE"], uid, cfg["API_KEY"],
        "ir.model.fields", "search",
        [[("model", "=", model), ("name", "=", field)]],
        {"limit": 1}
    ))
HAS_FEE  = model_has_field("event.event", "entrance_fee")
HAS_GCID = model_has_field("event.event", "gcid")

# ── Message handler
def process_message(ch, method, props, body):
    try:
        msg = xmltodict.parse(body)
        info = msg["attendify"]["info"]
        op   = info["operation"].lower()

        if "event" in msg["attendify"]:
            handle_event(msg["attendify"]["event"], op)

        elif "event_attendee" in msg["attendify"]:
            handle_attendee(msg["attendify"]["event_attendee"], op)

        else:
            print("✖  Unknown payload")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print("Error processing message:", e)

# ── Event CRUD 
def handle_event(ev, op):
    vals = {
        "external_uid": ev.get("uid"),
        "name":         ev.get("title"),
        "description":  ev.get("description") or "",
        "date_begin":   to_dt(ev.get("start_date"), ev.get("start_time")),
        "date_end":     to_dt(ev.get("end_date"),   ev.get("end_time")),
    }
    if HAS_FEE  and ev.get("entrance_fee"):
        vals["entrance_fee"] = float(ev["entrance_fee"])
    if HAS_GCID and ev.get("gcid"):
        vals["gcid"] = ev["gcid"]

    # lookup
    existing = models.execute_kw(cfg["DATABASE"], uid, cfg["API_KEY"],
        "event.event", "search_read",
        [[("external_uid", "=", vals["external_uid"])]],
        {"limit": 1, "fields": ["id"]})
    rec_id = existing and existing[0]["id"]
    ctx = {"context": {"skip_rabbit": True}}

    if op == "create":
        if rec_id:
            print("skip create - already exists", rec_id)
        else:
            new_id = models.execute_kw(cfg["DATABASE"], uid, cfg["API_KEY"],
                "event.event", "create", [vals], ctx)
            print("created event", new_id)

    elif op == "update":
        if rec_id:
            models.execute_kw(cfg["DATABASE"], uid, cfg["API_KEY"],
                "event.event", "write", [[rec_id], vals], ctx)
            print("updated event", rec_id)
        else:
            print("update skipped - uid unknown", vals["external_uid"])

    elif op == "delete":
        if rec_id:
            models.execute_kw(cfg["DATABASE"], uid, cfg["API_KEY"],
                "event.event", "unlink", [[rec_id]], ctx)
            print("deleted event", rec_id)
        else:
            print("delete skipped uid unknown", vals["external_uid"])

# ── Attendee CRUD
def handle_attendee(ea, op):
    user_uid  = ea.get("uid")
    event_uid = ea.get("event_id")

    # ── look up user/partner
    partner = models.execute_kw(cfg["DATABASE"], uid, cfg["API_KEY"],
        "res.partner", "search_read",
        [[("ref", "=", user_uid)]], {"limit": 1, "fields": ["id"]})
    if not partner:
        print("attendee skipped - user UID not found", user_uid)
        return
    partner_id = partner[0]["id"]

    # ── look up event
    event = models.execute_kw(cfg["DATABASE"], uid, cfg["API_KEY"],
        "event.event", "search_read",
        [[("external_uid", "=", event_uid)]], {"limit": 1, "fields": ["id"]})
    if not event:
        print("attendee skipped - event UID not found", event_uid)
        return
    event_id = event[0]["id"]

    # ── find existing registration
    existing = models.execute_kw(cfg["DATABASE"], uid, cfg["API_KEY"],
        "event.registration", "search_read",
        [[("event_id", "=", event_id), ("partner_id", "=", partner_id)]],
        {"limit": 1, "fields": ["id"]})
    reg_id = existing and existing[0]["id"]
    ctx = {"context": {"skip_rabbit": True}}

    if op == "create":
        if reg_id:
            print("skip registration – already exists", reg_id)
        else:
            new_id = models.execute_kw(cfg["DATABASE"], uid, cfg["API_KEY"],
                "event.registration", "create",
                [{"event_id": event_id, "partner_id": partner_id}], ctx)
            print("registered", new_id)

    elif op == "delete":
        if reg_id:
            models.execute_kw(cfg["DATABASE"], uid, cfg["API_KEY"],
                "event.registration", "unlink", [[reg_id]], ctx)
            print("unregistered", reg_id)
        else:
            print("unregister skipped - reg not found", user_uid, event_uid)

# main loop
print("Waiting for messages …")
ch.basic_consume(queue=queue, on_message_callback=process_message, auto_ack=False)
ch.start_consuming()
