"""Shared fixtures: fake Yahoo Finance and FRED responses (no network in tests)."""

import re

import numpy as np
import pandas as pd
import pytest
import streamlit as st


@pytest.fixture(autouse=True)
def clear_cache():
    st.cache_data.clear()
    yield


@pytest.fixture
def fake_yfinance(monkeypatch):
    def fake_download(tickers, start, end, **kwargs):
        tickers = [tickers] if isinstance(tickers, str) else list(tickers)
        index = pd.bdate_range(start, end - pd.Timedelta(days=1))
        rng = np.random.default_rng(0)
        values = 100 + np.cumsum(rng.normal(size=(len(index), len(tickers))), axis=0)
        columns = pd.MultiIndex.from_product([["Close"], sorted(tickers)])
        return pd.DataFrame(values, index=index, columns=columns)
    monkeypatch.setattr("yfinance.download", fake_download)


@pytest.fixture
def fake_fred(monkeypatch):
    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            pass

    def fake_get(url, timeout=None):
        match = re.search(r"id=([^&]+)&cosd=([^&]+)&coed=(.+)", url)
        ids, start, end = match.group(1).split(","), match.group(2), match.group(3)
        index = pd.date_range("2000-01-01", end, freq="D")  # like FRED: ignores `cosd`
        frame = pd.DataFrame(np.random.default_rng(1).random((len(index), len(ids))) + 3,
                             columns=ids)
        frame.insert(0, "observation_date", index.strftime("%Y-%m-%d"))
        return Response(frame.to_csv(index=False))
    monkeypatch.setattr("requests.get", fake_get)
