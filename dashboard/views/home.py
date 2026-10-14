"""Home page: market snapshot, indexed performance and returns of key indicators."""

import pandas as pd
import streamlit as st

from dashboard import analytics
from dashboard.charts import multi_line_chart, show_returns_table
from dashboard.config import HOME_ASSETS, HOME_DEFAULT_CHART, HOME_YIELD_SYMBOLS
from dashboard.data import download_close_prices
from dashboard.views.common import sidebar_controls


def last_move(series, is_yield):
    """(formatted last value, formatted change versus the previous observation)."""
    series = series.dropna()
    if len(series) < 2:
        return f"{series.iloc[-1]:,.2f}", None
    last, previous = series.iloc[-1], series.iloc[-2]
    if is_yield:
        return f"{last:.2f}%", f"{(last - previous) * 100:+.0f} bp"
    return f"{last:,.2f}", f"{(last / previous - 1) * 100:+.2f}%"


def home_page():
    st.title(":material/home: Market overview")
    st.write("A snapshot of the main markets: equities, rates, commodities, crypto and FX. "
             "Use the menu on the left to dive into each asset class, build a portfolio "
             "or backtest a strategy.")

    start, end = sidebar_controls()
    with st.sidebar:
        chart_symbols = st.multiselect("Assets in the chart", list(HOME_ASSETS),
                                       default=HOME_DEFAULT_CHART,
                                       format_func=lambda s: HOME_ASSETS[s], key="home_chart")

    with st.spinner("Loading quotations..."):
        try:
            prices = download_close_prices(tuple(HOME_ASSETS), start, end)
        except Exception as error:
            st.error(f"The quotations could not be loaded: {error}")
            return
    available = [s for s in HOME_ASSETS if s in prices.columns and prices[s].dropna().size > 1]
    missing = [HOME_ASSETS[s] for s in HOME_ASSETS if s not in available]
    if missing:
        st.warning("No data returned for: " + ", ".join(missing)
                   + ". Yahoo Finance may be temporarily unavailable: reload in a moment.")
    if not available:
        st.warning("No quotations were returned. Check the date range.")
        return
    prices = prices[available].sort_index().ffill()

    # ---- snapshot: last value and last move ----
    st.subheader("Snapshot")
    for row_start in range(0, len(available), 4):
        for slot, symbol in zip(st.columns(4), available[row_start:row_start + 4]):
            value, delta = last_move(prices[symbol], symbol in HOME_YIELD_SYMBOLS)
            slot.metric(HOME_ASSETS[symbol], value, delta)
    st.caption(f"Last observation: {prices.index[-1]:%Y-%m-%d}. Changes are versus the "
               "previous trading day (basis points for yields).")

    # ---- indexed performance over the selected period ----
    selected = [s for s in chart_symbols if s in available]
    window = prices[selected].loc[pd.Timestamp(start):pd.Timestamp(end)] if selected else None
    if window is not None and len(window) > 1:
        st.subheader("Performance over the period (indexed to 100)")
        first_valid = window.apply(lambda col: col.dropna().iloc[0])
        multi_line_chart(window.divide(first_valid).multiply(100)
                         .rename(columns=HOME_ASSETS), "Index (base 100)")
    else:
        st.info("Select at least one asset in the sidebar to draw the chart.")

    # ---- returns table ----
    st.subheader("Returns")
    trailing, calendar = analytics.compute_returns(prices)
    show_returns_table(pd.concat([trailing, calendar], axis=1).rename(index=HOME_ASSETS))
    st.caption("Market data from Yahoo Finance, for educational purposes only.")
