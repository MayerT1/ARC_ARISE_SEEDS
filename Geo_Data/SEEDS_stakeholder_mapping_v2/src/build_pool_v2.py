"""SEEDS stakeholder pool v2 — 8 events, realistic attendee roles, researched names.
Inputs : out/seeds_stakeholder_pool.csv (v1), research/contacts_*.py
Output : out/seeds_stakeholder_pool_v2.csv / .xlsx / .md
"""
import csv, re, sys, pandas as pd
sys.path.insert(0, 'research')
from contacts_tn_1 import TN1
from contacts_2 import C2
from contacts_3 import C3
from contacts_4 import FILL, C4, NEW_ORG, DROP_TEMPLATES
from build_pool import ROLE_DEFAULTS, F, NAME  # noqa (v1 tables)

ROLE_DEFAULTS = dict(ROLE_DEFAULTS)
ROLE_DEFAULTS['extension'] = (2, 0.6, 0.1, 0.6, 0.3, 0.0, 0.6, 0.6)

EVENTS = {  # 4 per state
 'A1': ('Huntsville Metro', 'Huntsville'),
 'A2': ('East Madison & Paint Rock Valley', 'Gurley / Paint Rock'),
 'A3': ('Lake Guntersville & Sand Mountain', 'Guntersville'),
 'A4': ('Scottsboro & NE Jackson (Tennessee River / plateau)', 'Scottsboro'),
 'T1': ('Highland Rim: Franklin + Coffee', 'Winchester / Tullahoma'),
 'T2': ('South Cumberland: Grundy + Marion', 'Monteagle / Tracy City'),
 'T3': ('Sequatchie Valley & Fall Creek: Sequatchie + Bledsoe + Van Buren', 'Pikeville / Dunlap'),
 'T4': ('Caney Fork & Center Hill: Warren + DeKalb', 'McMinnville / Smithville'),
}
CTY_EVENT = {'MAD': 'A1', 'MAR': 'A3', 'JAC': 'A4', 'FRA': 'T1', 'COF': 'T1', 'GRU': 'T2', 'MRN': 'T2',
             'SEQ': 'T3', 'BLE': 'T3', 'VAN': 'T3', 'WAR': 'T4', 'DEK': 'T4'}
FIPS2K = {v: k for k, v in F.items()}
A2_KEYS = ['Paint Rock', 'Gurley', 'New Hope (AL)', 'Owens Cross', 'Skyline', 'Walls of Jericho', 'Sauta', 'Fern Cave']

def C(*k): return ';'.join(F[x] for x in k)
AL, TN = ['MAD', 'MAR', 'JAC'], ['FRA', 'COF', 'GRU', 'MRN', 'SEQ', 'BLE', 'WAR', 'DEK', 'VAN']

