# Task 1 · Stakeholder Consultation and Survey Design (Oct – Dec 2026)

UAH supports consultation tools built on co-development and participatory planning methods.

**SOW activities**
- Design county- and community-level consultation and survey tools
- Align survey instruments with stakeholder agreements and planning frameworks
- Integrate data collection that supports downstream geospatial and economic analyses
- Keep collected data compatible with GIS and decision-support systems

**Link to the corridor planner (Tasks 2+3)**
- Survey priority questions map onto planner criteria. Aggregated responses are saved as a weights file that loads with *Import stakeholder weights*:
  ```json
  {"scenario": "Grundy Co. workshop, Nov 2026",
   "weights": {"forest_cover": 20, "riparian_proximity": 15, "trail_proximity": 15, "gateway_proximity": 20,
               "arc_need": 15, "development": -15}}
  ```
  Valid keys are listed in the planner fact sheet, section 5.
- Place-based comments are collected on the planner map (*Give feedback*) into a Google Sheet, with location and scenario attached.

**Status:** instrument design in progress.
