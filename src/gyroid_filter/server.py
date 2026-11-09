# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Local web app (stdlib only).  Listens on 127.0.0.1 with a random port and a per-run token."""
import base64
import hashlib
import io
import json
import os
import platform
import re
import secrets
import shutil
import struct
import sys
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import __version__, __build_date__, __app_name__
from . import regions as R
from .export3mf import write_prusa, write_orca
from .mesh import load_mesh, save_stl, Mesh
from .settings import clamp_density, DEFAULT_DENSITY_PCT

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
STATIC = {"/app.js": "text/javascript", "/style.css": "text/css",
          "/vendor/three-bundle.js": "text/javascript", "/vendor/THREE-LICENSE.txt": "text/plain",
          "/favicon.svg": "image/svg+xml"}
BYTES_PER_TRIANGLE = 900            # measured: about 810 bytes per triangle in CPython (200k triangles = 200 MB)
IDLE_SECONDS = 120                  # no browser ping for this long => exit (nothing is left running)


def free_ram_bytes():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return 2 * 1024 ** 3            # unknown (Windows/Mac): assume a small machine


def b64f32(floats):
    return base64.b64encode(struct.pack("<%df" % len(floats), *floats)).decode("ascii")


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.mesh = None
        self.topo = None
        self.sels = {}
        self.regions = []           # dicts: id,label,mesh,density,summary
        self.next_id = 1
        self.last_ping = time.time()
        self.pinged = False

    def reset(self, mesh):
        self.mesh, self.sels, self.regions, self.next_id = mesh, {}, [], 1
        self.topo = R.Topology(mesh)


def sel_info(sel):
    out = {"kind": sel["kind"], "triangles": len(sel["tris"])}
    if sel["kind"] == "cylinder":
        out.update(radius=round(sel["radius"], 3), length=round(sel["t1"] - sel["t0"], 3),
                   concave=sel["concave"], partial_arc=sel["arc"] is not None,
                   arc_deg=None if sel["arc"] is None else round((sel["arc"][1] - sel["arc"][0]) * 57.29578, 1))
    return out


def build_region(state, sel, p):
    mesh = state.mesh
    density = clamp_density(p.get("density", DEFAULT_DENSITY_PCT))
    th = R.wall_thickness(mesh, sel) if p.get("depth_mode", "through") == "through" else None
    if p.get("depth_mode", "through") == "through":
        if th is None:
            raise ValueError("Could not measure the wall thickness here; switch to a fixed depth.")
        depth = th + R.OVERSHOOT_MM
    else:
        depth = max(0.2, float(p.get("depth_mm", 3.0)))
    margin = max(0.0, float(p.get("margin_mm", 0.0)))
    if sel["kind"] == "plane":
        w = p.get("window") or {}
        window = None
        if margin > 0 or w.get("shape") == "ellipse" or any(k in w for k in ("u0", "u1", "v0", "v1")):
            window = {"shape": w.get("shape", "rect"), "margin_mm": margin,
                      "u0": w.get("u0", 0.0), "u1": w.get("u1", 1.0), "v0": w.get("v0", 0.0), "v1": w.get("v1", 1.0)}
        region, info = R.plane_region(mesh, sel, depth, window)
    else:
        ax = p.get("axial") or [0.0, 1.0]
        arc = p.get("arc")
        region, info = R.cylinder_region(sel, depth, (float(ax[0]), float(ax[1])),
                                         None if not arc else (float(arc[0]), float(arc[1])), margin)
    stats = {"triangles": len(region.tris), "closed": R.open_edges(region) == 0,
             "volume_mm3": round(abs(R.signed_volume(region)), 1), "depth_mm": round(depth, 2),
             "wall_mm": None if th is None else round(th, 2), "density": density}
    return region, stats


def cura_roots():
    home = os.path.expanduser("~")
    sysname = platform.system()
    if sysname == "Windows":
        return [os.path.join(os.environ.get("APPDATA", home), "cura")]
    if sysname == "Darwin":
        return [os.path.join(home, "Library", "Application Support", "cura")]
    return [os.path.join(home, ".local", "share", "cura"),
            os.path.join(home, ".var", "app", "com.ultimaker.cura", "data", "cura")]


def plugin_source():
    here = os.path.dirname(os.path.abspath(__file__))
    for base in (os.path.join(here, "..", "..", "cura_plugin"), os.path.join(here, "cura_plugin")):
        p = os.path.normpath(os.path.join(base, "GyroidFilter"))
        if os.path.isdir(p):
            return p
    return None


def _tree_hashes(root):
    out = {}
    for d, _, files in os.walk(root):
        if "__pycache__" in d:
            continue
        for f in files:
            if f.endswith(".pyc"):
                continue
            full = os.path.join(d, f)
            out[os.path.relpath(full, root).replace("\\", "/")] = hashlib.sha256(open(full, "rb").read()).hexdigest()
    return out


