/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    /** unique name for this patch */
    name: "event_sync.PosStore",

    /** override */
    async _loadPosSessionInformation(sessionInfo) {
        await this._super(...arguments);
        if (sessionInfo.event_id) {
            this.event = {
                id:           sessionInfo.event_id[0],
                display_name: sessionInfo.event_id[1],
            };
        }
    },
});