# org_key -> (sector, sub_sector, role_class, event, geo_type, geo_ref, counties, lat, lon, acres)
S, L, Fe, P, I, N, A = 'State', 'Local/Municipal', 'Federal', 'Private Landowner', 'Industry/Private Sector', 'Nonprofit/Conservation', 'Academic'
def st(s): return C(*(AL if s == '01' else TN if s == '47' else AL + TN))
ORG = {
 'TSP_HQ': (S, 'State parks system', 'state_agency_hq', 'T2', 'state_aoi', '47', st('47'), '', '', ''),
 'TDEC_HQ': (S, 'State conservation agency', 'state_agency_hq', 'T1', 'state_aoi', '47', st('47'), '', '', ''),
 'TDEC_OOR': (S, 'State outdoor recreation grants', 'state_agency_hq', 'T2', 'state_aoi', '47', st('47'), '', '', ''),
 'TSP_AREA4': (S, 'State parks area office', 'state_agency_regional', 'T3', 'county', C('MRN', 'SEQ', 'BLE', 'WAR', 'DEK'), C('MRN', 'SEQ', 'BLE', 'WAR', 'DEK'), '', '', ''),
 'CTSP': (S, 'Public state parks (linear trail)', 'state_park_unit', 'T3', 'county', C('MRN', 'SEQ', 'BLE'), C('MRN', 'SEQ', 'BLE'), '', '', ''),
 'FGSP': (S, 'Public state parks', 'state_park_unit', 'T2', 'site', 'Fiery Gizzard State Park|South Cumberland State Park', C('GRU', 'MRN'), '35.25', '-85.75', '7800'),
 'SGSP': (S, 'Public state parks', 'state_park_unit', 'T2', 'site', 'Savage Gulf State Park|Savage Gulf State Natural Area', C('GRU', 'SEQ'), '35.43', '-85.58', '19000'),
 'HOTC': (S, 'Public state parks', 'state_park_unit', 'T1', 'site', 'Head of the Crow State Park|Sherwood Forest State Natural Area|Carter State Natural Area', C('FRA'), '35.12', '-85.95', '5000'),
 'FCFSP': (S, 'Public state parks', 'state_park_unit', 'T3', 'site', 'Fall Creek Falls State Park', C('VAN', 'BLE'), '35.66', '-85.35', '29800'),
 'TFSP': (S, 'Public state parks', 'state_park_unit', 'T1', 'site', 'Tims Ford State Park', C('FRA'), '35.215', '-86.24', '3546'),
 'OSF': (S, 'Public state parks (cultural)', 'state_park_unit', 'T1', 'site', 'Old Stone Fort State Archaeological Park', C('COF'), '35.486', '-86.10', '876'),
 'RISP': (S, 'Public state parks', 'state_park_unit', 'T4', 'site', 'Rock Island State Park', C('WAR'), '35.81', '-85.64', '883'),
 'EESP': (S, 'Public state parks', 'state_park_unit', 'T4', 'site', 'Edgar Evins State Park', C('DEK'), '36.08', '-85.82', '6000'),
 'TDF_HQ': (S, 'State forestry', 'state_agency_hq', 'T4', 'state_aoi', '47', st('47'), '', '', ''),
 'TDF_COF_DEK_WAR': (S, 'State forestry (area forester)', 'state_agency_regional', 'T4', 'county', C('COF', 'DEK', 'WAR'), C('COF', 'DEK', 'WAR'), '', '', ''),
 'TDF_FRA_GRU_MRN': (S, 'State forestry (area forester)', 'state_agency_regional', 'T2', 'county', C('FRA', 'GRU', 'MRN'), C('FRA', 'GRU', 'MRN'), '', '', ''),
 'TDF_BLE': (S, 'State forestry (area forester)', 'state_agency_regional', 'T3', 'county', C('BLE'), C('BLE'), '', '', ''),
 'TDF_SEQ_VAN': (S, 'State forestry (area forester)', 'state_agency_regional', 'T3', 'county', C('SEQ', 'VAN'), C('SEQ', 'VAN'), '', '', ''),
 'TWRA_R3': (S, 'State wildlife mgmt', 'state_agency_regional', 'T3', 'county', C('GRU', 'MRN', 'SEQ', 'BLE', 'WAR', 'DEK', 'VAN'), C('GRU', 'MRN', 'SEQ', 'BLE', 'WAR', 'DEK', 'VAN'), '', '', ''),
 'TWRA_R2': (S, 'State wildlife mgmt', 'state_agency_regional', 'T1', 'county', C('FRA', 'COF'), C('FRA', 'COF'), '', '', ''),
 'TENNGREEN': (N, 'Land trust', 'ngo_land_trust', 'T2', 'state_aoi', '47', st('47'), '', '', ''),
 'TNC_TN': (N, 'Land trust / conservation', 'ngo_land_trust', 'T2', 'state_aoi', '47', st('47'), '', '', ''),
 'TCF_TN': (N, 'Land conservation', 'ngo_land_trust', 'T1', 'state_aoi', '47', st('47'), '', '', ''),
 'LTT': (N, 'Land trust / easements', 'ngo_land_trust', 'T1', 'state_aoi', '47', st('47'), '', '', ''),
 'FSC': (N, 'Park friends group', 'ngo_advocacy', 'T2', 'county', C('GRU', 'MRN', 'FRA'), C('GRU', 'MRN', 'FRA'), '', '', ''),
 'TWF': (N, 'Wildlife advocacy', 'ngo_advocacy', 'T4', 'state_aoi', '47', st('47'), '', '', ''),
 'TFA': (I, 'Timber industry / Tree Farm', 'industry_assoc', 'T3', 'state_aoi', '47', st('47'), '', '', ''),
 'TFBF': (P, 'Farm landowner association', 'industry_assoc', 'T1', 'state_aoi', '47', st('47'), '', '', ''),
 'TVA_NRR': (Fe, 'Federal utility / reservoir lands', 'federal_utility', 'T1', 'state_aoi', 'ALL', st('ALL'), '', '', ''),
 'SCTDD': (L, 'Regional development district / ARC LDD', 'regional_council', 'T1', 'county', C('FRA', 'COF'), C('FRA', 'COF'), '', '', ''),
 'SETDD': (L, 'Regional development district / ARC LDD', 'regional_council', 'T3', 'county', C('GRU', 'MRN', 'SEQ', 'BLE'), C('GRU', 'MRN', 'SEQ', 'BLE'), '', '', ''),
 'UCDD': (L, 'Regional development district / ARC LDD', 'regional_council', 'T4', 'county', C('WAR', 'DEK', 'VAN'), C('WAR', 'DEK', 'VAN'), '', '', ''),
 'TARCOG': (L, 'Regional COG / ARC LDD', 'regional_council', 'A1', 'county', C('MAD', 'MAR', 'JAC'), C('MAD', 'MAR', 'JAC'), '', '', ''),
 'DEK_CHAMBER': (I, 'Chamber / tourism', 'tourism_org', 'T4', 'county', C('DEK'), C('DEK'), '', '', ''),
 'AAFB': (Fe, 'DoW installation', 'federal_installation', 'T1', 'site', 'Arnold Air Force Base|Arnold Engineering Development Complex', C('COF', 'FRA'), '35.39', '-86.06', '39000'),
 'HSV_PARKS': (L, 'Municipal parks/greenways', 'municipal_dept', 'A1', 'place', '01:Huntsville', C('MAD'), '', '', ''),
 'ASP_HQ': (S, 'State parks system', 'state_agency_hq', 'A1', 'state_aoi', '01', st('01'), '', '', ''),
 'ASP_NW': (S, 'Public state parks (district)', 'state_park_unit', 'A1', 'multi_site', 'Monte Sano State Park|Cathedral Caverns State Park', C('MAD', 'MAR'), '34.745|34.573', '-86.512|-86.222', '2140|493'),
 'ASP_NE': (S, 'Public state parks', 'state_park_unit', 'A3', 'site', 'Lake Guntersville State Park', C('MAR'), '34.391', '-86.205', '6000'),
 'AFC_NE': (S, 'State forestry (region)', 'state_agency_regional', 'A4', 'county', C('MAD', 'MAR', 'JAC'), C('MAD', 'MAR', 'JAC'), '', '', ''),
 'AFC_MAR': (S, 'State forestry (county)', 'state_agency_regional', 'A3', 'county', C('MAR'), C('MAR'), '', '', ''),
 'ACES_NE': ('Academic', 'Cooperative Extension', 'extension', 'A2', 'county', C('JAC', 'MAD'), C('JAC', 'MAD'), '', '', ''),
 'TNC_AL': (N, 'Land trust / conservation', 'ngo_land_trust', 'A2', 'county', C('JAC', 'MAD', 'MAR'), C('JAC', 'MAD', 'MAR'), '', '', ''),
 'PRFRC': (A, 'Research station / preserve', 'academic', 'A2', 'site', 'Sharp-Bingham Mountain Preserve|Paint Rock Forest Research Center', C('JAC'), '34.83', '-86.20', '4000'),
 'ATFA': (P, 'Private forest landowner association', 'industry_assoc', 'A3', 'state_aoi', '01', st('01'), '', '', ''),
 'AFA': (I, 'Timber industry association', 'industry_assoc', 'A3', 'state_aoi', '01', st('01'), '', '', ''),
 'AFF': (P, 'Forest landowner outreach / Tree Farm', 'industry_assoc', 'A4', 'state_aoi', '01', st('01'), '', '', ''),
 'AWF': (N, 'Wildlife advocacy', 'ngo_advocacy', 'A1', 'state_aoi', '01', st('01'), '', '', ''),
 'WFF_D1': (S, 'State wildlife mgmt', 'state_agency_regional', 'A1', 'county', C('MAD'), C('MAD'), '', '', ''),
 'WFF_D2': (S, 'State wildlife mgmt', 'state_agency_regional', 'A4', 'county', C('JAC', 'MAR'), C('JAC', 'MAR'), '', '', ''),
 'WFF_SKYLINE': (S, 'State WMA', 'state_agency_regional', 'A2', 'site', 'Skyline Wildlife Management Area|James D. Martin-Skyline WMA|Walls of Jericho', C('JAC'), '34.97', '-86.08', '60000'),
 'WFF_PRIV': (S, 'State private lands program', 'state_agency_hq', 'A2', 'state_aoi', '01', st('01'), '', '', ''),
 'UTE_WAR': ('Academic', 'Cooperative Extension', 'extension', 'T4', 'county', C('WAR'), C('WAR'), '', '', ''),
 'UTE_COF': ('Academic', 'Cooperative Extension', 'extension', 'T1', 'county', C('COF'), C('COF'), '', '', ''),
 'UTE_FRA': ('Academic', 'Cooperative Extension', 'extension', 'T1', 'county', C('FRA'), C('FRA'), '', '', ''),
 'UTE_MRN': ('Academic', 'Cooperative Extension', 'extension', 'T2', 'county', C('MRN'), C('MRN'), '', '', ''),
 'UTE_GRU': ('Academic', 'Cooperative Extension', 'extension', 'T2', 'county', C('GRU'), C('GRU'), '', '', ''),
 'TRAE': (N, 'TBD', 'ngo_advocacy', '', 'state_aoi', 'ALL', st('ALL'), '', '', ''),
}
for k, (sec, sub, rc, ev, gt, gref, cs) in NEW_ORG.items():
    conv = lambda x: ';'.join(F[c] for c in x.split(';'))
    gref2 = conv(gref) if gt == 'county' else gref
    cs2 = gref2 if gt == 'county' else (st(gref) if gt == 'state_aoi' else conv(cs))
    ORG[k] = (sec, sub, rc, ev, gt, gref2, cs2, '', '', '')
