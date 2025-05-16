odoo.define(
    'event_sync.event_model',
    [
        '@web/core/registry',
        'point_of_sale.models',
        'moment',
    ],
    function (registry, PosGlobalState, moment) {
        'use strict';

        // Extra veld om events later via RPC mee te laden
        PosGlobalState.addFields(['event_ids']);

        registry.category('pos.models').add({
            model:  'event.event',
            fields: ['name', 'external_uid', 'date_begin', 'date_end'],
            domain: [['date_end', '>=', moment().format('YYYY-MM-DD HH:mm:ss')]],
            loaded(pos, events) {
                pos.events = events; // overal beschikbaar
            },
        });
    }
);