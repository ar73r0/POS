import pika
from dotenv import dotenv_values

# Load environment variables from .env
config = dotenv_values()

# Retrieve RabbitMQ settings from environment
RABBITMQ_HOST = config.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(config.get("RABBITMQ_PORT", "5672"))
RABBITMQ_USERNAME = config.get("RABBITMQ_USERNAME", "guest")
RABBITMQ_PASSWORD = config.get("RABBITMQ_PASSWORD", "guest")
RABBITMQ_VHOST = config.get("RABBITMQ_VHOST", "/")

# Define the XML message
xml_message = """
<attendify>
    <info>
        <sender>crm</sender>
        <operation>user.update</operation>
    </info>
    <user>
        <first_name>Pieter</first_name>
        <last_name>Huygen</last_name>
        <email>huygenlucas@gmail.com</email>
        <title>mr</title>
    </user>
</attendify>
"""

# Establish RabbitMQ connection
credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)
params = pika.ConnectionParameters(
    host=RABBITMQ_HOST,
    port=RABBITMQ_PORT,
    virtual_host=RABBITMQ_VHOST,
    credentials=credentials
)
connection = pika.BlockingConnection(params)
channel = connection.channel()

# Declare the queue and publish the message
queue_name = "pos.user"
channel.queue_declare(queue=queue_name, durable=True)
channel.basic_publish(exchange="", routing_key=queue_name, body=xml_message)

print("XML bericht verstuurd naar RabbitMQ.")
connection.close()
