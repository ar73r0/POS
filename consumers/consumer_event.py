import pika
import xmlrpc.client
import xmltodict
import xml.etree.ElementTree as ET
from dotenv import dotenv_values

# Load config
config = dotenv_values()

# Odoo connection
url = f"http://{config['ODOO_HOST']}:8069/"
db = config["DATABASE"]
USERNAME = config["EMAIL"]
PASSWORD = config["API_KEY"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# RabbitMQ connection
credentials = pika.PlainCredentials(config["RABBITMQ_USERNAME"], config["RABBITMQ_PASSWORD"])
params = pika.ConnectionParameters(
    host=config["RABBITMQ_HOST"],
    port=int(config.get("RABBITMQ_PORT", 30001)),
    virtual_host=config["RABBITMQ_VHOST"],
    credentials=credentials
)

connection = pika.BlockingConnection(params)
channel = connection.channel()

exchange_main = 'user-management'
queue_main = 'pos.event'
routing_key = 'event.register'

# XML message to send
xml_message = """
<attendify>
    <info>
        <sender>crm</sender>
        <operation>create</operation>
    </info>
    <event>
        <uid_event>SF230420251320</uid_event>
        <name>Super important event</name>
        <date>2025-04-23T14:30:00Z</date>
        <location>Bergensesteenweg 155 1651 Lot, België</location>
        <description>This is a cool event where you can walk around</description>
    </event>
</attendify>
"""

# Send XML message
channel.basic_publish(
    exchange=exchange_main,
    routing_key=routing_key,
    body=xml_message.encode('utf-8')
)

print("Event message sent.")


# Consumer logic
def process_message(ch, method, properties, body):
    try:
        print("Received message, processing...")
        parsed = xmltodict.parse(body.decode('utf-8'))
        operation = parsed["attendify"]["info"]["operation"].strip().lower()

        if operation == "create":
            event_data = parsed["attendify"]["event"]
            name = event_data.get("name", "Unnamed Event")
            date = event_data.get("date")
            location = event_data.get("location", "")
            description = event_data.get("description", "")

            event_vals = {
                "name": name,
                "date_begin": date,
                "location": location,
                "description": description,
            }

            new_event_id = models.execute_kw(
                db, uid, PASSWORD,
                'event.event', 'create',
                [event_vals]
            )

            print(f"Event created in Odoo with ID {new_event_id}")
        else:
            print(f"Ignored operation: {operation}")
    except Exception as e:
        print(f"Error processing event message: {e}")


channel.basic_consume(queue=queue_main, on_message_callback=process_message, auto_ack=True)
print("Waiting for event messages...")
channel.start_consuming()
