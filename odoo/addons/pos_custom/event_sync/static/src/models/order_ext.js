/**  Slaat het gekozen event mee op in elke order-payload
 *   ⇄  _order_fields() aan server-kant.
 */
odoo.define('event_sync.order_ext', function (require) {
    'use strict';

    const { Order } = require('point_of_sale.models');

    // bij het (her)laden van een order vanuit de DB
    const _super_init_from_JSON = Order.prototype.init_from_JSON;
    Order.prototype.init_from_JSON = function (json) {
        _super_init_from_JSON.call(this, json);
        this.event_id = json.event_id || false;
    };

    // bij het doorsturen naar de server
    const _super_export_as_JSON = Order.prototype.export_as_JSON;
    Order.prototype.export_as_JSON = function () {
        const json   = _super_export_as_JSON.call(this);
        json.event_id = this.event_id || false;
        return json;
    };
});