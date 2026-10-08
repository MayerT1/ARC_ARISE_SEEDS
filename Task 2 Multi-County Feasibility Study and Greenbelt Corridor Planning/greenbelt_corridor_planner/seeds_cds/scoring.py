"""Criterion normalisation and weighted-overlay priority. Mirrors docs/assets/engine.js.

Corridor routing lives in routing.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# criterion key -> (raw column, sign). sign -1 = distance-like (closer = higher score)
CRITERIA_SOURCE: dict[str, tuple[str, int]] = {
    "forest_cover": ("forest", 1),
    "canopy_height": ("canopy", 1),
    "tall_canopy": ("tall_canopy", 1),
    "ai_suitability": ("ai_suitability", 1),
    "protected_proximity": ("dist_protected", -1),
    "riparian_proximity": ("dist_water", -1),
    "terrain_relief": ("relief", 1),
    "development": ("developed", 1),
    "forest_loss": ("loss", 1),
    "road_proximity": ("dist_road", -1),
    "gateway_proximity": ("dist_gateway", -1),
    "hub_proximity": ("dist_hub", -1),
    "arc_need": ("arc_need", 1),
    "trail_density": ("trail_density", 1),
    "trail_proximity": ("dist_trail", -1),
    "walkable_proximity": ("dist_walkable", -1),
}
ABSOLUTE = {"arc_need"}  # already 0..1, categorical — not rank-transformed


def pct_rank(x: pd.Series) -> pd.Series:
    """Percentile rank 0..1 (ties averaged); NaN filled with median rank 0.5."""
    r = x.rank(pct=True, method="average")
    if r.notna().sum() > 1:
        r = (r - r.min()) / (r.max() - r.min())
    return r.fillna(0.5)


def normalize(raw: pd.DataFrame, keys: list[str] | None = None) -> pd.DataFrame:
    keys = keys or list(CRITERIA_SOURCE)
    out = {}
    for k in keys:
        col, sign = CRITERIA_SOURCE[k]
        if col not in raw:
            continue
        v = raw[col].astype(float)
        out[k] = v.clip(0, 1).fillna(0) if k in ABSOLUTE else pct_rank(sign * v)
    return pd.DataFrame(out, index=raw.index)


def composite(norm: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    w = {k: float(v) for k, v in weights.items() if k in norm and v}
    tot = sum(abs(v) for v in w.values())
    if not tot:
        return pd.Series(0.0, index=norm.index)
    s = sum(norm[k] * v for k, v in w.items()) / tot
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) if hi > lo else s * 0
