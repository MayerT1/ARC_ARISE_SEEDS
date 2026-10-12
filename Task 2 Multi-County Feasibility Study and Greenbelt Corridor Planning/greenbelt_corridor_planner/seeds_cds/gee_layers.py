"""Earth Engine criterion stack + Geo-AI (random forest) conservation suitability.

All images are lazy; nothing is computed until aggregate.reduce_cells() pulls hex means.
"""
from __future__ import annotations

import ee

ALBERS = "EPSG:5070"


# ---------------------------------------------------------------- setup
def init(project: str | None = None) -> None:
    """Initialise Earth Engine. Uses a service account when EE_SERVICE_ACCOUNT_KEY is set
    (JSON key text or a path to the key file; used by the scheduled GitHub Action)."""
    import json
    import os

    key = os.environ.get("EE_SERVICE_ACCOUNT_KEY")
    if key:
        info = json.loads(open(key).read() if os.path.exists(key) else key)
        creds = ee.ServiceAccountCredentials(info["client_email"], key_data=json.dumps(info))
        ee.Initialize(creds, project=project or info.get("project_id"))
        return
    project = project or os.environ.get("EE_PROJECT")
    if not project:
        raise SystemExit("Earth Engine project not set. Use --project <gcp-project>, set gee.project in "
                         "config/seeds.yaml, or set the EE_PROJECT environment variable.")
    try:
        ee.Initialize(project=project)
    except ee.EEException as e:
        if "not registered" in str(e) or "Not signed up" in str(e):
            raise SystemExit(f"Earth Engine refused project '{project}': {e}")
        ee.Authenticate()
        ee.Initialize(project=project)
    except Exception:  # first run on a machine / Colab
        ee.Authenticate()
        ee.Initialize(project=project)


def asset_ok(asset_id: str) -> bool:
    try:
        ee.data.getAsset(asset_id)
        return True
    except Exception:
        return False


def aoi_geometry(counties_gdf) -> ee.Geometry:
    geom = counties_gdf.geometry.union_all() if hasattr(counties_gdf.geometry, "union_all") \
        else counties_gdf.geometry.unary_union
    return ee.Geometry(geom.buffer(0.01).simplify(0.002).__geo_interface__)


# ---------------------------------------------------------------- helpers
def _proj(scale: float) -> ee.Projection:
    return ee.Projection(ALBERS).atScale(scale)


def distance_km(source: ee.Image, scale: float, nbhd: int) -> ee.Image:
    """Euclidean distance (km) to nearest non-zero pixel, computed on an Albers grid."""
    p = _proj(scale)
    m = source.unmask(0).gt(0).reproject(p)
    return m.fastDistanceTransform(nbhd).sqrt().multiply(scale / 1000.0).reproject(p)


def s2_indices(aoi, asset, start, end, max_cloud) -> ee.Image:
    def mask(img):
        scl = img.select("SCL")
        keep = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(7)).Or(scl.eq(11))
        return img.updateMask(keep)

    med = (
        ee.ImageCollection(asset).filterBounds(aoi).filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
        .map(mask).select(["B4", "B8", "B11"]).median()
    )
    return ee.Image.cat(
        med.normalizedDifference(["B8", "B4"]).rename("ndvi"),
        med.normalizedDifference(["B8", "B11"]).rename("ndmi"),
    )


def protected_layers(aoi, A: dict) -> tuple[ee.Image, ee.Image, str]:
    """(any protection, GAP 1-2 protection) as 0/1 images + source label."""
    if asset_ok(A["padus_fee"]):
        fcs = [ee.FeatureCollection(A["padus_fee"]).filterBounds(aoi)]
        if asset_ok(A.get("padus_easement", "")):
            fcs.append(ee.FeatureCollection(A["padus_easement"]).filterBounds(aoi))
        allp = ee.FeatureCollection(fcs).flatten()
        gap = allp.filter(ee.Filter.inList(A.get("padus_gap_field", "GAP_Sts"), ["1", "2"]))
        src = "PAD-US v2.0 fee+easement"
    else:
        allp = ee.FeatureCollection(A["wdpa_fallback"]).filterBounds(aoi)
        gap = allp.filter(ee.Filter.inList("IUCN_CAT", ["Ia", "Ib", "II", "III", "IV"]))
        src = "WDPA (PAD-US unavailable)"
    paint = lambda fc: ee.Image(0).byte().paint(fc, 1)  # noqa: E731
    return paint(allp), paint(gap), src


