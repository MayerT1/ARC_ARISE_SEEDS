import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from seeds_cds import scoring
from seeds_cds.config import load_config
from seeds_cds.gee_layers import auc
from seeds_cds.grid import neighbors
from seeds_cds.pipeline import run

ROOT = Path(__file__).resolve().parents[1]
AOI = ROOT / "config" / "aoi_counties.geojson"


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    import geopandas as gpd
    from seeds_cds.aoi import counties_from_file

    cfg = load_config()
    out = tmp_path_factory.mktemp("run")
    res = run(cfg, demo=True, counties=counties_from_file(AOI, cfg), web_dir=out / "web", gis_dir=out / "gis")
    return cfg, res, out


def test_normalize_range_and_direction():
    raw = pd.DataFrame({"forest": [0.1, 0.5, 0.9], "dist_road": [10.0, 1.0, 0.1], "arc_need": [1, 0.4, 0.1]})
    n = scoring.normalize(raw)
    assert np.allclose(n["forest_cover"], [0.0, 0.5, 1.0])
    assert np.allclose(n["road_proximity"], [0.0, 0.5, 1.0])  # closer = higher
    assert n["arc_need"].tolist() == [1, 0.4, 0.1]          # absolute, not ranked


def test_composite_signed_minmax():
    norm = pd.DataFrame({"a": [0.0, 1.0, 0.5], "b": [1.0, 0.0, 0.5]})
    p = scoring.composite(norm, {"a": 1, "b": -1})
    assert p.tolist() == [0.0, 1.0, 0.5]


def test_auc():
    assert auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auc([0, 1], [0.5, 0.5]) == 0.5


def test_demo_run_outputs(demo):
    cfg, res, out = demo
    cells = json.loads((out / "web" / "cells.json").read_text())
    assert cells["meta"]["demo"] is True
    assert len(cells["h3"]) == len(res["grid"]) > 2000
    assert {c["name"] for c in cells["counties"]} == {v[0] for v in cfg.counties.values()}
    for k, col in cells["norm"].items():
        assert min(col) >= 0 and max(col) <= 100, k
    assert (out / "gis" / "seeds_cells.gpkg").exists()
    assert len(res["hubs"]) >= 25


def test_greenbelt_connects_hubs(demo):
    cfg, res, _ = demo
    df, norm = res["grid"], res["norm"]
    pr = scoring.composite(norm, cfg.scenarios["balanced"]["weights"])
    cost = scoring.cell_cost(pr, df["protected"].fillna(0), norm["development"], cfg.corridor)
    g = scoring.build_graph(df["h3"].tolist(), neighbors(df["h3"].tolist()), dict(zip(df["h3"], cost)))
    parks = {h["id"]: h["cell"] for h in res["hubs"] if h["type"] == "park"}
    links = scoring.greenbelt_network(g, parks)
    assert len(links) == len(set(parks.values())) - 1
    assert all(L["cells"] for L in links)


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_js_engine_matches_python(demo, tmp_path):
    """Composite + greenbelt MST in docs/assets/engine.js agree with scoring.py."""
    cfg, res, out = demo
    df, norm = res["grid"], res["norm"]
    w = cfg.scenarios["conservation"]["weights"]
    cells = json.loads((out / "web" / "cells.json").read_text())
    h3s = cells["h3"]
    nb = neighbors(h3s)
    idx = {h: i for i, h in enumerate(h3s)}
    parks = [h for h in res["hubs"] if h["type"] == "park"]
    seen, hubs = set(), []
    for h in parks:
        if h["cell"] not in seen:
            seen.add(h["cell"]); hubs.append({"id": h["id"], "idx": idx[h["cell"]]})
    payload = {"norm": cells["norm"], "w": w, "n": len(h3s), "prot": cells["protected"],
               "nbrs": [[idx[x] for x in nb[h]] for h in h3s], "hubs": hubs, "p": cfg.corridor}
    (tmp_path / "in.json").write_text(json.dumps(payload))
    js = f"""
    const E = require({json.dumps(str(ROOT / 'docs/assets/engine.js'))});
    const d = require({json.dumps(str(tmp_path / 'in.json'))});
    const pr = E.composite(d.norm, d.w, d.n);
    const cost = E.cellCost(pr, d.prot, d.norm.development, d.p);
    const links = E.greenbelt(d.nbrs.map(a => Int32Array.from(a)), cost, d.hubs);
    console.log(JSON.stringify({{pr: Array.from(pr), links: links.map(l => [l.from, l.to].sort().join('|')).sort()}}));
    """
    o = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)

    # python side on the same (0-100 integer) inputs the web tool sees
    n100 = pd.DataFrame({k: np.array(v) / 100 for k, v in cells["norm"].items()})
    pr = scoring.composite(n100, w)
    assert np.allclose(pr.to_numpy(), o["pr"], atol=1e-9)
    cost = scoring.cell_cost(pr, pd.Series(cells["protected"]) / 100, n100["development"], cfg.corridor)
    g = scoring.build_graph(h3s, nb, dict(zip(h3s, cost)))
    py = scoring.greenbelt_network(g, {h["id"]: h3s[h["idx"]] for h in hubs})
    assert sorted("|".join(sorted([L["from"], L["to"]])) for L in py) == o["links"]
