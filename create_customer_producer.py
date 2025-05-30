import os, pika, time, json
import bcrypt
import random
import string



from dotenv import  dotenv_values

config = dotenv_values()

characters = string.ascii_letters + string.digits + string.punctuation
random_password = ''.join(random.choices(characters, k=12))
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(random_password.encode('utf-8'), salt)


password = hashed.decode('utf-8')
user_id = f"OD{int(time.time() * 1000)}"

xml = f"""
<attendify>
      <info>
          <sender>Kassa</sender>
          <operation>Create</operation>
      </info>
      <user>
          <uid>{user_id}</uid>
          <first_name>Osman</first_name>
          <last_name>Akturk</last_name>
          <date_of_birth>1990-01-01</date_of_birth>
          <phone_number> +3212345678 </phone_number>
          <title>Mr.</title>
          <email>osman@test.com</email>
          <password>{password}</password>
            
            
          <address>
              <street>Main Street</street>
              <number>42</number>
              <bus_number>B</bus_number>
              <city>Brussels</city>
              <province>Brussels-Capital</province>
              <country>Belgium</country>
              <postal_code>1000</postal_code>
          </address>
            
          <payment_details>
              <facturation_address>
                  <street>Billing Street</street>
                  <number>50</number>
                  <company_bus_number>B</company_bus_number>
                  <city>Antwerp</city>
                  <province>Flanders</province>
                  <country>Belgium</country>
                  <postal_code>2000</postal_code>
              </facturation_address>
              <payment_method>Credit Card</payment_method>
              <card_number>1234 1234 1234 1234</card_number>
          </payment_details>
            
          <email_registered>true</email_registered>
            
          <company>
              <id> COM001 </id>
              <name>TechCorp</name>
              <VAT_number>BE0477472701</VAT_number>
              <address>
                  <street>Corporate Avenue</street>
                  <number>10</number>
                  <city>Ghent</city>
                  <province>East Flanders</province>
                  <country>Belgium</country>
                  <postal_code>9000</postal_code>
              </address>
          </company>
            
          <from_company>false</from_company>
      </user>
</attendify>
"""


xml_min = f"""
<attendify>
    <info>
        <sender>Kassa</sender>
        <operation>create</operation>
    </info>
    <user>
        <uid>{user_id}</uid>
        <first_name>osman</first_name>
        <last_name>akturk</last_name>
        <email>osman@test.com</email>
        <title>Mr.</title>
        <password>{password}</password>
    </user>
</attendify>
"""


credentials = pika.PlainCredentials(config["RABBITMQ_USERNAME"], config["RABBITMQ_PASSWORD"])
params = pika.ConnectionParameters(config["RABBITMQ_HOST"], 30001, config["RABBITMQ_VHOST"], credentials)

connection = pika.BlockingConnection(params)

channel = connection.channel()

exchange_main = 'user-management'
routing_main = 'user.register'
queue_main = 'pos.user'



channel.exchange_declare(exchange=exchange_main, exchange_type="direct", durable=True)
channel.queue_declare(queue=queue_main, durable=True)
channel.queue_bind(queue=queue_main, exchange=exchange_main, routing_key=routing_main)

channel.basic_publish(exchange=exchange_main,
                      routing_key=routing_main,
                      body=xml,
                      properties=pika.BasicProperties(delivery_mode=2)
                      )
    

print("Message Sented")

connection.close()

