"""Trail/road network: OSM parsing, classification, conflation, graph build, routing preference."""
import json
import shutil
import subprocess
from pathlib import Path

import h3
import numpy as np
import pytest

from seeds_cds import network as nw
from seeds_cds.routing import Graph

ROOT = Path(__file__).resolve().parents[1]


def way(i, nodes, tags, lat0=35.0, lon0=-86.0, step=0.001):
    return {"type": "way", "id": i, "nodes": nodes, "tags": tags,
            "geometry": [{"lat": lat0 + 0 * k, "lon": lon0 + n * step} for k, n in enumerate(nodes)]}


def fixture():
    # nodes along a line at lon = -86 + id*0.001; roads 1-2-3, trail 3-4-5-6, sidewalk 2-7, private track 6-8
    return [
        way(1, [1, 2, 3], {"highway": "residential", "name": "Oak St"}),
        way(2, [3, 4, 5], {"highway": "path", "surface": "dirt", "name": "Ridge Trail"}),
        way(3, [5, 6], {"highway": "path", "surface": "dirt", "name": "Ridge Trail"}),
        way(4, [2, 7], {"highway": "footway", "footway": "sidewalk"}),
        way(5, [6, 8], {"highway": "track", "access": "private"}),
        way(6, [6, 9], {"highway": "cycleway", "name": "Big Spring Greenway"}),
        {"type": "relation", "id": 99, "tags": {"route": "hiking", "name": "Great Ridge Route"},
         "members": [{"type": "way", "ref": 2}, {"type": "way", "ref": 3}]},
        {"type": "way", "id": 50, "tags": {"leisure": "park", "name": "Ridge Park"}, "center": {"lat": 35.0, "lon": -85.995}},
    ]


def test_classify():
    c = nw.classify_osm
    assert c({"highway": "footway", "footway": "sidewalk"}) == "sidewalk"
    assert c({"highway": "cycleway"}) == "greenway"
    assert c({"highway": "path", "surface": "asphalt", "name": "Singing River Trail"}) == "greenway"
    assert c({"highway": "path", "surface": "dirt"}) == "trail"
    assert c({"highway": "track", "access": "private"}) is None
    assert c({"highway": "track", "access": "private", "foot": "designated"}) == "trail"
    assert c({"highway": "residential"}) == "road_local"
    assert c({"highway": "residential", "sidewalk": "both"}) == "sidewalk"
    assert c({"highway": "primary"}) == "road_arterial"
    assert c({"highway": "path", "foot": "no"}) is None


def test_parse_build_contract():
    ways, walk = nw.parse_osm(fixture())
    assert {w.id for w in ways} == {1, 2, 3, 4, 6}                 # private track dropped
    assert any(w.route == "Great Ridge Route" for w in ways)
    assert walk[0]["name"] == "Ridge Park"
    pos, edges = nw.build_graph(ways, [])
    # junctions: 2 (road+sidewalk), 3 (road+trail), 5 (way split), 6 (trail+greenway)
    edges = nw.contract(edges)
    trail = [e for e in edges if e["name"] == "Ridge Trail"]
    assert len(trail) == 1 and {trail[0]["u"], trail[0]["v"]} == {3, 6}   # 3-4-5 + 5-6 merged through node 5
    assert len(trail[0]["coords"]) == 4


def test_conflate_tags_and_adds():
    ways, _ = nw.parse_osm(fixture())
    # official line overlapping Ridge Trail and extending 1 km east past node 9
    off = nw.Way(-1, None, [(35.0, -86.0 + 0.003), (35.0, -86.0 + 0.009), (35.0, -86.0 + 0.020)], "trail",
                 "Ridge Trail (official)", "", {"tn_state_park_trails"})
    added = nw.conflate(ways, [off], tol_m=20)
    assert any("tn_state_park_trails" in w.sources for w in ways if w.name == "Ridge Trail")
    assert len(added) == 1 and nw.line_km(added[0].coords) > 0.8


