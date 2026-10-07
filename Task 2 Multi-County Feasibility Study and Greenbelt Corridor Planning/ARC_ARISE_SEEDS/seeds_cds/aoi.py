"""County AOI loading: Earth Engine TIGER, Census cartographic boundaries, or a local file."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import shape

from .config import Config

CENSUS_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip"


def _attach_meta(gdf: gpd.GeoDataFrame, cfg: Config) -> gpd.GeoDataFrame:
    meta = cfg.counties
    gdf = gdf[gdf["fips"].isin(meta)].copy()
    missing = set(meta) - set(gdf["fips"])
    if missing:
        raise ValueError(f"Counties not found in source: {sorted(missing)}")
    gdf["name"] = gdf["fips"].map(lambda f: meta[f][0])
    gdf["state"] = gdf["fips"].map(lambda f: meta[f][1])
    gdf["arc_status"] = gdf["fips"].map(lambda f: meta[f][2])
    gdf["arc_need"] = gdf["arc_status"].map(cfg.arc_need)
    return gdf[["fips", "name", "state", "arc_status", "arc_need", "geometry"]].reset_index(drop=True)


def counties_from_gee(cfg: Config) -> gpd.GeoDataFrame:
    import ee

    fc = ee.FeatureCollection(cfg.gee["assets"]["counties"]).filter(
        ee.Filter.inList("GEOID", list(cfg.counties))
    )
    fc = fc.map(lambda f: f.simplify(30))
    feats = fc.getInfo()["features"]
    rows = [{"fips": f["properties"]["GEOID"], "geometry": shape(f["geometry"])} for f in feats]
    return _attach_meta(gpd.GeoDataFrame(rows, crs="EPSG:4326"), cfg)


def counties_from_file(path: str | Path, cfg: Config) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path).to_crs("EPSG:4326")
    for col in ("GEOID", "fips", "FIPS", "id"):
        if col in gdf.columns:
            gdf["fips"] = gdf[col].astype(str).str.zfill(5)
            break
    else:
        raise ValueError("County file needs a GEOID/fips/id column")
    return _attach_meta(gdf, cfg)


def load_counties(cfg: Config, source: str | None = None) -> gpd.GeoDataFrame:
    source = source or cfg.grid.get("county_source", "gee")
    if source == "gee":
        return counties_from_gee(cfg)
    if source == "census":
        return counties_from_file(CENSUS_URL, cfg)
    return counties_from_file(source, cfg)
