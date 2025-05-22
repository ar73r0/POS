import socket
import pika
import xmltodict
import xmlrpc.client
import re
from dotenv import dotenv_values

# ────────────────────────────────────────────────────────────────────────
# ODOO RPC SETUP
# ────────────────────────────────────────────────────────────────────────
cfg        = dotenv_values()
DB         = cfg["DATABASE"]
USER       = cfg["EMAIL"]
PWD        = cfg["API_KEY"]
ODOO_HOST  = cfg.get("ODOO_HOST", "web")
ODOO_PORT  = int(cfg.get("ODOO_PORT", 8069))

socket.create_connection((ODOO_HOST, ODOO_PORT), timeout=5).close()

url    = f"http://{ODOO_HOST}:{ODOO_PORT}/xmlrpc/2/"
common = xmlrpc.client.ServerProxy(url + "common")
uid    = common.authenticate(DB, USER, PWD, {})
models = xmlrpc.client.ServerProxy(url + "object")


# ────────────────────────────────────────────────────────────────────────
# DATE-HELPER
# ────────────────────────────────────────────────────────────────────────
def to_dt(date_str: str | None, time_str: str | None = None):
    """Return 'YYYY-MM-DD HH:MM:SS' or False if date_str is empty."""
    if not date_str:
        return False
    if not time_str:
        time_str = "00:00:00"
    else:
        time_str = time_str.strip()
        if re.match(r"^\d{2}:\d{2}$", time_str):
            time_str += ":00"
        elif not re.match(r"^\d{2}:\d{2}:\d{2}$", time_str):
            raise ValueError(f"Unknown time format: {time_str}")
    return f"{date_str.strip()} {time_str}"


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
    "event.register", "event.unregister",
]

ch.exchange_declare(exchange=exchange, exchange_type="direct", durable=True)
ch.queue_declare(queue=queue, durable=True)
for rk in routing_keys:
    ch.queue_bind(queue=queue, exchange=exchange, routing_key=rk)
ch.basic_qos(prefetch_count=1)


# ────────────────────────────────────────────────────────────────────────
# MODEL-FIELD HELPERS
# ────────────────────────────────────────────────────────────────────────
def model_has_field(model: str, field: str) -> bool:
    return bool(models.execute_kw(
        DB, uid, PWD,
        "ir.model.fields", "search",
        [[("model", "=", model), ("name", "=", field)]],
        {"limit": 1},
    ))

HAS_FEE        = model_has_field("event.event", "entrance_fee")
HAS_GCID       = model_has_field("event.event", "gcid")
HAS_TICKET_UOM = model_has_field("event.event.ticket", "product_uom_id")

# helpers expected by test-suite
def to_odoo_datetime(date_str: str | None, time_str: str | None = None):
    return to_dt(date_str, time_str)

_has_evt_fee_field: bool | None = None
def event_has_fee_field() -> bool:
    global _has_evt_fee_field
    if _has_evt_fee_field is None:
        _has_evt_fee_field = bool(models.execute_kw(
            DB, uid, PWD,
            "ir.model.fields", "search",
            [[("model", "=", "event.event"), ("name", "=", "entrance_fee")]],
            {"limit": 1},
        ))
    return _has_evt_fee_field


# ────────────────────────────────────────────────────────────────────────
# PRODUCT & UoM HELPERS
# ────────────────────────────────────────────────────────────────────────
def find_or_create_event_product(ev: dict) -> int:
    title        = ev.get("title")
    event_uid    = ev.get("uid")
    gcid         = ev.get("gcid")
    fee          = float(ev.get("entrance_fee") or 0.0)
    default_code = event_uid or gcid or title or "event"

    prod = models.execute_kw(
        DB, uid, PWD,
        "product.template", "search_read",
        [[("default_code", "=", default_code)]],
        {"limit": 1, "fields": ["id", "name"]},
    )
    if prod:
        return prod[0]["id"]

    return models.execute_kw(
        DB, uid, PWD,
        "product.template", "create",
        [{
            "name": title or "Unnamed Event",
            "type": "service",
            "default_code": default_code,
            "list_price": fee,
            "sale_ok": True,
            "purchase_ok": False,
            "description_sale": (ev.get("description") or "") + "\nLocation: " + (ev.get("location") or ""),
        }],
    )


