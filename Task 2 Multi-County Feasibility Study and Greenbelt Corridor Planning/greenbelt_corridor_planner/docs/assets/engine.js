/* SEEDS-CDS engine: weighted overlay, corridor cost, Dijkstra, greenbelt MST.
   Pure functions; mirrors seeds_cds/scoring.py. Exposes window.SeedsEngine. */
(function (root) {
  "use strict";

  // norm: {key: Int[0..100]}, weights: {key: signed number} -> Float64Array 0..1 (min-max)
  function composite(norm, weights, n) {
    const keys = Object.keys(weights).filter((k) => norm[k] && weights[k]);
    const tot = keys.reduce((s, k) => s + Math.abs(weights[k]), 0);
    const out = new Float64Array(n);
    if (!tot) return out;
    for (const k of keys) {
      const w = weights[k] / tot / 100, col = norm[k];
      for (let i = 0; i < n; i++) out[i] += col[i] * w;
    }
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < n; i++) { if (out[i] < lo) lo = out[i]; if (out[i] > hi) hi = out[i]; }
    const span = hi - lo || 1;
    for (let i = 0; i < n; i++) out[i] = (out[i] - lo) / span;
    return out;
  }

  // per-criterion signed contribution for one cell (for tooltips)
  function contributions(norm, weights, i) {
    const keys = Object.keys(weights).filter((k) => norm[k] && weights[k]);
    const tot = keys.reduce((s, k) => s + Math.abs(weights[k]), 0) || 1;
    return keys.map((k) => ({ key: k, v: (norm[k][i] / 100) * (weights[k] / tot) }))
      .sort((a, b) => Math.abs(b.v) - Math.abs(a.v));
  }

  function cellCost(priority, protectedPct, devNorm, p) {
    const n = priority.length, c = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      let v = Math.pow(1 - priority[i], p.cost_exponent) + p.eps;
      if (protectedPct[i] > 50) v *= 1 - p.protected_discount;
      if (devNorm && devNorm[i] / 100 > p.development_barrier) v *= 10;
      c[i] = v;
    }
    return c;
  }

  // binary min-heap on [dist, idx]
  function Heap() { this.a = []; }
  Heap.prototype.push = function (d, i) {
    const a = this.a; a.push([d, i]); let k = a.length - 1;
    while (k) { const p = (k - 1) >> 1; if (a[p][0] <= a[k][0]) break; [a[p], a[k]] = [a[k], a[p]]; k = p; }
  };
  Heap.prototype.pop = function () {
    const a = this.a, top = a[0], last = a.pop();
    if (a.length) {
      a[0] = last; let k = 0;
      for (;;) {
        const l = 2 * k + 1, r = l + 1; let m = k;
        if (l < a.length && a[l][0] < a[m][0]) m = l;
        if (r < a.length && a[r][0] < a[m][0]) m = r;
        if (m === k) break; [a[m], a[k]] = [a[k], a[m]]; k = m;
      }
    }
    return top;
  };

  // nbrs: Array<Int32Array>, cost: Float64Array -> {dist, prev}
  function dijkstra(nbrs, cost, src) {
    const n = cost.length, dist = new Float64Array(n).fill(Infinity), prev = new Int32Array(n).fill(-1);
    const h = new Heap(); dist[src] = 0; h.push(0, src);
    while (h.a.length) {
      const [d, u] = h.pop();
      if (d > dist[u]) continue;
      const nb = nbrs[u];
      for (let j = 0; j < nb.length; j++) {
        const v = nb[j], nd = d + (cost[u] + cost[v]) / 2;
        if (nd < dist[v]) { dist[v] = nd; prev[v] = u; h.push(nd, v); }
      }
    }
    return { dist, prev };
  }

  function trace(prev, src, dst) {
    const p = [dst];
    while (p[p.length - 1] !== src) { const q = prev[p[p.length - 1]]; if (q < 0) return []; p.push(q); }
    return p.reverse();
  }

  // hubs: [{id, idx}] -> [{from, to, cost, path:[idx]}] (MST over least-cost distances, Kruskal)
  function greenbelt(nbrs, cost, hubs) {
    const runs = hubs.map((h) => dijkstra(nbrs, cost, h.idx));
    const edges = [];
    for (let a = 0; a < hubs.length; a++)
      for (let b = a + 1; b < hubs.length; b++) {
        const d = runs[a].dist[hubs[b].idx];
        if (isFinite(d)) edges.push([d, a, b]);
      }
    edges.sort((x, y) => x[0] - y[0]);
    const par = hubs.map((_, i) => i);
    const find = (x) => (par[x] === x ? x : (par[x] = find(par[x])));
    const links = [];
    for (const [d, a, b] of edges) {
      const ra = find(a), rb = find(b);
      if (ra === rb) continue;
      par[ra] = rb;
      links.push({ from: hubs[a].id, to: hubs[b].id, cost: d, path: trace(runs[a].prev, hubs[a].idx, hubs[b].idx) });
    }
    return links;
  }

  function haversineKm(a, b) {
    const R = 6371.0088, r = Math.PI / 180;
    const dLat = (b[0] - a[0]) * r, dLon = (b[1] - a[1]) * r;
    const s = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(s));
  }

  const api = { composite, contributions, cellCost, dijkstra, trace, greenbelt, haversineKm };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.SeedsEngine = api;
})(typeof window !== "undefined" ? window : globalThis);
