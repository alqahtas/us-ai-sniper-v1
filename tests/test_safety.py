import os
import unittest
from unittest.mock import patch

from us_sniper.config import Settings
from us_sniper.ibkr_client import IBKRClient


class FakeResponse:
    def raise_for_status(self): pass
    def json(self): return {"authenticated": True, "connected": True}


class SafetyTests(unittest.TestCase):
    def test_live_mode_refused(self):
        with patch.dict(os.environ, {"MODE": "live"}, clear=True):
            with self.assertRaises(RuntimeError):
                Settings.from_env()

    def test_client_is_read_only(self):
        calls = []
        def transport(*args, **kwargs):
            calls.append((args, kwargs)); return FakeResponse()
        client = IBKRClient("https://example.invalid/v1/api", transport=transport)
        self.assertTrue(client.auth_status()["authenticated"])
        self.assertTrue(calls[0][0][0].endswith("/iserver/auth/status"))
        self.assertFalse(any(hasattr(client, name) for name in ("submit_order", "cancel_order", "modify_order")))


if __name__ == "__main__":
    unittest.main()

