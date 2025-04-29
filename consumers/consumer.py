import sys
import os
import pika
import json
import xmlrpc.client
import xmltodict
import xml.etree.ElementTree as ET
from dotenv import dotenv_values
 
config = dotenv_values()
 
url = f"http://{config['ODOO_HOST']}:8069/"
db = config["DATABASE"]
USERNAME = config["EMAIL"]
PASSWORD = config["API_KEY"]
 
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
 
credentials = pika.PlainCredentials(config["RABBITMQ_USERNAME"], config["RABBITMQ_PASSWORD"])
params = pika.ConnectionParameters(
    host=config["RABBITMQ_HOST"],
    port=int(config["RABBITMQ_PORT"]),
    virtual_host=config["RABBITMQ_VHOST"],
    credentials=credentials
)
connection = pika.BlockingConnection(params)
channel = connection.channel()
 
exchange_main = 'user-management'
queue_main = 'pos.user'


exchange_monitoring = 'monitoring'
routing_key_monitoring_success = 'monitoring.success'
routing_key_monitoring_failure = 'monitoring.failure'
queue_monitoring = 'monitoring'
 

def delete_user(ref):
    partner_ids = models.execute_kw(
        db, uid, PASSWORD,
        'res.partner', 'search',
        [[['ref', '=', ref]]],
        {'context': {'active_test': False}}
    )
    if partner_ids:
        models.execute_kw(db, uid, PASSWORD, 'res.partner', 'unlink', [partner_ids])
        print(f"Customer {ref} deleted successfully.")
    else:
        print(f"Customer {ref} not found.")
 


 
