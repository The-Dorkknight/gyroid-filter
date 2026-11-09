# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
import http.client, io, json, math, threading, unittest, zipfile
import helpers as H
from gyroid_filter import server


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = server.State(); cls.token = "tok"
        cls.srv = server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: None)
        cls.srv.RequestHandlerClass = server.make_handler(cls.state, cls.token, cls.srv.server_address[1])
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.port = cls.srv.server_address[1]
        cls.conn = http.client.HTTPConnection("127.0.0.1", cls.port)      # ONE keep-alive connection, like a browser

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.conn.close()

    def call(self, path, body=None, headers=None, raw=False):
        h = {"X-Token": self.token}; h.update(headers or {})
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        self.conn.request("POST" if data is not None else "GET", path, body=data, headers=h)
        r = self.conn.getresponse(); b = r.read()
        return r.status, (b if raw else json.loads(b))

    def test_full_flow_on_one_keepalive_connection(self):
        st, r = self.call("/api/example", {}); self.assertEqual(st, 200); self.assertEqual(r["triangles"], 1536)
        m = self.state.mesh
        t = H.find_tri(m, lambda c, n: abs(math.hypot(c[0], c[1]) - 30) < .2 and abs(n[2]) < .1)
        st, s = self.call("/api/select", {"tri": t, "mode": "auto"}); self.assertEqual(s["info"]["kind"], "cylinder")
        st, e = self.call("/api/select", {"tri": t, "mode": "plane"}); self.assertEqual(e["info"]["kind"], "plane")
        st, e = self.call("/api/select", {"tri": 0, "mode": "cylinder"})            # flat floor: no cylinder there
        self.assertEqual(st, 400)
        p = {"depth_mode": "through", "density": 25, "margin_mm": 3}
        st, pv = self.call("/api/preview", {"sel_id": s["sel_id"], "params": p}); self.assertTrue(pv["stats"]["closed"])
        st, a = self.call("/api/add", {"sel_id": s["sel_id"], "params": p}); self.assertEqual(st, 200)
        for fl, ext in (("prusa", "3mf"), ("orca", "3mf"), ("stl", "zip")):
            st, d = self.call("/api/export?flavor=%s" % fl, raw=True); self.assertEqual(st, 200)
            self.assertTrue(zipfile.is_zipfile(io.BytesIO(d)), fl)
        names = zipfile.ZipFile(io.BytesIO(d)).namelist()
        self.assertIn("cartridge-region-1.stl", names)
        st, _ = self.call("/api/remove", {"id": a["id"]}); self.assertEqual(st, 200)
        st, e = self.call("/api/export?flavor=prusa", raw=True); self.assertEqual(st, 400)   # nothing left to export

    def test_security_checks(self):
        st, _ = self.call("/api/regions", headers={"X-Token": "wrong"}); self.assertEqual(st, 403)
        st, _ = self.call("/api/regions", headers={"Host": "evil.example"}); self.assertEqual(st, 403)
        st, _ = self.call("/vendor/../server.py"); self.assertEqual(st, 404)

    def test_open_a_model_first_and_bad_files(self):
        s2 = server.State()
        self.assertIsNone(s2.mesh)
        st, e = self.call("/api/load?name=bad.stl", b"not an stl"); self.assertEqual(st, 400)
        stl = open(H.os.path.join(H.ROOT, "examples", "cartridge.stl"), "rb").read()
        st, r = self.call("/api/load?name=c.stl", stl); self.assertEqual((st, r["triangles"]), (200, 1536))

    def test_cura_status_lists_nothing_when_cura_is_absent(self):
        st, r = self.call("/api/cura/status"); self.assertEqual(st, 200); self.assertTrue(r["source_found"])


if __name__ == "__main__":
    unittest.main()
