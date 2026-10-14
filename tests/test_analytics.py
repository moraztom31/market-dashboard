import numpy as np
import pandas as pd
import pytest

from dashboard import analytics


def make_prices(values, start="2024-01-01"):
    return pd.DataFrame({"A": values}, index=pd.bdate_range(start, periods=len(values)))


def test_period_return():
    series = pd.Series([100.0, 110.0], index=pd.to_datetime(["2024-01-01", "2024-01-02"]))
    assert analytics.period_return(series, pd.Timestamp("2024-01-01")) == pytest.approx(10.0)


def test_period_return_without_history_is_nan():
    series = pd.Series([100.0, 110.0], index=pd.to_datetime(["2024-01-10", "2024-01-11"]))
    assert np.isnan(analytics.period_return(series, pd.Timestamp("2024-01-01")))


def test_compute_returns_shapes():
    prices = pd.DataFrame({"A": np.linspace(100, 150, 400), "B": np.linspace(50, 40, 400)},
                          index=pd.bdate_range("2023-01-02", periods=400))
    trailing, calendar = analytics.compute_returns(prices)
    assert list(trailing.index) == ["A", "B"]
    assert list(trailing.columns) == ["7-day", "30-day", "90-day", "1-year"]
    assert list(calendar.columns) == ["Week to date", "Month to date",
                                      "Quarter to date", "Year to date"]
    assert trailing.loc["A"].gt(0).all() and trailing.loc["B"].lt(0).all()


def test_max_drawdown():
    prices = make_prices([100, 120, 60, 90])
    assert analytics.max_drawdown(prices)["A"] == pytest.approx(-0.5)


def test_volatility_of_constant_series_is_zero():
    assert analytics.annualized_volatility(make_prices([100] * 30))["A"] == 0


def test_annualized_return_doubling_in_one_year():
    index = pd.to_datetime(["2023-01-01", "2024-01-01"])
    prices = pd.DataFrame({"A": [100.0, 200.0]}, index=index)
    assert analytics.annualized_return(prices)["A"] == pytest.approx(1.0, abs=0.01)


def test_correlation_of_identical_and_opposite_assets():
    base = np.array([100, 102, 101, 105, 103, 108], dtype=float)
    prices = pd.DataFrame({"A": base, "B": base, "C": 20000 / base},
                          index=pd.bdate_range("2024-01-01", periods=len(base)))
    corr = analytics.correlation_matrix(prices)
    assert corr.loc["A", "B"] == pytest.approx(1.0)
    assert corr.loc["A", "C"] < -0.9


def test_risk_metrics_columns():
    metrics = analytics.risk_metrics(make_prices(np.linspace(100, 120, 60)))
    assert list(metrics.columns) == ["Annual return", "Annual volatility",
                                     "Sharpe ratio", "Max drawdown"]


def test_backtest_rising_market():
    price = pd.Series(np.linspace(100, 200, 200), index=pd.bdate_range("2024-01-01", periods=200))
    equity, position, trades = analytics.backtest_crossover(price, 5, 20)
    assert trades == 1  # enters once and never leaves
    assert position.iloc[-1] == 1
    assert equity["Strategy"].iloc[-1] <= equity["Buy & hold"].iloc[-1] + 1e-9


def test_backtest_costs_reduce_performance():
    rng = np.random.default_rng(3)
    price = pd.Series(100 + np.cumsum(rng.normal(size=300)),
                      index=pd.bdate_range("2024-01-01", periods=300))
    free, _, _ = analytics.backtest_crossover(price, 3, 10, cost_bps=0)
    costly, _, _ = analytics.backtest_crossover(price, 3, 10, cost_bps=50)
    assert costly["Strategy"].iloc[-1] <= free["Strategy"].iloc[-1]
