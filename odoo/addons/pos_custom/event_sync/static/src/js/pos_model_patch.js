/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import PosModel from "point_of_sale.models";

patch(PosModel.prototype, {
    // Runs *before* the POS actually loads its models list
    initialize: function (attributes, options) {
        // Find the session‐loader entry and add event_id to its fields
        for (const m of this.models) {
            if (m.model === "pos.session") {
                m.fields = m.fields.concat(["event_id"]);
                break;
            }
        }
        // call the original initializer
        this._super(attributes, options);
    },
});
