"""Currencies page: spot cross-rate matrix and pair chart."""

import altair as alt
import streamlit as st

from dashboard.config import ACCENT, FX_CURRENCIES
from dashboard.data import usd_value_table
from dashboard.views.common import sidebar_controls


def select_pair(base, quote):
    """Callback: clicking a matrix cell selects that pair."""
    st.session_state["fx_base"] = base
    st.session_state["fx_quote"] = quote


def currencies_page():
    st.title(":material/euro_symbol: Currencies")
    st.write("Spot cross matrix for " + ", ".join(FX_CURRENCIES) + ". Each cell is "
             "units of the column currency per 1 unit of the row currency.")

    # ---- sidebar controls (shared dates + pair selection) ----
    start_date, end_date = sidebar_controls()
    st.session_state.setdefault("fx_base", "EUR")
    st.session_state.setdefault("fx_quote", "USD")
    with st.sidebar:
        base = st.selectbox("Numerator (base)", FX_CURRENCIES, key="fx_base")
        quote = st.selectbox("Denominator (quote)", FX_CURRENCIES, key="fx_quote")

    # ---- download (cached) ----
    with st.spinner("Loading exchange rates..."):
        try:
            usd_values, missing_currencies = usd_value_table(start_date, end_date)
        except Exception as error:
            st.error(f"The exchange rates could not be loaded: {error}")
            return
    if missing_currencies:
        st.warning("No exchange-rate data could be loaded for: "
                   + ", ".join(missing_currencies) + " (they are left out of the matrix).")
    if usd_values.empty or len(usd_values.columns) < 2:
        st.warning("No exchange rates were returned. Check the date range.")
        return

    available = list(usd_values.columns)
    last_day = usd_values.index[-1]
    last = usd_values.iloc[-1]

    # ---- spot matrix: clicking a cell selects the pair ----
    st.subheader(f"Spot matrix — {last_day:%Y-%m-%d}")
    st.caption("Click a cell to plot that pair (row = numerator, column = denominator).")
    header = st.columns([0.8] + [1] * len(available))
    for col, currency in zip(header[1:], available):
        col.markdown(f"**{currency}**")
    for row_currency in available:
        cells = st.columns([0.8] + [1] * len(available))
        cells[0].markdown(f"**{row_currency}**")
        for cell, col_currency in zip(cells[1:], available):
            rate = last[row_currency] / last[col_currency]  # col units per 1 row unit
            label = f"{rate:,.2f}" if rate >= 10 else f"{rate:,.4f}"
            selected = (row_currency == base and col_currency == quote)
            cell.button(label, key=f"cell_{row_currency}_{col_currency}",
                        type="primary" if selected else "secondary",
                        on_click=select_pair, args=(row_currency, col_currency),
                        width="stretch")

    # ---- pair chart ----
    st.subheader(f"{base}/{quote}")
    if base not in available or quote not in available:
        st.warning("No data for the selected pair.")
        return
    if base == quote:
        st.info("Numerator and denominator are identical: the rate is always 1.")
        return
    pair = (usd_values[base] / usd_values[quote]).dropna()
    pair_df = pair.rename("rate").rename_axis("Date").reset_index()
    pair_chart = (
        alt.Chart(pair_df)
        .mark_line(color=ACCENT)
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("rate:Q", title=f"{quote} per 1 {base}",
                    scale=alt.Scale(zero=False, nice=True)),
            tooltip=[alt.Tooltip("Date:T"), alt.Tooltip("rate:Q", format=".4f")],
        )
        .interactive()  # zoom and pan with the mouse
    )
    st.altair_chart(pair_chart, width="stretch")
    change = (pair.iloc[-1] / pair.iloc[0] - 1) * 100
    st.metric(f"{base}/{quote} (last)", f"{pair.iloc[-1]:,.4f}",
              f"{change:+.2f}% over the period")
    st.download_button("Download series as CSV", pair.to_csv().encode("utf-8"),
                       f"{base}{quote}.csv", "text/csv", key="fx_dl")
