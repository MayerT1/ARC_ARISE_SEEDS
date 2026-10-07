"""End-to-end: AOI -> H3 grid -> raw criteria (GEE or demo) -> normalise -> web + GIS exports."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import h3
import numpy as np
import pandas as pd

from . import scoring
from .config import ROOT, Config
from .grid import build_grid, haversine_km, nearest_km, neighbors

WEB_DIR = ROOT / "docs" / "data"
GIS_DIR = ROOT / "outputs"


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
    info.pop("_layers", None)
    bands = ["forest", "developed", "relief", "canopy", "tall_canopy", "loss", "dist_water", "dist_road",
             "dist_protected", "protected", "protected_gap12"] + (["ai_suitability"] if ai else [])
    print(f"Reducing {len(bands)} bands over {len(grid)} cells ...")
    raw = reduce_cells(stack, grid, cfg, bands)
    return raw, {"source": "gee", "ai": ai, "tiles": tiles, **info}


def raw_from_demo(grid, cfg: Config) -> tuple[pd.DataFrame, dict]:
    from .demo import synth_ai_metrics, synth_raw

    return synth_raw(grid, cfg), {"source": "demo", "ai": synth_ai_metrics(),
                                  "protected_source": "synthetic"}


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
        counties=None, web_dir: Path = WEB_DIR, gis_dir: Path = GIS_DIR) -> dict:
    from .aoi import load_counties

    res = res or cfg.grid["h3_resolution"]
    src = county_source or cfg.grid.get("county_source", "gee")
    if not demo or (counties is None and src == "gee"):
        from . import gee_layers as gl
        gl.init(cfg.gee.get("project"))
    counties = counties if counties is not None else load_counties(cfg, src)
    grid = build_grid(counties, res)
    print(f"Grid: {len(grid)} H3 r{res} cells across {grid['county'].nunique()} counties")

    raw, meta = raw_from_demo(grid, cfg) if demo else raw_from_gee(grid, counties, cfg)
    df = grid.merge(raw, on="h3", how="left")
    df = add_python_criteria(df, cfg)
    norm = scoring.normalize(df)
    hubs = snap_hubs(cfg, df, res)

    write_web(df, norm, hubs, counties, cfg, meta, res, Path(web_dir))
    write_gis(df, norm, hubs, cfg, Path(gis_dir))
    return {"grid": df, "norm": norm, "hubs": hubs, "meta": meta}


# ---------------------------------------------------------------- exports
def _r(a, nd=3):
    return [None if (v is None or (isinstance(v, float) and np.isnan(v))) else round(float(v), nd) for v in a]


def write_web(df, norm, hubs, counties, cfg: Config, meta, res, out: Path) -> None:
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

    crit = {k: v for k, v in cfg.criteria.items() if k in norm}
    config = {
        "project": cfg.raw["project"], "criteria": crit, "scenarios": cfg.scenarios,
        "corridor": cfg.corridor, "hubs": hubs, "ai": meta.get("ai"),
        "protected_source": meta.get("protected_source"),
        "tiles": meta.get("tiles") or [], "tiles_generated": dt.datetime.now().isoformat(timespec="seconds"),
        "county_outline": json.loads(cty[["fips", "name", "geometry"]]
                                     .assign(geometry=cty.geometry.simplify(0.003)).to_json()),
    }
    (out / "config.json").write_text(json.dumps(config, separators=(",", ":"), default=str))
    print(f"Web data -> {out} ({(out / 'cells.json').stat().st_size / 1e6:.2f} MB cells)")


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


def write_gis(df, norm, hubs, cfg: Config, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    gdf = df.copy()
    for k in norm:
        gdf[f"n_{k}"] = norm[k].round(4)
    nb = neighbors(gdf["h3"].tolist())
    hub_cells = {h["id"]: h["cell"] for h in hubs}
    for sid, sc in cfg.scenarios.items():
        pr = scoring.composite(norm, sc["weights"])
        gdf[f"p_{sid}"] = pr.round(4)
        cost = scoring.cell_cost(pr, gdf["protected"].fillna(0), norm.get("development", pr * 0), cfg.corridor)
        g = scoring.build_graph(gdf["h3"].tolist(), nb, dict(zip(gdf["h3"], cost)))
        links = scoring.greenbelt_network(g, hub_cells)
        corridor = {c for L in links for c in L["cells"]}
        gdf[f"corr_{sid}"] = gdf["h3"].isin(corridor).astype(int)
        cand = gdf[gdf["h3"].isin(corridor) & (gdf["protected"].fillna(0) < 0.5)]
        cand[["h3", "county", "state", "lat", "lon", f"p_{sid}", "protected"]] \
            .sort_values(f"p_{sid}", ascending=False) \
            .to_csv(out / f"corridor_candidates_{sid}.csv", index=False)
    gdf.to_file(out / "seeds_cells.gpkg", layer="cells", driver="GPKG")
    gdf.drop(columns="geometry").to_csv(out / "seeds_cells.csv", index=False)
    print(f"GIS outputs -> {out}")
