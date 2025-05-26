/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
// Path to the POS Order class
import Order from "@point_of_sale/app/models/order";

// Patch the Order prototype
patch(Order.prototype, "event_sync.Order", {
    /**
     * Override the JSON exporter to include our event_id
     */
    export_as_JSON(superExportAsJSON) {
        // call the original
        const json = superExportAsJSON(...arguments);
        // pull the event from the store (set earlier by pos_session_patch)
        const storeEvent = this.env.pos.event;
        // if selected, attach its ID
        json.event_id = storeEvent ? storeEvent.id : false;
        return json;
    },
});
