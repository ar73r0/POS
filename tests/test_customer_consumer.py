import unittest
from unittest.mock import patch, MagicMock
import json
import importlib.util

print(">>> LOADED CONSUMER TESTS")

class TestCreateCustomerConsumer(unittest.TestCase):
    def setUp(self):
        self.valid_xml = """<attendify>
            <info>
                <operation>create</operation>
                <sender>API</sender>
            </info>
            <user>
                <id>123</id>
                <first_name>Jane</first_name>
                <last_name>Doe</last_name>
                <title>Mr</title>
                <email>jane@example.com</email>
                <phone_number>1234567890</phone_number>
                <address>
                    <street>Main St</street>
                    <number>42</number>
                    <bus_number>A</bus_number>
                    <city>Brussels</city>
                    <postal_code>1000</postal_code>
                    <country>Belgium</country>
                </address>
                <from_company>false</from_company>
            </user>
        </attendify>"""

    def test_parse_attendify_user(self):
        spec = importlib.util.spec_from_file_location("create_customer_consumer", "../create_customer_consumer.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with patch.object(module, "get_title_id", return_value=1), \
             patch.object(module, "get_country_id", return_value=21):
            odoo_user, invoice_address, company_data, operation, sender = module.parse_attendify_user(self.valid_xml)

            self.assertEqual(odoo_user["name"], "Jane_Doe")
            self.assertEqual(odoo_user["ref"], "123")
            self.assertEqual(odoo_user["email"], "jane@example.com")
            self.assertEqual(odoo_user["city"], "Brussels")
            self.assertEqual(operation, "create")
            self.assertEqual(sender, "API")
            self.assertIsNone(company_data)
            self.assertIsNotNone(odoo_user)

    @patch("pika.BlockingConnection")
    def test_customer_callback_create_user(self, mock_conn):
        spec = importlib.util.spec_from_file_location("create_customer_consumer", "../create_customer_consumer.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        mock_models = MagicMock()
        mock_models.execute_kw.side_effect = [[], 1001]
        module.models = mock_models
        module.uid = 1
        module.db = "odoo"
        module.PASSWORD = "password"
        module.get_title_id = lambda title: 1
        module.get_country_id = lambda c: 21
        module.exchange_monitoring = "monitoring"
        module.routing_key_monitoring_success = "monitoring.success"
        module.routing_key_monitoring_failure = "monitoring.failure"

        mock_channel = MagicMock()
        module.channel = mock_channel

        class DummyMethod:
            routing_key = "user.register"

        body = self.valid_xml.encode()

        module.customer_callback(mock_channel, DummyMethod(), None, body)

        self.assertTrue(mock_models.execute_kw.called)
        mock_channel.basic_publish.assert_called()
        args, kwargs = mock_channel.basic_publish.call_args
        self.assertEqual(kwargs["routing_key"], "monitoring.success")



class TestDeleteCustomerConsumer(unittest.TestCase):

    @patch("builtins.print")
    @patch("pika.BlockingConnection")
    def test_callback_valid_json(self, mock_conn, mock_print):
        import importlib.util
        spec = importlib.util.spec_from_file_location("delete_customer_consumer", "../delete_customer_consumer.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with patch.object(module, "delete_user") as mock_delete_user:
            body = json.dumps({"email": "test@example.com"}).encode("utf-8")

            class DummyMethod:
                routing_key = "user.delete"

            module.callback(MagicMock(), DummyMethod(), None, body)
            mock_delete_user.assert_called_once_with("test@example.com")

    @patch("builtins.print")
    @patch("pika.BlockingConnection")
    def test_callback_invalid_json(self, mock_conn, mock_print):
        import importlib.util
        spec = importlib.util.spec_from_file_location("delete_customer_consumer", "../delete_customer_consumer.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with patch.object(module, "delete_user") as mock_delete_user:
            body = b'{invalid_json'
            class DummyMethod:
                routing_key = "user.delete"
            module.callback(MagicMock(), DummyMethod(), None, body)
            mock_print.assert_called()



class TestGetConsumerInfo(unittest.TestCase):
    def test_customer_info_fetch(self):
        spec = importlib.util.spec_from_file_location("get_consumer_info", "../get_consumer_info.py")
        module = importlib.util.module_from_spec(spec)

        with patch("xmlrpc.client.ServerProxy") as mock_proxy, \
             patch("pika.BlockingConnection"), \
             patch("builtins.print"):
            mock_common = MagicMock()
            mock_common.authenticate.return_value = 1
            mock_models = MagicMock()
            mock_models.execute_kw.return_value = [
                {"name": "Jane_Doe", "email": "jane@example.com"}
            ]
            mock_proxy.side_effect = [mock_common, mock_models, mock_common, mock_models]
            spec.loader.exec_module(module)

            self.assertTrue(True)  # Als het tot hier geraakt zonder fout: geslaagd.


if __name__ == "__main__":
    unittest.main()
