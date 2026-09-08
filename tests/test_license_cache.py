from __future__ import annotations

import unittest
import sys
import types


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


if __name__ == "__main__":
    unittest.main()
