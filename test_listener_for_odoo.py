# import pika
# from dotenv import dotenv_values

# config = dotenv_values()


# rabbit_host = "localhost"
# rabbit_port = 5672
# rabbit_user = config["RABBITMQ_USERNAME"]
# rabbit_password = config["RABBITMQ_PASSWORD"]
# rabbit_vhost = config["RABBITMQ_VHOST"]

# exchange_name = "user-management"
# queue_name = "pos.listener"  
# routing_keys = ["user.register", "user.update", "user.delete"]

# credentials = pika.PlainCredentials(rabbit_user, rabbit_password)
# params = pika.ConnectionParameters(
#     host=rabbit_host,
#     port=rabbit_port,
#     virtual_host=rabbit_vhost,
#     credentials=credentials
# )

# connection = pika.BlockingConnection(params)
# channel = connection.channel()

# # Declare the direct exchange
# channel.exchange_declare(exchange=exchange_name, exchange_type='direct', durable=True)

# # Declare a queue for the listener
# channel.queue_declare(queue=queue_name, durable=True)

# # Bind the queue to each routing key we care about
# for rk in routing_keys:
#     channel.queue_bind(queue=queue_name, exchange=exchange_name, routing_key=rk)

# print(f"Listening on queue '{queue_name}' for routing keys {routing_keys}...")

# def callback(ch, method, properties, body):
#     # method.routing_key tells you if it's user.register, user.update, or user.delete
#     print(f" Received message with routing_key='{method.routing_key}':")
#     print(body.decode('utf-8'))
#     print("===")

# channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

# try:
#     channel.start_consuming()
# except KeyboardInterrupt:
#     print("Listener stopped.")
#     connection.close()
