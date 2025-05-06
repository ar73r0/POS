import unittest
from unittest.mock import patch, MagicMock
import importlib.util

class TestDeleteCustomerProducer(unittest.TestCase):

    @patch("delete_customer_producer.pika.BlockingConnection")
    def test_send_delete_request(self, mock_connection):
        from delete_customer_producer import send_delete_request

        mock_channel = MagicMock()
        mock_connection.return_value.channel.return_value = mock_channel

        send_delete_request("john@example.com")

        mock_channel.basic_publish.assert_called_once()
        args, kwargs = mock_channel.basic_publish.call_args
        self.assertEqual(kwargs["exchange"], "user-management")
        self.assertEqual(kwargs["routing_key"], "user.delete")
        self.assertIn("<email>john@example.com</email>", kwargs["body"])
        self.assertIn("<operation>delete</operation>", kwargs["body"])


class TestCreateCustomerProducer(unittest.TestCase):

    @patch("pika.BlockingConnection")
    def test_create_message_sent(self, mock_connection):
        import importlib.util
        import os

        path = os.path.abspath("create_customer_producer.py")
        spec = importlib.util.spec_from_file_location("create_customer_producer", path)
        producer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(producer)

        mock_channel = MagicMock()
        mock_connection.return_value.channel.return_value = mock_channel

        mock_channel.basic_publish(exchange="user-management",
                                   routing_key="user.register",
                                   body=producer.xml_min,
                                   properties=None)

        mock_channel.basic_publish.assert_called_once()
        args, kwargs = mock_channel.basic_publish.call_args
        self.assertIn("<first_name>osman</first_name>", kwargs["body"])

if __name__ == "__main__":
    unittest.main()
