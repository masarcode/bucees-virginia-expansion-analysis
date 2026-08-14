-- ============================================================
-- Analytical views. Applied idempotently by scripts/build_database.py.
-- ============================================================

DROP VIEW IF EXISTS v_county_growth;
CREATE VIEW v_county_growth AS
WITH deflator AS (
    -- ACS money values are in the final year of each period, so 2014-2018
    -- estimates are 2018 dollars. This factor restates them in 2023 dollars.
    SELECT (SELECT cpi FROM cpi_annual WHERE year = 2023)
         / (SELECT cpi FROM cpi_annual WHERE year = 2018) AS factor
)
SELECT
    cur.geoid,
    g.county_name,
    pri.total_population                          AS pop_2014_2018,
    cur.total_population                          AS pop_2019_2023,
    ROUND(100.0 * (cur.total_population - pri.total_population)
          / NULLIF(pri.total_population, 0), 2)   AS pop_growth_pct,
    pri.median_hh_income                          AS mhi_2014_2018,
    cur.median_hh_income                          AS mhi_2019_2023,
    -- 2014-2018 median household income restated in 2023 dollars
    ROUND(pri.median_hh_income * d.factor, 0)     AS mhi_2014_2018_in_2023usd,
    -- Nominal change: not adjusted for inflation
    ROUND(100.0 * (cur.median_hh_income - pri.median_hh_income)
          / NULLIF(pri.median_hh_income, 0), 2)   AS mhi_growth_pct,
    -- Real change: both periods expressed in 2023 dollars
    ROUND(100.0 * (cur.median_hh_income - pri.median_hh_income * d.factor)
          / NULLIF(pri.median_hh_income * d.factor, 0), 2)
                                                  AS mhi_growth_real_pct
FROM demographics cur
JOIN demographics pri
  ON pri.geoid = cur.geoid AND pri.acs_period = '2014-2018'
JOIN geography g ON g.geoid = cur.geoid
CROSS JOIN deflator d
WHERE cur.acs_period = '2019-2023';

DROP VIEW IF EXISTS v_county_profile;
CREATE VIEW v_county_profile AS
SELECT
    g.geoid,
    g.county_name,
    g.is_independent_city,
    g.aland_sqmi,
    g.region,
    d.total_population,
    d.households,
    d.median_hh_income,
    d.per_capita_income,
    d.median_age,
    ROUND(d.total_population / NULLIF(g.aland_sqmi, 0), 1) AS pop_density_sqmi,
    gr.pop_growth_pct,
    gr.mhi_growth_pct,
    gr.mhi_growth_real_pct,
    t.max_aadt,
    t.interstate_max_aadt,
    t.interstate_miles,
    t.vmt_proxy,
    ba.establishments      AS establishments_all,
    gas.establishments     AS gas_stations,
    food.establishments    AS food_service_estabs,
    ROUND(10000.0 * gas.establishments
          / NULLIF(d.total_population, 0), 2)     AS gas_stations_per_10k
FROM geography g
JOIN demographics d
  ON d.geoid = g.geoid AND d.acs_period = '2019-2023'
LEFT JOIN v_county_growth gr ON gr.geoid = g.geoid
LEFT JOIN traffic_summary t  ON t.geoid = g.geoid
LEFT JOIN business_activity ba
  ON ba.geoid = g.geoid AND ba.naics_code = '00'
LEFT JOIN business_activity gas
  ON gas.geoid = g.geoid AND gas.naics_code = '447'
LEFT JOIN business_activity food
  ON food.geoid = g.geoid AND food.naics_code = '722';

DROP VIEW IF EXISTS v_interstate_counties;
CREATE VIEW v_interstate_counties AS
SELECT
    p.geoid, p.county_name, p.total_population, p.median_hh_income,
    p.interstate_max_aadt, p.interstate_miles, p.vmt_proxy, p.pop_growth_pct
FROM v_county_profile p
WHERE p.interstate_max_aadt IS NOT NULL
ORDER BY p.interstate_max_aadt DESC;

DROP VIEW IF EXISTS v_scenario_leaders;
CREATE VIEW v_scenario_leaders AS
SELECT
    r.scenario, r.rank, r.weighted_score,
    g.geoid, g.county_name, g.region
FROM scenario_rankings r
JOIN geography g ON g.geoid = r.geoid
WHERE r.rank <= 15
ORDER BY r.scenario, r.rank;

DROP VIEW IF EXISTS v_validation_latest;
CREATE VIEW v_validation_latest AS
SELECT stage, check_name, status, details, MAX(run_ts) AS last_run
FROM validation_results
GROUP BY stage, check_name;
