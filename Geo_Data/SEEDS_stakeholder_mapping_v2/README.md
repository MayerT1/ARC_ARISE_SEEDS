# SEEDS focus-group stakeholder mapping — v2 (8 events)

ARC ARISE SEEDS · UAH · generated 2026-11-11

## Contents
| path | what |
|---|---|
| `data/seeds_stakeholder_pool_v2.csv` / `.xlsx` / `.md` | Institutional stakeholder pool: 307 rows, 165 named, 102 with email (63 published on a public page, rest agency-format `pattern`). Every named row has `source_url` + `as_of`; `verify_flag=Y` = check before inviting. |
| `notebooks/01b_SEEDS_Parcel_Landowner_Pull.ipynb` | Pulls county parcel/assessment data (TN Comptroller downloads; AL Revenue Commissioner ArcGIS/KCS or Regrid exports), aggregates holdings by owner, classifies owner type, keeps holdings >= **50 ac**, writes landowner candidates in pool schema with `approved_for_invite=False`. |
| `notebooks/02_SEEDS_Stakeholder_Influence_Ability.ipynb` | Footprints -> 2020 census block capture (raw pop, % AOI, % event catchment, % tract) -> Influence & Ability-to-Act scores -> per-stakeholder maps, AOI heat maps, round-robin invite lists for 8 events -> Google Drive. |
| `src/` | Generators: `build_pool.py` (v1 base), `build_pool_v2.py` (v2 pool), `build_notebook.py`, `build_parcel_notebook.py`, `research/contacts_*.py` (sourced contact records). Run from `src/`; outputs to `src/out/`. |

## Events
A1 Huntsville Metro · A2 East Madison & Paint Rock Valley · A3 Lake Guntersville & Sand Mountain · A4 Scottsboro & NE Jackson ·
T1 Franklin + Coffee · T2 Grundy + Marion · T3 Sequatchie + Bledsoe + Van Buren · T4 Warren + DeKalb.
AL catchments = nearest hub within county (edit `EVENTS` hubs in notebook 02). Rows per event in CSV: {'A1': 38, 'A2': 11, 'A3': 27, 'A4': 19, 'T1': 62, 'T2': 58, 'T3': 49, 'T4': 43}

## Run order (Colab)
1. Put `data/seeds_stakeholder_pool_v2.csv` in `MyDrive/SEEDS/stakeholder_mapping/`.
2. Download parcel data into `.../parcels/raw/TN/` and `/AL/` (or set AL ArcGIS URLs in `SOURCES`; use `discover()`), run **01b**.
3. LTNAL/ACI review `parcels/landowner_review_sheet.csv` -> set `approved_for_invite=True` in `landowner_candidates.csv`.
4. Run **02**. Outputs: `tables/`, `maps/`, `gis/` (GeoPackage + GeoJSON), interactive HTML.

## Sizing
8 events x 20-30 attendees @ 30% acceptance = 536-800 invites. Institutional pool (307) + vetted landowners (01b, up to 50/county) covers the range.

## Notes
* Emails marked `pattern` follow agency formats (first.last@tn.gov, @dcnr.alabama.gov, etc.) and are unverified.
* No active TN County Forestry Associations exist in the 9 TN counties (TDF list) — those rows removed; use TN Forestry Assoc / TDF area foresters.
* Owner/mailing fields in 01b come from public tax rolls; use for vetted outreach only.
* Notebooks were tested end-to-end on synthetic geometry; first real-data run happens in Colab.
