/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, "event_sync-pos-session", {
    async _loadPosSessionInformation(sessionInfo) {
        await this._super(...arguments);
        // store the event on the POS so orders can default to it
        if (sessionInfo.event_id) {
            this.event = {
                id: sessionInfo.event_id[0],
                display_name: sessionInfo.event_id[1],
            };
        }
    },
});
