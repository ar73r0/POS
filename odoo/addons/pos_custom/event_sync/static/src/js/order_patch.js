/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models/order";

patch(Order.prototype, {
    /* unique id for this patch */
    name: "event_sync.Order",

    // --------------------------------------------------
    // life-cycle: run once per Order instance
    // --------------------------------------------------
    setup() {
        this._super(...arguments);
        // default the event from the session
        if (this.pos.event && !this.event_id) {
            this.event_id = this.pos.event.id;
        }
    },

    // --------------------------------------------------
    // export / import so the event travels to the backend
    // --------------------------------------------------
    export_as_JSON() {
        const json = this._super(...arguments);
        if (this.event_id) {
            json.event_id = Number(this.event_id);
        }
        return json;
    },

    init_from_JSON(json) {
        this._super(...arguments);
        this.event_id = json.event_id || null;
    },
});
