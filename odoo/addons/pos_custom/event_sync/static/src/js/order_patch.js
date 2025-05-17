/** @odoo-module **/
import { patch } from '@web/core/utils/patch';
import { Order } from '@point_of_sale/app/store/models';

patch(Order.prototype, 'event_sync_order_patch', {
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.event_id = this.event_id || false;
        return json;
    },
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.event_id = json.event_id || null;
    },
});
