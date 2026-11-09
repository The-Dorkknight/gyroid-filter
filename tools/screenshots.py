# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Drive the real web UI in headless Chrome: load the example, pick surfaces, add regions, export,
save screenshots into docs/images/ and fail on any JavaScript error.  Needs: playwright + Chrome."""
import json, math, os, sys, threading, time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from gyroid_filter import server  # noqa: E402

OUT = os.path.join(ROOT, "docs", "images")
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")


def main():
    from playwright.sync_api import sync_playwright
    os.makedirs(OUT, exist_ok=True)
    state, token = server.State(), "shot"
    srv = server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: None)
    srv.RequestHandlerClass = server.make_handler(state, token, srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/" % srv.server_address[1]
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-proxy-server", "--use-gl=angle", "--use-angle=swiftshader",
                                                           "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox"])
        page = b.new_page(viewport={"width": 1280, "height": 760})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_timeout(500)
        page.click("#example")
        page.wait_for_function("window.__gf && window.__gf.model", timeout=20000)
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(OUT, "01-loaded.png"))

        def click_world(x, y, z):
            pt = page.evaluate("""([x,y,z]) => { const g = window.__gf; const v = new g.THREE.Vector3(x,y,z).project(g.camera);
                const r = document.getElementById('view').getBoundingClientRect();
                return [r.left + (v.x+1)/2*r.width, r.top + (1-v.y)/2*r.height]; }""", [x, y, z])
            page.mouse.click(pt[0], pt[1])
            page.wait_for_timeout(900)

        # the camera looks from +x,-y: the outer wall point at angle -45 deg is visible
        a = math.radians(-35)
        click_world(30 * math.cos(a), 30 * math.sin(a), 30)
        page.screenshot(path=os.path.join(OUT, "02-picked-cylinder.png"))
        sel_text = page.inner_text("#selinfo")
        page.wait_for_timeout(500)
        stats_text = page.inner_text("#stats")
        page.click("#add"); page.wait_for_timeout(600)
        # inner chamber wall is hidden; pick the base plate underside is hidden too -> add the tube wall seen from the top
        page.evaluate("""() => { const g = window.__gf; g.camera.position.set(60, -70, 110); g.controls.update(); }""")
        page.wait_for_timeout(300)
        click_world(12 * math.cos(math.radians(-49)), 12 * math.sin(math.radians(-49)), 55)
        sel2 = page.inner_text("#selinfo")
        page.fill("#density", "35"); page.dispatch_event("#density", "input"); page.wait_for_timeout(600)
        page.click("#add"); page.wait_for_timeout(600)
        page.screenshot(path=os.path.join(OUT, "03-regions-added.png"))
        for fl in ("xprusa", "xorca", "xstl"):
            assert not page.is_disabled("#" + fl), fl + " should be enabled"
        page.click(".tab[data-tab=cura]"); page.wait_for_timeout(600)
        page.screenshot(path=os.path.join(OUT, "04-cura-tab.png"))
        b.close()
    srv.shutdown()
    from PIL import Image
    for n in ("01-loaded", "02-picked-cylinder", "03-regions-added", "04-cura-tab"):
        f = os.path.join(OUT, n + ".png")
        Image.open(f).save(os.path.join(OUT, n + ".webp"), "WEBP", lossless=True, method=6)
        os.remove(f)
    print("selection 1:", sel_text); print("stats 1:", stats_text); print("selection 2:", sel2)
    print("regions on server:", [r["label"] for r in state.regions])
    if errors:
        print("JS ERRORS:", errors); return 1
    print("no JavaScript errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
