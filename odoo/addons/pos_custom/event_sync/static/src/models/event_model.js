/**  Haalt alle lopende events op bij het laden van de POS-sessie
 *   en bewaart ze in `pos.events`.
 */
odoo.define('event_sync.event_model', function (require) {
    'use strict';

    const { registry }       = require('@web/core/registry');
    const { PosGlobalState } = require('point_of_sale.models');
    const moment             = require('moment');   // zit standaard in de POS-assets

    // Extra veld om events later via RPC mee te laden
    PosGlobalState.addFields(['event_ids']);

    registry.category('pos.models').add({
        model:  'event.event',
        fields: ['name', 'external_uid', 'date_begin', 'date_end'],
        domain: [['date_end', '>=', moment().format('YYYY-MM-DD HH:mm:ss')]],
        loaded(pos, events) {
            pos.events = events;    // <— nu in alle JS overal beschikbaar
        },
    });
});