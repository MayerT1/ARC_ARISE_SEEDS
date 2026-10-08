"""Inline docs/tool + vendor libs + data into one self-contained HTML (offline / email / artifact preview).

  python scripts/bundle_preview.py [out.html] [--preview]
--preview: default to no basemap (for sandboxes that block tile servers).
"""
import json
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"


def main(out="seeds_planner_bundle.html", preview=False):
    html = (DOCS / "tool" / "index.html").read_text(encoding="utf-8")
    read = lambda p: (DOCS / p).read_text(encoding="utf-8")  # noqa: E731
    html = re.sub(r"<!doctype html>\s*<html[^>]*>\s*<head>|</head>\s*<body>|</body>\s*</html>", "", html, flags=re.I) \
        if preview else html
    html = html.replace('<link rel="stylesheet" href="../assets/vendor/leaflet.css">',
                        f"<style>{read('assets/vendor/leaflet.css')}</style>")
    html = html.replace('<link rel="stylesheet" href="../assets/app.css">', f"<style>{read('assets/app.css')}</style>")
    data = {"cells": json.loads(read("data/cells.json")), "config": json.loads(read("data/config.json"))}
    for k in ("network", "padus", "parcels"):
        f = DOCS / "data" / f"{k}.json"
        data[k] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    boot = f"<script>window.SEEDS_DATA={json.dumps(data, separators=(',', ':'))};" \
           f"window.SEEDS_PREVIEW={str(preview).lower()};</script>"
    for src in ["vendor/leaflet.js", "vendor/h3-js.umd.js", "engine.js", "app.js"]:
        tag = f'<script src="../assets/{src}"></script>'
        js = read(f"assets/{src}").replace("</script", "<\\/script")
        html = html.replace(tag, (boot if src == "vendor/leaflet.js" else "") + f"<script>{js}</script>")
    html = html.replace('href="../"', 'href="https://github.com/MayerT1/ARC_ARISE_SEEDS"')
    Path(out).write_text(html, encoding="utf-8")
    print(f"{out}: {Path(out).stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(*(args[:1] or []), preview="--preview" in sys.argv)
