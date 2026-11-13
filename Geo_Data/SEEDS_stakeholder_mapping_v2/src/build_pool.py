"""Generate SEEDS focus-group stakeholder pool CSV (Task 1).
Edit ROWS / ROLE_DEFAULTS and re-run. Output: seeds_stakeholder_pool.csv (+ .md)
"""
import csv, os

F = {  # 12-county AOI (2020 county FIPS)
    "MAD": "01089", "MAR": "01095", "JAC": "01071",
    "FRA": "47051", "COF": "47031", "GRU": "47061",
    "MRN": "47115", "SEQ": "47153", "BLE": "47007",
    "WAR": "47177", "DEK": "47041", "VAN": "47175",
}
NAME = {"01089": "Madison AL", "01095": "Marshall AL", "01071": "Jackson AL",
        "47051": "Franklin TN", "47031": "Coffee TN", "47061": "Grundy TN",
        "47115": "Marion TN", "47153": "Sequatchie TN", "47007": "Bledsoe TN",
        "47177": "Warren TN", "47041": "DeKalb TN", "47175": "Van Buren TN"}
AL = ["MAD", "MAR", "JAC"]
TN = ["FRA", "COF", "GRU", "MRN", "SEQ", "BLE", "WAR", "DEK", "VAN"]
REGION = {  # proposed 4 focus-group event regions
    "R1": "North Alabama (Madison, Marshall, Jackson)",
    "R2": "TN Southern Plateau & Highland Rim (Franklin, Coffee, Grundy)",
    "R3": "TN Sequatchie Valley & Walden Ridge (Marion, Sequatchie, Bledsoe)",
    "R4": "TN Northern Plateau & Caney Fork (Warren, DeKalb, Van Buren)",
}

def C(*k):
    return ";".join(F[x] for x in k)

# role_class -> authority(1-5), constituency(0-1), ability dims (0-1, higher = fewer constraints)
# d_control  : direct control of land/resource (fee-simple owner = 1)
# d_approval : 1 - depth of approval chain (sole decision = 1; act of legislature/Congress ~0.1)
# d_fiscal   : discretionary funding / resources
# d_authority: regulatory/statutory power over OTHERS' land use (zoning, permits, consultation)
# d_speed    : decision-cycle speed
# d_freedom  : freedom from external mandates (NEPA, mission, public process, HOA/zoning/tax)
ROLE_DEFAULTS = {
    #                        A  cons ctrl appr fisc auth spd  free
    "county_exec":          (5, 1.0, 0.5, 0.5, 0.6, 0.8, 0.5, 0.5),
    "municipal_exec":       (4, 1.0, 0.5, 0.5, 0.5, 0.8, 0.5, 0.5),
    "municipal_dept":       (3, 0.6, 0.6, 0.4, 0.5, 0.5, 0.5, 0.5),
    "regional_council":     (4, 0.6, 0.1, 0.5, 0.6, 0.2, 0.5, 0.6),
    "state_agency_hq":      (4, 0.6, 0.6, 0.3, 0.7, 0.7, 0.3, 0.3),
    "state_agency_regional":(3, 0.6, 0.6, 0.4, 0.4, 0.6, 0.4, 0.4),
    "state_park_unit":      (2, 0.3, 0.6, 0.3, 0.3, 0.4, 0.3, 0.3),
    "federal_installation": (3, 0.3, 0.8, 0.3, 0.6, 0.5, 0.2, 0.2),
    "federal_land_unit":    (2, 0.3, 0.6, 0.3, 0.3, 0.5, 0.2, 0.2),
    "federal_program":      (3, 0.6, 0.1, 0.5, 0.8, 0.5, 0.4, 0.4),
    "federal_utility":      (3, 0.3, 0.7, 0.3, 0.5, 0.6, 0.3, 0.3),
    "tourism_org":          (3, 0.6, 0.0, 0.7, 0.4, 0.0, 0.7, 0.7),
    "ngo_land_trust":       (3, 0.6, 0.8, 0.7, 0.6, 0.1, 0.6, 0.6),
    "ngo_advocacy":         (2, 0.6, 0.2, 0.8, 0.3, 0.0, 0.8, 0.7),
    "philanthropy":         (3, 0.3, 0.0, 0.7, 0.9, 0.0, 0.6, 0.8),
    "industry_assoc":       (3, 0.6, 0.2, 0.6, 0.4, 0.0, 0.6, 0.7),
    "industry_company":     (2, 0.3, 0.9, 0.7, 0.7, 0.1, 0.7, 0.6),
    "private_landowner":    (1, 0.1, 1.0, 1.0, 0.5, 0.0, 0.9, 0.8),
    "institutional_landowner": (2, 0.3, 0.9, 0.6, 0.5, 0.1, 0.6, 0.6),
    "utility_coop":         (2, 0.6, 0.3, 0.6, 0.5, 0.2, 0.5, 0.5),
    "water_authority":      (3, 0.6, 0.5, 0.5, 0.5, 0.6, 0.4, 0.4),
    "academic":             (2, 0.3, 0.3, 0.5, 0.4, 0.0, 0.5, 0.6),
    "tribal_thpo":          (3, 0.6, 0.0, 0.6, 0.2, 0.7, 0.4, 0.5),
    "conservation_district":(2, 0.6, 0.1, 0.6, 0.4, 0.2, 0.6, 0.6),
}

S_ST, S_LO, S_FE, S_PL, S_IN, S_NP, S_TR, S_AC = (
    "State", "Local/Municipal", "Federal", "Private Landowner",
    "Industry/Private Sector", "Nonprofit/Conservation", "Tribal", "Academic")

