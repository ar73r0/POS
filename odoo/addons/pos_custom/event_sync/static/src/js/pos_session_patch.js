/** @odoo-module **/

import { patch }    from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    name: "_event_sync.PosStore",

    async _loadPosSessionInformation(superFn, ...args) {
        await superFn(...args);
        const ev = this.session.event_id;
        this.event = ev ? { id: ev[0], display_name: ev[1] } : null;
    },
});
