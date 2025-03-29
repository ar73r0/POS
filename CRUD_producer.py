import pika

# Verbindingsparameters voor RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

# Declareren van de exchange en de queue
channel.exchange_declare(exchange='user_management', exchange_type='direct')
channel.queue_declare(queue='pos.user')
channel.queue_bind(queue='pos.user', exchange='user_management', routing_key='user.delete')

# Bericht dat verstuurd moet worden
message = 'User has been deleted'

# Bericht versturen naar de RabbitMQ exchange met de juiste routing key
channel.basic_publish(exchange='user_management', routing_key='user.delete', body=message)

print(f"✅ Bericht verstuurd naar RabbitMQ: {message}")

# Sluit de verbinding
connection.close()
