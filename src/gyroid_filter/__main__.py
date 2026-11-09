# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
import argparse
import sys

from . import __version__, __build_date__, __app_name__


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gyroid-filter", description="Open-cell gyroid regions for fillable carbon filters.")
    ap.add_argument("model", nargs="?", help="STL or 3MF to open at start")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser by itself")
    ap.add_argument("--port", type=int, default=0)
    a = ap.parse_args(argv)
    if a.version:
        print("%s %s (built %s)" % (__app_name__, __version__, __build_date__))
        return 0
    from .server import serve
    return serve(open_browser=not a.no_browser, port=a.port, preload=a.model)


if __name__ == "__main__":
    sys.exit(main())
