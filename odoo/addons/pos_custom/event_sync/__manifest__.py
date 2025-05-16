{
    'name': 'Event Sync with RabbitMQ',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Attendify',
    'category': 'Events',
    'summary': 'Sync events to RabbitMQ on create/update/delete',
    'depends': ['event', 'point_of_sale'],
    'data': [
        'static/src/security/ir.model.access.csv',
    ],
    'assets': {
        # Dev bundle (used when you *really* run the dev server)
        'point_of_sale.assets': [
            "event_sync/static/src/startup/register_event_button.js",
            "event_sync/static/src/models/event_model.js",
            "event_sync/static/src/models/order_ext.js",
            "event_sync/static/src/models/order_auto_event.js",
            "event_sync/static/src/components/event_selector_popup.js",
            "event_sync/static/src/xml/event_selector_popup.xml",
            "event_sync/static/src/components/event_button.js",
            "event_sync/static/src/components/event_button.xml",
        ],

        # Prod bundle –> this is what your browser is actually loading
        'point_of_sale.assets_prod': [
            "event_sync/static/src/startup/register_event_button.js",
            "event_sync/static/src/models/event_model.js",
            "event_sync/static/src/models/order_ext.js",
            "event_sync/static/src/models/order_auto_event.js",
            "event_sync/static/src/components/event_selector_popup.js",
            "event_sync/static/src/xml/event_selector_popup.xml",
            "event_sync/static/src/components/event_button.js",
            "event_sync/static/src/components/event_button.xml",
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
