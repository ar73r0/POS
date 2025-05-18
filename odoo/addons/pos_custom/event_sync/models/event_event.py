from odoo import models, fields

class EventEvent(models.Model):
    _inherit = "event.event"

    external_uid = fields.Char(
        string="External UID",
        help="Identifier imported from the external system",
        index=True,
    )
