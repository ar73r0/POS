from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class EventSync(models.Model):
    _inherit = 'event.event'  # inheret excisting module from odoo

    def _send_event_to_rabbitmq(self, operation):
        """
        Sends event data to RabbitMQ.
        """
        # code hier voor XML formatting etc

        _logger.info("Sending event %s to RabbitMQ [%s]", self.id, operation)
      

    @api.model_create_multi
    def create(self, vals_list):
        records = super(EventSync, self).create(vals_list)
        for record in records:
            record._send_event_to_rabbitmq('create')
        return records

    def write(self, vals):
        res = super(EventSync, self).write(vals)
        for record in self:
            record._send_event_to_rabbitmq('update')
        return res

    def unlink(self):
        for record in self:
            record._send_event_to_rabbitmq('delete')
        return super(EventSync, self).unlink()