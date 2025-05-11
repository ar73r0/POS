import logging
import xmlrpc.client
import xmltodict
import pika
from dotenv import dotenv_values

# Config helpers

config = dotenv_values()

# Odoo connection
ODOO_URL = f"http://{config['ODOO_HOST']}:8069/"
ODOO_DB = config['DATABASE']
ODOO_EMAIL = config['EMAIL']
ODOO_API_KEY = config['API_KEY']

common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
ODOO_UID = common.authenticate(ODOO_DB, ODOO_EMAIL, ODOO_API_KEY, {})
models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")

# RabbitMQ connection
RABBIT_PARAMS = pika.ConnectionParameters(
    host=config['RABBITMQ_HOST'],
    port=int(config['RABBITMQ_PORT']),
    virtual_host=config['RABBITMQ_VHOST'],
    credentials=pika.PlainCredentials(
        config['RABBITMQ_USERNAME'],
        config['RABBITMQ_PASSWORD']
    )
)

EXCHANGE_MAIN = 'user-management'
QUEUE_MAIN = 'pos.user'


# Utility helpers

def safe(value: str) -> str:
    """Stript een string, retourneert altijd een (mogelijke lege) string."""
    return (value or "").strip()


def bool_from_str(value: str) -> bool:
    """'true'/'True' → True, alles andere → False"""
    return safe(value).lower() == 'true'