SENIOR = {'Chris Padgett', 'Greer Tidwell', 'Laurel Creech', 'Mitch Reid', 'Matthew Capps', 'Chris Isaacson', 'Mike Butler', 'Heather Slayton', 'Kim Moore'}

rows, seen = [], {}
for rec in TN1 + C2 + C3 + C4:
    name, title, org, key, email, basis, src, asof, notes = rec
    seen[name] = (name, title, org, key, email, basis, src, asof, notes)   # later batches override
for name, (name, title, org, key, email, basis, src, asof, notes) in seen.items():
    sec, sub, rc, ev, gt, gref, cs, lat, lon, ac = ORG[key]
    pr = 3 if name in SENIOR else 1
    verify = 'Y' if (basis != 'published' or 'erify' in notes or asof < '2025') else 'N'
    rows.append(dict(org=org, poc_name=name, poc_role=title, poc_email=email, email_basis=basis, source_url=src, as_of=asof,
                     verify_flag=verify, sector=sec, sub_sector=sub, role_class=rc, event_region=ev, geo_type=gt, geo_ref=gref,
                     counties_fips=cs, lat=lat, lon=lon, approx_acres=ac, priority=pr, notes=notes, src_tag='researched'))
named_keys = {ORG[k][0] for k in []}

# ---------- carry over v1 institutional rows not superseded ----------
v1 = pd.read_csv('out/seeds_stakeholder_pool.csv', dtype=str).fillna('')
SUPERSEDED = ['Tims Ford State Park', 'South Cumberland State Park', 'Old Stone Fort', 'Fall Creek Falls', 'Rock Island State Park',
              'Edgar Evins', 'Cumberland Trail State Park', 'TN Division of Forestry - Franklin', 'TWRA Region', 'Development District',
              'TARCOG', 'Arnold AFB', 'Huntsville - Parks', 'Monte Sano', 'Lake Guntersville State Park', 'Cathedral Caverns',
              'Alabama Forestry Commission - Northeast', 'Nature Conservancy in Alabama', 'Nature Conservancy in Tennessee',
              'Tennessee Parks & Greenways', 'Land Trust for Tennessee', 'Friends of South Cumberland', 'TDEC Division of Parks',
              'Alabama TREASURE', 'Alabama Forestry Association', 'Tennessee Forestry Association', 'District I (Skyline',
              'Smithville-DeKalb', 'Tennessee Wildlife Federation', 'Farm Bureau', 'Farmers Federation', 'Soil Conservation',
              'Soil & Water', 'USDA NRCS', 'Chamber', 'Tourism (CVB)', 'Coffee County Tourism', 'Convention & Visitors Bureau']
