odoo.define(
    'event_sync.order_auto_event',
    ['point_of_sale.models'],
    function (Order) {
        'use strict';

        const _super_initialize = Order.prototype.initialize;
        Order.prototype.initialize = function (attributes, options) {
            _super_initialize.call(this, attributes, options);
            this.event_id = this.pos.selectedEvent ? this.pos.selectedEvent.id : false;
        };
    }
);