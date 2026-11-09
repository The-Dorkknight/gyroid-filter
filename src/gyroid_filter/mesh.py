# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Tiny pure-Python triangle mesh: STL / 3MF loading, welding, vector helpers."""
import math
import re
import struct
import zipfile
import xml.etree.ElementTree as ET


def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def length(a): return math.sqrt(dot(a, a))
def unit(a):
    l = length(a)
    return (a[0] / l, a[1] / l, a[2] / l) if l > 1e-15 else (0.0, 0.0, 0.0)


class Mesh:
    """verts: list of (x,y,z); tris: list of (a,b,c) vertex indices."""

    def __init__(self, verts, tris, name="part"):
        self.verts = verts
        self.tris = tris
        self.name = name
        self._normals = None
        self._areas = None

    def _compute(self):
        n, a = [], []
        v = self.verts
        for (i, j, k) in self.tris:
            c = cross(sub(v[j], v[i]), sub(v[k], v[i]))
            l = length(c)
            a.append(l / 2.0)
            n.append((c[0] / l, c[1] / l, c[2] / l) if l > 1e-15 else (0.0, 0.0, 0.0))
        self._normals, self._areas = n, a

    @property
    def normals(self):
        if self._normals is None:
            self._compute()
        return self._normals

    @property
    def areas(self):
        if self._areas is None:
            self._compute()
        return self._areas

    def bbox(self):
        xs = [p[0] for p in self.verts]; ys = [p[1] for p in self.verts]; zs = [p[2] for p in self.verts]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def tri_centroid(self, t):
        a, b, c = (self.verts[i] for i in self.tris[t])
        return ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3, (a[2] + b[2] + c[2]) / 3)

    def soup(self):
        """Flat list of floats, 9 per triangle (for the web viewer)."""
        out = []
        for (i, j, k) in self.tris:
            out.extend(self.verts[i]); out.extend(self.verts[j]); out.extend(self.verts[k])
        return out


def weld(triangles, name="part", digits=4):
    """triangles: iterable of three (x,y,z) points. Merges equal vertices, drops degenerates."""
    index, verts, tris = {}, [], []
    q = 10 ** digits
    for tri in triangles:
        ids = []
        for p in tri:
            key = (round(p[0] * q), round(p[1] * q), round(p[2] * q))
            i = index.get(key)
            if i is None:
                i = len(verts); index[key] = i
                verts.append((key[0] / q, key[1] / q, key[2] / q))
            ids.append(i)
        if ids[0] != ids[1] and ids[1] != ids[2] and ids[0] != ids[2]:
            tris.append(tuple(ids))
    return Mesh(verts, tris, name)


def load_stl(data, name="part"):
    if len(data) >= 84:
        n = struct.unpack_from("<I", data, 80)[0]
        if 84 + 50 * n == len(data):
            tris = []
            for i in range(n):
                f = struct.unpack_from("<12f", data, 84 + 50 * i)
                tris.append(((f[3], f[4], f[5]), (f[6], f[7], f[8]), (f[9], f[10], f[11])))
            return weld(tris, name)
    text = data.decode("utf-8", "replace")
    pts = re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", text)
    if not pts or len(pts) % 3:
        raise ValueError("Not a readable STL file")
    pts = [(float(a), float(b), float(c)) for a, b, c in pts]
    return weld([(pts[i], pts[i + 1], pts[i + 2]) for i in range(0, len(pts), 3)], name)


def save_stl(mesh, path):
    with open(path, "wb") as f:
        f.write(b"Gyroid Filter".ljust(80, b" "))
        f.write(struct.pack("<I", len(mesh.tris)))
        for t, (i, j, k) in enumerate(mesh.tris):
            n = mesh.normals[t]
            f.write(struct.pack("<12fH", *n, *mesh.verts[i], *mesh.verts[j], *mesh.verts[k], 0))


def _strip(tag): return tag.rsplit("}", 1)[-1]


def load_3mf(data, name="part"):
    """Geometry only: every mesh in the build, with item/component transforms applied.
    Slicer settings and modifiers inside the file are NOT kept."""
    import io
    z = zipfile.ZipFile(io.BytesIO(data))
    model = "3D/3dmodel.model"
    for n in z.namelist():
        if n.lower() == model.lower():
            model = n
    root = ET.fromstring(z.read(model))
    objects = {}
    build = []
    for el in root.iter():
        t = _strip(el.tag)
        if t == "object":
            oid = el.get("id")
            mesh_el = comps = None
            for ch in el:
                if _strip(ch.tag) == "mesh": mesh_el = ch
                if _strip(ch.tag) == "components": comps = ch
            objects[oid] = (mesh_el, comps)
        elif t == "item":
            build.append((el.get("objectid"), el.get("transform")))

    def mat(s):
        if not s: return None
        m = [float(x) for x in s.split()]
        return m if len(m) == 12 else None

    def apply(m, p):
        if m is None: return p
        return (p[0] * m[0] + p[1] * m[3] + p[2] * m[6] + m[9],
                p[0] * m[1] + p[1] * m[4] + p[2] * m[7] + m[10],
                p[0] * m[2] + p[1] * m[5] + p[2] * m[8] + m[11])

    triangles = []

    def emit(oid, chain, depth=0):
        if depth > 8 or oid not in objects: return
        mesh_el, comps = objects[oid]
        if mesh_el is not None:
            verts, tris = [], []
            for ch in mesh_el:
                if _strip(ch.tag) == "vertices":
                    verts = [(float(v.get("x")), float(v.get("y")), float(v.get("z"))) for v in ch]
                elif _strip(ch.tag) == "triangles":
                    tris = [(int(t.get("v1")), int(t.get("v2")), int(t.get("v3"))) for t in ch]
            for (a, b, c) in tris:
                pts = [verts[a], verts[b], verts[c]]
                for m in reversed(chain):
                    pts = [apply(m, p) for p in pts]
                triangles.append(tuple(pts))
        if comps is not None:
            for c in comps:
                emit(c.get("objectid"), chain + [mat(c.get("transform"))], depth + 1)

    for oid, tr in build:
        emit(oid, [mat(tr)])
    if not triangles:
        raise ValueError("No triangles found in the 3MF file")
    return weld(triangles, name)


def load_mesh(data, filename):
    base = re.sub(r"\.[^.]*$", "", filename.replace("\\", "/").split("/")[-1]) or "part"
    low = filename.lower()
    if low.endswith(".3mf"):
        return load_3mf(data, base)
    return load_stl(data, base)
