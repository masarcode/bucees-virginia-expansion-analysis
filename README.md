# Buc-ee's Virginia Expansion Analysis

**Where should Buc-ee's look next in Virginia?**

This project screens all **133 Virginia county-equivalents** using public demographic, business, highway, and geospatial data, then applies a separate feasibility screen to distinguish markets that score well from places that could realistically support a Buc-ee's-scale site.

The main takeaway is simple: **the highest-scoring market is not automatically the best site.** Fairfax County ranks #1 on raw attractiveness, but density and site-feasibility constraints make it a poor practical fit. After screening, the strongest opportunity is the **Hampton Roads corridor**, led by Virginia Beach, Chesapeake, and Suffolk.

> Portfolio project using public data only. Not affiliated with Buc-ee's Ltd. This is a county-level market screening exercise, not a parcel-level site recommendation.

## Explore the project

- **Live Streamlit app:** https://bucees-virginia-expansion.streamlit.app/
- **Tableau Public dashboards:** https://public.tableau.com/app/profile/masar.salim/viz/Buc-eesVirginiaExpansion-MarketSiteSelectionAnalysis/ExecutiveOverview#3
- **Executive summary:** [outputs/reports/executive_summary.md](outputs/reports/executive_summary.md)
- **Corridor recommendations:** [outputs/reports/corridor_recommendations.md](outputs/reports/corridor_recommendations.md)
- **Methodology:** [outputs/reports/methodology_report.md](outputs/reports/methodology_report.md)
- **Limitations:** [outputs/reports/limitations_report.md](outputs/reports/limitations_report.md)
- **Sources and citations:** [docs/citations.md](docs/citations.md)

## Key findings

### 1. Hampton Roads is the strongest expansion opportunity
Virginia Beach ranks **#4 statewide**, Chesapeake **#10**, and Suffolk **#17**. Together, the corridor contains roughly **1.65 million residents**, reaches up to **195,000 vehicles per day** on its busiest interstate segment, and keeps its eligible markets at least **58 miles** from the nearest existing or planned Buc-ee's location.

### 2. Fairfax is the best example of why scoring alone is not enough
Fairfax County has the highest raw attractiveness score in Virginia at **83.7/100**, but its population density of roughly **2,927 people per square mile** makes assembling an interchange-scale site of about 30 acres difficult. That is why the project keeps model ranking and final recommendation status separate.

### 3. Richmond is attractive, but overlap needs more work
Chesterfield ranks **#6** and Hanover **#12**, but both sit only about 33 miles from the planned New Kent location. They remain strong markets, but the project flags them for trade-area review rather than treating them as clean recommendations.

### 4. Winchester / Frederick is the strongest clean secondary option
Frederick County ranks **#14** and sits about **68.8 miles** from Mount Crawford. Traffic is lower than Hampton Roads, but spacing and growth make it a strong secondary corridor without the same overlap concern.

### 5. The model performs well as a screening tool
As a face-validity check, the model was rerun without Buc-ee's location data. On that blinded run, **Stafford ranked #3 of 133**, New Kent #21, and Rockingham #25. The project also includes **130 automated validation checks**, **8 automated tests**, and **80 sensitivity runs**; the lowest Spearman rank correlation observed was **0.9925**.

## What the model measures

Each jurisdiction is scored on eight components:

- Market demand
- Growth
- Purchasing power
- Highway opportunity
- Accessibility
- Commercial activity
- Competition
- Overlap risk

The project tests five strategic weighting scenarios:

- Balanced
- Highway-first
- Growth-chasing
- Affluent markets
- Underserved markets

The score is only the first layer. A separate screening layer then checks development status, overlap, interstate access, traffic-data availability, and large-site feasibility before assigning a recommendation status.

## Data sources

The analysis uses only public data:

- U.S. Census Bureau ACS 5-year estimates, 2014-2018 and 2019-2023
- U.S. Census Bureau County Business Patterns, 2023
- Virginia Department of Transportation traffic-volume data
- TIGER/Line county boundaries and road geometry
- BLS CPI-U for inflation adjustment
- Official Buc-ee's, state, and local-government sources for store status

Raw source files are preserved locally and can be re-downloaded through the pipeline. See [docs/citations.md](docs/citations.md) and [docs/source_inventory.md](docs/source_inventory.md) for source details.

## How the analysis works

1. **Acquire** the public datasets and preserve the raw inputs.
2. **Clean and standardize** GEOIDs, geometry, missing values, suppression flags, and VDOT jurisdiction records.
3. **Load** the analysis-ready data into SQLite.
4. **Score** all 133 jurisdictions across eight normalized components and five strategic scenarios.
5. **Screen** high-scoring markets for overlap, interstate access, development status, and site feasibility.
6. **Validate** the pipeline with automated checks, tests, and sensitivity analysis.
7. **Present** the results in Streamlit, Tableau, and written reports.

## Why the two-layer design matters

The project intentionally separates two questions:

- **Market attractiveness:** How strong is the market based on the model?
- **Recommendation status:** Is the market actually actionable after practical constraints are considered?

That distinction is the reason Fairfax can rank first without being recommended, while Virginia Beach becomes the top actionable site.

## Project outputs

The repository includes:

- A reproducible Python data pipeline
- SQLite analytical tables and SQL queries
- Geospatial processing with GeoPandas
- Five strategic weighting scenarios
- Sensitivity testing and validation checks
- A six-page Streamlit application
- Four Tableau Public dashboards
- Executive, methodology, corridor, and limitations reports

## Quick start

Create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Rebuild the project from source data:

```bash
python -m scripts.run_pipeline
```

Launch the Streamlit app:

```bash
streamlit run dashboard/app.py
```

Run the automated tests:

```bash
python -m pytest tests/ -q
```

No paid APIs are required.

## Repository structure

```text
config/          central project configuration
data/raw/        original downloads and source manifest
data/processed/  analysis-ready tables
database/        reproducible SQLite database
docs/            assumptions, citations, architecture, data dictionary
scripts/         acquisition, cleaning, analysis, and pipeline orchestration
sql/             schema, views, and business queries
dashboard/       Streamlit application
outputs/         figures, maps, tables, and written reports
tests/           automated test suite
```

## Tech stack

**Python, pandas, GeoPandas, NumPy, SQLite, SQLAlchemy, Plotly, Streamlit, Tableau, scikit-learn, PyArrow, PyYAML, pytest**

## Limitations

This is still a county-level screening model. It does not know whether a specific parcel is available, how much land costs, whether zoning would work, or how long the real drive time is between markets. Traffic exposure uses the highest available interstate mainline segment rather than a countywide average, and population density is used as a proxy for large-site feasibility.

Those limitations are intentional and documented. The next logical step would be parcel-level site screening with drive-time trade areas, land-price data, zoning, and exit-level fuel/food competition.
