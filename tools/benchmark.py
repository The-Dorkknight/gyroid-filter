# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Time the heavy steps on a big mesh, on one core, with and without numpy.  Usage: benchmark.py [segments]"""
import math, os, resource, sys, time, tempfile
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_example import revolve
from gyroid_filter.mesh import save_stl, load_stl
from gyroid_filter import regions as R


def run(segs, use_numpy):
    prof = [(9, 0), (30, 0), (30, 60), (27, 60), (27, 3), (12, 3), (12, 60), (9, 60)]
    m = revolve(prof, segs)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "big.stl"); save_stl(m, p)
        size = os.path.getsize(p) / 1e6
        t = time.time(); m = load_stl(open(p, "rb").read(), "big"); t_load = time.time() - t
    if not use_numpy:
        R._np = None
    t = time.time(); topo = R.Topology(m); t_topo = time.time() - t
    tri = next(i for i in range(len(m.tris)) if abs(math.hypot(*m.tri_centroid(i)[:2]) - 30) < .2 and abs(m.normals[i][2]) < .1)
    t = time.time(); sel = R.pick(m, topo, tri); t_pick = time.time() - t
    t = time.time(); th = R.wall_thickness(m, sel); t_thick = time.time() - t
    t = time.time(); reg, _ = R.cylinder_region(sel, th + 0.3); t_reg = time.time() - t
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print("%7d triangles (%5.1f MB STL) numpy=%-5s load %5.1fs  topology %5.1fs  pick %5.1fs  thickness %5.1fs  region %4.1fs  peak RSS %4.0f MB  kind=%s thick=%.2f"
          % (len(m.tris), size, use_numpy, t_load, t_topo, t_pick, t_thick, t_reg, rss, sel["kind"], th))


if __name__ == "__main__":
    segs = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    run(segs, "--no-numpy" not in sys.argv)
