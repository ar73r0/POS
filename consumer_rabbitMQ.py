import pika
import json
import xmlrpc.client

# Odoo login
odoo_url = "http://localhost:8069"
odoo_db = "odoo"
odoo_username = "huygenlucas@gmail.com"
odoo_password = "odoo"

# XML-RPC setup
common = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/common")
uid = common.authenticate(odoo_db, odoo_username, odoo_password, {})
models = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/object")

# Callback voor RabbitMQ messages
def on_message(ch, method, properties, body):
    try:
        data = json.loads(body)
        print("Bericht ontvangen:", data)  # Debug print

        if data.get("action") == "update_partner":
            email = data.get("email")
            new_name = data.get("name")

            # Zoek gebruiker
            partner_ids = models.execute_kw(odoo_db, uid, odoo_password,
                'res.partner', 'search',
                [[['email', '=', email]]])

            print("Gevonden partner IDs:", partner_ids)

            if partner_ids:
                # Update partner
                result = models.execute_kw(odoo_db, uid, odoo_password,
                    'res.partner', 'write',
                    [partner_ids, {'name': new_name}])
                print("Write result:", result)
                print(f"Partner bijgewerkt: {email} -> {new_name}")
            else:
                print("Geen partner gevonden met dit e-mailadres.")

    except Exception as e:
        print("Fout tijdens verwerking:", e)

# RabbitMQ connectie
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='odoo_queue')

channel.basic_consume(queue='odoo_queue', on_message_callback=on_message, auto_ack=True)
print("Wachten op berichten...")
channel.start_consuming()
