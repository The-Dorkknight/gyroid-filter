# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Pick a planar face or a cylinder from a mesh and build the solid 'region' that a
slicer then prints as open-cell gyroid (a modifier / cutting volume).

Pure Python on purpose (runs on a 7th-gen Core i3, no numpy needed). numpy is only
used, when present, to speed up the thickness probe on big meshes.
"""
import math
from .mesh import Mesh, sub, add, mul, dot, cross, unit, length

try:  # optional speed-up only
    import numpy as _np
except Exception:  # pragma: no cover
    _np = None

OVERSHOOT_MM = 0.3      # region pokes this far outside the surface so it fully crosses the skin


# ---------------------------------------------------------------- topology
class Topology:
    def __init__(self, mesh):
        edge = {}
        for t, (a, b, c) in enumerate(mesh.tris):
            for u, v in ((a, b), (b, c), (c, a)):
                edge.setdefault((u, v) if u < v else (v, u), []).append(t)
        nb = [[] for _ in mesh.tris]
        for ts in edge.values():
            if len(ts) == 2:
                nb[ts[0]].append(ts[1]); nb[ts[1]].append(ts[0])
        self.neighbours = nb


# ---------------------------------------------------------------- plane
def plane_cluster(mesh, topo, seed, angle_deg=1.0, dist_mm=0.05):
    n0 = mesh.normals[seed]
    d0 = dot(n0, mesh.verts[mesh.tris[seed][0]])
    cos_t = math.cos(math.radians(angle_deg))
    seen = {seed}
    stack = [seed]
    while stack:
        t = stack.pop()
        for nb in topo.neighbours[t]:
            if nb in seen:
                continue
            if dot(mesh.normals[nb], n0) < cos_t:
                continue
            if any(abs(dot(n0, mesh.verts[i]) - d0) > dist_mm for i in mesh.tris[nb]):
                continue
            seen.add(nb); stack.append(nb)
    return sorted(seen), n0, d0


def plane_frame(n):
    """Orthonormal (u, v, n) with a stable, human-sensible u (world X, else Y)."""
    ref = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    if abs(n[2]) < 0.9:                       # vertical-ish wall: u runs horizontally, v is up
        ref = (0.0, 0.0, 1.0)
        v = unit(sub(ref, mul(n, dot(ref, n))))
        u = unit(cross(v, n))
        return u, v, n
    u = unit(sub(ref, mul(n, dot(ref, n))))
    v = cross(n, u)
    return u, v, n


# ---------------------------------------------------------------- cylinder
def _jacobi_eigen(m):
    """Symmetric 3x3 eigen-decomposition; returns (values, vectors-as-columns list of 3 vectors)."""
    a = [list(r) for r in m]
    v = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
    for _ in range(40):
        p, q, big = 0, 1, 0.0
        for i in range(3):
            for j in range(i + 1, 3):
                if abs(a[i][j]) > big:
                    big, p, q = abs(a[i][j]), i, j
        if big < 1e-14:
            break
        th = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        c, s = math.cos(th), math.sin(th)
        for k in range(3):
            akp, akq = a[k][p], a[k][q]
            a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
        for k in range(3):
            apk, aqk = a[p][k], a[q][k]
            a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
        for k in range(3):
            vkp, vkq = v[k][p], v[k][q]
            v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    vals = [a[0][0], a[1][1], a[2][2]]
    vecs = [(v[0][i], v[1][i], v[2][i]) for i in range(3)]
    order = sorted(range(3), key=lambda i: vals[i])
    return [vals[i] for i in order], [vecs[i] for i in order]


def _patch(mesh, topo, seed, max_tris=8000, step_deg=25.0, spread_deg=30.0):
    """Grow around the seed until the normals have turned about `spread_deg` away from the seed's
    (so even a very finely tessellated cylinder gives a well-conditioned fit).  Returns (set, max angle)."""
    cos_s = math.cos(math.radians(step_deg))
    cos_spread = math.cos(math.radians(spread_deg))
    n0 = mesh.normals[seed]
    seen = {seed}
    queue = [seed]
    head, widest = 0, 1.0
    while head < len(queue) and len(seen) < max_tris:
        t = queue[head]; head += 1
        for nb in topo.neighbours[t]:
            if nb not in seen and dot(mesh.normals[nb], mesh.normals[t]) >= cos_s:
                seen.add(nb); queue.append(nb)
                widest = min(widest, dot(mesh.normals[nb], n0))
        if widest <= cos_spread:
            break
    return seen, math.acos(max(-1.0, min(1.0, widest)))


def fit_cylinder(mesh, topo, seed):
    """Returns a dict describing the cylinder the seed triangle belongs to, or None."""
    patch, spread = _patch(mesh, topo, seed)
    if len(patch) < 6 or spread < math.radians(10):
        return None                 # too little curvature around here: not a cylinder (or far too coarse)
    cov = [[0.0] * 3 for _ in range(3)]
    for t in patch:
        n = mesh.normals[t]
        for i in range(3):
            for j in range(3):
                cov[i][j] += n[i] * n[j]
    vals, vecs = _jacobi_eigen(cov)
    if vals[1] <= 0 or vals[0] / vals[1] > 0.02:
        return None                 # the normals do not all lie in one plane: a sphere/cone/blend, not a cylinder
    axis = unit(vecs[0])
    ref = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = unit(sub(ref, mul(axis, dot(ref, axis))))
    v = cross(axis, u)
    pts = {i for t in patch for i in mesh.tris[t]}
    xs = [(dot(mesh.verts[i], u), dot(mesh.verts[i], v)) for i in pts]
    # Kasa circle fit: x^2+y^2 + A x + B y + C = 0
    sxx = sum(x * x for x, _ in xs); syy = sum(y * y for _, y in xs); sxy = sum(x * y for x, y in xs)
    sx = sum(x for x, _ in xs); sy = sum(y for _, y in xs); n = float(len(xs))
    sz = sum(x * x + y * y for x, y in xs)
    sxz = sum(x * (x * x + y * y) for x, y in xs); syz = sum(y * (x * x + y * y) for x, y in xs)
    m = [[sxx, sxy, sx], [sxy, syy, sy], [sx, sy, n]]
    rhs = [-sxz, -syz, -sz]
    sol = _solve3(m, rhs)
    if sol is None:
        return None
    A, B, C = sol
    cx, cy = -A / 2, -B / 2
    r2 = cx * cx + cy * cy - C
    if r2 <= 1e-6:
        return None
    r = math.sqrt(r2)
    tol = 0.02 + 0.002 * r
    if any(abs(math.hypot(x - cx, y - cy) - r) > tol for x, y in xs):
        return None
    # grow over the whole mesh
    c0 = add(mul(u, cx), mul(v, cy))
    def radial(p):
        q = sub(p, c0)
        return sub(q, mul(axis, dot(q, axis)))
    n0 = mesh.normals[seed]
    cen = mesh.tri_centroid(seed)
    sign = 1 if dot(n0, radial(cen)) > 0 else -1
    sin_a = math.sin(math.radians(3.0))
    cluster = {seed}
    stack = [seed]
    while stack:
        t = stack.pop()
        for nb in topo.neighbours[t]:
            if nb in cluster:
                continue
            nn = mesh.normals[nb]
            if abs(dot(nn, axis)) > sin_a:
                continue
            if any(abs(length(radial(mesh.verts[i])) - r) > tol for i in mesh.tris[nb]):
                continue
            if (1 if dot(nn, radial(mesh.tri_centroid(nb))) > 0 else -1) != sign:
                continue
            cluster.add(nb); stack.append(nb)
    if len(cluster) < 6:
        return None
    vids = {i for t in cluster for i in mesh.tris[t]}
    ts = [dot(mesh.verts[i], axis) for i in vids]
    t0, t1 = min(ts), max(ts)
    # angular coverage
    angs = sorted({round(math.atan2(dot(sub(mesh.verts[i], c0), v), dot(sub(mesh.verts[i], c0), u)), 6) for i in vids})
    gaps = [(angs[(k + 1) % len(angs)] - angs[k]) % (2 * math.pi) for k in range(len(angs))]
    if len(angs) < 2:
        return None
    big = max(range(len(gaps)), key=lambda k: gaps[k])
    step = sorted(gaps)[len(gaps) // 2] or 1e-3
    if gaps[big] > max(3 * step, math.radians(12)):
        a0 = angs[(big + 1) % len(angs)]
        span = 2 * math.pi - gaps[big]
        arc = (a0, a0 + span)
    else:
        arc = None
    # centre of the axis at mid-extent
    centre = add(c0, mul(axis, (t0 + t1) / 2 - dot(c0, axis)))
    return {"kind": "cylinder", "tris": sorted(cluster), "axis": axis, "u": u, "v": v,
            "centre": centre, "t0": t0, "t1": t1, "c0": c0, "radius": r,
            "concave": sign < 0, "arc": arc}


def _solve3(m, b):
    a = [row[:] + [b[i]] for i, row in enumerate(m)]
    for i in range(3):
        piv = max(range(i, 3), key=lambda r: abs(a[r][i]))
        if abs(a[piv][i]) < 1e-12:
            return None
        a[i], a[piv] = a[piv], a[i]
        for r in range(3):
            if r != i:
                f = a[r][i] / a[i][i]
                for c in range(i, 4):
                    a[r][c] -= f * a[i][c]
    return [a[i][3] / a[i][i] for i in range(3)]


def pick(mesh, topo, tri, mode="auto"):
    """Select the face or cylinder that triangle `tri` belongs to.
    mode: 'plane' (flat face only), 'cylinder' (cylinder only, ValueError if none) or 'auto'.
    Auto prefers a cylinder when it covers more triangles than the flat patch the click also fits:
    a finely tessellated cylinder looks 'flat' over a few facets."""
    ids, n, d = plane_cluster(mesh, topo, tri)
    plane = {"kind": "plane", "tris": ids, "normal": n, "d": d}
    if mode == "plane":
        return plane
    cyl = fit_cylinder(mesh, topo, tri)
    if mode == "cylinder":
        if cyl is None:
            raise ValueError("No cylinder found at that spot (is it a flat face, a cone or a blend?)")
        return cyl
    if cyl is not None and len(cyl["tris"]) > len(ids):
        return cyl
    return plane


# ---------------------------------------------------------------- thickness probe
def ray_distance(mesh, origin, direction):
    """Smallest positive distance along the ray to any triangle, or None."""
    if _np is not None and len(mesh.tris) > 2000:
        if not hasattr(mesh, "_np_tris"):
            V = _np.asarray(mesh.verts, dtype=_np.float64)
            T = _np.asarray(mesh.tris, dtype=_np.int64)
            mesh._np_tris = (V[T[:, 0]], V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
        p0, e1, e2 = mesh._np_tris
        d = _np.asarray(direction); o = _np.asarray(origin)
        h = _np.cross(d, e2)
        a = (e1 * h).sum(1)
        ok = _np.abs(a) > 1e-12
        f = _np.where(ok, 1.0 / _np.where(ok, a, 1.0), 0.0)
        s = o - p0
        uu = f * (s * h).sum(1)
        q = _np.cross(s, e1)
        vv = f * (q * d).sum(1)
        t = f * (e2 * q).sum(1)
        hit = ok & (uu >= 0) & (vv >= 0) & (uu + vv <= 1) & (t > 1e-4)
        return float(t[hit].min()) if hit.any() else None
    best = None
    V = mesh.verts
    for (i, j, k) in mesh.tris:
        p0 = V[i]; e1 = sub(V[j], p0); e2 = sub(V[k], p0)
        h = cross(direction, e2); a = dot(e1, h)
        if -1e-12 < a < 1e-12:
            continue
        f = 1.0 / a; s = sub(origin, p0)
        u = f * dot(s, h)
        if u < 0 or u > 1:
            continue
        q = cross(s, e1); w = f * dot(direction, q)
        if w < 0 or u + w > 1:
            continue
        t = f * dot(e2, q)
        if t > 1e-4 and (best is None or t < best):
            best = t
    return best


def wall_thickness(mesh, sel, samples=3):
    """Median distance from the selected surface to the far side of the material."""
    tris = sel["tris"]
    pick_t = sorted(tris, key=lambda t: -mesh.areas[t])[:samples]
    out = []
    for t in pick_t:
        c = mesh.tri_centroid(t)
        if sel["kind"] == "plane":
            inward = mul(sel["normal"], -1.0)
        else:
            r = sub(c, sel["c0"]); r = sub(r, mul(sel["axis"], dot(r, sel["axis"])))
            # material lies radially outward for a concave surface, inward for a convex one
            inward = unit(r) if sel["concave"] else mul(unit(r), -1.0)
        o = add(c, mul(inward, 1e-3))
        d = ray_distance(mesh, o, inward)
        if d is not None:
            out.append(d + 1e-3)
    if not out:
        return None
    out.sort()
    return out[len(out) // 2]


# ---------------------------------------------------------------- region solids
def _clip_poly(poly, a, b, c):
    """Keep the half-plane a*x + b*y + c >= 0 (Sutherland-Hodgman, one edge)."""
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        sp = a * p[0] + b * p[1] + c
        sq = a * q[0] + b * q[1] + c
        if sp >= 0:
            out.append(p)
        if (sp >= 0) != (sq >= 0):
            t = sp / (sp - sq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


class _Builder:
    def __init__(self):
        self.verts, self.tris, self._idx = [], [], {}

    def vert(self, p):
        key = (round(p[0] * 1e4), round(p[1] * 1e4), round(p[2] * 1e4))
        i = self._idx.get(key)
        if i is None:
            i = len(self.verts); self._idx[key] = i
            self.verts.append((key[0] / 1e4, key[1] / 1e4, key[2] / 1e4))
        return i

    def tri(self, a, b, c):
        pa, pb, pc = (self.verts[a], self.verts[b], self.verts[c])
        if a != b != c != a and length(cross(sub(pb, pa), sub(pc, pa))) > 1e-9:
            self.tris.append((a, b, c))

    def mesh(self, name):
        return Mesh(self.verts, self.tris, name)


def plane_region(mesh, sel, depth, window=None, over=OVERSHOOT_MM):
    """Prism under a planar face. window = dict(shape='rect'|'ellipse', u0,u1,v0,v1 as 0..1 of the
    face's own extent) or None for the whole face.  Returns (Mesh, info)."""
    n = sel["normal"]
    u, v, _ = plane_frame(n)
    origin = mesh.verts[mesh.tris[sel["tris"][0]][0]]
    w0 = dot(n, origin)
    polys = []
    for t in sel["tris"]:
        polys.append([(dot(mesh.verts[i], u), dot(mesh.verts[i], v)) for i in mesh.tris[t]])
    us = [p[0] for poly in polys for p in poly]; vs = [p[1] for poly in polys for p in poly]
    umin, umax, vmin, vmax = min(us), max(us), min(vs), max(vs)
    info = {"u_extent": umax - umin, "v_extent": vmax - vmin}
    if window:
        wu0 = umin + window.get("u0", 0.0) * (umax - umin); wu1 = umin + window.get("u1", 1.0) * (umax - umin)
        wv0 = vmin + window.get("v0", 0.0) * (vmax - vmin); wv1 = vmin + window.get("v1", 1.0) * (vmax - vmin)
        m = float(window.get("margin_mm", 0.0))
        wu0 += m; wu1 -= m; wv0 += m; wv1 -= m
        if wu1 - wu0 <= 0.05 or wv1 - wv0 <= 0.05:
            raise ValueError("The window is empty (margin too big or limits crossed)")
        clip = [(1, 0, -wu0), (-1, 0, wu1), (0, 1, -wv0), (0, -1, wv1)]
        if window.get("shape") == "ellipse":
            cu, cv = (wu0 + wu1) / 2, (wv0 + wv1) / 2
            ru, rv = (wu1 - wu0) / 2, (wv1 - wv0) / 2
            clip = []
            k = 48
            for s in range(k):
                th = 2 * math.pi * (s + 0.5) / k
                # tangent half-plane of the ellipse at angle th
                nu, nv = math.cos(th) / ru, math.sin(th) / rv
                nl = math.hypot(nu, nv)
                clip.append((-nu / nl, -nv / nl, 1.0 / nl + (nu * cu + nv * cv) / nl))
            # (a*x + b*y + c >= 0)  <=>  n.(p-c) <= 1/|n|
        newpolys = []
        for poly in polys:
            for a, b, c in clip:
                if not poly: break
                poly = _clip_poly(poly, a, b, c)
            if len(poly) >= 3:
                newpolys.append(poly)
        polys = newpolys
        if not polys:
            raise ValueError("The window does not touch the selected face")
    bld = _Builder()
    top, bot = w0 + over, w0 - depth
    def P(p, w): return add(add(mul(u, p[0]), mul(v, p[1])), mul(n, w))
    edges = {}
    for poly in polys:
        for k in range(1, len(poly) - 1):
            tri = (poly[0], poly[k], poly[k + 1])
            ar = (tri[1][0] - tri[0][0]) * (tri[2][1] - tri[0][1]) - (tri[2][0] - tri[0][0]) * (tri[1][1] - tri[0][1])
            if abs(ar) < 1e-10:
                continue
            if ar < 0:
                tri = (tri[0], tri[2], tri[1])
            ta = [bld.vert(P(p, top)) for p in tri]
            bld.tri(ta[0], ta[1], ta[2])
            tb = [bld.vert(P(p, bot)) for p in tri]
            bld.tri(tb[0], tb[2], tb[1])
            for a_, b_ in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                ka = (round(a_[0] * 1e4), round(a_[1] * 1e4)); kb = (round(b_[0] * 1e4), round(b_[1] * 1e4))
                if ka == kb:
                    continue
                if (kb, ka) in edges:
                    del edges[(kb, ka)]
                else:
                    edges[(ka, kb)] = (a_, b_)
    for (a_, b_) in edges.values():
        at, bt = bld.vert(P(a_, top)), bld.vert(P(b_, top))
        ab, bb = bld.vert(P(a_, bot)), bld.vert(P(b_, bot))
        bld.tri(ab, bb, bt)
        bld.tri(ab, bt, at)
    return bld.mesh("open-cell"), info


def cylinder_region(sel, depth, axial=(0.0, 1.0), arc_deg=None, margin_mm=0.0, over=OVERSHOOT_MM):
    """Shell of thickness `depth` on the material side of a cylinder surface.
    axial = (f0, f1) fractions of the cylinder's own length; arc_deg = (a0, a1) degrees inside the
    cylinder's own angular extent, or None for all of it."""
    r = sel["radius"]
    if sel["concave"]:
        r_in, r_out = r - over, r + depth
    else:
        r_in, r_out = r - depth, r + over
    r_in = max(r_in, 0.05)
    L = sel["t1"] - sel["t0"]
    t0 = sel["t0"] + axial[0] * L + margin_mm
    t1 = sel["t0"] + axial[1] * L - margin_mm
    if t1 - t0 <= 0.05:
        raise ValueError("The axial window is empty (margin too big or limits crossed)")
    if sel["arc"] is None:
        a_start, a_end, full = 0.0, 2 * math.pi, True
        if arc_deg is not None:
            a_start, a_end = math.radians(arc_deg[0]), math.radians(arc_deg[1]); full = (a_end - a_start) >= 2 * math.pi - 1e-6
    else:
        s0, s1 = sel["arc"]
        span = s1 - s0
        full = False
        a_start, a_end = s0, s1
        if arc_deg is not None:
            a_start = s0 + span * arc_deg[0] / 360.0; a_end = s0 + span * arc_deg[1] / 360.0
    if a_end - a_start <= 1e-3:
        raise ValueError("The angular window is empty")
    nseg = max(8, int(math.ceil((a_end - a_start) / math.radians(3.0))))
    axis, u, v, c0 = sel["axis"], sel["u"], sel["v"], sel["c0"]
    base = sub(c0, mul(axis, dot(c0, axis)))
    def P(rad, th, t):
        return add(add(base, mul(axis, t)), add(mul(u, rad * math.cos(th)), mul(v, rad * math.sin(th))))
    bld = _Builder()
    for k in range(nseg):
        th0 = a_start + (a_end - a_start) * k / nseg
        th1 = a_start + (a_end - a_start) * (k + 1) / nseg
        o00, o01 = bld.vert(P(r_out, th0, t0)), bld.vert(P(r_out, th0, t1))
        o10, o11 = bld.vert(P(r_out, th1, t0)), bld.vert(P(r_out, th1, t1))
        i00, i01 = bld.vert(P(r_in, th0, t0)), bld.vert(P(r_in, th0, t1))
        i10, i11 = bld.vert(P(r_in, th1, t0)), bld.vert(P(r_in, th1, t1))
        bld.tri(o00, o10, o11); bld.tri(o00, o11, o01)        # outer wall, normal outward
        bld.tri(i00, i11, i10); bld.tri(i00, i01, i11)        # inner wall, normal inward
        bld.tri(o01, o11, i11); bld.tri(o01, i11, i01)        # top cap
        bld.tri(o00, i10, o10); bld.tri(o00, i00, i10)        # bottom cap
    if not full:
        for th, flip in ((a_start, False), (a_end, True)):
            i0, o0 = bld.vert(P(r_in, th, t0)), bld.vert(P(r_out, th, t0))
            i1, o1 = bld.vert(P(r_in, th, t1)), bld.vert(P(r_out, th, t1))
            if not flip:
                bld.tri(i0, o0, o1); bld.tri(i0, o1, i1)
            else:
                bld.tri(i0, o1, o0); bld.tri(i0, i1, o1)
    return bld.mesh("open-cell"), {"r_in": r_in, "r_out": r_out, "t0": t0, "t1": t1}


# ---------------------------------------------------------------- checks
def signed_volume(m):
    s = 0.0
    for (i, j, k) in m.tris:
        s += dot(m.verts[i], cross(m.verts[j], m.verts[k]))
    return s / 6.0


def open_edges(m):
    cnt = {}
    for (a, b, c) in m.tris:
        for u, v in ((a, b), (b, c), (c, a)):
            cnt[(u, v)] = cnt.get((u, v), 0) + 1
    return sum(1 for (u, v), n in cnt.items() if cnt.get((v, u), 0) != n)
