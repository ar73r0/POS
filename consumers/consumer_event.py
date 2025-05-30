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


def to_dt(date_str: str | None, time_str: str | None = None):
    """Geef 'YYYY-MM-DD HH:MM:SS' terug of False."""
    if not date_str:
        return False

    # default-tijd
    if not time_str:
        time_str = "00:00:00"
    else:
        time_str = time_str.strip()
        # voeg alleen seconden toe als ze ontbreken
        if re.match(r"^\d{2}:\d{2}$", time_str):
            time_str += ":00"
        elif not re.match(r"^\d{2}:\d{2}:\d{2}$", time_str):
            raise ValueError(f"Onbekend tijdformaat: {time_str}")

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
# HELPER: check if model has field
# ────────────────────────────────────────────────────────────────────────
def model_has_field(model: str, field: str) -> bool:
    return bool(models.execute_kw(
        DB, uid, PWD,
        "ir.model.fields", "search",
        [[("model", "=", model), ("name", "=", field)]],
        {"limit": 1}
    ))

HAS_FEE        = model_has_field("event.event", "entrance_fee")
HAS_GCID       = model_has_field("event.event", "gcid")
HAS_TICKET_UOM = model_has_field("event.event.ticket", "product_uom_id")


# ────────────────────────────────────────────────────────────────────────
# HELPER: product.template for event
# ────────────────────────────────────────────────────────────────────────
def find_or_create_event_product(ev: dict) -> int:
    title        = ev.get("title") or "Unnamed Event"
    event_uid    = ev.get("uid")
    gcid         = ev.get("gcid")
    fee          = float(ev.get("entrance_fee") or 0.0)
    default_code = event_uid or gcid or title or "event"

    # Build the full product name with "Ticket: " prefix
    full_name = f"Ticket: {title}"

    # 1) Search for an existing template
    existing = models.execute_kw(
        DB, uid, PWD,
        "product.template", "search_read",
        [[("default_code", "=", default_code)]],
        {"limit": 1, "fields": ["id", "name"]}
    )
    if existing:
        template_id = existing[0]["id"]
        print(f"Product template exists: {existing[0]['name']} (id={template_id})")
    else:
        template_id = None

    # 2) Locate Drinks/Tickets POS category
    pos_cat = models.execute_kw(
        DB, uid, PWD,
        "pos.category", "search_read",
        [[("name", "=", "Drinks/Tickets")]],
        {"limit": 1, "fields": ["id"]}
    )
    if not pos_cat:
        raise RuntimeError("POS category ‘Drinks/Tickets’ not found")
    pos_categ_id = pos_cat[0]["id"]

    # 3) Prepare the template values (no POS fields here)
    vals = {
        "name":             full_name,
        "type":             "service",
        "default_code":     default_code,
        "list_price":       fee,
        "sale_ok":          True,
        "purchase_ok":      False,
        "description_sale": (ev.get("description") or "") + "\nLocation: " + (ev.get("location") or ""),
    }

    # 4) Create or update the template
    if template_id:
        models.execute_kw(DB, uid, PWD,
            "product.template", "write",
            [[template_id], vals]
        )
        print(f"Updated template {template_id} to '{full_name}'")
    else:
        template_id = models.execute_kw(DB, uid, PWD,
            "product.template", "create",
            [vals]
        )
        print(f"Created template {default_code} as '{full_name}' (id={template_id})")

    # 5) Fetch its variants
    variant_ids = models.execute_kw(DB, uid, PWD,
        "product.product", "search",
        [[("product_tmpl_id", "=", template_id)]]
    )
    if not variant_ids:
        print("No variants found, skipping POS setup")
        return template_id

    # 6) Determine POS field type and set both category + availability
    has_m2o = model_has_field("product.product", "pos_categ_id")
    has_m2m = model_has_field("product.product", "pos_categ_ids")

    if has_m2o:
        write_vals = {
            "pos_categ_id":     pos_categ_id,
            "available_in_pos": True,
        }
    elif has_m2m:
        write_vals = {
            "pos_categ_ids":    [(6, 0, [pos_categ_id])],
            "available_in_pos": True,
        }
    else:
        # fallback: only toggle available_in_pos if it exists
        if model_has_field("product.product", "available_in_pos"):
            write_vals = {"available_in_pos": True}
        else:
            print("No POS-category or availability field on product.product; skipping")
            return template_id

    # 7) Apply to all variants
    models.execute_kw(DB, uid, PWD,
        "product.product", "write",
        [variant_ids, write_vals]
    )
    print(f"→ Prefixed name and set POS category + availability on variants {variant_ids}")

    return template_id


# ────────────────────────────────────────────────────────────────────────
# HELPER: ticket-product used for paid registrations
# ────────────────────────────────────────────────────────────────────────
def find_or_create_ticket_product() -> int:
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


# ────────────────────────────────────────────────────────────────────────
# HELPER: UoM lookup (Unit)
# ────────────────────────────────────────────────────────────────────────
def get_unit_uom_id() -> int:
    uom_ids = models.execute_kw(
        DB, uid, PWD,
        "uom.uom", "search",
        [[("category_id.name", "=", "Unit")]],
        {"limit": 1}
    )
    if not uom_ids:
        raise RuntimeError("No UoM 'Unit' found")
    return uom_ids[0]


