/**  Toon de Event-popup wanneer alle POS-data geladen is. */
odoo.define('event_sync.event_popup_start', function (require) {
    'use strict';

    // Juiste imports
    const { patch }     = require('@web/core/utils/patch');
    const { PosStore }  = require('@point_of_sale/app/store/pos_store');  // v17-path

    patch(PosStore.prototype, 'event_sync_event_popup_start', {
        /**
         *  Wordt exact één keer geroepen nadat de server-data binnen is.
         */
        async _initializeWithServerData(serverData) {
            await this._super(...arguments);

            if (!this.selectedEvent && (this.events || []).length) {
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
