import os, pika, time, json
from dotenv import  dotenv_values

config = dotenv_values()



xml = """
<attendify>
      <info>
          <sender>CRM</sender>
          <operation>Create</operation>
      </info>
      <user>
          <id>12345</id>
          <first_name>Osman</first_name>
          <last_name>Akturk</last_name>
          <date_of_birth>1990-01-01</date_of_birth>
          <phone_number> +3212345678 </phone_number>
          <title> title </title>
          <email>osman@test.com</email>
          <password>Pasword123456!</password>
            
            
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





credentials = pika.PlainCredentials(config["RABBITMQ_USERNAME"], config["RABBITMQ_PASSWORD"])
params = pika.ConnectionParameters("localhost", 5672, config["RABBITMQ_VHOST"], credentials)

connection = pika.BlockingConnection(params)

channel = connection.channel()

exchange_name = 'user.register'
routing_key = 'pos.user'
queue_name = 'pos.user'


channel.exchange_declare(exchange=exchange_name, exchange_type="topic", durable=True)

channel.basic_publish(exchange=exchange_name,
                      routing_key=routing_key,
                      body=xml,
                      )
    

print("Message Sented")

connection.close()

