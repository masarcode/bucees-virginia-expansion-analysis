# Buc-ee's Virginia Expansion Analysis

Where should Buc-ee's look next in Virginia? This project screens all 133
Virginia county-equivalents on public data, then applies an analyst layer
that separates places which merely score well from places that could
realistically host a store.

Portfolio project using public data only. Not affiliated with Buc-ee's Ltd.
County-level screening, not a parcel-level site recommendation.

Live Streamlit Dashboard: https://bucees-virginia-expansion.streamlit.app/
Public Tableau Dashboard: 

## What it found

Buc-ee's has one Virginia store open and two in the pipeline: Mount Crawford
on I-81, open since June 2025; Stafford on I-95, locally approved in May 2026
with no confirmed opening date; and New Kent on I-64, announced with its
opening tied to a VDOT interchange project. Those three counties are treated
as reference cases rather than recommendations.

Among the rest:

- **Hampton Roads is the clearest opportunity.** Virginia Beach ranks 4th,
  Chesapeake 10th and Suffolk 17th, together about 1.65 million residents,
  with every eligible jurisdiction at least 58 miles from the nearest
  existing or planned store.
- **The Richmond corridors score well but need trade-area work.**
  Chesterfield ranks 6th and Hanover 12th, both about 33 miles from the
  announced New Kent store, so they carry an overlap-review flag rather than
  a clean recommendation.
- **I-81 Winchester and Frederick is the strongest option with no overlap
  question**, 68.8 miles from Mount Crawford on the same corridor.
- **Northern Virginia scores highest and is not a candidate.** Fairfax ranks
  1st and Arlington 3rd, but both are too dense for an interchange-scale
  site, and Prince William falls inside the overlap screen for Stafford. The
  region is best read as the demand base that makes Stafford work.

A high score is not a recommendation. The model has no way to see land cost,
zoning, or whether a 30-acre parcel exists near an interchange.

Read next: [executive summary](outputs/reports/executive_summary.md) ·
[corridor recommendations](outputs/reports/corridor_recommendations.md) ·
[methodology](outputs/reports/methodology_report.md) ·
[limitations](outputs/reports/limitations_report.md) ·
[citations](docs/citations.md)

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Rebuild everything from source data:

```bash
python -m scripts.run_pipeline
```

Launch the dashboard, from the project root:

```bash
streamlit run dashboard/app.py
```

Run the tests:

```bash
python -m pytest tests/ -q
```

No API keys or credentials are required at any stage.

## How it works

1. **Acquire.** ACS 5-year estimates for 2014-2018 and 2019-2023, County
   Business Patterns 2023, VDOT traffic volumes, TIGER/Line boundaries and
   roads, BLS CPI-U for inflation adjustment, and a hand-compiled store list
   with a citation per row. Raw files are preserved and cataloged.
2. **Clean.** Standardize GEOIDs, validate geometry, resolve VDOT
   jurisdictions to counties, handle missing values and suppression flags.
3. **Load.** Build a SQLite database with analytical views.
4. **Score.** Eight components scaled 0 to 100, combined under five
   weighting scenarios, with a sensitivity sweep.
5. **Screen.** Apply development status, overlap, interstate access and
   feasibility rules to turn ranks into recommendations with stated reasons.
6. **Present.** A Streamlit dashboard and a set of written reports.

Every transformation records automated checks into a `validation_results`
table. All 130 currently pass. Those checks cover data integrity and
pipeline reproducibility, not the commercial accuracy of the conclusions.

## The two-layer design

The project keeps model output and analyst judgement visibly apart:

- **Market attractiveness rank** is what the model computes.
- **Recommendation status** is the decision after screening for existing
  stores, trade-area overlap, interstate access and site feasibility.

Every county carries both, plus the reason for its status. The disagreements
are the interesting part, and Fairfax ranking first while not being a
candidate is the clearest example.

## Repository layout

```
config/          central YAML configuration
data/raw/        original downloads, never modified, with MANIFEST.md
data/processed/  analysis-ready tables
database/        SQLite database, rebuilt by the pipeline
docs/            architecture, assumptions, data dictionary, citations, sources
scripts/         acquisition, cleaning, analysis, orchestrator
sql/             schema, views, business queries
dashboard/       Streamlit app
outputs/         figures, maps, tables, reports
tests/           pytest suite
```

## Tech stack

Python, pandas, GeoPandas, NumPy, SQLite, SQLAlchemy, Plotly, Streamlit,
scikit-learn, PyArrow, PyYAML, pytest.