# (org, poc_role, sector, sub_sector, role_class, event, geo_type, geo_ref, counties, lat, lon, acres, priority, notes, overrides)
# geo_type: county | place | site | multi_site | state_aoi | parcel_placeholder
#   county  : geo_ref = ';'-sep county FIPS
#   place   : geo_ref = ';'-sep 'STATEFP:Place Name' (TIGER 2020 place NAME)
#   site / multi_site : geo_ref = PAD-US Unit_Nm match string(s) '|'-sep; lat/lon/acres fallback '|'-sep
#   state_aoi : geo_ref = '01' | '47' | 'ALL' -> all AOI counties in that state
#   parcel_placeholder : geo_ref = county FIPS; acres -> circle at county interior point until parcel joined
R = []
def add(*a, ov=None):
    R.append(list(a) + [ov or {}])

def site(org, poc, sector, sub, rc, ev, padus, cty, lat, lon, ac, pr=1, notes="", ov=None):
    add(org, poc, sector, sub, rc, ev, "site", padus, cty, lat, lon, ac, pr, notes, ov=ov)

def cty(org, poc, sector, sub, rc, ev, counties, pr=1, notes="", ov=None):
    add(org, poc, sector, sub, rc, ev, "county", counties, counties, "", "", "", pr, notes, ov=ov)

def plc(org, poc, sector, sub, rc, ev, places, counties, pr=1, notes="", ov=None):
    add(org, poc, sector, sub, rc, ev, "place", places, counties, "", "", "", pr, notes, ov=ov)

def sta(org, poc, sector, sub, rc, ev, st, pr=1, notes="", ov=None):
    cs = C(*(AL if st == "01" else TN if st == "47" else AL + TN))
    add(org, poc, sector, sub, rc, ev, "state_aoi", st, cs, "", "", "", pr, notes, ov=ov)

def parcel(org, poc, sector, sub, rc, ev, county, ac, pr=2, notes=""):
    add(org, poc, sector, sub, rc, ev, "parcel_placeholder", county, county, "", "", ac, pr,
        "PLACEHOLDER - identify owner via county assessor / TN Comptroller parcel GIS / LTNAL-ACI landowner contacts; replace geometry with parcel polygon. " + notes)

# ======================= R1 North Alabama =======================
cty("Madison County Commission", "Commission Chairman", S_LO, "County government", "county_exec", "R1", C("MAD"))
plc("City of Huntsville", "Mayor", S_LO, "Municipal government", "municipal_exec", "R1", "01:Huntsville", C("MAD"), notes="Place extends into Limestone/Morgan; clipped to AOI")
plc("City of Huntsville - Parks & Recreation / Greenways", "Director of Parks & Recreation", S_LO, "Municipal parks/greenways", "municipal_dept", "R1", "01:Huntsville", C("MAD"), pr=2)
plc("City of Madison", "Mayor", S_LO, "Municipal government", "municipal_exec", "R1", "01:Madison", C("MAD"))
plc("Town of Gurley", "Mayor", S_LO, "Municipal government (gateway)", "municipal_exec", "R1", "01:Gurley", C("MAD"), pr=2, notes="Paint Rock / Flint gateway")
plc("Town of Owens Cross Roads", "Mayor", S_LO, "Municipal government", "municipal_exec", "R1", "01:Owens Cross Roads", C("MAD"), pr=3)
plc("City of New Hope (AL)", "Mayor", S_LO, "Municipal government (gateway)", "municipal_exec", "R1", "01:New Hope", C("MAD"), pr=3)
cty("Marshall County Commission", "Commission Chairman", S_LO, "County government", "county_exec", "R1", C("MAR"))
plc("City of Guntersville", "Mayor", S_LO, "Municipal government (lake gateway)", "municipal_exec", "R1", "01:Guntersville", C("MAR"))
plc("City of Albertville", "Mayor", S_LO, "Municipal government", "municipal_exec", "R1", "01:Albertville", C("MAR"), pr=2)
plc("City of Arab", "Mayor", S_LO, "Municipal government", "municipal_exec", "R1", "01:Arab", C("MAR"), pr=2)
plc("City of Boaz", "Mayor", S_LO, "Municipal government", "municipal_exec", "R1", "01:Boaz", C("MAR"), pr=3)
cty("Jackson County Commission", "Commission Chairman", S_LO, "County government", "county_exec", "R1", C("JAC"))
plc("City of Scottsboro", "Mayor", S_LO, "Municipal government (lake gateway)", "municipal_exec", "R1", "01:Scottsboro", C("JAC"))
plc("City of Stevenson", "Mayor", S_LO, "Municipal government (gateway)", "municipal_exec", "R1", "01:Stevenson", C("JAC"), pr=2)
plc("City of Bridgeport", "Mayor", S_LO, "Municipal government (gateway, TN line)", "municipal_exec", "R1", "01:Bridgeport", C("JAC"), pr=2)
cty("Top of Alabama Regional Council of Governments (TARCOG)", "Executive Director", S_LO, "Regional COG / ARC LDD", "regional_council", "R1", C("MAD", "MAR", "JAC"), notes="Also covers DeKalb AL, Limestone (outside AOI)")
site("AL DCNR State Parks - Monte Sano State Park", "Park Superintendent", S_ST, "Public state parks", "state_park_unit", "R1", "Monte Sano State Park", C("MAD"), 34.745, -86.512, 2140)
site("AL DCNR State Parks - Lake Guntersville State Park", "Park Superintendent", S_ST, "Public state parks", "state_park_unit", "R1", "Lake Guntersville State Park", C("MAR"), 34.391, -86.205, 6000)
site("AL DCNR State Parks - Cathedral Caverns State Park", "Park Superintendent", S_ST, "Public state parks", "state_park_unit", "R1", "Cathedral Caverns State Park", C("MAR"), 34.573, -86.222, 493, pr=2)
sta("AL DCNR State Lands Division - Forever Wild Land Trust", "Forever Wild Program Manager", S_ST, "State land acquisition", "state_agency_hq", "R1", "01", notes="Walls of Jericho, Skyline, Paint Rock tracts")
site("AL DCNR Wildlife & Freshwater Fisheries - District I (Skyline WMA / Walls of Jericho)", "District Supervisor / WMA Biologist", S_ST, "State wildlife mgmt", "state_agency_regional", "R1", "Skyline Wildlife Management Area|James D. Martin-Skyline WMA|Walls of Jericho", C("JAC"), 34.97, -86.08, 60000, notes="Acres approximate; prefer PAD-US polygon")
cty("Alabama Forestry Commission - Northeast Region", "Regional Forester", S_ST, "State forestry", "state_agency_regional", "R1", C("MAD", "MAR", "JAC"))
sta("ADECA - Appalachian Regional Commission State Program", "ARC Program Manager", S_ST, "State ARC / econ dev", "state_agency_hq", "R1", "01")
sta("Alabama Tourism Department", "Director / North AL Regional Rep", S_ST, "State tourism", "state_agency_hq", "R1", "01", pr=2)
cty("ALDOT North Region", "Region Engineer / TAP-RTP Coordinator", S_ST, "State transportation / trails funding", "state_agency_regional", "R1", C("MAD", "MAR", "JAC"), pr=2)
site("US Army Garrison Redstone Arsenal - Environmental Management Division", "Chief, Natural Resources Branch", S_FE, "DoW installation", "federal_installation", "R1", "Redstone Arsenal", C("MAD"), 34.65, -86.65, 38000)
site("NASA Marshall Space Flight Center - Environmental Engineering & Occupational Health", "Environmental Manager", S_FE, "NASA center", "federal_installation", "R1", "Marshall Space Flight Center|George C. Marshall Space Flight Center", C("MAD"), 34.646, -86.674, 1840, notes="Inside Redstone footprint")
add("USFWS Wheeler NWR Complex (Wheeler, Sauta Cave, Fern Cave NWRs)", "Refuge Manager", S_FE, "Federal wildlife refuge", "federal_land_unit", "R1", "multi_site",
    "Wheeler National Wildlife Refuge|Sauta Cave National Wildlife Refuge|Fern Cave National Wildlife Refuge", C("MAD", "JAC"),
    "34.60|34.648|34.67", "-86.80|-86.098|-86.27", "35000|264|199", 1, "Wheeler mostly Morgan/Limestone - clipped to AOI")
