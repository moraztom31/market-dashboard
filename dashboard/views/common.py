"""Shared sidebar and the Overview / Explorer page layout."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from dashboard import analytics
from dashboard.charts import multi_line_chart, return_bars, show_returns_table
from dashboard.config import LOOKBACKS, TRAILING_DAYS
from dashboard.data import download_close_prices
from dashboard.explorer import explorer


def apply_lookback():
    """Callback: choosing a lookback period moves the start date."""
    st.session_state["start"] = date.today() - timedelta(
        days=LOOKBACKS[st.session_state["lookback"]])
    st.session_state["end"] = date.today()


def sidebar_controls():
    """Lookback / start / end widgets shared by every page. Returns (start, end)."""
    # Streamlit drops the state of keyed widgets when they are not rendered on the previous
    # page run; re-assigning the values keeps them when the user switches page.
    for key in ("lookback", "start", "end"):
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]
    st.session_state.setdefault("start", date.today() - timedelta(days=365))
    st.session_state.setdefault("end", date.today())
    with st.sidebar:
        st.selectbox("Lookback", list(LOOKBACKS), index=3, key="lookback",
                     on_change=apply_lookback)
        start_date = st.date_input("Start date", key="start")
        end_date = st.date_input("End date", key="end")
    if start_date >= end_date:
        st.error("The start date must be earlier than the end date.")
        st.stop()
    if end_date > date.today():
        st.error("The end date cannot be in the future.")
        st.stop()
    return start_date, end_date


def overview(symbols, labels, start, end):
    """Latest prices, trailing/calendar returns and an indexed price chart."""
    if not symbols:
        st.info("Select at least one instrument in the sidebar.")
        return
    # Returns need about one year of history whatever the chosen window
    fetch_start = min(start, date.today() - timedelta(days=400))
    with st.spinner("Loading quotations..."):
        try:
            prices = download_close_prices(tuple(symbols), fetch_start, end)
        except Exception as error:
            st.error(f"The quotations could not be loaded: {error}")
            return
    missing = [s for s in symbols if s not in prices.columns or prices[s].dropna().empty]
    prices = prices.drop(columns=missing, errors="ignore")
    if missing:
        st.warning("No data returned for: " + ", ".join(labels.get(s, s) for s in missing)
                   + ". Yahoo Finance may be temporarily unavailable: reload in a moment.")
    if prices.empty:
        st.warning("No quotations were returned. Check the selection and date range.")
        return
    prices = prices.sort_index().ffill().rename(columns=lambda s: labels.get(s, s))

    st.subheader("Latest prices")
    latest = prices.iloc[-1]
    st.dataframe(pd.DataFrame([latest.values], columns=latest.index)
                 .style.format("{:,.2f}"), hide_index=True, width="stretch")
    st.caption(f"Observed at {prices.index[-1]:%Y-%m-%d}")

    trailing, calendar = analytics.compute_returns(prices)
    st.subheader("Trailing returns")
    return_bars(trailing, list(TRAILING_DAYS))
    show_returns_table(trailing)
    st.subheader("Calendar returns")
    return_bars(calendar, list(calendar.columns))
    show_returns_table(calendar)

    window = prices.loc[pd.Timestamp(start):pd.Timestamp(end)].dropna(how="all")
    if len(window) > 1:
        st.subheader("Price history (indexed to 100 at the start of the period)")
        first_valid = window.apply(
            lambda col: col.dropna().iloc[0] if col.notna().any() else float("nan"))
        multi_line_chart(window.divide(first_valid).multiply(100), "Index (base 100)")


def asset_page(prefix, title, intro, options, default, selector_label, labels=None):
    """Page with an Overview tab and an Explorer tab (form-based)."""
    labels = labels or {}
    st.title(title)
    st.write(intro)
    start, end = sidebar_controls()
    with st.sidebar:
        selected = st.multiselect(selector_label, options, default=default,
                                  format_func=lambda s: labels.get(s, s),
                                  key=f"{prefix}_sidebar_selection")
    tab_overview, tab_explorer = st.tabs(["Overview", "Explorer"])
    with tab_overview:
        overview(selected, labels, start, end)
    with tab_explorer:
        st.write("Build your own comparison: choose instruments and dates in the form, "
                 "then add normalisation and moving averages.")
        explorer(prefix, options, default, selector_label, labels)
