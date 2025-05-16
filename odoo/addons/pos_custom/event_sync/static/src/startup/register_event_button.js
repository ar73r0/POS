odoo.define('event_sync.register_event_button', function (require) {
    'use strict';

    const { PosStore }  = require('@point_of_sale/app/store/pos_store');
    const { patch }     = require('@web/core/utils/patch');
    const EventButton   = require('event_sync.event_button');

    /** voeg de knop toe aan het arraytje met control-buttons */
    patch(PosStore.prototype, 'event_sync_register_event_button', {
        setupComponents() {
            this._super(...arguments);
            this.controlButtons.push(EventButton);   // links van Customer
        },
    });
});