UOM_UNIT_ID = get_unit_uom_id()


# ────────────────────────────────────────────────────────────────────────
# HELPER: venue partner lookup/create
# ────────────────────────────────────────────────────────────────────────
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
def process_message(ch, method, props, body):
    try:
        msg  = xmltodict.parse(body)
        root = msg.get("attendify", {})
        op   = root["info"]["operation"].lower()

        if "event" in root:
            handle_event(root["event"], op)
        elif "event_attendee" in root:
            handle_attendee(root["event_attendee"], op)
        else:
            print("Unknown payload type")

        ch.basic_ack(delivery_tag=method.delivery_tag)  # ACK only after success
    except Exception as e:
        print("Error processing message:", e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)  # drop bad one



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
        "date_end": to_dt(ev.get("end_date"), ev.get("end_time")),
    }

    fee = 0.0
    fee_str = ev.get("entrance_fee")
    if fee_str:
        try:
            fee = float(fee_str)
            if HAS_FEE:
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
            {"limit": 1, "fields": ["id"]}
        )
        if org:
            vals["organizer_id"] = org[0]["id"]

    # registration limit
    limit_val = ev.get("registration_limit") or ev.get("seats_max") or ev.get("limit")
    if limit_val:
        try:
            limit_int = int(limit_val)
            vals["seats_max"] = limit_int
            vals["seats_limited"] = True
        except ValueError:
            print("seats_max parse error:", limit_val)

    existing = models.execute_kw(
        DB, uid, PWD,
        "event.event", "search_read",
        [[("external_uid", "=", event_uid)]],
        {"limit": 1, "fields": ["id"]}
    )
    rec_id = existing and existing[0]["id"]
    ctx = {"context": {"skip_rabbit": True}}

    if op == "create":
        if rec_id:
            print(f"Event exists (id={rec_id}), skipping")
            return

        new_id = models.execute_kw(
            DB, uid, PWD,
            "event.event", "create", [vals], ctx
        )
        print(f"Event created  id={new_id}")

        # product.template
        find_or_create_event_product(ev)

        # create ticket if fee > 0
        if fee > 0:
            ticket_vals = {
                "event_id":  new_id,
                "name":      f"Ticket: {vals['name']}",
                "price":     fee,
                "product_id": PRODUCT_ID,
            }
            if HAS_TICKET_UOM:
                ticket_vals["product_uom_id"] = UOM_UNIT_ID

            tkt_id = models.execute_kw(
                DB, uid, PWD,
                "event.event.ticket", "create", [ticket_vals], ctx
            )
            print(f"Ticket created  id={tkt_id}")

    elif op == "update":
        if rec_id:
            models.execute_kw(
                DB, uid, PWD,
                "event.event", "write", [[rec_id], vals], ctx
            )
            print(f"Event updated  id={rec_id}")
        else:
            print("update skipped - uid unknown")

    elif op == "delete":
        if rec_id:
            models.execute_kw(
                DB, uid, PWD,
                "event.event", "unlink", [[rec_id]], ctx
            )
            print(f"Event deleted  id={rec_id}")
        else:
            print("delete skipped - uid unknown")


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
        {"limit": 1, "fields": ["id"]}
    )
    if not partner:
        print("user UID not found")
        return
    partner_id = partner[0]["id"]

    event = models.execute_kw(
        DB, uid, PWD,
        "event.event", "search_read",
        [[("external_uid", "=", event_uid)]],
        {"limit": 1, "fields": ["id"]}
    )
    if not event:
        print("event UID not found")
        return
    event_id = event[0]["id"]

    existing = models.execute_kw(
        DB, uid, PWD,
        "event.registration", "search_read",
        [[("event_id", "=", event_id), ("partner_id", "=", partner_id)]],
        {"limit": 1, "fields": ["id"]}
    )
    reg_id = existing and existing[0]["id"]
    ctx    = {"context": {"skip_rabbit": True}}

    # Helper: fetch first ticket (if any) to link sale order / price
    def _get_first_ticket_id(ev_id: int):
        tix = models.execute_kw(
            DB, uid, PWD,
            "event.event.ticket", "search_read",
            [[("event_id", "=", ev_id)]],
            {"limit": 1, "fields": ["id"], "order": "id ASC"}
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
            "event.registration", "create", [reg_vals], ctx
        )
        print(f"Registered  id={new_id}")

    elif op == "unregister":
        if reg_id:
            models.execute_kw(
                DB, uid, PWD,
                "event.registration", "unlink", [[reg_id]], ctx
            )
            print(f"Unregistered  id={reg_id}")
        else:
            print("nothing to delete - registration not found")
    else:
        print(f"Ignored attendee op '{op}' (unsupported)")


print("Waiting for RabbitMQ messages …")
ch.basic_consume(queue=queue, on_message_callback=process_message, auto_ack=False)
ch.start_consuming()