site("NPS Russell Cave National Monument", "Superintendent", S_FE, "National Park Service", "federal_land_unit", "R1", "Russell Cave National Monument", C("JAC"), 34.975, -85.814, 310)
cty("TVA - Guntersville Reservoir Natural Resources", "Watershed / Natural Resource Manager", S_FE, "Federal utility / reservoir lands", "federal_utility", "R1", C("MAR", "JAC", "MAD"))
cty("USDA NRCS Alabama - Area 1 (North)", "Area Conservationist", S_FE, "USDA conservation programs", "federal_program", "R1", C("MAD", "MAR", "JAC"))
sta("USDA Rural Development - Alabama", "Area Director (North AL)", S_FE, "USDA rural development", "federal_program", "R1", "01", pr=2)
cty("The Nature Conservancy in Alabama - Paint Rock / Walls of Jericho", "North Alabama Program Director", S_NP, "Land trust / conservation", "ngo_land_trust", "R1", C("JAC", "MAD", "MAR"), notes="Paint Rock River watershed")
cty("Southeastern Cave Conservancy Inc. (SCCi)", "Preserve Chair / Executive Director", S_NP, "Cave land trust", "ngo_land_trust", "R1", C("JAC", "MRN", "FRA"), pr=2, notes="Multiple cave preserves; replace with preserve polygons")
cty("Singing River Trail", "Executive Director", S_NP, "Regional trail org", "ngo_advocacy", "R1", C("MAD", "MAR"), notes="Also Limestone/Morgan")
cty("Alabama Mountain Lakes Tourist Association", "President / CEO", S_IN, "Regional tourism", "tourism_org", "R1", C("MAD", "MAR", "JAC"), notes="16-county N. AL tourism region")
cty("Huntsville/Madison County Convention & Visitors Bureau", "President / CEO", S_IN, "Tourism CVB", "tourism_org", "R1", C("MAD"))
cty("Marshall County Convention & Visitors Bureau", "President", S_IN, "Tourism CVB", "tourism_org", "R1", C("MAR"))
cty("Mountain Lakes Chamber of Commerce (Jackson Co.)", "President", S_IN, "Chamber / tourism", "tourism_org", "R1", C("JAC"))
sta("Alabama TREASURE Forest Association", "Executive Director (+ county chapter chairs)", S_PL, "Private forest landowner association", "industry_assoc", "R1", "01", notes="Best proxy for family forest owners")
sta("Alabama Forestry Association", "Executive Vice President", S_IN, "Timber industry association", "industry_assoc", "R1", "01")
cty("Alabama Farmers Federation (Madison/Marshall/Jackson County Federations)", "County Federation Presidents", S_PL, "Farm landowner association", "industry_assoc", "R1", C("MAD", "MAR", "JAC"))
cty("Poultry integrator complex - Marshall Co. (verify company)", "Complex / Live Production Manager", S_IN, "Agribusiness (poultry)", "industry_company", "R1", C("MAR"), pr=3, notes="Largest ag employer type on Sand Mountain; land-use influence via growers")
cty("Alabama A&M University - Forestry, Ecology & Wildlife Program", "Department Chair", S_AC, "Land-grant university", "academic", "R1", C("MAD"), pr=2)
cty("Madison / Marshall / Jackson County Soil & Water Conservation Districts", "District Chairs / Administrative Coordinators", S_LO, "Soil & water conservation district", "conservation_district", "R1", C("MAD", "MAR", "JAC"), pr=2)
cty("SORBA Huntsville (Monte Sano / Land Trust trails)", "Chapter President", S_NP, "Mountain bike / trail org", "ngo_advocacy", "R1", C("MAD"), pr=3)
parcel("Private landowner - large forest tract, Jackson Co. (Cumberland Plateau / Paint Rock)", "Landowner", S_PL, "Private forest landowner", "private_landowner", "R1", C("JAC"), 1200)
parcel("Private landowner - large farm / forest, east Madison Co. (Flint River)", "Landowner", S_PL, "Private agricultural landowner", "private_landowner", "R1", C("MAD"), 500)
parcel("Private landowner - large tract, Marshall Co. (Sand Mountain / lake bluffs)", "Landowner", S_PL, "Private forest landowner", "private_landowner", "R1", C("MAR"), 600)
parcel("Timber / TIMO landowner - Jackson Co.", "Regional Forester / Land Manager", S_IN, "Industrial / investment timberland", "industry_company", "R1", C("JAC"), 5000)

