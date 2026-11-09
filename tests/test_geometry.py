# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
import math, unittest
import helpers as H
from gyroid_filter import regions as R
from gyroid_filter.mesh import load_stl, save_stl, load_3mf
from gyroid_filter.export3mf import write_prusa, write_orca
import tempfile, os


class Geometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = H.cartridge_mesh(); cls.topo = R.Topology(cls.m)

    def pick_cyl(self, r, zmin=-1, conc=None):
        t = H.find_tri(self.m, lambda c, n: abs(math.hypot(c[0], c[1]) - r) < .2 and abs(n[2]) < .1 and c[2] > zmin)
        return R.pick(self.m, self.topo, t)

    def test_four_cylinders_detected_with_correct_side(self):
        for r, concave in ((30, False), (27, True), (12, False), (9, True)):
            s = self.pick_cyl(r, 10)
            self.assertEqual(s["kind"], "cylinder", r)
            self.assertAlmostEqual(s["radius"], r, delta=0.05)
            self.assertEqual(s["concave"], concave, r)
            self.assertIsNone(s["arc"])

    def test_wall_thickness_is_3mm_for_all_four(self):
        for r in (30, 27, 12, 9):
            self.assertAlmostEqual(R.wall_thickness(self.m, self.pick_cyl(r, 10)), 3.0, delta=0.02)

    def test_flat_face_is_a_plane(self):
        t = H.find_tri(self.m, lambda c, n: abs(c[2] - 3) < .01 and n[2] > .9)
        s = R.pick(self.m, self.topo, t)
        self.assertEqual(s["kind"], "plane"); self.assertAlmostEqual(R.wall_thickness(self.m, s), 3.0, delta=0.02)

    def test_cylinder_region_is_closed_and_has_the_right_volume(self):
        s = self.pick_cyl(30, 10)
        reg, info = R.cylinder_region(s, 3.3)
        self.assertEqual(R.open_edges(reg), 0)
        want = math.pi * ((30.3) ** 2 - (26.7) ** 2) * 60
        self.assertAlmostEqual(R.signed_volume(reg) / want, 1.0, delta=0.01)

    def test_axial_window_and_margin(self):
        s = self.pick_cyl(30, 10)
        reg, info = R.cylinder_region(s, 3.3, axial=(0.0, 1.0), margin_mm=5.0)
        self.assertAlmostEqual(info["t0"], 5.0, 3); self.assertAlmostEqual(info["t1"], 55.0, 3)
        with self.assertRaises(ValueError):
            R.cylinder_region(s, 3.3, margin_mm=40)

    def test_partial_arc_cylinder(self):
        # half pipe: keep only the upper half of the outer wall
        tris = []
        for k in range(48):
            a0, a1 = math.pi * k / 48, math.pi * (k + 1) / 48
            P = lambda r, a, z: (r * math.cos(a), r * math.sin(a), z)
            for r, flip in ((10, False), (7, True)):
                q = [P(r, a0, 0), P(r, a1, 0), P(r, a1, 20), P(r, a0, 20)]
                t = [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
                tris += [(b, a, c) for a, b, c in t] if flip else t
        m = H.weld(tris, "half"); topo = R.Topology(m)
        s = R.pick(m, topo, 10, "cylinder")
        self.assertEqual(s["kind"], "cylinder"); self.assertIsNotNone(s["arc"])
        self.assertAlmostEqual(math.degrees(s["arc"][1] - s["arc"][0]), 180, delta=4)
        reg, _ = R.cylinder_region(s, 3.3)
        self.assertEqual(R.open_edges(reg), 0); self.assertGreater(R.signed_volume(reg), 0)

    def test_plane_region_whole_window_ellipse_and_errors(self):
        b = H.box_mesh(60, 40, 10); topo = R.Topology(b)
        t = H.find_tri(b, lambda c, n: abs(c[2] - 10) < 1e-6 and n[2] > .9)
        s = R.pick(b, topo, t); self.assertEqual(s["kind"], "plane"); self.assertEqual(len(s["tris"]), 2)
        reg, _ = R.plane_region(b, s, 4.0)
        self.assertEqual(R.open_edges(reg), 0)
        self.assertAlmostEqual(R.signed_volume(reg), 60 * 40 * (4.0 + R.OVERSHOOT_MM), delta=1)
        reg, _ = R.plane_region(b, s, 4.0, {"shape": "rect", "margin_mm": 5})
        self.assertAlmostEqual(R.signed_volume(reg), 50 * 30 * (4.0 + R.OVERSHOOT_MM), delta=1)
        reg, _ = R.plane_region(b, s, 4.0, {"shape": "ellipse", "margin_mm": 0})
        v = R.signed_volume(reg) / (4.0 + R.OVERSHOOT_MM)
        self.assertAlmostEqual(v / (math.pi * 30 * 20), 1.0, delta=0.03)
        self.assertEqual(R.open_edges(reg), 0)
        reg, _ = R.plane_region(b, s, 4.0, {"u0": 0.0, "u1": 0.5})
        self.assertAlmostEqual(R.signed_volume(reg) / (30 * 40 * (4.3)), 1.0, delta=0.01)
        with self.assertRaises(ValueError):
            R.plane_region(b, s, 4.0, {"margin_mm": 30})

    def test_finely_tessellated_cylinder_is_still_a_cylinder(self):
        from make_example import revolve
        m = revolve([(9, 0), (30, 0), (30, 60), (27, 60), (27, 3), (12, 3), (12, 60), (9, 60)], 1500)   # 0.24 deg facets
        topo = R.Topology(m)
        t = H.find_tri(m, lambda c, n: abs(math.hypot(c[0], c[1]) - 30) < .2 and abs(n[2]) < .1)
        s = R.pick(m, topo, t)
        self.assertEqual(s["kind"], "cylinder"); self.assertAlmostEqual(s["radius"], 30, delta=0.05)
        self.assertEqual(len(s["tris"]), 3000)
        with self.assertRaises(ValueError):
            R.pick(H.box_mesh(10, 10, 10), R.Topology(H.box_mesh(10, 10, 10)), 0, "cylinder")

    def test_flat_face_not_mistaken_for_cylinder_in_auto(self):
        b = H.box_mesh(20, 20, 20); topo = R.Topology(b)
        for t in range(len(b.tris)):
            self.assertEqual(R.pick(b, topo, t)["kind"], "plane")


class Files(unittest.TestCase):
    def test_stl_roundtrip_and_3mf_reload(self):
        b = H.box_mesh(10, 20, 30, "b")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "b.stl"); save_stl(b, p)
            with open(p, "rb") as f:
                b2 = load_stl(f.read(), "b")
            self.assertEqual((len(b2.verts), len(b2.tris)), (8, 12))
        reg = H.box_mesh(5, 5, 5, "r")
        data = write_prusa(b, [("r1", reg, 25)])
        self.assertEqual(len(load_3mf(data).tris), 12 + 12)    # geometry only: modifiers are merged on reload

    def test_ascii_stl(self):
        txt = b"solid t\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid"
        self.assertEqual(len(load_stl(txt).tris), 1)


if __name__ == "__main__":
    unittest.main()
