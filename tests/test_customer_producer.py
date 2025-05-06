import unittest
from unittest.mock import patch, MagicMock
import importlib.util

print(">>> LOADED PRODUCER TESTS")

class TestCreateCustomerProducer(unittest.TestCase):

    @patch("pika.BlockingConnection")
    def test_create_message_sent(self, mock_conn):
        print(">>> RUNNING test_create_message_sent")
        mock_channel = MagicMock()
        mock_conn.return_value.channel.return_value = mock_channel

        spec = importlib.util.spec_from_file_location("create_customer_producer", "create_customer_producer.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        mock_channel.basic_publish.assert_called_once()


class TestDeleteCustomerProducer(unittest.TestCase):

    @patch("pika.BlockingConnection")
    def test_send_delete_request(self, mock_conn):
        print(">>> RUNNING test_send_delete_request")
        mock_channel = MagicMock()
        mock_conn.return_value.channel.return_value = mock_channel

        spec = importlib.util.spec_from_file_location("delete_customer_producer", "delete_customer_producer.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        module.send_delete_request("john@example.com")
        mock_channel.basic_publish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
