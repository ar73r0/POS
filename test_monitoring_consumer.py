# import pika
# from dotenv import dotenv_values

# config = dotenv_values()


# credentials = pika.PlainCredentials(config["RABBITMQ_USERNAME"], config["RABBITMQ_PASSWORD"])
# params = pika.ConnectionParameters("localhost", 5672, config["RABBITMQ_VHOST"], credentials)

# connection = pika.BlockingConnection(params)

# channel = connection.channel()


# exchange_monitoring = 'monitoring'
# routing_key_monitoring_success = 'monitoring.success'
# routing_key_monitoring_failure = 'monitoring.failure'
# queue_monitoring='monitoring'


# channel.exchange_declare(exchange=exchange_monitoring, exchange_type='direct', durable=True)
# channel.queue_declare(queue=queue_monitoring, durable=True)
# channel.queue_bind(exchange=exchange_monitoring, queue=queue_monitoring, routing_key=routing_key_monitoring_success)
# channel.queue_bind(exchange=exchange_monitoring, queue=queue_monitoring, routing_key=routing_key_monitoring_failure)


# def monitoring_callback(ch, method, properties, body):
#     print(f"[MONITORING] Routing Key: {method.routing_key}")
#     print(body.decode())


# channel.basic_consume(queue="monitoring", on_message_callback=monitoring_callback, auto_ack=True)
# print("Monitoring... ")
# channel.start_consuming()

