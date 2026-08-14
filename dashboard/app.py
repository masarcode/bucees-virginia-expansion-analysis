"""Buc-ee's Virginia expansion dashboard.

Run from the project root:  streamlit run dashboard/app.py

Navigation is declared here so each page carries a readable name in the
sidebar rather than inheriting its filename.
"""

import streamlit as st

st.set_page_config(page_title="Buc-ee's Virginia Expansion",
                   page_icon="🦫", layout="wide")

pages = [
    st.Page("views/executive_overview.py", title="Executive Overview",
            icon=":material/insights:", default=True),
    st.Page("views/corridor_recommendations.py", title="Corridor Recommendations",
            icon=":material/alt_route:"),
    st.Page("views/county_explorer.py", title="County Explorer",
            icon=":material/travel_explore:"),
    st.Page("views/market_comparison.py", title="Market Comparison",
            icon=":material/compare_arrows:"),
    st.Page("views/vdot_district_screening.py", title="VDOT District Screening",
            icon=":material/map:"),
    st.Page("views/methodology.py", title="Methodology & Data Quality",
            icon=":material/fact_check:"),
]

st.navigation(pages).run()
