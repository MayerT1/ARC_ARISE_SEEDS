"""CLI.

  python -m seeds_cds run --project <gcp>     # GEE pipeline -> docs/data + outputs/
  python -m seeds_cds serve                   # open the planner at http://localhost:8000/tool/
  python -m seeds_cds tiles --project <gcp>   # refresh Earth Engine overlay tiles (URLs expire)
  python -m seeds_cds run --demo --counties config/aoi_counties.geojson   # synthetic, offline
"""
from __future__ import annotations

import argparse
import functools
import http.server
import threading
import webbrowser

from .config import DEFAULT_CONFIG, DEFAULT_HUBS, ROOT, load_config
from .pipeline import refresh_tiles, run


def serve(port: int, open_browser: bool = True) -> None:
    docs = ROOT / "docs"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(docs))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://localhost:{port}/tool/"
    print(f"Serving {docs}\nPlanner: {url}\nCtrl+C to stop")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="seeds_cds")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="build grid, criteria, exports")
    r.add_argument("--config", default=str(DEFAULT_CONFIG))
    r.add_argument("--hubs", default=str(DEFAULT_HUBS))
    r.add_argument("--demo", action="store_true", help="synthetic criteria (no GEE)")
    r.add_argument("--res", type=int, help="H3 resolution override")
    r.add_argument("--counties", help="gee | census | path to county geojson/gpkg")
    r.add_argument("--project", help="GCP project for Earth Engine")
    r.add_argument("--no-ai", action="store_true", help="skip RF suitability")
    r.add_argument("--serve", action="store_true", help="open the planner when done")

    t = sub.add_parser("tiles", help="refresh Earth Engine overlay tile URLs only")
    t.add_argument("--config", default=str(DEFAULT_CONFIG))
    t.add_argument("--project")
    t.add_argument("--no-ai", action="store_true")

    s = sub.add_parser("serve", help="serve docs/ locally and open the planner")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-browser", action="store_true")

    a = ap.parse_args(argv)
    if a.cmd == "serve":
        return serve(a.port, not a.no_browser)

    cfg = load_config(a.config, getattr(a, "hubs", DEFAULT_HUBS))
    if a.project:
        cfg.raw["gee"]["project"] = a.project
    if a.no_ai:
        cfg.raw["ai"]["enabled"] = False
    if a.cmd == "tiles":
        return refresh_tiles(cfg)
    run(cfg, demo=a.demo, res=a.res, county_source=a.counties)
    if a.serve:
        serve(8000)


if __name__ == "__main__":
    main()
