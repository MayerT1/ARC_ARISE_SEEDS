"""CLI.

  python -m seeds_cds run                    # GEE pipeline -> docs/data + outputs/
  python -m seeds_cds run --demo --counties counties.geojson   # synthetic, offline
  python -m seeds_cds run --res 8 --project my-gcp-project
"""
from __future__ import annotations

import argparse

from .config import DEFAULT_CONFIG, DEFAULT_HUBS, load_config
from .pipeline import run


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
    a = ap.parse_args(argv)

    cfg = load_config(a.config, a.hubs)
    if a.project:
        cfg.raw["gee"]["project"] = a.project
    if a.no_ai:
        cfg.raw["ai"]["enabled"] = False
    run(cfg, demo=a.demo, res=a.res, county_source=a.counties)


if __name__ == "__main__":
    main()