def test_polyline_roundtrip():
    c = [(35.12345, -86.54321), (35.2, -86.4), (34.99999, -85.00001)]
    assert nw.decode_polyline(nw.encode_polyline(c)) == c


def _toy_graph():
    """3x? hex patch: hub A and hub B with a winding existing trail between them vs a straight new build."""
    a = h3.latlng_to_cell(35.0, -86.0, 7)
    cells = sorted(h3.grid_disk(a, 4))
    lat0, lon0 = h3.cell_to_latlng(a)
    b_lat, b_lon = lat0, lon0 + 0.12
    # trail detours north (~1.6x straight length)
    pts = [(lat0, lon0), (lat0 + 0.04, lon0 + 0.03), (lat0 + 0.05, lon0 + 0.06), (lat0 + 0.04, lon0 + 0.09), (b_lat, b_lon)]
    idx = {c: i for i, c in enumerate(cells)}
    net = {"classes": nw.CLASSES,
           "nodes": {"lat": [p[0] for p in pts], "lon": [p[1] for p in pts],
                     "hex": [idx.get(h3.latlng_to_cell(p[0], p[1], 7), -1) for p in pts]},
           "edges": {"u": [0, 1, 2, 3], "v": [1, 2, 3, 4], "cls": [1, 1, 1, 1],
                     "km": [nw.hav_km(pts[i], pts[i + 1]) for i in range(4)], "name": [0] * 4, "src": [0] * 4,
                     "geom": [nw.encode_polyline([pts[i], pts[i + 1]]) for i in range(4)]},
           "gaps": {"u": [], "v": [], "km": [], "hex": []}}
    return cells, net, (lat0, lon0), (b_lat, b_lon)


P = {"cost": {"greenway": 0.08, "trail": 0.12, "sidewalk": 0.35, "road_local": 0.6, "road_collector": 1.5,
              "road_arterial": 4.0, "new": 1.0},
     "cost_exponent": 2, "protected_discount": 0.5, "development_barrier": 0.6, "hub_snap_km": 1.5}


def test_route_prefers_existing_trail():
    cells, net, A, B = _toy_graph()
    g = Graph(cells, net)
    lr = g.land_res(np.full(len(cells), 0.5), np.zeros(len(cells)), np.zeros(len(cells)), P)
    cost = g.edge_cost(lr, P)
    idx = {c: i for i, c in enumerate(cells)}
    hubs = [{"id": "A", "lat": A[0], "lon": A[1], "hex": idx[h3.latlng_to_cell(*A, 7)]},
            {"id": "B", "lat": B[0], "lon": B[1], "hex": idx.get(h3.latlng_to_cell(*B, 7), -1)}]
    link = g.greenbelt(hubs, cost, lr, P)[0]
    b = g.breakdown(link["edges"])
    assert b["trail"] > 10 and b["new"] < 0.5
    # make new construction nearly free -> straight new build wins
    P2 = {**P, "cost": {**P["cost"], "new": 0.01}}
    link2 = g.greenbelt(hubs, g.edge_cost(lr, P2), lr, P2)[0]
    assert g.breakdown(link2["edges"])["trail"] < b["trail"]


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    from seeds_cds.aoi import counties_from_file
    from seeds_cds.config import load_config
    from seeds_cds.pipeline import run

    cfg = load_config()
    out = tmp_path_factory.mktemp("run")
    res = run(cfg, demo=True, counties=counties_from_file(ROOT / "config" / "aoi_counties.geojson", cfg),
              web_dir=out / "web", gis_dir=out / "gis")
    return cfg, res, out


