"""Trail-following corridor routing. Mirrors docs/assets/engine.js (tested for parity).

Graph nodes: H hex centres (index 0..H-1) + M network nodes (H..H+M-1).
Edge types:
  0 network   existing trail/greenway/sidewalk/road edge     cost = km * cost[class]
  1 gap       straight new connector from a trail dead-end   cost = km * cost.new * mean(landRes over crossed hexes)
  2 lattice   hex centre -> neighbouring hex centre (new)    cost = km * cost.new * mean(landRes[a], landRes[b])
  3 access    network node -> its hex centre (new)           cost = km * cost.new * landRes[hex]
landRes[h] = (0.5 + 1.5 * (1 - priority[h])^k) * protected discount * development barrier
"""
from __future__ import annotations

import heapq
import math

import h3
import numpy as np

NEW_TYPES = {1, 2, 3}


def hav(lat1, lon1, lat2, lon2):
    r = math.pi / 180
    s = math.sin((lat2 - lat1) * r / 2) ** 2 + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin((lon2 - lon1) * r / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(s))


class Graph:
    def __init__(self, h3cells: list[str], net: dict):
        self.H = len(h3cells)
        idx = {c: i for i, c in enumerate(h3cells)}
        cen = [h3.cell_to_latlng(c) for c in h3cells]
        nl, no, nh = net["nodes"]["lat"], net["nodes"]["lon"], net["nodes"]["hex"]
        self.M = len(nl)
        self.lat = [c[0] for c in cen] + list(nl)
        self.lon = [c[1] for c in cen] + list(no)
        a, b, t, km, ref = [], [], [], [], []
        E = net["edges"]
        for i in range(len(E["u"])):
            a.append(self.H + E["u"][i]); b.append(self.H + E["v"][i]); t.append(0); km.append(E["km"][i]); ref.append(E["cls"][i])
        G = net["gaps"]
        for i in range(len(G["u"])):
            a.append(self.H + G["u"][i]); b.append(self.H + G["v"][i]); t.append(1); km.append(G["km"][i]); ref.append(i)
        for i, c in enumerate(h3cells):
            for n in h3.grid_disk(c, 1):
                j = idx.get(n)
                if j is not None and j > i:
                    a.append(i); b.append(j); t.append(2)
                    km.append(hav(self.lat[i], self.lon[i], self.lat[j], self.lon[j])); ref.append(-1)
        for i in range(self.M):
            h = nh[i]
            if h >= 0:
                a.append(h); b.append(self.H + i); t.append(3)
                km.append(hav(self.lat[h], self.lon[h], nl[i], no[i])); ref.append(-1)
        self.a, self.b, self.t = np.array(a), np.array(b), np.array(t)
        self.km, self.ref = np.array(km, float), np.array(ref)
        self.gap_hex = G["hex"]
        self.classes = net["classes"]
        n = self.H + self.M
        self.adj = [[] for _ in range(n)]
        for e in range(len(a)):
            self.adj[a[e]].append(e)
            self.adj[b[e]].append(e)

    # ------------------------------------------------------------ costs
    def land_res(self, priority, protected_pct, dev_pct, P):
        r = 0.5 + 1.5 * (1 - np.asarray(priority)) ** P["cost_exponent"]
        r = r * np.where(np.asarray(protected_pct) > 50, 1 - P["protected_discount"], 1.0)
        r = r * np.where(np.asarray(dev_pct) / 100 > P["development_barrier"], 10.0, 1.0)
        return r

    def edge_cost(self, lr, P) -> np.ndarray:
        C = P["cost"]
        cls_cost = np.array([C[c] for c in self.classes])
        cost = np.empty(len(self.km))
        m0 = self.t == 0
        cost[m0] = self.km[m0] * cls_cost[self.ref[m0]]
        for e in np.where(self.t == 1)[0]:
            hx = self.gap_hex[self.ref[e]]
            cost[e] = self.km[e] * C["new"] * float(np.mean(lr[hx]))
        m2 = self.t == 2
        cost[m2] = self.km[m2] * C["new"] * (lr[self.a[m2]] + lr[self.b[m2]]) / 2
        m3 = self.t == 3
        cost[m3] = self.km[m3] * C["new"] * lr[self.a[m3]]
        return cost

    def seeds(self, lat, lon, hex_idx, lr, P) -> list[tuple[int, float]]:
        C = P["cost"]
        out = []
        if hex_idx is not None and hex_idx >= 0:
            out.append((hex_idx, hav(lat, lon, self.lat[hex_idx], self.lon[hex_idx]) * C["new"] * float(lr[hex_idx])))
        if self.M:
            nl = np.array(self.lat[self.H:]); no = np.array(self.lon[self.H:])
            r = math.pi / 180
            d = 2 * 6371.0088 * np.arcsin(np.sqrt(np.sin((nl - lat) * r / 2) ** 2 + np.cos(lat * r) * np.cos(nl * r) * np.sin((no - lon) * r / 2) ** 2))
            near = np.argsort(d, kind="stable")[:5]
            for i in near:
                if d[i] <= P["hub_snap_km"]:
                    out.append((self.H + int(i), float(d[i]) * C["road_local"]))
        return out

    # ------------------------------------------------------------ search
    def dijkstra(self, seeds, cost):
        n = self.H + self.M
        dist = np.full(n, np.inf)
        pe = np.full(n, -1)
        pq = []
        for s, c in seeds:
            if c < dist[s]:
                dist[s] = c
                heapq.heappush(pq, (c, s))
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            for e in self.adj[u]:
                v = self.b[e] if self.a[e] == u else self.a[e]
                nd = d + cost[e]
                if nd < dist[v]:
                    dist[v] = nd
                    pe[v] = e
                    heapq.heappush(pq, (nd, v))
        return dist, pe

    def trace(self, pe, end) -> list[tuple[int, int]]:
        """[(edge, from_node)] from a seed to end."""
        out, v = [], end
        while pe[v] >= 0:
            e = pe[v]
            u = self.a[e] if self.b[e] == v else self.b[e]
            out.append((int(e), int(u)))
            v = u
        return out[::-1]

    def greenbelt(self, hubs, cost, lr, P):
        """hubs: [{id, lat, lon, hex}] -> MST links [{from, to, cost, edges, start, end}]."""
        S = [self.seeds(h["lat"], h["lon"], h["hex"], lr, P) for h in hubs]
        runs = [self.dijkstra(s, cost) for s in S]
        pairs = []
        for i in range(len(hubs)):
            for j in range(i + 1, len(hubs)):
                best, end = math.inf, -1
                for s, c in S[j]:
                    v = runs[i][0][s] + c
                    if v < best:
                        best, end = v, s
                if math.isfinite(best):
                    pairs.append((best, i, j, end))
        pairs.sort(key=lambda x: (x[0], x[1], x[2]))
        par = list(range(len(hubs)))

        def find(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x

        links = []
        for d, i, j, end in pairs:
            ri, rj = find(i), find(j)
            if ri == rj:
                continue
            par[ri] = rj
            path = self.trace(runs[i][1], end)
            links.append({"from": hubs[i]["id"], "to": hubs[j]["id"], "cost": d, "edges": path,
                          "start": path[0][1] if path else end, "end": end})
        return links

    def breakdown(self, path) -> dict:
        out = {"trail": 0.0, "walk": 0.0, "new": 0.0}
        for e, _ in path:
            if self.t[e] in NEW_TYPES:
                out["new"] += self.km[e]
            elif self.classes[self.ref[e]] in ("greenway", "trail"):
                out["trail"] += self.km[e]
            else:
                out["walk"] += self.km[e]
        return out
