import os
import sys
import unittest
import importlib.util
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

#  Locate repo root and make sure it's import‑able
TEST_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


#  Helper to find + import res_partner.py with stubs in place
def _find_res_partner_file():
    for p in (
        os.path.join(
            PROJECT_ROOT,
            "addons",
            "pos_custom",
            "customer_rabbit_connector",
            "models",
            "res_partner.py",
        ),
        os.path.join(PROJECT_ROOT, "res_partner.py"),
    ):
        if os.path.isfile(p):
            return p
    raise FileNotFoundError("res_partner.py not found")


def _import_res_partner(env):
    # ---- stub Odoo framework pieces ------------------------------------
    fake_fields = SimpleNamespace(Char=lambda **kw: None)
    fake_api = SimpleNamespace(model_create_multi=lambda fn: fn)

    class _ModelMeta(type):
        def __new__(mcls, n, b, d):
            d.setdefault(
                "with_context",
                lambda self, **ctx: (self.env.context.update(ctx) or self)
            )
            return super().__new__(mcls, n, b, d)

    class FakeModel(metaclass=_ModelMeta):
        pass

    fake_models = SimpleNamespace(Model=FakeModel)
    fake_odoo = SimpleNamespace(
        models=fake_models,
        fields=fake_fields,
        api=fake_api,
    )
    sys.modules.update({
        "odoo": fake_odoo,
        "odoo.models": fake_models,
        "odoo.fields": fake_fields,
        "odoo.api": fake_api,
    })

    # ---- stub dotenv (load_dotenv *and* dotenv_values) -----------------
    sys.modules["dotenv"] = SimpleNamespace(
        load_dotenv=lambda *_, **__: None,
        dotenv_values=lambda *_, **__: env,   # res_partner calls this on import
    )

    # ---- import with env patched ---------------------------------------
    with patch.dict(os.environ, env, clear=True):
        spec = importlib.util.spec_from_file_location(
            "res_partner", _find_res_partner_file()
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    module.ResPartner.write = lambda self, vals: (self.__dict__.update(vals) or True)
    return module


#  Shared helpers
GOOD_ENV = {
    "RABBITMQ_HOST": "localhost",
    "RABBITMQ_PORT": "5672",
    "RABBITMQ_USERNAME": "u",
    "RABBITMQ_PASSWORD": "p",
    "RABBITMQ_VHOST": "vh",
}


def _partner(module, *, email="john@example.com"):
    """Return a minimal ResPartner instance ready for testing."""
    P = module.ResPartner
    p = P()
    p.id = 1
    p.email = email
    p.name = "John Doe"
    p.ref = ""                   
    p.integration_pw_hash = None
    p.title = SimpleNamespace(name="")   
    p.env = SimpleNamespace(context={})
    return p


def _fake_blocking_connection():
    """Return an object that mimics pika.BlockingConnection."""
    ch = MagicMock()
    return SimpleNamespace(channel=lambda: ch, close=lambda: None)


#  Test‑case
class TestProducerRouting(unittest.TestCase):
    """Validate routing‑keys for create / update / delete and skip logic."""

    def setUp(self):
        self.module = _import_res_partner(GOOD_ENV)

        self.module.bcrypt.gensalt = MagicMock(return_value=b"salt")
        self.module.bcrypt.hashpw = MagicMock(return_value=b"fakehash")

        self.fake_conn = _fake_blocking_connection()
        self.module.pika.PlainCredentials     = MagicMock()
        self.module.pika.ConnectionParameters = MagicMock()
        self.module.pika.BlockingConnection   = MagicMock(return_value=self.fake_conn)

    def test_create_routing_key(self):
        p = _partner(self.module)
        p._send_to_rabbitmq("create")
        ch = self.fake_conn.channel()
        self.assertEqual(ch.basic_publish.call_args.kwargs["routing_key"], "user.register")

    def test_update_routing_key(self):
        p = _partner(self.module)
        p._send_to_rabbitmq("create")             
        self.fake_conn.channel().basic_publish.reset_mock()

        p._send_to_rabbitmq("update")
        self.assertEqual(self.fake_conn.channel().basic_publish.call_args.kwargs["routing_key"],
                         "user.update")

    def test_delete_routing_key(self):
        p = _partner(self.module)
        p._send_to_rabbitmq("delete")
        self.assertEqual(self.fake_conn.channel().basic_publish.call_args.kwargs["routing_key"],
                         "user.delete")

    def test_no_email_skips_publish(self):
        p = _partner(self.module, email="")
        p._send_to_rabbitmq("create")
        self.fake_conn.channel().basic_publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
