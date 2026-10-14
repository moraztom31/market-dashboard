"""Data access: Yahoo Finance (yfinance) and FRED, with Streamlit caching."""

import io
import time
from datetime import timedelta

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from dashboard.config import FX_CURRENCIES, FX_SYMBOLS


class NoDataError(Exception):
    """Yahoo Finance returned no data for a symbol."""


RETRIES = 3
RETRY_DELAY = 1.0  # seconds, multiplied by the attempt number


@st.cache_data(show_spinner=False, ttl=3600)
def _download_one(symbol, start, end):
    """Download the daily closes of ONE symbol, retrying on empty answers or errors.

    Exceptions are never cached by Streamlit: a failure (rate limiting, empty answer)
    is therefore retried on the next run instead of being remembered for an hour.
    """
    last_error = None
    for attempt in range(RETRIES):
        try:
            data = yf.download(
                symbol,
                start=start,
                end=end + timedelta(days=1),  # yfinance treats `end` as exclusive
                interval="1d",
                auto_adjust=False,
                progress=False,
            )
            if not data.empty:
                close = data["Close"]
                if isinstance(close, pd.DataFrame):  # one-column frame in recent yfinance
                    close = close.iloc[:, 0]
                close = close.dropna()
                if not close.empty:
                    return close.rename(symbol)
        except Exception as error:  # network error, Yahoo rate limit, ...
            last_error = error
        if attempt < RETRIES - 1:
            time.sleep(RETRY_DELAY * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise NoDataError(symbol)


def download_close_prices(tickers, start, end):
    """Daily closing prices, one column per ticker that returned data.

    Tickers are downloaded one by one (cached individually), so a temporary Yahoo
    failure on one ticker does not hide the others. If nothing could be loaded and
    a download error occurred, that error is raised; if Yahoo simply returned no
    data, an empty DataFrame is returned.
    """
    series, errors = [], []
    for symbol in tickers:
        try:
            series.append(_download_one(symbol, start, end))
        except NoDataError:
            continue
        except Exception as error:
            errors.append(error)
    if not series:
        if errors:
            raise errors[-1]
        return pd.DataFrame()
    return pd.concat(series, axis=1).sort_index()


@st.cache_data(show_spinner=False, ttl=3600)
def download_fred(series_ids, start, end):
    """Download FRED series through the public CSV endpoint (one column per series)."""
    url = ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + ",".join(series_ids)
           + f"&cosd={start:%Y-%m-%d}&coed={end:%Y-%m-%d}")
    # requests ships its own certificates (pandas/urllib can fail with
    # CERTIFICATE_VERIFY_FAILED on some macOS Python installs)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = pd.read_csv(io.StringIO(response.text), na_values=["."])
    data = data.set_index(data.columns[0])
    data.index = pd.to_datetime(data.index)
    data = data.apply(pd.to_numeric, errors="coerce")
    # FRED can return the full history whatever the requested dates: filter here
    data = data.loc[pd.Timestamp(start):pd.Timestamp(end)]
    return data.dropna(how="all")


def usd_value_table(start, end):
    """Value of 1 unit of each currency expressed in USD.

    Returns (DataFrame, list of currencies for which no data could be loaded).
    """
    table = pd.DataFrame()
    missing = []
    for currency, (candidates, quoted_in_usd) in FX_SYMBOLS.items():
        series = None
        for symbol in candidates:  # try the fallbacks until one returns data
            try:
                quotes = download_close_prices((symbol,), start, end)
            except Exception:
                continue
            if not quotes.empty and not quotes[symbol].dropna().empty:
                series = quotes[symbol].dropna()
                break
        if series is None:
            missing.append(currency)
        else:
            table[currency] = series if quoted_in_usd else 1.0 / series
    if table.empty:
        return table, missing
    table = table.sort_index().ffill().dropna(how="any")  # common dates only
    table.insert(0, "USD", 1.0)
    return table[[c for c in FX_CURRENCIES if c in table.columns]], missing