for _, r in v1.iterrows():
    if r.role_class == 'municipal_exec' or any(s in r.org for s in SUPERSEDED):
        continue
    if r.geo_type == 'parcel_placeholder':
        continue                                 # replaced by parcel notebook output
    d = r.to_dict()
    first = FIPS2K[r.counties_fips.split(';')[0]]
    ev = 'A2' if any(k in r.org for k in A2_KEYS) else ('A4' if 'Russell Cave' in r.org else CTY_EVENT[first])
    role = r.poc_role
    if r.role_class == 'county_exec':
        role, pr = 'County Mayor/Chair (courtesy invite) or designee - chief of staff / grants coordinator', '3'
    else:
        pr = r.priority
    rows.append(dict(org=r.org, poc_name='TBD - verify', poc_role=role, poc_email='', email_basis='none', source_url='', as_of='',
                     verify_flag='Y', sector=r.sector, sub_sector=r.sub_sector, role_class=r.role_class, event_region=ev,
                     geo_type=r.geo_type, geo_ref=r.geo_ref, counties_fips=r.counties_fips, lat=r.lat, lon=r.lon,
                     approx_acres=r.approx_acres, priority=int(pr), notes=r.notes, src_tag='v1_role'))

# ---------- realistic-attendee templates per county ----------
CNAME = {k: NAME[F[k]].rsplit(' ', 1)[0] for k in F}
ST = {k: ('AL' if k in AL else 'TN') for k in F}
def tpl(org, role, sec, sub, rc, k, pr, notes=''):
    rows.append(dict(org=org, poc_name='TBD - verify', poc_role=role, poc_email='', email_basis='none', source_url='', as_of='',
                     verify_flag='Y', sector=sec, sub_sector=sub, role_class=rc, event_region=CTY_EVENT[k], geo_type='county',
                     geo_ref=F[k], counties_fips=F[k], lat='', lon='', approx_acres='', priority=pr, notes=notes, src_tag='template'))