# ---------------------------------------------------------------- stack
def build_stack(aoi: ee.Geometry, cfg) -> tuple[ee.Image, dict]:
    G, A = cfg.gee, cfg.gee["assets"]
    ds, nb = G["distance_scale"], G["distance_neighborhood"]
    info: dict = {}

    nlcd = ee.ImageCollection(A["nlcd"]).sort("system:time_start", False).first().select("landcover")
    forest = nlcd.remap([41, 42, 43], [1, 1, 1], 0).rename("forest")
    developed = nlcd.remap([21, 22, 23, 24], [0.25, 0.5, 0.75, 1.0], 0).rename("developed")
    wetwater = nlcd.remap([11, 90, 95], [1, 1, 1], 0).rename("wetwater")

    dem = dem_mosaic(aoi, A["dem"])
    dem30 = dem.reduceResolution(ee.Reducer.mean(), maxPixels=64).reproject(_proj(30))
    slope = ee.Terrain.slope(dem30).rename("slope")
    relief = dem30.reduceNeighborhood(ee.Reducer.stdDev(), ee.Kernel.circle(300, "meters")).rename("relief")

    chm = naip_chm(aoi, A["naip_chm"])                      # m, all elevated features
    veg = nlcd.remap([41, 42, 43, 52, 90], [1, 1, 1, 1, 1], 0).eq(1)
    canopy = chm.updateMask(veg).rename("canopy")          # vegetation-only canopy height
    tall = chm.gte(10).And(veg).rename("tall_canopy")      # 0/1 -> cell mean = fraction

    hansen = ee.Image(A["hansen"])
    loss = hansen.select("loss").updateMask(hansen.select("datamask").eq(1)).rename("loss")

    s2s = s2_indices(aoi, A["s2"], *G["s2_window"]["summer"], G["max_cloud_pct"])
    s2w = s2_indices(aoi, A["s2"], *G["s2_window"]["winter"], G["max_cloud_pct"])

    roads = ee.FeatureCollection(A["roads"]).filterBounds(aoi)
    rivers = ee.FeatureCollection(A["rivers"]).filterBounds(aoi)
    jrc = ee.Image(A["jrc_water"]).select("occurrence").gt(50)
    water_src = ee.Image(0).byte().paint(rivers, 1).Or(jrc.unmask(0)).Or(wetwater)

    prot, gap12, psrc = protected_layers(aoi, A)
    info["protected_source"] = psrc

    stack = ee.Image.cat(
        forest, developed, wetwater,
        dem30.rename("elevation"), slope, relief,
        canopy, tall, chm.unmask(0).rename("chm_all"), loss,
        s2s.select("ndvi").rename("ndvi_summer"), s2s.select("ndmi").rename("ndmi_summer"),
        s2w.select("ndvi").rename("ndvi_winter"),
        distance_km(ee.Image(0).byte().paint(roads, 1), ds, nb).rename("dist_road"),
        distance_km(water_src, ds, nb).rename("dist_water"),
        distance_km(prot, ds, nb).rename("dist_protected"),
        prot.rename("protected"), gap12.rename("protected_gap12"),
    ).clip(aoi)
    info["_layers"] = {"nlcd": nlcd, "dem30": dem30, "chm": chm, "hansen": hansen, "prot": prot, "gap12": gap12}
    return stack, info


def dem_mosaic(aoi, asset: str) -> ee.Image:
    """3DEP 10m_collection mosaic with a real (10 m) default projection."""
    col = ee.ImageCollection(asset).filterBounds(aoi).select("elevation")
    return col.mosaic().setDefaultProjection(col.first().projection())


def naip_chm(aoi, asset: str) -> ee.Image:
    """NAIP CHM CONUS (gee-community-catalog): uint16 cm, nodata 65535 -> metres."""
    col = ee.ImageCollection(asset).filterBounds(aoi)
    first = col.first()
    img = col.mosaic().setDefaultProjection(first.projection())
    return img.updateMask(img.neq(65535)).divide(100).rename("chm")


# ---------------------------------------------------------------- map tiles for the web tool
VIRIDIS = ["440154", "482777", "3f4a8a", "31688e", "26828e", "1f9e89", "35b779", "6ece58", "fde725"]


def tile_layers(aoi: ee.Geometry, stack: ee.Image, info: dict) -> list[dict]:
    """getMapId tile URL templates for raster overlays. URLs expire; rerun `seeds_cds tiles` to refresh."""
    L = info["_layers"]
    defs = [
        ("naip_chm", "Canopy height, NAIP CHM 0.6 m (m)", L["chm"].clip(aoi),
         {"min": 0, "max": 30, "palette": VIRIDIS}),
        ("nlcd", "NLCD land cover", L["nlcd"].clip(aoi), {}),
        ("hillshade", "Hillshade, 3DEP 10 m", ee.Terrain.hillshade(L["dem30"]).clip(aoi), {"min": 120, "max": 230}),
        ("forest_loss", "Forest loss year 2001-2025 (Hansen)",
         L["hansen"].select("lossyear").selfMask().clip(aoi), {"min": 1, "max": 25, "palette": ["fee08b", "f46d43", "a50026"]}),
        ("protected", "Protected land (GAP 1-2 dark, all light)",
         L["prot"].add(L["gap12"]).selfMask().clip(aoi), {"min": 1, "max": 2, "palette": ["9ecae1", "08519c"]}),
    ]
    if "ai_suitability" in stack.bandNames().getInfo():
        defs.insert(0, ("ai_suitability", "Geo-AI conservation suitability (RF prob.)",
                        stack.select("ai_suitability"), {"min": 0, "max": 1, "palette": VIRIDIS}))
    out = []
    for key, label, img, vis in defs:
        try:
            url = img.getMapId(vis)["tile_fetcher"].url_format
            out.append({"key": key, "label": label, "url": url})
            print(f"  tiles: {key}")
        except Exception as e:  # one bad layer shouldn't kill the run
            print(f"  tiles: {key} skipped ({e})")
    return out


