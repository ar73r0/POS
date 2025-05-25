from odoo import models, fields

class PosConfig(models.Model):
    _inherit = "pos.config"

    event_id = fields.Many2one(
        "event.event",
        string="Event",
        ondelete="set null",
        index=True,
    )