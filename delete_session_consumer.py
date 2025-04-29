import pika
import json
import xmlrpc.client
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

exchange_name = 'session-management'
queue_name = 'pos.session'
routing_key = 'session.delete'

channel.exchange_declare(exchange=exchange_name, exchange_type='topic', durable=True)
channel.queue_declare(queue=queue_name, durable=True)
channel.queue_bind(exchange=exchange_name, queue=queue_name, routing_key=routing_key)

def delete_session(session_id):
    session_ids = models.execute_kw(
        db, uid, PASSWORD,
        'session.model',  # replace with your actual model
        'search',
        [[['session_id', '=', session_id]]]
    )

    if session_ids:
        models.execute_kw(db, uid, PASSWORD, 'session.model', 'unlink', [session_ids])
        print(f"Session {session_id} deleted successfully.")
    else:
        print(f"Session {session_id} not found.")

def callback(ch, method, properties, body):
    try:
        data = json.loads(body.decode("utf-8"))
        session_id = data.get("session_id")

        if session_id:
            delete_session(session_id)
        else:
            print("Invalid message format.")
    except Exception as e:
        print(f"Error processing message: {e}")

channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
print("Waiting for delete session requests...")
channel.start_consuming()
