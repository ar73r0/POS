odoo.define(
    'event_sync.register_event_button',
    [
        '@point_of_sale/app/store/pos_store',
        '@web/core/utils/patch',
        'event_sync.EventButton',
    ],
    function (PosStore, patch, EventButton) {
        'use strict';

        patch(PosStore.prototype, 'event_sync_register_event_button', {
            setupComponents() {
                this._super(...arguments);
                this.controlButtons.push(EventButton); // links van Customer
            },
        });
    }
);