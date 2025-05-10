{
    'name': 'POS Customer Sync with RabbitMQ',
    'version': '1.0',
    'depends': ['point_of_sale','event'],
    'license': 'LGPL-3',
    'author': 'Attendify',
    'category': 'Point of Sale',
    'summary': 'Send POS customer updates/deletes/creates to RabbitMQ',
    'description': 'Sends res.partner (POS customer) updates as XML to RabbitMQ.',
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}


