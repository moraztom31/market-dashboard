"""Volatility estimation and forecasting: realised, EWMA (RiskMetrics) and GARCH(1,1).

Pure pandas/numpy (+ the `arch` package for GARCH), no Streamlit.
All volatilities are annualised and expressed in percent.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from dashboard.analytics import TRADING_DAYS

MIN_OBSERVATIONS = 250  # about one trading year


def log_returns(prices):
    """Daily log returns in percent."""
    return (np.log(prices / prices.shift(1)) * 100).dropna()


def realized_volatility(returns, window=21):
    """Rolling standard deviation of returns, annualised."""
    return returns.rolling(window).std() * np.sqrt(TRADING_DAYS)


def ewma_volatility(returns, decay=0.94):
    """RiskMetrics EWMA volatility: recent days weigh more (decay 0.94 for daily data)."""
    variance = (returns ** 2).ewm(alpha=1 - decay, adjust=False).mean()
    return np.sqrt(variance) * np.sqrt(TRADING_DAYS)


@dataclass
class GarchFit:
    conditional_volatility: pd.Series  # fitted daily volatility, annualised (%)
    forecast: pd.Series                # volatility forecast for the next days, annualised (%)
    omega: float
    alpha: float                       # reaction to the latest shock
    beta: float                        # persistence of past volatility
    persistence: float                 # alpha + beta
    long_run_volatility: float         # level the forecast converges to, annualised (%)
    half_life: float                   # days for a volatility shock to fade by half


def fit_garch(returns, horizon=21):
    """Fit a GARCH(1,1) model and forecast the next `horizon` trading days.

    Raises ValueError when there are too few observations or the fit fails.
    """
    from arch import arch_model  # imported here: heavy import, only needed on this page

    returns = returns.dropna()
    if len(returns) < MIN_OBSERVATIONS:
        raise ValueError(f"At least {MIN_OBSERVATIONS} daily returns are needed "
                         f"(got {len(returns)}).")
    result = arch_model(returns, mean="Constant", vol="GARCH", p=1, q=1,
                        dist="normal").fit(disp="off")
    params = result.params
    omega, alpha, beta = float(params["omega"]), float(params["alpha[1]"]), float(params["beta[1]"])
    persistence = alpha + beta
    long_run_variance = omega / (1 - persistence) if persistence < 1 else float("nan")
    half_life = np.log(0.5) / np.log(persistence) if 0 < persistence < 1 else float("nan")
    variance_forecast = result.forecast(horizon=horizon).variance.iloc[-1].to_numpy()
    forecast_index = pd.RangeIndex(1, horizon + 1, name="Days ahead")
    return GarchFit(
        conditional_volatility=result.conditional_volatility * np.sqrt(TRADING_DAYS),
        forecast=pd.Series(np.sqrt(variance_forecast) * np.sqrt(TRADING_DAYS), index=forecast_index),
        omega=omega, alpha=alpha, beta=beta, persistence=persistence,
        long_run_volatility=float(np.sqrt(long_run_variance * TRADING_DAYS)),
        half_life=float(half_life),
    )