# ---------------------------------------------------------------- Geo-AI
def ai_suitability(stack: ee.Image, aoi: ee.Geometry, cfg) -> tuple[ee.Image, dict]:
    """RF presence/background model: where does unprotected land look like GAP 1-2 land?

    Returns probability image and a lazy dict of diagnostics (importance + test preds).
    """
    C = cfg.ai
    preds = C["predictors"]
    X = stack.select(preds)
    label = stack.select("protected_gap12").rename("label").toInt()

    samples = X.addBands(label).stratifiedSample(
        numPoints=C["points_per_class"], classBand="label", region=aoi,
        scale=C["sample_scale"], seed=C["seed"], geometries=False, tileScale=4,
    ).randomColumn("rand", C["seed"])
    train = samples.filter(ee.Filter.lt("rand", C["train_fraction"]))
    test = samples.filter(ee.Filter.gte("rand", C["train_fraction"]))

    clf = (
        ee.Classifier.smileRandomForest(numberOfTrees=C["n_trees"], seed=C["seed"])
        .setOutputMode("PROBABILITY").train(train, "label", preds)
    )
    prob = X.classify(clf).rename("ai_suitability")
    diag = {
        "importance": ee.Dictionary(clf.explain()).get("importance"),
        "test": test.classify(clf, "p").select(["label", "p"]),
    }
    return prob, diag


def ai_metrics(diag: dict) -> dict:
    """Pull RF diagnostics client-side: normalised importance + holdout AUC."""
    imp = ee.Dictionary(diag["importance"]).getInfo() or {}
    tot = sum(imp.values()) or 1.0
    imp = {k: round(v / tot, 4) for k, v in sorted(imp.items(), key=lambda kv: -kv[1])}
    t = diag["test"]
    y = t.aggregate_array("label").getInfo()
    p = t.aggregate_array("p").getInfo()
    return {"importance": imp, "auc": round(auc(y, p), 4), "n_test": len(y)}


def auc(y, p) -> float:
    """Mann-Whitney AUC, no sklearn dependency."""
    pairs = sorted(zip(p, y))
    ranks, i = [0.0] * len(pairs), 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        for k in range(i, j + 1):
            ranks[k] = (i + j) / 2 + 1
        i = j + 1
    n1 = sum(1 for _, yy in pairs if yy == 1)
    n0 = len(pairs) - n1
    if not n1 or not n0:
        return float("nan")
    r1 = sum(r for r, (_, yy) in zip(ranks, pairs) if yy == 1)
    return (r1 - n1 * (n1 + 1) / 2) / (n1 * n0)


# ---------------------------------------------------------------- PAD-US ownership export (web layer)
PADUS_PROPS = ["Unit_Nm", "Loc_Nm", "Own_Type", "Own_Name", "Loc_Own", "Mang_Type", "Mang_Name", "Loc_Mang",
               "Des_Tp", "Category", "GAP_Sts", "Pub_Access", "GIS_Acres", "EsmtHldr"]


def padus_features(aoi: ee.Geometry, A: dict, page: int = 2000) -> list[dict]:
    """PAD-US fee + easement polygons clipped to the AOI, simplified, with ownership attributes."""
    feats = []
    for key, cat in (("padus_fee", "Fee"), ("padus_easement", "Easement")):
        asset = A.get(key)
        if not asset or not asset_ok(asset):
            continue
        fc = ee.FeatureCollection(asset).filterBounds(aoi)
        n = fc.size().getInfo()
        if not n:
            continue
        names = set(ee.Feature(fc.first()).propertyNames().getInfo())
        keep = [p for p in PADUS_PROPS if p in names]

        def clean(f, keep=keep, cat=cat):
            g = f.geometry().intersection(aoi, 30).simplify(30)
            return ee.Feature(g, f.toDictionary(keep)).set("Category", cat)

        lst = fc.map(clean).toList(n)
        for off in range(0, n, page):
            got = ee.FeatureCollection(lst.slice(off, off + page)).getInfo()["features"]
            feats += [f for f in got if f.get("geometry")]
        print(f"  PAD-US {cat}: {n} units")
    out = []
    for f in feats:
        f.pop("id", None)
        g = _polygons_only(f.get("geometry"))
        if g:
            f["geometry"] = g
            out.append(f)
    return out


def _polygons_only(g):
    """Keep polygon parts of a geometry (EE intersections can return GeometryCollections)."""
    if not g:
        return None
    t = g.get("type")
    if t in ("Polygon", "MultiPolygon"):
        return g
    if t == "GeometryCollection":
        polys = []
        for x in g.get("geometries", []):
            p = _polygons_only(x)
            if p:
                polys += [p["coordinates"]] if p["type"] == "Polygon" else p["coordinates"]
        return {"type": "MultiPolygon", "coordinates": polys} if polys else None
    return None
