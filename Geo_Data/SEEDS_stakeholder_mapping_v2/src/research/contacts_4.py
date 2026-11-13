"""Batch 4 - fills TBD template/v1 rows. FILL: org-substring -> list of
(name, role, email, email_basis, source_url, as_of, notes). First entry fills the TBD row; extras are cloned rows."""
MTAS = 'https://www.mtas.tennessee.edu/city/'
CTAS = 'https://ctas.tennessee.edu/county/'
TSU = 'https://www.tnstate.edu/extension/coopext_dir_county_staff.aspx'
SWCD = 'https://www.TN.gov/content/dam/tn/agriculture/documents/landwaterstewardship/SCDOnlineDirectory.pdf'
FILL = {
 # ---------- TN county executives (CTAS 2026) ----------
 'Franklin County (TN) Government': [('Chris Guess', 'County Mayor', 'fcmayor@franklincotn.gov', 'published', CTAS + 'franklin', '2026', '')],
 'Coffee County (TN) Government': [('Dennis Hunt', 'County Mayor', 'dhunt@cafes.net', 'published', CTAS + 'coffee', '2026', '')],
 'Grundy County (TN) Government': [('Michael Brady', 'County Mayor', 'grundymayor@yahoo.com', 'published', CTAS + 'grundy', '2026', '')],
 'Marion County (TN) Government': [('David Jackson Jr.', 'County Mayor', 'djackson@marioncountytn.net', 'published', CTAS + 'marion', '2026', '')],
 'Sequatchie County Government': [('Keith Cartwright', 'County Executive', 'seqexec@bledsoe.net', 'published', CTAS + 'sequatchie', '2026', '')],
 'Bledsoe County Government': [('Kris Frady', 'County Mayor', 'bledsoemayor@bledsoe.net', 'published', CTAS + 'bledsoe', '2026', '')],
 'Warren County (TN) Government': [('Terry Bell', 'County Executive', 'tbell@warrencountytn.gov', 'published', CTAS + 'warren', '2026', '')],
 'DeKalb County (TN) Government': [('Patrick Ray', 'County Mayor', 'dekalbmayorray@gmail.com', 'published', CTAS + 'dekalb', '2026', '')],
 'Van Buren County (TN) Government': [('Barry Austin', 'County Executive', 'mayorbaustin@outlook.com', 'published', CTAS + 'van-buren', '2026', '')],
 'DeKalb County (TN) - Planning': [('Brian Reed', 'Public Works Director (no county planning office listed)', 'dekalbtnrecycles@gmail.com', 'published', CTAS + 'dekalb', '2026', '')],
 # ---------- AL county ----------
 'Madison County Commission': [('Rex Vaughn', 'Commission Chairman (appointed Mar 2026)', '', 'none', 'https://www.madisoncountyal.gov/government/about-your-county/commission-chairman', '2026-03', 'Owner, Vaughn Farms')],
 'Marshall County Commission': [('John Young', 'Commission Chairman', '', 'none', 'https://governor.alabama.gov/newsroom/2025/08/governor-ivey-appoints-john-young-as-chairman-of-the-marshall-county-commission/', '2026-07', ''),
                                ('Ashleigh Bubbett', 'County Administrator (realistic attendee)', '', 'none', 'https://www.marshallal.gov/minutes/commissionminutes/2026%20May%2027.pdf', '2026-05', '')],
 'Madison County (AL) - Parks & Recreation': [('Ryan Yates', 'County Parks & Recreation Director', '', 'none', 'https://huntsvillebusinessjournal.com/news/2025/04/17/madison-county-parks-and-recreation-sees-increase-in-facility-usage-youth-sports-enrollment/', '2025-04', '')],
 'Jackson County (AL) - Planning': [('Karen Suggs', 'Project Manager, Jackson County Economic Development Authority', '', 'none', 'https://businessalabama.com/spotlight-on-jackson-marshall-dekalb-cherokee-movers-shapers-3/', '2025', 'Launch 2035 land use committee')],
 # ---------- TN cities (MTAS) ----------
 'City/Town of Winchester': [('Yvonne Stewart', 'Special Projects Coordinator (parks contact)', 'yvonnestewart@winchester-tn.com', 'published', 'https://www.mtas.tennessee.edu/parks_recdirectors', '2026', '')],
 'City of Winchester - Planning': [('Beth Rhoton', 'City Administrator', 'bethrhoton@winchester-tn.com', 'published', MTAS + 'winchester', '2026', '')],
 'City/Town of Decherd': [('Rob Bennett', 'City Administrator', 'rob.bennett@decherdtn.gov', 'published', MTAS + 'decherd', '2026', '')],
 'City/Town of Cowan': [('Amiee Ingle', 'City Recorder', 'amiee.ingle@cityofcowan.net', 'published', MTAS + 'cowan', '2026', '')],
 'City/Town of Estill Springs': [('Tina Smith', 'City Recorder', 'tsmith@united.net', 'published', MTAS + 'estill-springs', '2026', '')],
 'City/Town of Manchester': [('A.J. Fox', 'Parks & Recreation Director', 'ajfox@cityofmanchestertn.com', 'published', MTAS + 'manchester', '2026', '')],
 'City of Manchester - Planning': [('Brittany Fiske', 'Community Development & Zoning Director', 'bfiske@cityofmanchestertn.com', 'published', MTAS + 'manchester', '2026', '')],
 'City/Town of Tullahoma': [('J.P. Kraft', 'Parks & Recreation Director', 'jkraft@tullahomatn.gov', 'published', MTAS + 'tullahoma', '2026', '')],
 'City of Tullahoma - Planning': [('Winston Brooks', 'Community & Economic Development Director', 'wbrooks@tullahomatn.gov', 'published', MTAS + 'tullahoma', '2026', ''),
                                  ('Jason Quick', 'City Administrator', 'jquick@tullahomatn.gov', 'published', MTAS + 'tullahoma', '2026', '')],
 'City/Town of Monteagle': [('Debbie Taylor', 'City Recorder', 'debbieadmin@benlomand.net', 'published', MTAS + 'monteagle', '2026', '')],
 'City/Town of Tracy City': [('Roxanna Fults', 'City Recorder', 'tracycity@blomand.net', 'published', MTAS + 'tracy-city', '2026', '')],
 'City/Town of Altamont': [('Wendy Bess', 'City Recorder', 'altcityhall@blomand.net', 'published', MTAS + 'altamont', '2026', '')],
 'City/Town of Beersheba Springs': [('Natasha King', 'City Recorder', 'nking3611@gmail.com', 'published', MTAS + 'beersheba-springs', '2026', '')],
 'City/Town of Jasper': [('Justin Baker', 'Parks & Recreation Director / Street Supt.', '', 'none', MTAS + 'jasper', '2026', '423-942-5979'),
                         ('Paula Turney', 'City Recorder', 'paulaturney@jaspertn.gov', 'published', MTAS + 'jasper', '2026', '')],
 'City/Town of South Pittsburg': [('Michael Hudson', 'City Administrator', 'mhudson@southpittsburg-tn.gov', 'published', MTAS + 'south-pittsburg', '2026', '')],
 'City/Town of Kimball': [('Tonia May', 'City Recorder / HR Director', 'tmay@townofkimball.com', 'published', MTAS + 'kimball', '2026', '')],
 'City/Town of Whitwell': [('Lonnie Cleek', 'City Manager', 'lonnie@cityofwhitwell1956.org', 'published', MTAS + 'whitwell', '2026', '')],
 'City/Town of Dunlap': [('Clayton Smith', 'Public Works Director', 'csmith@cityofdunlap.com', 'published', MTAS + 'dunlap', '2026', ''),
                         ('Norman D. Hatfield', 'City Recorder', 'nhatfield@cityofdunlap.com', 'published', MTAS + 'dunlap', '2026', '')],
 'City/Town of Pikeville': [('Debra Barnett', 'City Recorder', 'cityrecorder@bledsoe.net', 'published', MTAS + 'pikeville', '2026', '')],
 'City/Town of McMinnville': [('Justin Scott', 'Parks & Recreation Director', 'jscott@mcminnvilletn.gov', 'published', 'https://www.mtas.tennessee.edu/city/mcminnville', '2026', '')],
 'City of McMinnville - Planning': [('David Baird', 'Director of Community Development', '', 'none', 'https://cms2.revize.com/revize/mcminnville/09.06.2022_McMinnville%20Parks%20&%20Recreation%20%20Final%20Draft.pdf', '2022', 'verify'),
                                    ('Kate Kemezis', 'Planner', '', 'none', 'https://cms2.revize.com/revize/mcminnville/09.06.2022_McMinnville%20Parks%20&%20Recreation%20%20Final%20Draft.pdf', '2022', 'verify')],
 'City/Town of Smithville': [('Kevin Robinson', 'Public Works Director', 'krobinson@smithvillecityhall.com', 'published', MTAS + 'smithville', '2026', '')],
 'City/Town of Alexandria': [('Jessica Howard', 'Town Recorder', 'town.recorder@townofalexandria.us', 'published', MTAS + 'alexandria', '2026', '')],
 'City/Town of Spencer': [('Crystal Crain', 'City Recorder', 'spencertngov@benlomand.net', 'published', MTAS + 'spencer', '2026', 'Fall Creek Falls gateway')],
 # ---------- AL cities ----------
 'City/Town of Madison': [('Kory Alfred', 'Parks & Recreation Director', '', 'none', 'https://www.themadisonrecord.com/2025/09/17/mcdab-presents-check-parks-recreation-chairperson-steps', '2025-09', '')],
 'City/Town of Guntersville': [('Matt Bryant', 'Parks & Recreation Director', '', 'none', 'https://www.guntersvilleal.org/parks-recreation', '2026', '256-571-7590')],
 'City of Scottsboro - Planning': [('Katie Kirkland', 'Events & Marketing Coordinator / Main Street Director', '', 'none', 'https://businessalabama.com/spotlight-on-jackson-marshall-dekalb-cherokee-movers-shapers-2/', '2025', 'verify')],
 # ---------- Extension ----------
 'UT-TSU Extension - Bledsoe': [('J.C. Rains', 'Extension Agent III & County Director (livestock/forage)', '', 'none', 'https://utia.tennessee.edu/person?id=5673', '2026', ''),
                                ('Whitney Jackson', 'Extension Agent, 4-H & ANR (TSU)', 'wsimmon2@tnstate.edu', 'published', TSU, '2026', '')],
 'UT-TSU Extension - Sequatchie': [('Dusty Ragland', 'Extension Agent (MS Wildlife Biology)', '', 'none', 'https://utia.tennessee.edu/person?id=21057', '2026', '')],
 'UT-TSU Extension - DeKalb': [('Brooklynn Gunter', 'Extension Agent, 4-H (TSU)', 'bgunter@tnstate.edu', 'published', TSU, '2026', 'Ask for county director')],
 'Alabama Cooperative Extension - Madison': [('Marcus Garner', 'Urban Regional Extension Agent (Madison/Marshall/Limestone)', '', 'none', 'https://ssl.acesag.auburn.edu/directory-new/u/Marcus-Garner-cngqPPYN', '2026', '256-532-1578')],
 'Alabama Cooperative Extension - Marshall': [('Brian Brown', 'Regional Extension Agent (Marshall/DeKalb/Etowah/Cherokee)', 'brownbw@auburn.edu', 'published', 'https://www.aces.edu/?p=109438', '2026', '')],
 'Alabama Cooperative Extension - Jackson': [('Jenna Schmidt', 'Extension Agent (Jackson/Marshall/NE AL)', '', 'none', 'https://www.aces.edu/?p=85768', '2026', 'verify program area')],
 # ---------- NRCS / SWCD ----------
 'USDA NRCS - Madison County': [('Anthony Hudson', 'District Conservationist (Huntsville Field Office)', 'anthony.hudson@usda.gov', 'pattern', 'https://southeastagnet.com/2014/02/18/alabamas-madison-county-earth-team-receives-national-award', '2014', 'OLD - verify; office 256-532-1677')],
 'USDA NRCS - Franklin County': [('TBD - verify', 'District Conservationist (Winchester FO)', '', 'none', 'https://www.Nrcs.Usda.Gov/sites/default/files/2022-10/Area%203%20Service%20Centers_0.pdf', '2022', 'Office 931-967-2521 x3')],
 'USDA NRCS - Coffee County': [('TBD - verify', 'District Conservationist (Manchester FO)', '', 'none', 'https://www.Nrcs.Usda.Gov/sites/default/files/2022-10/Area%203%20Service%20Centers_0.pdf', '2022', 'Office 931-728-2472 x3')],
 'USDA NRCS - Grundy County': [('TBD - verify', 'District Conservationist (Jasper FO; serves Grundy+Marion)', '', 'none', 'https://www.Nrcs.Usda.Gov/sites/default/files/2022-10/Area%203%20Service%20Centers_0.pdf', '2022', 'Office 423-942-2244 x3')],
 'USDA NRCS - Marion County': [('TBD - verify', 'District Conservationist (Jasper FO)', '', 'none', 'https://www.Nrcs.Usda.Gov/sites/default/files/2022-10/Area%203%20Service%20Centers_0.pdf', '2022', 'Office 423-942-2244 x3')],
 'USDA NRCS - Sequatchie County': [('TBD - verify', 'District Conservationist (Pikeville FO; serves Sequatchie+Bledsoe)', '', 'none', 'https://www.Nrcs.Usda.Gov/sites/default/files/2022-10/Area%203%20Service%20Centers_0.pdf', '2022', 'Office 423-447-2532 x3')],
 'USDA NRCS - Bledsoe County': [('TBD - verify', 'District Conservationist (Pikeville FO)', '', 'none', 'https://www.Nrcs.Usda.Gov/sites/default/files/2022-10/Area%203%20Service%20Centers_0.pdf', '2022', 'Office 423-447-2532 x3')],
 'USDA NRCS - Warren County': [('TBD - verify', 'District Conservationist (McMinnville FO; serves Warren+Van Buren)', '', 'none', 'https://www.Nrcs.Usda.Gov/sites/default/files/2022-10/Area%203%20Service%20Centers_0.pdf', '2022', 'Office 931-668-4383 x3')],
 'USDA NRCS - Van Buren County': [('TBD - verify', 'District Conservationist (McMinnville FO)', '', 'none', 'https://www.Nrcs.Usda.Gov/sites/default/files/2022-10/Area%203%20Service%20Centers_0.pdf', '2022', 'Office 931-668-4383 x3')],
 'USDA NRCS - DeKalb County': [('TBD - verify', 'District Conservationist (Smithville FO)', '', 'none', 'https://www.Nrcs.Usda.Gov/sites/default/files/2022-10/Area%203%20Service%20Centers_0.pdf', '2022', 'Office 615-597-8225 x3')],
 'Franklin County Soil Conservation': [('Carolyn Montoye', 'District Secretary', 'carolyn.montoye@tn.nacdnet.net', 'published', SWCD, 'unknown', '931-967-3504 x3')],
 'DeKalb County Soil Conservation': [('Pamela Hale', 'District Secretary', 'pamela.hale@tn.nacdnet.net', 'published', SWCD, 'unknown', '615-597-8226 x3')],
 'Bledsoe County Soil Conservation': [('Renita (Shorty) Beaty', 'District Secretary', '', 'none', 'https://www.tn.gov/agriculture/farms/conservation/agricultural-resources-conservation-fund_rd/swcd-online-directory.html', 'unknown', '423-447-2532 x3; listed email belongs to another person - verify')],
 'Madison County Soil & Water': [('Kathy Walker', 'District Administrative Coordinator', '', 'none', 'https://southeastagnet.com/2014/02/18/alabamas-madison-county-earth-team-receives-national-award', '2014', 'OLD - verify; 256-532-1692')],
 'Jackson County Soil & Water': [('Jim Green', 'District supervisor; AACD 2nd Vice President', '', 'none', 'https://alabamasoilandwater.gov/aacd', '2026', 'verify district role')],
 # ---------- tourism ----------
 'Huntsville/Madison County Convention': [('Jennifer Moore', 'President & CEO', '', 'none', 'https://www.huntsville.org/about-cvb/staff-directory/', '2026', '')],
 'Marshall County Convention': [('Katy Norton', 'President & CEO, Marshall County Tourism & Sports', '', 'none', 'https://www.northalabama.org/about-us/our-team/', '2026', '')],
 'Mountain Lakes Chamber': [('Lydia Pennington', 'Director of Marketing & Tourism', '', 'none', 'https://www.northalabama.org/about-us/our-team/', '2026', '')],
 'Alabama Mountain Lakes Tourist Association': [('Tami Reist', 'President & CEO', '', 'none', 'https://256today.com/amlas-karen-beasley-named-alabama-restaurant-and-hospitality-associations-tourism-promoter-of-the-year/', '2025', ''),
                                                ('Karen Beasley', 'VP Marketing & Communications', 'karen@northalabama.org', 'published', 'https://www.northalabama.org/articles/post/new-slate-of-officers-for-20252027/', '2025-09', '')],
 # ---------- NGOs / federal ----------
 'Singing River Trail': [('Misti Potter', 'Executive Director', '', 'none', 'https://singingrivertrail.com/looking-ahead-to-a-bright-2026/', '2026', '')],
 'Mountain Goat Trail Alliance': [('Patrick Dean', 'Executive Director', '', 'none', 'https://www.guidestar.org/profile/20-5363669', '2025', '')],
 'Tennessee River Gorge Trust': [('Eliot Berz', 'Executive Director', 'executivedirector@trgt.org', 'published', 'https://www.trgt.org/staff-board', '2026', '')],
 'Southeastern Climbers Coalition': [('Ben Lowe', 'Executive Director', 'ben@seclimbers.org', 'published', 'https://www.seclimbers.org/?p=586', '2026', ''),
                                     ('Kara Matassino', 'Stewardship Director', 'kara@seclimbers.org', 'published', 'https://www.seclimbers.org/?p=586', '2026', '')],
 'Cumberland River Compact': [('Mekayle Houghton', 'Executive Director', '', 'none', 'https://cumberlandrivercompact.org/team_member/mekayle-houghton/', '2026', ''),
                              ('Cooper Breeden', 'Land Conservation Program Manager', '', 'none', 'https://cumberlandrivercompact.org/team_member/cooper-breeden/', '2026', 'Private landowner engagement point')],
 'Russell Cave National Monument': [('Steve Theus', 'Superintendent (Little River Canyon NPres & Russell Cave NM)', '', 'none', 'https://www.nps.gov/ruca/learn/news/superintendent-steve-theus.htm', '2024', 'Superintendent vacancy posted 2026 - verify')],
 'Redstone Arsenal': [('Christine Easterwood', 'Ecologist, Environmental Management Division (INRMP lead)', '', 'none', 'https://denix.osd.mil/inrmp/denix-files/sites/98/2024/02/Final_Redstone_INRMP_2017-2021_Update.pdf', '2021', 'verify')],
}