# ======================= R2 TN Southern Plateau & Highland Rim =======================
cty("Franklin County (TN) Government", "County Mayor", S_LO, "County government", "county_exec", "R2", C("FRA"))
plc("City of Winchester", "Mayor", S_LO, "Municipal government (lake gateway)", "municipal_exec", "R2", "47:Winchester", C("FRA"))
plc("City of Decherd", "Mayor", S_LO, "Municipal government", "municipal_exec", "R2", "47:Decherd", C("FRA"), pr=2)
plc("City of Cowan", "Mayor", S_LO, "Municipal government (trail gateway)", "municipal_exec", "R2", "47:Cowan", C("FRA"), pr=2)
plc("City of Estill Springs", "Mayor", S_LO, "Municipal government (lake gateway)", "municipal_exec", "R2", "47:Estill Springs", C("FRA"), pr=3)
cty("Coffee County (TN) Government", "County Mayor", S_LO, "County government", "county_exec", "R2", C("COF"))
plc("City of Manchester", "Mayor", S_LO, "Municipal government", "municipal_exec", "R2", "47:Manchester", C("COF"))
plc("City of Tullahoma", "Mayor / City Administrator", S_LO, "Municipal government", "municipal_exec", "R2", "47:Tullahoma", C("COF", "FRA"))
cty("Grundy County (TN) Government", "County Mayor", S_LO, "County government (Distressed)", "county_exec", "R2", C("GRU"))
plc("Town of Monteagle", "Mayor", S_LO, "Municipal government (gateway)", "municipal_exec", "R2", "47:Monteagle", C("GRU", "MRN", "FRA"))
plc("Town of Tracy City", "Mayor", S_LO, "Municipal government (gateway)", "municipal_exec", "R2", "47:Tracy City", C("GRU"))
plc("Town of Altamont", "Mayor", S_LO, "Municipal government (gateway)", "municipal_exec", "R2", "47:Altamont", C("GRU"), pr=2)
plc("Town of Beersheba Springs", "Mayor", S_LO, "Municipal government (Stone Door gateway)", "municipal_exec", "R2", "47:Beersheba Springs", C("GRU"), pr=2)
plc("Town of Palmer", "Mayor", S_LO, "Municipal government (gateway)", "municipal_exec", "R2", "47:Palmer", C("GRU"), pr=3)
cty("South Central Tennessee Development District", "Executive Director", S_LO, "Regional development district / ARC LDD", "regional_council", "R2", C("FRA", "COF"), notes="13-county district; Grundy is SETDD")
sta("TDEC Division of Parks & Conservation (Tennessee State Parks HQ)", "Deputy Commissioner / Director of State Parks", S_ST, "State parks system", "state_agency_hq", "R2", "47")
site("TDEC - Tims Ford State Park", "Park Manager", S_ST, "Public state parks", "state_park_unit", "R2", "Tims Ford State Park", C("FRA"), 35.215, -86.24, 3546)
site("TDEC - South Cumberland State Park (Savage Gulf, Fiery Gizzard, Grundy Forest, Collins Gulf)", "Park Manager", S_ST, "Public state parks", "state_park_unit", "R2", "South Cumberland State Park|Savage Gulf State Natural Area|Grundy Forest State Natural Area|Fiery Gizzard|Collins Gulf", C("GRU", "MRN", "FRA"), 35.36, -85.66, 30800, notes="Multi-unit park; PAD-US strongly preferred over point")
site("TDEC - Old Stone Fort State Archaeological Park", "Park Manager", S_ST, "Public state parks (cultural)", "state_park_unit", "R2", "Old Stone Fort State Archaeological Park", C("COF"), 35.486, -86.10, 876)
add("TDEC Division of Natural Areas - Middle TN (Short Springs, May Prairie, Carter SNAs)", "Stewardship Ecologist (Middle TN)", S_ST, "State natural areas", "state_agency_regional", "R2", "multi_site",
    "Short Springs State Natural Area|May Prairie State Natural Area|Carter State Natural Area", C("COF", "FRA"),
    "35.40|35.43|35.03", "-86.19|-86.03|-86.07", "420|280|140", 2, "")
