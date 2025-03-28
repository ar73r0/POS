import pika
import xmlrpc.client

# 🔹 Odoo server details
url = "http://localhost:8069"  # Pas aan indien nodig
db = "odoo"
username = "soufian.jaatar@student.ehb.be"  # Moet een admin-user zijn, geen klant
password = "jouw passwoord"

# 🔹 Verbinden met Odoo
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

if uid:
    print(f"✅ Succesvol verbonden met Odoo als {username}")
else:
    print("❌ Authenticatie mislukt")
    exit()

# 🔹 Verbinden met de object interface
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# 🔹 Klantgegevens
customer_data = {
    'name': 'John Doe',  # Naam
    'company_type': 'person',  # 'person' voor individu, 'company' voor bedrijf
    'company_name': 'TechCorp',  # Bedrijfsnaam (indien van toepassing)
    
    # 📞 Contactgegevens
    'street': 'Main Street 42',  # Straat + nummer
    'street2': 'B',  # Extra adresregel
    'zip': '1000',  # Postcode
    'city': 'Brussels',  # Stad
    'state_id': False,  # Moet een Odoo ID zijn
    'country_id': 21,  # België (check de ID in jouw Odoo instance)
    
    # 📜 Belastinginformatie
    'vat': 'BE0477472701',  # BTW-nummer
    
    # 💼 Job & contact
    'function': 'Sales Director',  # Job positie
    'phone': '+32 12 34 56 78',
    'mobile': '+32 12 34 56 78',
    'email': 'john.doe@test.com',
    'website': 'https://www.odoo.com',
    
    # 🏷️ Titel (bv. Mister, Mevr., Dr.)
    'title': False,  # Odoo verwacht een ID van een title-record, als die bestaat
    
    # 🏆 Tags (Categorieën)
    'category_id': [],  # Bijvoorbeeld: ["B2B", "VIP", "Consulting"]
    
    # 👤 Markeren als klant
    'customer_rank': 1  # Dit maakt de partner een klant in Odoo
}

# 🔹 Klant aanmaken in Odoo
customer_id = models.execute_kw(db, uid, password, 'res.partner', 'create', [customer_data])

if customer_id:
    print(f"✅ Klant aangemaakt met ID: {customer_id}")
else:
    print("❌ Klant aanmaken mislukt")

# 🔹 Klant verwijderen (optioneel)
'''
if customer_id:
    delete_success = models.execute_kw(db, uid, password, 'res.partner', 'unlink', [[customer_id]])
    
    if delete_success:
        print(f"✅ Klant met ID {customer_id} succesvol verwijderd.")
    else:
        print("❌ Verwijderen mislukt.")
'''
