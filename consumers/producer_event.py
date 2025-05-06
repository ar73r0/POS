import pika
from dotenv import dotenv_values

# Load config
config = dotenv_values()

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

# Declare exchange and routing key
exchange_main = 'user-management'
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

# Publish the message
channel.basic_publish(
    exchange=exchange_main,
    routing_key=routing_key,
    body=xml_message.encode('utf-8')
)

print("Event message sent.")

# Close the connection
connection.close()