site("TN Division of Forestry - Franklin State Forest", "District Forester / Forest Manager", S_ST, "State forestry", "state_agency_regional", "R2", "Franklin State Forest", C("FRA", "MRN"), 35.05, -85.95, 6941)
cty("TWRA Region II (Middle Tennessee)", "Region Manager", S_ST, "State wildlife mgmt", "state_agency_regional", "R2", C("FRA", "COF"), notes="Verify regional boundaries")
site("Department of the Air Force - Arnold AFB / AEDC", "Natural Resources Manager (Environmental Mgmt)", S_FE, "DoW installation", "federal_installation", "R2", "Arnold Air Force Base|Arnold Engineering Development Complex", C("COF", "FRA"), 35.39, -86.06, 39000, notes="Woods Reservoir; largest single landholder in R2")
cty("TVA - Tims Ford & Normandy Reservoirs", "Natural Resources Manager", S_FE, "Federal utility / reservoir lands", "federal_utility", "R2", C("FRA", "COF"))
cty("USDA NRCS Tennessee - Middle Area", "Area Conservationist", S_FE, "USDA conservation programs", "federal_program", "R2", C("FRA", "COF", "GRU", "WAR", "DEK", "VAN"), notes="Verify TN NRCS area boundaries")
sta("USDA Forest Service - State & Private Forestry (Forest Legacy / Landscape Scale Restoration)", "Region 8 S&PF Program Manager", S_FE, "Federal forestry programs", "federal_program", "R2", "ALL", pr=2)
site("University of the South - Office of Domain Management", "Domain Manager", S_AC, "Institutional landowner (~13,000 ac)", "institutional_landowner", "R2", "University of the South|Sewanee Domain", C("FRA", "GRU"), 35.205, -85.92, 13000, notes="Project partner institution - landowner seat")
plc("Mountain Goat Trail Alliance", "Executive Director", S_NP, "Rail-trail org", "ngo_advocacy", "R2", "47:Cowan;47:Sewanee;47:Monteagle;47:Tracy City;47:Palmer", C("FRA", "GRU"), notes="Linear corridor; places as proxy footprint")
cty("South Cumberland Community Fund", "Executive Director", S_NP, "Community foundation", "philanthropy", "R2", C("FRA", "GRU", "MRN"))
site("Friends of South Cumberland State Park", "President", S_NP, "Park friends group", "ngo_advocacy", "R2", "South Cumberland State Park|Savage Gulf State Natural Area", C("GRU", "MRN"), 35.36, -85.66, 30800, pr=2)
sta("Tennessee Parks & Greenways Foundation", "President / CEO", S_NP, "Land trust / parks foundation", "ngo_land_trust", "R2", "47")
sta("Tennessee Wildlife Federation", "CEO / Conservation Director", S_NP, "Wildlife advocacy", "ngo_advocacy", "R2", "47", pr=2)
sta("TN Dept of Economic & Community Development - ARC State Program", "ARC Program Manager", S_ST, "State ARC / econ dev", "state_agency_hq", "R2", "47")
cty("Manchester / Coffee County Tourism (CVB)", "Tourism Director", S_IN, "Tourism CVB", "tourism_org", "R2", C("COF"))
plc("Tullahoma Area Chamber of Commerce", "President", S_IN, "Chamber of commerce", "tourism_org", "R2", "47:Tullahoma", C("COF", "FRA"), pr=2)
cty("Franklin County (TN) Chamber of Commerce", "President", S_IN, "Chamber / tourism", "tourism_org", "R2", C("FRA"))
cty("Grundy County Chamber / South Cumberland Plateau Tourism", "Director", S_IN, "Chamber / tourism", "tourism_org", "R2", C("GRU"))
cty("Duck River Agency / Duck River Utility Commission", "Executive Director", S_LO, "Regional water authority (Duck headwaters)", "water_authority", "R2", C("COF"), pr=2)
site("Bonnaroo - Great Stage Park (festival operator)", "Site / Operations Manager", S_IN, "Event tourism / private land", "industry_company", "R2", "Great Stage Park", C("COF"), 35.477, -86.054, 700, pr=2)
cty("Motlow State Community College", "VP Workforce & Economic Development", S_AC, "Community college / workforce", "academic", "R2", C("COF", "FRA", "WAR"))
site("Monteagle Sunday School Assembly", "Executive Director", S_IN, "Heritage institution / landowner", "institutional_landowner", "R2", "Monteagle Sunday School Assembly", C("GRU", "MRN"), 35.243, -85.838, 96, pr=3)
cty("Tennessee Farm Bureau - Franklin / Coffee / Grundy County FBs", "County Farm Bureau Presidents", S_PL, "Farm landowner association", "industry_assoc", "R2", C("FRA", "COF", "GRU"))
cty("Franklin / Coffee / Grundy Soil Conservation Districts", "District Chairs", S_LO, "Soil conservation district", "conservation_district", "R2", C("FRA", "COF", "GRU"), pr=2)
parcel("Private landowner - large plateau forest tract, Franklin Co.", "Landowner", S_PL, "Private forest landowner", "private_landowner", "R2", C("FRA"), 1500)
parcel("Private landowner - large ag / forest tract, Coffee Co.", "Landowner", S_PL, "Private agricultural landowner", "private_landowner", "R2", C("COF"), 800)
parcel("Private landowner - large plateau forest tract, Grundy Co.", "Landowner", S_PL, "Private forest landowner", "private_landowner", "R2", C("GRU"), 2000)
parcel("Timber / TIMO landowner - Grundy / Franklin plateau", "Regional Forester / Land Manager", S_IN, "Industrial / investment timberland", "industry_company", "R2", C("GRU"), 5000)
sta("Cherokee Nation - Tribal Historic Preservation Office", "THPO", S_TR, "Tribal cultural resources", "tribal_thpo", "R2", "ALL", notes="Old Stone Fort, cave & mound sites; Section 106")

