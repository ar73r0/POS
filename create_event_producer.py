import pika
from dotenv import dotenv_values

config = dotenv_values()

credentials = pika.PlainCredentials(config["RABBITMQ_USERNAME"], config["RABBITMQ_PASSWORD"])
params = pika.ConnectionParameters(config["RABBITMQ_HOST"], 30001, config["RABBITMQ_VHOST"], credentials)
connection = pika.BlockingConnection(params)
channel = connection.channel()

exchange_main = 'user-management'
routing_key = 'event.register'

xml_message = """
<attendify>
    <info>
        <sender>crm</sender>
        <operation>create</operation>
    </info>
    <event>
        <uid_event>SF230420251320</uid_event>
        <name>Super important event</name>
        <start_date>2025-04-23T14:30:00Z</start_date>
        <end_date>2025-04-27T14:30:00Z</end_date>
        <address>Bergensesteenweg 155 1651 Lot, België</address>
        <description>This is a cool event where you can walk around</description>
        <max_attendees>100</max_attendees>
    </event>
</attendify>
"""

channel.basic_publish(
    exchange=exchange_main,
    routing_key=routing_key,
    body=xml_message.encode('utf-8')
)

print("Event message sent.")
connection.close()
