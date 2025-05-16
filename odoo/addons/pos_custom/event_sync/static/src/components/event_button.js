odoo.define(
    'event_sync.EventButton',
    [
        'owl',
        '@point_of_sale/app/store/registries',
        '@point_of_sale/app/hooks/pos_hook',
    ],
    function (owl, Registries, usePos) {
        'use strict';

        const { Component } = owl;

        class EventButton extends Component {
            setup() {
                super.setup();
                this.pos = usePos();
            }

            /* label dat op de knop staat */
            get label() {
                return this.pos.selectedEvent
                    ? this.pos.selectedEvent.name
                    : this.env._t('Event');
            }

            get tooltip() {
                return this.pos.selectedEvent
                    ? this.env._t('Huidig event: ') + this.pos.selectedEvent.name
                    : this.env._t('Kies een event');
            }

            async onClick() {
                const { confirmed, payload } = await this.env.services.popup.add(
                    'EventSelectorPopup',
                    { title: this.env._t('Selecteer een event') }
                );
                if (confirmed) {
                    this.pos.selectedEvent = payload.event;
                    if (this.pos.get_order()) {
                        this.pos.get_order().event_id = payload.event.id;
                    }
                    this.render(); // knoplabel updaten
                }
            }
        }

        EventButton.template = 'EventButton';
        EventButton.category = 'pos.control_buttons';

        Registries.Component.add(EventButton);

        return EventButton;
    }
);