/** @odoo-module **/
import { patch } from '@web/core/utils/patch';
import { Order }   from "@point_of_sale/app/store/models/order";

patch(Order.prototype, {
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        if (this.event_id) {
            json.event_id = Number(this.event_id);
        }
        return json;
    },
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.event_id = json.event_id || null;
    },
});

patch(Order.prototype, "event_sync-default-event", {
    setup() {
        this._super(...arguments);
        // `this.pos.event` was set in step 3
        if (this.pos.event && !this.event_id) {
            this.event_id = this.pos.event.id;
        }
    },
});
