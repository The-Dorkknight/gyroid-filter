# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
import io, unittest, zipfile
import xml.etree.ElementTree as ET
import helpers as H
from gyroid_filter.export3mf import write_prusa, write_orca
from gyroid_filter import settings


class Export(unittest.TestCase):
    def setUp(self):
        self.body = H.box_mesh(40, 40, 10, "body")
        self.r1, self.r2 = H.box_mesh(10, 10, 5, "r1"), H.box_mesh(8, 8, 4, "r2")
        self.regs = [("Open cell 1", self.r1, 25), ("Open cell 2 & more", self.r2, 40)]

    def test_prusa_layout(self):
        z = zipfile.ZipFile(io.BytesIO(write_prusa(self.body, self.regs)))
        self.assertIn("Metadata/Slic3r_PE_model.config", z.namelist())
        model = ET.fromstring(z.read("3D/3dmodel.model"))
        ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
        tris = model.findall(".//m:triangle", ns)
        self.assertEqual(len(tris), 12 * 3)
        cfg = ET.fromstring(z.read("Metadata/Slic3r_PE_model.config"))
        vols = cfg.findall(".//volume")
        self.assertEqual([(v.get("firstid"), v.get("lastid")) for v in vols], [("0", "11"), ("12", "23"), ("24", "35")])
        kinds = [[m.get("value") for m in v if m.get("key") == "volume_type"][0] for v in vols]
        self.assertEqual(kinds, ["ModelPart", "ParameterModifier", "ParameterModifier"])
        kv = {m.get("key"): m.get("value") for m in vols[2] if m.get("type") == "volume"}
        self.assertEqual(kv["fill_pattern"], "gyroid"); self.assertEqual(kv["fill_density"], "40%"); self.assertEqual(kv["perimeters"], "0")
        self.assertEqual(vols[2].find("metadata[@key='name']").get("value"), "Open cell 2 & more")

    def test_orca_layout(self):
        z = zipfile.ZipFile(io.BytesIO(write_orca(self.body, self.regs)))
        model = ET.fromstring(z.read("3D/3dmodel.model"))
        ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
        objs = model.findall(".//m:resources/m:object", ns)
        self.assertEqual(len(objs), 4)                              # 3 volumes + 1 assembly
        self.assertEqual(len(objs[3].findall(".//m:component", ns)), 3)
        self.assertEqual(model.find(".//m:item", ns).get("objectid"), "4")
        cfg = ET.fromstring(z.read("Metadata/model_settings.config"))
        parts = cfg.findall(".//part")
        self.assertEqual([p.get("subtype") for p in parts], ["normal_part", "modifier_part", "modifier_part"])
        kv = {m.get("key"): m.get("value") for m in parts[1]}
        self.assertEqual(kv["sparse_infill_pattern"], "gyroid"); self.assertEqual(kv["sparse_infill_density"], "25%")
        self.assertEqual(kv["wall_loops"], "0"); self.assertEqual(kv["top_shell_layers"], "0")

    def test_placement_puts_part_on_bed_centre(self):
        z = zipfile.ZipFile(io.BytesIO(write_prusa(self.body, self.regs, bed_xy=(100, 90))))
        item = ET.fromstring(z.read("3D/3dmodel.model")).find(".//{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}item")
        self.assertEqual(item.get("transform"), "1 0 0 0 1 0 0 0 1 100.00000 90.00000 0.00000")

    def test_density_is_clamped(self):
        self.assertEqual(settings.clamp_density(1), 5); self.assertEqual(settings.clamp_density(99), 60)
        self.assertEqual(dict(settings.prusa_config(99))["fill_density"], "60%")
        c = settings.cura_settings(10)
        self.assertTrue(c["cutting_mesh"]); self.assertEqual(c["infill_pattern"], "gyroid"); self.assertEqual(c["wall_line_count"], 0)


if __name__ == "__main__":
    unittest.main()