def find_or_create_ticket_product() -> int:
    prod = models.execute_kw(
        DB, uid, PWD,
        "product.product", "search_read",
        [[("name", "=", "Event Registration")]],
        {"limit": 1, "fields": ["id"]},
    )
    if prod:
        return prod[0]["id"]
    return models.execute_kw(
        DB, uid, PWD,
        "product.product", "create",
        [{"name": "Event Registration", "type": "service"}],
    )

PRODUCT_ID = find_or_create_ticket_product()


def get_unit_uom_id() -> int:
    recs = models.execute_kw(
        DB, uid, PWD,
        "uom.uom", "search_read",
        [[("category_id.name", "=", "Unit")]],
        {"limit": 1, "fields": ["id"]},
    )
    if not recs:
        raise RuntimeError("No UoM 'Unit' found")
    return recs[0]["id"]

UOM_UNIT_ID = get_unit_uom_id()


def find_or_create_venue_partner(name: str) -> int:
    name = name.strip()
    rec = models.execute_kw(
        DB, uid, PWD,
        "res.partner", "search_read",
        [[("name", "=", name)]],
        {"limit": 1, "fields": ["id"]},
    )
    if rec:
        return rec[0]["id"]
    return models.execute_kw(
        DB, uid, PWD,
        "res.partner", "create",
        [{"name": name, "supplier_rank": 0, "customer_rank": 0}],
    )


# ────────────────────────────────────────────────────────────────────────
# MESSAGE HANDLER (dispatch)
# ────────────────────────────────────────────────────────────────────────
def process_message(ch, method, props, body):
    text = body.decode() if isinstance(body, (bytes, bytearray)) else body

    try:
        parsed = xmltodict.parse(text)
        root   = parsed.get("attendify", {})
        op     = root["info"]["operation"].lower()

        if "event" in root:
            handle_event(root["event"], op)
        elif "event_attendee" in root:
            handle_attendee(root["event_attendee"], op)

    except Exception:
        import xml.etree.ElementTree as ET
        try:
            root_elem = ET.fromstring(text)
            op = (root_elem.findtext("./info/operation") or "").strip().lower()

            if op in {"create", "update", "delete"}:
                ev_elem = root_elem.find("event")
                if ev_elem is not None:
                    ev = {c.tag: c.text or "" for c in ev_elem}
                    handle_event(ev, op)
                else:
                    print("No <event> element found (fallback)")
            else:
                print("Unknown payload type (fallback)")
        except Exception as e:
            print("Error processing message:", e)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

    ch.basic_ack(delivery_tag=method.delivery_tag)


# ────────────────────────────────────────────────────────────────────────
# EVENT CRUD
# ────────────────────────────────────────────────────────────────────────
def handle_event(ev: dict, op: str):
    event_uid = ev.get("uid")
    print(f"\nEVENT {op.upper()}  uid={event_uid}")

    vals = {
        "external_uid": event_uid,
        "name": ev.get("title"),
        "description": ev.get("description") or "",
        "date_begin": to_dt(ev.get("start_date"), ev.get("start_time")),
        "date_end":   to_dt(ev.get("end_date"),   ev.get("end_time")),
    }

    fee_str = ev.get("entrance_fee")
    if fee_str:
        try:
            fee = float(fee_str)
            if event_has_fee_field():
                vals["entrance_fee"] = fee
        except ValueError:
            print("entrance_fee parse error:", fee_str)

    if HAS_GCID and ev.get("gcid"):
        vals["gcid"] = ev["gcid"].strip()

    location = ev.get("location")
    if location:
        vals["address_id"] = find_or_create_venue_partner(location)

    org_uid = ev.get("organizer_uid")
    if org_uid:
        org = models.execute_kw(
            DB, uid, PWD,
            "res.partner", "search_read",
            [[("ref", "=", org_uid)]],
            {"limit": 1, "fields": ["id"]},
        )
        if org:
            vals["organizer_id"] = org[0]["id"]

    limit_val = ev.get("registration_limit") or ev.get("seats_max") or ev.get("limit")
    if limit_val:
        try:
            vals["seats_max"]     = int(limit_val)
            vals["seats_limited"] = True
        except ValueError:
            print("seats_max parse error:", limit_val)

    existing = models.execute_kw(
        DB, uid, PWD,
        "event.event", "search_read",
        [[("external_uid", "=", event_uid)]],
        {"limit": 1, "fields": ["id"]},
    )
    rec_id = existing and existing[0]["id"]
    ctx = {"context": {"skip_rabbit": True}}

    if op == "create":
        if rec_id:
            print(f"Event exists (id={rec_id}), skipping")
            return
        new_id = models.execute_kw(
            DB, uid, PWD,
            "event.event", "create", [vals], ctx,
        )
        print(f"Event created  id={new_id}")

    elif op == "update":
        if rec_id:
            models.execute_kw(
                DB, uid, PWD,
                "event.event", "write", [[rec_id], vals], ctx,
            )
            print(f"Event updated  id={rec_id}")

    elif op == "delete":
        if rec_id:
            models.execute_kw(
                DB, uid, PWD,
                "event.event", "unlink", [[rec_id]], ctx,
            )
            print(f"Event deleted  id={rec_id}")


