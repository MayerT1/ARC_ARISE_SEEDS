# Greenbelt Corridor Planner: Fact Sheet

**SEEDS (Southern Environmental & Economic Development Strategy) · ARC ARISE · UAH SOW Tasks 2 + 3**
**Version 0.2.2** · maintained alongside the code: every technical change updates this file (see [Keeping this document current](#20-keeping-this-document-current)).

---

## 1. At a glance

| | |
|---|---|
| **What it is** | A web map that helps planners decide which land matters most for conservation and recreation across 12 counties. It then proposes greenbelt trail corridors that reuse existing trails and shows who owns the land along them. |
| **Who it is for** | County and city planners, land trusts, state parks, tourism partners, and community members giving feedback |
| **Study area** | 12 counties in Northeast Alabama and Southeast Tennessee (section 3) |
| **SOW tasks** | Task 2: Multi-County Feasibility Study and Greenbelt Corridor Planning (Oct 2026 – Sep 2027) · Task 3: Geo-AI Decision Support Prototype (Oct 2026 – Mar 2028) |
| **Lead / partners** | Appalachian Conservation Institute (prime) · University of Alabama in Huntsville (subrecipient, technical lead) · Land Trust of North Alabama · University of the South, Sewanee · South Cumberland Tourism Partnership (advisory) |
| **Built with** | Google Earth Engine, OpenStreetMap, PAD-US, USGS / state trail layers, county parcel services, H3 hexagons, Python, Leaflet |
| **Runs as** | A static website (no server). All analysis is pre-computed by a Python pipeline, and the browser re-scores and re-routes instantly as users change settings. |

### What questions it answers

1. **Where is the most valuable land?** This covers ecology, Geo-AI similarity to already-protected land, recreation potential, tourism access, economic need, and existing trails. You choose how much each matters.
2. **How do we connect parks and gateway towns with a greenbelt?** Routes follow existing trails and greenways first, then sidewalks and quiet streets. New trail is proposed only where nothing exists.
3. **Where are the gaps, and who owns them?** Every stretch that needs new trail is listed with its length, county and land value. Public and protected owners come from PAD-US, and private parcels from county assessor data where connected.
4. **What do stakeholders think?** Anyone can drop a comment on the map. The comment saves the exact scenario they were looking at.

---

## 2. How it works, step by step

The pipeline (`python -m seeds_cds run`) runs these steps in order. The web planner then recomputes steps 7 to 9 live as users change settings.

| Step | What happens | Where |
|---|---|---|
| 1. Grid | The 12 counties are tiled with H3 hexagons at resolution 7 (~5.2 km² each, ~3,200 cells). Each cell belongs to the county containing its center. | `aoi.py`, `grid.py` |
| 2. Earth Engine criteria | Land cover, canopy height, terrain, forest loss, satellite indices, rivers, roads and protected areas are summarized as a mean for every cell. | `gee_layers.py`, `aggregate.py` |
| 3. Geo-AI suitability | A random forest learns what strictly protected land looks like and scores every 30 m pixel. The score is then averaged per cell. | `gee_layers.ai_suitability` |
| 4. Trail, road and walkable network | Trails, greenways, sidewalks, streets and parks are pulled from OpenStreetMap and official trail layers. They are merged, typed, and built into a routing network. | `sources.py`, `network.py` |
| 5. Ownership | PAD-US public and protected land is exported with owner, manager and access. County parcel services are registered for live lookup. | `gee_layers.padus_features`, `config/sources.yaml` |
| 6. Normalize | Every criterion is converted to a percentile rank from 0 to 1 across the region, so different units can be combined. | `scoring.normalize` |
| 7. Score | The user's signed weights combine criteria into one priority score (0 to 1) per cell. | `scoring.composite`, `engine.js` |
| 8. Route | Least-cost corridors run over the combined network. Existing trail is cheap, streets cost more, and new construction is expensive (cheaper through high-priority land). | `routing.py`, `engine.js` |
| 9. Screen land | Corridors are intersected with PAD-US and parcels. Gaps are listed, and private parcels on gap segments are flagged as easement or acquisition candidates. | `parcels.py`, `app.js` |
| 10. Publish | JSON for the website, plus GeoPackage and CSV files for GIS users. | `pipeline.write_web`, `write_gis` |

---

## 3. Study area

| County | State | ARC FY26 economic status | ARC need score used |
|---|---|---|---|
| Madison | AL | Competitive | 0.10 |
| Marshall | AL | Transitional | 0.40 |
| Jackson | AL | Transitional | 0.40 |
| Franklin | TN | Transitional | 0.40 |
| Grundy | TN | Distressed | 1.00 |
| Marion | TN | Transitional | 0.40 |
| Sequatchie | TN | At-Risk | 0.75 |
| Bledsoe | TN | Distressed | 1.00 |
| Warren | TN | At-Risk | 0.75 |
| Coffee | TN | Transitional | 0.40 |
| DeKalb | TN | At-Risk | 0.75 |
| Van Buren | TN | At-Risk | 0.75 |

County boundaries come from Census TIGER 2018 (`TIGER/2018/Counties` in Earth Engine). **Hubs** are the places corridors connect: 15 recreation hubs (state parks, preserves, natural areas) and 17 gateway communities, listed in `config/hubs.csv`. Hub coordinates are approximate and must be verified by partners before reporting.

---

## 4. Why hexagons, and why this size

**Why H3 hexagons rather than square pixels or parcels?**
- Every hexagon has six neighbors, all the same distance away. Squares have neighbors at two different distances (edge and corner), which bends least-cost routes toward diagonal or right-angle artifacts.
- H3 cells are nearly equal-area at a given resolution, so cell averages are comparable everywhere in the region.
- H3 is a global, open indexing system (Uber H3). The cell IDs in our exports join directly to any other H3 dataset.
- Cells are a neutral planning unit. They don't depend on parcel boundaries, which change and aren't public everywhere.

**Why resolution 7 (~5.2 km², ~1.4 km edge, ~2.4 km between centers)?**

| Resolution | Average cell area | Cells in study area | Trade-off |
|---|---|---|---|
| 6 | ~36 km² | ~460 | Too coarse: one cell can hold a ridge, a valley and a town |
| **7 (default)** | **~5.2 km²** | **~3,200** | Matches regional planning scale (cove, ridge, valley), loads fast on phones, and re-scores instantly |
| 8 | ~0.74 km² | ~21,000 | Neighborhood scale. Use for county-level studies (`--res 8`); the website gets ~6x heavier |
| 9 | ~0.11 km² | ~150,000 | Parcel scale; too heavy for a browser over 12 counties |

Corridors no longer depend on hexagon size. Since 0.2.0, routes follow the real trail and street lines, and hexagons only set the cost of building new trail where no route exists.

---

## 5. Criteria

All criteria are computed per hexagon, then ranked from 0 to 1 across the region (section 8). In the table, **Sign** is the direction that becomes a high score: + means more is higher, and − means closer or less is higher. Whether a criterion is wanted or avoided is set by the weight's sign in each scenario. Development, for example, gets a negative weight.

| Key | Label in the app | Data and method | Unit | Sign | Group |
|---|---|---|---|---|---|
| `forest_cover` | Forest cover | Share of 30 m pixels in NLCD 2021 classes 41/42/43 (deciduous, evergreen, mixed forest) | % | + | Ecology |
| `canopy_height` | Canopy height (NAIP CHM) | Mean canopy height from the NAIP 0.6 m canopy height model, masked to NLCD vegetation (41/42/43/52/90) so buildings and power lines are excluded | m | + | Ecology |
| `tall_canopy` | Tall canopy (>=10 m) | Share of vegetation pixels at least 10 m tall in the NAIP CHM (mature forest) | % | + | Ecology |
| `riparian_proximity` | Proximity to rivers/wetlands | Distance from the cell to the nearest river (HydroSHEDS free-flowing rivers), surface water present more than 50% of the time (JRC Global Surface Water) or wetland/open water (NLCD 11/90/95) | km | − | Ecology |
| `ai_suitability` | Geo-AI conservation suitability | Random-forest probability that the land resembles GAP 1–2 protected land (section 7) | 0–1 | + | Geo-AI |
| `protected_proximity` | Proximity to protected land | Distance to the nearest PAD-US fee or easement land | km | − | Connectivity |
| `terrain_relief` | Terrain relief | Standard deviation of elevation within 300 m (3DEP 10 m resampled to 30 m): bluffs, coves, gorges | m | + | Recreation |
| `road_proximity` | Road access | Distance to the nearest TIGER 2016 road | km | − | Recreation |
| `development` | Development intensity | NLCD developed classes 21/22/23/24 weighted 0.25/0.5/0.75/1.0 | % | + | Pressure (usually weighted negative) |
| `forest_loss` | Forest loss 2001-2025 | Share of pixels with any loss in Hansen Global Forest Change v1.13 | % | + | Pressure (usually weighted negative) |
| `gateway_proximity` | Gateway community access | Straight-line distance to the nearest gateway community in `hubs.csv` | km | − | Tourism |
| `hub_proximity` | Recreation hub access | Straight-line distance to the nearest recreation hub in `hubs.csv` | km | − | Tourism |
| `arc_need` | ARC economic need | County ARC status converted to a need score (section 3); not ranked | 0–1 | + | Equity |
| `trail_density` | Existing trail density | Kilometers of existing trail and greenway inside the cell divided by cell area | km/km² | + | Trails |
| `trail_proximity` | Proximity to existing trails | Distance from the cell center to the nearest existing trail or greenway | km | − | Trails |
| `walkable_proximity` | Proximity to parks & walkable spaces | Distance to the nearest OpenStreetMap park, nature reserve, recreation ground, garden, playground or protected area | km | − | Trails |

**Scenario presets** (weights can be edited in the app; `config/seeds.yaml` → `scenarios`):

| Scenario | Emphasis |
|---|---|
| `balanced` | Forest, Geo-AI, protected-land proximity, rivers, relief, gateways, ARC need and trail proximity; avoids development |
| `conservation` | Forest, canopy, tall canopy, Geo-AI, protected proximity, rivers; avoids development, roads and forest loss |
| `recreation` | Relief, gateways, existing trails, hubs, walkable spaces, forest, rivers; avoids development |
| `equity` | ARC need first, then gateways, forest, hubs, Geo-AI; avoids development |
| `stakeholder` | Placeholder for weights from the Task 1 survey. Partners can also import a weights JSON in the app. |

---

## 6. Data sources

| Dataset | Provider | Earth Engine asset or endpoint | Resolution / date | Used for |
|---|---|---|---|---|
| County boundaries | US Census TIGER | `TIGER/2018/Counties` | vector, 2018 | Study area, county assignment |
| Land cover | USGS NLCD | `USGS/NLCD_RELEASES/2021_REL/NLCD` | 30 m, 2021 | Forest, development, wetlands, vegetation mask, Geo-AI |
| Elevation | USGS 3DEP | `USGS/3DEP/10m_collection` | 10 m (resampled to 30 m) | Relief, slope, elevation, hillshade |
| Canopy height | NAIP CHM CONUS (community catalog) | `projects/naip-chm/assets/conus-structure-model` | 0.6 m; NAIP 2012–2023, 96% from 2022–2023; values stored in cm | Canopy height, tall canopy, Geo-AI predictor |
| Forest change | Univ. of Maryland (Hansen et al.) | `UMD/hansen/global_forest_change_2025_v1_13` | 30 m, 2001 to the latest year in v1.13 | Forest loss |
| Satellite imagery | ESA Copernicus Sentinel-2 | `COPERNICUS/S2_SR_HARMONIZED` | 10–20 m; summer 2023 and winter 2023–24 medians, cloud-masked with SCL | NDVI / NDMI predictors (leaf-on vs leaf-off separates evergreen and deciduous) |
| Rivers | WWF HydroSHEDS | `WWF/HydroSHEDS/v1/FreeFlowingRivers` | vector | Riparian proximity |
| Surface water | EC JRC Global Surface Water | `JRC/GSW1_4/GlobalSurfaceWater` | 30 m, 1984–2021 | Riparian proximity |
| Roads (criterion) | US Census TIGER | `TIGER/2016/Roads` | vector, 2016 | Road access criterion |
| Protected land | USGS GAP PAD-US v2.0 | `USGS/GAP/PAD-US/v20/fee`, `.../easement` | vector | Geo-AI labels, protected proximity, ownership layer, routing discount |
| Protected land (fallback) | WCMC WDPA | `WCMC/WDPA/current/polygons` | vector | Used only if PAD-US is unavailable |
| Trails, greenways, sidewalks, streets, parks | OpenStreetMap contributors (ODbL) | Overpass API | vector, live | Routing network, trail criteria, walkable spaces |
| Official trail layers | USGS National Digital Trails; TN State Parks (TDEC); Singing River Trail; LTNA; Sewanee; city/county greenways | `config/sources.yaml` | vector | Merged with OSM; adds missing segments and official names |
| Parcels | County assessors / TN Comptroller | `config/sources.yaml` → `parcels` | vector | Ownership along corridors |
| Hubs | Project partners | `config/hubs.csv` | points (approximate) | Corridor endpoints, tourism criteria |
| ARC county status | Appalachian Regional Commission | `config/seeds.yaml` → `counties` | FY26 | Equity criterion |

### Source registry status (`config/sources.yaml`)

Run `python -m seeds_cds sources` to test every endpoint from your machine. It reports reachability, the resolved layer, the feature count in the study area, field names, and whether the server allows browser (CORS) requests.

| id | Source | Type | Status |
|---|---|---|---|
| `osm` | OpenStreetMap via Overpass | overpass | verified, the backbone |
| `usgs_ndt` | USGS National Digital Trails | arcgis | verify (layer resolved by name) |
| `tn_state_park_trails` | TN State Parks trails (TDEC) | arcgis | verify |
| `singing_river_trail` | Singing River Trail alignment (built and planned) | file | needed: request GIS from Singing River Trail |
| `ltna_preserves_trails` | Land Trust of North Alabama preserve trails | file | needed: request from LTNA |
| `sewanee_domain_trails` | University of the South Domain trails | file | needed: request from Sewanee |
| `huntsville_greenways` | City of Huntsville greenways | arcgis | needed: service URL |
| `local_extra` | Any other trail files in `data_sources/trails/` | file | add as received |
| `madison_al`, `marshall_al`, `jackson_al` | AL county assessor parcels | arcgis | needed: service URLs |
| `tn_statewide` | TN Comptroller statewide parcels | arcgis | needed: service requires a token (`TNMAP_TOKEN`) |
| `local_parcels` | Parcel files (county exports, Regrid) in `data_sources/parcels/` | file | add as received |

---

## 7. The Geo-AI model

**Question it answers:** which unprotected land looks most like the land this region has already chosen to protect?

| Item | Setting | Why |
|---|---|---|
| Algorithm | Random forest (`ee.Classifier.smileRandomForest`), 300 trees, probability output | Robust with mixed predictors, no scaling needed, reports variable importance, runs inside Earth Engine |
| Positive label | Land inside PAD-US GAP status 1 or 2 (managed for biodiversity) | The region's own record of conservation-quality land |
| Background | Everything else in the study area | Presence/background design. "Not protected" does not mean "not valuable". |
| Sampling | Stratified random sample: 2,500 points per class at 90 m, seed 42 | Balanced classes; 90 m reduces spatial autocorrelation between points |
| Train/test | 70% / 30% random split | The holdout gives an honest accuracy estimate |
| Predictors | forest, developed, wetwater, elevation, slope, relief, chm_all (NAIP canopy height), ndvi_summer, ndvi_winter, ndmi_summer, dist_road, dist_water | Ecology, terrain, structure, phenology and access |
| Leakage control | Distance to protected land is **not** a predictor | Otherwise the model would just learn "near a park" |
| Metric | Area under the ROC curve (AUC) on the 30% holdout, shown in the Data tab | 0.5 = random, 1.0 = perfect. The first real run (0.1.x) scored 0.854. |
| Output | Probability per 30 m pixel, averaged per hexagon (`ai_suitability`) | |

**How to read it:** a high score on unprotected land means it resembles protected land in canopy, terrain, moisture, seasonality and remoteness. This makes it a candidate for review, not a verdict. The model inherits any bias in where land has historically been protected, such as steep plateau land being easier to protect than valley farmland.

---

## 8. From criteria to a priority score

1. **Normalize.** Each criterion is converted to its percentile rank across all cells and rescaled from 0 to 1 (ties averaged). For distance criteria, the value is negated first so closer means higher. Cells with no data get the middle value, 0.5. `arc_need` is already 0 to 1 and is used as is.
   - *Why rank instead of raw values?* Criteria have different units and skewed distributions. Ranking makes a 10-point weight mean the same thing for every criterion and stops a few extreme cells from dominating.
2. **Weight.** Priority = Σ (weight × normalized value) / Σ |weight|, then rescaled from 0 to 1 across the region. Negative weights subtract.
3. **Explain.** The tooltip on every cell shows the five criteria contributing most to its score, with raw values.

---

## 9. Existing trails, roads and walkable spaces

### What is collected

From **OpenStreetMap** (Overpass API, in 0.25° tiles, cached in `outputs/cache/`), within the counties plus a 3 km buffer:
- Ways tagged `highway` = path, footway, cycleway, bridleway, track, steps, pedestrian, living_street, residential, unclassified, tertiary(_link), secondary(_link), primary(_link), trunk(_link)
- Route relations: hiking, foot, walking, bicycle, mtb, horse. These give each way its trail-system name, such as a named state trail or greenway.
- Walkable spaces: `leisure` = park, nature_reserve, recreation_ground, garden, playground, and `boundary=protected_area`

From **official layers** in `config/sources.yaml`: ArcGIS REST services queried by bounding box with pagination, plus local files (GeoJSON, GeoPackage or Shapefile) dropped in `data_sources/trails/`.

### Classification

| Class | Rule | Default cost per km |
|---|---|---|
| `greenway` | `cycleway`; paved path or footway that is named or on a route; any path named *greenway*, *Singing River*, *rail trail*, *riverwalk* or *multi-use* | 0.08 |
| `trail` | `path`, `track`, `bridleway`, `steps` and unpaved footways not covered above; official trail layers default here | 0.12 |
| `sidewalk` | `footway=sidewalk/crossing`, pedestrian streets, living streets, residential, tertiary or secondary streets tagged with a sidewalk | 0.35 |
| `road_local` | residential, unclassified | 0.60 |
| `road_collector` | tertiary, secondary | 1.50 |
| `road_arterial` | primary, trunk | 4.00 |
| *excluded* | motorways; anything with `foot=no`; `access=private/no` unless `foot` is yes, designated, permissive or destination | — |

### Building the network
1. **Merge official layers with OSM (conflation).** Each official line is sampled every 25 m. Points within 20 m of an OSM way mark that way as confirmed by the official source and supply its name if OSM has none. Runs of 3 or more unmatched points (≥50 m) are new segments missing from OSM. They are added, and their ends are snapped to the nearest OSM node within 40 m.
2. **Planned trails** (official features whose status field says *plan*, *proposed* or *future*) are drawn as dotted lines but are **not** routable, since they don't exist yet.
3. **Split and join.** Ways are split wherever they share a node (intersections). Chains of same-class, same-name segments are then joined back into single edges.
4. **Prune.** Isolated fragments shorter than 0.3 km are dropped unless they are named trails.
5. **Simplify** display geometry to 5 m (endpoints kept exact).
6. **Gap connectors.** From every trail or greenway dead end, the 4 nearest network nodes within 2.5 km become candidate new connectors, preferring nodes on a *different* connected piece of network. These are the bridges that close gaps.

**Limits.** OSM completeness varies by county and depends on volunteers. Official layers fill gaps once partners provide them. Sidewalk mapping is sparse outside Huntsville. All of this is shown in the Data tab.

---

## 10. Corridor routing

### The routing graph
- **Network nodes and edges:** existing trails, greenways, sidewalks and streets (section 9).
- **Gap connectors:** straight new-build links from trail dead ends (section 9, step 6).
- **Hex lattice:** each hexagon center links to its 6 neighbors as new build. This lets routes cross land with no trail or street at all.
- **Access links:** each network node links to its hexagon center (new build).

### Cost of a route = Σ km × factor

| Edge | Cost per km |
|---|---|
| Existing network | `corridor.cost[class]` (table in section 9) |
| Any new build (gap connector, lattice, access) | `corridor.cost.new` (1.0) × land resistance |

**Land resistance** for new build in a cell = (0.5 + 1.5 × (1 − priority)^k) × protected discount × development barrier, where:
- k = `cost_exponent` (2). Resistance ranges from 0.5 on the best land to 2.0 on the worst.
- Protected discount: cells more than 50% protected cost × (1 − `protected_discount`), default × 0.5. Building through land already conserved is easier.
- Development barrier: cells above the `development_barrier` percentile (0.6) cost × 10, which keeps new trail out of dense development.

**What the defaults mean.** New trail costs about 4 to 17 times as much per km as using an existing trail, and a quiet street costs 5 times as much. So routes follow existing trails, take a longer trail route over a short new build when the difference is reasonable, and add new trail where it closes a real gap, ideally through high-priority land. Users can change all of these with the Routing costs sliders, and the app shows the resulting ratios.

### Hubs and the greenbelt network
- Each hub starts from its own hexagon center (new-build cost) and from up to 5 network nodes within `hub_snap_km` (1.5 km), costed as local street.
- **Greenbelt network mode:** least-cost routes are found between every pair of selected hubs (Dijkstra). The cheapest set of links connecting all of them is then kept (a minimum spanning tree, Kruskal), giving a connected greenbelt without redundant parallel routes.
- **Point-to-point mode:** a single least-cost route between two hubs or any two map points.
- The Python pipeline (`routing.py`) and the browser (`engine.js`) use identical rules. A test checks that both give the same links, costs and composition.

### What the planner reports for each corridor
- **Composition:** km on existing trail or greenway, km on sidewalks or streets, and km of new connectors, as a bar and a percentage.
- **Links:** each hub-to-hub link with length, trail share and new km.
- **Gaps to close:** each continuous new-build stretch with the features it connects, county, length and mean priority, plus a Zoom button.
- **Corridor zone:** hexagons the route touches plus one ring of neighbors, used for the candidate-cell list and statistics.

---

## 11. Land ownership and acquisition screening

**PAD-US (always on).** The pipeline exports PAD-US fee and easement polygons clipped to the study area with: unit name (`Unit_Nm`), owner type and name (`Own_Type`, `Own_Name`), manager (`Mang_Type`, `Mang_Name`), designation (`Des_Tp`), category (Fee/Easement), GAP status (`GAP_Sts`), public access (`Pub_Access`: OA open, RA restricted, XA closed, UK unknown) and acres. The Land tab lists every unit the corridor crosses with the km inside it.

**Parcels (as services are connected).**
- In the browser, *Find parcels along corridor* sends the corridor lines to each parcel service as a 30 m buffered query.
- *Parcels (live)* shows parcel lines for the current view at zoom 14 and above.
- In batch, `python -m seeds_cds parcels --scenario balanced` does the same in Python. It also works for sources that need a token or block browser requests, and for downloaded parcel files.

**Field detection.** Parcel id, owner, acres, land use, value and address are matched by common field names (`parcel_fields` in `config/sources.yaml`).

**Owner classes** (regular expressions on the owner name, first match wins): Federal, State, Local, Nonprofit, Utility, Private.

**Screening logic** for each parcel the corridor crosses:
- Private or unknown owner **and** the corridor needs new trail there → **Easement / acquisition candidate**
- Public, non-profit or utility owner with new trail → **Coordinate with owner**
- Corridor uses existing trail or street only → **On existing route**

This is a screening list for planners, not a legal or title finding.

---

## 12. Using the app

| Tab | What you do |
|---|---|
| **Priority** | Pick a scenario or move the weight sliders. *MAP* shows any single criterion. Filter by county, hide protected cells, or show the top 20%. Import or save weights as JSON. |
| **Corridors** | Choose *Greenbelt network* (pick hubs) or *Point to point* (pick or click two places). Read the composition, links and gaps. Adjust routing costs. Export the corridor GeoJSON or gaps CSV. |
| **Land** | Public and protected land on the route; parcels and owners with acquisition screening; high-priority unprotected cells near the corridor. Export parcels CSV. |
| **Counties** | Mean priority, top-20% share and existing trail km per county with ARC status. Export priority cells as GeoJSON. |
| **Data** | Geo-AI accuracy and predictor importance, network km by class, and the status of every data source. |
| **Layers** (map) | Priority hexes, existing trails and greenways, sidewalks and streets (zoom 12+), planned trails, parks, public and protected land, parcels (zoom 14+), feedback pins, Earth Engine rasters, basemap. |

**Map line key:** solid magenta = corridor on existing trail; dotted magenta = on sidewalk or street; dashed magenta = gap needing new trail; teal = greenway; brown dashed = trail; blue fill = PAD-US public or protected land.

---

## 13. Feedback

*Give feedback* → click the map → choose a topic and write a comment (name and organization are optional). Each comment saves its location, the scenario, weights, routing settings and data date, so planners can reproduce exactly what the person saw.

- **Collection:** a Google Sheet behind a Google Apps Script web app (`feedback/apps_script.gs`). There is no server to run, and the sheet owner controls the data. Set `web.feedback_endpoint` in `config/seeds.yaml`.
- **Moderation:** comments appear as map pins. Set `show` to FALSE in the sheet to hide a pin.
- **Before the endpoint is set:** the app offers a copy-ready comment and a pre-filled GitHub issue link.

---

## 14. Outputs

| File | Contents |
|---|---|
| `docs/data/cells.json` | Per-cell normalized criteria (0–100), raw values, county and protection share (web) |
| `docs/data/config.json` | Criteria, scenarios, routing settings, hubs, model metrics, tiles, sources (web) |
| `docs/data/network.json` | Routing network: nodes, edges (class, km, name, source, encoded geometry), gap connectors, walkable spaces, planned trails (web) |
| `docs/data/padus.json` | PAD-US ownership polygons (web) |
| `docs/data/parcels.json` | Optional: corridor parcels exported by the pipeline for the web |
| `outputs/seeds_cells.gpkg` / `.csv` | Every cell: raw criteria, `n_*` normalized, `p_<scenario>` priority, `corr_<scenario>` corridor flag |
| `outputs/corridors.gpkg` (layer `segments`) | Every corridor segment per scenario: kind (existing/new), class, name, km, link totals |
| `outputs/corridor_gaps.csv` | New-build segments only |
| `outputs/corridor_candidates_<scenario>.csv` | Unprotected high-priority cells on each scenario's corridor |
| `outputs/corridor_parcels_<scenario>.csv` / `.gpkg` | Parcels and PAD-US units along the corridor with owner class, km existing and new, and screening result |
| `outputs/cache/` | Cached Earth Engine results and downloaded network sources |

---

## 15. Commands

```bash
python -m seeds_cds run --project <gcp-project>     # everything (Earth Engine + network + exports)
python -m seeds_cds network                         # rebuild network + corridors, reuse cached Earth Engine
python -m seeds_cds network --refresh               # same, re-download OSM / ArcGIS sources
python -m seeds_cds sources                         # test every data source endpoint
python -m seeds_cds parcels --scenario balanced     # parcels and owners along a corridor
python -m seeds_cds tiles --project <gcp-project>   # refresh Earth Engine map overlays (they expire)
python -m seeds_cds serve                           # open the planner locally
python -m seeds_cds run --demo --counties config/aoi_counties.geojson   # synthetic data, offline
python -m pytest -q                                 # tests, including Python/JS parity and this fact sheet
```

---

## 16. Hosting

The planner is a static website: HTML, JavaScript and JSON files, with no server and no database. Any static host works.

| Option | Cost | Private repo OK | Who can open the site | Notes |
|---|---|---|---|---|
| **GitHub Pages** (recommended once the repo is public) | Free for public repos | Needs GitHub Pro/Team for private repos | Anyone with the link | `.github/workflows/pages.yml` publishes on every push to `main` |
| **Cloudflare Pages** | Free | Yes | Anyone, or only approved emails with Cloudflare Access (free up to 50 users) | Best fit for sharing with reviewers while the repo stays private |
| **Netlify** | Free tier | Yes | Anyone; password protection on paid plans | Simple drag-and-drop deploy of `docs/` |
| UAH web server | — | — | — | Copy the `docs/` folder |

**Earth Engine overlay tiles expire.** A hosted site needs them refreshed. `.github/workflows/refresh-tiles.yml` runs `python -m seeds_cds tiles` daily using an Earth Engine service account (GitHub secret `EE_SERVICE_ACCOUNT_KEY`) and commits the new URLs. Everything else on the site (priority, trails, corridors, PAD-US) is static and never expires.

**Data size at r7:** cells ~0.5 MB, network ~2–5 MB depending on how many street classes are included (`network.road_classes`), PAD-US ~0.5–2 MB. GitHub Pages and Cloudflare compress these for transfer.

---

## 17. Limitations

- Hub coordinates are approximate and need partner verification.
- OSM trail and sidewalk completeness varies. Official layers for the Singing River Trail, LTNA, Sewanee and city greenways must be supplied to be authoritative.
- Parcel ownership for the 3 Alabama counties and the 9 Tennessee counties is not connected yet (section 6 status table). PAD-US covers public and protected land only.
- Routing uses walkability classes, not slope, trail condition, legal access agreements or bridge and road-crossing feasibility. Gaps are where to look, not engineered alignments.
- Corridor resistance is a planning surface derived from priority, not a species-specific movement model.
- The Geo-AI model learns from where land *has been* protected, which reflects history and opportunity as well as ecology.
- PAD-US field names are assumed from v2.0. The export keeps whichever fields exist.

---

## 18. Adding data

- **A trail system from a partner:** save it as GeoJSON in `data_sources/trails/` (or point an `arcgis` entry at its service in `config/sources.yaml`). Set `class` (trail or greenway) and `planned_field` if it mixes built and planned segments. Then run `python -m seeds_cds network`.
- **A county parcel service:** set `url` (and `layer_match`) for the county's entry under `parcels`. Run `python -m seeds_cds sources` to confirm it answers and allows browser requests, then rerun the pipeline. If the service needs a token, set `token_env` and the environment variable, and use `python -m seeds_cds parcels`.
- **Hubs:** edit `config/hubs.csv` (id, name, type park|gateway, state, lat, lon).

---

## 19. Change log

| Version | Date | Changes |
|---|---|---|
| 0.2.2 | 2026-10-09 | Browser routing 4–5× faster on the full network (typed-array heap, early exit once all hubs are reached, bounded hub snapping): ~0.85 s for 15 hubs over ~92k nodes; local server sends no-cache headers and asset URLs carry the version so updates load without a hard refresh; page body never scrolls (panel scrolls on its own) |
| 0.2.1 | 2026-10-08 | Fixed Overpass query (OSM download failed in 0.2.0); failing OSM tiles split in 4 and retried, finished tiles cached, run stops without writing if OSM returns nothing; `sources` runs a small test query; ArcGIS layer auto-selection skips label/annotation layers and picks the layer with most features in the AOI; 403 retried with a browser User-Agent; Earth Engine project read from config or `EE_PROJECT`; map keeps a fixed size while the side panel scrolls (single-column layout below 700 px) |
| 0.2.0 | 2026-10-08 | Trail-following corridors over the real trail, sidewalk and street network (OSM + official layers) with gap connectors; corridor composition and gaps-to-close list; new criteria `trail_density`, `trail_proximity`, `walkable_proximity`; PAD-US ownership layer and route crossing table; parcel source registry with live and batch corridor parcel lookup and owner screening; map feedback with Google Sheets backend; `network`, `sources`, `parcels` commands; Earth Engine results cached; service-account auth for scheduled tile refresh; hosting workflows; this fact sheet |
| 0.1.1 | 2026-10-07 | Earth Engine overlay tiles in the app (`tiles`, `serve` commands); NAIP 0.6 m canopy height replaces GEDI; `tall_canopy` criterion; 3DEP `10m_collection`; Hansen v1.13 |
| 0.1.0 | 2026-10-07 | First release: H3 grid, Earth Engine criteria, random-forest suitability, scenario weights, hex-based least-cost greenbelt |

---

## 20. Keeping this document current

This fact sheet is part of the technical rollout. Any change to criteria, data sources, routing classes or costs, commands, or the version number must update it in the same commit. `tests/test_factsheet.py` fails the build when:
- the version here differs from `seeds_cds.__version__` or `config/seeds.yaml`
- a criterion, data source id, network class, routing cost key or CLI command exists in code but is not documented here
