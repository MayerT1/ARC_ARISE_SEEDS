"""Public data clients: Overpass (OSM), ArcGIS REST (Map/FeatureServer), local vector files.

All network calls cache raw responses under outputs/cache/ so reruns are offline.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

from .config import ROOT

CACHE = ROOT / "outputs" / "cache"
UA = "SEEDS-greenbelt-planner/0.2 (UAH; ARC ARISE SEEDS)"


def load_sources(path: str | Path | None = None) -> dict:
    path = Path(path or ROOT / "config" / "sources.yaml")
    if not path.is_absolute():
        path = ROOT / path
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------- http
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def _http(url: str, data: bytes | None = None, timeout: int = 200, tries: int = 4, headers=None) -> bytes:
    """GET/POST with retry on transient errors only; on 403 retry once with a browser User-Agent."""
    import urllib.error

    ua = UA
    k = 0
    while True:
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": ua, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 403 and ua != BROWSER_UA:
                ua = BROWSER_UA
                continue
            if e.code not in (429, 500, 502, 503, 504) or k >= tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if k >= tries - 1:
                raise
        wait = 10 * 2 ** k
        print(f"    retry in {wait}s ({url[:60]}...)")
        time.sleep(wait)
        k += 1


def _cached(key: str, fetch, refresh: bool = False):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{key}.json"
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))
    obj = fetch()
    f.write_text(json.dumps(obj), encoding="utf-8")
    return obj


# ---------------------------------------------------------------- Overpass
HIGHWAYS = ("path|footway|cycleway|bridleway|track|steps|pedestrian|living_street|residential|unclassified|"
            "tertiary|tertiary_link|secondary|secondary_link|primary|primary_link|trunk|trunk_link")


def overpass_query(s, w, n, e) -> str:
    """Ways with full geometry + node ids, route relations (tags + members), walkable spaces (centers)."""
    bb = f"{s},{w},{n},{e}"
    return f"""[out:json][timeout:300][maxsize:536870912];
