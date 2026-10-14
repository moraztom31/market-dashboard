import numpy as np
import pandas as pd
import streamlit as st

from dashboard.views.portfolio import cached_simulation
from dashboard.views.volatility import cached_garch_fit
from tests.test_volatility import simulate_garch


def test_cached_simulation_is_stable():
    rng = np.random.default_rng(0)
    returns = pd.DataFrame(rng.normal(0, 0.01, (300, 3)), columns=list("ABC"),
                           index=pd.bdate_range("2024-01-01", periods=300))
    first = cached_simulation(returns, 0.0)
    second = cached_simulation(returns, 0.0)
    pd.testing.assert_frame_equal(first, second)


def test_cached_garch_fit_returns_same_result():
    returns = simulate_garch(n=600)
    first = cached_garch_fit(returns, 10)
    second = cached_garch_fit(returns, 10)
    assert first.persistence == second.persistence
    assert len(second.forecast) == 10
