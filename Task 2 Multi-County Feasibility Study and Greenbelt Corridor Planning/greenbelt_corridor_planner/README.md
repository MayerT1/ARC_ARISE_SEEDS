# Greenbelt Corridor Planner (SEEDS Tasks 2 + 3)

Land prioritization, Geo-AI conservation suitability, existing trail networks, land ownership and
trail-following greenbelt corridors for 12 counties in NE Alabama and SE Tennessee.

**Read [FACT_SHEET.md](FACT_SHEET.md)** for the full method, data, models, settings and limitations.

```bash
pip install -r requirements.txt
python -m seeds_cds run --project <gcp-project> --serve   # Earth Engine + trails/roads -> planner
python -m seeds_cds network --serve                       # rebuild trails/corridors only (reuses Earth Engine cache)
python -m seeds_cds sources                               # check trail / parcel endpoints
python -m seeds_cds parcels --scenario balanced           # owners along the corridor
python -m seeds_cds tiles --project <gcp-project>         # refresh Earth Engine overlays
python -m pytest -q
```

| Folder | |
|---|---|
| `config/` | `seeds.yaml` (criteria, scenarios, routing, web), `sources.yaml` (trail + parcel sources), `hubs.csv` |
| `seeds_cds/` | pipeline: `aoi`, `grid`, `gee_layers`, `aggregate`, `scoring`, `network`, `routing`, `sources`, `parcels`, `pipeline` |
| `docs/` | the website (landing page + `tool/` planner); `docs/data/` is written by the pipeline |
| `data_sources/` | drop partner trail and parcel files here |
| `feedback/` | Google Apps Script backend for map comments |
| `outputs/` | GIS exports + cache (git-ignored) |
| `tests/` | pytest: scoring, network, Python/JS routing parity, fact-sheet coverage |