# ======================= R3 TN Sequatchie Valley & Walden Ridge =======================
cty("Marion County (TN) Government", "County Mayor", S_LO, "County government", "county_exec", "R3", C("MRN"))
plc("City of Jasper", "Mayor", S_LO, "Municipal government", "municipal_exec", "R3", "47:Jasper", C("MRN"))
plc("City of South Pittsburg", "Mayor", S_LO, "Municipal government (river gateway)", "municipal_exec", "R3", "47:South Pittsburg", C("MRN"))
plc("City of Kimball", "Mayor", S_LO, "Municipal government", "municipal_exec", "R3", "47:Kimball", C("MRN"), pr=2)
plc("Town of Whitwell", "Mayor", S_LO, "Municipal government", "municipal_exec", "R3", "47:Whitwell", C("MRN"), pr=2)
plc("City of New Hope (TN)", "Mayor", S_LO, "Municipal government", "municipal_exec", "R3", "47:New Hope", C("MRN"), pr=3)
cty("Sequatchie County Government", "County Mayor / Executive", S_LO, "County government (At-Risk)", "county_exec", "R3", C("SEQ"))
plc("City of Dunlap", "Mayor", S_LO, "Municipal government (Coke Ovens gateway)", "municipal_exec", "R3", "47:Dunlap", C("SEQ"))
cty("Bledsoe County Government", "County Mayor", S_LO, "County government (Distressed)", "county_exec", "R3", C("BLE"))
plc("City of Pikeville", "Mayor", S_LO, "Municipal government (Fall Creek gateway)", "municipal_exec", "R3", "47:Pikeville", C("BLE"))
cty("Southeast Tennessee Development District", "Executive Director", S_LO, "Regional development district / ARC LDD", "regional_council", "R3", C("MRN", "SEQ", "BLE", "GRU"), notes="10-county district (Chattanooga)")
cty("Thrive Regional Partnership", "President / CEO", S_NP, "Tri-state regional planning (incl. Jackson AL)", "regional_council", "R3", C("MRN", "SEQ", "BLE", "GRU", "JAC"), notes="Cross-state bridge AL-TN")
cty("TDEC - Cumberland Trail State Park", "Park Manager", S_ST, "Public state parks (linear trail)", "state_park_unit", "R3", C("MRN", "SEQ", "BLE"), notes="Linear park; replace with trail buffer if available")
site("TN Division of Forestry - Prentice Cooper State Forest", "Forest Manager", S_ST, "State forestry", "state_agency_regional", "R3", "Prentice Cooper State Forest", C("MRN"), 35.10, -85.43, 25000)
site("TN Division of Forestry - Bledsoe State Forest", "Forest Manager", S_ST, "State forestry", "state_agency_regional", "R3", "Bledsoe State Forest", C("BLE"), 35.63, -85.17, 8000, pr=2)
cty("TWRA Region III (Cumberland Plateau)", "Region Manager", S_ST, "State wildlife mgmt", "state_agency_regional", "R3", C("MRN", "SEQ", "BLE", "GRU", "WAR", "VAN", "DEK"), notes="Verify regional boundaries")
cty("TDOT Region 2 - Multimodal / Transportation Alternatives", "Region 2 Planning / TA Coordinator", S_ST, "State transportation / trails funding", "state_agency_regional", "R3", C(*TN), pr=2, notes="Verify region coverage per county")
sta("TN Dept of Tourist Development - Rural Tourism", "Rural Tourism / Regional Rep", S_ST, "State tourism", "state_agency_hq", "R3", "47")
cty("TVA - Nickajack Reservoir / Nickajack Cave Refuge", "Natural Resources Manager", S_FE, "Federal utility / reservoir lands", "federal_utility", "R3", C("MRN"))
cty("USDA NRCS Tennessee - East / Southeast Area", "Area Conservationist", S_FE, "USDA conservation programs", "federal_program", "R3", C("MRN", "SEQ", "BLE"), notes="Verify TN NRCS area boundaries")
sta("NPS Rivers, Trails & Conservation Assistance (RTCA) - Southeast", "Community Planner", S_FE, "Federal technical assistance", "federal_program", "R3", "ALL", pr=2)
cty("Tennessee River Gorge Trust", "Executive Director", S_NP, "Land trust", "ngo_land_trust", "R3", C("MRN"), notes="Also Hamilton Co.")
add("Southeastern Climbers Coalition (Denny Cove, Foster Falls)", "Executive Director", S_NP, "Climbing access / landowner", "ngo_land_trust", "R3", "multi_site",
    "Denny Cove|Foster Falls", C("MRN"), "35.15|35.18", "-85.73|-85.67", "685|500", 2, "")