def process_message(ch, method, properties, body):
    try:

        parsed = xmltodict.parse(body.decode('utf-8'))
        operation = parsed["attendify"]["info"]["operation"].strip().lower()
        sender = parsed["attendify"]["info"]["sender"]
        routing_key = method.routing_key
 
        if operation == "delete":
            try:
                print("Body (raw):", body)
                print("Body (decoded):", body.decode('utf-8', errors='replace'))
 
                data = xmltodict.parse(body.decode("utf-8"))
                ref = data['attendify']['user'].get("id")
                if ref:
                    delete_user(ref)
                else:
                    print("Invalid delete request format.")
            except Exception as e:
                print(f"Error parsing XML in delete message: {e}")
 
        elif operation == "update":
            root = ET.fromstring(body)
            operation = root.find('info/operation').text.strip().lower()
 
            if operation != 'update':
                print("Operation mismatch in user.update message")
                return
 
            ref = root.find('user/id').text.strip()
            email = root.find('user/email').text.strip()
            first_name = root.find('user/first_name').text.strip()
            last_name = root.find('user/last_name').text.strip()
            title = root.find('user/title').text.strip() if root.find('user/title') is not None else ""
 
            partner_ids = models.execute_kw(
                db, uid, PASSWORD,
                'res.partner', 'search',
                [[('ref', '=', ref)]],
                {'context': {'active_test': False}}
            )
 
            if partner_ids:
                update_fields = {
                    'name': f"{first_name}_{last_name}",
                    'email': email,
                    'title': title
                }
                models.execute_kw(db, uid, PASSWORD, 'res.partner', 'write', [partner_ids, update_fields])
                print(f"Updated user {ref}.")
            else:
                print(f"No user found with email {ref}.")
 
        elif operation == "create":

            def get_country_id(country):
                    
                country_name_to_code = {
                        "Afghanistan": "AF",
                        "Albania": "AL",
                        "Algeria": "DZ",
                        "American Samoa": "AS",
                        "Andorra": "AD",
                        "Angola": "AO",
                        "Anguilla": "AI",
                        "Antarctica": "AQ",
                        "Antigua and Barbuda": "AG",
                        "Argentina": "AR",
                        "Armenia": "AM",
                        "Aruba": "AW",
                        "Australia": "AU",
                        "Austria": "AT",
                        "Azerbaijan": "AZ",
                        "Bahamas": "BS",
                        "Bahrain": "BH",
                        "Bangladesh": "BD",
                        "Barbados": "BB",
                        "Belarus": "BY",
                        "Belgium": "BE",
                        "Belize": "BZ",
                        "Benin": "BJ",
                        "Bermuda": "BM",
                        "Bhutan": "BT",
                        "Bolivia": "BO",
                        "Bonaire, Sint Eustatius and Saba": "BQ",
                        "Bosnia and Herzegovina": "BA",
                        "Botswana": "BW",
                        "Bouvet Island": "BV",
                        "Brazil": "BR",
                        "British Indian Ocean Territory": "IO",
                        "Brunei Darussalam": "BN",
                        "Bulgaria": "BG",
                        "Burkina Faso": "BF",
                        "Burundi": "BI",
                        "Cambodia": "KH",
                        "Cameroon": "CM",
                        "Canada": "CA",
                        "Cape Verde": "CV",
                        "Cayman Islands": "KY",
                        "Central African Republic": "CF",
                        "Chad": "TD",
                        "Chile": "CL",
                        "China": "CN",
                        "Christmas Island": "CX",
                        "Cocos (Keeling) Islands": "CC",
                        "Colombia": "CO",
                        "Comoros": "KM",
                        "Congo": "CG",
                        "Cook Islands": "CK",
                        "Costa Rica": "CR",
                        "Croatia": "HR",
                        "Cuba": "CU",
                        "Curaçao": "CW",
                        "Cyprus": "CY",
                        "Czech Republic": "CZ",
                        "Côte d'Ivoire": "CI",
                        "Democratic Republic of the Congo": "CD",
                        "Denmark": "DK",
                        "Djibouti": "DJ",
                        "Dominica": "DM",
                        "Dominican Republic": "DO",
                        "Ecuador": "EC",
                        "Egypt": "EG",
                        "El Salvador": "SV",
                        "Equatorial Guinea": "GQ",
                        "Eritrea": "ER",
                        "Estonia": "EE",
                        "Eswatini": "SZ",
                        "Ethiopia": "ET",
                        "Falkland Islands": "FK",
                        "Faroe Islands": "FO",
                        "Fiji": "FJ",
                        "Finland": "FI",
                        "France": "FR",
                        "French Guiana": "GF",
                        "French Polynesia": "PF",
                        "French Southern Territories": "TF",
                        "Gabon": "GA",
                        "Gambia": "GM",
                        "Georgia": "GE",
                        "Germany": "DE",
                        "Ghana": "GH",
                        "Gibraltar": "GI",
                        "Greece": "GR",
                        "Greenland": "GL",
                        "Grenada": "GD",
                        "Guadeloupe": "GP",
                        "Guam": "GU",
                        "Guatemala": "GT",
                        "Guernsey": "GG",
                        "Guinea": "GN",
                        "Guinea-Bissau": "GW",
                        "Guyana": "GY",
                        "Haiti": "HT",
                        "Heard Island and McDonald Islands": "HM",
                        "Holy See (Vatican City State)": "VA",
                        "Honduras": "HN",
                        "Hong Kong": "HK",
                        "Hungary": "HU",
                        "Iceland": "IS",
                        "India": "IN",
                        "Indonesia": "ID",
                        "Iran": "IR",
                        "Iraq": "IQ",
                        "Ireland": "IE",
                        "Isle of Man": "IM",
                        "Israel": "IL",
                        "Italy": "IT",
                        "Jamaica": "JM",
                        "Japan": "JP",
                        "Jersey": "JE",
                        "Jordan": "JO",
                        "Kazakhstan": "KZ",
                        "Kenya": "KE",
                        "Kiribati": "KI",
                        "Kosovo": "XK",
                        "Kuwait": "KW",
                        "Kyrgyzstan": "KG",
                        "Laos": "LA",
                        "Latvia": "LV",
                        "Lebanon": "LB",
                        "Lesotho": "LS",
                        "Liberia": "LR",
                        "Libya": "LY",
                        "Liechtenstein": "LI",
                        "Lithuania": "LT",
                        "Luxembourg": "LU",
                        "Macau": "MO",
                        "Madagascar": "MG",
                        "Malawi": "MW",
                        "Malaysia": "MY",
                        "Maldives": "MV",
                        "Mali": "ML",
                        "Malta": "MT",
                        "Marshall Islands": "MH",
                        "Martinique": "MQ",
                        "Mauritania": "MR",
                        "Mauritius": "MU",
                        "Mayotte": "YT",
                        "Mexico": "MX",
                        "Micronesia": "FM",
                        "Moldova": "MD",
                        "Monaco": "MC",
                        "Mongolia": "MN",
                        "Montenegro": "ME",
                        "Montserrat": "MS",
                        "Morocco": "MA",
                        "Mozambique": "MZ",
                        "Myanmar": "MM",
                        "Namibia": "NA",
                        "Nauru": "NR",
                        "Nepal": "NP",
                        "Netherlands": "NL",
                        "New Caledonia": "NC",
                        "New Zealand": "NZ",
                        "Nicaragua": "NI",
                        "Niger": "NE",
                        "Nigeria": "NG",
                        "Niue": "NU",
                        "Norfolk Island": "NF",
                        "North Korea": "KP",
                        "North Macedonia": "MK",
                        "Northern Mariana Islands": "MP",
                        "Norway": "NO",
                        "Oman": "OM",
                        "Pakistan": "PK",
                        "Palau": "PW",
                        "Panama": "PA",
                        "Papua New Guinea": "PG",
                        "Paraguay": "PY",
                        "Peru": "PE",
                        "Philippines": "PH",
                        "Pitcairn Islands": "PN",
                        "Poland": "PL",
                        "Portugal": "PT",
                        "Puerto Rico": "PR",
                        "Qatar": "QA",
                        "Romania": "RO",
                        "Russian Federation": "RU",
                        "Rwanda": "RW",
                        "Réunion": "RE",
                        "Saint Barthélémy": "BL",
                        "Saint Helena, Ascension and Tristan da Cunha": "SH",
                        "Saint Kitts and Nevis": "KN",
                        "Saint Lucia": "LC",
                        "Saint Martin (French part)": "MF",
                        "Saint Pierre and Miquelon": "PM",
                        "Saint Vincent and the Grenadines": "VC",
                        "Samoa": "WS",
                        "San Marino": "SM",
                        "Saudi Arabia": "SA",
                        "Senegal": "SN",
                        "Serbia": "RS",
                        "Seychelles": "SC",
                        "Sierra Leone": "SL",
                        "Singapore": "SG",
                        "Sint Maarten (Dutch part)": "SX",
                        "Slovakia": "SK",
                        "Slovenia": "SI",
                        "Solomon Islands": "SB",
                        "Somalia": "SO",
                        "South Africa": "ZA",
                        "South Georgia and the South Sandwich Islands": "GS",
                        "South Korea": "KR",
                        "South Sudan": "SS",
                        "Spain": "ES",
                        "Sri Lanka": "LK",
                        "State of Palestine": "PS",
                        "Sudan": "SD",
                        "Suriname": "SR",
                        "Svalbard and Jan Mayen": "SJ",
                        "Sweden": "SE",
                        "Switzerland": "CH",
                        "Syria": "SY",
                        "São Tomé and Príncipe": "ST",
                        "Taiwan": "TW",
                        "Tajikistan": "TJ",
                        "Tanzania": "TZ",
                        "Thailand": "TH",
                        "Timor-Leste": "TL",
                        "Togo": "TG",
                        "Tokelau": "TK",
                        "Tonga": "TO",
                        "Trinidad and Tobago": "TT",
                        "Tunisia": "TN",
                        "Turkmenistan": "TM",
                        "Turks and Caicos Islands": "TC",
                        "Tuvalu": "TV",
                        "Türkiye": "TR",
                        "USA Minor Outlying Islands": "UM",
                        "Uganda": "UG",
                        "Ukraine": "UA",
                        "United Arab Emirates": "AE",
                        "United Kingdom": "GB",
                        "United States": "US",
                        "Uruguay": "UY",
                        "Uzbekistan": "UZ",
                        "Vanuatu": "VU",
                        "Venezuela": "VE",
                        "Vietnam": "VN",
                        "Virgin Islands (British)": "VG",
                        "Virgin Islands (USA)": "VI",
                        "Wallis and Futuna": "WF",
                        "Western Sahara": "EH",
                        "Yemen": "YE",
                        "Zambia": "ZM",
                        "Zimbabwe": "ZW",
                        "Åland Islands": "AX"
                    }

                country_code = country_name_to_code.get(country.capitalize())
                    
                

                if country_code:
                        result = models.execute_kw(
                            db, uid, PASSWORD,
                            'res.country', 'search_read',
                            [[['code', '=', country_code]]],
                            {'fields': ['id'], 'limit': 1}
                        )

                        if result:
                            country_id = result[0]['id']

                
                return country_id

            def get_title_id(title):
                result = models.execute_kw(
                                    db, uid, PASSWORD,
                                    'res.partner.title', 'search_read',
                                    [[["shortcut", "=", title]]],
                                    {'fields': ['id'], 'limit': 1}
                                )

                if result:
                    return result[0]['id']
                return None

            def get_or_create_company_id(models, db, uid, password, company_data):
                domain = [['name', '=', company_data['name']], ['is_company', '=', True]]
                if company_data.get('vat'):
                    domain.append(['vat', '=', company_data['vat']])

                existing = models.execute_kw(
                                    db, uid, password,
                                    'res.partner', 'search_read',
                                    [domain],
                                    {'fields': ['id'], 'limit': 1}
                                )

                if existing:
                    return existing[0]['id']

                return models.execute_kw(
                                    db, uid, password,
                                    'res.partner', 'create',
                                    [company_data]
                                )



            try:
                

                user_data = parsed["attendify"]["user"]

                
            
                address = user_data.get("address")

                if address:
                    
                    street = address["street"]
                    number = address["number"]
                    bus = address.get("bus_number", "")
                    street2 = f"{number} Bus {bus}"
                    city = address["city"]
                    zip = address["postal_code"]
                    country = address["country"].strip().title()
                    country_id = get_country_id(country)
                

                email = user_data["email"]

                title = user_data["title"]

                if title:
                    title_id = get_title_id(title)



                invoice_data = user_data.get("payment_details", {}).get("facturation_address", {})
                invoice_address = None

                if invoice_data:
                    inv_street = invoice_data["street"]
                    inv_number = invoice_data["number"]
                    inv_bus = invoice_data.get("company_bus_number", "")
                    inv_street2 = f"{inv_number} Bus {inv_bus}".strip()
                    inv_city = invoice_data["city"]
                    inv_zip = invoice_data["postal_code"]
                    inv_country = invoice_data["country"].strip().title()
                    inv_country_id = get_country_id(inv_country)

                    invoice_address = {
                        "type": "invoice",
                        "name": f"{user_data['first_name']}_{user_data['last_name']} (Invoice Address)",
                        "email": email,
                        "phone": user_data.get("phone_number"),
                        "street": inv_street,
                        "street2": inv_street2,
                        "city": inv_city,
                        "zip": inv_zip,
                        "country_id": inv_country_id
                        }
                        


                from_company = user_data.get("from_company", "false").strip().lower()
                
                    

                if from_company == 'true':
                        company_raw = user_data["company"]
                        company_name = company_raw.get("name", "").strip()
                        company_vat = company_raw.get("VAT_number", "").strip()
                        company_address = company_raw.get("address", {})

                        company_street = company_address.get("street", "").strip()
                        company_number = company_address.get("number", "").strip()
                        company_street2 = company_number
                        company_city = company_address.get("city", "").strip()
                        company_zip = company_address.get("postal_code", "").strip()
                        company_country = company_address.get("country", "").strip().title()
                        company_country_id = get_country_id(company_country)

                        company_data = {
                            "name": company_name,
                            "vat": company_vat,
                            "street": company_street,
                            "street2": company_street2,
                            "city": company_city,
                            "zip": company_zip,
                            "country_id": company_country_id,
                            "is_company": True,
                            "customer_rank": 1,
                            "company_type": "company"
                        }
                        
                else:
                    company_data = None

                    
                odoo_user = {
                        "name": f"{user_data['first_name']}_{user_data['last_name']}",
                        "email": user_data.get("email"),
                        "customer_rank": 1,
                        "is_company": False,
                        "company_type": "person"
                    }
                
                if address:
                    odoo_user["street"] = street
                    odoo_user["street2"] = street2
                    odoo_user["city"] = city
                    odoo_user["zip"] = zip
                    odoo_user["country_id"] = country_id
                

               
                
                if user_data.get("phone_number"):
                      odoo_user["phone"] = user_data["phone_number"]
                
                if title:
                      odoo_user["title"] = title_id

                if user_data.get("id"):
                      odoo_user["ref"] = user_data["id"]
                    
                

            except Exception as e:
                print(f"XML parse error: {e}")
                    

            existing_user = models.execute_kw(
                    db, uid, PASSWORD,
                    'res.partner', 'search_read',
                    [[['email', '=', odoo_user['email']]]],
                    {'fields': ['id'], 'limit': 1}
                )

            if existing_user:
                    print(f"User {email} already exists with ID: {existing_user[0]['id']}")
                    return


            if company_data:
                    company_id = get_or_create_company_id(models, db, uid, PASSWORD, company_data)
                    odoo_user["parent_id"] = company_id
                    odoo_user["company_type"] = "person"
                    odoo_user["is_company"] = False
                
                
            new_partner_id = models.execute_kw(
                    db, uid, PASSWORD,  
                    'res.partner', 'create',  
                    [odoo_user]
                )

            print(f"Registered new user: {email} (ID {new_partner_id})")

            if invoice_address:
                    invoice_address["parent_id"] = new_partner_id
                    invoice_id = models.execute_kw(
                        db, uid, PASSWORD,
                        'res.partner', 'create',
                        [invoice_address]
                    )
                    print(f"Invoice address ID: {invoice_id}")


        else:
            print(f"Unknown routing key: {routing_key}")
 
    except Exception as e:
        print(f"Error processing message: {e}")
 
 
channel.basic_consume(queue=queue_main, on_message_callback=process_message, auto_ack=True)
print("Waiting for user messages...")
channel.start_consuming()
 
