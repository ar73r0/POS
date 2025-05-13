import os
import sys
import unittest
import importlib.util
from unittest.mock import patch, MagicMock

#  Helpers: project root + dynamic importer
TEST_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def import_consumer(filename: str, modname: str):
    """Import *filename* (from project‑root) as module *modname*."""
    path = os.path.join(PROJECT_ROOT, filename)
    spec = importlib.util.spec_from_file_location(modname, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


print(f">>> LOADED CONSUMER TESTS (root = {PROJECT_ROOT})")


#  CREATE
class TestCreateCustomerConsumer(unittest.TestCase):
    """Covers the *create* branch of create_customer_consumer.customer_callback."""

    def setUp(self):
        self.valid_xml = "<attendify></attendify>"

    @patch("builtins.print")        
    def test_customer_callback_create_user(self, _):
        module = import_consumer("create_customer_consumer.py",
                                 "create_customer_consumer")

        odoo_user = {
            "name": "Jane_Doe",
            "ref": "123",
            "email": "jane@example.com",
            "phone": "0123456789",
            "street": "Main St",
            "city": "Brussels",
            "zip": "1000",
            "country_id": 21,
        }
        invoice_address, company_data = {}, None
        operation, sender = "create", "API"

        def fake_execute_kw(db, uid, pwd, model, method, *a, **k):
            if method in ("search", "search_read"):
                return []
            if method == "create":
                return 42
            return None

        with patch.object(module, "parse_attendify_user",
                          return_value=(odoo_user, invoice_address,
                                        company_data, operation, sender)), \
             patch.object(module, "get_country_id", return_value=21):

            module.models = MagicMock()
            module.models.execute_kw.side_effect = fake_execute_kw

            module.db, module.uid, module.PASSWORD = "db", 1, "pwd"
            module.exchange_main = "exch.main"
            module.exchange_monitoring = "exch.mon"
            module.routing_key_monitoring_success = "mon.succ"
            module.routing_key_monitoring_failure = "mon.fail"
            module.channel = MagicMock()

            class DummyMethod:
                routing_key = "user.register"

            module.customer_callback(module.channel, DummyMethod(), None,
                                     self.valid_xml.encode())

            module.models.execute_kw.assert_any_call(
                "db", 1, "pwd", 'res.partner', 'create', [odoo_user]
            )

            _, kwargs = module.channel.basic_publish.call_args
            self.assertEqual(kwargs["exchange"], "exch.mon")
            self.assertEqual(kwargs["routing_key"], "mon.succ")

            body_str: str = kwargs["body"]
            self.assertIn("<attendify>", body_str)
            self.assertIn("<monitoring>user.register.success</monitoring>",
                          body_str)

#  UPDATE
class TestUpdateCustomerConsumer(unittest.TestCase):
    """Verifies the (not‑yet‑implemented) update route publishes failure."""

    def setUp(self):
        self.update_xml = "<attendify></attendify>"

    def test_customer_callback_update_user_publishes_failure(self):
        module = import_consumer("create_customer_consumer.py",
                                 "create_customer_consumer")

        with patch.object(module, "parse_attendify_user",
                          return_value=({"ref": "123"}, None, None,
                                        "update", "API")):

            module.models = MagicMock()
            # search_read returns an existing partner – triggers update flow
            module.models.execute_kw.side_effect = [[{"id": 99}]]

            module.db, module.uid, module.PASSWORD = "db", 1, "pwd"
            module.exchange_monitoring = "exch.mon"
            module.routing_key_monitoring_failure = "mon.fail"
            module.channel = MagicMock()

            class DummyMethod:
                routing_key = "user.update"

            module.customer_callback(module.channel, DummyMethod(), None,
                                     self.update_xml.encode())

            module.channel.basic_publish.assert_called_once_with(
                exchange="exch.mon",
                routing_key="mon.fail",
                body=unittest.mock.ANY,
            )

#  DELETE
class TestDeleteCustomerConsumer(unittest.TestCase):
    """Covers delete_customer_consumer.delete_user & callback."""

    def setUp(self):
        with patch("dotenv.dotenv_values", return_value={
            "DATABASE": "db",
            "EMAIL": "user@example.com",
            "API_KEY": "pwd",
            "RABBITMQ_USERNAME": "u",
            "RABBITMQ_PASSWORD": "p",
            "RABBITMQ_VHOST": "vh",
        }), \
             patch("xmlrpc.client.ServerProxy",
                   return_value=MagicMock(authenticate=lambda *_, **__: 1)), \
             patch("pika.BlockingConnection",
                   return_value=MagicMock(channel=lambda: MagicMock())):
            self.module = import_consumer("delete_customer_consumer.py",
                                          "delete_customer_consumer")

    def test_delete_user_unlink_calls(self):
        self.module.models.execute_kw.return_value = [456]
        self.module.delete_user("foo@bar.com")

        self.module.models.execute_kw.assert_any_call(
            self.module.db, self.module.uid, self.module.PASSWORD,
            'res.partner', 'search',
            [[['email', 'ilike', 'foo@bar.com']]],
            {'context': {'active_test': False}}
        )
        self.module.models.execute_kw.assert_any_call(
            self.module.db, self.module.uid, self.module.PASSWORD,
            'res.partner', 'unlink', [[456]]
        )

    def test_callback_with_valid_email(self):
        self.module.delete_user = MagicMock()

        mock_channel = MagicMock()
        class DummyMethod: pass
        body = b'{"email": "bar@baz.com"}'

        self.module.callback(mock_channel, DummyMethod(), None, body)
        self.module.delete_user.assert_called_once_with("bar@baz.com")

#  READ / GET
class TestGetConsumerInfo(unittest.TestCase):
    """Checks that get_consumer_info.py fetches data and prints it."""

    def test_get_consumer_info_prints(self):
        with patch("dotenv.dotenv_values", return_value={
            "EMAIL": "user@example.com",
            "API_KEY": "pwd",
            "RABBITMQ_USERNAME": "u",
            "RABBITMQ_PASSWORD": "p",
            "RABBITMQ_VHOST": "vh",
            "RABBITMQ_HOST": "localhost",
        }), \
             patch("pika.PlainCredentials"), \
             patch("pika.ConnectionParameters", return_value=MagicMock()), \
             patch("pika.BlockingConnection",
                   return_value=MagicMock(channel=lambda: MagicMock())), \
             patch("xmlrpc.client.ServerProxy") as mock_sp, \
             patch("builtins.print") as mock_print:

            common = MagicMock(authenticate=MagicMock(return_value=1))
            models = MagicMock()
            models.execute_kw.return_value = [{
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
                "password": "secret",
                "title": "Ms",
            }]

            def serverproxy_factory(url, *_, **__):
                return common if url.endswith("/common") else models

            mock_sp.side_effect = serverproxy_factory

            import_consumer("get_consumer_info.py", "get_consumer_info")

        self.assertTrue(models.execute_kw.called)
        self.assertTrue(mock_print.called)


if __name__ == "__main__":
    unittest.main()