way["highway"~"^({HIGHWAYS})$"]({bb});
out body geom;
relation["route"~"^(hiking|foot|walking|bicycle|mtb|horse)$"]({bb});
out body;
(
  way["leisure"~"^(park|nature_reserve|recreation_ground|garden|playground)$"]({bb});
  relation["leisure"~"^(park|nature_reserve)$"]({bb});
  way["boundary"="protected_area"]({bb});
  relation["boundary"="protected_area"]({bb});
);
out tags center;
"""


def _overpass_post(endpoint: str, q: str) -> dict:
    import urllib.error

    body = urllib.parse.urlencode({"data": q}).encode()
    try:
        raw = _http(endpoint, data=body, timeout=360,
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="ignore")
        hint = re.sub(r"<[^>]+>", " ", msg)
        hint = " ".join(hint.split())[:300]
        raise RuntimeError(f"HTTP {e.code} from {endpoint}: {hint}") from None
    out = json.loads(raw)
    if out.get("remark") and "error" in out["remark"].lower():
        raise RuntimeError(f"Overpass: {out['remark'][:300]}")
    return out


def _tiles(bbox, step):
    w, s, e, n = bbox
    out, y = [], s
    while y < n - 1e-9:
        x = w
        while x < e - 1e-9:
            out.append((round(y, 4), round(x, 4), round(min(y + step, n), 4), round(min(x + step, e), 4)))
            x += step
        y += step
    return out


def fetch_overpass(bbox: tuple[float, float, float, float], src: dict, tile_deg: float, refresh=False) -> list[dict]:
    """bbox = (west, south, east, north). Tiles the bbox; a failing tile is split into 4 and retried;
    tiles that still fail are reported and skipped (rerun later; finished tiles are cached)."""
    endpoints = src.get("endpoints", ["https://overpass-api.de/api/interpreter"])
    els, seen, failed = [], set(), []
    queue = [(t, 0) for t in _tiles(bbox, tile_deg)]
    total = len(queue)
    done = 0
    while queue:
        t, depth = queue.pop(0)
        key = "osm_" + "_".join(f"{v:.4f}" for v in t)

        def fetch(t=t):
            last = None
            for ep in endpoints:
                try:
                    return _overpass_post(ep, overpass_query(*t))
                except Exception as ex:
                    last = ex
                    print(f"    {ex}")
            raise last

        try:
            data = _cached(key, fetch, refresh)
        except Exception:
            if depth < 2:
                s_, w_, n_, e_ = t
                my, mx = (s_ + n_) / 2, (w_ + e_) / 2
                print(f"  tile {t} failed -> splitting in 4")
                queue[0:0] = [((s_, w_, my, mx), depth + 1), ((s_, mx, my, e_), depth + 1),
                              ((my, w_, n_, mx), depth + 1), ((my, mx, n_, e_), depth + 1)]
            else:
                failed.append(t)
            continue
        if depth == 0:
            done += 1
        n_new = 0
        for el in data.get("elements", []):
            k = (el["type"], el["id"])
            if k not in seen:
                seen.add(k)
                els.append(el)
                n_new += 1
        print(f"  OSM tile {done}/{total}{' (part)' if depth else ''} {t}: {n_new} new elements")
        time.sleep(1)  # be polite to the public Overpass servers
    if failed:
        print(f"  WARNING: {len(failed)} OSM tiles failed and were skipped: {failed}. Rerun to retry them.")
    return els


# ---------------------------------------------------------------- ArcGIS REST
def _arc_json(url: str, params: dict, token: str | None = None) -> dict:
    p = {"f": "json", **params}
    if token:
        p["token"] = token
    out = json.loads(_http(url + "?" + urllib.parse.urlencode(p), timeout=120))
    if isinstance(out, dict) and "error" in out:
        raise RuntimeError(f"{url}: {out['error'].get('code')} {out['error'].get('message')}")
    return out


def arcgis_layer_url(src: dict, geom_hint: str | None = None, bbox=None) -> str:
    """Resolve a service root to a layer URL: name match, geometry type, skip label/annotation
    layers, then the candidate with the most features in bbox."""
    url = src["url"].rstrip("/")
    if re.search(r"/(MapServer|FeatureServer)/\d+$", url):
        return url
    if src.get("layer") is not None:
        return f"{url}/{src['layer']}"
    token = os.environ.get(src.get("token_env", "") or "_none_")
    info = _arc_json(url, {}, token)
    layers = [L for L in (info.get("layers") or []) if not L.get("subLayerIds")]
    pat = (src.get("layer_match") or "").lower()
    skip = re.compile(src.get("layer_exclude") or r"label|anno|text|point", re.I)
    cand = [L for L in layers if pat in L.get("name", "").lower() and not skip.search(L.get("name", ""))] \
        or [L for L in layers if pat in L.get("name", "").lower()] or layers
    scored = []
    for L in cand:
        try:
            meta = _arc_json(f"{url}/{L['id']}", {}, token)
        except Exception:
            continue
        if geom_hint and geom_hint not in (meta.get("geometryType") or ""):
            continue
        n = 0
        if bbox is not None:
            try:
                n = _arc_json(f"{url}/{L['id']}/query", {"where": "1=1", "geometry": ",".join(map(str, bbox)),
                                                        "geometryType": "esriGeometryEnvelope", "inSR": 4326,
                                                        "returnCountOnly": "true"}, token).get("count", 0)
            except Exception:
                pass
        scored.append((n, -L["id"], L))
    if not scored:
        if not cand:
            raise RuntimeError(f"{url}: no layers")
        return f"{url}/{cand[0]['id']}"
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return f"{url}/{scored[0][2]['id']}"


def fetch_arcgis(src: dict, bbox, geom_hint: str | None = None, refresh=False, where="1=1") -> list[dict]:
    """GeoJSON features (EPSG:4326) intersecting bbox, paginated."""
    token = os.environ.get(src.get("token_env", "") or "_none_")
    layer = arcgis_layer_url(src, geom_hint, bbox)
    key = "arc_" + hashlib.md5(f"{layer}|{bbox}|{where}".encode()).hexdigest()[:16]

    def fetch():
        feats, off = [], 0
        meta = _arc_json(layer, {}, token)
        page = int(meta.get("maxRecordCount") or 1000)
        while True:
            q = {"where": where, "geometry": ",".join(map(str, bbox)), "geometryType": "esriGeometryEnvelope",
                 "inSR": 4326, "outSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": "*",
                 "returnGeometry": "true", "resultOffset": off, "resultRecordCount": page, "f": "geojson"}
            if token:
                q["token"] = token
            res = json.loads(_http(f"{layer}/query?" + urllib.parse.urlencode(q), timeout=180))
            if "error" in res:
                raise RuntimeError(f"{layer}: {res['error']}")
            batch = res.get("features", [])
            feats += batch
            print(f"    {src['id']}: {len(feats)} features")
            if len(batch) < page and not res.get("exceededTransferLimit") and not (
                    res.get("properties") or {}).get("exceededTransferLimit"):
                break
            off += len(batch)
            if not batch:
                break
        return {"type": "FeatureCollection", "features": feats, "layer": layer}

    return _cached(key, fetch, refresh)["features"]


# ---------------------------------------------------------------- files
def fetch_files(src: dict) -> list[dict]:
    import geopandas as gpd

    pats = src["path"] if isinstance(src["path"], list) else [src["path"]]
    feats = []
    for pat in pats:
        for f in sorted(glob.glob(str(ROOT / pat))):
            g = gpd.read_file(f).to_crs("EPSG:4326")
            g["_file"] = Path(f).stem
            feats += json.loads(g.to_json())["features"]
    return feats


def fetch_source(src: dict, bbox, geom_hint=None, refresh=False) -> list[dict]:
    t = src["type"]
    if t == "arcgis":
        if not src.get("url"):
            return []
        return fetch_arcgis(src, bbox, geom_hint, refresh)
    if t == "file":
        return fetch_files(src)
    raise ValueError(f"fetch_source does not handle type {t}")


# ---------------------------------------------------------------- field detection
def detect_fields(props: dict, spec: dict) -> dict:
    keys = {k.upper(): k for k in props}
    out = {}
    for role, names in spec.items():
        out[role] = next((keys[n.upper()] for n in names if n.upper() in keys), None)
    return out


def owner_class(owner: str | None, classes: dict) -> str:
    o = (owner or "").upper()
    for name, pat in classes.items():
        if re.search(pat, o):
            return name
    return "Unknown"


# ---------------------------------------------------------------- check
def check_sources(cfg_sources: dict, bbox) -> list[dict]:
    """Probe every arcgis/file source: reachability, resolved layer, feature count in AOI, CORS."""
    rows = []
    for group in ("network", "parcels"):
        for src in cfg_sources.get(group, []):
            r = {"group": group, "id": src["id"], "type": src["type"], "status_cfg": src.get("status")}
            try:
                if src["type"] == "overpass":
                    raw = _http(src["endpoints"][0].replace("interpreter", "status"), timeout=30)
                    test = _overpass_post(src["endpoints"][0], overpass_query(bbox[1], bbox[0], bbox[1] + 0.02, bbox[0] + 0.02))
                    r["result"] = (f"reachable ({raw.decode(errors='ignore').splitlines()[0][:40]}); "
                                   f"test query returned {len(test.get('elements', []))} elements")
                elif src["type"] == "arcgis":
                    if not src.get("url"):
                        r["result"] = "no url configured"
                    else:
                        token = os.environ.get(src.get("token_env", "") or "_none_")
                        layer = arcgis_layer_url(src, "Polyline" if group == "network" else "Polygon", bbox)
                        meta = _arc_json(layer, {}, token)
                        cnt = _arc_json(layer + "/query", {"where": "1=1", "geometry": ",".join(map(str, bbox)),
                                                           "geometryType": "esriGeometryEnvelope", "inSR": 4326,
                                                           "returnCountOnly": "true"}, token)
                        try:
                            req = urllib.request.Request(layer + "?f=json", headers={"Origin": "https://example.org", "User-Agent": BROWSER_UA})
                            with urllib.request.urlopen(req, timeout=60) as resp:
                                cors = resp.headers.get("Access-Control-Allow-Origin")
                        except Exception:
                            cors = None
                        r["result"] = (f"OK layer={layer} '{meta.get('name')}' {meta.get('geometryType')} "
                                       f"count_in_aoi={cnt.get('count')} cors={'yes' if cors else 'NO (planner must use pipeline export)'}")
                        r["fields"] = ", ".join(f["name"] for f in meta.get("fields", [])[:40])
                else:
                    n = len(fetch_files(src))
                    r["result"] = f"{n} features" if n else f"no file at {src['path']}"
            except Exception as e:
                r["result"] = f"FAIL {type(e).__name__}: {e}"
            rows.append(r)
            print(f"[{group}] {src['id']:<24} {r['result']}")
            if r.get("fields"):
                print(f"{'':27}fields: {r['fields']}")
    return rows
