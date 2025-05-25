/** @odoo-module **/

import { patch }    from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    name: "event_sync.PosStore",

    /**
     * Patch the real method:  loadPosSessionInformation
     */
    async loadPosSessionInformation(superFn, ...args) {
        // run the core loader
        await superFn(...args);

        // keep the event on the store
        const ev = this.session.event_id;          // [id, display_name] or false
        this.event = ev ? { id: ev[0], display_name: ev[1] } : null;
    },
});
