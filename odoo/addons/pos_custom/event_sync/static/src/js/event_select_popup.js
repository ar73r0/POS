/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registerPopup } from "@point_of_sale/app/utils/register_popups";
import { useService } from "@web/core/utils/hooks";

export class EventSelectPopup extends Component {
    setup() {
        super.setup();
        this.rpc   = useService("rpc");
        this.state = useState({ events: [] });

        onWillStart(async () => {
            /* grab the next 50 upcoming events */
            const today  = new Date().toISOString().slice(0, 10);
            this.state.events = await this.rpc({
                model: "event.event",
                method: "search_read",
                args: [[["date_end", ">", today]], ["id", "name", "date_begin"]],
                kwargs: { limit: 50, order: "date_begin asc" },
            });
        });
    }

    /** user clicked an event row */
    select(ev) {
        this.props.confirm({ event: ev });
        this.trigger("close-popup");
    }
}
EventSelectPopup.template = "event_sync.EventSelectPopup";
registerPopup("EventSelectPopup", EventSelectPopup);
