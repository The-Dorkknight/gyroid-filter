# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Cura-independent helpers (numpy only) so they can be unit-tested outside Cura."""
import numpy


def triangles_from_arrays(vertices, indices):
    """vertices (N,3) float; indices (M,3) int or None (then vertices are a triangle soup)."""
    v = numpy.asarray(vertices, dtype=numpy.float64)
    if indices is None:
        return v.reshape(-1, 3, 3)
    return v[numpy.asarray(indices, dtype=numpy.int64)]


def ray_first_triangle(tri_points, origin, direction):
    """Index of the nearest triangle hit by the ray, or None.  tri_points: (M,3,3)."""
    o = numpy.asarray(origin, dtype=numpy.float64)
    d = numpy.asarray(direction, dtype=numpy.float64)
    p0 = tri_points[:, 0]
    e1 = tri_points[:, 1] - p0
    e2 = tri_points[:, 2] - p0
    h = numpy.cross(d, e2)
    a = (e1 * h).sum(1)
    ok = numpy.abs(a) > 1e-12
    f = numpy.where(ok, 1.0 / numpy.where(ok, a, 1.0), 0.0)
    s = o - p0
    u = f * (s * h).sum(1)
    q = numpy.cross(s, e1)
    v = f * (q * d).sum(1)
    t = f * (e2 * q).sum(1)
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6)
    if not hit.any():
        return None
    ts = numpy.where(hit, t, numpy.inf)
    return int(ts.argmin())


def build_mesh(vertices, indices, gyroid_core):
    """Weld to a gyroid_core Mesh whose triangle order matches `indices` exactly (so a ray-hit
    triangle number is also the mesh's triangle number).  Returns (mesh, tri_points)."""
    tri_points = triangles_from_arrays(vertices, indices)
    flat = tri_points.reshape(-1, 3)
    key = numpy.round(flat * 1e4).astype(numpy.int64)
    uniq, inv = numpy.unique(key, axis=0, return_inverse=True)
    verts = [tuple(float(c) / 1e4 for c in row) for row in uniq]
    tris = [tuple(int(i) for i in row) for row in inv.reshape(-1, 3)]
    return gyroid_core.mesh.Mesh(verts, tris, "model"), tri_points


def selftest(core):
    """Runs inside Cura at start-up: builds a small tube in memory, picks its wall, builds the
    region and checks it is a closed solid.  Returns a one-line result string."""
    import math
    segs, r_o, r_i, h = 48, 10.0, 7.0, 20.0
    tris = []
    def P(r, a, z): return (r * math.cos(a), r * math.sin(a), z)
    for k in range(segs):
        a0, a1 = 2 * math.pi * k / segs, 2 * math.pi * (k + 1) / segs
        for (r, flip) in ((r_o, False), (r_i, True)):
            q = [P(r, a0, 0), P(r, a1, 0), P(r, a1, h), P(r, a0, h)]
            t = [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
            tris += [(b, a, c) for a, b, c in t] if flip else t
        for z, up in ((h, True), (0, False)):
            q = [P(r_i, a0, z), P(r_i, a1, z), P(r_o, a1, z), P(r_o, a0, z)]
            t = [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
            tris += t if up else [(b, a, c) for a, b, c in t]
    m = core.mesh.weld(tris, "tube")
    topo = core.regions.Topology(m)
    t = next(i for i in range(len(m.tris))
             if abs(math.hypot(*m.tri_centroid(i)[:2]) - r_o) < 0.2 and abs(m.normals[i][2]) < 0.1)
    sel = core.regions.pick(m, topo, t)
    ok = sel["kind"] == "cylinder" and abs(sel["radius"] - r_o) < 0.05 and not sel["concave"]
    th = core.regions.wall_thickness(m, sel) if ok else None
    ok = ok and th is not None and abs(th - 3.0) < 0.05
    reg, _ = core.regions.cylinder_region(sel, 3.3) if ok else (None, None)
    ok = ok and core.regions.open_edges(reg) == 0 and core.regions.signed_volume(reg) > 0
    return "PASS" if ok else "FAIL (kind=%s)" % sel.get("kind")
