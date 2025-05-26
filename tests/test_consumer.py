# """
# tests/test_consumer.py
# ~~~~~~~~~~~~~~~~~~~~~~

# Unit‑tests for the CRUD dispatcher in consumers/consumer.py.

# External services (dotenv, xmlrpc, pika) are stub‑mocked so no real
# connections are made.  Focus: create / update / delete dispatch and the
# delete‑helper behaviour.
# """

# import os
# import sys
# import types
# import unittest
# import importlib.util
# from types import SimpleNamespace
# from unittest.mock import MagicMock, patch

# # ──────────────────────────────────────────────────────────────────────────────
# #  Dynamic import with heavy stubbing
# # ──────────────────────────────────────────────────────────────────────────────
# TEST_DIR = os.path.dirname(__file__)
# PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, os.pardir))
# if PROJECT_ROOT not in sys.path:
#     sys.path.insert(0, PROJECT_ROOT)

# CONSUMER_PATH = os.path.join(PROJECT_ROOT, "consumers", "consumer.py")


# def import_consumer():
#     """Import consumers/consumer.py with all external deps stubbed."""
#     # ---- dotenv ---------------------------------------------------------
#     fake_env = {
#         "ODOO_HOST": "odoo",
#         "DATABASE": "db",
#         "EMAIL": "u@example.com",
#         "API_KEY": "pwd",
#         "RABBITMQ_HOST": "rabbit",
#         "RABBITMQ_PORT": "5672",
#         "RABBITMQ_USERNAME": "ru",
#         "RABBITMQ_PASSWORD": "rpw",
#         "RABBITMQ_VHOST": "/",
#     }
#     sys.modules["dotenv"] = SimpleNamespace(
#         dotenv_values=lambda *_, **__: fake_env
#     )

#     # ---- xmlrpc ---------------------------------------------------------
#     common_proxy = MagicMock(authenticate=lambda *_, **__: 1)
#     models_proxy = MagicMock()

#     xmlrpc_mod = types.ModuleType("xmlrpc")
#     xmlrpc_client_mod = types.ModuleType("xmlrpc.client")
#     xmlrpc_client_mod.ServerProxy = MagicMock(side_effect=[common_proxy, models_proxy])
#     xmlrpc_mod.client = xmlrpc_client_mod
#     sys.modules.update(
#         {
#             "xmlrpc": xmlrpc_mod,
#             "xmlrpc.client": xmlrpc_client_mod,
#         }
#     )

#     # ---- pika -----------------------------------------------------------
#     fake_channel = MagicMock()
#     fake_conn = MagicMock(channel=lambda: fake_channel, close=lambda: None)
#     sys.modules["pika"] = SimpleNamespace(
#         PlainCredentials=MagicMock(),
#         ConnectionParameters=MagicMock(),
#         BlockingConnection=MagicMock(return_value=fake_conn),
#     )

#     # ---- import file ----------------------------------------------------
#     spec = importlib.util.spec_from_file_location("consumers.consumer", CONSUMER_PATH)
#     module = importlib.util.module_from_spec(spec)
#     spec.loader.exec_module(module)

#     # expose models for convenience in tests
#     module.models = models_proxy
#     return module, fake_channel


# # ──────────────────────────────────────────────────────────────────────────────
# #  Helper – build minimal Attendify XML
# # ──────────────────────────────────────────────────────────────────────────────
# def _xml(op: str) -> bytes:
#     return f"""
# <attendify>
#   <info><operation>{op}</operation></info>
#   <user>
#     <uid>ABC123</uid>
#     <first_name>John</first_name>
#     <last_name>Doe</last_name>
#     <email>john@example.com</email>
#     <password>secret</password>
#     <title>Dr</title>
#   </user>
# </attendify>
# """.encode()


# # ──────────────────────────────────────────────────────────────────────────────
# #  Test‑case
# # ──────────────────────────────────────────────────────────────────────────────
# class TestConsumerCRUD(unittest.TestCase):
#     @classmethod
#     def setUpClass(cls):
#         cls.consumer, cls.ch = import_consumer()

#     # ------------------------------------------------------------------ #
#     #  Dispatcher                                                         #
#     # ------------------------------------------------------------------ #
#     def _call_process(self, op: str):
#         m = SimpleNamespace(delivery_tag=99)
#         self.consumer.process_message(self.ch, m, None, _xml(op))

#     def test_dispatch_create(self):
#         with patch.object(self.consumer, "_handle_user_create") as h:
#             self._call_process("create")
#             h.assert_called_once()
#             self.ch.basic_ack.assert_called_with(delivery_tag=99)

#     def test_dispatch_update(self):
#         with patch.object(self.consumer, "_handle_user_update") as h:
#             self._call_process("update")
#             h.assert_called_once()
#             self.ch.basic_ack.assert_called_with(delivery_tag=99)

#     def test_dispatch_delete(self):
#         with patch.object(self.consumer, "_handle_user_delete") as h:
#             self._call_process("delete")
#             h.assert_called_once()
#             self.ch.basic_ack.assert_called_with(delivery_tag=99)

#     # ------------------------------------------------------------------ #
#     #  Delete helper                                                      #
#     # ------------------------------------------------------------------ #
#     def test_handle_delete_invokes_delete_user(self):
#         xml_dict = self.consumer.xmltodict.parse(_xml("delete").decode())
#         with patch.object(self.consumer, "delete_user") as du:
#             self.consumer._handle_user_delete(xml_dict)
#             du.assert_called_once_with("ABC123")


# if __name__ == "__main__":
#     unittest.main()