# Statische mapping landnaam → ISO‑2 code
from typing import Dict
COUNTRY_NAME_TO_CODE: Dict[str, str] = {
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

        
def get_country_id(country_name: str):
    """Geeft Odoo country_id terug of False als niet gevonden."""
    code = COUNTRY_NAME_TO_CODE.get(safe(country_name).title())
    if not code:
        return False
    res = models.execute_kw(
        ODOO_DB, ODOO_UID, ODOO_API_KEY,
        'res.country', 'search_read',
        [[['code', '=', code]]],
        {'fields': ['id'], 'limit': 1}
    )
    return res[0]['id'] if res else False


def get_title_id(shortcut: str):
    res = models.execute_kw(
        ODOO_DB, ODOO_UID, ODOO_API_KEY,
        'res.partner.title', 'search_read',
        [[('shortcut', '=', safe(shortcut))]],
        {'fields': ['id'], 'limit': 1}
    )
    return res[0]['id'] if res else False


def get_or_create_company_id(company_vals: dict):
    domain = [['name', '=', company_vals['name']], ['is_company', '=', True]]
    if company_vals.get('vat'):
        domain.append(['vat', '=', company_vals['vat']])

    existing = models.execute_kw(
        ODOO_DB, ODOO_UID, ODOO_API_KEY,
        'res.partner', 'search_read',
        [domain],
        {'fields': ['id'], 'limit': 1}
    )
    if existing:
        return existing[0]['id']

    return models.execute_kw(
        ODOO_DB, ODOO_UID, ODOO_API_KEY,
        'res.partner', 'create',
        [company_vals]
    )


# CRUD helpers

def delete_user(ref: str):
    partner_ids = models.execute_kw(
        ODOO_DB, ODOO_UID, ODOO_API_KEY,
        'res.partner', 'search',
        [[['ref', '=', ref]]],
        {'context': {'active_test': False}}
    )
    if partner_ids:
        models.execute_kw(
            ODOO_DB, ODOO_UID, ODOO_API_KEY,
            'res.partner', 'unlink',
            [partner_ids]
        )
        logging.info("Customer %s deleted", ref)
    else:
        logging.info("Customer %s not found (nothing to delete)", ref)


# Message handler

def process_message(ch, method, properties, body):
    """Callback voor RabbitMQ consumer."""
    try:
        parsed = xmltodict.parse(body.decode('utf-8'))
        info = parsed.get('attendify', {}).get('info', {})
        operation = safe(info.get('operation')).lower()

        if not operation:
            raise ValueError('operation tag is missing')

        if operation == 'delete':
            _handle_delete(parsed)
        elif operation == 'update':
            _handle_update(parsed)
        elif operation == 'create':
            _handle_create(parsed)
        else:
            raise ValueError(f'Unknown operation: {operation}')

        # success → ACK
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        logging.error("Error processing message: %s", exc, exc_info=True)
        # failure → NACK (niet opnieuw in de queue)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


# Handlers per operation

def _handle_delete(parsed):
    uid_value = safe(parsed['attendify']['user'].get('uid'))
    if not uid_value:
        raise ValueError('UID missing in delete message')
    delete_user(uid_value)


def _handle_update(parsed):
    user = parsed['attendify']['user']

    ref = safe(user.get('uid'))
    if not ref:
        raise ValueError('UID missing in update message')

    partner_ids = models.execute_kw(
        ODOO_DB, ODOO_UID, ODOO_API_KEY,
        'res.partner', 'search',
        [[['ref', '=', ref]]],
        {'context': {'active_test': False}}
    )
    if not partner_ids:
        logging.info("Partner with ref %s not found (update ignored)", ref)
        return

    update_vals = {
        'name': f"{safe(user.get('first_name'))} {safe(user.get('last_name'))}",
        'email': safe(user.get('email')),
    }
    title_id = get_title_id(user.get('title'))
    if title_id:
        update_vals['title'] = title_id

    models.execute_kw(
        ODOO_DB, ODOO_UID, ODOO_API_KEY,
        'res.partner', 'write',
        [partner_ids, update_vals],
        {'context': {'skip_rabbit': True}}
    )
    logging.info("Updated user with ref %s", ref)


def _handle_create(parsed):
    """Maak persoon + optioneel facturatie‑ en bedrijfspartner"""
    user = parsed['attendify']['user']

    uid_value = safe(user.get('uid'))
    if not uid_value:
        raise ValueError('UID missing in create message')

    existing = models.execute_kw(
        ODOO_DB, ODOO_UID, ODOO_API_KEY,
        'res.partner', 'search_read',
        [[['ref', '=', uid_value]]],
        {'fields': ['id'], 'limit': 1}
    )
    if existing:
        logging.info('User %s already exists (ID %s) – create skipped', uid_value, existing[0]['id'])
        return

    # Adres persoon          
    addr = user.get('address', {}) or {}
    person_vals = {
        'ref': uid_value,
        'is_company': False,
        'customer_rank': 1,
        'company_type': 'person',
        'name': f"{safe(user.get('first_name'))} {safe(user.get('last_name'))}",
        'email': safe(user.get('email')),
        'phone': safe(user.get('phone_number')),
        'street': safe(addr.get('street')),
        'street2': f"{safe(addr.get('number'))} Bus {safe(addr.get('bus_number'))}".strip(),
        'city': safe(addr.get('city')),
        'zip': safe(addr.get('postal_code')),
    }
    country_id = get_country_id(addr.get('country'))
    if country_id:
        person_vals['country_id'] = country_id

    title_id = get_title_id(user.get('title'))
    if title_id:
        person_vals['title'] = title_id

    # Bedrijf               
    company_id = False
    if bool_from_str(user.get('from_company')):
        comp = user.get('company', {}) or {}
        comp_addr = comp.get('address', {}) or {}
        company_vals = {
            'name': safe(comp.get('name')),
            'vat': safe(comp.get('VAT_number')),
            'is_company': True,
            'customer_rank': 1,
            'company_type': 'company',
            'street': safe(comp_addr.get('street')),
            'street2': safe(comp_addr.get('number')),
            'city': safe(comp_addr.get('city')),
            'zip': safe(comp_addr.get('postal_code')),
        }
        comp_country_id = get_country_id(comp_addr.get('country'))
        if comp_country_id:
            company_vals['country_id'] = comp_country_id

        company_id = get_or_create_company_id(company_vals)
        person_vals['parent_id'] = company_id

    # Partner aanmaken      
    partner_id = models.execute_kw(
        ODOO_DB, ODOO_UID, ODOO_API_KEY,
        'res.partner', 'create',
        [person_vals]
    )
    logging.info("Registered new user %s (ID %s)", uid_value, partner_id)

    # Facturatie‑adres
    inv_addr = user.get('payment_details', {}).get('facturation_address', {}) or {}
    if any(inv_addr.values()):  # alleen als er data is
        invoice_vals = {
            'type': 'invoice',
            'parent_id': partner_id,
            'name': f"{safe(user.get('first_name'))} {safe(user.get('last_name'))} (Invoice Address)",
            'street': safe(inv_addr.get('street')),
            'street2': f"{safe(inv_addr.get('number'))} Bus {safe(inv_addr.get('company_bus_number'))}".strip(),
            'city': safe(inv_addr.get('city')),
            'zip': safe(inv_addr.get('postal_code')),
            'email': safe(user.get('email')),
            'phone': safe(user.get('phone_number')),
        }
        inv_country_id = get_country_id(inv_addr.get('country'))
        if inv_country_id:
            invoice_vals['country_id'] = inv_country_id

        invoice_id = models.execute_kw(
            ODOO_DB, ODOO_UID, ODOO_API_KEY,
            'res.partner', 'create',
            [invoice_vals]
        )
        logging.info("Created invoice address for %s (ID %s)", uid_value, invoice_id)

# Main – start consumer

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logging.info('Connecting to RabbitMQ…')
    connection = pika.BlockingConnection(RABBIT_PARAMS)
    channel = connection.channel()
    channel.basic_consume(queue=QUEUE_MAIN, on_message_callback=process_message, auto_ack=False)
    logging.info('Waiting for user messages…')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logging.info('Stopping consumer…')
        channel.stop_consuming()
    finally:
        connection.close()


if __name__ == '__main__':
    main()
