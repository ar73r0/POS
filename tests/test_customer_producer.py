import os
import sys
import unittest
import importlib.util
from unittest.mock import patch, MagicMock

#  Helpers ─ project‑root + dynamic importer
TEST_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def import_module(filename: str, modname: str):
    """Import *filename* (from project‑root) under the name *modname*."""
    path = os.path.join(PROJECT_ROOT, filename)
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


print(">>> LOADED PRODUCER TESTS")


_FAKE_ENV = {
    "DATABASE": "db",
    "EMAIL": "user@example.com",
    "API_KEY": "pwd",
    "RABBITMQ_USERNAME": "u",
    "RABBITMQ_PASSWORD": "p",
    "RABBITMQ_HOST": "localhost",
    "RABBITMQ_PORT": "5672",
    "RABBITMQ_VHOST": "vh",
}

#  CREATE  -------------------------------------------------------------------
class TestCreateCustomerProducer(unittest.TestCase):
    """Verifies that the create‑producer publishes exactly one message."""

    def test_create_message_sent(self):
        mock_channel = MagicMock()

        with patch("dotenv.dotenv_values", return_value=_FAKE_ENV), \
             patch.dict(sys.modules, {"bcrypt": MagicMock()}), \
             patch("pika.PlainCredentials"), \
             patch("pika.ConnectionParameters"), \
             patch("pika.BasicProperties"), \
             patch("pika.BlockingConnection") as mock_conn:

            mock_conn.return_value.channel.return_value = mock_channel

            import_module("create_customer_producer.py",
                          "create_customer_producer")

        mock_channel.basic_publish.assert_called_once()

#  DELETE  -------------------------------------------------------------------
class TestDeleteCustomerProducer(unittest.TestCase):
    """Verifies that send_delete_request publishes one message."""

    def test_send_delete_request(self):
        mock_channel = MagicMock()

        with patch("dotenv.dotenv_values", return_value=_FAKE_ENV), \
             patch("pika.PlainCredentials"), \
             patch("pika.ConnectionParameters"), \
             patch("pika.BasicProperties"), \
             patch("pika.BlockingConnection") as mock_conn:

            mock_conn.return_value.channel.return_value = mock_channel

            module = import_module("delete_customer_producer.py",
                                   "delete_customer_producer")

            module.send_delete_request("john@example.com")

        mock_channel.basic_publish.assert_called_once()

#  GET  ----------------------------------------------------------------------
class TestGetProducerInfo(unittest.TestCase):
    """Verifies that get_producer_info publishes at least one message."""

    def test_get_message_sent(self):
        mock_channel = MagicMock()

        with patch("dotenv.dotenv_values", return_value=_FAKE_ENV), \
             patch("pika.PlainCredentials"), \
             patch("pika.ConnectionParameters"), \
             patch("pika.BasicProperties"), \
             patch("pika.BlockingConnection") as mock_conn, \
             patch("xmlrpc.client.ServerProxy") as mock_sp:

            mock_conn.return_value.channel.return_value = mock_channel

            common = MagicMock(authenticate=MagicMock(return_value=1))
            models = MagicMock()
            models.execute_kw.return_value = [
                {"name": "Jane Doe", "email": "jane@example.com",
                 "phone": "123456789"}
            ]

            def proxy_factory(url, *_, **__):
                return common if url.endswith("/common") else models

            mock_sp.side_effect = proxy_factory

            import_module("get_producer_info.py", "get_producer_info")

        self.assertTrue(mock_channel.basic_publish.called)


if __name__ == "__main__":
    unittest.main()
