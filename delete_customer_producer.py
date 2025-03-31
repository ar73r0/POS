import pika
import sys
from dotenv import dotenv_values
 
config = dotenv_values()
 
def send_delete_request(email):
    credentials = pika.PlainCredentials(config["RABBITMQ_USERNAME"], config["RABBITMQ_PASSWORD"])
    params = pika.ConnectionParameters("localhost", 5672, config["RABBITMQ_VHOST"], credentials)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
 
    exchange_name = 'user-management'
    routing_key = 'user.delete'
 
    # XML message
    message = f"""
    <attendify>
        <info>
            <sender>CLI</sender>
            <operation>delete</operation>
        </info>
        <user>
            <email>{email}</email>
        </user>
    </attendify>
    """.strip()
 
    channel.basic_publish(exchange=exchange_name, routing_key=routing_key, body=message)
    print(f"Sent delete request for user: {email}")
    connection.close()
 
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python delete_customer_producer.py <user_email>")
        sys.exit(1)
 
    user_email = sys.argv[1]
    send_delete_request(user_email)