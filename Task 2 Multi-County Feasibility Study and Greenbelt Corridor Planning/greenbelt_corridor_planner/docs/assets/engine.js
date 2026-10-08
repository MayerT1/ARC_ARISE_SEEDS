/* SEEDS-CDS engine. Pure functions; mirrors seeds_cds/scoring.py + seeds_cds/routing.py (parity-tested).
   Exposes window.SeedsEngine (browser) / module.exports (node tests). */
(function (root) {
  "use strict";

  // ------------------------------------------------------------ priority
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
    for (let i = 0; i < n; i++) out[i] = hi > lo ? (out[i] - lo) / span : 0;
    return out;
  }

  function contributions(norm, weights, i) {
    const keys = Object.keys(weights).filter((k) => norm[k] && weights[k]);
    const tot = keys.reduce((s, k) => s + Math.abs(weights[k]), 0) || 1;
    return keys.map((k) => ({ key: k, v: (norm[k][i] / 100) * (weights[k] / tot) }))
      .sort((a, b) => Math.abs(b.v) - Math.abs(a.v));
  }

  // ------------------------------------------------------------ geometry
  function haversineKm(a, b) {
    const R = 6371.0088, r = Math.PI / 180;
    const dLat = (b[0] - a[0]) * r, dLon = (b[1] - a[1]) * r;
    const s = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(s));
  }

  function decodePolyline(str) {
    const out = []; let i = 0, lat = 0, lon = 0;
    while (i < str.length) {
      const v = [0, 0];
      for (let k = 0; k < 2; k++) {
        let shift = 0, res = 0, b;
        do { b = str.charCodeAt(i++) - 63; res |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
        v[k] = res & 1 ? ~(res >> 1) : res >> 1;
      }
      lat += v[0]; lon += v[1];
      out.push([lat / 1e5, lon / 1e5]);
    }
    return out;
  }

  // ring: [[lon,lat],...]; pt: [lon,lat]
  function pointInRing(pt, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }
  function pointInGeometry(pt, g) {
    const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
    return polys.some((p) => pointInRing(pt, p[0]) && !p.slice(1).some((h) => pointInRing(pt, h)));
  }
  // densify a [lat,lon] polyline into points every stepKm
  function densify(coords, stepKm) {
    const out = [];
    for (let i = 0; i + 1 < coords.length; i++) {
      const a = coords[i], b = coords[i + 1], d = haversineKm(a, b), n = Math.max(1, Math.ceil(d / stepKm));
      for (let k = 0; k < n; k++) out.push([a[0] + ((b[0] - a[0]) * k) / n, a[1] + ((b[1] - a[1]) * k) / n, d / n]);
    }
    return out;
  }

  // ------------------------------------------------------------ routing graph
  /* Nodes: H hex centres [0..H) + M network nodes [H..H+M).
     Edge types: 0 network, 1 gap connector, 2 hex lattice, 3 node->hex access (1-3 = new build). */
  function buildGraph(hexCenters, hexNbrs, net) {
    const H = hexCenters.length, M = net ? net.nodes.lat.length : 0;
    const lat = new Float64Array(H + M), lon = new Float64Array(H + M);
    for (let i = 0; i < H; i++) { lat[i] = hexCenters[i][0]; lon[i] = hexCenters[i][1]; }
    for (let i = 0; i < M; i++) { lat[H + i] = net.nodes.lat[i]; lon[H + i] = net.nodes.lon[i]; }
    const A = [], B = [], T = [], K = [], R = [];
    if (net) {
      const E = net.edges;
      for (let i = 0; i < E.u.length; i++) { A.push(H + E.u[i]); B.push(H + E.v[i]); T.push(0); K.push(E.km[i]); R.push(E.cls[i]); }
      const G = net.gaps;
      for (let i = 0; i < G.u.length; i++) { A.push(H + G.u[i]); B.push(H + G.v[i]); T.push(1); K.push(G.km[i]); R.push(i); }
    }
    for (let i = 0; i < H; i++) for (const j of hexNbrs[i]) if (j > i) {
      A.push(i); B.push(j); T.push(2); K.push(haversineKm([lat[i], lon[i]], [lat[j], lon[j]])); R.push(-1);
    }
    for (let i = 0; i < M; i++) {
      const h = net.nodes.hex[i];
      if (h >= 0) { A.push(h); B.push(H + i); T.push(3); K.push(haversineKm([lat[h], lon[h]], [lat[H + i], lon[H + i]])); R.push(-1); }
    }
    const nE = A.length, n = H + M;
    // CSR adjacency
    const deg = new Int32Array(n + 1);
    for (let e = 0; e < nE; e++) { deg[A[e] + 1]++; deg[B[e] + 1]++; }
    for (let i = 0; i < n; i++) deg[i + 1] += deg[i];
    const fill = deg.slice(0, n), adj = new Int32Array(2 * nE);
    for (let e = 0; e < nE; e++) { adj[fill[A[e]]++] = e; adj[fill[B[e]]++] = e; }
    return { H, M, n, lat, lon, a: Int32Array.from(A), b: Int32Array.from(B), t: Int8Array.from(T),
      km: Float64Array.from(K), ref: Int32Array.from(R), off: deg, adj,
      classes: net ? net.classes : [], gapHex: net ? net.gaps.hex : [] };
  }

  function landRes(priority, protectedPct, devPct, P) {
    const n = priority.length, r = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      let v = 0.5 + 1.5 * Math.pow(1 - priority[i], P.cost_exponent);
      if (protectedPct[i] > 50) v *= 1 - P.protected_discount;
      if (devPct && devPct[i] / 100 > P.development_barrier) v *= 10;
      r[i] = v;
    }
    return r;
  }

  function edgeCost(g, lr, P) {
    const C = P.cost, cc = g.classes.map((c) => C[c]), out = new Float64Array(g.km.length);
    for (let e = 0; e < out.length; e++) {
      const t = g.t[e];
      if (t === 0) out[e] = g.km[e] * cc[g.ref[e]];
      else if (t === 1) {
        const hx = g.gapHex[g.ref[e]]; let s = 0;
        for (const h of hx) s += lr[h];
        out[e] = g.km[e] * C.new * (s / hx.length);
      } else if (t === 2) out[e] = g.km[e] * C.new * (lr[g.a[e]] + lr[g.b[e]]) / 2;
      else out[e] = g.km[e] * C.new * lr[g.a[e]];
    }
    return out;
  }

  // starting points for a hub: its hex centre (new build) + network nodes within hub_snap_km
  function seeds(g, lat, lon, hex, lr, P) {
    const out = [];
    if (hex != null && hex >= 0) out.push([hex, haversineKm([lat, lon], [g.lat[hex], g.lon[hex]]) * P.cost.new * lr[hex]]);
    if (g.M) {
      const d = [];
      for (let i = 0; i < g.M; i++) d.push([haversineKm([lat, lon], [g.lat[g.H + i], g.lon[g.H + i]]), i]);
      d.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
      for (const [km, i] of d.slice(0, 5)) if (km <= P.hub_snap_km) out.push([g.H + i, km * P.cost.road_local]);
    }
    return out;
  }

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

  function dijkstra(g, seedList, cost) {
    const dist = new Float64Array(g.n).fill(Infinity), pe = new Int32Array(g.n).fill(-1), h = new Heap();
    for (const [s, c] of seedList) if (c < dist[s]) { dist[s] = c; h.push(c, s); }
    while (h.a.length) {
      const [d, u] = h.pop();
      if (d > dist[u]) continue;
      for (let k = g.off[u]; k < g.off[u + 1]; k++) {
        const e = g.adj[k], v = g.a[e] === u ? g.b[e] : g.a[e], nd = d + cost[e];
        if (nd < dist[v]) { dist[v] = nd; pe[v] = e; h.push(nd, v); }
      }
    }
    return { dist, pe };
  }

  // [[edge, fromNode], ...] from a seed to `end`
  function trace(g, pe, end) {
    const out = []; let v = end;
    while (pe[v] >= 0) { const e = pe[v], u = g.b[e] === v ? g.a[e] : g.b[e]; out.push([e, u]); v = u; }
    return out.reverse();
  }

  // hubs: [{id, lat, lon, hex}] -> MST links
  function greenbelt(g, hubs, cost, lr, P) {
    const S = hubs.map((h) => seeds(g, h.lat, h.lon, h.hex, lr, P));
    const runs = S.map((s) => dijkstra(g, s, cost));
    const pairs = [];
    for (let i = 0; i < hubs.length; i++) for (let j = i + 1; j < hubs.length; j++) {
      let best = Infinity, end = -1;
      for (const [s, c] of S[j]) { const v = runs[i].dist[s] + c; if (v < best) { best = v; end = s; } }
      if (isFinite(best)) pairs.push([best, i, j, end]);
    }
    pairs.sort((x, y) => x[0] - y[0] || x[1] - y[1] || x[2] - y[2]);
    const par = hubs.map((_, i) => i);
    const find = (x) => { while (par[x] !== x) { par[x] = par[par[x]]; x = par[x]; } return x; };
    const links = [];
    for (const [d, i, j, end] of pairs) {
      const ri = find(i), rj = find(j);
      if (ri === rj) continue;
      par[ri] = rj;
      const path = trace(g, runs[i].pe, end);
      links.push({ from: hubs[i].id, to: hubs[j].id, cost: d, edges: path,
        start: path.length ? path[0][1] : end, end, hubFrom: hubs[i], hubTo: hubs[j] });
    }
    return links;
  }

  function pointToPoint(g, a, b, cost, lr, P) {
    const Sa = seeds(g, a.lat, a.lon, a.hex, lr, P), Sb = seeds(g, b.lat, b.lon, b.hex, lr, P);
    const r = dijkstra(g, Sa, cost);
    let best = Infinity, end = -1;
    for (const [s, c] of Sb) { const v = r.dist[s] + c; if (v < best) { best = v; end = s; } }
    if (!isFinite(best)) return null;
    const path = trace(g, r.pe, end);
    return { from: a.id, to: b.id, cost: best, edges: path, start: path.length ? path[0][1] : end, end, hubFrom: a, hubTo: b };
  }

  const TRAILISH = new Set(["greenway", "trail"]);
  function breakdown(g, path) {
    const out = { trail: 0, walk: 0, new: 0 };
    for (const [e] of path) {
      if (g.t[e] !== 0) out.new += g.km[e];
      else if (TRAILISH.has(g.classes[g.ref[e]])) out.trail += g.km[e];
      else out.walk += g.km[e];
    }
    return out;
  }

  // ------------------------------------------------------------ parcels
  function detectFields(props, spec) {
    const keys = {}; for (const k of Object.keys(props || {})) keys[k.toUpperCase()] = k;
    const out = {};
    for (const [role, names] of Object.entries(spec || {})) {
      const hit = names.find((n) => keys[n.toUpperCase()]);
      out[role] = hit ? keys[hit.toUpperCase()] : null;
    }
    return out;
  }
  function ownerClass(owner, classes) {
    const o = String(owner || "").toUpperCase();
    for (const [name, pat] of Object.entries(classes || {})) if (new RegExp(pat).test(o)) return name;
    return "Unknown";
  }

  const api = { composite, contributions, haversineKm, decodePolyline, pointInGeometry, densify,
    buildGraph, landRes, edgeCost, seeds, dijkstra, trace, greenbelt, pointToPoint, breakdown,
    detectFields, ownerClass };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.SeedsEngine = api;
})(typeof window !== "undefined" ? window : globalThis);