def test_demo_outputs(demo):
    cfg, res, out = demo
    cells = json.loads((out / "web" / "cells.json").read_text())
    assert cells["meta"]["demo"] is True and len(cells["h3"]) > 2000
    for k in ("trail_density", "trail_proximity", "walkable_proximity"):
        assert k in cells["norm"]
    netj = json.loads((out / "web" / "network.json").read_text())
    assert len(netj["edges"]["u"]) > 50 and len(netj["gaps"]["u"]) > 0
    assert (out / "web" / "padus.json").exists() and (out / "gis" / "corridors.gpkg").exists()


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_js_engine_matches_python(demo, tmp_path):
    """Composite + trail-network greenbelt in docs/assets/engine.js agree with routing.py."""
    import pandas as pd
    from seeds_cds import scoring

    cfg, res, out = demo
    cells = json.loads((out / "web" / "cells.json").read_text())
    netj = json.loads((out / "web" / "network.json").read_text())
    h3s = cells["h3"]
    idx = {h: i for i, h in enumerate(h3s)}
    w = cfg.scenarios["recreation"]["weights"]
    Pc = cfg.corridor
    hubs = [{"id": h["id"], "lat": h["lat"], "lon": h["lon"], "hex": idx[h["cell"]]} for h in res["hubs"] if h["type"] == "park"]
    payload = {"norm": cells["norm"], "w": w, "n": len(h3s), "prot": cells["protected"], "h3": h3s, "net": netj,
               "hubs": hubs, "P": Pc}
    (tmp_path / "in.json").write_text(json.dumps(payload))
    js = f"""
    const h3 = require({json.dumps(str(ROOT / 'docs/assets/vendor/h3-js.umd.js'))});
    const E = require({json.dumps(str(ROOT / 'docs/assets/engine.js'))});
    const d = require({json.dumps(str(tmp_path / 'in.json'))});
    const ix = new Map(d.h3.map((h, i) => [h, i]));
    const cen = d.h3.map(h => h3.cellToLatLng(h));
    const nb = d.h3.map(h => h3.gridDisk(h, 1).filter(x => x !== h && ix.has(x)).map(x => ix.get(x)));
    const g = E.buildGraph(cen, nb, d.net);
    const pr = E.composite(d.norm, d.w, d.n);
    const lr = E.landRes(pr, d.prot, d.norm.development, d.P);
    const cost = E.edgeCost(g, lr, d.P);
    const links = E.greenbelt(g, d.hubs, cost, lr, d.P);
    console.log(JSON.stringify({{pr: Array.from(pr),
      links: links.map(l => ({{k: [l.from, l.to].sort().join('|'), c: l.cost, b: E.breakdown(g, l.edges)}}))}}));
    """
    o = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)

    n100 = pd.DataFrame({k: np.array(v) / 100 for k, v in cells["norm"].items()})
    pr = scoring.composite(n100, w).to_numpy()
    assert np.allclose(pr, o["pr"], atol=1e-9)
    g = Graph(h3s, netj)
    lr = g.land_res(pr, np.array(cells["protected"]), np.array(cells["norm"]["development"]), Pc)
    links = g.greenbelt(hubs, g.edge_cost(lr, Pc), lr, Pc)
    py = {"|".join(sorted([L["from"], L["to"]])): L for L in links}
    js_links = {L["k"]: L for L in o["links"]}
    assert set(py) == set(js_links)
    for k, L in py.items():
        assert abs(L["cost"] - js_links[k]["c"]) < 1e-6 * max(1, L["cost"])
        b = g.breakdown(L["edges"])
        assert all(abs(b[t] - js_links[k]["b"][t]) < 1e-6 for t in b)


def test_padus_polygons_only():
    from seeds_cds.gee_layers import _polygons_only
    sq = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
    gc = {"type": "GeometryCollection", "geometries": [sq, {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}]}
    assert _polygons_only(gc)["type"] == "MultiPolygon" and len(_polygons_only(gc)["coordinates"]) == 1
    assert _polygons_only({"type": "LineString", "coordinates": [[0, 0], [1, 1]]}) is None
    assert _polygons_only(None) is None
