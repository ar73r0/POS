import os
import pika
import xmltodict
import xmlrpc.client
from dotenv import dotenv_values

# Load config
cfg = dotenv_values()

# Set up Odoo RPC
url     = f"http://{cfg['ODOO_HOST']}:8069/xmlrpc/2/"
common  = xmlrpc.client.ServerProxy(url + "common")
uid     = common.authenticate(cfg["DATABASE"], cfg["EMAIL"], cfg["API_KEY"], {})
models  = xmlrpc.client.ServerProxy(url + "object")

# Set up RabbitMQ
creds = pika.PlainCredentials(cfg["RABBITMQ_USERNAME"], cfg["RABBITMQ_PASSWORD"])
params = pika.ConnectionParameters(
    host=cfg["RABBITMQ_HOST"],
    port=int(cfg.get("RABBITMQ_PORT", 5672)),
    virtual_host=cfg["RABBITMQ_VHOST"],
    credentials=creds,
)
conn    = pika.BlockingConnection(params)
ch      = conn.channel()

exchange     = "event"
queue        = "pos.event"
routing_keys = ["event.register", "event.update", "event.delete"]

ch.exchange_declare(exchange=exchange, exchange_type="direct", durable=True)
ch.queue_declare(queue=queue, durable=True)
for rk in routing_keys:
    ch.queue_bind(exchange=exchange, queue=queue, routing_key=rk)
ch.basic_qos(prefetch_count=1)


def process_message(ch, method, props, body):
    try:
        msg = xmltodict.parse(body)
        op  = msg["attendify"]["info"]["operation"].lower()
        ev  = msg["attendify"]["event"]

        # Prepare vals
        vals = {
            "external_uid": ev.get("uid_event"),
            "name":         ev.get("name"),
            "date_begin":   ev.get("start_date"),
            "date_end":     ev.get("end_date"),
        }

        # Handle description (strip CDATA)
        desc = ev.get("description", "")
        if desc.startswith("<![CDATA[") and desc.endswith("]]>"):
            desc = desc[9:-3]
        vals["description"] = desc

        # Deduplicate by external_uid
        existing = models.execute_kw(
            cfg["DATABASE"], uid, cfg["API_KEY"],
            "event.event", "search_read",
            [[("external_uid","=", vals["external_uid"])]],
            {"limit": 1, "fields": ["id"]}
        )
        dup_id = existing and existing[0]["id"]

        # Add skip_rabbit=True tag
        ctx = {"context": {"skip_rabbit": True}}

        if op == "create":
            if dup_id:
                print("Skipping create; already exists", dup_id)
            else:
                new_id = models.execute_kw(
                    cfg["DATABASE"], uid, cfg["API_KEY"],
                    "event.event", "create",
                    [vals],
                    ctx
                )
                print("Created event", new_id)

        elif op == "update":
            if dup_id:
                models.execute_kw(
                    cfg["DATABASE"], uid, cfg["API_KEY"],
                    "event.event", "write",
                    [[dup_id], vals],
                    ctx
                )
                print("Updated event", dup_id)
            else:
                # fallback to create if no existing record
                new_id = models.execute_kw(
                    cfg["DATABASE"], uid, cfg["API_KEY"],
                    "event.event", "create",
                    [vals],
                    ctx
                )
                print("Created event", new_id)

        elif op == "delete":
            if dup_id:
                models.execute_kw(
                    cfg["DATABASE"], uid, cfg["API_KEY"],
                    "event.event", "unlink",
                    [[dup_id]],
                    ctx
                )
                print("Deleted event", dup_id)
            else:
                print("Nothing to delete for UID", vals["external_uid"])

        else:
            print("Ignored unknown operation:", op)

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print("Error processing message:", e)


ch.basic_consume(queue=queue, on_message_callback=process_message, auto_ack=False)
print("Waiting for event messages…")
ch.start_consuming()
