# Source Inventory

Every external source used, what it provides, and where the file-level
record lives. Numbered citations for specific factual claims are in
[citations.md](citations.md). Download times, file sizes and row counts are
in [data/raw/MANIFEST.md](../data/raw/MANIFEST.md).

All sources are public. No credentials were used, nothing behind a login was
accessed, and no personally identifiable information is present.

## Datasets

| # | Source | Publisher | Vintage | Accessed | Used for |
|---|---|---|---|---|---|
| 1 | ACS 5-year table-based summary file, tables B01002, B01003, B08303, B11001, B19013, B19301, B23025, B25077 | U.S. Census Bureau | 2019-2023 | 2026-08-04 | Current population, income, age, labour force, housing, commuting |
| 2 | ACS 5-year sequence files for Virginia, sequences 3, 28, 36, 59, 65, 79, 115, plus geography file and table lookup | U.S. Census Bureau | 2014-2018 | 2026-08-04 | Prior-period values for growth comparison |
| 3 | County Business Patterns complete county file, cbp23co.zip | U.S. Census Bureau | 2023, NAICS 2017 basis | 2026-08-04 | Establishments: all sectors, 447 gasoline stations, 44-45 retail, 722 food service |
| 4 | Traffic Volume feature service, 123,766 segments | Virginia Department of Transportation | 2024 publication | 2026-08-04 | ADT, AAWDT, truck percentages, jurisdiction, district |
| 5 | Cartographic boundary counties, cb_2023_us_county_500k | U.S. Census Bureau TIGER/Line | 2023 | 2026-08-04 | County and independent city geometry, GEOIDs |
| 6 | Primary roads, tl_2023_us_primaryroads | U.S. Census Bureau TIGER/Line | 2023 | 2026-08-04 | Interstate geometry for distance measurement |
| 7 | Virginia places, cb_2023_51_place_500k | U.S. Census Bureau TIGER/Line | 2023 | 2026-08-04 | Assigning VDOT town records to counties |
| 8 | CPI-U all items, series CUUR0000SA0 | U.S. Bureau of Labor Statistics | 1913-2025 annual averages | 2026-08-05 | Restating 2018 dollars in 2023 dollars |
| 9 | Buc-ee's official location list | Buc-ee's Ltd | Accessed 2026-08-03 | 2026-08-03 | 17 open stores east of the Mississippi |
| 10 | Nominatim geocoding | OpenStreetMap Foundation | Accessed 2026-08-03 | 2026-08-03 | Store coordinates, raw responses preserved |

## Store development status

Each Virginia site is classified from the most authoritative source
available. Citation numbers refer to [citations.md](citations.md).

| Site | Status used in this analysis | Basis |
|---|---|---|
| Mount Crawford, Rockingham County (I-81 Exit 240) | Open, since 2025-06-30 | Listed as operating on the official location page [1]; opening date from Virginia Business [2] |
| Stafford County (Austin Ridge Drive, near I-95) | Locally approved, no confirmed opening date | Stafford County Planning and Zoning project page: Board of Supervisors approved 2026-05-19, applications CUP24155520 and RC25156318, 36.18 acres, no opening date stated [3]; vote margin from Potomac Local [4] |
| New Kent County (I-64 Exit 211) | Announced | New Kent County announcement, conditional use permit submitted, 27.68 acres [5]; December 2031 expectation and interchange dependency from Virginia Business [6] and the VDOT project page [7] |
| Mebane, North Carolina (I-85/I-40) | Under construction | C-Store Dive [8]; included because it is close enough to southern Virginia to affect overlap |

## Access notes

- Census API endpoints at api.census.gov began requiring a key, verified
  2026-08-03 when data requests returned HTTP 302 to a "Missing Key" page.
  All Census data therefore comes from the official bulk files, which do not
  require one. Metadata endpoints stayed open and were used to confirm every
  ACS variable code before download.
- The Buc-ee's location page does not distinguish open stores from planned
  ones, so development status is taken from the county and state sources
  above rather than from the company list.