# brand-new rows: (name, title, org, org_key, email, basis, src, asof, notes)  -> org_key must exist in ORG (build_pool_v2) or in NEW_ORG
NEW_ORG = {
 'HEC': ('Nonprofit/Conservation', 'Environmental coalition', 'ngo_advocacy', 'A1', 'place', '01:Huntsville', 'MAD'),
 'ALTA': ('Industry/Private Sector', 'Trail / active-transportation planning consultant', 'ngo_advocacy', 'A1', 'state_aoi', '01', None),
 'TNECD_SC': ('State', 'State econ dev regional director', 'state_agency_regional', 'T1', 'county', 'FRA;COF', 'FRA;COF'),
 'TNECD_UC': ('State', 'State econ dev regional director', 'state_agency_regional', 'T4', 'county', 'WAR;DEK;VAN', 'WAR;DEK;VAN'),
 'TNECD_SE': ('State', 'State econ dev regional director', 'state_agency_regional', 'T2', 'county', 'GRU;MRN;SEQ;BLE', 'GRU;MRN;SEQ;BLE'),
 'ACES_ADFO': ('Academic', 'Cooperative Extension (regional)', 'extension', 'A3', 'county', 'MAD;MAR;JAC', 'MAD;MAR;JAC'),
}
C4 = [
 ('Trae Watson', 'Planner / landscape architect (MLA) - trails & multimodal design', 'Alta Planning + Design', 'ALTA', 'traewatson@altago.com', 'pattern', 'https://altago.com/people/trae-watson/', '2026', 'USER-REQUESTED; AL trails; verify email'),
 ('Ankur Shah', 'President', 'Huntsville Environmental Coalition (HEC)', 'HEC', '', 'none', 'https://citylifestyle.com/articles/invest-in-sustainability', '2025', 'USER-REQUESTED org'),
 ('Emily Canfield', 'Board Member', 'Huntsville Environmental Coalition (HEC)', 'HEC', '', 'none', 'https://citylifestyle.com/articles/invest-in-sustainability', '2025', ''),
 ('John Hatfield', 'Regional Director (South Central TN; Coffee, Franklin)', 'TN Dept of Economic & Community Development', 'TNECD_SC', 'john.hatfield@tn.gov', 'published', 'https://tnecd.com/wp-content/uploads/2024/06/TNECD-Regional-Directors.pdf', '2024', 'verify county assignment'),
 ('Angela Regitko', 'Regional Director (Upper Cumberland; Warren, DeKalb, Van Buren)', 'TN Dept of Economic & Community Development', 'TNECD_UC', 'angela.regitko@tn.gov', 'published', 'https://tnecd.com/wp-content/uploads/2024/06/TNECD-Regional-Directors.pdf', '2024', ''),
 ('Lynn Tully', 'Regional Director (Southeast TN - probable)', 'TN Dept of Economic & Community Development', 'TNECD_SE', 'lynn.tully@tn.gov', 'published', 'https://tnecd.com/wp-content/uploads/2024/06/TNECD-Regional-Directors.pdf', '2024', 'Region assignment unclear on source - verify'),
 ('Chris Becker', 'Assistant Director for Field Operations, NE Alabama (Madison/Marshall/Jackson)', 'Alabama Cooperative Extension System', 'ACES_ADFO', '', 'none', 'https://www.aces.edu/?p=119246', '2025', 'Route to county Extension coordinators'),
 ('Creig Kimbro', 'Extension Agent III & County Co-Director (Regional Fisheries Agent)', 'UT-TSU Extension Grundy County', 'UTE_GRU', '', 'none', 'https://utia.tennessee.edu/person?id=13622', '2026', ''),
]
DROP_TEMPLATES = ['Forestry Association (CFA)']   # TDF lists no active CFA in any of the 9 TN AOI counties
