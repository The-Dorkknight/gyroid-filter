# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""The Cura installer, against a fake Cura settings folder (NOT a real Cura). Covers the bugs met in earlier Cura plug-ins:
flat copy that Cura does not list under Marketplace > Manage, an unreadable packages.json being overwritten,
and a 'loaded' log line being taken as proof although Cura crashed afterwards."""
import json, os, tempfile, unittest
import helpers as H
from gyroid_filter import server


class CuraInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = os.path.join(self.tmp.name, "cura", "5.11")
        os.makedirs(os.path.join(self.cfg, "plugins"))
        self._roots = server.cura_roots
        server.cura_roots = lambda: [os.path.join(self.tmp.name, "cura")]

    def tearDown(self):
        server.cura_roots = self._roots
        self.tmp.cleanup()

    def pk(self):
        return os.path.join(self.cfg, "packages.json")

    def test_installs_in_cura_package_layout_and_records_it(self):
        other = {"installed": {"OtherPlugin": {"package_info": {"package_id": "OtherPlugin"}}}, "to_remove": ["GyroidFilter", "x"],
                 "to_install": {"GyroidFilter": {}}}
        json.dump(other, open(self.pk(), "w"))
        r = server.cura_install(self.cfg)
        self.assertTrue(r["verified"] and r["registered"])
        self.assertTrue(os.path.isfile(os.path.join(self.cfg, "plugins", "GyroidFilter", "GyroidFilter", "plugin.json")))
        self.assertFalse(os.path.exists(os.path.join(self.cfg, "plugins", "GyroidFilter", "plugin.json")))   # not flat
        d = json.load(open(self.pk()))
        self.assertIn("OtherPlugin", d["installed"])                       # other plug-ins' records kept
        self.assertEqual(d["installed"]["GyroidFilter"]["package_info"]["package_type"], "plugin")
        self.assertEqual(d["to_remove"], ["x"]); self.assertNotIn("GyroidFilter", d["to_install"])   # stale entries cleared
        c = server.cura_status()["copies"][0]
        self.assertTrue(c["installed"] and c["in_sync"] and c["registered"] and not c["old_layout"])

    def test_old_flat_copy_is_migrated(self):
        flat = os.path.join(self.cfg, "plugins", "GyroidFilter"); os.makedirs(flat)
        open(os.path.join(flat, "plugin.json"), "w").write("{}")
        self.assertTrue(server.cura_status()["copies"][0]["old_layout"])
        server.cura_install(self.cfg)
        self.assertFalse(server.cura_status()["copies"][0]["old_layout"])

    def test_unreadable_packages_json_is_never_overwritten(self):
        open(self.pk(), "w").write("{ this is not json")
        with self.assertRaises(ValueError):
            server.cura_install(self.cfg)
        self.assertEqual(open(self.pk()).read(), "{ this is not json")
        self.assertFalse(os.path.exists(os.path.join(self.cfg, "plugins", "GyroidFilter")))   # nothing half-installed
        with self.assertRaises(ValueError):
            server.cura_uninstall(self.cfg)

    def test_uninstall_removes_folder_and_record_only_for_us(self):
        json.dump({"installed": {"OtherPlugin": {}}}, open(self.pk(), "w"))
        server.cura_install(self.cfg); server.cura_uninstall(self.cfg)
        self.assertFalse(os.path.exists(os.path.join(self.cfg, "plugins", "GyroidFilter")))
        self.assertEqual(list(json.load(open(self.pk()))["installed"]), ["OtherPlugin"])

    def test_log_check_is_strict(self):
        log = os.path.join(self.cfg, "cura.log")
        def state(text):
            open(log, "w").write(text); return server.cura_log_state(self.cfg)["state"]
        self.assertEqual(state(""), "never")
        self.assertEqual(state("x GyroidFilter: core self-test PASS\n"), "loaded")
        self.assertEqual(state("x GyroidFilter: core self-test PASS\nTraceback (most recent call last)\n"), "crashed")
        self.assertEqual(state("x GyroidFilter: core self-test crashed: boom\n"), "failed")


if __name__ == "__main__":
    unittest.main()