have_ext = {'WAR', 'COF', 'FRA', 'MRN', 'GRU'}
for k in F:
    c, s = CNAME[k], ST[k]
    tpl(f'{c} County ({s}) - Planning / Economic Development', 'Planning Director or Economic Development Director', L, 'County planning / ED', 'municipal_dept', k, 1)
    tpl(f'{c} County ({s}) - Parks & Recreation', 'County Parks & Recreation Director', L, 'County parks', 'municipal_dept', k, 1)
    if k not in have_ext:
        tpl(f'{"UT-TSU Extension" if s == "TN" else "Alabama Cooperative Extension"} - {c} County', 'County Extension Director / ANR Agent', 'Academic', 'Cooperative Extension', 'extension', k, 1, 'Private landowner engagement point')
    tpl(f'USDA NRCS - {c} County Service Center', 'District Conservationist', Fe, 'USDA conservation programs', 'federal_program', k, 1, 'Private landowner engagement point (EQIP/CSP/ACEP)')
    tpl(f'USDA FSA - {c} County Office', 'County Executive Director', Fe, 'USDA farm programs', 'federal_program', k, 2, 'Private landowner engagement point (CRP)')
    tpl(f'{c} County {"Soil Conservation" if s == "TN" else "Soil & Water Conservation"} District', 'District Manager / Administrative Coordinator', L, 'Conservation district', 'conservation_district', k, 2)
    tpl(f'{c} County {"Farm Bureau" if s == "TN" else "Farmers Federation (ALFA)"}', 'County President / Board', P, 'Farm landowner association', 'industry_assoc', k, 2, 'Private landowner channel')
    tpl(f'{c} County {"Forestry Association (CFA)" if s == "TN" else "Forestry Planning Committee"}', 'President / Chair', P, 'Forest landowner association', 'industry_assoc', k, 2, 'Private forest landowner channel')
    if s == 'TN':
        tpl(f'{c} County Chamber of Commerce / Tourism', 'Executive Director / Tourism Director', I, 'Chamber / tourism', 'tourism_org', k, 1)
