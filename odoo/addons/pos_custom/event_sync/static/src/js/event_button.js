/** @odoo-module **/
import { Component } from "@odoo/owl";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";

import { EventSelectPopup } from "./event_select_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";

export class EventButton extends Component {
  static template = "event_sync.EventButton";

  setup() {
    super.setup();
    this.pos   = usePos();
    this.orm   = useService("orm");
    this.popup = useService("popup");
  }

  async onClick() {
    // 1) fetch events
    const events = await this.orm.call("event.event", "search_read",
      [[], ["id", "name"]]
    );

    if (!events.length) {
      await this.popup.add(ConfirmPopup, {
        title: _t("No Events"),
        body:  _t("There are no events available."),
      });
      return;
    }

    // 2) show selector
    const { confirmed, payload: selectedId } =
      await this.popup.add(EventSelectPopup, { events });

    // user cancelled or nothing chosen ➜ do nothing
    if (!confirmed || !selectedId) {
      return;
    }

    // 3) tag order and acknowledge
    const order = this.pos.get_order();
    if (order) {
      order.event_id = selectedId;
      await this.popup.add(ConfirmPopup, {
        title: _t("Event set"),
        body:  _t("Order tagged with event %(id)s", { id: selectedId }),
      });
    }
  }
}

ProductScreen.addControlButton({
  component: EventButton,
  condition: () => true,
});
