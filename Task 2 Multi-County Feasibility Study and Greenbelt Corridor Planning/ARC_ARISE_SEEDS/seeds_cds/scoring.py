"""Criterion normalisation, weighted-overlay priority, least-cost corridors, greenbelt network.

Mirrors docs/assets/engine.js so Python outputs and the web tool agree.
"""
from __future__ import annotations

import heapq

import networkx as nx
import numpy as np
import pandas as pd

from .grid import haversine_km

# criterion key -> (raw column, sign). sign -1 = distance-like (closer = higher score)
CRITERIA_SOURCE: dict[str, tuple[str, int]] = {
    "forest_cover": ("forest", 1),
    "canopy_height": ("canopy", 1),
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


def cell_cost(priority: pd.Series, protected_frac: pd.Series, development: pd.Series, p: dict) -> pd.Series:
    c = (1 - priority) ** p["cost_exponent"] + p["eps"]
    c = c * np.where(protected_frac > 0.5, 1 - p["protected_discount"], 1.0)
    c = c * np.where(development > p["development_barrier"], 10.0, 1.0)
    return pd.Series(c, index=priority.index)


def build_graph(cells: list[str], nbrs: dict[str, list[str]], cost: dict[str, float]) -> nx.Graph:
    g = nx.Graph()
    for u in cells:
        for v in nbrs[u]:
            if u < v:
                g.add_edge(u, v, w=(cost[u] + cost[v]) / 2)
    return g


def dijkstra(g: nx.Graph, src: str) -> tuple[dict, dict]:
    dist, prev, pq = {src: 0.0}, {}, [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, np.inf):
            continue
        for v, e in g[u].items():
            nd = d + e["w"]
            if nd < dist.get(v, np.inf):
                dist[v], prev[v] = nd, u
                heapq.heappush(pq, (nd, v))
    return dist, prev


def trace(prev: dict, src: str, dst: str) -> list[str]:
    path = [dst]
    while path[-1] != src:
        if path[-1] not in prev:
            return []
        path.append(prev[path[-1]])
    return path[::-1]


def path_length_km(path: list[str], lat: dict, lon: dict) -> float:
    return float(sum(haversine_km(lat[a], lon[a], lat[b], lon[b]) for a, b in zip(path, path[1:])))


def greenbelt_network(g: nx.Graph, hub_cells: dict[str, str]) -> list[dict]:
    """Least-cost paths between all hub pairs -> MST over path costs -> list of links."""
    ids = [h for h, c in hub_cells.items() if c in g]
    runs = {h: dijkstra(g, hub_cells[h]) for h in ids}
    k = nx.Graph()
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d = runs[a][0].get(hub_cells[b])
            if d is not None:
                k.add_edge(a, b, w=d)
    links = []
    for a, b in nx.minimum_spanning_tree(k, weight="w").edges():
        path = trace(runs[a][1], hub_cells[a], hub_cells[b])
        links.append({"from": a, "to": b, "cost": k[a][b]["w"], "cells": path})
    return links
