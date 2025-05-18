/** @odoo-module **/
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";

export class EventSelectPopup extends AbstractAwaitablePopup {
    static template     = "event_sync.EventSelectPopup";
    static defaultProps = { title:"Select an Event", confirmText:"OK", cancelText:"Cancel", events:[] };

    setup() {
        super.setup();
        this.state = useState({ selectedId: this.props.events[0]?.id || null });
    }

    // Base class will call this in its own confirm()
    getPayload() {
        return this.state.selectedId;
    }
    // no confirm() override at all
}
