# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Copy the shared geometry core into the Cura plug-in (one source of truth: src/gyroid_filter).
Run after changing mesh.py / regions.py / settings.py.  `--check` only reports differences."""
import os, shutil, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "src", "gyroid_filter")
DST = os.path.join(ROOT, "cura_plugin", "GyroidFilter", "gyroid_core")
FILES = ["mesh.py", "regions.py", "settings.py"]
INIT = ('# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)\n'
        '# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.\n'
        '"""Copy of src/gyroid_filter (made by tools/build_cura_plugin.py). Do not edit here."""\n'
        'from . import mesh, regions, settings  # noqa: F401\n')


def main():
    check = "--check" in sys.argv
    os.makedirs(DST, exist_ok=True)
    bad = 0
    for f in FILES:
        a, b = os.path.join(SRC, f), os.path.join(DST, f)
        same = os.path.exists(b) and open(a, "rb").read() == open(b, "rb").read()
        if not same:
            bad += 1
            if not check:
                shutil.copyfile(a, b)
    init = os.path.join(DST, "__init__.py")
    if not os.path.exists(init) or open(init).read() != INIT:
        bad += 1
        if not check:
            open(init, "w").write(INIT)
    print(("OUT OF DATE: %d file(s)" % bad) if check and bad else "plug-in core is up to date")
    return 1 if (check and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
