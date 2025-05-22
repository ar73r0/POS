import os
import sys
import unittest
import datetime
import importlib.util
import xml.etree.ElementTree as ET
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, ANY

# ─── 0) Stub externe modules vóór import van consumer_event ────────────

# 0a) dotenv
dotenv_mod = ModuleType("dotenv")
dotenv_mod.dotenv_values = lambda: {
    "ODOO_HOST":       "fake_host",
    "ODOO_PORT":       "8069",
    "DATABASE":        "db",
    "EMAIL":           "me@example.com",
    "API_KEY":         "secret",
    "RABBITMQ_USERNAME":"u",
    "RABBITMQ_PASSWORD":"p",
    "RABBITMQ_HOST":   "rmq_host",
    "RABBITMQ_PORT":   "5672",
    "RABBITMQ_VHOST":  "/",
}
sys.modules["dotenv"] = dotenv_mod

# 0b) socket
import socket as _socket
_socket.create_connection = lambda *args, **kwargs: SimpleNamespace(close=lambda: None)

# 0c) pika
pika_mod = ModuleType("pika")
pika_mod.PlainCredentials     = lambda u,p: None
pika_mod.ConnectionParameters = lambda **kw: None
# fake channel + conn, zodat start_consuming niet blokkeert
fake_channel = SimpleNamespace(
    exchange_declare=lambda *a,**k: None,
    queue_declare    =lambda *a,**k: None,
    queue_bind       =lambda *a,**k: None,
    basic_qos        =lambda *a,**k: None,
    basic_consume    =lambda *a,**k: None,
    start_consuming  =lambda: None,
    basic_ack        =lambda *a,**k: None,
)
fake_conn = SimpleNamespace(channel=lambda: fake_channel)
pika_mod.BlockingConnection   = lambda params: fake_conn
sys.modules["pika"] = pika_mod

# 0d) xmlrpc.client.ServerProxy
import xmlrpc.client as _xmlrpc_client
_orig_ServerProxy = _xmlrpc_client.ServerProxy
def _dummy_ServerProxy(url):
    class Dummy(object): pass
    inst = Dummy()
    if url.endswith("/common"):
        inst.authenticate = lambda db, email, key, ctx: 42
    elif url.endswith("/object"):
        # we will override execute_kw in each test as needed
        inst.execute_kw = lambda *a, **k: []
    return inst
_xmlrpc_client.ServerProxy = _dummy_ServerProxy

# 0e) xmltodict.parse -> minimal parser met ElementTree
try:
    import xmltodict
except ImportError:
    xmltodict = ModuleType("xmltodict")
    sys.modules["xmltodict"] = xmltodict

def _dummy_parse(body):
    root = ET.fromstring(body)
    op = root.findtext("./info/operation").lower()
    ev_elem = root.find("event")
    ev = {child.tag: child.text or "" for child in ev_elem}
    return {"attendify": {"info": {"operation": op}, "event": ev}}

xmltodict.parse = _dummy_parse

# ─── 1) Dynamisch inladen van consumer_event.py ───────────────────────
TEST_DIR    = os.path.dirname(__file__)
PROJECT     = os.path.abspath(os.path.join(TEST_DIR, os.pardir))
MODULE_PATH = os.path.join(PROJECT, "consumers", "consumer_event.py")
if not os.path.isfile(MODULE_PATH):
    raise FileNotFoundError(f"Kan consumer_event.py niet vinden op {MODULE_PATH!r}")

spec = importlib.util.spec_from_file_location("consumer_event", MODULE_PATH)
consumer_event = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer_event)

# Alias
ce = consumer_event

