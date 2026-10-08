"""SEEDS Greenbelt Corridor Planner CLI.

  python -m seeds_cds run --project <gcp>       # Earth Engine + trails/roads -> docs/data + outputs/
  python -m seeds_cds network                   # rebuild trails/roads/corridors, reuse cached Earth Engine
  python -m seeds_cds network --refresh         # same, re-download OSM / ArcGIS sources
  python -m seeds_cds sources                   # check every endpoint in config/sources.yaml
  python -m seeds_cds parcels --scenario balanced   # parcels + owners along the routed corridor
  python -m seeds_cds tiles --project <gcp>     # refresh Earth Engine overlay tiles (URLs expire)
  python -m seeds_cds serve                     # open the planner at http://localhost:8000/tool/
  python -m seeds_cds run --demo --counties config/aoi_counties.geojson   # synthetic, offline
"""
from __future__ import annotations

import argparse
import functools
import http.server
import threading
import webbrowser

from .config import DEFAULT_CONFIG, DEFAULT_HUBS, ROOT, load_config


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

    def common(p, gee=True):
        p.add_argument("--config", default=str(DEFAULT_CONFIG))
        p.add_argument("--hubs", default=str(DEFAULT_HUBS))
        p.add_argument("--counties", help="gee | census | path to county geojson/gpkg")
        if gee:
            p.add_argument("--project", help="GCP project for Earth Engine")

    r = sub.add_parser("run", help="full pipeline")
    common(r)
    r.add_argument("--demo", action="store_true", help="synthetic criteria + network (no GEE, no downloads)")
    r.add_argument("--res", type=int, help="H3 resolution override")
    r.add_argument("--no-ai", action="store_true", help="skip RF suitability")
    r.add_argument("--reuse-gee", action="store_true", help="reuse cached Earth Engine criteria")
    r.add_argument("--skip-network", action="store_true", help="do not rebuild the trail/road network")
    r.add_argument("--refresh", action="store_true", help="re-download network sources (ignore cache)")
    r.add_argument("--serve", action="store_true", help="open the planner when done")

    n = sub.add_parser("network", help="rebuild trails/roads/corridors reusing cached Earth Engine results")
    common(n)
    n.add_argument("--res", type=int)
    n.add_argument("--refresh", action="store_true", help="re-download OSM / ArcGIS sources")
    n.add_argument("--serve", action="store_true")

    s = sub.add_parser("sources", help="check every data source endpoint")
    common(s)

    p = sub.add_parser("parcels", help="parcels and owners along a routed corridor")
    common(p, gee=False)
    p.add_argument("--scenario", default="balanced")
    p.add_argument("--buffer", type=float, default=30, help="metres either side of the corridor")

    t = sub.add_parser("tiles", help="refresh Earth Engine overlay tile URLs only")
    common(t)
    t.add_argument("--no-ai", action="store_true")

    v = sub.add_parser("serve", help="serve docs/ locally and open the planner")
    v.add_argument("--port", type=int, default=8000)
    v.add_argument("--no-browser", action="store_true")

    a = ap.parse_args(argv)
    if a.cmd == "serve":
        return serve(a.port, not a.no_browser)

    cfg = load_config(a.config, a.hubs)
    if getattr(a, "project", None):
        cfg.raw["gee"]["project"] = a.project
    if getattr(a, "no_ai", False):
        cfg.raw["ai"]["enabled"] = False

    if a.cmd == "tiles":
        from .pipeline import refresh_tiles
        return refresh_tiles(cfg)
    if a.cmd == "parcels":
        from .parcels import run_parcels
        return run_parcels(cfg, a.scenario, a.buffer)
    if a.cmd == "sources":
        from .aoi import load_counties
        from .sources import check_sources, load_sources
        if (a.counties or cfg.grid.get("county_source", "gee")) == "gee":
            from . import gee_layers as gl
            gl.init(cfg.gee.get("project"))
        c = load_counties(cfg, a.counties)
        return check_sources(load_sources(cfg.raw["network"].get("sources")), tuple(c.total_bounds))

    from .pipeline import run
    reuse = a.cmd == "network" or a.reuse_gee
    run(cfg, demo=getattr(a, "demo", False), res=a.res, county_source=a.counties, reuse_gee=reuse,
        skip_network=getattr(a, "skip_network", False), refresh_network=a.refresh)
    if a.serve:
        serve(8000)


if __name__ == "__main__":
    main()
