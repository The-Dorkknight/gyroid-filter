# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
import collections, math, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from gyroid_filter.mesh import Mesh, weld, load_stl  # noqa: E402


def cartridge_mesh():
    with open(os.path.join(ROOT, "examples", "cartridge.stl"), "rb") as f:
        return load_stl(f.read(), "cartridge")


def box_mesh(sx, sy, sz, name="box"):
    x, y, z = sx / 2, sy / 2, sz
    p = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = []
    for a, b, c, d in quads:
        tris += [(p[a], p[b], p[c]), (p[a], p[c], p[d])]
    return weld(tris, name)


def find_tri(mesh, pred):
    return next(t for t in range(len(mesh.tris)) if pred(mesh.tri_centroid(t), mesh.normals[t]))


def gcode_types(path, center, z_targets, tol=0.11):
    """{z: Counter((type, 1mm radial band))} of extruding moves around `center` (x, y)."""
    typ, z, x, y, e = None, 0.0, 0.0, 0.0, 0.0
    rel = False
    out = collections.defaultdict(collections.Counter)
    dirs = collections.defaultdict(set)
    for line in open(path):
        if line.startswith(";TYPE:"):
            typ = line[6:].strip(); continue
        if line.startswith("M83"): rel = True
        if line.startswith(("G1", "G0")):
            m = dict((w[0], float(w[1:])) for w in line.split(";")[0].split()[1:] if re.match(r"[XYZE]-?[\d.]+$", w))
            nx, ny = m.get("X", x), m.get("Y", y)
            if "Z" in m: z = m["Z"]
            ext = (m.get("E", 0) > 0) if rel else (m.get("E", e) > e)
            if "E" in m and not rel: e = m["E"]
            if ext and typ:
                for zt in z_targets:
                    if abs(z - zt) < tol:
                        r = math.hypot((x + nx) / 2 - center[0], (y + ny) / 2 - center[1])
                        out[zt][(typ, int(r))] += 1
                        if typ == "Internal infill":
                            dirs[zt].add(round(math.degrees(math.atan2(ny - y, nx - x)) % 180))
            x, y = nx, ny
    return out, dirs
