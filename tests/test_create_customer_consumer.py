import unittest
from unittest.mock import patch, MagicMock
import sys
import os
from io import StringIO
import xmlrpc.client
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from create_customer_consumer import customer_callback

class TestCustomerConsumer(unittest.TestCase):
    
    @patch('pika.BlockingConnection')
    @patch('xmlrpc.client.ServerProxy')
    @patch('xmltodict.parse')
    def test_customer_callback_success(self, mock_parse, mock_server_proxy, mock_pika):
        # Arrange
        mock_parse.return_value = {
            "attendify": {
                "info": {"operation": "create", "sender": "test_sender"},
                "user": {
                    "id": "1234",
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john.doe@example.com",
                    "phone_number": "123456789",
                    "address": {
                        "street": "Main St",
                        "number": "123",
                        "bus_number": "1",
                        "city": "Cityville",
                        "postal_code": "12345",
                        "country": "USA"
                    },
                    "payment_details": {
                        "facturation_address": {
                            "street": "Billing St",
                            "number": "456",
                            "city": "Cityville",
                            "postal_code": "12346",
                            "country": "USA"
                        }
                    }
                }
            }
        }

        mock_server_proxy.return_value = MagicMock()
        mock_server_proxy.return_value.execute_kw.return_value = [{'id': 1}]
        
        mock_pika.return_value = MagicMock()
        mock_pika.return_value.channel.return_value = MagicMock()

        # Create an instance of the function
        from create_customer_consumer import customer_callback

        body = "<attendify><info><operation>create</operation><sender>test_sender</sender></info><user><id>1234</id><first_name>John</first_name><last_name>Doe</last_name></user></attendify>"
        method = MagicMock()
        method.routing_key = 'user.register'
        properties = MagicMock()

        # Act
        customer_callback(mock_pika.return_value, method, properties, body.encode())

        # Assert
        mock_server_proxy.return_value.execute_kw.assert_called_with(
            'your_database', 'your_uid', 'your_password',
            'res.partner', 'create', [MagicMock()]
        )
        mock_pika.return_value.channel.return_value.basic_publish.assert_called_with(
            exchange='monitoring',
            routing_key='monitoring.success',
            body='<attendify><info><sender>KASSA</sender><operation>create</operation><monitoring>user.register.success</monitoring></info></attendify>'
        )
    
    @patch('pika.BlockingConnection')
    @patch('xmlrpc.client.ServerProxy')
    @patch('xmltodict.parse')
    def test_customer_callback_failure(self, mock_parse, mock_server_proxy, mock_pika):
        # Arrange
        mock_parse.return_value = {
            "attendify": {
                "info": {"operation": "create", "sender": "test_sender"},
                "user": {
                    "id": "1234",
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john.doe@example.com",
                    "phone_number": "123456789",
                    "address": {
                        "street": "Main St",
                        "number": "123",
                        "bus_number": "1",
                        "city": "Cityville",
                        "postal_code": "12345",
                        "country": "USA"
                    }
                }
            }
        }

        mock_server_proxy.return_value = MagicMock()
        mock_server_proxy.return_value.execute_kw.return_value = []

        mock_pika.return_value = MagicMock()
        mock_pika.return_value.channel.return_value = MagicMock()

        # Create an instance of the function
        from create_customer_consumer import customer_callback

        body = "<attendify><info><operation>create</operation><sender>test_sender</sender></info><user><id>1234</id><first_name>John</first_name><last_name>Doe</last_name></user></attendify>"
        method = MagicMock()
        method.routing_key = 'user.register'
        properties = MagicMock()

        # Act
        customer_callback(mock_pika.return_value, method, properties, body.encode())

        # Assert that failure callback was called
        mock_pika.return_value.channel.return_value.basic_publish.assert_called_with(
            exchange='monitoring',
            routing_key='monitoring.failure',
            body='<attendify><info><sender>KASSA</sender><operation>create</operation><monitoring>user.register.failure</monitoring><reason>User already exists</reason></info></attendify>'
        )

if __name__ == '__main__':
    unittest.main()
