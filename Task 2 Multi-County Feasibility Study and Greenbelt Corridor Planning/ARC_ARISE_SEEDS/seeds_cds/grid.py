"""H3 hex grid over the AOI; cells assigned to counties by centroid."""
from __future__ import annotations

import geopandas as gpd
import h3
import numpy as np
from shapely.geometry import Point, Polygon


def cell_polygon(cell: str) -> Polygon:
    return Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(cell)])


def build_grid(counties: gpd.GeoDataFrame, res: int) -> gpd.GeoDataFrame:
    """Every H3 cell whose centroid falls inside a county (one county per cell)."""
    rows = []
    seen: set[str] = set()
    for c in counties.itertuples():
        # buffer slightly so edge cells with centroid inside are captured
        cells = h3.geo_to_cells(c.geometry.buffer(0.02).__geo_interface__, res)
        for cell in cells:
            if cell in seen:
                continue
            lat, lng = h3.cell_to_latlng(cell)
            if c.geometry.contains(Point(lng, lat)):
                seen.add(cell)
                rows.append(
                    dict(h3=cell, fips=c.fips, county=c.name, state=c.state,
                         arc_status=c.arc_status, arc_need=c.arc_need, lat=lat, lon=lng)
                )
    gdf = gpd.GeoDataFrame(rows, geometry=[cell_polygon(r["h3"]) for r in rows], crs="EPSG:4326")
    return gdf.sort_values("h3").reset_index(drop=True)


def neighbors(cells: list[str]) -> dict[str, list[str]]:
    s = set(cells)
    return {c: [n for n in h3.grid_disk(c, 1) if n != c and n in s] for c in cells}


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(a))


def nearest_km(lat: np.ndarray, lon: np.ndarray, pts: list[tuple[float, float]]) -> np.ndarray:
    if not pts:
        return np.full(len(lat), np.nan)
    d = np.stack([haversine_km(lat, lon, p[0], p[1]) for p in pts], axis=1)
    return d.min(axis=1)
