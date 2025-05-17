/** @odoo-module **/
import { patch }        from "@web/core/utils/patch";
import { _t }           from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService }   from "@web/core/utils/hooks";

patch(ProductScreen.prototype, "event_sync_pos_button", {
    setup() {
        super.setup();
        this.rpc          = useService("rpc");
        this.notification = useService("notification");
    },

    /* choose an event and store it on the current order */
    async select_event() {
        const { confirmed, payload } = await this.showPopup("EventSelectPopup");
        if (!confirmed) { return; }

        const order = this.env.pos.get_order();
        order.event_id = payload.event.id;
        this.notification.add(
            _t("Event set: ") + payload.event.name,
            { type: "info" }
        );
    },

});
