import pika
import xmlrpc.client
import xml.etree.ElementTree as ET
from dotenv import dotenv_values

# Load environment variables
config = dotenv_values()

# Odoo credentials
url = "http://localhost:8069/"
db = config["DATABASE"]
USERNAME = config["EMAIL"]
PASSWORD = config["API_KEY"]

# Authenticate with Odoo
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# RabbitMQ connection
credentials = pika.PlainCredentials(
    config["RABBITMQ_USERNAME"],
    config["RABBITMQ_PASSWORD"]
)
params = pika.ConnectionParameters(
    host="localhost",  
    port=5672,
    virtual_host=config["RABBITMQ_VHOST"],
    credentials=credentials
)
connection = pika.BlockingConnection(params)
channel = connection.channel()

# Matching exchange, queue, routing key
exchange_name = 'user-management'
routing_key = 'user.update'
queue_name = 'pos.user'

channel.exchange_declare(exchange=exchange_name, exchange_type='direct', durable=True)
channel.queue_declare(queue=queue_name, durable=True)
channel.queue_bind(exchange=exchange_name, queue=queue_name, routing_key=routing_key)

def on_message(ch, method, properties, body):
    """Handle <operation>user.update</operation> messages – only updates existing partners."""
    try:
        root = ET.fromstring(body)
        operation = root.find('info/operation').text.strip()
        print("Bericht ontvangen: Operatie =", operation)

        if operation.lower() == "user.update":
            # Extract user data
            first_name = root.find('user/first_name').text.strip()
            last_name = root.find('user/last_name').text.strip()
            email_element = root.find('user/email')
            email = email_element.text.strip() if email_element is not None else ""

            title_element = root.find('user/title')
            title = title_element.text.strip() if title_element is not None else ""

            new_name = f"{first_name} {last_name}"

            # Search for existing res.partner by email
            partner_ids = models.execute_kw(
                db, uid, PASSWORD,
                'res.partner',
                'search',
                [[('email', 'ilike', email)]],
                {'context': {'active_test': False}}
            )
            print("Gevonden partner IDs:", partner_ids)

            if partner_ids:
                # Update the partner 
                update_fields = {
                    'name': new_name,
                    'email': email,
                    'title': title
                }
                result = models.execute_kw(
                    db, uid, PASSWORD,
                    'res.partner',
                    'write',
                    [partner_ids, update_fields]
                )
                print("Partner bijgewerkt:", result, update_fields)
            else:
                print(f"Geen bestaande partner gevonden met e-mailadres: {email}. Geen update uitgevoerd.")
        else:
            print("Operatie niet ondersteund:", operation)
    except Exception as e:
        print(f"Fout tijdens verwerking: {e}")

# Start consuming
channel.basic_consume(queue=queue_name, on_message_callback=on_message, auto_ack=True)
print("Waiting for user.update messages...")
channel.start_consuming()
