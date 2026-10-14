from datetime import date

import pandas as pd
import pytest

from dashboard import data

START, END = date(2025, 1, 1), date(2025, 3, 1)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(data.time, "sleep", lambda seconds: None)


def make_fake(real, failing, calls):
    """Wrap the fake yfinance: `failing` symbols return nothing for the first N calls."""
    def fake(symbol, start, end, **kwargs):
        calls[symbol] = calls.get(symbol, 0) + 1
        if symbol in failing and calls[symbol] <= failing[symbol]:
            return pd.DataFrame()
        return real(symbol, start, end, **kwargs)
    return fake


def test_transient_failure_is_retried(fake_yfinance, monkeypatch):
    import yfinance
    calls = {}
    monkeypatch.setattr("yfinance.download", make_fake(yfinance.download, {"AAPL": 2}, calls))
    prices = data.download_close_prices(("AAPL", "MSFT"), START, END)
    assert list(prices.columns) == ["AAPL", "MSFT"]
    assert calls["AAPL"] == 3  # two empty answers, then success


def test_persistent_failure_does_not_hide_other_tickers(fake_yfinance, monkeypatch):
    import yfinance
    calls = {}
    monkeypatch.setattr("yfinance.download", make_fake(yfinance.download, {"AAPL": 99}, calls))
    prices = data.download_close_prices(("AAPL", "MSFT"), START, END)
    assert list(prices.columns) == ["MSFT"]


def test_failure_is_not_cached(fake_yfinance, monkeypatch):
    import yfinance
    calls = {}
    monkeypatch.setattr("yfinance.download", make_fake(yfinance.download, {"AAPL": data.RETRIES}, calls))
    assert data.download_close_prices(("AAPL",), START, END).empty  # all attempts fail
    again = data.download_close_prices(("AAPL",), START, END)       # Yahoo is back
    assert list(again.columns) == ["AAPL"]


def test_download_error_is_raised_when_nothing_loads(monkeypatch):
    def boom(*args, **kwargs):
        raise ConnectionError("rate limited")
    monkeypatch.setattr("yfinance.download", boom)
    with pytest.raises(ConnectionError):
        data.download_close_prices(("AAPL",), START, END)
