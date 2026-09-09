from __future__ import annotations

import unittest
import sys
import types
from unittest import mock


octoprint = types.ModuleType("octoprint")
octoprint.plugin = types.ModuleType("octoprint.plugin")
for name in ("SettingsPlugin", "TemplatePlugin", "AssetPlugin", "SimpleApiPlugin", "StartupPlugin"):
    setattr(octoprint.plugin, name, type(name, (), {}))
octoprint_access = types.ModuleType("octoprint.access")
octoprint_permissions = types.ModuleType("octoprint.access.permissions")
octoprint_permissions.Permissions = type("Permissions", (), {"CONTROL": object(), "ADMIN": object()})
sys.modules.setdefault("octoprint", octoprint)
sys.modules.setdefault("octoprint.plugin", octoprint.plugin)
sys.modules.setdefault("octoprint.access", octoprint_access)
sys.modules.setdefault("octoprint.access.permissions", octoprint_permissions)

from octoprint_lazarus import LazarusPlugin, MONTH_SECONDS


class DummyPlugin:
    def __init__(self):
        self.saved = None

    def _get_install_id(self):
        return "octoprint-install"

    def _save_license_cache(self, payload):
        self.saved = payload


class DummySettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, path):
        return self.values.get(path[0])


class LicenseCacheTests(unittest.TestCase):
    def test_short_lived_grant_never_gets_month_long_cache(self):
        plugin = DummyPlugin()
        now = 1_000_000
        deadline = now + 600

        status = LazarusPlugin._license_status_from_payload(
            plugin,
            {
                "access_expires_at": deadline,
                "cache_expires_at": deadline,
                "license_kind": "creator_tester",
                "license_model": "v2",
            },
            now=now,
        )

        self.assertEqual(status["expires_at"], deadline)
        self.assertEqual(status["access_expires_at"], deadline)
        self.assertEqual(status["access_kind"], "creator_tester")
        self.assertEqual(plugin.saved["expires_at"], deadline)

    def test_lifetime_subscription_keeps_existing_month_cache(self):
        plugin = DummyPlugin()
        now = 1_000_000

        status = LazarusPlugin._license_status_from_payload(
            plugin,
            {"license_kind": "subscription", "license_model": "v2"},
            now=now,
        )

        self.assertEqual(status["expires_at"], now + MONTH_SECONDS)

    def test_manage_subscription_creates_billing_portal_session(self):
        plugin = LazarusPlugin()
        plugin._settings = DummySettings(
            {
                "engine_url": "https://3dprintsaver.com/",
                "license_email": "buyer@example.com",
                "license_key": "license-key",
            }
        )
        response = mock.Mock(status_code=200)
        response.json.return_value = {
            "ok": True,
            "portal_url": "https://billing.stripe.test/session",
        }

        with mock.patch("octoprint_lazarus.requests.post", return_value=response) as post:
            result = plugin._manage_subscription({})

        self.assertEqual(result["portal_url"], "https://billing.stripe.test/session")
        post.assert_called_once_with(
            "https://3dprintsaver.com/manage-subscription",
            json={
                "email": "buyer@example.com",
                "license_key": "license-key",
                "return_origin": "https://3dprintsaver.com",
                "return_path": "/subscription",
            },
            timeout=10,
        )

    def test_manage_subscription_requires_credentials(self):
        plugin = LazarusPlugin()
        plugin._settings = DummySettings({"engine_url": "https://3dprintsaver.com"})

        with mock.patch("octoprint_lazarus.requests.post") as post:
            result = plugin._manage_subscription({})

        self.assertFalse(result["ok"])
        self.assertIn("checkout email and license key", result["error"])
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
