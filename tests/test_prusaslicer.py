# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Slices our 3MF in a real PrusaSlicer (skipped when the prusa-slicer command is not installed) and
reads the G-code: inside the region there must be no perimeters and no solid skin, only infill whose
direction changes all the time (gyroid) even though the global pattern is straight lines."""
import math, os, shutil, subprocess, tempfile, unittest
import helpers as H
from gyroid_filter import regions as R
from gyroid_filter.export3mf import write_prusa

PRUSA = shutil.which("prusa-slicer") or shutil.which("PrusaSlicer")


def slice_3mf(data, d, extra=()):
    src, out = os.path.join(d, "in.3mf"), os.path.join(d, "out.gcode")
    with open(src, "wb") as f: f.write(data)
    cmd = [PRUSA, "--export-gcode", "--dont-arrange", "--fill-pattern=rectilinear", "--fill-density=20%", "--perimeters=3",
           "--layer-height=0.3", "--first-layer-height=0.3", *extra, "-o", out, src]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-600:] + r.stderr[-600:]
    return out


@unittest.skipUnless(PRUSA, "prusa-slicer is not installed")
class RealSlice(unittest.TestCase):
    def test_cartridge_walls_become_open_cell_gyroid(self):
        m = H.cartridge_mesh(); topo = R.Topology(m)
        regs = []
        for r in (30, 12):
            t = H.find_tri(m, lambda c, n, r=r: abs(math.hypot(c[0], c[1]) - r) < .2 and abs(n[2]) < .1 and c[2] > 10)
            s = R.pick(m, topo, t)
            reg, _ = R.cylinder_region(s, R.wall_thickness(m, s) + R.OVERSHOOT_MM, margin_mm=5)
            regs.append(("wall r%d" % r, reg, 25))
        with tempfile.TemporaryDirectory() as d:
            g = slice_3mf(write_prusa(m, regs), d)
            types, dirs = H.gcode_types(g, (125, 105), [30.0, 58.0])
        inside = types[30.0]
        for (typ, band), n in inside.items():
            if band in (27, 28, 29, 9, 10, 11):                       # the wall bands, middle of the part
                self.assertEqual(typ, "Internal infill", (typ, band))
        self.assertGreater(sum(n for (t, b), n in inside.items() if b in (27, 28, 29)), 100)
        self.assertGreater(len(dirs[30.0]), 12, "infill directions: straight rectilinear would give 2")
        above = types[58.0]                                            # above the 5 mm rim: normal walls
        self.assertTrue(any(t == "External perimeter" for (t, b) in above))

    def test_flat_window_in_a_plate(self):
        plate = H.box_mesh(60, 60, 6, "plate"); topo = R.Topology(plate)
        t = H.find_tri(plate, lambda c, n: abs(c[2] - 6) < 1e-6 and n[2] > .9)
        s = R.pick(plate, topo, t)
        reg, _ = R.plane_region(plate, s, 6 + R.OVERSHOOT_MM, {"shape": "ellipse", "margin_mm": 15})
        with tempfile.TemporaryDirectory() as d:
            g = slice_3mf(write_prusa(plate, [("window", reg, 30)], bed_xy=(100, 100)), d)
            types, dirs = H.gcode_types(g, (100, 100), [3.0])
        c = types[3.0]
        inner = {t for (t, b), n in c.items() if b < 14}                  # radius < 14 mm: inside the 15 mm-margin oval
        outer = {t for (t, b), n in c.items() if b >= 25}                 # well outside the window
        self.assertEqual(inner, {"Internal infill"})
        self.assertIn("External perimeter", outer | {t for (t, b), n in c.items() if b >= 28})


if __name__ == "__main__":
    unittest.main()
