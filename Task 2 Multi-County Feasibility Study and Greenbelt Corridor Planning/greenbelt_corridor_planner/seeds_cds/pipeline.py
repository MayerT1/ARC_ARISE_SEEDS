"""End-to-end: AOI -> H3 grid -> criteria (GEE or demo) + trail network -> web + GIS exports.

GEE results are cached in outputs/cache/ so `python -m seeds_cds network` (= run --reuse-gee)
can rebuild trails/roads/corridors without recomputing Earth Engine.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
from shapely.geometry import LineString

from . import scoring
from .config import ROOT, Config
from .grid import build_grid, haversine_km, nearest_km

WEB_DIR = ROOT / "docs" / "data"
GIS_DIR = ROOT / "outputs"
CACHE = GIS_DIR / "cache"
GEE_BANDS = ["forest", "developed", "relief", "canopy", "tall_canopy", "loss", "dist_water", "dist_road",
             "dist_protected", "protected", "protected_gap12", "ai_suitability"]


# ---------------------------------------------------------------- raw criteria
def raw_from_gee(grid, counties, cfg: Config) -> tuple[pd.DataFrame, dict]:
    from . import gee_layers as gl
    from .aggregate import reduce_cells

    aoi = gl.aoi_geometry(counties)
    stack, info = gl.build_stack(aoi, cfg)
    ai = None
    if cfg.ai.get("enabled", True):
        prob, diag = gl.ai_suitability(stack, aoi, cfg)
        stack = stack.addBands(prob)
        print("Geo-AI: pulling RF diagnostics ...")
        ai = gl.ai_metrics(diag)
        print(f"  holdout AUC = {ai['auc']}")
    tiles = gl.tile_layers(aoi, stack, info) if cfg.raw.get("tiles", {}).get("enabled", True) else []
    print("PAD-US: exporting public & protected land ownership ...")
    padus = gl.padus_features(aoi, cfg.gee["assets"])
    info.pop("_layers", None)
    bands = [b for b in GEE_BANDS if b != "ai_suitability" or ai]
    print(f"Reducing {len(bands)} bands over {len(grid)} cells ...")
    raw = reduce_cells(stack, grid, cfg, bands)
    return raw, {"source": "gee", "ai": ai, "tiles": tiles, "padus": padus, **info}


def raw_from_demo(grid, cfg: Config) -> tuple[pd.DataFrame, dict]:
    from .demo import synth_ai_metrics, synth_padus, synth_raw

    return synth_raw(grid, cfg), {"source": "demo", "ai": synth_ai_metrics(), "protected_source": "synthetic",
                                  "padus": synth_padus(cfg)}


def save_gee_cache(raw: pd.DataFrame, meta: dict, res: int) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    raw.to_csv(CACHE / f"gee_raw_r{res}.csv", index=False)
    (CACHE / f"gee_meta_r{res}.json").write_text(json.dumps(meta, default=str))


def load_gee_cache(res: int, web_dir: Path) -> tuple[pd.DataFrame, dict]:
    f, m = CACHE / f"gee_raw_r{res}.csv", CACHE / f"gee_meta_r{res}.json"
    if f.exists() and m.exists():
        print(f"Reusing cached Earth Engine criteria: {f}")
        return pd.read_csv(f), json.loads(m.read_text())
    # fallback: previous run's GIS table + web config (pre-0.2 builds)
    csv, conf = GIS_DIR / "seeds_cells.csv", Path(web_dir) / "config.json"
    if csv.exists() and conf.exists():
        print(f"Reusing Earth Engine criteria from previous run: {csv}")
        df = pd.read_csv(csv)
        c = json.loads(conf.read_text())
        meta = {"source": "gee", "ai": c.get("ai"), "tiles": c.get("tiles", []),
                "protected_source": c.get("protected_source"), "padus": None}
        return df[["h3"] + [b for b in GEE_BANDS if b in df]], meta
    raise FileNotFoundError("No cached Earth Engine results. Run `python -m seeds_cds run` once without --reuse-gee.")


# ---------------------------------------------------------------- assemble
def add_python_criteria(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    lat, lon = df["lat"].to_numpy(), df["lon"].to_numpy()
    df["dist_gateway"] = nearest_km(lat, lon, [(h.lat, h.lon) for h in cfg.hubs_of("gateway")])
    df["dist_hub"] = nearest_km(lat, lon, [(h.lat, h.lon) for h in cfg.hubs_of("park")])
    return df


def snap_hubs(cfg: Config, df: pd.DataFrame, res: int) -> list[dict]:
    cellset = set(df["h3"])
    out = []
    for h in cfg.hubs:
        c = h3.latlng_to_cell(h.lat, h.lon, res)
        if c not in cellset:
            d = haversine_km(df["lat"].to_numpy(), df["lon"].to_numpy(), h.lat, h.lon)
            i = int(np.argmin(d))
            if d[i] > 10:  # hub outside AOI
                continue
            c = df["h3"].iat[i]
        out.append({**h.__dict__, "cell": c})
    return out


def run(cfg: Config, demo: bool = False, res: int | None = None, county_source: str | None = None,
        counties=None, web_dir: Path = WEB_DIR, gis_dir: Path = GIS_DIR, reuse_gee: bool = False,
        skip_network: bool = False, refresh_network: bool = False) -> dict:
    from .aoi import load_counties
    from .network import attach, build_network, export_payload

    res = res or cfg.grid["h3_resolution"]
    src = county_source or cfg.grid.get("county_source", "gee")
    if (not demo and not reuse_gee) or (counties is None and src == "gee"):
        from . import gee_layers as gl
        gl.init(cfg.gee.get("project"))
    counties = counties if counties is not None else load_counties(cfg, src)
    grid = build_grid(counties, res)
    print(f"Grid: {len(grid)} H3 r{res} cells across {grid['county'].nunique()} counties")

    if demo:
        raw, meta = raw_from_demo(grid, cfg)
    elif reuse_gee:
        raw, meta = load_gee_cache(res, Path(web_dir))
        if not meta.get("padus"):
            old = Path(web_dir) / "padus.json"
            meta["padus"] = json.loads(old.read_text())["features"] if old.exists() else []
        if not meta["padus"]:
            try:  # older cache without ownership: export PAD-US only (fast)
                from . import gee_layers as gl
                gl.init(cfg.gee.get("project"))
                print("PAD-US: exporting public & protected land ownership ...")
                meta["padus"] = gl.padus_features(gl.aoi_geometry(counties), cfg.gee["assets"])
                save_gee_cache(raw, meta, res)
            except Exception as e:
                print(f"PAD-US export skipped ({type(e).__name__}: {e})")
    else:
        raw, meta = raw_from_gee(grid, counties, cfg)
        save_gee_cache(raw, meta, res)

    df = grid.merge(raw, on="h3", how="left")
    df = add_python_criteria(df, cfg)
    hubs = snap_hubs(cfg, df, res)

    net_payload = None
    if not skip_network:
        net = build_network(cfg, grid, counties, refresh=refresh_network, demo=demo, hubs=hubs)
        link = attach(net, grid, res, cfg)
        for k, v in link["criteria"].items():
            df[k] = v
        net_payload = export_payload(net, link, cfg)
        s = net.stats
        print(f"Network: {s['nodes']} nodes, {s['edges']} edges, {len(link['gaps'])} gap candidates; km by class {s['km_by_class']}")
    elif (Path(web_dir) / "network.json").exists():
        net_payload = json.loads((Path(web_dir) / "network.json").read_text())

    norm = scoring.normalize(df)
    write_web(df, norm, hubs, counties, cfg, meta, res, Path(web_dir), net_payload)
    write_gis(df, norm, hubs, cfg, Path(gis_dir), net_payload)
    return {"grid": df, "norm": norm, "hubs": hubs, "meta": meta, "network": net_payload}


# ---------------------------------------------------------------- exports
def _r(a, nd=3):
    return [None if (v is None or (isinstance(v, float) and np.isnan(v))) else round(float(v), nd) for v in a]


def write_web(df, norm, hubs, counties, cfg: Config, meta, res, out: Path, net_payload=None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    cty = counties.sort_values(["state", "name"]).reset_index(drop=True)
    cidx = {f: i for i, f in enumerate(cty["fips"])}
    raw_cols = {k: v[0] for k, v in scoring.CRITERIA_SOURCE.items() if k in norm}
    cells = {
        "meta": {"res": res, "n": len(df), "generated": dt.datetime.now().isoformat(timespec="seconds"),
                 "demo": meta["source"] == "demo", "source": meta["source"]},
        "counties": cty[["fips", "name", "state", "arc_status"]].to_dict("records"),
        "h3": df["h3"].tolist(),
        "county": [cidx[f] for f in df["fips"]],
        "protected": [int(round(v * 100)) for v in df["protected"].fillna(0)],
        "gap12": [int(round(v * 100)) for v in df["protected_gap12"].fillna(0)],
        "norm": {k: [int(round(v * 100)) for v in norm[k]] for k in norm},
        "raw": {k: _r(df[c]) for k, c in raw_cols.items()},
    }
    (out / "cells.json").write_text(json.dumps(cells, separators=(",", ":")))

    from .sources import load_sources
    reg = load_sources(cfg.raw.get("network", {}).get("sources"))
    crit = {k: v for k, v in cfg.criteria.items() if k in norm}
    config = {
        "project": cfg.raw["project"], "criteria": crit, "scenarios": cfg.scenarios,
        "corridor": cfg.corridor, "hubs": hubs, "ai": meta.get("ai"),
        "protected_source": meta.get("protected_source"),
        "tiles": meta.get("tiles") or [], "tiles_generated": dt.datetime.now().isoformat(timespec="seconds"),
        "web": cfg.raw.get("web", {}),
        "parcels": [{k: s.get(k) for k in ("id", "label", "fips", "url", "layer_match", "status")}
                    for s in reg.get("parcels", []) if s.get("type") == "arcgis"],
        "parcel_fields": reg.get("parcel_fields", {}), "owner_classes": reg.get("owner_classes", {}),
        "network_sources": [{k: s.get(k) for k in ("id", "label", "owner", "status")} for s in reg.get("network", [])],
        "county_outline": json.loads(cty[["fips", "name", "geometry"]]
                                     .assign(geometry=cty.geometry.simplify(0.003)).to_json()),
    }
    (out / "config.json").write_text(json.dumps(config, separators=(",", ":"), default=str))
    if meta.get("padus") is not None:
        (out / "padus.json").write_text(json.dumps({"type": "FeatureCollection", "features": meta["padus"]},
                                                   separators=(",", ":")))
    if net_payload is not None:
        (out / "network.json").write_text(json.dumps(net_payload, separators=(",", ":")))
    sizes = ", ".join(f"{p.name} {p.stat().st_size / 1e6:.2f} MB" for p in sorted(out.glob("*.json")))
    print(f"Web data -> {out} ({sizes})")


def refresh_tiles(cfg: Config, web_dir: Path = WEB_DIR) -> None:
    """Regenerate EE map tile URLs only (they expire) and patch docs/data/config.json."""
    from . import gee_layers as gl
    from .aoi import load_counties

    gl.init(cfg.gee.get("project"))
    counties = load_counties(cfg)
    aoi = gl.aoi_geometry(counties)
    stack, info = gl.build_stack(aoi, cfg)
    if cfg.ai.get("enabled", True):
        stack = stack.addBands(gl.ai_suitability(stack, aoi, cfg)[0])
    p = Path(web_dir) / "config.json"
    conf = json.loads(p.read_text())
    conf["tiles"] = gl.tile_layers(aoi, stack, info)
    conf["tiles_generated"] = dt.datetime.now().isoformat(timespec="seconds")
    p.write_text(json.dumps(conf, separators=(",", ":"), default=str))
    print(f"Tiles refreshed -> {p}")


def route_scenario(df, norm, hubs, cfg: Config, net_payload, weights, graph=None):
    """Greenbelt network for one weight set. Returns (graph, links, priority)."""
    from .routing import Graph

    g = graph or Graph(df["h3"].tolist(), net_payload)
    pr = scoring.composite(norm, weights).to_numpy()
    P = cfg.corridor
    lr = g.land_res(pr, df["protected"].fillna(0).to_numpy() * 100, norm["development"].to_numpy() * 100, P)
    cost = g.edge_cost(lr, P)
    hx = {c: i for i, c in enumerate(df["h3"])}
    parks = [{"id": h["id"], "lat": h["lat"], "lon": h["lon"], "hex": hx[h["cell"]]} for h in hubs if h["type"] == "park"]
    return g, g.greenbelt(parks, cost, lr, P), pr


def link_geometry(g, net_payload, link):
    """[(coords, kind, class)] for every edge in a routed link, oriented along the route."""
    from .network import decode_polyline

    E = net_payload["edges"]
    out = []
    for e, frm in link["edges"]:
        t = int(g.t[e])
        if t == 0:
            i = e  # network edges are first in the edge list
            c = decode_polyline(E["geom"][i])
            if g.a[e] != frm:
                c = c[::-1]
            out.append((c, "existing", net_payload["classes"][E["cls"][i]], net_payload["names"][E["name"][i]]))
        else:
            to = g.b[e] if g.a[e] == frm else g.a[e]
            out.append(([(g.lat[frm], g.lon[frm]), (g.lat[to], g.lon[to])], "new", "new", ""))
    return out


def write_gis(df, norm, hubs, cfg: Config, out: Path, net_payload=None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    gdf = df.copy()
    for k in norm:
        gdf[f"n_{k}"] = norm[k].round(4)
    graph = None
    rows = []
    for sid, sc in cfg.scenarios.items():
        pr = scoring.composite(norm, sc["weights"])
        gdf[f"p_{sid}"] = pr.round(4)
        if net_payload is None:
            continue
        graph, links, _ = route_scenario(df, norm, hubs, cfg, net_payload, sc["weights"], graph)
        cells = set()
        for L in links:
            b = graph.breakdown(L["edges"])
            for coords, kind, cls, name in link_geometry(graph, net_payload, L):
                rows.append({"scenario": sid, "from": L["from"], "to": L["to"], "kind": kind, "class": cls, "name": name,
                             "km": round(sum(haversine_km(a[0], a[1], c[0], c[1]) for a, c in zip(coords, coords[1:])), 3),
                             "link_km_existing_trail": round(b["trail"], 2), "link_km_walk_road": round(b["walk"], 2),
                             "link_km_new": round(b["new"], 2),
                             "geometry": LineString([(c[1], c[0]) for c in coords])})
                for la, lo in coords:
                    cells.add(h3.latlng_to_cell(la, lo, h3.get_resolution(df["h3"].iat[0])))
        gdf[f"corr_{sid}"] = gdf["h3"].isin(cells).astype(int)
        cand = gdf[gdf["h3"].isin(cells) & (gdf["protected"].fillna(0) < 0.5)]
        cand[["h3", "county", "state", "lat", "lon", f"p_{sid}", "protected"]] \
            .sort_values(f"p_{sid}", ascending=False) \
            .to_csv(out / f"corridor_candidates_{sid}.csv", index=False)
    if rows:
        cg = gpd.GeoDataFrame(rows, crs="EPSG:4326")
        cg.to_file(out / "corridors.gpkg", layer="segments", driver="GPKG")
        cg[cg["kind"] == "new"].drop(columns="geometry").to_csv(out / "corridor_gaps.csv", index=False)
    gdf.to_file(out / "seeds_cells.gpkg", layer="cells", driver="GPKG")
    gdf.drop(columns="geometry").to_csv(out / "seeds_cells.csv", index=False)
    print(f"GIS outputs -> {out}")
