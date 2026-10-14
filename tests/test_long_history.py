"""Pages with 5 years of history: the out-of-sample and forecast-evaluation sections run."""

from datetime import date, timedelta

from streamlit.testing.v1 import AppTest


def run_page(module, function):
    at = AppTest.from_string(f"from {module} import {function}\n{function}()", default_timeout=300)
    at.session_state["start"] = date.today() - timedelta(days=1826)
    at.session_state["end"] = date.today()
    return at.run()


def test_portfolio_out_of_sample_and_stress(fake_yfinance, fake_fred):
    at = run_page("dashboard.views.portfolio", "portfolio_page")
    assert not at.exception and not at.error
    headers = [s.value for s in at.subheader]
    assert any("Out-of-sample" in h for h in headers)
    assert any("Stress tests" in h for h in headers)
    assert any("Out-of-sample, the best Sharpe" in i.value for i in at.info)


def test_volatility_forecast_evaluation(fake_yfinance, fake_fred):
    at = run_page("dashboard.views.volatility", "volatility_page")
    assert not at.exception and not at.error
    assert any("walk-forward" in s.value for s in at.subheader)
    assert any("Lowest error" in i.value for i in at.info)
