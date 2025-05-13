import xmlrpc.client
import pika
from dotenv import dotenv_values

config = dotenv_values()

url = "http://localhost:8069/"
db = config["DATABASE"]
USERNAME = config["EMAIL"]
PASSWORD = config["API_KEY"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, USERNAME, PASSWORD, {})

if not uid:
    print("Authentication failed.")
    exit()

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

session_info = models.execute_kw(db, uid, PASSWORD,
    'session.model', 'search_read',
    [[['active', '=', True]]],  # Filter condition as needed
    {'fields': ['session_id', 'user_id', 'start_time', 'end_time']}
)

operation = "create_or_update"

for session in session_info:
    session_id = session.get('session_id', '')
    user_id = session.get('user_id', '')
    start_time = session.get('start_time', '')
    end_time = session.get('end_time', '')

    xml_message = f"""<attendify>
    <info>
        <sender>odoo</sender>
        <operation>{operation}</operation>
    </info>
    <session>
        <session_id>{session_id}</session_id>
        <user_id>{user_id}</user_id>
        <start_time>{start_time}</start_time>
        <end_time>{end_time}</end_time>
    </session>
</attendify>"""

    print(xml_message)
    print("\n" + "-" * 40 + "\n")
