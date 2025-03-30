import sys, os, pika
from dotenv import  dotenv_values
import xmlrpc.client
import dicttoxml
import json
import xml.etree.ElementTree as ET
import xmltodict

config = dotenv_values()





def main():
    url = "http://localhost:8069/"
    db = config["DATABASE"]
    USERNAME = config["EMAIL"]
    PASSWORD = config["API_KEY"]


    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, USERNAME, PASSWORD, {})
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")




    credentials = pika.PlainCredentials(config["RABBITMQ_USERNAME"], config["RABBITMQ_PASSWORD"])
    params = pika.ConnectionParameters("localhost", 5672, config["RABBITMQ_VHOST"], credentials)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()


    exchange_main = 'user-management'
    routing_key_main = 'user.register'
    queue_main = 'pos.user'



    channel.exchange_declare(exchange=exchange_main, exchange_type="direct", durable=True)
    channel.queue_declare(queue=queue_main, durable=True)
    channel.queue_bind(queue=queue_main, exchange=exchange_main, routing_key=routing_key_main)


    exchange_monitoring = 'monitoring'
    routing_key_monitoring_success = 'monitoring.success'
    routing_key_monitoring_failure = 'monitoring.failure'
    queue_monitoring='monitoring'




    channel.exchange_declare(exchange=exchange_monitoring, exchange_type='direct', durable=True)
    channel.queue_declare(queue=queue_monitoring, durable=True)
    channel.queue_bind(exchange=exchange_monitoring, queue=queue_monitoring, routing_key=routing_key_monitoring_success)
    channel.queue_bind(exchange=exchange_monitoring, queue=queue_monitoring, routing_key=routing_key_monitoring_failure)




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
        
        country_id = None

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




        

   

    def parse_attendify_user(xml_data):
    
        try:
            parsed = xmltodict.parse(xml_data)
            
            
            operation = parsed["attendify"]["info"]["operation"].strip().lower()
            sender = parsed["attendify"]["info"]["sender"]

            user_data = parsed["attendify"]["user"]
            adress = user_data["address"]
            street = adress["street"]
            number = adress["number"]
            bus = adress.get("bus_number", "")
            street2 = f"{number} Bus {bus}"
            city = adress["city"]
            zip = adress["postal_code"]
            country = adress["country"].strip().title()
            country_id = get_country_id(country)
            title_id = get_title_id(user_data["title"])
            


           


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
                    "email": user_data.get("email"),
                    "phone": user_data.get("phone_number"),
                    "street": inv_street,
                    "street2": inv_street2,
                    "city": inv_city,
                    "zip": inv_zip,
                    "country_id": inv_country_id,
                }
                


            from_company = user_data["from_company"].strip().lower()
            

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
                    "company_type": "company",
                }
                
            else:
                company_data = None

            
            odoo_user = {
                "ref": user_data["id"],
                "name": f"{user_data['first_name']}_{user_data['last_name']}",
                "email": user_data.get("email"),
                "phone": user_data.get("phone_number"),
                "street": street,
                "street2": street2,
                "city": city,
                "zip": zip,
                "country_id" : country_id,
                "customer_rank": 1,
                "is_company": False,
                "company_type": "person",
                "title" : get_title_id(user_data["title"])
                
            }



            

            return odoo_user, invoice_address, company_data, operation, sender
        except Exception as e:
            print(f"XML parse error: {e}")
            return {}, None, None, None, None




    def customer_callback(ch, method, properties, body):
   

        try:
            odoo_user, invoice_address, company_data, operation, sender = parse_attendify_user(body.decode())
            operation = operation.lower()

            if (
                (method.routing_key == "user.register" and operation != "create") or 
                (method.routing_key == "user.update" and operation != "update") or 
                (method.routing_key == "user.delete" and operation != "delete")
                ):
                print("routing_key does not match operation information")

                failure_xml = """
                <attendify>
                    <info>
                        <sender>KASSA</sender>
                        <operation>{operation}</operation>
                        <monitoring>{method.routing_key}</monitoring>
                        <reason>Operation information does not match routing_key</reason>
                    </info>
                </attendify>
                """
                channel.basic_publish(
                    exchange=exchange_monitoring,
                    routing_key=routing_key_monitoring_failure,
                    body=failure_xml
                )

                return


            existing_user = models.execute_kw(
                db, uid, PASSWORD,
                'res.partner', 'search_read',
                [[['ref', '=', odoo_user['ref']]]],
                {'fields': ['id'], 'limit': 1}
            )

            if existing_user:
                print(f"User already exists with ID: {existing_user[0]['id']}")
                failure_xml = """
                <attendify>
                    <info>
                        <sender>KASSA</sender>
                        <operation>create</operation>
                        <monitoring>user.register.failure</monitoring>
                        <reason>User already exists</reason>
                    </info>
                </attendify>
                """
                channel.basic_publish(
                    exchange=exchange_monitoring,
                    routing_key=routing_key_monitoring_failure,
                    body=failure_xml
                )

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

            print(f"Created user ID: {new_partner_id}")

            if invoice_address:
                invoice_address["parent_id"] = new_partner_id
                invoice_id = models.execute_kw(
                    db, uid, PASSWORD,
                    'res.partner', 'create',
                    [invoice_address]
                )
                print(f"Invoice address ID: {invoice_id}")


            success_xml = """
            <attendify>
                <info>
                    <sender>KASSA</sender>
                    <operation>create</operation>
                    <monitoring>user.register.success</monitoring>
                </info>
            </attendify>
            """
            channel.basic_publish(
                exchange=exchange_monitoring,
                routing_key=routing_key_monitoring_success,
                body=success_xml
            )

            

        except Exception as e:
            print(f"Faut: {e}")

            failure_xml = """
            <attendify>
                <info>
                    <sender>KASSA</sender>
                    <operation>create</operation>
                    <monitoring>user.register.failure</monitoring>
                    <reason>An error occurred while creating the user, please try again.</reason>
                </info>
            </attendify>
            """
            channel.basic_publish(
                exchange=exchange_monitoring,
                routing_key=routing_key_monitoring_failure,
                body=failure_xml
            )

            




    channel.basic_consume(queue=queue_main, 
                        on_message_callback=customer_callback,
                        auto_ack=True)

    print("Waiting ...")

    channel.start_consuming()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)