PLUGIN_ID = "GyroidFilter"
PLUGIN_VERSION = "0.1.0"


def _plugin_dirs(cfg):
    """Cura's own package layout is plugins/<ID>/<ID>/. The old flat layout plugins/<ID>/ is detected so it can be migrated."""
    outer = os.path.join(cfg, "plugins", PLUGIN_ID)
    return outer, os.path.join(outer, PLUGIN_ID)


def _read_packages(cfg):
    """packages.json as a dict, {} if absent. Raises ValueError if it exists but cannot be read: never overwrite it then,
    because it holds Cura's record of every other installed plug-in."""
    path = os.path.join(cfg, "packages.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError("Cura's packages.json exists but cannot be read (%s). I left it alone; nothing was installed." % e)
    if not isinstance(data, dict):
        raise ValueError("Cura's packages.json is not what I expected. I left it alone; nothing was installed.")
    return data


def _write_packages(cfg, data):
    path = os.path.join(cfg, "packages.json")
    if os.path.exists(path):
        shutil.copy2(path, path + ".gyroid-backup")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp, path)


def _registered(cfg):
    try:
        return PLUGIN_ID in (_read_packages(cfg).get("installed") or {})
    except ValueError:
        return False


def cura_log_state(cfg):
    """What cura.log proves. 'loaded' needs our self-test line and no crash text after it; it can NOT prove Cura stayed up."""
    line, crash = "", ""
    seen = False
    try:
        with open(os.path.join(cfg, "cura.log"), "r", errors="replace") as f:
            for ln in f:
                if "GyroidFilter" in ln:
                    line = ln.strip()[-200:]
                    if "self-test PASS" in ln:
                        seen, crash = True, ""
                if seen and re.search(r"Traceback|Segmentation|Fatal|CRITICAL|core dumped", ln):
                    crash = ln.strip()[-200:]
    except OSError:
        pass
    state = "never" if not line else ("crashed" if crash else ("loaded" if seen else "failed"))
    return {"state": state, "line": line, "crash": crash}


def cura_status():
    src = plugin_source()
    want = _tree_hashes(src) if src else {}
    found = []
    for root in cura_roots():
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if not re.match(r"^\d+\.\d+", name) or not os.path.isdir(os.path.join(root, name)):
                continue
            cfg = os.path.join(root, name)
            outer, dest = _plugin_dirs(cfg)
            installed = os.path.isdir(dest)
            flat_old = os.path.isfile(os.path.join(outer, "plugin.json"))     # old flat copy: not in Manage
            in_sync = installed and _tree_hashes(dest) == want
            lg = cura_log_state(cfg)
            found.append({"config_dir": cfg, "version": name, "installed": installed or flat_old, "old_layout": flat_old,
                          "registered": _registered(cfg), "in_sync": in_sync, "log_state": lg["state"],
                          "loaded_in_last_run": lg["state"] == "loaded", "log_line": lg["crash"] or lg["line"]})
    return {"source_found": src is not None, "copies": found, "roots": cura_roots()}


def cura_install(config_dir):
    src = plugin_source()
    if not src:
        raise ValueError("Plug-in source folder not found next to the app.")
    allowed = [c["config_dir"] for c in cura_status()["copies"]]
    if config_dir not in allowed:
        raise ValueError("Not a Cura folder I know about.")
    data = _read_packages(config_dir)            # raises before anything is touched if it is unreadable
    outer, dest = _plugin_dirs(config_dir)
    if os.path.isdir(outer):
        shutil.rmtree(outer)                     # also removes an old flat copy
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    ok = _tree_hashes(dest) == _tree_hashes(src)       # read back, do not trust the copy
    data.setdefault("installed", {})[PLUGIN_ID] = {
        "package_info": {"package_id": PLUGIN_ID, "package_type": "plugin", "display_name": "Gyroid Filter",
                         "description": "Make a picked face or cylinder open-cell gyroid for fillable carbon filters.",
                         "package_version": PLUGIN_VERSION, "sdk_version": 8, "sdk_version_semver": "8.0.0",
                         "author": {"author_id": "The-Dorkknight", "display_name": "Matthew Armstrong"}},
        "location": outer, "is_bundled": False}
    if isinstance(data.get("to_install"), dict):
        data["to_install"].pop(PLUGIN_ID, None)
    if isinstance(data.get("to_remove"), list):
        data["to_remove"] = [x for x in data["to_remove"] if x != PLUGIN_ID]
    _write_packages(config_dir, data)
    return {"installed": True, "verified": ok, "registered": _registered(config_dir), "dest": dest}


