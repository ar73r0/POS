{
    'name': 'Event Sync with RabbitMQ',
    'version': '1.0',
    'depends': ['event', 'point_of_sale', 'pos_self_order'],
    'assets': {
        # Odoo 17 POS bundle
        'point_of_sale._assets_pos': [
            'event_sync/static/src/js/event_button.js',
            'event_sync/static/src/js/event_select_popup.js',
            'event_sync/static/src/js/order_patch.js',
            'event_sync/static/src/xml/pos_event_button.xml',
        ],
    },
    'web.assets_qweb': [
        'event_sync/static/src/xml/pos_event_button.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
