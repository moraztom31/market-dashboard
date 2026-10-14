"""Financial analytics on price tables (pure pandas, no Streamlit)."""

from datetime import timedelta

import numpy as np
import pandas as pd

from dashboard.config import TRAILING_DAYS

TRADING_DAYS = 252


# ---- returns -----------------------------------------------------------------
def period_return(series, reference_date):
    """Return in % between the value at reference_date (or before) and the last value."""
    reference = series.asof(reference_date)
    if pd.isna(reference) or reference == 0:
        return float("nan")
    return (series.iloc[-1] / reference - 1) * 100


def compute_returns(prices):
    """Trailing and calendar returns (in %) -> two DataFrames, one row per asset."""
    trailing, calendar = {}, {}
    for asset in prices.columns:
        series = prices[asset].dropna()
        last_day = series.index[-1]
        quarter_start = pd.Timestamp(last_day.year, 3 * ((last_day.month - 1) // 3) + 1, 1)
        references = {
            "Week to date": last_day.normalize() - timedelta(days=last_day.weekday() + 1),
            "Month to date": last_day.replace(day=1).normalize() - timedelta(days=1),
            "Quarter to date": quarter_start - timedelta(days=1),
            "Year to date": pd.Timestamp(last_day.year, 1, 1) - timedelta(days=1),
        }
        trailing[asset] = {label: period_return(series, last_day - timedelta(days=days))
                           for label, days in TRAILING_DAYS.items()}
        calendar[asset] = {label: period_return(series, ref)
                           for label, ref in references.items()}
    return pd.DataFrame(trailing).T, pd.DataFrame(calendar).T


def daily_returns(prices):
    """Daily simple returns (NaN are not forward-filled)."""
    return prices.pct_change(fill_method=None)


# ---- risk / return metrics (one value per column) ----------------------------
def annualized_return(prices):
    """Compound annual growth rate between the first and last observation."""
    values = {}
    for column in prices.columns:
        series = prices[column].dropna()
        years = (series.index[-1] - series.index[0]).days / 365.25 if len(series) > 1 else 0
        if years > 0 and series.iloc[0] > 0:
            values[column] = (series.iloc[-1] / series.iloc[0]) ** (1 / years) - 1
        else:
            values[column] = float("nan")
    return pd.Series(values, dtype=float)


def annualized_volatility(prices):
    """Standard deviation of daily returns, annualised on 252 trading days."""
    return daily_returns(prices).std() * np.sqrt(TRADING_DAYS)


def sharpe_ratio(prices, risk_free=0.0):
    """(Annual return - risk-free rate) / annual volatility."""
    volatility = annualized_volatility(prices).replace(0, np.nan)
    return (annualized_return(prices) - risk_free) / volatility


def drawdown_series(prices):
    """Drawdown from the running maximum (0 = at a high, -0.2 = 20% below it)."""
    return prices / prices.cummax() - 1


def max_drawdown(prices):
    """Worst peak-to-trough decline."""
    return drawdown_series(prices).min()


def risk_metrics(prices, risk_free=0.0):
    """Table of annual return, volatility, Sharpe ratio and max drawdown per asset."""
    return pd.DataFrame({
        "Annual return": annualized_return(prices),
        "Annual volatility": annualized_volatility(prices),
        "Sharpe ratio": sharpe_ratio(prices, risk_free),
        "Max drawdown": max_drawdown(prices),
    })


def correlation_matrix(prices):
    """Correlation of daily returns between assets."""
    return daily_returns(prices).corr()


# ---- strategy backtest -------------------------------------------------------
def backtest_crossover(price, short_window, long_window, cost_bps=0.0):
    """Long-only moving-average crossover strategy versus buy & hold.

    The position is long (1) when the short moving average is above the long one,
    flat (0) otherwise. The signal is lagged by one day to avoid look-ahead bias.
    Returns (equity curves in base 100, position series, number of position changes).
    """
    price = price.dropna()
    returns = price.pct_change().fillna(0.0)
    short_ma = price.rolling(short_window).mean()
    long_ma = price.rolling(long_window).mean()
    position = (short_ma > long_ma).astype(float).shift(1).fillna(0.0)
    trades = position.diff().abs().fillna(0.0)
    strategy_returns = position * returns - trades * cost_bps / 10_000
    equity = pd.DataFrame({
        "Strategy": (1 + strategy_returns).cumprod() * 100,
        "Buy & hold": (1 + returns).cumprod() * 100,
    })
    return equity, position, int(trades.sum())


# ---- portfolio construction ---------------------------------------------------
def portfolio_equity(returns, weights):
    """Equity curve (base 100) of a constant-weight portfolio rebalanced daily."""
    weights = weights.reindex(returns.columns).fillna(0.0)
    portfolio_returns = returns.mul(weights, axis=1).sum(axis=1)
    return (1 + portfolio_returns).cumprod() * 100


def portfolio_stats(returns, weights, risk_free=0.0):
    """Expected annual return, volatility and Sharpe ratio from historical mean/covariance."""
    weights = weights.reindex(returns.columns).fillna(0.0).to_numpy()
    mean = returns.mean().to_numpy() * TRADING_DAYS
    cov = returns.cov().to_numpy() * TRADING_DAYS
    expected = float(weights @ mean)
    volatility = float(np.sqrt(weights @ cov @ weights))
    sharpe = (expected - risk_free) / volatility if volatility > 0 else float("nan")
    return {"Return": expected, "Volatility": volatility, "Sharpe ratio": sharpe}


def simulate_portfolios(returns, n_samples=20_000, risk_free=0.0, seed=0):
    """Random long-only portfolios (weights >= 0, sum = 1) plus each single asset."""
    n_assets = returns.shape[1]
    rng = np.random.default_rng(seed)
    weights = np.vstack([np.eye(n_assets), rng.dirichlet(np.ones(n_assets), size=n_samples)])
    mean = returns.mean().to_numpy() * TRADING_DAYS
    cov = returns.cov().to_numpy() * TRADING_DAYS
    expected = weights @ mean
    volatility = np.sqrt(np.einsum("ij,jk,ik->i", weights, cov, weights))
    sharpe = (expected - risk_free) / np.where(volatility > 0, volatility, np.nan)
    simulation = pd.DataFrame(weights, columns=returns.columns)
    simulation["Return"] = expected
    simulation["Volatility"] = volatility
    simulation["Sharpe ratio"] = sharpe
    return simulation


def pick_portfolio(simulation, kind, assets):
    """Weights of the best simulated portfolio: 'max_sharpe' or 'min_volatility'."""
    if kind == "max_sharpe":
        row = simulation["Sharpe ratio"].idxmax()
    elif kind == "min_volatility":
        row = simulation["Volatility"].idxmin()
    else:
        raise ValueError(f"unknown kind: {kind}")
    return simulation.loc[row, list(assets)].astype(float)


def inverse_volatility_weights(returns):
    """Risk-parity-like weights: each asset weighted by 1 / volatility."""
    inverse = 1 / returns.std()
    return inverse / inverse.sum()
