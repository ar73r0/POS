from odoo import models, fields

class PosSession(models.Model):
    _inherit = "pos.session"

    # link to the Event
    event_id = fields.Many2one(
        "event.event",
        string="Event",
        ondelete="set null",
        index=True,
    )