CHAMBERS_AL = [('Huntsville/Madison County Convention & Visitors Bureau (Visit Huntsville)', 'MAD'), ('Marshall County Convention & Visitors Bureau', 'MAR'), ('Mountain Lakes Chamber of Commerce (Jackson Co.)', 'JAC')]
for org, k in CHAMBERS_AL:
    tpl(org, 'Destination development / partnerships manager', I, 'Tourism CVB', 'tourism_org', k, 1)

CITIES = [  # (place, state fips, county key, big?)
 ('Huntsville', '01', 'MAD', True), ('Madison', '01', 'MAD', True), ('Gurley', '01', 'MAD', False), ('New Hope', '01', 'MAD', False),
 ('Guntersville', '01', 'MAR', True), ('Albertville', '01', 'MAR', True), ('Arab', '01', 'MAR', True), ('Boaz', '01', 'MAR', False),
 ('Scottsboro', '01', 'JAC', True), ('Stevenson', '01', 'JAC', False), ('Bridgeport', '01', 'JAC', False),
 ('Winchester', '47', 'FRA', True), ('Decherd', '47', 'FRA', False), ('Cowan', '47', 'FRA', False), ('Estill Springs', '47', 'FRA', False),
 ('Manchester', '47', 'COF', True), ('Tullahoma', '47', 'COF', True), ('Monteagle', '47', 'GRU', False), ('Tracy City', '47', 'GRU', False),
 ('Altamont', '47', 'GRU', False), ('Beersheba Springs', '47', 'GRU', False), ('Jasper', '47', 'MRN', False), ('South Pittsburg', '47', 'MRN', False),
 ('Kimball', '47', 'MRN', False), ('Whitwell', '47', 'MRN', False), ('Dunlap', '47', 'SEQ', False), ('Pikeville', '47', 'BLE', False),
 ('McMinnville', '47', 'WAR', True), ('Smithville', '47', 'DEK', False), ('Alexandria', '47', 'DEK', False), ('Spencer', '47', 'VAN', False)]
for pl, stf, k, big in CITIES:
    ev = 'A2' if pl in ('Gurley', 'New Hope') else CTY_EVENT[k]
    base = dict(poc_name='TBD - verify', poc_email='', email_basis='none', source_url='', as_of='', verify_flag='Y', sector=L,
                event_region=ev, geo_type='place', geo_ref=f'{stf}:{pl}', counties_fips=F[k], lat='', lon='', approx_acres='', src_tag='template')
    if pl == 'Huntsville':
        rows.append(base | dict(org='City of Huntsville - Planning (Greenways / Open Space)', poc_role='Planning Director / Greenway Planner', sub_sector='Municipal planning', role_class='municipal_dept', priority=1, notes=''))
        continue
    rows.append(base | dict(org=f'City/Town of {pl} - Parks & Recreation / Public Works', poc_role='Parks & Recreation Director (or Public Works / Town Administrator)', sub_sector='Municipal parks', role_class='municipal_dept', priority=1 if big else 2, notes='Gateway community'))
    if big:
        rows.append(base | dict(org=f'City of {pl} - Planning & Community Development', poc_role='Planning / Community Development Director', sub_sector='Municipal planning', role_class='municipal_dept', priority=1, notes=''))

