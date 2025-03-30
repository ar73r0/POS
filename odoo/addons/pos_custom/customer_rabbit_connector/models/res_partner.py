from odoo import models, api
import pika
import xml.etree.ElementTree as ET
import logging
from dotenv import dotenv_values  # moet installed zijn

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    def _send_to_rabbitmq(self, operation):
        """
        Sends customer data as XML to RabbitMQ.
        """
        # Only send messages if there is an email
        if not self.email:
            _logger.debug("No email found for partner ID %s. Message not sent.", self.id)
            return
        
        # Split
        name_parts = self.name.split(' ')
        first_name = name_parts[0] if name_parts else ''
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ''
        
        # Build XML 
        xml_message = f"""
<attendify>
    <info>
        <sender>pos</sender>
        <operation>pos.{operation}</operation>
    </info>
    <user>
        <first_name>{first_name}</first_name>
        <last_name>{last_name}</last_name>
        <email>{self.email}</email>
        <title>{self.title.name if self.title else ''}</title>
    </user>
</attendify>
"""

        # Load RabbitMQ credentials from .env
        config = dotenv_values()  # loads variables from .env
        rabbit_host = config.get("RABBITMQ_HOST", "rabbitmq")
        rabbit_port = int(config.get("RABBITMQ_PORT", "5672"))
        rabbit_user = config.get("RABBITMQ_USERNAME", "guest")
        rabbit_password = config.get("RABBITMQ_PASSWORD", "guest")
        rabbit_vhost = config.get("RABBITMQ_VHOST", "/")

        try:
            _logger.debug("Attempting to send RabbitMQ message for partner ID %s: %s", self.id, xml_message)
            # Build the connection with environment-based credentials
            credentials = pika.PlainCredentials(rabbit_user, rabbit_password)
            params = pika.ConnectionParameters(
                host=rabbit_host,
                port=rabbit_port,
                virtual_host=rabbit_vhost,
                credentials=credentials
            )
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            # Declare queue & publish. Using default exchange here.
            channel.queue_declare(queue='pos.user', durable=True)
            channel.basic_publish(exchange='', routing_key='pos.user', body=xml_message)
            connection.close()

            _logger.info("Message sent to RabbitMQ for partner ID %s: %s", self.id, xml_message)
        except Exception as e:
            _logger.error("Error sending message to RabbitMQ for partner ID %s: %s", self.id, e)

    @api.model_create_multi
    def create(self, vals_list):
        _logger.debug("Creating partner(s) with values: %s", vals_list)
        records = super(ResPartner, self).create(vals_list)
        return records

    def write(self, vals):
        _logger.debug("Updating partner(s) with ID(s): %s and values: %s", self.ids, vals)
        res = super(ResPartner, self).write(vals)
        for record in self:
            _logger.debug("Triggering RabbitMQ update for partner ID %s", record.id)
            record._send_to_rabbitmq('update')  
        return res