def cura_uninstall(config_dir):
    allowed = [c["config_dir"] for c in cura_status()["copies"]]
    if config_dir not in allowed:
        raise ValueError("Not a Cura folder I know about.")
    data = _read_packages(config_dir)
    outer, _ = _plugin_dirs(config_dir)
    if os.path.isdir(outer):
        shutil.rmtree(outer)
    if isinstance(data.get("installed"), dict) and PLUGIN_ID in data["installed"]:
        del data["installed"][PLUGIN_ID]
        _write_packages(config_dir, data)
    return {"removed": True}


def make_handler(state, token, port):
    class H(BaseHTTPRequestHandler):
        server_version = "GyroidFilter/" + __version__
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *a):
            if os.environ.get("GYROID_DEBUG"):
                sys.stderr.write("[http] " + fmt % a + "\n")

        # -- helpers
        def _ok_host(self):
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def _send(self, code, body, ctype="application/json", extra=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _authed(self, q):
            return secrets.compare_digest(self.headers.get("X-Token", q.get("t", [""])[0]), token)

        def _json_body(self):
            return json.loads(self.raw or b"{}")

        # -- verbs
        def do_GET(self):
            if not self._ok_host():
                return self._send(403, {"error": "bad host"})
            u = urlparse(self.path); q = parse_qs(u.query)
            if u.path in ("/", "/index.html"):
                html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
                html = (html.replace("__TOKEN__", token).replace("__VERSION__", __version__)
                        .replace("__BUILD__", __build_date__))
                return self._send(200, html, "text/html; charset=utf-8")
            if u.path in STATIC:
                return self._send(200, open(os.path.join(WEB, u.path.lstrip("/")), "rb").read(), STATIC[u.path])
            if not u.path.startswith("/api/"):
                return self._send(404, {"error": "not found"})
            if not self._authed(q):
                return self._send(403, {"error": "bad token"})
            try:
                with state.lock:
                    return self._api_get(u.path, q)
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            except Exception as e:  # pragma: no cover
                return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

        def do_POST(self):
            if not self._ok_host():
                return self._send(403, {"error": "bad host"})
            u = urlparse(self.path); q = parse_qs(u.query)
            n = int(self.headers.get("Content-Length") or 0)
            self.raw = self.rfile.read(n) if n else b""        # always drain the body (keep-alive!)
            if not self._authed(q):
                return self._send(403, {"error": "bad token"})
            try:
                with state.lock:
                    return self._api_post(u.path, q)
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            except Exception as e:  # pragma: no cover
                return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

        # -- API
        def _api_get(self, path, q):
            if path == "/api/ping":
                state.last_ping, state.pinged = time.time(), True
                return self._send(200, {"ok": True})
            if path == "/api/quit":
                self._send(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if path == "/api/regions":
                return self._send(200, self._regions_json())
            if path == "/api/cura/status":
                return self._send(200, cura_status())
            if path == "/api/export":
                return self._export(q)
            return self._send(404, {"error": "unknown api"})

        def _regions_json(self):
            return [{"id": r["id"], "label": r["label"], "density": r["density"], "stats": r["stats"],
                     "soup": b64f32(r["mesh"].soup())} for r in state.regions]

        def _api_post(self, path, q):
            if path == "/api/load":
                data = self.raw
                name = q.get("name", ["model.stl"])[0]
                t0 = time.time()
                mesh = load_mesh(data, name)
                need = len(mesh.tris) * BYTES_PER_TRIANGLE
                have = free_ram_bytes()
                if need > have * 0.6:
                    raise ValueError("This model has %d triangles and needs about %d MB; only about %d MB is free. "
                                     "Reduce the triangle count first (e.g. decimate in Blender/MeshLab) and try again."
                                     % (len(mesh.tris), need // 2 ** 20, have // 2 ** 20))
                state.reset(mesh)
                lo, hi = mesh.bbox()
                return self._send(200, {"name": mesh.name, "triangles": len(mesh.tris), "bbox": [lo, hi],
                                        "soup": b64f32(mesh.soup()), "seconds": round(time.time() - t0, 2)})
            if path == "/api/example":
                root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "examples", "cartridge.stl"))
                if not os.path.exists(root):
                    raise ValueError("Example file not found next to the app.")
                mesh = load_mesh(open(root, "rb").read(), "cartridge.stl")
                state.reset(mesh)
                lo, hi = mesh.bbox()
                return self._send(200, {"name": mesh.name, "triangles": len(mesh.tris), "bbox": [lo, hi],
                                        "soup": b64f32(mesh.soup()), "seconds": 0})
            if state.mesh is None:
                raise ValueError("Open a model first.")
            body = self._json_body()
            if path == "/api/select":
                tri = int(body["tri"])
                if not 0 <= tri < len(state.mesh.tris):
                    raise ValueError("Triangle out of range")
                t0 = time.time()
                sel = R.pick(state.mesh, state.topo, tri, body.get("mode", "auto"))
                sid = state.next_id; state.next_id += 1
                state.sels[sid] = sel
                th = R.wall_thickness(state.mesh, sel)
                if sel["kind"] == "plane":
                    u, v, _ = R.plane_frame(sel["normal"])
                    ext = None
                else:
                    ext = None
                info = sel_info(sel)
                info["wall_mm"] = None if th is None else round(th, 2)
                return self._send(200, {"sel_id": sid, "tris": sel["tris"], "info": info,
                                        "seconds": round(time.time() - t0, 2)})
            if path in ("/api/preview", "/api/add"):
                sel = state.sels.get(int(body["sel_id"]))
                if sel is None:
                    raise ValueError("Pick a face or cylinder first.")
                region, stats = build_region(state, sel, body.get("params", {}))
                out = {"stats": stats, "soup": b64f32(region.soup())}
                if path == "/api/add":
                    rid = state.next_id; state.next_id += 1
                    n = len(state.regions) + 1
                    what = ("flat face" if sel["kind"] == "plane" else
                            ("hole r%.1f" % sel["radius"] if sel["concave"] else "cylinder r%.1f" % sel["radius"]))
                    label = "Open cell %d (%s)" % (n, what)
                    state.regions.append({"id": rid, "label": label, "mesh": region,
                                          "density": stats["density"], "stats": stats})
                    out["id"], out["label"] = rid, label
                return self._send(200, out)
            if path == "/api/remove":
                state.regions = [r for r in state.regions if r["id"] != int(body["id"])]
                return self._send(200, {"ok": True})
            if path == "/api/cura/install":
                return self._send(200, cura_install(body["config_dir"]))
            if path == "/api/cura/uninstall":
                return self._send(200, cura_uninstall(body["config_dir"]))
            return self._send(404, {"error": "unknown api"})

        def _export(self, q):
            if state.mesh is None or not state.regions:
                raise ValueError("Add at least one open-cell region first.")
            flavor = q.get("flavor", ["prusa"])[0]
            regs = [(r["label"], r["mesh"], r["density"]) for r in state.regions]
            base = state.mesh.name
            if flavor == "stl":
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp.stl")
                    try:
                        save_stl(state.mesh, tmp); z.write(tmp, base + ".stl")
                        for i, (label, m, dens) in enumerate(regs, 1):
                            save_stl(m, tmp); z.write(tmp, "%s-region-%d.stl" % (base, i))
                    finally:
                        if os.path.exists(tmp): os.remove(tmp)
                    z.writestr("README.txt", "Add each -region- file to your slicer as a MODIFIER, then set: "
                               "infill pattern gyroid, infill density %s%%, walls 0, top and bottom layers 0.\n"
                               "Densities: %s\n" % (regs[0][2], ", ".join("%s%%" % d for _, _, d in regs)))
                data, name, ctype = buf.getvalue(), base + "-regions.zip", "application/zip"
            else:
                bx = float(q.get("bed_x", ["125" if flavor == "prusa" else "128"])[0])
                by = float(q.get("bed_y", ["105" if flavor == "prusa" else "128"])[0])
                if flavor == "orca":
                    data = write_orca(state.mesh, regs, (bx, by)); name = base + "-opencell-orca.3mf"
                else:
                    data = write_prusa(state.mesh, regs, (bx, by)); name = base + "-opencell-prusa.3mf"
                ctype = "model/3mf"
            return self._send(200, data, ctype, {"Content-Disposition": 'attachment; filename="%s"' % name})

    return H


def serve(open_browser=True, port=0, preload=None, quiet=False):
    state = State()
    token = secrets.token_urlsafe(16)
    srv = ThreadingHTTPServer(("127.0.0.1", port), lambda *a, **k: None)
    real_port = srv.server_address[1]
    srv.RequestHandlerClass = make_handler(state, token, real_port)
    url = "http://127.0.0.1:%d/" % real_port
    if preload:
        state.reset(load_mesh(open(preload, "rb").read(), preload))
    if not quiet:
        print("%s %s (built %s)" % (__app_name__, __version__, __build_date__))
        print("Open this address in your browser if it does not open by itself:\n  " + url)
        print("Leave this window open while you work. Close the browser tab (or press Ctrl+C here) to stop.")
    if open_browser:
        import webbrowser
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    def watchdog():
        while True:
            time.sleep(5)
            if state.pinged and time.time() - state.last_ping > IDLE_SECONDS:
                if not quiet:
                    print("Browser tab closed; shutting down.")
                srv.shutdown()
                return
    threading.Thread(target=watchdog, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0
