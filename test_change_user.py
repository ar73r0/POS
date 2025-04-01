import pika
from dotenv import dotenv_values
 
# Load environment variables from .env
config = dotenv_values()
 
# Build RabbitMQ connection parameters
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
 
# Establish connection & channel
connection = pika.BlockingConnection(params)
channel = connection.channel()
 
# Define exchange, routing key, and queue
exchange_main = 'user-management'
routing_main = 'user.update'
queue_main = 'pos.user'
 """
# Declare exchange, queue, and bind them
channel.exchange_declare(exchange=exchange_main, exchange_type='direct', durable=True)
channel.queue_declare(queue=queue_main, durable=True)
channel.queue_bind(exchange=exchange_main, queue=queue_main, routing_key=routing_main)
 """
# Define the XML message
xml_message = """
<attendify>
    <info>
        <sender>crm</sender>
        <operation>user.update</operation>
    </info>
    <user>
        <first_name>Lucas</first_name>
        <last_name>Huygen</last_name>
        <email>osman@test.com</email>
        <title>mr</title>
    </user>
</attendify>
"""
 """
# Publish the message
channel.basic_publish(
    exchange=exchange_main,
    routing_key=routing_main,
    body=xml_message
)"""
print("Message sent to RabbitMQ.")
 
# Close connection
connection.close()
 
