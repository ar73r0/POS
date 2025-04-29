import pika
import time
import os
import logging
from datetime import datetime
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO)

# RabbitMQ verbinding
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST')
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.environ.get('RABBITMQ_USERNAME')
RABBITMQ_PASS = os.environ.get('RABBITMQ_PASSWORD')
RABBITMQ_VHOST = os.environ.get('RABBITMQ_VHOST')

# Heartbeat config
SENDER = os.environ.get('SENDER_NAME', 'pos')
CONTAINER_NAME = os.environ.get('CONTAINER_NAME', 'pos-heartbeat')
EXCHANGE_NAME = os.environ.get('HEARTBEAT_EXCHANGE', 'monitoring')
ROUTING_KEY = os.environ.get('HEARTBEAT_ROUTING_KEY', 'monitoring.heartbeat')
HEARTBEAT_INTERVAL = int(os.environ.get('HEARTBEAT_INTERVAL', '1'))

def create_heartbeat_message():
    root = ET.Element('attendify')
    info = ET.SubElement(root, 'info')
    ET.SubElement(info, 'sender').text = SENDER
    ET.SubElement(info, 'container_name').text = CONTAINER_NAME
    ET.SubElement(info, 'timestamp').text = datetime.utcnow().isoformat() + 'Z'
    return ET.tostring(root, encoding='utf-8', method='xml')

def main():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            virtual_host=RABBITMQ_VHOST,
            credentials=credentials
        )
    )
    channel = connection.channel()

    # Declareer exchange 
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='topic', durable=True)

    logging.info(f"[Heartbeat] POS heartbeat gestart voor container '{CONTAINER_NAME}'")

    try:
        while True:
            message = create_heartbeat_message()
            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=ROUTING_KEY,
                body=message,
                properties=pika.BasicProperties(delivery_mode=2)
            )
            logging.info(f"[Heartbeat] Verzonden: {message.decode('utf-8')}")
            time.sleep(HEARTBEAT_INTERVAL)
    except KeyboardInterrupt:
        logging.info("POS heartbeat gestopt")
    finally:
        connection.close()

if __name__ == "__main__":
    main()
