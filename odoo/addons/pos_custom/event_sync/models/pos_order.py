import os
import logging
import xml.etree.ElementTree as ET
from odoo import models

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()

        for order in self:
            root = ET.Element('attendify', {
                'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                'xsi:noNamespaceSchemaLocation': 'tab_item.xsd'
            })

            info = ET.SubElement(root, 'info')
            ET.SubElement(info, 'sender').text = 'pos'
            ET.SubElement(info, 'operation').text = 'create'

            tab = ET.SubElement(root, 'tab')
            ET.SubElement(tab, 'uid').text = f'u{order.partner_id.id or "0"}'
            ET.SubElement(tab, 'event_id').text = 'e5' # Test event ID
            ET.SubElement(tab, 'timestamp').text = order.date_order.isoformat()

            items = ET.SubElement(tab, 'items')
            for line in order.lines:
                item = ET.SubElement(items, 'tab_item')
                ET.SubElement(item, 'item_name').text = line.product_id.name
                ET.SubElement(item, 'quantity').text = str(line.qty)
                ET.SubElement(item, 'price').text = str(line.price_unit)

            xml_data = ET.tostring(root, encoding='utf-8').decode()

            _logger.info("💡 Generated POS XML:\n%s", xml_data)

           

        return res
