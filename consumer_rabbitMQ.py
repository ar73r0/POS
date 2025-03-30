import pika
import xmlrpc.client
import xml.etree.ElementTree as ET

# Odoo login
odoo_url = "http://localhost:8069"
odoo_db = "odoo"
odoo_username = "huygenlucas@gmail.com"
odoo_password = "odoo"

# XML-RPC setup
common = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/common")
uid = common.authenticate(odoo_db, odoo_username, odoo_password, {})
models = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/object")

# Callback voor RabbitMQ berichten
def on_message(ch, method, properties, body):
    try:
        # XML bericht parsen
        root = ET.fromstring(body)
        operation = root.find('info/operation').text.strip()
        print("Bericht ontvangen: Operatie =", operation)
        
        if operation.lower() == "user.update":
            # Gegevens uit het <user> element ophalen
            first_name = root.find('user/first_name').text.strip()
            last_name = root.find('user/last_name').text.strip()
            email = root.find('user/email').text.strip()
            title = root.find('user/title').text.strip()
            
            # Combineer voornaam en achternaam 
            new_name = f"{first_name} {last_name}"
            
            # Zoek de partner op basis van email
            partner_ids = models.execute_kw(odoo_db, uid, odoo_password,
                'res.partner', 'search',
                [[['email', '=', email]]])
            print("Gevonden partner IDs:", partner_ids)
            
            if partner_ids:
                # Alle velden die geupdate worden
                update_fields = {
                    'name': new_name,
                    'email': email,
                    'title': title
                }
                # Update de partner met de nieuwe gegevens
                result = models.execute_kw(odoo_db, uid, odoo_password,
                    'res.partner', 'write',
                    [partner_ids, update_fields])
                print("Write result:", result)
                print(f"Partner bijgewerkt met gegevens: {update_fields}")
            else:
                print("Geen partner gevonden met dit e-mailadres.")
        else:
            print("Operatie niet ondersteund:", operation)
    except Exception as e:
        print("Fout tijdens verwerking:", e)

# RabbitMQ connectie
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='POS.user')

channel.basic_consume(queue='POS.user', on_message_callback=on_message, auto_ack=True)
print("Wachten op berichten...")
channel.start_consuming()
