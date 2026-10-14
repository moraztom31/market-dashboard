import numpy as np
import pandas as pd
import pytest

from dashboard import analytics


@pytest.fixture
def returns():
    rng = np.random.default_rng(42)
    index = pd.bdate_range("2023-01-02", periods=500)
    return pd.DataFrame({
        "LOW": rng.normal(0.0003, 0.004, 500),    # low volatility
        "MID": rng.normal(0.0004, 0.010, 500),
        "HIGH": rng.normal(0.0005, 0.020, 500),   # high volatility
    }, index=index)


def test_single_asset_portfolio_equals_asset(returns):
    equity = analytics.portfolio_equity(returns, pd.Series({"LOW": 1.0}))
    expected = (1 + returns["LOW"]).cumprod() * 100
    assert equity.iloc[-1] == pytest.approx(expected.iloc[-1])


def test_simulated_weights_are_long_only_and_sum_to_one(returns):
    simulation = analytics.simulate_portfolios(returns, n_samples=500)
    weights = simulation[list(returns.columns)]
    assert (weights >= 0).all().all()
    assert weights.sum(axis=1).to_numpy() == pytest.approx(np.ones(len(weights)))


def test_pick_portfolio_extremes(returns):
    simulation = analytics.simulate_portfolios(returns, n_samples=2000)
    best = analytics.pick_portfolio(simulation, "max_sharpe", returns.columns)
    safest = analytics.pick_portfolio(simulation, "min_volatility", returns.columns)
    assert best.sum() == pytest.approx(1.0)
    assert safest["LOW"] > safest["HIGH"]
    stats_best = analytics.portfolio_stats(returns, best)["Sharpe ratio"]
    assert stats_best == pytest.approx(simulation["Sharpe ratio"].max())


def test_pick_portfolio_rejects_unknown_kind(returns):
    simulation = analytics.simulate_portfolios(returns, n_samples=10)
    with pytest.raises(ValueError):
        analytics.pick_portfolio(simulation, "nope", returns.columns)


def test_inverse_volatility_favours_low_volatility(returns):
    weights = analytics.inverse_volatility_weights(returns)
    assert weights.sum() == pytest.approx(1.0)
    assert weights["LOW"] > weights["MID"] > weights["HIGH"]
