FROM odoo:17.0

WORKDIR /opt/odoo

# Extra modules en config
COPY ./addons /mnt/extra-addons
COPY ./config/odoo.conf /etc/odoo/odoo.conf
COPY ./requirements.txt /opt/odoo/requirements.txt

# reqs
RUN pip3 install --no-cache-dir --upgrade -r /opt/odoo/requirements.txt

ENV PYTHONPATH=/usr/local/lib/python3.10/site-packages

EXPOSE 8069

CMD ["odoo", "--config=/etc/odoo/odoo.conf"]
