"""Smoke tests: every page runs without exception on fake data."""

import pytest
from streamlit.testing.v1 import AppTest

PAGES = [
    ("dashboard.views.home", "home_page"),
    ("dashboard.views.assets", "stocks_page"),
    ("dashboard.views.assets", "commodities_page"),
    ("dashboard.views.bonds", "bonds_page"),
    ("dashboard.views.currencies", "currencies_page"),
    ("dashboard.views.backtest", "backtest_page"),
    ("dashboard.views.portfolio", "portfolio_page"),
    ("dashboard.views.volatility", "volatility_page"),
]


@pytest.mark.parametrize("module,function", PAGES)
def test_page_runs(module, function, fake_yfinance, fake_fred):
    at = AppTest.from_string(f"from {module} import {function}\n{function}()",
                             default_timeout=120).run()
    assert not at.exception
    assert not at.error


def test_explorer_form_submission(fake_yfinance, fake_fred):
    at = AppTest.from_string(
        "from dashboard.views.assets import stocks_page\nstocks_page()",
        default_timeout=120).run()
    form_button = next(b for b in at.button if "Load" in b.label)
    form_button.click().run()
    assert not at.exception
    assert any("Loaded" in s.value for s in at.success)


def test_explorer_rejects_empty_selection(fake_yfinance, fake_fred):
    at = AppTest.from_string(
        "from dashboard.views.assets import stocks_page\nstocks_page()",
        default_timeout=120).run()
    next(m for m in at.multiselect if m.label == "Tickers" and m.key == "stocks_selection"
         ).set_value([])
    next(b for b in at.button if "Load" in b.label).click().run()
    assert any("at least one" in e.value for e in at.error)


def test_line_charts_are_interactive_plotly_charts(fake_yfinance, fake_fred):
    at = AppTest.from_string(
        "from dashboard.views.assets import stocks_page\nstocks_page()",
        default_timeout=120).run()
    assert not at.exception
    assert len(at.get("plotly_chart")) >= 1


def test_y_axis_zoom_slider_is_available(fake_yfinance, fake_fred):
    at = AppTest.from_string(
        "from dashboard.views.assets import stocks_page\nstocks_page()",
        default_timeout=120).run()
    slider = next(s for s in at.slider if s.label.startswith("Y-axis zoom"))
    slider.set_value(4.0).run()
    assert not at.exception
