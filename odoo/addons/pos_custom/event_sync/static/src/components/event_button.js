odoo.define('event_sync.event_button', function (require) {
    'use strict';

    const { Component } = owl;
    const { usePos }    = require('@point_of_sale/app/hooks/pos_hook');

    class EventButton extends Component {
        setup() {
            super.setup();
            this.pos = usePos();
        }

        /** label dat we op de knop tonen */
        get label() {
            return this.pos.selectedEvent
                ? this.pos.selectedEvent.name
                : this.env._t('Event');
        }

        /** tooltip */
        get tooltip() {
            return this.pos.selectedEvent
                ? this.env._t('Huidig event: ') + this.pos.selectedEvent.name
                : this.env._t('Kies een event');
        }

        /** klik → popup tonen */
        async onClick() {
            const { confirmed, payload } = await this.env.services.popup.add(
                'EventSelectorPopup',
                { title: this.env._t('Selecteer een event') }
            );
            if (confirmed) {
                this.pos.selectedEvent = payload.event;
                /* huidige order bijwerken */
                if (this.pos.get_order()) {
                    this.pos.get_order().event_id = payload.event.id;
                }
                /* forceer hertekenen */
                this.render();
            }
        }
    }

    EventButton.template = 'EventButton';
    return EventButton;
});