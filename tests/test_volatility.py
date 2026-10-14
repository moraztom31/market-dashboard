import numpy as np
import pandas as pd
import pytest

from dashboard import volatility


def simulate_garch(n=3000, omega=0.05, alpha=0.08, beta=0.90, seed=1):
    rng = np.random.default_rng(seed)
    returns, variance = np.zeros(n), omega / (1 - alpha - beta)
    for t in range(n):
        returns[t] = np.sqrt(variance) * rng.standard_normal()
        variance = omega + alpha * returns[t] ** 2 + beta * variance
    return pd.Series(returns, index=pd.bdate_range("2010-01-01", periods=n))


def test_log_returns_of_constant_growth():
    prices = pd.Series(100 * 1.01 ** np.arange(10), index=pd.bdate_range("2024-01-01", periods=10))
    assert volatility.log_returns(prices).to_numpy() == pytest.approx(np.full(9, np.log(1.01) * 100))


def test_realized_volatility_of_constant_returns_is_zero():
    returns = pd.Series(np.full(60, 0.5))
    assert volatility.realized_volatility(returns).dropna().iloc[-1] == pytest.approx(0.0, abs=1e-9)


def test_ewma_reacts_to_a_recent_shock():
    returns = pd.Series(np.full(100, 0.1))
    shocked = returns.copy()
    shocked.iloc[-1] = 5.0
    assert volatility.ewma_volatility(shocked).iloc[-1] > 5 * volatility.ewma_volatility(returns).iloc[-1]


def test_garch_recovers_persistence_and_forecasts_towards_long_run_level():
    fit = volatility.fit_garch(simulate_garch(), horizon=30)
    assert 0.85 < fit.persistence < 1.0
    assert len(fit.forecast) == 30
    # the forecast converges towards the long-run level
    gap_start = abs(fit.forecast.iloc[0] - fit.long_run_volatility)
    gap_end = abs(fit.forecast.iloc[-1] - fit.long_run_volatility)
    assert gap_end <= gap_start + 1e-9
    assert fit.half_life > 0


def test_garch_needs_enough_data():
    with pytest.raises(ValueError):
        volatility.fit_garch(simulate_garch(n=100))
