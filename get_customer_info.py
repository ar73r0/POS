import xmlrpc.client
from dotenv import dotenv_values

# Load environment variables
config = dotenv_values()

# Odoo connection details (make sure to include the trailing slash like your working script!)
url = "http://localhost:8069/"
db = config["DATABASE"]
USERNAME = config["EMAIL"]
PASSWORD = config["API_KEY"]

# Authenticate with Odoo
common = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/common")
uid = common.authenticate(db, USERNAME, PASSWORD, {})

if not uid:
    print("Authentication failed.")
    exit()

# Connect to object endpoint
models = xmlrpc.client.ServerProxy(f"{url}xmlrpc/2/object")

def get_user_account_details():
    """Fetch and display the account details of the currently authenticated user."""
    try:
        # First get the user’s partner_id
        user_info = models.execute_kw(
            db, uid, PASSWORD,
            'res.users', 'read',
            [uid],
            {'fields': ['partner_id']}
        )

        partner_id = user_info[0]['partner_id'][0]  # Get the ID from the (id, name) tuple

        # Now fetch the partner's info
        partner_info = models.execute_kw(
            db, uid, PASSWORD,
            'res.partner', 'read',
            [partner_id],
            {'fields': ['name', 'email', 'phone', 'street', 'city', 'zip', 'country_id']}
        )

        partner = partner_info[0]
        print("Account Details:")
        print("Name:", partner.get('name', 'N/A'))
        print("Email:", partner.get('email', 'N/A'))
        print("Phone:", partner.get('phone', 'N/A'))
        print("Address:", f"{partner.get('street', 'N/A')}, {partner.get('city', 'N/A')}, {partner.get('zip', 'N/A')}")
        print("Country ID:", partner.get('country_id', ['N/A'])[1] if partner.get('country_id') else 'N/A')

    except Exception as e:
        print("Error fetching account details:", str(e))

if __name__ == "__main__":
    get_user_account_details()
