import xmlrpc.client
from dotenv import dotenv_values

#config = dotenv_values()

# 🔹 Odoo server details
url = "http://localhost:8069"  # Pas aan indien nodig
db = "odoo"
USERNAME = "jouw-email"  # Moet een admin-user zijn, geen klant
PASSWORD = "jouw_wachtwoord"  # Vul hier je wachtwoord in

# Connect to Odoo
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, USERNAME, PASSWORD, {})

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

def get_customer_info():
    """Fetch all customer details from Odoo."""
    if not uid:
        print("Authentication failed.")
        return

    try:
        # Fetch all customers from 'res.partner' (Odoo's customer model)
        customers = models.execute_kw(
            db, uid, PASSWORD,
            'res.partner', 'search_read',
            [[]],  # Empty list means fetch all records
            {
                'fields': ['id', 'name', 'email', 'phone', 'street', 'city', 'zip', 'country_id']
            }
        )

        if customers:
            for customer in customers:
                print("Customer ID:", customer.get('id'))
                print("Name:", customer.get('name'))
                print("Email:", customer.get('email', 'N/A'))
                print("Phone:", customer.get('phone', 'N/A'))
                print("Address:", f"{customer.get('street', 'N/A')}, {customer.get('city', 'N/A')}, {customer.get('zip', 'N/A')}")
                print("Country ID:", customer.get('country_id', 'N/A'))
                print("-" * 50)
        else:
            print("No customers found.")

    except Exception as e:
        print("Error fetching customer information:", str(e))

if __name__ == "__main__":
    get_customer_info()
