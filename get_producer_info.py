import xmlrpc.client
import pika
from dotenv import dotenv_values

config = dotenv_values()

url = "http://localhost:8069/"
db = config["DATABASE"]
USERNAME = config["EMAIL"]
PASSWORD = config["API_KEY"]

common = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/common")
uid = common.authenticate(db, USERNAME, PASSWORD, {})
if not uid:
    print("Authentication failed.")
    exit()

models = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/object")

credentials = pika.PlainCredentials(config["RABBITMQ_USERNAME"], config["RABBITMQ_PASSWORD"])
params = pika.ConnectionParameters(config["RABBITMQ_HOST"], int(config["RABBITMQ_PORT"]), config["RABBITMQ_VHOST"], credentials)
connection = pika.BlockingConnection(params)
channel = connection.channel()

exchange = 'user-management'
routing_key = 'user.info'
channel.exchange_declare(exchange=exchange, exchange_type="direct", durable=True)

customers = models.execute_kw(db, uid, PASSWORD,
    'res.partner', 'search_read',
    [[['customer_rank', '>=', 0]]],
    {'fields': ['name', 'email', 'phone']}
)

sent_emails = set()

for customer in customers:
    name = customer.get("name", "").strip()
    email = customer.get("email")

    if not email or email in sent_emails:
        continue
    sent_emails.add(email)

    raw_phone = customer.get("phone")
    phone = str(raw_phone).strip() if raw_phone else ''

    parts = name.split()
    first_name = parts[0] if parts else ''
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ''

    xml_message = f"""
    <attendify>
        <info>
            <sender>odoo</sender>
            <operation>get</operation>
        </info>
        <user>
            <first_name>{first_name}</first_name>
            <last_name>{last_name}</last_name>
            <email>{email}</email>
            <phone_number>{phone}</phone_number>
        </user>
    </attendify>
    """.strip()

    channel.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=xml_message,
        properties=pika.BasicProperties(delivery_mode=2)
    )

    print(xml_message)
    print("\n" + "-" * 40 + "\n")

connection.close()
