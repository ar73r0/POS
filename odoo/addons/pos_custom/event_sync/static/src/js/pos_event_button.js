/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

export class EventButton extends Component {
    static template = "your_module_name.EventButton";  // Template defined in XML
    setup() {
        this.pos = usePos();                 // POS model (for current order)
        this.popup = useService("popup");    // Popup service to show popups:contentReference[oaicite:3]{index=3}
        this.orm = useService("orm");        // ORM service for RPC calls (to fetch events)
    }

    async onClick() {
        const order = this.pos.get_order();
        if (!order) return;
        // Fetch events from the server (you can add a domain to filter events as needed)
        let events;
        try {
            events = await this.orm.searchRead("event.event", [], ["name"]);
        } catch (e) {
            console.error("Failed to fetch events", e);
            return;
        }
        if (!events || events.length === 0) {
            // No events found: show an error popup to inform the user
            await this.popup.add(ErrorPopup, {
                title: _t("No Events"),
                body: _t("No events are available to select.")
            });
            return;
        }
        // Prepare list of events for selection
        const eventList = events.map(ev => ({
            id: ev.id,
            label: ev.name,
            item: ev.id,          // 'item' is the value that will be returned if selected
            // (Optional) isSelected: mark current event as pre-selected if already set on order
            ...(order.event_id && order.event_id === ev.id ? { isSelected: true } : {})
        }));

        // Open a SelectionPopup to let user pick an event:contentReference[oaicite:4]{index=4}
        const { confirmed, payload } = await this.popup.add(SelectionPopup, {
            title: _t("Select Event"),
            list: eventList,
            isInputSelected: true  // auto-focus on the list for keyboard input
        });
        if (confirmed) {
            const selectedEventId = payload;  // payload will be the `item` of the chosen option
            order.event_id = selectedEventId;               // store the selected event ID on the order
            const chosenEvent = events.find(ev => ev.id === selectedEventId);
            order.event_name = chosenEvent ? chosenEvent.name : "";  // store name as well (optional)
            // At this point, the order holds the selected event. This can be used when pushing the order.
            console.log(`Event selected for order: ${order.event_id} - ${order.event_name}`);
        }
    }
}

// Register the button in the ProductScreen's control buttons
ProductScreen.addControlButton({
    component: EventButton,
    condition: () => true,  // always show the button (you can add conditions here if needed)
});
