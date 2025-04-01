FROM odoo:17.0

WORKDIR /opt/odoo

# Kopieer je Odoo-addons
COPY ./addons /mnt/extra-addons

# Kopieer je .env
COPY .env /opt/odoo/.env

# Kopieer je config en requirements
COPY ./config/odoo.conf /etc/odoo/odoo.conf
COPY requirements.txt /opt/odoo/requirements.txt

RUN pip3 install --no-cache-dir -r /opt/odoo/requirements.txt

EXPOSE 8069

CMD ["odoo", "--config=/etc/odoo/odoo.conf"]
