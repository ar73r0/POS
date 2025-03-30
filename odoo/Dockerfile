FROM odoo:17.0
WORKDIR /opt/odoo
COPY ./addons /mnt/extra-addons
COPY ./config/odoo.conf /etc/odoo/odoo.conf
COPY requirements.txt /opt/odoo/requirements.txt
RUN pip3 install --no-cache-dir -r /opt/odoo/requirements.txt
# Install required Python package
RUN pip3 install pika
RUN chown -R odoo:odoo /mnt/extra-addons /etc/odoo /opt/odoo
EXPOSE 8069
CMD ["odoo", "--config=/etc/odoo/odoo.conf"]
