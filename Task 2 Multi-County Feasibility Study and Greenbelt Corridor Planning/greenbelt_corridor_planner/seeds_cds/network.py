"""Existing trail / walkable-road network: ingest, classify, conflate, build routing graph, export.

Classes (cheapest to most expensive to route along, see corridor.cost in seeds.yaml):
  greenway        paved shared-use path, cycleway, named greenway
  trail           natural-surface path, track, bridleway, steps, hiking/MTB route
  sidewalk        sidewalk, pedestrian street, crossing, street with mapped sidewalk
  road_local      residential / unclassified street
  road_collector  tertiary / secondary
  road_arterial   primary / trunk
Motorways and ways closed to walking (access=private/no, foot=no) are excluded.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field

import h3
import numpy as np
from shapely.geometry import LineString, Point, shape
from shapely.strtree import STRtree

CLASSES = ["greenway", "trail", "sidewalk", "road_local", "road_collector", "road_arterial"]
TRAILISH = {"greenway", "trail"}
PAVED = {"asphalt", "concrete", "paved", "paving_stones", "concrete:plates", "concrete:lanes", "sett", "chipseal"}
WALK_OK = {"yes", "designated", "permissive", "destination"}

LAT0 = 35.2  # AOI reference latitude for local metric projection
KX, KY = 111_320.0 * math.cos(math.radians(LAT0)), 110_574.0  # metres per degree


def to_xy(lat, lon):
    return np.asarray(lon) * KX, np.asarray(lat) * KY


def from_xy(x, y):
    return np.asarray(y) / KY, np.asarray(x) / KX


def hav_km(a, b) -> float:
    r = math.pi / 180
    dlat, dlon = (b[0] - a[0]) * r, (b[1] - a[1]) * r
    s = math.sin(dlat / 2) ** 2 + math.cos(a[0] * r) * math.cos(b[0] * r) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(s))


def line_km(coords) -> float:
    return sum(hav_km(a, b) for a, b in zip(coords, coords[1:]))


# ---------------------------------------------------------------- polyline codec (Google, 1e5, lat/lon)
def encode_polyline(coords) -> str:
    out, plat, plon = [], 0, 0
    for lat, lon in coords:
        ilat, ilon = round(lat * 1e5), round(lon * 1e5)
        for d in (ilat - plat, ilon - plon):
            v = ~(d << 1) if d < 0 else d << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plon = ilat, ilon
    return "".join(out)


def decode_polyline(s: str):
    coords, i, lat, lon = [], 0, 0, 0
    while i < len(s):
        vals = []
        for _ in range(2):
            shift = res = 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                res |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            vals.append(~(res >> 1) if res & 1 else res >> 1)
        lat += vals[0]
        lon += vals[1]
        coords.append((lat / 1e5, lon / 1e5))
    return coords


# ---------------------------------------------------------------- OSM parsing
def classify_osm(tags: dict, on_route: bool = False) -> str | None:
    hw = tags.get("highway")
    if not hw:
        return None
    access, foot = tags.get("access", ""), tags.get("foot", "")
    if foot == "no" or (access in ("private", "no") and foot not in WALK_OK):
        return None
    surface = tags.get("surface", "")
    paved = surface in PAVED
    name = (tags.get("name") or "").lower()
    greenwayish = bool(re.search(r"greenway|singing river|rail.?trail|riverwalk|multi.?use", name))
    if hw in ("path", "footway", "cycleway", "bridleway", "track", "steps"):
        if hw == "footway" and tags.get("footway") in ("sidewalk", "crossing", "traffic_island"):
            return "sidewalk"
        if hw == "cycleway" or greenwayish or (paved and hw in ("path", "footway") and (on_route or name)):
            return "greenway"
        if hw == "footway" and not on_route and not name and surface not in ("ground", "dirt", "gravel", "unpaved", "grass", "compacted", "fine_gravel", "earth", "rock", "wood"):
            return "sidewalk"
        return "trail"
    if hw in ("pedestrian", "living_street"):
        return "sidewalk"
    sw = tags.get("sidewalk", "") or tags.get("sidewalk:both", "")
    has_sw = sw in ("both", "left", "right", "yes")
    if hw in ("residential", "unclassified"):
        return "sidewalk" if has_sw else "road_local"
    if hw.startswith(("tertiary", "secondary")):
        return "sidewalk" if has_sw else "road_collector"
    if hw.startswith(("primary", "trunk")):
        return "road_arterial"
    return None


@dataclass
class Way:
    id: int
    nodes: list            # osm node ids (or None for official lines)
    coords: list           # [(lat, lon)]
    cls: str
    name: str = ""
    route: str = ""
    sources: set = field(default_factory=lambda: {"osm"})


def parse_osm(elements: list[dict]) -> tuple[list[Way], list[dict]]:
    route_of: dict[int, list[str]] = defaultdict(list)
    for el in elements:
        if el["type"] == "relation" and el.get("tags", {}).get("route"):
            nm = el["tags"].get("name") or el["tags"].get("ref") or ""
            for m in el.get("members", []):
                if m.get("type") == "way":
                    route_of[m["ref"]].append(nm)
    ways, walk = [], []
    for el in elements:
        t = el.get("tags", {})
        if el["type"] == "way" and "highway" in t and el.get("geometry") and el.get("nodes"):
            cls = classify_osm(t, el["id"] in route_of)
            if not cls:
                continue
            rnames = [r for r in route_of.get(el["id"], []) if r]
            coords = [(g["lat"], g["lon"]) for g in el["geometry"]]
            ways.append(Way(el["id"], el["nodes"], coords, cls, t.get("name", ""), "; ".join(sorted(set(rnames)))))
        elif ("leisure" in t or t.get("boundary") == "protected_area") and (el.get("center") or el.get("lat")):
            c = el.get("center") or {"lat": el["lat"], "lon": el["lon"]}
            walk.append({"name": t.get("name", ""), "kind": t.get("leisure") or "protected_area",
                         "lat": c["lat"], "lon": c["lon"]})
    return ways, walk


# ---------------------------------------------------------------- official lines -> conflation
def official_lines(features: list[dict], src: dict) -> tuple[list[Way], list[dict]]:
    """Return (routable official lines, planned lines for display)."""
    routable, planned = [], []
    pf = src.get("planned_field")
    for f in features:
        g = f.get("geometry")
        if not g:
            continue
        p = f.get("properties") or {}
        name = next((str(p[k]) for k in p if k.lower() in ("name", "trail_name", "trailname", "trail", "label", "mapname")
                     and p[k]), "")
        is_plan = bool(pf and pf in p and re.search(r"plan|propos|future", str(p[pf]), re.I))
        parts = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"] if g["type"] == "MultiLineString" else []
        for part in parts:
            coords = [(c[1], c[0]) for c in part]
            if len(coords) < 2:
                continue
            if is_plan:
                planned.append({"name": name, "source": src["id"], "geom": encode_polyline(coords)})
            else:
                routable.append(Way(-1, None, coords, src.get("class", "trail"), name, "",
                                    {src["id"] if src["id"] != "local_extra" else f"file:{p.get('_file', 'local')}"}))
    return routable, planned


def conflate(osm: list[Way], official: list[Way], tol_m: float, step_m: float = 25.0) -> list[Way]:
    """Tag OSM ways covered by official lines; return official pieces not already in OSM."""
    if not official:
        return []
    geoms = [LineString(np.column_stack(to_xy(*zip(*w.coords)))) for w in osm]
    tree = STRtree(geoms) if geoms else None
    added = []
    for ow in official:
        xs, ys = to_xy(*zip(*ow.coords))
        line = LineString(np.column_stack([xs, ys]))
        n = max(2, int(line.length / step_m) + 1)
        pts = [line.interpolate(i / (n - 1), normalized=True) for i in range(n)]
        matched = np.zeros(n, bool)
        if tree is not None:
            idx, dist = tree.query_nearest(pts, max_distance=tol_m, return_distance=True)
            for (pi, gi), d in zip(idx.T, dist):
                matched[pi] = True
                w = osm[gi]
                w.sources |= ow.sources
                if not w.name and ow.name:
                    w.name = ow.name
        run = []
        for i in range(n + 1):
            if i < n and not matched[i]:
                run.append(pts[i])
                continue
            if len(run) >= 3:
                lat, lon = from_xy([p.x for p in run], [p.y for p in run])
                added.append(Way(-1, None, list(zip(lat.tolist(), lon.tolist())), ow.cls, ow.name, "", set(ow.sources)))
            run = []
    return added


# ---------------------------------------------------------------- graph
@dataclass
class Network:
    lat: list
    lon: list
    edges: list            # dicts: u, v, cls, name, src(tuple), coords
    walkable: list
    planned: list
    stats: dict = field(default_factory=dict)


def build_graph(osm: list[Way], added: list[Way], snap_m: float = 40.0) -> tuple[dict, list[dict]]:
    """Split OSM ways at shared nodes, snap official additions, return (node->latlon, edges)."""
    pos: dict = {}
    use = defaultdict(int)
    for w in osm:
        for nid, c in zip(w.nodes, w.coords):
            pos[nid] = c
            use[nid] += 1
        use[w.nodes[0]] += 1
        use[w.nodes[-1]] += 1
    forced = set()
    # snap official-addition endpoints to the nearest OSM vertex
    ends = []
    if added and pos:
        ids = list(pos)
        P = [Point(*to_xy(pos[i][0], pos[i][1])) for i in ids]
        tree = STRtree(P)
        next_id = -1
        for a in added:
            ep = []
            for c in (a.coords[0], a.coords[-1]):
                q = Point(*to_xy(*c))
                hit = tree.query_nearest(q, max_distance=snap_m)
                if len(hit):
                    nid = ids[int(hit[0])]
                    forced.add(nid)
                else:
                    nid = next_id
                    next_id -= 1
                    pos[nid] = c
                ep.append(nid)
            ends.append(ep)
    elif added:
        next_id = -1
        for a in added:
            ep = []
            for c in (a.coords[0], a.coords[-1]):
                pos[next_id] = c
                ep.append(next_id)
                next_id -= 1
            ends.append(ep)

    junction = {n for n, k in use.items() if k >= 2} | forced
    edges = []
    for w in osm:
        start = 0
        for i in range(1, len(w.nodes)):
            if w.nodes[i] in junction or i == len(w.nodes) - 1:
                if w.nodes[start] != w.nodes[i] or i - start > 1:
                    edges.append(dict(u=w.nodes[start], v=w.nodes[i], cls=w.cls, name=w.name or w.route,
                                      src=tuple(sorted(w.sources)), coords=w.coords[start:i + 1]))
                start = i
    for a, (u, v) in zip(added, ends):
        coords = [pos[u]] + a.coords[1:-1] + [pos[v]]
        edges.append(dict(u=u, v=v, cls=a.cls, name=a.name, src=tuple(sorted(a.sources)), coords=coords))
    used = {e["u"] for e in edges} | {e["v"] for e in edges}
    return {n: pos[n] for n in used}, edges


def contract(edges: list[dict]) -> list[dict]:
    """Merge chains through degree-2 nodes whose two edges share class, name and sources."""
    inc = defaultdict(list)
    for i, e in enumerate(edges):
        inc[e["u"]].append(i)
        inc[e["v"]].append(i)

    def key(e):
        return (e["cls"], e["name"], e["src"])

    def passthrough(n):
        es = inc[n]
        return len(es) == 2 and es[0] != es[1] and key(edges[es[0]]) == key(edges[es[1]])

    done = [False] * len(edges)
    out = []
    for i, e in enumerate(edges):
        if done[i]:
            continue
        # walk backwards from u then forwards from v
        chain_coords = list(e["coords"])
        done[i] = True
        u, v = e["u"], e["v"]
        for direction in ("fwd", "back"):
            node = v if direction == "fwd" else u
            cur = i
            while passthrough(node) and node not in (u if direction == "fwd" else v,):
                nxt = [j for j in inc[node] if j != cur][0]
                if done[nxt]:
                    break
                done[nxt] = True
                ne = edges[nxt]
                c = ne["coords"] if ne["u"] == node else ne["coords"][::-1]
                other = ne["v"] if ne["u"] == node else ne["u"]
                if direction == "fwd":
                    chain_coords += c[1:]
                    v = other
                else:
                    chain_coords = c[::-1][:-1] + chain_coords
                    u = other
                node, cur = other, nxt
        out.append(dict(e, u=u, v=v, coords=chain_coords))
    return out


def components(nodes: list, edges: list[dict]) -> dict:
    par = {n: n for n in nodes}

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    for e in edges:
        a, b = find(e["u"]), find(e["v"])
        if a != b:
            par[a] = b
    return {n: find(n) for n in nodes}


def prune(pos: dict, edges: list[dict], min_km: float) -> tuple[dict, list[dict]]:
    comp = components(list(pos), edges)
    km = defaultdict(float)
    named = set()
    for e in edges:
        e["km"] = line_km(e["coords"])
        km[comp[e["u"]]] += e["km"]
        if e["name"] and e["cls"] in TRAILISH:
            named.add(comp[e["u"]])
    keep = {c for c, k in km.items() if k >= min_km or c in named}
    edges = [e for e in edges if comp[e["u"]] in keep]
    used = {e["u"] for e in edges} | {e["v"] for e in edges}
    return {n: pos[n] for n in used}, edges


def simplify_coords(coords, tol_m: float):
    if len(coords) <= 2 or tol_m <= 0:
        return coords
    xs, ys = to_xy(*zip(*coords))
    s = LineString(np.column_stack([xs, ys])).simplify(tol_m, preserve_topology=False)
    lat, lon = from_xy(*np.asarray(s.coords).T)
    out = list(zip(lat.tolist(), lon.tolist()))
    out[0], out[-1] = coords[0], coords[-1]  # exact endpoints keep topology
    return out


def clip_to_aoi(ways: list[Way], aoi_geom) -> list[Way]:
    from shapely.prepared import prep

    P = prep(aoi_geom)
    return [w for w in ways if P.intersects(LineString([(c[1], c[0]) for c in w.coords]))]


# ---------------------------------------------------------------- build from sources
def build_network(cfg, grid, counties, refresh=False, demo=False, hubs=None) -> Network:
    from .sources import fetch_overpass, fetch_source, load_sources

    N = cfg.raw["network"]
    if demo:
        return demo_network(grid, cfg, hubs or [])
    reg = load_sources(N.get("sources"))
    aoi = counties.geometry.union_all() if hasattr(counties.geometry, "union_all") else counties.geometry.unary_union
    buf = aoi.buffer(N.get("aoi_buffer_km", 3) / 100.0)
    w, s, e, n = buf.bounds
    osm_ways, walk, official, planned, used_src = [], [], [], [], []
    for src in reg.get("network", []):
        if src.get("enabled") is False:
            continue
        try:
            if src["type"] == "overpass":
                print(f"Network: {src['id']} (Overpass)")
                ow, wk = parse_osm(fetch_overpass((w, s, e, n), src, N.get("tile_deg", 0.25), refresh))
                osm_ways += ow
                walk += wk
                used_src.append(src["id"])
            else:
                feats = fetch_source(src, (w, s, e, n), "Polyline", refresh)
                if feats:
                    print(f"Network: {src['id']} -> {len(feats)} features")
                    r, p = official_lines(feats, src)
                    official += r
                    planned += p
                    used_src.append(src["id"])
        except Exception as ex:
            print(f"Network: {src['id']} skipped ({type(ex).__name__}: {ex})")
    allowed = set(N.get("road_classes", [])) | TRAILISH | {"sidewalk"}
    osm_ways = [x for x in clip_to_aoi(osm_ways, buf) if x.cls in allowed]
    official = clip_to_aoi(official, buf)
    print(f"Network: {len(osm_ways)} OSM ways, {len(official)} official lines, {len(walk)} walkable spaces")
    if "osm" in [x["id"] for x in reg.get("network", []) if x.get("enabled") is not False] and not osm_ways:
        raise SystemExit("OpenStreetMap returned no ways, so streets, sidewalks and most trails are missing. "
                         "Nothing was written. Check the messages above and rerun "
                         "`python -m seeds_cds network` (finished tiles are cached).")
    added = conflate(osm_ways, official, N.get("conflate_m", 20))
    pos, edges = build_graph(osm_ways, added)
    edges = contract(edges)
    pos, edges = prune(pos, edges, N.get("min_component_km", 0.3))
    for ed in edges:
        ed["coords"] = simplify_coords(ed["coords"], N.get("simplify_m", 5))
    from shapely.prepared import prep
    Pb = prep(buf)
    walk = [x for x in walk if Pb.contains(Point(x["lon"], x["lat"]))]
    net = _finalize(pos, edges, walk, planned)
    net.stats.update(sources=used_src, official_added_km=round(sum(line_km(a.coords) for a in added), 1))
    return net


def _finalize(pos: dict, edges: list[dict], walk, planned) -> Network:
    ids = sorted(pos)
    ix = {n: i for i, n in enumerate(ids)}
    for e in edges:
        e["u"], e["v"] = ix[e["u"]], ix[e["v"]]
        e["km"] = line_km(e["coords"])
    lat = [pos[n][0] for n in ids]
    lon = [pos[n][1] for n in ids]
    km = defaultdict(float)
    for e in edges:
        km[e["cls"]] += e["km"]
    return Network(lat, lon, edges, walk, planned,
                   {"nodes": len(ids), "edges": len(edges), "km_by_class": {k: round(v, 1) for k, v in km.items()}})


# ---------------------------------------------------------------- link to hex grid
def attach(net: Network, grid, res: int, cfg) -> dict:
    """Node -> hex, gap connector candidates, hex trail criteria."""
    C = cfg.raw["network"]
    idx = {h: i for i, h in enumerate(grid["h3"])}
    node_hex = [idx.get(h3.latlng_to_cell(a, b, res), -1) for a, b in zip(net.lat, net.lon)]

    # degree + component
    deg = np.zeros(len(net.lat), int)
    for e in net.edges:
        deg[e["u"]] += 1
        deg[e["v"]] += 1
    comp = components(list(range(len(net.lat))), net.edges)
    trail_nodes = set()
    for e in net.edges:
        if e["cls"] in TRAILISH:
            trail_nodes.update((e["u"], e["v"]))
    adj = defaultdict(set)
    for e in net.edges:
        adj[e["u"]].add(e["v"])
        adj[e["v"]].add(e["u"])

    # gap candidates: from trail dead-ends to nearby nodes (prefer other components)
    gaps = []
    if len(net.lat):
        X, Y = to_xy(net.lat, net.lon)
        pts = [Point(x, y) for x, y in zip(X, Y)]
        tree = STRtree(pts)
        rmax = C.get("gap_max_km", 2.5) * 1000
        k = C.get("gap_k", 4)
        seen = set()
        for a in trail_nodes:
            if deg[a] != 1:
                continue
            near = tree.query(pts[a].buffer(rmax))
            cand = []
            for b in near:
                b = int(b)
                if b == a or b in adj[a]:
                    continue
                d = math.hypot(X[a] - X[b], Y[a] - Y[b])
                if 20 <= d <= rmax:
                    cand.append((comp[a] == comp[b], d, b))
            cand.sort()
            for same, d, b in cand[:k]:
                key = (min(a, b), max(a, b))
                if key in seen:
                    continue
                seen.add(key)
                hexes = sorted({idx[c] for c in (h3.latlng_to_cell(
                    net.lat[a] + (net.lat[b] - net.lat[a]) * t, net.lon[a] + (net.lon[b] - net.lon[a]) * t, res)
                    for t in np.linspace(0, 1, max(2, int(d / 400) + 2))) if c in idx})
                gaps.append({"u": a, "v": b, "km": round(d / 1000, 4), "hex": hexes or [node_hex[a]]})

    # hex criteria
    hlat, hlon = grid["lat"].to_numpy(), grid["lon"].to_numpy()
    hx, hy = to_xy(hlat, hlon)
    centers = [Point(x, y) for x, y in zip(hx, hy)]
    trail_lines = [LineString(np.column_stack(to_xy(*zip(*e["coords"])))) for e in net.edges if e["cls"] in TRAILISH]
    if trail_lines:
        t = STRtree(trail_lines)
        _, d = t.query_nearest(centers, return_distance=True, all_matches=False)
        dist_trail = np.asarray(d) / 1000
    else:
        dist_trail = np.full(len(grid), np.nan)
    dens = np.zeros(len(grid))
    for e in net.edges:
        if e["cls"] not in TRAILISH:
            continue
        c = e["coords"]
        n = max(2, int(e["km"] / 0.05) + 1)
        seg = LineString([(b, a) for a, b in c])
        per = e["km"] / n
        for i in range(n):
            p = seg.interpolate(i / (n - 1), normalized=True)
            j = idx.get(h3.latlng_to_cell(p.y, p.x, res))
            if j is not None:
                dens[j] += per
    area = np.array([h3.cell_area(h, "km^2") for h in grid["h3"]])
    if net.walkable:
        wp = [Point(*to_xy(w["lat"], w["lon"])) for w in net.walkable]
        _, d = STRtree(wp).query_nearest(centers, return_distance=True, all_matches=False)
        dist_walk = np.asarray(d) / 1000
    else:
        dist_walk = np.full(len(grid), np.nan)
    return {"node_hex": node_hex, "gaps": gaps,
            "criteria": {"dist_trail": dist_trail, "trail_density": dens / area, "dist_walkable": dist_walk}}


def export_payload(net: Network, link: dict, cfg) -> dict:
    names, nix = [""], {"": 0}
    srcs, six = [], {}
    for e in net.edges:
        if e["name"] not in nix:
            nix[e["name"]] = len(names)
            names.append(e["name"])
        k = "|".join(e["src"])
        if k not in six:
            six[k] = len(srcs)
            srcs.append(list(e["src"]))
    cix = {c: i for i, c in enumerate(CLASSES)}
    return {
        "classes": CLASSES, "names": names, "sources": srcs,
        "nodes": {"lat": [round(v, 5) for v in net.lat], "lon": [round(v, 5) for v in net.lon], "hex": link["node_hex"]},
        "edges": {"u": [e["u"] for e in net.edges], "v": [e["v"] for e in net.edges],
                  "cls": [cix[e["cls"]] for e in net.edges], "km": [round(e["km"], 4) for e in net.edges],
                  "name": [nix[e["name"]] for e in net.edges], "src": [six["|".join(e["src"])] for e in net.edges],
                  "geom": [encode_polyline(e["coords"]) for e in net.edges]},
        "gaps": {"u": [g["u"] for g in link["gaps"]], "v": [g["v"] for g in link["gaps"]],
                 "km": [g["km"] for g in link["gaps"]], "hex": [g["hex"] for g in link["gaps"]]},
        "walkable": net.walkable, "planned": net.planned, "stats": net.stats,
    }


# ---------------------------------------------------------------- synthetic network (demo only)
def demo_network(grid, cfg, hubs) -> Network:
    """Synthetic roads between towns + trail loops at parks + a greenway. Clearly NOT real data."""
    rng = np.random.default_rng(11)
    pos, edges, nid = {}, [], [0]

    def node(lat, lon):
        nid[0] += 1
        pos[nid[0]] = (lat, lon)
        return nid[0]

    def wiggle(a, b, n, amp):
        t = np.linspace(0, 1, n)
        lat = a[0] + (b[0] - a[0]) * t + amp * np.sin(t * np.pi * rng.uniform(1, 3)) * rng.normal()
        lon = a[1] + (b[1] - a[1]) * t + amp * np.sin(t * np.pi * rng.uniform(1, 3)) * rng.normal()
        lat[0], lon[0], lat[-1], lon[-1] = a[0], a[1], b[0], b[1]
        return list(zip(lat.tolist(), lon.tolist()))

    gw = [h for h in hubs if h["type"] == "gateway"]
    pk = [h for h in hubs if h["type"] == "park"]
    town = {h["id"]: node(h["lat"], h["lon"]) for h in gw}
    # roads: each town to its 3 nearest towns
    done = set()
    for a in gw:
        near = sorted(gw, key=lambda b: hav_km((a["lat"], a["lon"]), (b["lat"], b["lon"])))[1:4]
        for b in near:
            k = tuple(sorted((a["id"], b["id"])))
            if k in done:
                continue
            done.add(k)
            d = hav_km((a["lat"], a["lon"]), (b["lat"], b["lon"]))
            cls = "road_arterial" if d > 25 else "road_collector"
            mid = node(*wiggle((a["lat"], a["lon"]), (b["lat"], b["lon"]), 3, 0.01)[1])
            for u, v in ((town[a["id"]], mid), (mid, town[b["id"]])):
                edges.append(dict(u=u, v=v, cls=cls, name=f"Synthetic Hwy {len(edges)}", src=("synthetic",),
                                  coords=wiggle(pos[u], pos[v], 8, 0.008)))
    # trails: loop + spur at each park, spur ends near (not on) the road network -> gaps to close
    for p in pk:
        c = (p["lat"], p["lon"])
        ring = [node(c[0] + 0.02 * math.sin(a), c[1] + 0.025 * math.cos(a)) for a in np.linspace(0, 2 * math.pi, 7)[:-1]]
        for i in range(len(ring)):
            u, v = ring[i], ring[(i + 1) % len(ring)]
            edges.append(dict(u=u, v=v, cls="trail", name=f"{p['name']} Loop (synthetic)", src=("synthetic",),
                              coords=wiggle(pos[u], pos[v], 6, 0.002)))
        t = min(gw, key=lambda g: hav_km(c, (g["lat"], g["lon"])))
        d = hav_km(c, (t["lat"], t["lon"]))
        f = max(0.0, 1 - 1.2 / max(d, 1e-6))  # stop ~1.2 km short of the town
        end = node(c[0] + (t["lat"] - c[0]) * f * 0.85, c[1] + (t["lon"] - c[1]) * f * 0.85)
        edges.append(dict(u=ring[0], v=end, cls="trail", name=f"{p['name']} Connector (synthetic)",
                          src=("synthetic",), coords=wiggle(pos[ring[0]], pos[end], 10, 0.004)))
    # greenway along a synthetic river (Huntsville -> Guntersville) if both exist
    if "huntsville" in town and "guntersville" in town:
        a, b = pos[town["huntsville"]], pos[town["guntersville"]]
        mid = node(*wiggle(a, b, 3, 0.03)[1])
        for u, v in ((town["huntsville"], mid), (mid, town["guntersville"])):
            edges.append(dict(u=u, v=v, cls="greenway", name="Synthetic River Greenway", src=("synthetic",),
                              coords=wiggle(pos[u], pos[v], 12, 0.006)))
    walk = [{"name": f"{p['name']} (synthetic)", "kind": "park", "lat": p["lat"], "lon": p["lon"]} for p in pk]
    net = _finalize(pos, edges, walk, [])
    net.stats["sources"] = ["synthetic"]
    return net
