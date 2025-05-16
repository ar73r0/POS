/**  Popup met een eenvoudige lijst radio-buttons
 *   zodat de kassamedewerker één event kiest.
 *
 */
odoo.define('event_sync.event_selector_popup', function (require) {
    'use strict';

    const { usePos } = require('@point_of_sale/app/hooks/pos_hook');
    const { useState } = owl;
    const { Popup } = require('@point_of_sale/app/utils/Popup');

    class EventSelectorPopup extends Popup {
        setup() {
            super.setup();
            this.pos   = usePos();
            this.state = useState({ selectedId: null });
        }

        /** alle events die we in event_model.js hebben geladen */
        get events() {
            return this.pos.events || [];
        }

        /** gebruiker klikt op OK */
        confirm() {
            const ev = this.events.find(e => e.id === this.state.selectedId);
            this.props.resolve({ event: ev });
            this.pos.selectedEvent = ev;      // onthoud voor nieuwe orders
            this.trigger('close-popup');
        }

        /** gebruiker klikt op Cancel / sluit */
        cancel() {
            this.props.reject();
            this.trigger('close-popup');
        }

        /** radio-button geklikt */
        selectEvent(id) {
            this.state.selectedId = id;
        }
    }

    EventSelectorPopup.template = 'EventSelectorPopup';   // QWeb-naam

    return EventSelectorPopup;
});
