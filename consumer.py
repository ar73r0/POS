import sys
import os
import pika
import json
import xmlrpc.client
import xmltodict
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
channel.queue_bind(queue=queue_main, exchange=exchange_main, routing_key='user.register')
channel.queue_bind(queue=queue_main, exchange=exchange_main, routing_key='user.update')
channel.queue_bind(queue=queue_main, exchange=exchange_main, routing_key='user.delete')

exchange_monitoring = 'monitoring'
routing_key_monitoring_success = 'monitoring.success'
routing_key_monitoring_failure = 'monitoring.failure'
queue_monitoring = 'monitoring'

channel.exchange_declare(exchange=exchange_monitoring, exchange_type='direct', durable=True)
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

def process_message(ch, method, properties, body):
    try:
        data = json.loads(body.decode("utf-8"))
        operation = method.routing_key
        
        if operation == "user.delete":
            email = data.get("email")
            if email:
                delete_user(email)
            else:
                print("Invalid delete request format.")
        else:
            print(f"Unsupported operation: {operation}")
    except Exception as e:
        print(f"Error processing message: {e}")

channel.basic_consume(queue=queue_main, on_message_callback=process_message, auto_ack=True)
print("Waiting for user requests...")
channel.start_consuming()

if __name__ == "__main__":
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
