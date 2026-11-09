# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
import os, subprocess, sys, unittest
import helpers as H


class Packaging(unittest.TestCase):
    def test_launchers_exist_and_are_executable_with_right_line_endings(self):
        for n in ("GyroidFilter-Linux.sh", "GyroidFilter-Mac.command"):
            p = os.path.join(H.ROOT, n)
            self.assertTrue(os.access(p, os.X_OK), n)
            self.assertNotIn(b"\r\n", open(p, "rb").read(), n)
        bat = open(os.path.join(H.ROOT, "GyroidFilter-Windows.bat"), "rb").read()
        self.assertIn(b"\r\n", bat); self.assertNotIn(b"\n", bat.replace(b"\r\n", b""))

    def test_cura_plugin_core_copy_is_current(self):
        r = subprocess.run([sys.executable, os.path.join(H.ROOT, "tools", "build_cura_plugin.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_version_flag(self):
        r = subprocess.run([sys.executable, "-m", "gyroid_filter", "--version"], capture_output=True, text=True,
                           env=dict(os.environ, PYTHONPATH=os.path.join(H.ROOT, "src")))
        self.assertIn("0.1.0-wip", r.stdout)

    def test_every_source_file_carries_the_licence_header(self):
        skip = {"three-bundle.js"}
        for d, _, files in os.walk(H.ROOT):
            if any(x in d for x in (".git", "__pycache__", "vendor")):
                continue
            for f in files:
                if f.endswith((".py", ".sh", ".command", ".qml")) and f not in skip:
                    head = open(os.path.join(d, f), encoding="utf-8").read(900)
                    self.assertIn("PolyForm Noncommercial", head, os.path.join(d, f))


if __name__ == "__main__":
    unittest.main()
