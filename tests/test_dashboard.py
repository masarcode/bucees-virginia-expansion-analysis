"""Smoke tests for every Streamlit dashboard page."""

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = PROJECT_ROOT / "dashboard"
sys.path.insert(0, str(DASHBOARD))

PAGES = sorted((DASHBOARD / "views").glob("*.py"))


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.stem)
def test_dashboard_page_loads_without_exception(page):
    app = AppTest.from_file(str(page), default_timeout=30)
    app.run()

    errors = [str(exception.value) for exception in app.exception]
    assert not errors, f"{page.name}: {errors}"
