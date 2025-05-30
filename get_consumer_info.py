import xmlrpc.client
from dotenv import dotenv_values
import pika


config = dotenv_values()

url = "http://localhost:8069/"
db = "odoo"
USERNAME = config["EMAIL"]
PASSWORD = config["API_KEY"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
 
credentials = pika.PlainCredentials(config["RABBITMQ_USERNAME"], config["RABBITMQ_PASSWORD"])
params = pika.ConnectionParameters(config["RABBITMQ_HOST"], 30001, config["RABBITMQ_VHOST"], credentials)
connection = pika.BlockingConnection(params)
channel = connection.channel()

common = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/common")
uid = common.authenticate(db, USERNAME, PASSWORD, {})

if not uid:
    print("Authentication failed.")
    exit()

print(f"Authenticated as user ID: {uid}")   

models = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/object")

customer_info = models.execute_kw(db, uid, PASSWORD,
        'res.partner', 'search_read',
        #[[['ref', '=', uid]]],
        [[['customer_rank', '>=', 0]]],
        {'fields': ['name', 'email', 'phone', 'street', 'city', 'zip', 'country_id']}
        )

operation = "create_or_update"

for customer in customer_info:
    full_name = customer.get('name', '')
    first_name, *last_parts = full_name.split("_")
    last_name = " ".join(last_parts) if last_parts else ''
    email = customer.get('email', '')
    phone = customer.get('phone', '')
    password = "default_password"
    title = ''

    xml_message = f"""<attendify>
    <info>
        <sender>odoo</sender>
        <operation>{operation}</operation>
    </info>
    <user>
        <first_name>{first_name}</first_name>
        <last_name>{last_name}</last_name>
        <email>{email}</email>
        <password>{password}</password>
        <title>{title}</title>
    </user>
</attendify>"""

    print(xml_message)
    print("\n" + "-" * 40 + "\n")