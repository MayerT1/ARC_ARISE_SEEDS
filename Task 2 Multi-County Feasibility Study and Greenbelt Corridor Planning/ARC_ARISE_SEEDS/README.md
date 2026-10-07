# ARC ARISE · SEEDS — UAH technical tools

Southern Environmental & Economic Development Strategy (SEEDS). 12 counties in NE Alabama and SE Tennessee. Period: Oct 2026 – Apr 2028.

| SOW task | Status | Where |
|---|---|---|
| T1 Stakeholder consultation & survey design | in design | exports weights JSON → planner |
| **T2 Feasibility study & greenbelt corridor planning** | **v0.1** | `seeds_cds/` pipeline + `docs/tool/` |
| **T3 Geo-AI decision support prototype** | **v0.1** | same tool (folded together) |
| T4 Economic impact assessment design | in design | – |
| T5 Economic impact projection tool | planned | – |

## Greenbelt Corridor Planner (Tasks 2 + 3)

```
counties ─► H3 grid (r7 ≈ 5 km², ~3.2k cells)
        ─► Earth Engine criterion stack ─► hex zonal means
             NLCD · 3DEP · GEDI RH98 · Hansen GFC · S2 NDVI/NDMI · TIGER roads · HydroSHEDS · PAD-US
        ─► Geo-AI: RF suitability (GAP 1-2 vs background; no distance-to-protected predictor)
        ─► percentile-normalised criteria ─► docs/data/*.json  +  outputs/*.gpkg|csv
web tool (static, GitHub Pages):
   signed scenario weights ─► composite priority ─► cell resistance (1-p)^k
   ─► least-cost paths on hex graph ─► greenbelt network = MST over hubs
   ─► corridor zone + unprotected high-priority candidate cells
```

### Run

```bash
pip install -r requirements.txt
earthengine authenticate                       # once

python -m seeds_cds run --project <gcp-project>          # real data -> docs/data + outputs/
python -m seeds_cds run --res 8 --project <gcp-project>  # ~21k cells
python -m seeds_cds run --demo --counties config/aoi_counties.geojson   # synthetic, offline
python -m pytest -q                                       # includes JS<->Python engine parity
```

Colab: `notebooks/01_run_pipeline.ipynb`.

Windows (Command Prompt):

```bat
cd C:\Users\Mayer\Documents\GitHub\ARC_ARISE_SEEDS
python -m seeds_cds run --project <gcp-project>
git add docs/data outputs && git commit -m "Refresh criteria" && git push
```

### Configure

- `config/seeds.yaml`: counties and ARC status, GEE assets, RF settings, criteria, **scenario weights**, corridor parameters.
- `config/hubs.csv`: recreation hubs and gateway communities. **Coordinates are approximate. Verify them before reporting.**
- Stakeholder (Task 1) input: in the tool, use **Import stakeholder weights** with a JSON like `{"scenario": "Grundy Co. workshop", "weights": {"forest_cover": 20, "development": -15}}`. You can also edit the `stakeholder` scenario in `seeds.yaml`.

### Outputs

| File | Use |
|---|---|
| `docs/data/cells.json`, `config.json` | web tool data (columnar, ~0.4 MB at r7) |
| `outputs/seeds_cells.gpkg` / `.csv` | every criterion (`n_*`), priority per scenario (`p_*`), corridor flag (`corr_*`) |
| `outputs/corridor_candidates_<scenario>.csv` | unprotected corridor cells ranked by priority, for easement or acquisition review |

`outputs/` is git-ignored except when you choose to commit it.

### Publish (GitHub Pages)

Settings → Pages → Deploy from branch → `main` / `/docs`. The site is then at `https://mayert1.github.io/ARC_ARISE_SEEDS/` (planner at `/tool/`). On a free plan, Pages from a private repo needs GitHub Pro or an org plan. Otherwise make the repo public, or use `scripts/bundle_preview.py` to produce a single offline HTML file.

### Known gaps / next

- PAD-US `GAP_Sts` field name and asset IDs are assumed. The pipeline falls back to WDPA if PAD-US is missing.
- GEDI is footprint-sparse; cells with no shots get a median rank. Consider swapping in a wall-to-wall canopy height layer.
- No stream-order or trail layer yet. Add OSM trails and NHDPlus when available.
- Corridor resistance is a priority transform, not a species-specific resistance surface.
- Hub list needs ACI/LTNAL review.

## Layout

```
config/          seeds.yaml, hubs.csv, aoi_counties.geojson
seeds_cds/       aoi, grid, gee_layers, aggregate, scoring, pipeline, demo, __main__
docs/            GitHub Pages: index.html (project), tool/ (planner), assets/, data/
notebooks/       Colab runner
scripts/         bundle_preview.py
tests/           pytest (+ node parity)
```