# ----------------------------------------------------------------------
# Thin wrappers for unit-tests (patched by pytest)
# ----------------------------------------------------------------------
def _handle_create(root_elem):  # noqa: D401
    ev = {c.tag: c.text or "" for c in root_elem.find("event")}
    handle_event(ev, "create")

def _handle_update(root_elem):
    ev = {c.tag: c.text or "" for c in root_elem.find("event")}
    handle_event(ev, "update")

def _handle_delete(root_elem):
    ev = {c.tag: c.text or "" for c in root_elem.find("event")}
    handle_event(ev, "delete")
# ----------------------------------------------------------------------


# ────────────────────────────────────────────────────────────────────────
# REGISTRATION CRUD
# ────────────────────────────────────────────────────────────────────────
def handle_attendee(ea: dict, op: str):
    user_uid  = ea.get("uid")
    event_uid = ea.get("event_id")
    print(f"\nATTENDEE {op.upper()} user={user_uid} event={event_uid}")

    partner = models.execute_kw(
        DB, uid, PWD,
        "res.partner", "search_read",
        [[("ref", "=", user_uid)]],
        {"limit": 1, "fields": ["id"]},
    )
    if not partner:
        print("user UID not found")
        return
    partner_id = partner[0]["id"]

    event = models.execute_kw(
        DB, uid, PWD,
        "event.event", "search_read",
        [[("external_uid", "=", event_uid)]],
        {"limit": 1, "fields": ["id"]},
    )
    if not event:
        print("event UID not found")
        return
    event_id = event[0]["id"]

    existing = models.execute_kw(
        DB, uid, PWD,
        "event.registration", "search_read",
        [[("event_id", "=", event_id), ("partner_id", "=", partner_id)]],
        {"limit": 1, "fields": ["id"]},
    )
    reg_id = existing and existing[0]["id"]
    ctx = {"context": {"skip_rabbit": True}}

    def _get_first_ticket_id(ev_id: int):
        tix = models.execute_kw(
            DB, uid, PWD,
            "event.event.ticket", "search_read",
            [[("event_id", "=", ev_id)]],
            {"limit": 1, "fields": ["id"], "order": "id ASC"},
        )
        return tix[0]["id"] if tix else False

    if op == "register":
        if reg_id:
            print(f"Already registered (id={reg_id})")
            return
        ticket_id = _get_first_ticket_id(event_id)
        reg_vals  = {"event_id": event_id, "partner_id": partner_id}
        if ticket_id:
            reg_vals["event_ticket_id"] = ticket_id
        new_id = models.execute_kw(
            DB, uid, PWD,
            "event.registration", "create", [reg_vals], ctx,
        )
        print(f"Registered  id={new_id}")

    elif op == "unregister":
        if reg_id:
            models.execute_kw(
                DB, uid, PWD,
                "event.registration", "unlink", [[reg_id]], ctx,
            )
            print(f"Unregistered  id={reg_id}")
        else:
            print("nothing to delete - registration not found")
    else:
        print(f"Ignored attendee op '{op}' (unsupported)")


# ────────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ────────────────────────────────────────────────────────────────────────
print("Waiting for RabbitMQ messages …")
ch.basic_consume(queue=queue, on_message_callback=process_message, auto_ack=False)
ch.start_consuming()
