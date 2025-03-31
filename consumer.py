import sys
import os
import pika
import json
import xmlrpc.client
import xmltodict
import xml.etree.ElementTree as ET
from dotenv import dotenv_values
 
config = dotenv_values()
 
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
 
exchange_main = 'user-management'
queue_main = 'pos.user'
 
channel.exchange_declare(exchange=exchange_main, exchange_type="direct", durable=True)
channel.queue_declare(queue=queue_main, durable=True)
 
for rk in ['user.register', 'user.update', 'user.delete']:
    channel.queue_bind(queue=queue_main, exchange=exchange_main, routing_key=rk)
 
exchange_monitoring = 'monitoring'
routing_key_monitoring_success = 'monitoring.success'
routing_key_monitoring_failure = 'monitoring.failure'
queue_monitoring = 'monitoring'
 
channel.exchange_declare(exchange=exchange_monitoring, exchange_type='topic', durable=True)
channel.queue_declare(queue=queue_monitoring, durable=True)
channel.queue_bind(exchange=exchange_monitoring, queue=queue_monitoring, routing_key=routing_key_monitoring_success)
channel.queue_bind(exchange=exchange_monitoring, queue=queue_monitoring, routing_key=routing_key_monitoring_failure)
 
def delete_user(email):
    partner_ids = models.execute_kw(
        db, uid, PASSWORD,
        'res.partner', 'search',
        [[['email', 'ilike', email]]],
        {'context': {'active_test': False}}
    )
    if partner_ids:
        models.execute_kw(db, uid, PASSWORD, 'res.partner', 'unlink', [partner_ids])
        print(f"Customer {email} deleted successfully.")
    else:
        print(f"Customer {email} not found.")
 
def get_title_id(title):
    result = models.execute_kw(
        db, uid, PASSWORD,
        'res.partner.title', 'search_read',
        [[['shortcut', '=', title]]],
        {'fields': ['id'], 'limit': 1}
    )
    return result[0]['id'] if result else None
 
def process_message(ch, method, properties, body):
    try:
        routing_key = method.routing_key
 
        if routing_key == "user.delete":
            try:
                print("Body (raw):", body)
                print("Body (decoded):", body.decode('utf-8', errors='replace'))
 
                data = xmltodict.parse(body.decode("utf-8"))
                email = data['attendify']['user'].get("email")
                if email:
                    delete_user(email)
                else:
                    print("Invalid delete request format.")
            except Exception as e:
                print(f"Error parsing XML in delete message: {e}")
 
        elif routing_key == "user.update":
            root = ET.fromstring(body)
            operation = root.find('info/operation').text.strip().lower()
 
            if operation != 'user.update':
                print("Operation mismatch in user.update message")
                return
 
            email = root.find('user/email').text.strip()
            first_name = root.find('user/first_name').text.strip()
            last_name = root.find('user/last_name').text.strip()
            title = root.find('user/title').text.strip() if root.find('user/title') is not None else ""
 
            partner_ids = models.execute_kw(
                db, uid, PASSWORD,
                'res.partner', 'search',
                [[('email', 'ilike', email)]],
                {'context': {'active_test': False}}
            )
 
            if partner_ids:
                update_fields = {
                    'name': f"{first_name} {last_name}",
                    'email': email,
                    'title': title
                }
                models.execute_kw(db, uid, PASSWORD, 'res.partner', 'write', [partner_ids, update_fields])
                print(f"Updated user {email}.")
            else:
                print(f"No user found with email {email}.")
 
        elif routing_key == "user.register":
            data = xmltodict.parse(body.decode("utf-8"))
            user_data = data['attendify']['user']
            name = f"{user_data['first_name']}_{user_data['last_name']}"
            email = user_data.get("email")
            phone = user_data.get("phone_number")
            street = user_data['address']['street']
            number = user_data['address']['number']
            bus = user_data['address'].get('bus_number', '')
            street2 = f"{number} Bus {bus}"
            city = user_data['address']['city']
            zip_code = user_data['address']['postal_code']
 
            existing_user = models.execute_kw(
                db, uid, PASSWORD,
                'res.partner', 'search_read',
                [[['email', '=', email]]],
                {'fields': ['id'], 'limit': 1}
            )
 
            if existing_user:
                print(f"User already exists: {email}")
            else:
                new_user = {
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'street': street,
                    'street2': street2,
                    'city': city,
                    'zip': zip_code,
                    'customer_rank': 1,
                    'is_company': False,
                    'company_type': 'person',
                    'title': get_title_id(user_data.get('title', ''))
                }
                new_id = models.execute_kw(db, uid, PASSWORD, 'res.partner', 'create', [new_user])
                print(f"Registered new user: {email} (ID {new_id})")
 
        else:
            print(f"Unknown routing key: {routing_key}")
 
    except Exception as e:
        print(f"Error processing message: {e}")
 
 
channel.basic_consume(queue=queue_main, on_message_callback=process_message, auto_ack=True)
print("Waiting for user messages...")
channel.start_consuming()
 