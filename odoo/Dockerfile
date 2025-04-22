FROM odoo:17.0

WORKDIR /opt/odoo

# Extra modules en config
COPY odoo/addons /mnt/extra-addons
COPY odoo/.env /opt/odoo/.env
COPY odoo/config/odoo.conf /etc/odoo/odoo.conf
COPY odoo/requirements.txt /opt/odoo/requirements.txt

# Installeer vereisten één keer, globaal
RUN pip3 install --no-cache-dir --upgrade -r /opt/odoo/requirements.txt

# (optioneel maar veilig) Zet juiste PYTHONPATH
ENV PYTHONPATH=/usr/local/lib/python3.10/site-packages

EXPOSE 8069

CMD ["odoo", "--config=/etc/odoo/odoo.conf"]
