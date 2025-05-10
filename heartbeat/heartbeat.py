# heartbeat/heartbeat.py
import os
import time
import logging
import pika
import xml.etree.ElementTree as ET
from datetime import datetime
import docker

logging.basicConfig(level=logging.INFO)

# RabbitMQ verbinding
RABBITMQ_HOST = os.environ['RABBITMQ_HOST']
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.environ['RABBITMQ_USERNAME']
RABBITMQ_PASS = os.environ['RABBITMQ_PASSWORD']
RABBITMQ_VHOST = os.environ['RABBITMQ_VHOST']

# Heartbeat config
SENDER         = os.environ.get('SENDER_NAME', 'pos')
CONTAINER_NAME = os.environ['CONTAINER_NAME']        
EXCHANGE_NAME  = os.environ.get('HEARTBEAT_EXCHANGE', 'monitoring')
ROUTING_KEY    = os.environ.get('HEARTBEAT_ROUTING_KEY', 'monitoring.heartbeat')
INTERVAL       = int(os.environ.get('HEARTBEAT_INTERVAL', '1'))
TARGET         = os.environ['TARGET_CONTAINER']    

# Docker-client via socket
docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')

def is_target_healthy():
    try:
        ctr = docker_client.containers.get(TARGET)
        status = ctr.attrs.get('State', {}) \
                         .get('Health', {}) \
                         .get('Status')
        return status == 'healthy'
    except Exception:
        return False

def create_heartbeat_msg():
    root = ET.Element('heartbeat')
    ET.SubElement(root, 'sender').text         = SENDER
    ET.SubElement(root, 'container_name').text = CONTAINER_NAME
    ET.SubElement(root, 'timestamp').text      = datetime.utcnow().isoformat() + 'Z'
    return ET.tostring(root, encoding='utf-8', method='xml')

def main():
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    conn = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            virtual_host=RABBITMQ_VHOST,
            credentials=creds
        )
    )
    ch = conn.channel()
    ch.exchange_declare(exchange=EXCHANGE_NAME,
                        exchange_type='topic',
                        durable=True)

    logging.info(f"[Heartbeat] gestart voor container '{CONTAINER_NAME}', target='{TARGET}'")
    try:
        while True:
            if is_target_healthy():
                msg = create_heartbeat_msg()
                ch.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key=ROUTING_KEY,
                    body=msg,
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                logging.info(f"[Heartbeat] Verzonden: {msg.decode()}")
            else:
                logging.warning(f"[Heartbeat] Sla over: target '{TARGET}' niet healthy")
            time.sleep(INTERVAL)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
