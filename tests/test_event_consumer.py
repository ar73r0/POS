# import os
# import sys
# import unittest
# import types
# import importlib.util
# import xml.etree.ElementTree as ET
# from types import ModuleType, SimpleNamespace
# from unittest.mock import MagicMock

# # Create a fake 'odoo' package
# odoo_pkg = types.ModuleType("odoo")

# # Create a fake submodule 'odoo.api'
# api_mod = types.ModuleType("odoo.api")
# # Make api.Environment available if your code uses it
# api_mod.Environment = lambda cr, uid, ctx: None

# # Attach it
# odoo_pkg.api = api_mod
# odoo_pkg.SUPERUSER_ID = 1

# # Register both in sys.modules so 'import odoo' and 'import odoo.api' work
# sys.modules["odoo"] = odoo_pkg
# sys.modules["odoo.api"] = api_mod

# # ─── 0) Stub external modules *before* importing consumer_event ─────────

# # 0a) python-dotenv
# dotenv_mod = ModuleType("dotenv")
# dotenv_mod.dotenv_values = lambda: {
#     "ODOO_HOST":        "fake_host",
#     "ODOO_PORT":        "8069",
#     "DATABASE":         "db",
#     "EMAIL":            "me@example.com",
#     "API_KEY":          "secret",
#     "RABBITMQ_USERNAME":"u",
#     "RABBITMQ_PASSWORD":"p",
#     "RABBITMQ_HOST":    "rmq_host",
#     "RABBITMQ_PORT":    "5672",
#     "RABBITMQ_VHOST":   "/",
# }
# sys.modules["dotenv"] = dotenv_mod

# # 0b) socket
# import socket as _socket
# _socket.create_connection = lambda *a, **k: SimpleNamespace(close=lambda: None)

# # 0c) pika
# pika_mod = ModuleType("pika")
# pika_mod.PlainCredentials     = lambda u, p: None
# pika_mod.ConnectionParameters = lambda **kw: None

# _fake_channel = SimpleNamespace(
#     exchange_declare=lambda *a, **k: None,
#     queue_declare   =lambda *a, **k: None,
#     queue_bind      =lambda *a, **k: None,
#     basic_qos       =lambda *a, **k: None,
#     basic_consume   =lambda *a, **k: None,
#     start_consuming =lambda: None,
#     basic_ack       =lambda *a, **k: None,
#     basic_nack      =lambda *a, **k: None,
# )
# pika_mod.BlockingConnection   = lambda params: SimpleNamespace(channel=lambda: _fake_channel)
# sys.modules["pika"] = pika_mod

# # 0d) xmlrpc.client.ServerProxy
# import xmlrpc.client as _xmlrpc_client

# def _dummy_ServerProxy(url):
#     """Very small fake of the XML-RPC endpoints used in consumer_event.py."""
#     class Dummy:        # pylint: disable=too-few-public-methods
#         pass

#     inst = Dummy()
#     if url.endswith("/common"):
#         inst.authenticate = lambda db, email, key, ctx: 42
#     else:  # /object
#         def execute_kw(db, uid, key, model, method, args, kwargs=None):
#             # Needed during module import
#             if model == "uom.uom" and method == "search":
#                 return [1]                  # expected: list of IDs
#             # All other queries: return an empty result so that
#             # tests can patch the function with MagicMock.
#             return []
#         inst.execute_kw = execute_kw
#     return inst

# _xmlrpc_client.ServerProxy = _dummy_ServerProxy  # monkey-patch

# # 0e) xmltodict with minimal functionality for our XML fixtures
# try:
#     import xmltodict
# except ImportError:          # pragma: no cover
#     xmltodict = ModuleType("xmltodict")
#     sys.modules["xmltodict"] = xmltodict

# def _dummy_parse(body: bytes):
#     root = ET.fromstring(body)
#     op   = root.findtext("./info/operation").lower()

#     ev_elem = root.find("event")
#     if ev_elem is not None:
#         payload = {c.tag: (c.text or "") for c in ev_elem}
#         return {"attendify": {"info": {"operation": op},
#                               "event": payload}}

#     ea_elem = root.find("event_attendee")
#     if ea_elem is not None:
#         payload = {c.tag: (c.text or "") for c in ea_elem}
#         return {"attendify": {"info": {"operation": op},
#                               "event_attendee": payload}}

#     raise ValueError("Unknown test payload")

# xmltodict.parse = _dummy_parse

# # ─── 1) Dynamically load consumers/consumer_event.py ──────────────────

# PROJECT_DIR  = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
# MODULE_PATH  = os.path.join(PROJECT_DIR, "consumers", "consumer_event.py")
# if not os.path.isfile(MODULE_PATH):
#     raise FileNotFoundError(f"Cannot find consumer_event.py at {MODULE_PATH!r}")

# spec = importlib.util.spec_from_file_location("consumer_event", MODULE_PATH)
# consumer_event = importlib.util.module_from_spec(spec)   # type: ignore
# spec.loader.exec_module(consumer_event)                  # type: ignore

