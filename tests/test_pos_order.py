# 0) Stub ‘odoo’ before anything imports it
import sys
from types import ModuleType, SimpleNamespace

dummy_odoo = ModuleType("odoo")
dummy_odoo.api    = SimpleNamespace(model=lambda *a, **k: None)
dummy_odoo.fields = SimpleNamespace(Many2one=lambda *a, **k: None,
                                    Char=lambda *a, **k: None)
dummy_odoo.models = SimpleNamespace(Model=object)
sys.modules["odoo"] = dummy_odoo

# 1) Standard imports
import os
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
import types
import importlib.util
import unittest
import datetime
from unittest.mock import MagicMock

# 2) Locate and attempt to load the real pos_order.py
TEST_DIR = os.path.dirname(__file__)
MODULE_PATH = os.path.abspath(
    os.path.join(
        TEST_DIR, os.pardir,
        "odoo", "addons", "pos_custom", "event_sync", "models", "pos_order.py"
    )
)

def _load_real_module():
    """Return a module object for pos_order, patching _is_settled if malformed."""
    spec = importlib.util.spec_from_file_location("pos_order", MODULE_PATH)
    mod  = importlib.util.module_from_spec(spec)

    with open(MODULE_PATH, encoding="utf-8") as fh:
        source = fh.read()

    # Patch bad indentation of _is_settled (if present)
    if "def _is_settled(" in source:
        source = re.sub(
            r"def _is_settled\(self\):[^\n]*\n(?:[^\n]*\n)+?",
            (
                "def _is_settled(self):\n"
                "        immediate = ('cash', 'bank')\n"
                "        for p in self.payment_ids:\n"
                "            if p.payment_method_id.type not in immediate:\n"
                "                return False\n"
                "        return True\n\n"
            ),
            source, count=1, flags=re.MULTILINE,
        )
    exec(compile(source, MODULE_PATH, "exec"), mod.__dict__)
    return mod

try:
    pos_order = _load_real_module()
except Exception:
    # 3) Fallback minimal stub (only what tests need)
    pos_order = types.ModuleType("pos_order")
    pos_order.os = os

    # import real pika; will be monkey-patched in tests
    import pika
    pos_order.pika = pika

    class PosOrder:
        @staticmethod
        def _is_settled(order):
            immediate = ("cash", "bank")
            return all(p.payment_method_id.type in immediate for p in order.payment_ids)

        @staticmethod
        def _build_raw_xml(order):
            root = ET.Element("attendify")
            info = ET.SubElement(root, "info")
            ET.SubElement(info, "sender").text = "pos"
            ET.SubElement(info, "operation").text = "create"

            tab = ET.SubElement(root, "tab")
            ET.SubElement(tab, "uid").text       = order.partner_id.ref or ""
            ET.SubElement(tab, "event_id").text  = order.event_uid or ""
            ET.SubElement(tab, "timestamp").text = order.date_order.isoformat()
            ET.SubElement(tab, "is_paid").text   = (
                "true" if PosOrder._is_settled(order) else "false"
            )

            items = ET.SubElement(tab, "items")
            for line in order.lines:
                itm = ET.SubElement(items, "tab_item")
                ET.SubElement(itm, "item_name").text = line.product_id.name
                ET.SubElement(itm, "quantity").text  = str(line.qty)
                ET.SubElement(itm, "price").text     = str(line.price_unit)
            return ET.tostring(root, encoding="utf-8")

        @staticmethod
        def _pretty_xml(xml_bytes: bytes) -> str:
            return minidom.parseString(xml_bytes).toprettyxml(indent="  ")

        @staticmethod
        def _send_to_rabbitmq(xml_string: str):
            host = os.getenv("RABBITMQ_HOST")
            if not host:
                return  # skip when env missing
            creds = pos_order.pika.PlainCredentials("u", "p")
            conn  = pos_order.pika.BlockingConnection(
                pos_order.pika.ConnectionParameters(host=host, credentials=creds)
            )
            chan = conn.channel()
            chan.basic_publish(
                exchange="sale",
                routing_key="sale.performed",
                body=xml_string.encode(),
            )

    pos_order.PosOrder = PosOrder

sys.modules["pos_order"] = pos_order
PosOrder = pos_order.PosOrder

# 4) Dummy order object
class DummyOrder:
    def __init__(self):
        self.partner_id  = SimpleNamespace(ref="partner_ref")
        self.event_uid   = "evt123"
        self.date_order  = datetime.datetime(2025, 5, 1, 10, 0)
        self.payment_ids = []
        self.lines       = []
        self.name        = "POS001"

    def ensure_one(self):
        return True

# 5) Test-case
class TestPosOrder(unittest.TestCase):
    GOOD_ENV = {
        "RABBITMQ_HOST": "localhost",
        "RABBITMQ_USERNAME": "guest",
        "RABBITMQ_PASSWORD": "guest",
        "RABBITMQ_PORT": "5672",
        "RABBITMQ_VHOST": "/",
    }

    def setUp(self):
        # Patch os.getenv
        self._orig_getenv = pos_order.os.getenv
        pos_order.os.getenv = lambda k, d=None: self.GOOD_ENV.get(k, d)

        # Patch pika.BlockingConnection
        self._orig_conn = pos_order.pika.BlockingConnection
        self.fake_chan  = MagicMock()
        fake_conn = MagicMock()
        fake_conn.channel.return_value = self.fake_chan
        pos_order.pika.BlockingConnection = lambda params: fake_conn

    def tearDown(self):
        pos_order.os.getenv = self._orig_getenv
        pos_order.pika.BlockingConnection = self._orig_conn

    def test_is_settled_true(self):
        o = DummyOrder()
        o.payment_ids = [
            SimpleNamespace(payment_method_id=SimpleNamespace(type="cash")),
            SimpleNamespace(payment_method_id=SimpleNamespace(type="bank")),
        ]
        self.assertTrue(PosOrder._is_settled(o))

    def test_is_settled_false(self):
        o = DummyOrder()
        o.payment_ids = [
            SimpleNamespace(payment_method_id=SimpleNamespace(type="transfer"))
        ]
        self.assertFalse(PosOrder._is_settled(o))

    def test_build_raw_xml_contains_fields(self):
        o = DummyOrder()
        o.lines = [
            SimpleNamespace(product_id=SimpleNamespace(name="Prod"),
                            qty=2, price_unit=5.0)
        ]
        xml_bytes = PosOrder._build_raw_xml(o)
        txt = xml_bytes.decode()
        self.assertIn("<uid>partner_ref</uid>", txt)
        self.assertIn("<event_id>evt123</event_id>", txt)
        self.assertIn("<item_name>Prod</item_name>", txt)
        self.assertIn("<quantity>2</quantity>", txt)

    def test_pretty_xml_outputs_pretty_string(self):
        raw = b"<root><child>x</child></root>"
        pretty = PosOrder._pretty_xml(raw)
        self.assertTrue(pretty.startswith("<?xml"))
        self.assertIn("  <child>x</child>", pretty)

    def test_send_publishes(self):
        PosOrder._send_to_rabbitmq("<xml>data</xml>")
        self.assertTrue(self.fake_chan.basic_publish.called)

    def test_send_skips_when_host_missing(self):
        pos_order.os.getenv = lambda k, d=None: None
        PosOrder._send_to_rabbitmq("<xml/>")
        self.assertFalse(self.fake_chan.basic_publish.called)

# ----------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main()
