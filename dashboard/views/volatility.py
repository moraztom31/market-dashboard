"""Volatility page: realised vs EWMA vs GARCH(1,1) and a volatility forecast."""

import pandas as pd
import streamlit as st

from dashboard import volatility
from dashboard.charts import multi_line_chart
from dashboard.config import ACCENT, BLUE, VOL_SYMBOLS
from dashboard.data import download_close_prices
from dashboard.views.common import sidebar_controls


def volatility_page():
    st.title(":material/monitoring: Volatility forecast")
    st.write("Volatility measures how much a price swings. It is not constant: calm and "
             "turbulent periods cluster together, so recent moves help to forecast the "
             "next days. This page compares three estimates and forecasts the volatility "
             "of the coming trading days.")
    with st.expander("What do these models do?"):
        st.markdown(
            "- **Realised (21 days)**: standard deviation of the last 21 daily returns.\n"
            "- **EWMA (RiskMetrics)**: like realised volatility but recent days weigh more "
            "(decay factor 0.94). Its forecast is flat.\n"
            "- **GARCH(1,1)**: a statistical model where today's variance depends on the "
            "latest shock (*alpha*) and on yesterday's variance (*beta*). After a shock, "
            "volatility fades back towards a long-run level; the forecast shows that path.\n\n"
            "Volatility is annualised (daily value × √252) and expressed in %.")

    start, end = sidebar_controls()
    st.caption("Tip: use the 5y lookback in the sidebar; GARCH needs at least a year of data.")
    with st.sidebar:
        symbol = st.selectbox("Instrument", list(VOL_SYMBOLS), key="vol_symbol",
                              format_func=lambda s: VOL_SYMBOLS[s])
        horizon = st.slider("Forecast horizon (trading days)", 5, 60, 21, key="vol_horizon")
        decay = st.slider("EWMA decay factor", 0.80, 0.99, 0.94, 0.01, key="vol_decay")

    with st.spinner("Loading quotations..."):
        try:
            prices = download_close_prices((symbol,), start, end)
        except Exception as error:
            st.error(f"The quotations could not be loaded: {error}")
            return
    if prices.empty or symbol not in prices.columns:
        st.warning("No quotations were returned. Check the instrument and date range.")
        return
    returns = volatility.log_returns(prices[symbol].dropna())
    if len(returns) < volatility.MIN_OBSERVATIONS:
        st.warning(f"Only {len(returns)} daily returns: widen the period "
                   f"(at least {volatility.MIN_OBSERVATIONS} are needed).")
        return

    realised = volatility.realized_volatility(returns)
    ewma = volatility.ewma_volatility(returns, decay)
    with st.spinner("Fitting the GARCH(1,1) model..."):
        try:
            garch = volatility.fit_garch(returns, horizon)
        except Exception as error:
            st.error(f"The GARCH model could not be fitted: {error}")
            return

    name = VOL_SYMBOLS[symbol]
    st.subheader("Current volatility and forecast")
    cols = st.columns(4)
    cols[0].metric("Realised (21d)", f"{realised.dropna().iloc[-1]:.1f}%")
    cols[1].metric("EWMA", f"{ewma.iloc[-1]:.1f}%")
    cols[2].metric(f"GARCH forecast (avg {horizon}d)", f"{garch.forecast.mean():.1f}%")
    cols[3].metric("GARCH long-run level", f"{garch.long_run_volatility:.1f}%")

    st.subheader(f"Annualised volatility of {name} (%)")
    history = pd.DataFrame({"Realised 21d": realised, f"EWMA ({decay:.2f})": ewma,
                            "GARCH(1,1)": garch.conditional_volatility}).dropna()
    multi_line_chart(history, "Annualised volatility (%)",
                     colors={"Realised 21d": "#9aa0a6", f"EWMA ({decay:.2f})": BLUE,
                             "GARCH(1,1)": ACCENT})

    st.subheader(f"Forecast for the next {horizon} trading days")
    path = pd.DataFrame({
        "GARCH forecast": garch.forecast.to_numpy(),
        "EWMA forecast (flat)": float(ewma.iloc[-1]),
        "GARCH long-run level": garch.long_run_volatility,
    }, index=pd.RangeIndex(1, horizon + 1, name="Days ahead")).rename_axis("Date")
    multi_line_chart(path, "Annualised volatility (%)", x_title="Days ahead", temporal=False,
                     colors={"GARCH forecast": ACCENT, "EWMA forecast (flat)": BLUE,
                             "GARCH long-run level": "#7bc67b"})

    st.subheader("GARCH(1,1) parameters")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("alpha (reaction to shocks)", f"{garch.alpha:.3f}")
    c2.metric("beta (persistence)", f"{garch.beta:.3f}")
    c3.metric("alpha + beta", f"{garch.persistence:.3f}")
    half_life = "n/a" if pd.isna(garch.half_life) else f"{garch.half_life:.0f} days"
    c4.metric("Half-life of a shock", half_life)
    st.caption("alpha + beta close to 1 means volatility is very persistent: shocks fade "
               "slowly. Estimated on the selected period only; forecasts are statistical "
               "estimates, not investment advice.")
