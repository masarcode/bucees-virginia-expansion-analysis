-- ============================================================
-- Business questions answered directly in SQL.
-- Run: sqlite3 database/bucees_va.sqlite < sql/business_queries.sql
-- ============================================================

-- Q1. Where is Virginia's heaviest interstate traffic exposure?
SELECT county_name, interstate_max_aadt, interstate_miles,
       ROUND(vmt_proxy / 1e6, 1) AS daily_vmt_millions
FROM v_interstate_counties
LIMIT 10;

-- Q2. Which counties combine strong growth with real market size?
-- (>= 25k residents and above-median growth)
SELECT county_name, pop_2019_2023, pop_growth_pct, mhi_growth_pct
FROM v_county_growth
WHERE pop_2019_2023 >= 25000
  AND pop_growth_pct > (SELECT AVG(pop_growth_pct) FROM v_county_growth)
ORDER BY pop_growth_pct DESC
LIMIT 15;

-- Q3. Where is fuel retail thinnest relative to population?
-- (candidate underserved markets, min population floor)
SELECT county_name, total_population, gas_stations, gas_stations_per_10k
FROM v_county_profile
WHERE total_population >= 20000 AND gas_stations IS NOT NULL
ORDER BY gas_stations_per_10k ASC
LIMIT 15;

-- Q4. High-income corridors: affluent counties with interstate access.
SELECT county_name, median_hh_income, interstate_max_aadt, pop_growth_pct
FROM v_county_profile
WHERE interstate_max_aadt IS NOT NULL
ORDER BY median_hh_income DESC
LIMIT 15;

-- Q5. How do the strategy scenarios rank counties? (after Stage 7)
SELECT scenario, rank, county_name, ROUND(weighted_score, 1) AS score
FROM v_scenario_leaders
WHERE rank <= 5
ORDER BY scenario, rank;

-- Q6. Data quality: any checks not passing, most recent run per check.
SELECT stage, check_name, status, details
FROM v_validation_latest
WHERE status != 'pass'
ORDER BY stage;
