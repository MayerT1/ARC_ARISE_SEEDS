"""Hex-level zonal means of the EE stack (batched reduceRegions + getInfo with retry)."""
from __future__ import annotations

import time

import ee
import pandas as pd

from .gee_layers import ALBERS


def _fc(sub) -> ee.FeatureCollection:
    return ee.FeatureCollection([
        ee.Feature(ee.Geometry.Polygon([list(map(list, geom.exterior.coords))]), {"h3": h})
        for h, geom in zip(sub["h3"], sub.geometry)
    ])


def _getinfo(obj, tries: int = 5):
    for k in range(tries):
        try:
            return obj.getInfo()
        except ee.EEException as e:  # quota / timeout / computation timed out
            if k == tries - 1:
                raise
            wait = 2 ** k * 5
            print(f"  EE error ({e}); retry in {wait}s")
            time.sleep(wait)


def reduce_cells(stack: ee.Image, grid, cfg, bands: list[str] | None = None) -> pd.DataFrame:
    G = cfg.gee
    img = stack.select(bands) if bands else stack
    rows = []
    bs = G["batch_size"]
    n = len(grid)
    for i in range(0, n, bs):
        sub = grid.iloc[i : i + bs]
        red = img.reduceRegions(
            collection=_fc(sub), reducer=ee.Reducer.mean(),
            scale=G["scale"], crs=ALBERS, tileScale=G["tile_scale"],
        ).map(lambda f: ee.Feature(None, f.toDictionary()))
        out = _getinfo(red)
        rows += [f["properties"] for f in out["features"]]
        print(f"  reduced {min(i + bs, n)}/{n} cells")
    return pd.DataFrame(rows)
