import pika
import psycopg2
import json

# PostgreSQL database configuratie
DB_CONFIG = {
    "dbname": "postgres",
    "user": "odoo",
    "password": "odoo",
    "host": "odoo-db",
    "port": "5432"
}

# RabbitMQ configuratie
RABBITMQ_HOST = "rabbitmq"
QUEUE_NAME = "pos.user"
ROUTING_KEY = "user.delete"

# Functie om een gebruiker te verwijderen uit de database
def delete_user(user_id):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Controleer of gebruiker bestaat
        cursor.execute("SELECT id FROM res_users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            print(f"Gebruiker met ID {user_id} bestaat niet.")
            return False
        
        # Verwijder de gebruiker
        cursor.execute("DELETE FROM res_users WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Gebruiker met ID {user_id} succesvol verwijderd.")
        return True
    except Exception as e:
        print(f"Fout bij verwijderen van gebruiker: {e}")
        return False

# Functie om een RabbitMQ bericht te sturen
def send_rabbitmq_message(user_id):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        
        message = json.dumps({"user_id": user_id, "action": "delete"})
        channel.basic_publish(exchange='', routing_key=ROUTING_KEY, body=message,
                              properties=pika.BasicProperties(delivery_mode=2))
        print(f"Verwijderingsbericht gestuurd naar RabbitMQ: {message}")
        connection.close()
    except Exception as e:
        print(f"Fout bij versturen van RabbitMQ bericht: {e}")

# Hoofdfunctie om gebruiker te verwijderen en bericht te versturen
def remove_user(user_id):
    if delete_user(user_id):
        send_rabbitmq_message(user_id)

# Test met een voorbeeld ID
if __name__ == "__main__":
    test_user_id = 2  # Vervang dit door een echte user ID uit je database
    remove_user(test_user_id)
