/**
 *  Patch de POS-App zodat er meteen na het laden
 *  (maar vóór de eerste bestelling) een event-popup komt.
 */
odoo.define('event_sync.event_popup_start', function (require) {
    'use strict';

    const Registries   = require('@point_of_sale/app/store/registries');
    const { PosStore } = require('point_of_sale.models');
    const { patch }    = owl;

    patch(PosStore.prototype, 'event_sync_event_popup_start', {
        /**
         *  _initializeWithServerData wordt exact één keer geroepen
         *  wanneer alle data uit de back-end geladen is.
         */
        async _initializeWithServerData(serverData) {
            await this._super(...arguments);

            // Popup alleen tonen wanneer er minstens één event is
            if ((this.events || []).length) {
                const { confirmed, payload } = await this.env.services.popup.add(
                    'EventSelectorPopup',
                    { title: this.env._t('Selecteer een event') }
                );
                if (confirmed) {
                    this.selectedEvent = payload.event;
                }
            }
        },
    });
});
