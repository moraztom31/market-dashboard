"""Data access: Yahoo Finance (yfinance) and FRED, with Streamlit caching."""

import io
from datetime import timedelta

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from dashboard.config import FX_CURRENCIES, FX_SYMBOLS


@st.cache_data(show_spinner=False, ttl=3600)
def download_close_prices(tickers, start, end):
    """Download daily closing prices (cached: identical requests are not repeated)."""
    data = yf.download(
        list(tickers),
        start=start,
        end=end + timedelta(days=1),  # yfinance treats `end` as exclusive
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
    if data.empty:
        return pd.DataFrame()

    # Depending on the yfinance version, one ticker may come back as a
    # Series or as a one-column DataFrame: normalise to a DataFrame.
    close = data["Close"].copy()
    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])
    elif len(tickers) == 1:
        close.columns = [tickers[0]]
    return close.dropna(how="all")


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