# ─── 2) Tests ─────────────────────────────────────────────────────────
class TestConsumerEvent(unittest.TestCase):

    def test_to_odoo_datetime_empty(self):
        self.assertFalse(ce.to_odoo_datetime("", ""))
        self.assertFalse(ce.to_odoo_datetime("", None))

    def test_to_odoo_datetime_formats(self):
        # default time when empty
        self.assertEqual(
            ce.to_odoo_datetime("2025-05-20", ""),
            "2025-05-20 00:00:00"
        )
        # explicit time
        self.assertEqual(
            ce.to_odoo_datetime("2025-05-20", "15:30"),
            "2025-05-20 15:30:00"
        )

    def test_event_has_fee_field_caching(self):
        # reset cache
        ce._has_evt_fee_field = None
        # first: stub execute_kw => []
        ce.models.execute_kw = lambda *a, **k: []
        self.assertFalse(ce.event_has_fee_field())
        # next: stub execute_kw => [1]
        ce._has_evt_fee_field = None
        ce.models.execute_kw = lambda *a, **k: [1]
        self.assertTrue(ce.event_has_fee_field())

    def _make_body(self, op):
        xml = f"""<?xml version="1.0"?>
<attendify>
  <info><sender>x</sender><operation>{op}</operation></info>
  <event>
    <uid>U123</uid>
    <title>TITLE</title>
    <location>LOC</location>
    <start_date>2025-05-20</start_date>
    <end_date>2025-05-21</end_date>
    <start_time>09:00</start_time>
    <end_time>11:00</end_time>
    <entrance_fee>5.50</entrance_fee>
    <description>DESC</description>
    <organizer_uid>P1</organizer_uid>
  </event>
</attendify>"""
        return xml.encode("utf-8")

    def test_process_message_create(self):
        # Simuleer: no existing event
        seq = [
            [{"id": 2}],  # res.partner search_read
            [{"id": 3}],  # res.users search_read
            [],           # existing = []
            77            # create returns new id
        ]
        m = MagicMock(side_effect=seq)
        ce.models.execute_kw = m
        ce.event_has_fee_field = lambda: True

        ch = MagicMock()
        method = SimpleNamespace(delivery_tag=101)
        ce.process_message(ch, method, None, self._make_body("create"))

        ch.basic_ack.assert_called_once_with(delivery_tag=101)
        # laatste call = create
        args = m.call_args_list[-1][0]
        self.assertEqual(args[3], "event.event")
        self.assertEqual(args[4], "create")
        vals = args[5][0]
        self.assertEqual(vals["external_uid"], "U123")
        self.assertEqual(vals["name"], "TITLE")
        self.assertEqual(vals["description"], "DESC")
        self.assertEqual(vals["date_begin"], "2025-05-20 09:00:00")
        self.assertEqual(vals["date_end"],   "2025-05-21 11:00:00")
        self.assertAlmostEqual(vals["entrance_fee"], 5.50)
        self.assertEqual(m.call_args_list[-1][0][6], {"context": {"skip_rabbit": True}})

    def test_process_message_update(self):
        # Simuleer: existing found
        seq = [
            [{"id": 2}],        # partner
            [{"id": 3}],        # user
            [{"id": 55}],       # existing
            True                # write returns True
        ]
        m = MagicMock(side_effect=seq)
        ce.models.execute_kw = m
        ce.event_has_fee_field = lambda: True

        ch = MagicMock()
        method = SimpleNamespace(delivery_tag=202)
        ce.process_message(ch, method, None, self._make_body("update"))

        ch.basic_ack.assert_called_once_with(delivery_tag=202)
        # laatste call = write
        args = m.call_args_list[-1][0]
        self.assertEqual(args[3], "event.event")
        self.assertEqual(args[4], "write")
        # five= [[55], vals], so ID is args[5][0][0]
        self.assertEqual(args[5][0][0], 55)
        self.assertIsInstance(args[5][1], dict)
        self.assertEqual(m.call_args_list[-1][0][6], {"context": {"skip_rabbit": True}})

    def test_process_message_delete(self):
        # Simuleer: ensure partner lookup happens so seq-aligns correctly
        seq = [
            [{"id": 2}],      # partner
            [],               # user   (skipped)
            [{"id": 77}],     # existing
            True              # unlink returns True
        ]
        m = MagicMock(side_effect=seq)
        ce.models.execute_kw = m
        ce.event_has_fee_field = lambda: False

        ch = MagicMock()
        method = SimpleNamespace(delivery_tag=303)
        ce.process_message(ch, method, None, self._make_body("delete"))

        ch.basic_ack.assert_called_once_with(delivery_tag=303)
        # laatste call = unlink
        args = m.call_args_list[-1][0]
        self.assertEqual(args[3], "event.event")
        self.assertEqual(args[4], "unlink")
        # unlink gets [[77]], not [77]
        self.assertEqual(args[5], [[77]])
        self.assertEqual(m.call_args_list[-1][0][6], {"context": {"skip_rabbit": True}})

if __name__ == "__main__":
    unittest.main()
