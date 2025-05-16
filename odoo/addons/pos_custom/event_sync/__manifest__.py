{
    'name': 'Event Sync with RabbitMQ',
    'version': '1.0',
    'license': 'LGPL-3',
    'depends': ['event', 'point_of_sale'],
    'author': 'Attendify',
    'category': 'Events',
    'summary': 'Sync events to RabbitMQ on create/update/delete',
    'description': 'This module sends event.event model updates to RabbitMQ in XML format.',
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
        'assets': {
        'point_of_sale.assets': [
            "event_sync/static/src/models/event_model.js",
            "event_sync/static/src/models/order_ext.js",
            "event_sync/static/src/models/order_auto_event.js",
            "event_sync/static/src/components/event_selector_popup.js",
            "event_sync/static/src/xml/event_selector_popup.xml",
            "event_sync/static/src/startup/event_popup_start.js",
        ],
    },
}
