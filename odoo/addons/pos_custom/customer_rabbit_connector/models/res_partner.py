from odoo import models, api
import pika
import xml.etree.ElementTree as ET
import logging

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
        
        # split
        name_parts = self.name.split(' ')
        first_name = name_parts[0] if name_parts else ''
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ''
        
        # XML klaarmaken
        xml_message = f"""
<attendify>
    <info>
        <sender>POS</sender>
        <operation>{POS.update}</operation>
    </info>
    <user>
        <first_name>{first_name}</first_name>
        <last_name>{last_name}</last_name>
        <email>{self.email}</email>
        <title>{self.title.name if self.title else ''}</title>
    </user>
</attendify>
"""
        try:
            _logger.debug("Attempting to send RabbitMQ message for partner ID %s: %s", self.id, xml_message)
            connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
            channel = connection.channel()
            channel.queue_declare(queue='POS.user')
            channel.basic_publish(exchange='', routing_key='POS.user', body=xml_message)
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