cty("Open Space Institute - Southern Cumberland Program", "Southern Program Director", S_NP, "Land trust / acquisition", "ngo_land_trust", "R3", C("MRN", "GRU", "FRA", "SEQ", "BLE", "VAN"))
sta("The Land Trust for Tennessee - Southeast TN", "Southeast TN Director", S_NP, "Land trust / easements", "ngo_land_trust", "R3", "47")
cty("Lyndhurst Foundation", "President", S_NP, "Philanthropy (S. Cumberland conservation)", "philanthropy", "R3", C("MRN", "SEQ", "BLE", "GRU"), pr=2)
cty("Cumberland Trail Conference", "Executive Director", S_NP, "Trail org", "ngo_advocacy", "R3", C("MRN", "SEQ", "BLE"))
cty("Tennessee Aquarium Conservation Institute", "Director", S_AC, "Aquatic conservation science", "academic", "R3", C("MRN", "SEQ", "BLE", "GRU"), pr=3)
cty("Marion County (TN) Chamber of Commerce", "President", S_IN, "Chamber / tourism", "tourism_org", "R3", C("MRN"))
cty("Sequatchie County / Dunlap Chamber & Tourism", "Director", S_IN, "Chamber / tourism", "tourism_org", "R3", C("SEQ"))
cty("Bledsoe County Chamber of Commerce", "President", S_IN, "Chamber / tourism", "tourism_org", "R3", C("BLE"))
cty("Southeast Tennessee Tourism Association", "President", S_IN, "Regional tourism", "tourism_org", "R3", C("MRN", "SEQ", "BLE", "GRU"))
plc("Lodge Cast Iron", "Community / Corporate Affairs Director", S_IN, "Manufacturer / heritage tourism anchor", "industry_company", "R3", "47:South Pittsburg", C("MRN"), pr=2, notes="National Cornbread Festival host")
cty("Sequatchie Valley Electric Cooperative", "General Manager", S_IN, "Rural electric coop", "utility_coop", "R3", C("MRN", "SEQ", "BLE", "GRU"), pr=2, notes="Verify service territory")
site("Tennessee Tree Toppers (Henson Gap hang-gliding launch)", "President", S_NP, "Adventure recreation / tourism", "ngo_advocacy", "R3", "Henson Gap", C("SEQ"), 35.36, -85.33, 50, pr=3, notes="Coords approximate")
sta("Tennessee Forestry Association", "Executive Vice President", S_IN, "Timber industry association", "industry_assoc", "R3", "47")
cty("Tennessee Farm Bureau - Marion / Sequatchie / Bledsoe County FBs", "County Farm Bureau Presidents", S_PL, "Farm landowner association", "industry_assoc", "R3", C("MRN", "SEQ", "BLE"))
cty("Marion / Sequatchie / Bledsoe Soil Conservation Districts", "District Chairs", S_LO, "Soil conservation district", "conservation_district", "R3", C("MRN", "SEQ", "BLE"), pr=2)
parcel("Private landowner - Sequatchie Valley farm, Marion Co.", "Landowner", S_PL, "Private agricultural landowner", "private_landowner", "R3", C("MRN"), 600)
parcel("Private landowner - plateau forest tract, Sequatchie Co.", "Landowner", S_PL, "Private forest landowner", "private_landowner", "R3", C("SEQ"), 1500)
parcel("Private landowner - Walden Ridge forest tract, Bledsoe Co.", "Landowner", S_PL, "Private forest landowner", "private_landowner", "R3", C("BLE"), 2000)
parcel("Timber / TIMO landowner - Bledsoe / Sequatchie plateau", "Regional Forester / Land Manager", S_IN, "Industrial / investment timberland", "industry_company", "R3", C("BLE"), 8000)

# ======================= R4 TN Northern Plateau & Caney Fork =======================
cty("Warren County (TN) Government", "County Executive", S_LO, "County government (At-Risk)", "county_exec", "R4", C("WAR"))
plc("City of McMinnville", "Mayor", S_LO, "Municipal government", "municipal_exec", "R4", "47:McMinnville", C("WAR"))
plc("Town of Morrison", "Mayor", S_LO, "Municipal government", "municipal_exec", "R4", "47:Morrison", C("WAR"), pr=3)
cty("DeKalb County (TN) Government", "County Mayor", S_LO, "County government (At-Risk)", "county_exec", "R4", C("DEK"))
plc("City of Smithville", "Mayor", S_LO, "Municipal government (lake gateway)", "municipal_exec", "R4", "47:Smithville", C("DEK"))
plc("Town of Alexandria", "Mayor", S_LO, "Municipal government", "municipal_exec", "R4", "47:Alexandria", C("DEK"), pr=3)
plc("Town of Liberty", "Mayor", S_LO, "Municipal government", "municipal_exec", "R4", "47:Liberty", C("DEK"), pr=3)
cty("Van Buren County (TN) Government", "County Executive", S_LO, "County government (At-Risk)", "county_exec", "R4", C("VAN"))
plc("Town of Spencer", "Mayor", S_LO, "Municipal government (Fall Creek gateway)", "municipal_exec", "R4", "47:Spencer", C("VAN"))
cty("Upper Cumberland Development District", "Executive Director", S_LO, "Regional development district / ARC LDD", "regional_council", "R4", C("WAR", "DEK", "VAN"), notes="14-county district")
site("TDEC - Fall Creek Falls State Park", "Park Manager", S_ST, "Public state parks", "state_park_unit", "R4", "Fall Creek Falls State Park", C("VAN", "BLE"), 35.66, -85.35, 29800)
site("TDEC - Rock Island State Park", "Park Manager", S_ST, "Public state parks", "state_park_unit", "R4", "Rock Island State Park", C("WAR"), 35.81, -85.64, 883)
site("TDEC - Edgar Evins State Park", "Park Manager", S_ST, "Public state parks", "state_park_unit", "R4", "Edgar Evins State Park", C("DEK"), 36.08, -85.82, 6000)
sta("TDEC Natural Areas Program (statewide)", "Director, Natural Areas", S_ST, "State natural areas", "state_agency_hq", "R4", "47", pr=2)
site("TDEC Natural Areas - Big Bone Cave SNA", "Stewardship Ecologist (Cumberland Plateau)", S_ST, "State natural areas", "state_agency_regional", "R4", "Big Bone Cave State Natural Area", C("VAN"), 35.77, -85.55, 334, pr=3)
cty("TN Division of Forestry - Cumberland Plateau / Upper Cumberland District", "District Forester", S_ST, "State forestry", "state_agency_regional", "R4", C("WAR", "DEK", "VAN"))
sta("TN Division of Forestry - Forest Legacy Program", "Forest Legacy Coordinator", S_ST, "State forestry / easements", "state_agency_hq", "R4", "47", pr=2)
cty("USACE Nashville District - Center Hill Lake", "Resource Manager", S_FE, "Federal reservoir lands", "federal_utility", "R4", C("DEK"), notes="Lake also in Putnam/White")
cty("TVA - Great Falls Reservoir", "Natural Resources Manager", S_FE, "Federal utility / reservoir lands", "federal_utility", "R4", C("WAR"), pr=2)
sta("USFWS Tennessee Ecological Services Field Office (Cookeville)", "Field Supervisor", S_FE, "Federal ES / endangered species", "federal_program", "R4", "47")
sta("USDA Rural Development - Tennessee", "Area Director", S_FE, "USDA rural development", "federal_program", "R4", "47", pr=2)
sta("The Nature Conservancy in Tennessee - Cumberland Plateau", "Cumberland Plateau Program Director", S_NP, "Land trust / conservation", "ngo_land_trust", "R4", "47")
sta("Tennessee Trails Association", "President", S_NP, "Trail org", "ngo_advocacy", "R4", "47", pr=2)
cty("Cumberland River Compact", "Executive Director", S_NP, "Watershed org (Caney Fork)", "ngo_advocacy", "R4", C("WAR", "DEK", "VAN"), pr=2)
site("Tennessee Tech University - Appalachian Center for Craft", "Director", S_AC, "University / craft heritage", "academic", "R4", "Appalachian Center for Craft", C("DEK"), 36.02, -85.86, 600, pr=2, notes="Coords approximate")
cty("Tennessee Nursery & Landscape Association", "Executive Director", S_IN, "Nursery industry (McMinnville)", "industry_assoc", "R4", C("WAR"))
site("Cumberland Caverns", "General Manager", S_IN, "Show cave / tourism (private land)", "industry_company", "R4", "Cumberland Caverns", C("WAR"), 35.70, -85.68, 500, pr=2, notes="Acres approximate")
cty("McMinnville-Warren County Chamber of Commerce", "President", S_IN, "Chamber / tourism", "tourism_org", "R4", C("WAR"))
cty("Smithville-DeKalb County Chamber of Commerce", "Director", S_IN, "Chamber / tourism", "tourism_org", "R4", C("DEK"))
cty("Van Buren County Chamber / Tourism", "Director", S_IN, "Chamber / tourism", "tourism_org", "R4", C("VAN"))
cty("Upper Cumberland Tourism Association", "Executive Director", S_IN, "Regional tourism", "tourism_org", "R4", C("WAR", "DEK", "VAN"))
cty("Caney Fork Electric Cooperative", "General Manager", S_IN, "Rural electric coop", "utility_coop", "R4", C("WAR", "DEK", "VAN"), pr=2, notes="Verify service territory")
cty("Tennessee Farm Bureau - Warren / DeKalb / Van Buren County FBs", "County Farm Bureau Presidents", S_PL, "Farm landowner association", "industry_assoc", "R4", C("WAR", "DEK", "VAN"))
cty("Warren / DeKalb / Van Buren Soil Conservation Districts", "District Chairs", S_LO, "Soil conservation district", "conservation_district", "R4", C("WAR", "DEK", "VAN"), pr=2)
parcel("Private landowner - nursery / farm operation, Warren Co.", "Landowner", S_PL, "Private agricultural landowner", "private_landowner", "R4", C("WAR"), 500)
parcel("Private landowner - Center Hill shoreline farm / forest, DeKalb Co.", "Landowner", S_PL, "Private landowner", "private_landowner", "R4", C("DEK"), 600)
parcel("Private landowner - plateau forest tract, Van Buren Co.", "Landowner", S_PL, "Private forest landowner", "private_landowner", "R4", C("VAN"), 2500)
parcel("Timber / TIMO landowner - Van Buren plateau", "Regional Forester / Land Manager", S_IN, "Industrial / investment timberland", "industry_company", "R4", C("VAN"), 8000)
sta("Eastern Band of Cherokee Indians - Tribal Historic Preservation Office", "THPO", S_TR, "Tribal cultural resources", "tribal_thpo", "R1", "ALL", notes="Russell Cave, cave & mound sites; Section 106")

