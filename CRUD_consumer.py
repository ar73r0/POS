import pika

# Verbindingsparameters voor RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

# Declareren van de exchange en de queue
channel.exchange_declare(exchange='user_management', exchange_type='direct')
channel.queue_declare(queue='pos.user')
channel.queue_bind(queue='pos.user', exchange='user_management', routing_key='user.delete')

# Callback functie voor het ontvangen van berichten
def callback(ch, method, properties, body):
    print(f"✅ Bericht ontvangen: {body.decode()}")

# Consumer starten op de queue 'pos.user'
channel.basic_consume(queue='pos.user', on_message_callback=callback, auto_ack=True)

print('🔄 Wachten op berichten...')
channel.start_consuming()
