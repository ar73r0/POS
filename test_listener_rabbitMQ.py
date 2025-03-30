import pika
from dotenv import dotenv_values

# Load environment variables from .env
config = dotenv_values()

# Extract RabbitMQ credentials/host from environment
RABBITMQ_HOST = config.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(config.get("RABBITMQ_PORT", "5672"))
RABBITMQ_USERNAME = config.get("RABBITMQ_USERNAME", "guest")
RABBITMQ_PASSWORD = config.get("RABBITMQ_PASSWORD", "guest")
RABBITMQ_VHOST = config.get("RABBITMQ_VHOST", "/")

# Create connection parameters
credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)
params = pika.ConnectionParameters(
    host=RABBITMQ_HOST,
    port=RABBITMQ_PORT,
    virtual_host=RABBITMQ_VHOST,
    credentials=credentials
)

# Establish the connection and declare the queue
connection = pika.BlockingConnection(params)
channel = connection.channel()
channel.queue_declare(queue='POS.user', durable=True)

# Define the callback
def callback(ch, method, properties, body):
    print("Ontvangen bericht:")
    print(body.decode('utf-8'))

# Consume messages
channel.basic_consume(queue='POS.user', on_message_callback=callback, auto_ack=True)
print("Luistert naar berichten op queue 'POS.user' ...")
channel.start_consuming()
