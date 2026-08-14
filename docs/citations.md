# Citations

Numbered sources for external factual claims made in the README, executive
summary, methodology report and dashboard. Dataset-level provenance (file
names, sizes, row counts, download times) is in
[data/raw/MANIFEST.md](../data/raw/MANIFEST.md) and
[source_inventory.md](source_inventory.md).

Where an official source carries the detail, it is cited in preference to
news coverage. News reporting is cited only for facts that official pages do
not state.

---

**[1] Buc-ee's Locations.** Buc-ee's Ltd. https://buc-ees.com/locations/
Accessed 2026-08-03.
Supports: the list of 17 open stores east of the Mississippi used in the
overlap calculation, and Mount Crawford as the only Virginia store listed as
operating. Note: the page does not separate open stores from planned ones,
so development status for planned sites comes from sources [3] to [7].

**[2] Virginia's first Buc-ee's opens soon: here's what to know.** Virginia
Business. https://virginiabusiness.com/virginia-buc-ees-opening-mount-crawford/
Accessed 2026-08-03.
Supports: Mount Crawford (Rockingham County, I-81 Exit 240) opened
2025-06-30. Store address 6500 Buc-ee's Blvd, per [1].

**[3] Buc-ee's of Stafford.** Stafford County, Virginia, Department of
Planning and Zoning.
https://staffordcountyva.gov/government/departments_p-z/planning_and_zoning/buc-ee_s_of_stafford.php
Accessed 2026-08-05.
Supports: the Stafford County Board of Supervisors voted to approve the
project on 2026-05-19; applications CUP24155520 (conditional use permit) and
RC25156318 (zoning reclassification); site of 36.18 acres on the east side of
Austin Ridge Drive in the Garrisonville Election District. The page states no
opening date and notes the project "will take significant time to build".
This is the basis for classifying Stafford as locally approved with no
confirmed opening date.

**[4] Beaver Fever Sweeps Stafford: Supervisors Approve Buc-ee's.** Potomac
Local News, 2026-05-20.
https://www.potomaclocal.com/2026/05/20/beaver-fever-sweeps-stafford-supervisors-approve-buc-ees/
Accessed 2026-08-03.
Supports: the approval vote was 5-2 and followed a public hearing running
into the early morning. Used only for the vote margin and hearing length,
which [3] does not state.

**[5] Buc-ee's Travel Center to expand to New Kent County.** New Kent County,
Virginia. https://www.newkent-va.us/CivicAlerts.aspx?AID=453&ARC=908
Accessed 2026-08-05.
Supports: New Kent County as an announced Buc-ee's location, with a
conditional use permit submitted to the county Planning and Zoning
Department; store program of roughly 74,000 square feet and 120 fueling
positions; site of 27.68 acres.

**[6] Buc-ee's delays second Virginia location by four years.** Virginia
Business. https://virginiabusiness.com/buc-ees-pushes-new-kent-location-opening-2031/
Accessed 2026-08-03.
Supports: the expected New Kent opening moved to December 2031, discussed at
a New Kent County Planning Commission meeting on 15 December, with the VDOT
Exit 211 interchange project cited as a factor in timing.

**[7] I-64 at Exit 211 interchange improvement project, New Kent.** Virginia
Department of Transportation.
https://www.vdot.virginia.gov/projects/richmond-district/i-64-at-exit-211-interchange-improvement-project-new-kent/
Accessed 2026-08-05.
Supports: the Exit 211 diverging diamond interchange project is in design,
with construction estimated to start spring 2027 and finish autumn 2029.
This is the infrastructure dependency behind the New Kent timeline in [6].

**[8] Buc-ee's breaks ground in North Carolina.** C-Store Dive.
https://www.cstoredive.com/news/buc-ees-breaks-ground-in-north-carolina/822421/
Accessed 2026-08-03.
Supports: the Mebane, North Carolina site (I-85/I-40) is under construction.
Included because it is close enough to southern Virginia to affect the
overlap metric.

**[9] American Community Survey 5-Year Data.** U.S. Census Bureau.
https://www.census.gov/data/developers/data-sets/acs-5year.html
Supports: ACS 5-year estimates are period estimates describing a 60-month
window rather than a single point in time, which is why growth in this
project is described as a change between two period estimates rather than an
annual population change.

**[10] Comparing ACS Data.** U.S. Census Bureau.
https://www.census.gov/programs-surveys/acs/guidance/comparing-acs-data.html
Supports: the Census Bureau's guidance against comparing overlapping 5-year
periods, which is why this project uses 2014-2018 and 2019-2023.

**[11] Consumer Price Index for All Urban Consumers (CPI-U), U.S. city
average, all items, not seasonally adjusted, series CUUR0000SA0.** U.S.
Bureau of Labor Statistics.
https://download.bls.gov/pub/time.series/cu/cu.data.1.AllItems
Accessed 2026-08-05.
Supports: annual averages of 251.107 for 2018 and 304.702 for 2023, giving a
deflator of 1.21343. Used to restate 2014-2018 ACS income in 2023 dollars so
that real and nominal income growth can be reported separately.

**[12] Traffic Volume (Average Daily Traffic).** Virginia Department of
Transportation, published via the VDOT open data ArcGIS service.
https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/VDOT_Traffic_Volume_2024/FeatureServer/0
Accessed 2026-08-03.
Supports: all traffic figures. Records are directional linear-referencing
events carrying ADT and AAWDT fields with quality codes. The extract used
here contains 123,766 segments.

**[13] County Business Patterns.** U.S. Census Bureau.
https://www.census.gov/programs-surveys/cbp.html
Supports: establishment counts by NAICS code, including the definition of
NAICS 447 as gasoline stations and the disclosure-avoidance flags that this
project preserves.

**[14] TIGER/Line Shapefiles and Cartographic Boundary Files.** U.S. Census
Bureau. https://www.census.gov/geographies/mapping-files.html
Supports: county and independent city boundaries, primary road geometry used
for interstate distance, and Virginia incorporated place boundaries used to
assign VDOT town records to counties.

**[15] Nominatim.** OpenStreetMap Foundation.
https://nominatim.openstreetmap.org/ Accessed 2026-08-03.
Supports: coordinates for compiled store locations. Raw responses are
preserved in `data/raw/bucees/geocode/`.
