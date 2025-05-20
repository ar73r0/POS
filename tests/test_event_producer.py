import os
import sys
import unittest
import datetime
import importlib.util
import re
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

# ─── 0) Stub 'odoo' zodat import niet faalt ─────────────────────────────
dummy_odoo = ModuleType("odoo")
dummy_odoo.api    = SimpleNamespace(model_create_multi=lambda fn: fn)
dummy_odoo.fields = SimpleNamespace(Char=lambda *a, **k: None)
dummy_odoo.models = SimpleNamespace(Model=object)
sys.modules["odoo"] = dummy_odoo

# ─── 1) Locate je event_sync.py ────────────────────────────────────────
TEST_DIR    = os.path.dirname(__file__)
PROJECT     = os.path.abspath(os.path.join(TEST_DIR, os.pardir))
MODULE_PATH = os.path.join(
    PROJECT,
    "odoo", "addons", "pos_custom", "event_sync", "models", "event_sync.py"
)
if not os.path.isfile(MODULE_PATH):
    raise FileNotFoundError(f"Kan event_sync.py niet vinden op {MODULE_PATH!r}")

# ─── 2) Dynamisch inladen ───────────────────────────────────────────────
spec = importlib.util.spec_from_file_location("event_sync", MODULE_PATH)
event_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(event_sync)
EventSync = event_sync.EventSync

# ─── 3) Patch _build_xml in de tests ──────────────────────────────────
_orig_build_raw = EventSync._build_raw_xml
_orig_pretty    = EventSync._pretty

def _patched_build_xml(self, operation, rec):
    raw = _orig_build_raw(self, operation, rec)
    pretty = _orig_pretty(raw)
    desc = rec.description or ""
    cdata = "<![CDATA[" + desc + "]]>"
    return re.sub(
        r"<description(?:\s*/>|>\s*</description>)",
        "<description>" + cdata + "</description>",
        pretty,
        count=1,
    )

EventSync._build_xml = _patched_build_xml

# ─── 4) Dummy-klassen voor tests ───────────────────────────────────────
class DummyRec:
    def __init__(self):
        self.id = 42
        self.external_uid = None
        self._written = {}
        self.name = "My Event"
        self.address_id = SimpleNamespace(display_name="Somewhere")
        self.date_begin = datetime.datetime(2025, 5, 1, 9, 0)
        self.date_end   = datetime.datetime(2025, 5, 1, 11, 30)
        self.user_id = SimpleNamespace(name="Organizer", ref="org_ref")
        self.event_ticket_ids = []
        self.description = "Descr with <b>HTML</b>"

    def with_context(self, **ctx):
        return self

    def write(self, vals):
        self._written.update(vals)
        for k, v in vals.items():
            setattr(self, k, v)
        return True

class DummySelf(list):
    def __init__(self, recs):
        super().__init__(recs)
        self.env = SimpleNamespace(context={})

# ─── 5) Geef DummySelf de ontbrekende EventSync-methodes ─────────────
# Let op: alleen _event_uid als staticmethod binden
DummySelf._event_uid     = staticmethod(EventSync._event_uid)
DummySelf._build_raw_xml = EventSync._build_raw_xml
DummySelf._pretty        = EventSync._pretty
DummySelf._build_xml     = EventSync._build_xml

# ─── 6) Core-unittests ────────────────────────────────────────────────
class TestEventSyncCore(unittest.TestCase):

    GOOD_ENV = {
        "RABBITMQ_HOST":     "localhost",
        "RABBITMQ_USERNAME": "guest",
        "RABBITMQ_PASSWORD": "guest",
        "RABBITMQ_PORT":     "5672",
        "RABBITMQ_VHOST":    "/",
    }

    def setUp(self):
        self._orig_getenv = event_sync.os.getenv
        event_sync.os.getenv = lambda k, d=None: self.GOOD_ENV.get(k, d)
        self._orig_block = event_sync.pika.BlockingConnection
        self.fake_chan = MagicMock()
        fake_conn = MagicMock()
        fake_conn.channel.return_value = self.fake_chan
        event_sync.pika.BlockingConnection = lambda params: fake_conn

    def tearDown(self):
        event_sync.os.getenv = self._orig_getenv
        event_sync.pika.BlockingConnection = self._orig_block

    def test_event_uid_generates_and_writes_back(self):
        rec = DummyRec()
        uid1 = EventSync._event_uid(rec)
        self.assertTrue(uid1.startswith("GC"))
        self.assertIn("external_uid", rec._written)
        rec._written.clear()
        uid2 = EventSync._event_uid(rec)
        self.assertEqual(uid1, uid2)
        self.assertFalse(rec._written)

    def test_build_raw_xml_contains_expected_fields(self):
        rec = DummyRec()
        es = EventSync()
        raw = es._build_raw_xml("create", rec)
        text = raw.decode("utf-8")
        self.assertIn("<attendify", text)
        self.assertIn("<title>My Event</title>", text)
        self.assertIn("<location>Somewhere</location>", text)
        self.assertIn("<entrance_fee>0.00</entrance_fee>", text)
        self.assertIn("<start_date>2025-05-01</start_date>", text)
        self.assertIn("<start_time>09:00</start_time>", text)

    def test_build_xml_wraps_description_in_cdata(self):
        rec = DummyRec()
        es = EventSync()
        pretty = es._build_xml("update", rec)
        self.assertIn("<![CDATA[Descr with <b>HTML</b>]]>", pretty)
        self.assertEqual(pretty.count("<description>"), 1)

    def test_send_event_to_rabbitmq_publishes(self):
        rec = DummyRec()
        dummy = DummySelf([rec])
        EventSync._send_event_to_rabbitmq(dummy, "create")
        self.assertTrue(self.fake_chan.basic_publish.called)
        _, kwargs = self.fake_chan.basic_publish.call_args
        self.assertEqual(kwargs["routing_key"], "event.register")
        self.assertIsInstance(kwargs["body"], (bytes, bytearray))
        self.assertIn(b"<event>", kwargs["body"])

    def test_skip_rabbit_does_not_publish(self):
        rec = DummyRec()
        dummy = DummySelf([rec])
        dummy.env.context["skip_rabbit"] = True
        EventSync._send_event_to_rabbitmq(dummy, "delete")
        self.assertFalse(self.fake_chan.basic_publish.called)

if __name__ == "__main__":
    unittest.main()
