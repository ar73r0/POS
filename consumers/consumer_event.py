import socket
import pika
import xmltodict
import xmlrpc.client
from datetime import datetime
from dotenv import dotenv_values

# Config
cfg = dotenv_values()

# Odoo RPC
ODOO_HOST = cfg.get("ODOO_HOST", "web")
ODOO_PORT = int(cfg.get("ODOO_PORT", 8069))
socket.create_connection((ODOO_HOST, ODOO_PORT), timeout=5).close()

url    = f"http://{ODOO_HOST}:{ODOO_PORT}/xmlrpc/2/"
common = xmlrpc.client.ServerProxy(url + "common")
uid    = common.authenticate(cfg["DATABASE"], cfg["EMAIL"], cfg["API_KEY"], {})
models = xmlrpc.client.ServerProxy(url + "object")

def to_odoo_datetime(date_str, time_str="00:00"):
    """Return Odoo‐style 'YYYY-MM-DD HH:MM:SS' or False for empty date."""
    if not date_str:
        return False
    combined = f"{date_str} {time_str or '00:00'}:00"
    dt       = datetime.strptime(combined, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# RabbitMQ setup
creds = pika.PlainCredentials(cfg["RABBITMQ_USERNAME"], cfg["RABBITMQ_PASSWORD"])
params = pika.ConnectionParameters(
    host=cfg["RABBITMQ_HOST"],
    port=int(cfg.get("RABBITMQ_PORT", 5672)),
    virtual_host=cfg["RABBITMQ_VHOST"],
    credentials=creds,
)
conn = pika.BlockingConnection(params)
ch   = conn.channel()

exchange, queue = "event", "pos.event"
routing_keys    = ["event.register", "event.update", "event.delete"]

ch.exchange_declare(exchange, "direct", durable=True)
ch.queue_declare(queue, durable=True)
for rk in routing_keys:
    ch.queue_bind(queue=queue, exchange=exchange, routing_key=rk)
ch.basic_qos(prefetch_count=1)

# --------------------------------------------------------------------------
# Helper to detect if the event.event model has an entrance_fee field
_has_evt_fee_field = None
def event_has_fee_field():
    global _has_evt_fee_field
    if _has_evt_fee_field is None:
        _has_evt_fee_field = bool(
            models.execute_kw(
                cfg["DATABASE"], uid, cfg["API_KEY"],
                "ir.model.fields", "search",
                [[("model", "=", "event.event"), ("name", "=", "entrance_fee")]],
                {"limit": 1}
            )
        )
    return _has_evt_fee_field
# --------------------------------------------------------------------------

def process_message(ch, method, props, body):
    try:
        msg = xmltodict.parse(body)
        op  = msg["attendify"]["info"]["operation"].lower()
        ev  = msg["attendify"]["event"]

        vals = {
            "external_uid": ev.get("uid"),
            "name":         ev.get("title"),
            "description":  ev.get("description") or "",
            "date_begin":   to_odoo_datetime(ev.get("start_date"), ev.get("start_time")),
            "date_end":     to_odoo_datetime(ev.get("end_date"),   ev.get("end_time")),
        }

        # Only set entrance_fee if the model actually has that field
        if ev.get("entrance_fee") and event_has_fee_field():
            vals["entrance_fee"] = float(ev.get("entrance_fee"))

        # Organizer lookup (organizer_uid = OD… user UID)
        organizer_uid = ev.get("organizer_uid")
        if organizer_uid:
            partner = models.execute_kw(
                cfg["DATABASE"], uid, cfg["API_KEY"],
                "res.partner", "search_read",
                [[("ref", "=", organizer_uid)]],
                {"limit": 1, "fields": ["id"]}
            )
            if partner:
                user = models.execute_kw(
                    cfg["DATABASE"], uid, cfg["API_KEY"],
                    "res.users", "search_read",
                    [[("partner_id", "=", partner[0]["id"])]],
                    {"limit": 1, "fields": ["id"]}
                )
                if user:
                    vals["user_id"] = user[0]["id"]

        # Upsert into event.event
        existing = models.execute_kw(
            cfg["DATABASE"], uid, cfg["API_KEY"],
            "event.event", "search_read",
            [[("external_uid", "=", vals["external_uid"])]],
            {"limit": 1, "fields": ["id"]}
        )
        dup_id = existing and existing[0]["id"]
        ctx    = {"context": {"skip_rabbit": True}}

        if op == "create":
            if dup_id:
                print("Skipping create; already exists", dup_id)
            else:
                new_id = models.execute_kw(
                    cfg["DATABASE"], uid, cfg["API_KEY"],
                    "event.event", "create", [vals], ctx
                )
                print("Created event", new_id)

        elif op == "update":
            if dup_id:
                models.execute_kw(
                    cfg["DATABASE"], uid, cfg["API_KEY"],
                    "event.event", "write", [[dup_id], vals], ctx
                )
                print("Updated event", dup_id)
            else:
                new_id = models.execute_kw(
                    cfg["DATABASE"], uid, cfg["API_KEY"],
                    "event.event", "create", [vals], ctx
                )
                print("Created event", new_id)

        elif op == "delete":
            if dup_id:
                models.execute_kw(
                    cfg["DATABASE"], uid, cfg["API_KEY"],
                    "event.event", "unlink", [[dup_id]], ctx
                )
                print("Deleted event", dup_id)
            else:
                print("Nothing to delete for UID", vals["external_uid"])

        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print("Error processing message:", e)

# Start consumer
ch.basic_consume(queue=queue, on_message_callback=process_message, auto_ack=False)
print("Waiting for event messages…")
ch.start_consuming()
