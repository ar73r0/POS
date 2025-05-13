"""
tests/test_event_producer.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Controleert routing‑keys (create / update / delete) en de guard
bij ontbrekende RabbitMQ‑config in EventSync._send_event_to_rabbitmq().
"""

import os, sys, importlib.util, unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))
CANDIDATES = [
    os.path.join(ROOT, "addons", "pos_custom",
                 "customer_rabbit_connector", "models", "event_sync.py"),
    os.path.join(ROOT, "odoo", "addons", "pos_custom",
                 "event_sync", "models", "event_sync.py"),
]

GOOD_ENV = {
    "RABBITMQ_HOST": "rabbit", "RABBITMQ_PORT": "5672",
    "RABBITMQ_USERNAME": "u",   "RABBITMQ_PASSWORD": "pw",
    "RABBITMQ_VHOST": "/",
}


def _load_event_module(env):
    path = next((p for p in CANDIDATES if os.path.isfile(p)), None)
    if not path:
        raise FileNotFoundError("event_sync.py niet gevonden")

    # --- mini‑Odoo stubs -------------------------------------------
    fake_fields = SimpleNamespace(Char=lambda **_: None, Float=lambda **_: None)
    fake_api = SimpleNamespace(model_create_multi=lambda fn: fn)
    class _Meta(type):
        def __new__(m, n, b, d):
            d.setdefault("with_context",
                         lambda self, **ctx: (self.env.context.update(ctx) or self))
            return super().__new__(m, n, b, d)
    class FakeModel(metaclass=_Meta): pass
    fake_models = SimpleNamespace(Model=FakeModel)
    sys.modules.update({
        "odoo": SimpleNamespace(models=fake_models, fields=fake_fields, api=fake_api),
        "odoo.models": fake_models, "odoo.fields": fake_fields, "odoo.api": fake_api,
    })

    # --- dotenv & pika stubs ---------------------------------------
    sys.modules["dotenv"] = SimpleNamespace(dotenv_values=lambda *a, **k: {})
    fake_ch = MagicMock()
    sys.modules["pika"] = SimpleNamespace(
        PlainCredentials=MagicMock(),
        ConnectionParameters=MagicMock(),
        BlockingConnection=MagicMock(
            return_value=SimpleNamespace(channel=lambda: fake_ch, close=lambda: None)
        ),
        BasicProperties=MagicMock(),          # ← toegevoegd
    )

    # --- import with custom getenv ---------------------------------
    spec = importlib.util.spec_from_file_location("event_sync", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.os.getenv = lambda k, d=None, _env=env: _env.get(k, d)

    module.EventSync.__iter__ = lambda self: iter([self])
    module.EventSync.write  = lambda self, vals: (self.__dict__.update(vals) or True)
    return module, fake_ch


def _dummy_event(mod):
    ev = mod.EventSync()
    ev.id = 1
    ev.env = SimpleNamespace(context={})
    ev.external_uid = ""
    ev.name = "TestEvent"
    ev.address_id = SimpleNamespace(display_name="HQ")
    ev.date_begin = datetime(2025, 5, 1, 9, 0)
    ev.date_end   = datetime(2025, 5, 1, 17, 0)
    ev.user_id = SimpleNamespace(name="Organizer", ref="ORG123")
    ev.event_ticket_ids = []
    ev.description = ""
    ev.entrance_fee = None
    ev.title = SimpleNamespace(name="")
    return ev


class TestEventProducer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod, cls.ch = _load_event_module(GOOD_ENV)

    def _assert_routing(self, op, expected):
        self.ch.basic_publish.reset_mock()
        _dummy_event(self.mod)._send_event_to_rabbitmq(op)
        rk = self.ch.basic_publish.call_args.kwargs["routing_key"]
        self.assertEqual(rk, expected)

    def test_create_routing(self):
        self._assert_routing("create", "event.register")

    def test_update_routing(self):
        self._assert_routing("update", "event.update")

    def test_delete_routing(self):
        self._assert_routing("delete", "event.delete")

    def test_guard_skips_without_config(self):
        poor_env = {"RABBITMQ_PORT": "5672"}
        bad_mod, bad_ch = _load_event_module(poor_env)
        _dummy_event(bad_mod)._send_event_to_rabbitmq("create")
        bad_ch.basic_publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
