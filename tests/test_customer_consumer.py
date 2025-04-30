import unittest
import pika
from unittest.mock import patch, MagicMock
from create_customer_consumer import parse_attendify_user, customer_callback

class TestCustomerConsumer(unittest.TestCase):

    def setUp(self):
        self.valid_xml = """
        <attendify>
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
        </attendify>
        """

    @patch("create_customer_consumer.get_title_id", return_value=1)
    @patch("create_customer_consumer.get_country_id", return_value=21)
    def test_parse_minimal_valid_user(self, mock_country, mock_title):
        odoo_user, invoice_address, company_data, operation, sender = parse_attendify_user(self.valid_xml)

        self.assertEqual(odoo_user["name"], "Jane_Doe")
        self.assertEqual(odoo_user["ref"], "123")
        self.assertEqual(odoo_user["email"], "jane@example.com")
        self.assertEqual(odoo_user["city"], "Brussels")
        self.assertEqual(operation, "create")
        self.assertEqual(sender, "API")
        self.assertIsNone(company_data)
        self.assertIsNone(invoice_address)

    @patch("create_customer_consumer.get_title_id", return_value=1)
    @patch("create_customer_consumer.get_country_id", return_value=21)
    def test_customer_callback(self, mock_country, mock_title):
        mock_models = MagicMock()
        mock_models.execute_kw.side_effect = [
            [],  # search_read (no existing user)
            1234  # create partner
        ]

        mock_channel = MagicMock()

        class DummyMethod:
            routing_key = "user.register"

        body = self.valid_xml.encode()

        customer_callback(
            mock_channel,
            DummyMethod(),
            None,
            body,
            models=mock_models,
            db="odoo",
            uid=1,
            password="password",
            exchange_monitoring="monitoring",
            routing_key_success="monitoring.success",
            routing_key_failure="monitoring.failure"
        )

        self.assertTrue(mock_models.execute_kw.called)
        self.assertTrue(mock_channel.basic_publish.called)


if __name__ == "__main__":
    unittest.main()

# =============================
# DELETE CUSTOMER CONSUMER TESTS
# =============================
import json

class TestDeleteCustomerConsumer(unittest.TestCase):

    @patch("delete_customer_consumer.models")
    @patch("delete_customer_consumer.uid", 1)
    @patch("delete_customer_consumer.db", "odoo")
    @patch("delete_customer_consumer.PASSWORD", "secret")
    def test_delete_user_found(self, mock_models):
        from delete_customer_consumer import delete_user

        mock_models.execute_kw.side_effect = [[42], None]

        with patch("builtins.print") as mock_print:
            delete_user("test@example.com")
            mock_print.assert_called_with("Customer test@example.com deleted successfully.")

    @patch("delete_customer_consumer.models")
    @patch("delete_customer_consumer.uid", 1)
    @patch("delete_customer_consumer.db", "odoo")
    @patch("delete_customer_consumer.PASSWORD", "secret")
    def test_delete_user_not_found(self, mock_models):
        from delete_customer_consumer import delete_user

        mock_models.execute_kw.return_value = []

        with patch("builtins.print") as mock_print:
            delete_user("missing@example.com")
            mock_print.assert_called_with("Customer missing@example.com not found.")

    @patch("delete_customer_consumer.delete_user")
    def test_callback_valid_email(self, mock_delete_user):
        from delete_customer_consumer import callback

        mock_ch = MagicMock()
        body = json.dumps({"email": "test@example.com"}).encode("utf-8")

        class DummyMethod:
            routing_key = "user.delete"

        callback(mock_ch, DummyMethod(), None, body)
        mock_delete_user.assert_called_with("test@example.com")

    @patch("delete_customer_consumer.delete_user")
    def test_callback_invalid_json(self, mock_delete_user):
        from delete_customer_consumer import callback

        mock_ch = MagicMock()
        bad_body = b'{invalid'

        with patch("builtins.print") as mock_print:
            class DummyMethod:
                routing_key = "user.delete"
            callback(mock_ch, DummyMethod(), None, bad_body)
            mock_print.assert_called()


# =========================
# GET CUSTOMER INFO TESTS
# =========================
class TestGetConsumerInfo(unittest.TestCase):

    @patch("get_consumer_info.models")
    @patch("get_consumer_info.uid", 1)
    @patch("get_consumer_info.db", "odoo")
    @patch("get_consumer_info.PASSWORD", "secret")
    def test_customer_info_output(self, mock_models):
        from get_consumer_info import customer_info

        mock_models.execute_kw.return_value = [
            {"name": "Jane_Doe", "email": "jane@example.com", "phone": "123", "street": "Main St", "city": "Brussels", "zip": "1000", "country_id": [1, "Belgium"]}
        ]

        self.assertEqual(len(customer_info), 1)
        self.assertEqual(customer_info[0]["email"], "jane@example.com")