import numpy as np
import pandas as pd
import pytest

from dashboard import analytics, volatility
from tests.test_volatility import simulate_garch


@pytest.fixture
def returns():
    rng = np.random.default_rng(7)
    return pd.DataFrame(rng.normal(0.0004, [0.004, 0.01, 0.02], (900, 3)),
                        columns=["LOW", "MID", "HIGH"],
                        index=pd.bdate_range("2020-01-01", periods=900))


def test_walk_forward_covers_only_out_of_sample_days(returns):
    oos = analytics.walk_forward_returns(returns, "equal_weight", window=300, step=21)
    assert oos.index[0] == returns.index[300]
    assert len(oos) == len(returns) - 300


def test_walk_forward_equal_weight_matches_the_mean(returns):
    oos = analytics.walk_forward_returns(returns, "equal_weight", window=300, step=21)
    expected = returns.mean(axis=1).iloc[300:]
    assert oos.to_numpy() == pytest.approx(expected.to_numpy())


def test_walk_forward_uses_only_past_data(returns):
    base = analytics.walk_forward_returns(returns, "inverse_volatility", window=300, step=21)
    changed = returns.copy()
    changed.iloc[600:] = 0.5  # a huge change in the far future
    other = analytics.walk_forward_returns(changed, "inverse_volatility", window=300, step=21)
    first_blocks = base.index[:200]  # days well before the change (weights estimated earlier)
    assert base.loc[first_blocks].to_numpy() == pytest.approx(other.loc[first_blocks].to_numpy())


def test_walk_forward_costs_reduce_returns(returns):
    free = analytics.walk_forward_returns(returns, "max_sharpe", window=300, step=21, cost_bps=0)
    costly = analytics.walk_forward_returns(returns, "max_sharpe", window=300, step=21, cost_bps=100)
    assert costly.sum() < free.sum()


def test_scenario_result_total_return_and_drawdown():
    index = pd.bdate_range("2020-01-01", periods=6)
    prices = pd.DataFrame({"A": [100, 110, 90, 99, 100, 105.0]}, index=index)
    total, drawdown = analytics.scenario_result(prices, pd.Series({"A": 1.0}),
                                                index[0], index[-1])
    assert total == pytest.approx(0.05)
    assert drawdown == pytest.approx(90 / 110 - 1)


def test_scenario_result_is_nan_without_data():
    index = pd.bdate_range("2020-01-01", periods=10)
    prices = pd.DataFrame({"A": np.linspace(100, 110, 10)}, index=index)
    total, drawdown = analytics.scenario_result(prices, pd.Series({"A": 0.5, "B": 0.5}),
                                                index[0], index[-1])
    assert np.isnan(total) and np.isnan(drawdown)


def test_forecast_evaluation_and_errors():
    returns = simulate_garch(n=900, seed=5)
    evaluation = volatility.evaluate_forecasts(returns, horizon=21, min_train=500, step=42)
    assert len(evaluation) >= 5
    errors = volatility.forecast_errors(evaluation)
    assert {"GARCH(1,1)", "EWMA", "Last 21d realised"} == set(errors.index)
    assert (errors["RMSE"] >= 0).all()
    assert list(errors["RMSE"]) == sorted(errors["RMSE"])
