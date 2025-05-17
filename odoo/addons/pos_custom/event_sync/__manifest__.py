# event_sync/__manifest__.py
{
    'name': 'Event Sync with RabbitMQ',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Attendify',
    'category': 'Events',
    'summary': 'Sync events to RabbitMQ on create/update/delete and from POS',
    'depends': ['event', 'point_of_sale'],
    'assets': {
        # 17.0’s private POS bundle
        'point_of_sale._assets_pos': [
            'event_sync/static/src/js/event_button.js',
            'event_sync/static/src/js/order_patch.js',
            'event_sync/static/src/xml/event_button.xml',
            'event_sync/static/src/js/event_select_popup.js',
            'event_sync/static/src/xml/event_select_popup.xml',
        ],
        # load your QWeb templates so OWL can find them
        'web.assets_qweb': [
            'event_sync/static/src/xml/event_button.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
