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

    def _loader_params_pos_session(self):
        """Include event_id in the fields the POS preloads for pos.session."""
        params = super()._loader_params_pos_session()
        # ensure our field is in the list
        fields = params.setdefault('search_params', {}).setdefault('fields', [])
        if 'event_id' not in fields:
            fields.append('event_id')
        return params
