# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Build the one-file PDF manual from the repo's own documents.
Needs: pip install markdown pillow playwright  (and a Chromium: playwright install chromium, or set CHROME).
Usage: python tools/make_pdf.py [--out docs/Gyroid-Filter-manual.pdf]"""
import argparse, html, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from gyroid_filter import __version__, __build_date__  # noqa: E402

REPO = "https://github.com/The-Dorkknight/gyroid-filter"
CHAPTERS = [("README.md", "Overview and how to use it"), ("HOW_IT_WORKS.md", "How it works"),
            ("DESIGN_NOTES.md", "Design notes and research"), ("CHANGELOG.md", "Changelog"),
            ("THIRD_PARTY.md", "Third-party parts"), ("LICENSE.md", "Licence")]
CSS = """
@page{size:A4;margin:16mm 15mm 18mm}
body{font:10pt/1.5 -apple-system,"Segoe UI",Roboto,"DejaVu Sans",sans-serif;color:#1f2933}
h1,h2,h3,h4{color:#0f766e;line-height:1.25;break-after:avoid}h2{border-bottom:1px solid #cdeee9;padding-bottom:2px;margin-top:1.4em}
a{color:#0b5f8a;text-decoration:none}code{background:#eef6f5;border-radius:3px;padding:0 3px;font-size:9pt}
pre{background:#f1f7f6;border:1px solid #d6e8e5;border-radius:6px;padding:8px 10px;white-space:pre-wrap;word-break:break-word;font-size:8.3pt;break-inside:avoid}
pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:9pt}th{background:#d9f3ef;text-align:left}
td,th{border:1px solid #cfe3e0;padding:4px 6px;vertical-align:top}tr:nth-child(even) td{background:#f6fbfa}
td img{max-height:65mm;width:auto}
blockquote{margin:8px 0;padding:6px 12px;background:#fff6e5;border-left:4px solid #ffa94d;break-inside:avoid}
img{max-width:100%;height:auto;border:1px solid #d6e8e5;border-radius:4px}
.cover{min-height:255mm;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;break-after:page}
.cover img.icon{width:34mm;border:0;border-radius:8mm}.cover h1{font-size:34pt;margin:10px 0 0;color:#0f766e}
.cover p.pitch{font-size:13pt;color:#3b4a56;max-width:150mm}
.pill{display:inline-block;background:#c2410c;color:#fff;border-radius:99px;padding:3px 12px;font-weight:700;font-size:9pt}
.cover .shots img{width:84mm;margin-right:4mm}.notice{font-size:8.5pt;color:#52606d;max-width:165mm;margin-top:12px}
.chap{break-before:page}.chap>.hd{background:linear-gradient(90deg,#0f766e,#2dd4bf);color:#fff;padding:10px 14px;border-radius:8px;margin-bottom:10px}
.chap>.hd h1{color:#fff;margin:0;font-size:19pt}.chap>.hd div{opacity:.9;font-size:9.5pt}
.toc li{margin:3px 0}
"""


def jpeg_copy(src, tmp, cache):
    if src in cache:
        return cache[src]
    from PIL import Image
    im = Image.open(src)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA"); bg = Image.new("RGB", im.size, "white"); bg.paste(im, mask=im.split()[3]); im = bg
    else:
        im = im.convert("RGB")
    if im.width > 1000:
        im = im.resize((1000, round(im.height * 1000 / im.width)), Image.LANCZOS)
    dst = os.path.join(tmp, "img%d.jpg" % len(cache))
    im.save(dst, "JPEG", quality=72, progressive=True, optimize=True)
    cache[src] = "file://" + dst
    return cache[src]


def render(md_path, idx, tmp, cache, ids):
    import markdown
    base = os.path.dirname(md_path)
    text = open(md_path, encoding="utf-8").read()
    text = re.sub(r"\A\s*#\s[^\n]*\n", "", text)          # chapter header replaces the first title
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\(https?://[^)]*\)", "", text)   # remote badges
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "toc", "attr_list"],
                             extension_configs={"toc": {"slugify": lambda v, s, i=idx: "c%d-%s" % (i, re.sub(r"[^\w]+", "-", v.lower()).strip("-")), "toc_depth": "2-3"}})

    def fix_img(m):
        src = m.group(1)
        if re.match(r"https?:", src):
            return ""
        p = os.path.normpath(os.path.join(base, src))
        return 'src="%s"' % jpeg_copy(p, tmp, cache) if os.path.exists(p) else 'src="" alt="missing"'
    body = re.sub(r'src="([^"]+)"', fix_img, body)

    def fix_a(m):
        href = m.group(1)
        if re.match(r"(https?:|mailto:|#)", href):
            return m.group(0)
        path = href.split("#")[0]
        full = os.path.normpath(os.path.join(base, path))
        name = os.path.basename(full)
        if name in ids:
            return 'href="#chapter-%s"' % ids[name]
        return 'href="%s/blob/main/%s"' % (REPO, os.path.relpath(full, ROOT).replace(os.sep, "/"))
    return re.sub(r'href="([^"]*)"', fix_a, body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "Gyroid-Filter-manual.pdf"))
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp(prefix="gfpdf")
    cache = {}
    chap = [(f, t) for f, t in CHAPTERS if os.path.exists(os.path.join(ROOT, f))]
    ids = {f: i for i, (f, _) in enumerate(chap)}
    parts = []
    for i, (f, t) in enumerate(chap):
        parts.append('<section class="chap" id="chapter-%d"><div class="hd"><h1>%s</h1><div>%s</div></div>%s</section>'
                     % (i, html.escape(f.rsplit(".", 1)[0].replace("_", " ").title()), html.escape(t), render(os.path.join(ROOT, f), i, tmp, cache, ids)))
    icon = jpeg_copy(os.path.join(ROOT, "docs", "images", "icon-512.png"), tmp, cache)
    shots = "".join('<img src="%s">' % jpeg_copy(os.path.join(ROOT, "docs", "images", n), tmp, cache) for n in ("02-picked-cylinder.webp", "03-regions-added.webp"))
    toc = "".join('<li><a href="#chapter-%d">%s</a> <span style="color:#667">· %s</span></li>' % (i, f.rsplit(".", 1)[0].replace("_", " ").title(), t) for i, (f, t) in enumerate(chap))
    doc = ('<!doctype html><meta charset="utf-8"><style>%s</style><div class="cover"><img class="icon" src="%s"><h1>Gyroid Filter</h1>'
           '<p class="pitch">Pick a flat face or a cylinder and make it open-cell gyroid, for fillable carbon filters. Cura, PrusaSlicer, OrcaSlicer.</p>'
           '<p><span class="pill">WORK IN PROGRESS · MANY FEATURES MAY BE BROKEN</span></p><p>Version %s · built %s</p><div class="shots">%s</div>'
           '<p class="notice">Source-available, non-commercial (PolyForm Noncommercial 1.0.0). Provided as is, with no warranty and no liability. '
           'Not a medical or safety device; nothing here has been tested for filtration performance.</p></div>'
           '<h1>Contents</h1><ol class="toc">%s</ol>%s') % (CSS, icon, __version__, __build_date__, shots, toc, "".join(parts))
    hp = os.path.join(tmp, "manual.html")
    open(hp, "w", encoding="utf-8").write(doc)
    foot = ('<div style="font:7pt sans-serif;color:#667;width:100%%;padding:0 15mm;display:flex;justify-content:space-between">'
            '<span>Gyroid Filter %s · work in progress · PolyForm Noncommercial 1.0.0</span><span>page <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>' % __version__)
    chrome = os.environ.get("CHROME")
    with sync_playwright() as p:
        kw = {"executable_path": chrome} if chrome else ({"executable_path": "/usr/bin/google-chrome"} if os.path.exists("/usr/bin/google-chrome") else {})
        b = p.chromium.launch(args=["--no-proxy-server", "--allow-file-access-from-files", "--no-sandbox"], **kw)
        pg = b.new_page(); pg.goto("file://" + hp); pg.wait_for_timeout(500)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        pg.pdf(path=a.out, format="A4", print_background=True, display_header_footer=True, header_template="<span></span>", footer_template=foot,
               margin={"top": "16mm", "bottom": "18mm", "left": "15mm", "right": "15mm"})
        b.close()
    if shutil.which("qpdf"):
        t2 = a.out + ".tmp"
        subprocess.run(["qpdf", "--object-streams=generate", "--compress-streams=y", "--recompress-flate", a.out, t2], check=False)
        if os.path.exists(t2):
            os.replace(t2, a.out)
    shutil.rmtree(tmp, ignore_errors=True)
    print("wrote %s (%.2f MB)" % (a.out, os.path.getsize(a.out) / 1e6))


if __name__ == "__main__":
    main()
