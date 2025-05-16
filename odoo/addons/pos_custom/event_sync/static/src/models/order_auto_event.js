/**  Zorgt dat elke nieuwe order automatisch het
 *   in de popup gekozen event erft.
 */
odoo.define('event_sync.order_auto_event', function (require) {
    'use strict';

    const { Order } = require('point_of_sale.models');

    const _super_initialize = Order.prototype.initialize;
    Order.prototype.initialize = function (attributes, options) {
        _super_initialize.call(this, attributes, options);
        this.event_id = this.pos.selectedEvent
            ? this.pos.selectedEvent.id
            : false;
    };
});