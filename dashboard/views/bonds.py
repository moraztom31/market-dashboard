"""Bonds page: OECD 10-year yields and U.S. Treasury curve (FRED) + explorer."""

import altair as alt
import streamlit as st

from dashboard.charts import line_with_points, multi_line_chart
from dashboard.config import BOND_SYMBOLS, OECD_COUNTRIES, UST_TENORS
from dashboard.data import download_fred
from dashboard.explorer import explorer
from dashboard.views.common import sidebar_controls


def bonds_page():
    st.title("📉 Bonds")
    st.write("U.S. Treasury curve and OECD 10-year government yields (FRED).")
    start, end = sidebar_controls()
    with st.sidebar:
        countries = st.multiselect("OECD countries", list(OECD_COUNTRIES),
                                   default=list(OECD_COUNTRIES), key="bonds_countries")
        maturities = st.multiselect("U.S. Treasury maturities", list(UST_TENORS),
                                    default=["3M", "2Y", "10Y", "30Y"], key="bonds_maturities")

    tab_overview, tab_explorer = st.tabs(["Overview", "Explorer"])
    with tab_overview:
        # ---- OECD 10-year yields (monthly data) ----
        if countries:
            with st.spinner("Loading OECD yields from FRED..."):
                try:
                    oecd = download_fred(tuple(OECD_COUNTRIES[c] for c in countries), start, end)
                except Exception as error:
                    oecd = None
                    st.error(f"The OECD yields could not be loaded from FRED: {error}")
            if oecd is not None and oecd.empty:
                st.warning("FRED returned no OECD data for this period.")
            elif oecd is not None:
                oecd = oecd.rename(columns={v: k for k, v in OECD_COUNTRIES.items()})
                last = oecd.ffill().iloc[-1].dropna().sort_values()
                st.subheader(f"OECD 10-year yields snapshot ({oecd.index[-1]:%Y-%m-%d})")
                snapshot = last.rename("Yield").rename_axis("Country").reset_index()
                st.altair_chart(
                    alt.Chart(snapshot).mark_bar().encode(
                        x=alt.X("Country:N", sort=None, title=None),
                        y=alt.Y("Yield:Q", title="Yield (%)"),
                        color=alt.Color("Yield:Q", legend=None,
                                        scale=alt.Scale(range=["#ffffff", "#ff9f36"])),
                        tooltip=["Country:N", alt.Tooltip("Yield:Q", format=".2f")],
                    ), width="stretch")
                st.subheader("OECD 10-year yields over time")
                multi_line_chart(oecd, "Yield (%)", step=True)
        else:
            st.info("Select at least one OECD country in the sidebar.")

        # ---- U.S. Treasury curve (daily data) ----
        with st.spinner("Loading U.S. Treasury yields from FRED..."):
            try:
                ust = download_fred(tuple(UST_TENORS.values()), start, end)
            except Exception as error:
                ust = None
                st.error(f"The Treasury yields could not be loaded from FRED: {error}")
        if ust is not None and ust.empty:
            st.warning("FRED returned no Treasury data for this period.")
        elif ust is not None:
            ust = ust.rename(columns={v: k for k, v in UST_TENORS.items()})
            curve = ust.ffill().iloc[-1].rename("Yield").rename_axis("Tenor").reset_index()
            st.subheader(f"U.S. Treasury yield curve snapshot ({ust.index[-1]:%Y-%m-%d})")
            line_with_points(curve, "Tenor", "Yield", "Yield (%)")
            st.subheader("U.S. Treasury yield curve over time")
            if maturities:
                multi_line_chart(ust[maturities], "Yield (%)")
            else:
                st.info("Select at least one maturity in the sidebar.")

    with tab_explorer:
        st.write("Build your own comparison of U.S. Treasury yields (in %): choose "
                 "instruments and dates in the form, then add normalisation and moving averages.")
        explorer("bonds", list(BOND_SYMBOLS), ["^FVX", "^TNX"], "Yields", BOND_SYMBOLS)
