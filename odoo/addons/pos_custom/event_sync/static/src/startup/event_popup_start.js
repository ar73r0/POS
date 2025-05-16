odoo.define('event_sync.event_popup_start', function (require) {
    'use strict';

    const { patch }   = require('@web/core/utils/patch');
    const { PosStore } = require('@point_of_sale/app/store/pos_store');

    patch(PosStore.prototype, 'event_sync_event_popup_start', {
        async _initializeWithServerData(serverData) {
            await this._super(...arguments);

            if (!this.selectedEvent && (this.events || []).length) {
                const { confirmed, payload } = await this.env.services.popup.add(
                    'EventSelectorPopup',
                    { title: 'Selecteer een event' }
                );
                if (confirmed) {
                    this.selectedEvent = payload.event;
                }
            }
        },
    });
});
