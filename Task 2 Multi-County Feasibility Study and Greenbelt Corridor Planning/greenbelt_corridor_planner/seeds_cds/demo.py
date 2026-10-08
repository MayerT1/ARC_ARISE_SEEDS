"""Synthetic raw criteria for UI development / offline demo. NOT real data."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .grid import haversine_km, nearest_km

TOWNS = {  # (lat, lon, intensity, sigma_km) — synthetic urban footprint only
    "huntsville": (34.73, -86.59, 1.0, 14), "scottsboro": (34.67, -86.03, 0.5, 5),
    "guntersville": (34.36, -86.29, 0.5, 5), "mcminnville": (35.68, -85.77, 0.5, 5),
    "manchester": (35.48, -86.09, 0.45, 5), "tullahoma": (35.36, -86.21, 0.5, 6),
    "winchester": (35.19, -86.11, 0.4, 4),
}


def _field(lat, lon, rng, n=40, sigma=(6, 25)):
    f = np.zeros_like(lat)
    clat, clon = lat.mean(), lon.mean()
    for _ in range(n):
        y, x = clat + rng.uniform(-0.9, 0.9), clon + rng.uniform(-0.9, 0.9)
        s = rng.uniform(*sigma)
        f += rng.normal() * np.exp(-(haversine_km(lat, lon, y, x) ** 2) / (2 * s * s))
    return (f - f.min()) / (f.max() - f.min() + 1e-9)


def synth_raw(grid, cfg, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    lat, lon = grid["lat"].to_numpy(), grid["lon"].to_numpy()
    n = len(grid)
    noise = lambda s: rng.normal(0, s, n)  # noqa: E731

    dev = sum(a * np.exp(-(haversine_km(lat, lon, y, x) ** 2) / (2 * s * s)) for y, x, a, s in TOWNS.values())
    dev = np.clip(dev + 0.04 * _field(lat, lon, rng) + noise(0.02), 0, 1)
    plateau = _field(lat, lon, rng, n=25, sigma=(15, 40))
    forest = np.clip(0.9 - 1.2 * dev + 0.25 * (plateau - 0.5) + noise(0.08), 0, 1)

    parks = [(h.lat, h.lon) for h in cfg.hubs_of("park")]
    dpark = nearest_km(lat, lon, parks)
    protected = np.clip(np.exp(-(dpark / rng.uniform(2.5, 5.0, n)) ** 2) + noise(0.05), 0, 1)
    protected = np.where(protected > 0.25, protected, 0.0)
    gap12 = protected * (rng.random(n) < 0.6)
    pcells = protected > 0.5
    dprot = nearest_km(lat, lon, list(zip(lat[pcells], lon[pcells])))

    relief = np.clip(10 + 70 * plateau * forest + 25 * np.exp(-dpark / 8) + noise(6), 2, None)
    raw = pd.DataFrame({
        "h3": grid["h3"].to_numpy(),
        "forest": forest,
        "developed": dev,
        "relief": relief,
        "canopy": np.clip(6 + 22 * forest + noise(3), 0, 40),
        "tall_canopy": np.clip(0.9 * forest - 0.1 + noise(0.08), 0, 1),
        "loss": np.clip(0.02 + 0.15 * dev * forest + np.abs(noise(0.02)), 0, 1),
        "dist_water": np.clip(4 * _field(lat, lon, rng, n=60, sigma=(3, 8)) + np.abs(noise(0.4)), 0, None),
        "dist_road": np.clip(3.5 * (1 - dev) * forest + np.abs(noise(0.3)), 0, None),
        "dist_protected": dprot,
        "protected": protected,
        "protected_gap12": gap12,
    })
    logit = 3 * forest + 0.03 * relief - 4 * dev - 0.2 * raw["dist_road"].to_numpy() + noise(0.6) - 1.5
    raw["ai_suitability"] = 1 / (1 + np.exp(-logit))
    return raw


def synth_ai_metrics() -> dict:
    return {
        "importance": {"forest": 0.22, "relief": 0.18, "ndvi_winter": 0.14, "slope": 0.12, "developed": 0.1,
                       "dist_road": 0.08, "ndmi_summer": 0.06, "ndvi_summer": 0.04, "elevation": 0.03,
                       "dist_water": 0.02, "wetwater": 0.01},
        "auc": None, "n_test": 0, "note": "synthetic placeholder — run pipeline with GEE for real values",
    }


def synth_padus(cfg) -> list[dict]:
    """Circles around park hubs labelled as synthetic public land. NOT real ownership data."""
    import math
    feats = []
    for h in cfg.hubs_of("park"):
        r = 0.02
        ring = [[h.lon + 1.2 * r * math.cos(a), h.lat + r * math.sin(a)] for a in [i * math.pi / 12 for i in range(25)]]
        feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {"Unit_Nm": f"{h.name} (synthetic)", "Own_Type": "STAT", "Own_Name": "SDNR",
                                     "Mang_Name": "SPR", "Pub_Access": "OA", "GAP_Sts": "2", "Category": "Fee",
                                     "GIS_Acres": 900}})
    return feats