# # Short alias
# ce = consumer_event

# ce.to_odoo_datetime = ce.to_dt

# # ─── 2) Unit tests ────────────────────────────────────────────────────

# class TestConsumerEvent(unittest.TestCase):

#     # ── helpers ───────────────────────────────────────────────────────
#     @staticmethod
#     def _xml_body(op: str) -> bytes:
#         return f"""<?xml version="1.0"?>
# <attendify>
#   <info><sender>x</sender><operation>{op}</operation></info>
#   <event>
#     <uid>U123</uid>
#     <title>TITLE</title>
#     <location>LOC</location>
#     <start_date>2025-05-20</start_date>
#     <end_date>2025-05-21</end_date>
#     <start_time>09:00</start_time>
#     <end_time>11:00</end_time>
#     <entrance_fee>5.50</entrance_fee>
#     <description>DESC</description>
#     <organizer_uid>P1</organizer_uid>
#   </event>
# </attendify>""".encode()

#     # ── to_dt helper ──────────────────────────────────────────────────
#     def test_to_dt_empty(self):
#         self.assertFalse(ce.to_dt("", ""))
#         self.assertFalse(ce.to_dt("", None))

#     def test_to_dt_formats(self):
#         self.assertEqual(ce.to_dt("2025-05-20", ""),       "2025-05-20 00:00:00")
#         self.assertEqual(ce.to_dt("2025-05-20", "15:30"),  "2025-05-20 15:30:00")

#     # ── consumer behaviour ────────────────────────────────────────────
#     def test_process_message_create(self):
#         seq = [
#             [{"id": 2}],   # organiser
#             [{"id": 3}],   # venue
#             [],            # event search_read
#             77,            # event create
#             [],            # product search
#             88,            # product create
#             99,            # ticket create
#         ]
#         m = MagicMock(side_effect=seq)
#         ce.models.execute_kw = m
#         ce.open_pos_session_for_event = lambda *a, **kw: None
#         ce.HAS_FEE = True

#         ch     = MagicMock()
#         method = SimpleNamespace(delivery_tag=101)

#         ce.process_message(ch, method, None, self._xml_body("create"))

#         ch.basic_ack.assert_called_once_with(delivery_tag=101)

#         _, _, _, model, method_name, args, ctx = m.call_args_list[-4][0]
#         # -4 because the fourth call from the end is the event.create
#         self.assertEqual(model,       "event.event")
#         self.assertEqual(method_name, "create")
#         vals = args[0]
#         self.assertEqual(vals["external_uid"], "U123")
#         self.assertEqual(vals["name"],         "TITLE")
#         self.assertEqual(vals["description"],  "DESC")
#         self.assertEqual(vals["date_begin"],   "2025-05-20 09:00:00")
#         self.assertEqual(vals["date_end"],     "2025-05-21 11:00:00")
#         self.assertAlmostEqual(vals["entrance_fee"], 5.50)
#         self.assertEqual(ctx, {"context": {"skip_rabbit": True}})

#     def test_process_message_update(self):
#         seq = [
#             [{"id": 2}],      # organiser
#             [{"id": 3}],      # venue
#             [{"id": 55}],     # existing event
#             True              # write
#         ]
#         m = MagicMock(side_effect=seq)
#         ce.models.execute_kw = m
#         ce.HAS_FEE = True

#         ch     = MagicMock()
#         method = SimpleNamespace(delivery_tag=202)

#         ce.process_message(ch, method, None, self._xml_body("update"))

#         ch.basic_ack.assert_called_once_with(delivery_tag=202)

#         _, _, _, model, method_name, args, ctx = m.call_args_list[-1][0]
#         self.assertEqual(model,       "event.event")
#         self.assertEqual(method_name, "write")
#         self.assertEqual(args[0][0], 55)        # [[55], vals]
#         self.assertIsInstance(args[1], dict)
#         self.assertEqual(ctx, {"context": {"skip_rabbit": True}})

#     def test_process_message_delete(self):
#         seq = [
#             [{"id": 2}],      # organiser
#             [{"id": 3}],      # venue
#             [{"id": 77}],     # existing event
#             True              # unlink
#         ]
#         m = MagicMock(side_effect=seq)
#         ce.models.execute_kw = m
#         ce.HAS_FEE = False

#         ch     = MagicMock()
#         method = SimpleNamespace(delivery_tag=303)

#         ce.process_message(ch, method, None, self._xml_body("delete"))

#         ch.basic_ack.assert_called_once_with(delivery_tag=303)

#         _, _, _, model, method_name, args, ctx = m.call_args_list[-1][0]
#         self.assertEqual(model,       "event.event")
#         self.assertEqual(method_name, "unlink")
#         self.assertEqual(args[0], [77])           # consumer passes [id]
#         self.assertEqual(ctx, {"context": {"skip_rabbit": True}})


# if __name__ == "__main__":
#     unittest.main()