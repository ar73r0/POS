import pika

xml_message = """
<attendify>
    <info>
        <sender>crm</sender>
        <operation>user.update</operation>
    </info>
    <user>
        <first_name>Pieter</first_name>
        <last_name>Huygen</last_name>
        <email>tester@gmail.com</email>
        <title>mr</title>
    </user>
</attendify>
"""

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='POS.user')
channel.basic_publish(exchange='', routing_key='POS.user', body=xml_message)
print("XML bericht verstuurd naar RabbitMQ.")
connection.close()
