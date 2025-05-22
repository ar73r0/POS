# consumers/consumer.py
# -*- coding: utf-8 -*-
import logging
import xmlrpc.client
import xmltodict
import pika
from dotenv import dotenv_values

# ────────────────────────────────────────────────────────────────────────
# HELPERS FOR TEST-SUITE HOOKS
# ────────────────────────────────────────────────────────────────────────
def _handle_create(parsed):
    user = parsed['attendify']['user']
    ref  = (user.get('uid') or '').strip()
    if not ref:
        raise ValueError('UID missing in create message')
    # call into your "create user" logic:
    _create_user_logic(user)

def _handle_update(parsed):
    user = parsed['attendify']['user']
    ref  = (user.get('uid') or '').strip()
    if not ref:
        raise ValueError('UID missing in update message')
    # call into your "update user" logic:
    _update_user_logic(user)

def _handle_delete(parsed):
    ref = (parsed['attendify']['user'].get('uid') or '').strip()
    if not ref:
        raise ValueError('UID missing in delete message')
    delete_user(ref)

# ────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────────────────────────────
config      = dotenv_values()
ODOO_URL    = f"http://{config['ODOO_HOST']}:8069/"
ODOO_DB     = config['DATABASE']
ODOO_EMAIL  = config['EMAIL']
ODOO_API    = config['API_KEY']
RABBIT_HOST = config['RABBITMQ_HOST']
RABBIT_PORT = int(config['RABBITMQ_PORT'])
RABBIT_USER = config['RABBITMQ_USERNAME']
RABBIT_PWD  = config['RABBITMQ_PASSWORD']
RABBIT_VHOST= config['RABBITMQ_VHOST']

# ────────────────────────────────────────────────────────────────────────
# ODOO RPC SETUP
# ────────────────────────────────────────────────────────────────────────
common = xmlrpc.client.ServerProxy(f"{ODOO_URL}xmlrpc/2/common")
UID    = common.authenticate(ODOO_DB, ODOO_EMAIL, ODOO_API, {})
models = xmlrpc.client.ServerProxy(f"{ODOO_URL}xmlrpc/2/object")

# ────────────────────────────────────────────────────────────────────────
# RABBITMQ SETUP
# ────────────────────────────────────────────────────────────────────────
creds  = pika.PlainCredentials(RABBIT_USER, RABBIT_PWD)
params = pika.ConnectionParameters(
    host=RABBIT_HOST, port=RABBIT_PORT,
    virtual_host=RABBIT_VHOST,
    credentials=creds,
)
conn   = pika.BlockingConnection(params)
ch     = conn.channel()

EXCHANGE_MAIN = 'user-management'
QUEUE_MAIN    = 'pos.user'
ch.exchange_declare(exchange=EXCHANGE_MAIN, exchange_type="direct", durable=True)
ch.queue_declare   (queue=QUEUE_MAIN, durable=True)

# ────────────────────────────────────────────────────────────────────────
# UTILITY HELPERS
# ────────────────────────────────────────────────────────────────────────
def safe(value: str) -> str:
    return (value or "").strip()

def bool_from_str(value: str) -> bool:
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
    code = COUNTRY_NAME_TO_CODE.get(safe(country_name).title())
    if not code:
        return False
    res = models.execute_kw(
        ODOO_DB, UID, ODOO_API,
        'res.country', 'search_read',
        [[['code', '=', code]]],
        {'fields': ['id'], 'limit': 1, 'context': {'skip_rabbit': True}}
    )
    return res[0]['id'] if res else False

def get_title_id(shortcut: str):
    res = models.execute_kw(
        ODOO_DB, UID, ODOO_API,
        'res.partner.title', 'search_read',
        [[('shortcut', '=', safe(shortcut))]],
        {'fields': ['id'], 'limit': 1, 'context': {'skip_rabbit': True}}
    )
    return res[0]['id'] if res else False

