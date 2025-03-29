import sys, os, pika
from dotenv import  dotenv_values
import xmlrpc.client
import dicttoxml
import json
import xml.etree.ElementTree as ET
import xmltodict

config = dotenv_values()

def main():
    url = "http://localhost:8069/"
    db = config["DATABASE"]
    USERNAME = config["EMAIL"]
    PASSWORD = config["API_KEY"]

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, USERNAME, PASSWORD, {})
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    credentials = pika.PlainCredentials(config["RABBITMQ_USERNAME"], config["RABBITMQ_PASSWORD"])
    params = pika.ConnectionParameters("localhost", 5672, config["RABBITMQ_VHOST"], credentials)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    exchange_name ='user.delete'
    routing_key = 'pos.user'
    queue_name = 'pos.user'

    channel.exchange_declare(exchange=exchange_name, exchange_type='topic', durable=True)
    channel.queue_declare(queue=queue_name, durable=True)
    channel.queue_bind(exchange=exchange_name, queue=queue_name, routing_key=routing_key)

    def get_country_id(country):
        country_name_to_code = {
            "Belgium": "BE",
            "France": "FR",
            "Netherlands": "NL",
            "Germany": "DE"
        }

        country_code = country_name_to_code.get(country)
        country_id = None

        if country_code:
            result = models.execute_kw(
                db, uid, PASSWORD,
                'res.country', 'search_read',
                [[['code', '=', country_code]]],
                {'fields': ['id'], 'limit': 1}
            )
            if result:
                country_id = result[0]['id']

        return country_id

    def parse_attendify_user(xml_data):
        try:
            parsed = xmltodict.parse(xml_data)
            user_data = parsed["attendify"]["user"]
            address = user_data["address"]
            street = address["street"]
            number = address["number"]
            bus = address.get("bus_number", "")
            street2 = f"{number} Bus {bus}"
            city = address["city"]
            zip_code = address["postal_code"]
            country = address["country"].strip().title()
            country_id = get_country_id(country)

            customer_data = {
                "name": user_data["name"],
                "email": user_data["email"],
                "phone": user_data["phone"],
                "street": street,
                "street2": street2.strip(),
                "city": city,
                "zip": zip_code,
                "country_id": country_id
            }

            return customer_data
        except Exception as e:
            print(f"Error parsing XML: {e}")
            return None

    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
    channel.start_consuming()

def callback(ch, method, properties, body):
    xml_data = body.decode("utf-8")
    customer_data = parse_attendify_user(xml_data)
    if customer_data:
        print(f"Customer Data: {customer_data}")
    else:
        print("Failed to parse customer data.")

if __name__ == "__main__":
    main()
