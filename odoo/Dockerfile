FROM odoo:17.0

WORKDIR /opt/odoo

# Extra modules en config
COPY ./addons /mnt/extra-addons
COPY ./config/odoo.conf /etc/odoo/odoo.conf
COPY ./requirements.txt /opt/odoo/requirements.txt

# reqs
## switch to root so pip can write to global site-packages
USER root
RUN python3 -m pip install --no-cache-dir --upgrade -r /opt/odoo/requirements.txt
## go back to the odoo user
USER odoo


EXPOSE 8069

CMD ["odoo", "--config=/etc/odoo/odoo.conf"]

