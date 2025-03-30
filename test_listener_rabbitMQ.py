import pika

def callback(ch, method, properties, body):
    print("Ontvangen bericht:")
    print(body.decode('utf-8'))

# Maak verbinding met RabbitMQ (pas host/poort aan indien nodig)
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Zorg dat de queue bestaat
channel.queue_declare(queue='POS.user')

# Luister naar berichten op de queue
channel.basic_consume(queue='POS.user', on_message_callback=callback, auto_ack=True)

print("Luistert naar berichten op queue 'POS.user' ...")
channel.start_consuming()