# ---- per-row overrides (applied on top of role defaults) ----
OV = {
    "Department of the Air Force - Arnold AFB / AEDC": dict(d_speed=0.15, d_freedom=0.15),
    "US Army Garrison Redstone Arsenal - Environmental Management Division": dict(d_speed=0.15, d_freedom=0.15),
    "University of the South - Office of Domain Management": dict(authority=3),
    "City of Huntsville": dict(authority=5),
    "Thrive Regional Partnership": dict(d_authority=0.0, d_fiscal=0.4),
}

COLS = ["stakeholder_id", "org", "poc_role", "poc_name", "poc_email", "sector", "sub_sector", "role_class",
        "event_region", "event_region_name", "geo_type", "geo_ref", "counties_fips", "counties", "lat", "lon",
        "approx_acres", "priority", "authority", "constituency", "d_control", "d_approval", "d_fiscal",
        "d_authority", "d_speed", "d_freedom", "geom_status", "notes"]

out = []
for i, r in enumerate(R, 1):
    org, poc, sector, sub, rc, ev, gt, gref, cs, lat, lon, ac, pr, notes, ov = r
    A, cons, *d = ROLE_DEFAULTS[rc]
    row = dict(zip(["authority", "constituency", "d_control", "d_approval", "d_fiscal", "d_authority", "d_speed", "d_freedom"], [A, cons] + d))
    row.update(OV.get(org, {})); row.update(ov)
    geom_status = {"county": "exact (TIGER)", "place": "exact (TIGER)", "state_aoi": "exact (TIGER)",
                   "site": "PAD-US match else point+acres", "multi_site": "PAD-US match else point+acres",
                   "parcel_placeholder": "PLACEHOLDER - needs parcel"}[gt]
    out.append(dict(stakeholder_id=f"SEEDS-{i:03d}", org=org, poc_role=poc, poc_name="TBD - verify", poc_email="",
                    sector=sector, sub_sector=sub, role_class=rc, event_region=ev, event_region_name=REGION[ev],
                    geo_type=gt, geo_ref=gref, counties_fips=cs,
                    counties="; ".join(NAME[c] for c in cs.split(";")), lat=lat, lon=lon, approx_acres=ac,
                    priority=pr, geom_status=geom_status, notes=notes, **row))

os.makedirs("out", exist_ok=True)
with open("out/seeds_stakeholder_pool.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(out)

# summary
from collections import Counter
print("total", len(out))
print(Counter(o["event_region"] for o in out))
print(Counter(o["sector"] for o in out))
print(Counter((o["event_region"], o["priority"]) for o in out))
