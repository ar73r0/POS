import sys
import os

# Add the root directory to the system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import patch, MagicMock
import xmltodict
from create_customer_consumer import get_country_id, get_title_id, get_or_create_company_id, parse_attendify_user, customer_callback
# Testen kunnen zoals eerder worden gedefinieerd
from unittest.mock import ANY


@patch("create_customer_consumer.models.execute_kw")
def test_get_country_id_found(mock_execute_kw):
    # Mock a successful response from the Odoo RPC call
    mock_execute_kw.return_value = [{'id': 123}]
    
    result = get_country_id("Canada")
    
    assert result == 123
    mock_execute_kw.assert_called_once()

@patch("create_customer_consumer.models.execute_kw")
def test_get_country_id_not_found(mock_execute_kw):
    # Mock an empty response
    mock_execute_kw.return_value = []

    result = get_country_id("Narnia")  # Not a real country
    assert result is None
    mock_execute_kw.assert_called_once()

@patch("create_customer_consumer.models.execute_kw")
def test_get_title_id_found(mock_execute_kw):
    # Simulate a match found for the title
    mock_execute_kw.return_value = [{'id': 456}]
    
    from create_customer_consumer import get_title_id
    result = get_title_id("Mr")
    
    assert result == 456
    mock_execute_kw.assert_called_once_with(
        ANY, ANY, ANY,
        'res.partner.title', 'search_read',
        [[["shortcut", "=", "Mr"]]], 
        {'fields': ['id'], 'limit': 1}
    )

@patch("create_customer_consumer.models.execute_kw")
def test_get_title_id_not_found(mock_execute_kw):
    # Simulate no match found
    mock_execute_kw.return_value = []

    from create_customer_consumer import get_title_id
    result = get_title_id("Emperor")
    
    assert result is None
    mock_execute_kw.assert_called_once()

@patch("create_customer_consumer.models.execute_kw")
def test_get_or_create_company_id_existing(mock_execute_kw):
    # First call to search_read returns existing company
    mock_execute_kw.side_effect = [
        [{'id': 789}],  # existing company found
    ]
    
    from create_customer_consumer import get_or_create_company_id
    company_data = {
        'name': 'Acme Inc.',
        'vat': 'US123456789'
    }
    
    result = get_or_create_company_id(
        models=mock_execute_kw,  # passing the mock as models
        db="fake_db",
        uid=1,
        password="fake_pwd",
        company_data=company_data
    )

    assert result == 789
    assert mock_execute_kw.call_count == 1  # only search_read was called

@patch("create_customer_consumer.models.execute_kw")
def test_get_or_create_company_id_new(mock_execute_kw):
    # First call to search_read returns nothing, second call creates a new company
    mock_execute_kw.side_effect = [
        [],         # no existing company
        999         # newly created company ID
    ]
    
    from create_customer_consumer import get_or_create_company_id
    company_data = {
        'name': 'Globex Corp.',
        'vat': 'DE987654321'
    }
    
    result = get_or_create_company_id(
        models=mock_execute_kw,
        db="fake_db",
        uid=1,
        password="fake_pwd",
        company_data=company_data
    )

    assert result == 999
    assert mock_execute_kw.call_count == 2

# Sample XML data for testing
valid_xml_data = '''<attendify>
    <info>
        <operation>create</operation>
        <sender>system</sender>
    </info>
    <user>
        <id>1</id>
        <first_name>John</first_name>
        <last_name>Doe</last_name>
        <email>john.doe@example.com</email>
        <phone_number>1234567890</phone_number>
        <title>Mr</title>
        <address>
            <street>Main St</street>
            <number>123</number>
            <bus_number>4A</bus_number>
            <city>New York</city>
            <postal_code>10001</postal_code>
            <country>USA</country>
        </address>
        <payment_details>
            <facturation_address>
                <street>Billing St</street>
                <number>456</number>
                <company_bus_number>12B</company_bus_number>
                <city>Los Angeles</city>
                <postal_code>90001</postal_code>
                <country>USA</country>
            </facturation_address>
        </payment_details>
    </user>
</attendify>'''

invalid_xml_data = '''<attendify>
    <info>
        <operation>create</operation>
    </info>
</attendify>'''

# Test for successful XML parsing
@patch("create_customer_consumer.get_title_id")
@patch("create_customer_consumer.get_country_id")
def test_parse_attendify_user_success(mock_get_country_id, mock_get_title_id):
    # Mock return values
    mock_get_country_id.return_value = 1
    mock_get_title_id.return_value = 2

    # Call the function
    odoo_user, invoice_address, company_data, operation, sender = parse_attendify_user(valid_xml_data)

    # Assert the returned data is as expected
    assert odoo_user["name"] == "John_Doe"
    assert odoo_user["email"] == "john.doe@example.com"
    assert odoo_user["phone"] == "1234567890"
    assert odoo_user["street"] == "Main St"
    assert odoo_user["street2"] == "123 Bus 4A"
    assert odoo_user["city"] == "New York"
    assert odoo_user["zip"] == "10001"
    assert odoo_user["country_id"] == 1
    assert operation == "create"
    assert sender == "system"
    assert invoice_address is not None
    assert company_data is None