def get_or_create_company_id(vals: dict):
    domain = [['name','=',vals['name']], ['is_company','=',True]]
    if vals.get('vat'):
        domain.append(['vat','=',vals['vat']])
    existing = models.execute_kw(
        ODOO_DB, UID, ODOO_API,
        'res.partner', 'search_read',
        [domain],
        {'fields':['id'],'limit':1,'context':{'skip_rabbit':True}}
    )
    if existing:
        return existing[0]['id']
    return models.execute_kw(
        ODOO_DB, UID, ODOO_API,
        'res.partner', 'create', [vals],
        {'context':{'skip_rabbit':True}}
    )

def delete_user(ref: str):
    partner_ids = models.execute_kw(
        ODOO_DB, UID, ODOO_API,
        'res.partner','search',[[['ref','=',ref]]],
        {'context':{'active_test':False,'skip_rabbit':True}}
    )
    if partner_ids:
        models.execute_kw(
            ODOO_DB, UID, ODOO_API,
            'res.partner','unlink',[partner_ids],
            {'context':{'skip_rabbit':True}}
        )
        logging.info("Deleted user %s", ref)
    else:
        logging.info("User %s not found", ref)

# ────────────────────────────────────────────────────────────────────────
# ACTUAL CREATE / UPDATE LOGIC
# ────────────────────────────────────────────────────────────────────────
def _create_user_logic(user: dict):
    ref = safe(user.get('uid'))
    # 1) Skip if already exists
    exists = models.execute_kw(
        ODOO_DB, UID, ODOO_API,
        'res.partner','search_read',
        [[['ref','=',ref]]],
        {'limit':1,'context':{'skip_rabbit':True}}
    )
    if exists:
        logging.info("User %s already exists", ref)
        return
    # 2) Build partner vals
    vals = {
        'ref':           ref,
        'name':          f"{safe(user.get('first_name'))} {safe(user.get('last_name'))}",
        'email':         safe(user.get('email')),
        'integration_pw_hash': safe(user.get('password')),
        'customer_rank': 1,
        'company_type':  'person',
    }
    # optional company address, country, title …
    country_id = get_country_id(user.get('country'))
    if country_id:
        vals['country_id'] = country_id
    title_id = get_title_id(user.get('title'))
    if title_id:
        vals['title'] = title_id
    # 3) Create
    partner_id = models.execute_kw(
        ODOO_DB, UID, ODOO_API,
        'res.partner','create',[vals],
        {'context':{'skip_rabbit':True}}
    )
    logging.info("Created user %s → %s", ref, partner_id)

def _update_user_logic(user: dict):
    ref = safe(user.get('uid'))
    ids = models.execute_kw(
        ODOO_DB, UID, ODOO_API,
        'res.partner','search',[[['ref','=',ref]]],
        {'context':{'active_test':False,'skip_rabbit':True}}
    )
    if not ids:
        logging.info("User %s not found (update skipped)", ref)
        return
    vals = {
        'name':  f"{safe(user.get('first_name'))} {safe(user.get('last_name'))}",
        'email': safe(user.get('email')),
    }
    pw = safe(user.get('password'))
    if pw:
        vals['integration_pw_hash'] = pw
    title_id = get_title_id(user.get('title'))
    if title_id:
        vals['title'] = title_id
    models.execute_kw(
        ODOO_DB, UID, ODOO_API,
        'res.partner','write',[ids, vals],
        {'context':{'skip_rabbit':True}}
    )
    logging.info("Updated user %s", ref)

# ────────────────────────────────────────────────────────────────────────
# MESSAGE DISPATCHER
# ────────────────────────────────────────────────────────────────────────
def process_message(ch, method, props, body):
    text = body.decode() if isinstance(body, (bytes, bytearray)) else body
    try:
        data = xmltodict.parse(text)
        op   = data['attendify']['info']['operation'].strip().lower()

        if   op == 'create':
            _handle_create(data)
        elif op == 'update':
            _handle_update(data)
        elif op == 'delete':
            _handle_delete(data)
        else:
            raise ValueError(f"Unknown operation: {op}")

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

# ────────────────────────────────────────────────────────────────────────
# STARTUP (only when run as __main__)
# ────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    ch.basic_consume(queue=QUEUE_MAIN,
                     on_message_callback=process_message,
                     auto_ack=False)
    logging.info("Waiting for user messages…")
    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        ch.stop_consuming()
    finally:
        conn.close()


if __name__ == '__main__':
    main()