/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
// POS’s core loader class (ES module path)
import { PosModel } from "@point_of_sale/app/store/pos_model";

patch(PosModel.prototype, {
    name: "event_sync.PosModel",

    /**
     * initialize(superInitialize, session, attributes)
     * Runs before any models are loaded so we can inject our field.
     */
    initialize(superInitialize, session, attributes) {
        // inject into the pos.session loader
        this.models.forEach((m) => {
            if (m.model === "pos.session" && !m.fields.includes("event_id")) {
                m.fields.push("event_id");
            }
        });
        // call core initializer
        return superInitialize(session, attributes);
    },
});
