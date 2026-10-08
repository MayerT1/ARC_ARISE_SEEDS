# Task 3 · Geo-AI Decision Support Prototype (Oct 2026 – Mar 2028)

Combined with Task 2 in one tool: [Greenbelt Corridor Planner](../Task%202%20Multi-County%20Feasibility%20Study%20and%20Greenbelt%20Corridor%20Planning/greenbelt_corridor_planner/)

**SOW activities → where they live**
| Activity | Planner component |
|---|---|
| Integrate GIS with remote sensing, ecological and land-use data | Earth Engine stack: NLCD, 3DEP, NAIP 0.6 m canopy height, Hansen, Sentinel-2, HydroSHEDS, JRC water, PAD-US |
| Dynamic corridor planning and visualization | Live least-cost routing over trails and streets, adjustable costs, gaps and parcel screening |
| Incorporate stakeholder and community input | Stakeholder weight import (Task 1), map feedback pins stored in Google Sheets |
| Interactive dashboard for scenario analysis | Web planner: scenarios, county summaries, Geo-AI diagnostics, exports |

**Geo-AI model:** random forest trained on PAD-US GAP 1–2 land versus background (holdout AUC ≈ 0.85 on the first run), explained in fact sheet section 7.

**Next (2027–28):** stakeholder-weighted scenario library, parcel-level acquisition ranking, trail condition and slope in routing, model refresh with new NAIP/NLCD releases.
