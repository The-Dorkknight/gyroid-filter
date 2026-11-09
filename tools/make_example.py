# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Make examples/cartridge.stl: a simple fillable filter cartridge (open at the top).

  outer wall r 27..30, inner tube r 9..12, base plate 3 mm, height 60 mm.
The annular chamber between the two walls is where the carbon goes."""
import math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from gyroid_filter.mesh import Mesh, save_stl, weld, sub, cross, dot


def revolve(profile, segs=96):
    """profile: counter-clockwise polygon of (r, z). Returns welded Mesh with outward normals."""
    tris = []
    for k in range(segs):
        a0, a1 = 2 * math.pi * k / segs, 2 * math.pi * (k + 1) / segs
        for i in range(len(profile)):
            (r0, z0), (r1, z1) = profile[i], profile[(i + 1) % len(profile)]
            p = lambda r, z, a: (r * math.cos(a), r * math.sin(a), z)
            q00, q01 = p(r0, z0, a0), p(r0, z0, a1)
            q10, q11 = p(r1, z1, a0), p(r1, z1, a1)
            tris.append((q00, q01, q11)); tris.append((q00, q11, q10))
    m = weld(tris, "cartridge")
    vol = sum(dot(m.verts[i], cross(m.verts[j], m.verts[k])) for i, j, k in m.tris) / 6
    if vol < 0:
        m.tris = [(a, c, b) for a, b, c in m.tris]; m._normals = None
    return m


def cartridge():
    prof = [(9, 0), (30, 0), (30, 60), (27, 60), (27, 3), (12, 3), (12, 60), (9, 60)]
    return revolve([(r, z) for r, z in prof])


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "examples", "cartridge.stl")
    m = cartridge()
    save_stl(m, out)
    print("wrote", os.path.normpath(out), len(m.tris), "triangles")
