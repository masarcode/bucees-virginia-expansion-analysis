-- ============================================================
-- Buc-ee's Virginia Expansion Analysis - SQLite schema
-- Applied by scripts/utils/db.py::init_schema()
-- ============================================================

PRAGMA foreign_keys = ON;

-- Virginia counties and independent cities (unit of analysis).
CREATE TABLE IF NOT EXISTS geography (
    geoid          TEXT PRIMARY KEY,          -- 5-digit state+county FIPS
    county_name    TEXT NOT NULL,
    state_fips     TEXT NOT NULL,
    county_fips    TEXT NOT NULL,
    is_independent_city INTEGER NOT NULL DEFAULT 0,
    aland_sqmi     REAL,
    awater_sqmi    REAL,
    centroid_lat   REAL,
    centroid_lon   REAL,
    region         TEXT                        -- regional market label (Stage 8)
);

-- ACS 5-year county demographics; one row per county per period.
CREATE TABLE IF NOT EXISTS demographics (
    geoid              TEXT NOT NULL REFERENCES geography(geoid),
    acs_period         TEXT NOT NULL,          -- e.g. '2019-2023'
    total_population   INTEGER,
    median_hh_income   REAL,
    per_capita_income  REAL,
    median_age         REAL,
    labor_force        INTEGER,
    employed           INTEGER,
    median_home_value  REAL,
    households         INTEGER,
    commuters_total    INTEGER,
    PRIMARY KEY (geoid, acs_period)
);

-- County Business Patterns; one row per county x year x NAICS code.
CREATE TABLE IF NOT EXISTS business_activity (
    geoid           TEXT NOT NULL REFERENCES geography(geoid),
    year            INTEGER NOT NULL,
    naics_code      TEXT NOT NULL,
    naics_desc      TEXT,
    establishments  INTEGER,
    employment      INTEGER,
    annual_payroll  INTEGER,                   -- $1,000s
    emp_suppressed  INTEGER NOT NULL DEFAULT 0,-- 1 if employment withheld (noise/suppression)
    PRIMARY KEY (geoid, year, naics_code)
);

-- County-level rollup of VDOT AADT segments.
CREATE TABLE IF NOT EXISTS traffic_summary (
    geoid              TEXT NOT NULL REFERENCES geography(geoid),
    year               INTEGER NOT NULL,
    segment_count      INTEGER,
    max_aadt           REAL,
    mean_aadt          REAL,
    interstate_max_aadt REAL,                  -- max AADT on interstate segments
    interstate_miles   REAL,
    vmt_proxy          REAL,                   -- sum(AADT x segment length)
    PRIMARY KEY (geoid, year)
);

-- Existing and announced Buc-ee's locations (competition / overlap inputs).
CREATE TABLE IF NOT EXISTS bucees_locations (
    location_id    INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('open','under_construction','announced')),
    state          TEXT NOT NULL,
    city           TEXT,
    latitude       REAL,
    longitude      REAL,
    opened_date    TEXT,
    source_url     TEXT NOT NULL,
    accessed_date  TEXT NOT NULL
);

-- Component + composite scores, all normalized 0-100 (Stage 6).
CREATE TABLE IF NOT EXISTS market_scores (
    geoid                TEXT PRIMARY KEY REFERENCES geography(geoid),
    market_demand        REAL,
    growth               REAL,
    purchasing_power     REAL,
    highway_opportunity  REAL,
    accessibility        REAL,
    commercial_activity  REAL,
    competition          REAL,
    overlap_risk         REAL
);

-- Scenario-weighted rankings (Stage 7).
CREATE TABLE IF NOT EXISTS scenario_rankings (
    scenario        TEXT NOT NULL,
    geoid           TEXT NOT NULL REFERENCES geography(geoid),
    weighted_score  REAL NOT NULL,
    rank            INTEGER NOT NULL,
    PRIMARY KEY (scenario, geoid)
);

-- Analyst screening layer: separates model attractiveness from the final
-- recommendation after development status, overlap, access and feasibility
-- filters are applied (Stage 11).
CREATE TABLE IF NOT EXISTS recommendations (
    geoid                 TEXT PRIMARY KEY REFERENCES geography(geoid),
    corridor              TEXT,
    attractiveness_rank   INTEGER,
    weighted_score        REAL,
    recommendation_status TEXT NOT NULL,
    reason                TEXT,
    store_status          TEXT,     -- open / announced / locally approved
    overlap_flag          TEXT
);

-- BLS CPI-U annual averages, used to express 2014-2018 ACS money values
-- in 2023 dollars (ACS reports each period in its final year's dollars).
CREATE TABLE IF NOT EXISTS cpi_annual (
    year INTEGER PRIMARY KEY,
    cpi  REAL NOT NULL
);

-- Every automated validation check, appended per pipeline run.
CREATE TABLE IF NOT EXISTS validation_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ts      TEXT NOT NULL,                 -- ISO-8601 UTC
    stage       TEXT NOT NULL,
    check_name  TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('pass','fail','warn')),
    details     TEXT
);

CREATE INDEX IF NOT EXISTS idx_business_naics ON business_activity(naics_code);
CREATE INDEX IF NOT EXISTS idx_rankings_scenario ON scenario_rankings(scenario, rank);
CREATE INDEX IF NOT EXISTS idx_validation_stage ON validation_results(stage, status);
