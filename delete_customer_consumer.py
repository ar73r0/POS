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

exchange_name = 'user.delete'
queue_name = 'pos.user'
routing_key = 'pos.user'

channel.exchange_declare(exchange=exchange_name, exchange_type='topic', durable=True)
channel.queue_declare(queue=queue_name, durable=True)
channel.queue_bind(exchange=exchange_name, queue=queue_name, routing_key=routing_key)

def delete_user(email):
    user_ids = models.execute_kw(db, uid, PASSWORD, 'res.users', 'search', [[['login', '=', email]]])
    
    if user_ids:
        models.execute_kw(db, uid, PASSWORD, 'res.users', 'unlink', [user_ids])
        print(f"User {email} deleted successfully.")
    else:
        print(f"User {email} not found.")

def callback(ch, method, properties, body):
    try:
        data = json.loads(body.decode("utf-8"))
        email = data.get("email")
        
        if email:
            delete_user(email)
        else:
            print("Invalid message format.")
    except Exception as e:
        print(f"Error processing message: {e}")

channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
print("Waiting for delete user requests...")
channel.start_consuming()