# ---------- drop non-existent template orgs ----------
rows = [r for r in rows if not any(d in r['org'] for d in DROP_TEMPLATES)]
# ---------- fill TBD rows with researched names ----------
import copy
EXEC = ('Mayor', 'Chairman', 'County Executive')
nfill = 0
for key, people in FILL.items():
    hits = [r for r in rows if key in r['org'] and r['poc_name'] == 'TBD - verify'] or [r for r in rows if key in r['org']]
    if not hits:
        print('!! FILL key not matched:', key); continue
    base = hits[0]
    for i, (nm, role, email, basis, src, asof, notes) in enumerate(people):
        tgt = base if i == 0 else copy.deepcopy(base)
        tgt.update(poc_name=nm, poc_role=role, poc_email=email, email_basis=basis, source_url=src, as_of=asof,
                   verify_flag='Y' if (basis != 'published' or 'erify' in notes or asof < '2025' or nm.startswith('TBD')) else 'N',
                   notes=(notes + ' | ' + str(base.get('notes', ''))).strip(' |'), src_tag='researched' if not nm.startswith('TBD') else base['src_tag'])
        if i > 0:
            tgt['priority'] = 3 if any(e in role for e in EXEC) else 1
            rows.append(tgt)
        nfill += 0 if nm.startswith('TBD') else 1
print('filled/added named rows:', nfill)

# ---------- assemble ----------
df = pd.DataFrame(rows)
df = df.drop_duplicates(subset=['org', 'poc_name', 'poc_role'])
dims = df.role_class.map(ROLE_DEFAULTS)
for i, c in enumerate(['authority', 'constituency', 'd_control', 'd_approval', 'd_fiscal', 'd_authority', 'd_speed', 'd_freedom']):
    df[c] = dims.map(lambda t: t[i])
df.loc[df.role_class.eq('county_exec'), 'authority'] = 5
df.loc[df.org.str.contains('Arnold|Redstone', regex=True), ['d_speed', 'd_freedom']] = 0.15
df['event_name'] = df.event_region.map(lambda e: EVENTS.get(e, ('auto (notebook assigns by footprint)', ''))[0])
df['counties'] = df.counties_fips.map(lambda s: '; '.join(NAME[x] for x in s.split(';')))
df['geom_status'] = df.geo_type.map({'county': 'exact (TIGER)', 'place': 'exact (TIGER)', 'state_aoi': 'exact (TIGER)',
                                     'site': 'PAD-US match else point+acres', 'multi_site': 'PAD-US match else point+acres'})
df['approved_for_invite'] = True
df = df.sort_values(['event_region', 'priority', 'sector', 'org']).reset_index(drop=True)
df.insert(0, 'stakeholder_id', [f'SEEDS2-{i+1:03d}' for i in range(len(df))])
COLS = ['stakeholder_id', 'org', 'poc_name', 'poc_role', 'poc_email', 'email_basis', 'verify_flag', 'source_url', 'as_of', 'sector',
        'sub_sector', 'role_class', 'event_region', 'event_name', 'priority', 'geo_type', 'geo_ref', 'counties_fips', 'counties', 'lat', 'lon',
        'approx_acres', 'authority', 'constituency', 'd_control', 'd_approval', 'd_fiscal', 'd_authority', 'd_speed', 'd_freedom',
        'geom_status', 'approved_for_invite', 'src_tag', 'notes']
df = df[COLS]
df.to_csv('out/seeds_stakeholder_pool_v2.csv', index=False)
with pd.ExcelWriter('out/seeds_stakeholder_pool_v2.xlsx') as xw:
    df.to_excel(xw, 'pool', index=False)
    pd.DataFrame([(k, *v) for k, v in EVENTS.items()], columns=['event', 'name', 'hub']).to_excel(xw, 'events', index=False)
with open('out/seeds_stakeholder_pool_v2.md', 'w') as f:
    f.write('# SEEDS focus-group stakeholder pool v2 (8 events)\n\nNamed contacts are from public sources (see source_url, as_of). '
            '`email_basis`: published = listed on a public page; pattern = agency address format, unverified. verify_flag=Y needs a check before invites.\n\n')
    for ev, g in df.groupby('event_region'):
        nm = EVENTS.get(ev, ('Auto-assign',))[0]
        f.write(f'## {ev} - {nm} ({len(g)})\n\n' + g[['stakeholder_id', 'org', 'poc_name', 'poc_role', 'poc_email', 'email_basis', 'sector', 'priority']].to_markdown(index=False) + '\n\n')
print(len(df), 'rows'); print(df.groupby(['event_region', 'priority']).size().unstack(fill_value=0))
print(df.sector.value_counts()); print('named:', (df.poc_name != 'TBD - verify').sum(), ' with email:', (df.poc_email != '').sum(),
      ' published email:', (df.email_basis == 'published').sum())