# Test for invalid XML parsing
@patch("create_customer_consumer.get_title_id")
@patch("create_customer_consumer.get_country_id")
def test_parse_attendify_user_invalid_xml(mock_get_country_id, mock_get_title_id):
    # Mock return values (though they won't be used in this case)
    mock_get_country_id.return_value = 1
    mock_get_title_id.return_value = 2

    # Call the function with invalid XML
    odoo_user, invoice_address, company_data, operation, sender = parse_attendify_user(invalid_xml_data)

    # Assert that the function returns empty or None values for invalid XML
    assert odoo_user == {}
    assert invoice_address is None
    assert company_data is None
    assert operation is None
    assert sender is None


# Test for successful XML parsing and user creation
@patch("create_customer_consumer.models.execute_kw")
def test_customer_callback_create(mock_execute_kw):
    # Mock the necessary functions
    mock_execute_kw.return_value = [{'id': 1}]  # Simulating that user does not exist yet
    
    # Mock the channel object to track publish calls
    mock_channel = MagicMock()
    
    # Simulate the XML data (valid case)
    valid_xml_data = '''<attendify>
        <info>
            <operation>create</operation>
            <sender>system</sender>
        </info>
        <user>
            <id>1</id>
            <first_name>John</first_name>
            <last_name>Doe</last_name>
            <email>john.doe@example.com</email>
            <phone_number>1234567890</phone_number>
            <title>Mr</title>
            <address>
                <street>Main St</street>
                <number>123</number>
                <bus_number>4A</bus_number>
                <city>New York</city>
                <postal_code>10001</postal_code>
                <country>USA</country>
            </address>
        </user>
    </attendify>'''

    mock_parse_attendify_user = MagicMock(return_value=(
        {"ref": "1", "name": "John_Doe", "email": "john.doe@example.com", "phone": "1234567890", "street": "Main St"},
        None, None, "create", "system"
    ))
    
    # Patch the function
    with patch("create_customer_consumer.parse_attendify_user", mock_parse_attendify_user):
        # Call the function with mock data
        customer_callback(mock_channel, MagicMock(routing_key="user.register"), MagicMock(), valid_xml_data)
    
    # Check if the channel's basic_publish method was called with the correct success XML
    mock_channel.basic_publish.assert_called_with(
        exchange="monitoring_exchange",
        routing_key="user.register.success",
        body="""
            <attendify>
                <info>
                    <sender>KASSA</sender>
                    <operation>create</operation>
                    <monitoring>user.register.success</monitoring>
                </info>
            </attendify>
        """
    )


# Test when user already exists
@patch("create_customer_consumer.models.execute_kw")
def test_customer_callback_user_exists(mock_execute_kw):
    # Mock the necessary functions
    mock_execute_kw.return_value = [{'id': 1}]  # Simulating that user already exists
    
    # Mock the channel object to track publish calls
    mock_channel = MagicMock()
    
    # Simulate the XML data (valid case)
    valid_xml_data = '''<attendify>
        <info>
            <operation>create</operation>
            <sender>system</sender>
        </info>
        <user>
            <id>1</id>
            <first_name>John</first_name>
            <last_name>Doe</last_name>
            <email>john.doe@example.com</email>
            <phone_number>1234567890</phone_number>
            <title>Mr</title>
            <address>
                <street>Main St</street>
                <number>123</number>
                <bus_number>4A</bus_number>
                <city>New York</city>
                <postal_code>10001</postal_code>
                <country>USA</country>
            </address>
        </user>
    </attendify>'''

    mock_parse_attendify_user = MagicMock(return_value=(
        {"ref": "1", "name": "John_Doe", "email": "john.doe@example.com", "phone": "1234567890", "street": "Main St"},
        None, None, "create", "system"
    ))
    
    # Patch the function
    with patch("create_customer_consumer.parse_attendify_user", mock_parse_attendify_user):
        # Call the function with mock data
        customer_callback(mock_channel, MagicMock(routing_key="user.register"), MagicMock(), valid_xml_data)
    
    # Check if the failure XML is published (user already exists)
    mock_channel.basic_publish.assert_called_with(
        exchange="monitoring_exchange",
        routing_key="user.register.failure",
        body="""
            <attendify>
                <info>
                    <sender>KASSA</sender>
                    <operation>create</operation>
                    <monitoring>user.register.failure</monitoring>
                    <reason>User already exists</reason>
                </info>
            </attendify>
        """
    )


# Test when operation does not match routing_key
@patch("create_customer_consumer.models.execute_kw")
def test_customer_callback_invalid_operation(mock_execute_kw):
    # Simulate an operation that does not match
    valid_xml_data = '''<attendify>
        <info>
            <operation>delete</operation>
            <sender>system</sender>
        </info>
    </attendify>'''
    
    mock_channel = MagicMock()
    
    # Call the function with invalid operation
    customer_callback(mock_channel, MagicMock(routing_key="user.register"), MagicMock(), valid_xml_data)
    
    # Assert that the failure route is triggered for invalid operations
    mock_channel.basic_publish.assert_called_with(
        exchange="monitoring_exchange",
        routing_key="user.register.failure",
        body="""
            <attendify>
                <info>
                    <sender>KASSA</sender>
                    <operation>delete</operation>
                    <monitoring>user.register.failure</monitoring>
                    <reason>Invalid operation</reason>
                </info>
            </attendify>
        """
    )
