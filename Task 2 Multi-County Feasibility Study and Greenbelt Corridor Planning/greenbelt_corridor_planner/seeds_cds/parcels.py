"""Parcels along routed corridors: who owns the land each corridor segment crosses.

  python -m seeds_cds parcels [--scenario balanced] [--buffer 30]

Queries every configured parcel source (config/sources.yaml) with the corridor geometry,
adds PAD-US public/protected ownership, classifies owners, and measures corridor length
inside each parcel (split into existing-trail vs new-connector km).
Writes outputs/corridor_parcels_<scenario>.csv and .gpkg.
"""
from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, shape

from .config import Config
from .sources import _http, arcgis_layer_url, detect_fields, fetch_files, load_sources, owner_class


def _query_lines(src: dict, paths: list[list[list[float]]], buffer_m: float) -> list[dict]:
    """POST polyline query (avoids URL length limits); chunks long paths."""
    token = os.environ.get(src.get("token_env", "") or "_none_")
    layer = arcgis_layer_url(src, "Polygon")
    feats, seen = [], set()
    chunk = []
    for p in paths:
        for i in range(0, len(p), 150):
            chunk.append(p[i:i + 151])
    for i in range(0, len(chunk), 20):
        geom = {"paths": chunk[i:i + 20], "spatialReference": {"wkid": 4326}}
        q = {"geometry": json.dumps(geom), "geometryType": "esriGeometryPolyline", "inSR": 4326, "outSR": 4326,
             "spatialRel": "esriSpatialRelIntersects", "distance": buffer_m, "units": "esriSRUnit_Meter",
             "outFields": "*", "returnGeometry": "true", "f": "geojson"}
        if token:
            q["token"] = token
        res = json.loads(_http(f"{layer}/query", data=urllib.parse.urlencode(q).encode(),
                               headers={"Content-Type": "application/x-www-form-urlencoded"}))
        for f in res.get("features", []):
            k = json.dumps(f.get("properties"), sort_keys=True)[:400]
            if k not in seen:
                seen.add(k)
                feats.append(f)
    return feats


def corridor_parcels(cfg: Config, segments: gpd.GeoDataFrame, padus: list[dict], buffer_m: float = 30) -> gpd.GeoDataFrame:
    reg = load_sources(cfg.raw.get("network", {}).get("sources"))
    spec, classes = reg.get("parcel_fields", {}), reg.get("owner_classes", {})
    paths = [[list(c) for c in g.coords] for g in segments.geometry]
    rows = []
    for src in reg.get("parcels", []):
        try:
            if src["type"] == "arcgis":
                if not src.get("url"):
                    continue
                feats = _query_lines(src, paths, buffer_m)
            else:
                feats = fetch_files(src)
        except Exception as e:
            print(f"Parcels: {src['id']} skipped ({type(e).__name__}: {e})")
            continue
        print(f"Parcels: {src['id']} -> {len(feats)} parcels")
        for f in feats:
            p = f.get("properties") or {}
            fl = detect_fields(p, spec)
            g = (lambda r: p.get(fl[r]) if fl.get(r) else None)
            rows.append({"source": src["id"], "parcel_id": g("id"), "owner": g("owner"), "acres": g("acres"),
                         "landuse": g("landuse"), "value": g("value"), "address": g("address"),
                         "owner_class": owner_class(g("owner"), classes), "geometry": shape(f["geometry"])})
    for f in padus or []:
        p = f["properties"]
        rows.append({"source": "PAD-US", "parcel_id": p.get("Unit_Nm"), "owner": p.get("Own_Name") or p.get("Loc_Own"),
                     "acres": p.get("GIS_Acres"), "landuse": p.get("Des_Tp"), "value": None, "address": None,
                     "owner_class": f"Protected ({p.get('Own_Type', '?')}, {p.get('Category', '')}, access {p.get('Pub_Access', '?')})",
                     "geometry": shape(f["geometry"])})
    if not rows:
        return gpd.GeoDataFrame(columns=["source", "geometry"], crs="EPSG:4326")
    P = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    # corridor km inside each parcel, by segment kind
    seg = segments.to_crs(5070)
    Pm = P.to_crs(5070)
    for kind in ("existing", "new"):
        s = seg[seg["kind"] == kind].geometry.union_all() if (seg["kind"] == kind).any() else None
        P[f"km_{kind}"] = [round(g.intersection(s).length / 1000, 3) if s is not None else 0.0 for g in Pm.geometry]
    P = P[(P["km_existing"] + P["km_new"]) > 0].copy()
    P["acquisition_screen"] = np.where(P["owner_class"].isin(["Private", "Unknown"]) & (P["km_new"] > 0),
                                       "candidate: easement / acquisition", np.where(P["source"] == "PAD-US", "already protected", "coordinate with owner"))
    return P.sort_values(["acquisition_screen", "km_new"], ascending=[True, False])


def run_parcels(cfg: Config, scenario: str = "balanced", buffer_m: float = 30, gis_dir: Path | None = None,
                web_dir: Path | None = None) -> Path:
    from .pipeline import GIS_DIR, WEB_DIR

    gis_dir, web_dir = Path(gis_dir or GIS_DIR), Path(web_dir or WEB_DIR)
    segs = gpd.read_file(gis_dir / "corridors.gpkg", layer="segments")
    segs = segs[segs["scenario"] == scenario]
    if segs.empty:
        raise SystemExit(f"No corridor segments for scenario '{scenario}'. Run the pipeline first.")
    pad = web_dir / "padus.json"
    padus = json.loads(pad.read_text())["features"] if pad.exists() else []
    P = corridor_parcels(cfg, segs, padus, buffer_m)
    out = gis_dir / f"corridor_parcels_{scenario}.csv"
    P.drop(columns="geometry").to_csv(out, index=False)
    if len(P):
        P.to_file(gis_dir / f"corridor_parcels_{scenario}.gpkg", driver="GPKG")
    print(f"Parcels along '{scenario}' corridor: {len(P)} -> {out}")
    return out
