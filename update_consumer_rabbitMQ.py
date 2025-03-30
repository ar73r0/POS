import pika
import xmlrpc.client
import xml.etree.ElementTree as ET
from dotenv import dotenv_values

# Load environment variables from .env
config = dotenv_values()

# Odoo credentials
url = "http://localhost:8069/" 
db = config["DATABASE"]
USERNAME = config["EMAIL"]
PASSWORD = config["API_KEY"]

# XML-RPC setup for Odoo
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# RabbitMQ credentials from .env
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

# RabbitMQ exchange/queue settings
exchange_name = 'user.update'
queue_name = 'pos.user'      
routing_key = 'pos.user'

channel.exchange_declare(exchange=exchange_name, exchange_type='topic', durable=True)
channel.queue_declare(queue=queue_name, durable=True)
channel.queue_bind(exchange=exchange_name, queue=queue_name, routing_key=routing_key)

def on_message(ch, method, properties, body):
    """
    Callback that receives an XML message for 'user.update'.
    """
    try:
        # Parse the incoming XML
        root = ET.fromstring(body)
        operation = root.find('info/operation').text.strip()
        print("Bericht ontvangen: Operatie =", operation)

        if operation.lower() == "user.update":
            # Extract data from <user> element
            first_name = root.find('user/first_name').text.strip()
            last_name = root.find('user/last_name').text.strip()
            email = root.find('user/email').text.strip()
            title = root.find('user/title').text.strip() if root.find('user/title') is not None else ''

            new_name = f"{first_name} {last_name}"
            
            # Search for the partner by email
            partner_ids = models.execute_kw(
                db, uid, PASSWORD,
                'res.partner',
                'search',
                [[('email', 'ilike', email)]],
                {'context': {'active_test': False}}
            )
            print("Gevonden partner IDs:", partner_ids)

            if partner_ids:
                # Update the partner with new data
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
                print("Write result:", result)
                print(f"Partner bijgewerkt met gegevens: {update_fields}")
            else:
                print(f"Geen partner gevonden met e-mailadres: {email}")
        else:
            print("Operatie niet ondersteund:", operation)
    except Exception as e:
        print(f"Fout tijdens verwerking: {e}")

# Consume messages
channel.basic_consume(queue=queue_name, on_message_callback=on_message, auto_ack=True)
print("Waiting for update user requests...")
channel.start_consuming()
