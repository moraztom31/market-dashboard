"""Portfolio page: all-weather benchmark vs custom and optimised long-only portfolios."""

import pandas as pd
import streamlit as st

from dashboard import analytics
from dashboard.charts import correlation_heatmap, frontier_chart, multi_line_chart, weights_bars
from dashboard.config import (ACCENT, BENCHMARK_WEIGHTS, BLUE, PORTFOLIO_DEFAULT_ASSETS,
                              PORTFOLIO_UNIVERSE)
from dashboard.data import download_close_prices
from dashboard.views.common import sidebar_controls

BENCHMARK = "Benchmark 40/30/30"
COLOURS = {BENCHMARK: "#9aa0a6", "Custom": BLUE, "Max Sharpe": ACCENT,
           "Min volatility": "#7bc67b", "Inverse volatility": "#b48ead"}


def portfolio_page():
    st.title(":material/pie_chart: Portfolio")
    st.write("**Long-only, all-weather portfolio** benchmarked against 40% World Equities · "
             "30% Government Bonds · 30% Commodities — compared with custom and optimised "
             "allocations, judged on risk-adjusted returns and not just performance.")

    start, end = sidebar_controls()
    st.caption("Tip: use the 5y lookback in the sidebar for more robust estimates.")
    with st.sidebar:
        selected = st.multiselect("Assets", list(PORTFOLIO_UNIVERSE),
                                  default=PORTFOLIO_DEFAULT_ASSETS,
                                  format_func=lambda s: PORTFOLIO_UNIVERSE[s], key="pf_assets")
        risk_free = st.number_input("Risk-free rate (%)", 0.0, 10.0, 0.0, step=0.25,
                                    key="pf_risk_free") / 100

    # the benchmark always needs its three ETFs, even if they are not selected
    symbols = sorted(set(selected) | set(BENCHMARK_WEIGHTS))
    with st.spinner("Loading quotations..."):
        try:
            prices = download_close_prices(tuple(symbols), start, end)
        except Exception as error:
            st.error(f"The quotations could not be loaded: {error}")
            return
    available = [s for s in symbols if s in prices.columns and prices[s].dropna().size > 0]
    missing = [s for s in symbols if s not in available]
    if missing:
        st.warning("No data returned for: " + ", ".join(missing) + ".")
    selected = [s for s in selected if s in available]
    if len(selected) < 2:
        st.info("Select at least two assets with data in the sidebar.")
        return
    returns = analytics.daily_returns(prices[available]).dropna()
    if len(returns) < 60:
        st.warning(f"Only {len(returns)} common daily observations: widen the period.")
        return
    names = {s: PORTFOLIO_UNIVERSE[s] for s in available}

    # ---- portfolios (all weights expressed on the same asset list) ----
    with st.expander("Custom weights (%)"):
        custom_raw = pd.Series({s: st.number_input(names[s], 0.0, 100.0,
                                                   round(100 / len(selected), 1), step=5.0,
                                                   key=f"pf_w_{s}") for s in selected})
    if custom_raw.sum() == 0:
        st.error("The custom weights must not all be zero.")
        return
    simulation = analytics.simulate_portfolios(returns[selected], risk_free=risk_free)
    portfolios = {
        "Custom": custom_raw / custom_raw.sum(),
        "Max Sharpe": analytics.pick_portfolio(simulation, "max_sharpe", selected),
        "Min volatility": analytics.pick_portfolio(simulation, "min_volatility", selected),
        "Inverse volatility": analytics.inverse_volatility_weights(returns[selected]),
    }
    if all(s in available for s in BENCHMARK_WEIGHTS):
        portfolios = {BENCHMARK: pd.Series(BENCHMARK_WEIGHTS), **portfolios}
    weights = pd.DataFrame({k: v.reindex(available).fillna(0.0) for k, v in portfolios.items()})

    # ---- results ----
    equity = pd.DataFrame({k: analytics.portfolio_equity(returns, weights[k])
                           for k in weights.columns})
    st.subheader("Performance of each portfolio (base 100)")
    multi_line_chart(equity, "Value (base 100)", colors={k: COLOURS[k] for k in equity.columns})

    metrics = analytics.risk_metrics(equity, risk_free)
    metrics.insert(0, "Total return", equity.iloc[-1] / 100 - 1)
    st.dataframe(
        metrics.style.format({"Total return": "{:+.1%}", "Annual return": "{:+.1%}",
                              "Annual volatility": "{:.1%}", "Sharpe ratio": "{:.2f}",
                              "Max drawdown": "{:.1%}"}, na_rep="n/a"),
        width="stretch")

    st.subheader("Allocations")
    shown = weights.loc[(weights != 0).any(axis=1)].rename(index=names)
    weights_bars(shown)
    st.dataframe(shown.style.format("{:.0%}"), width="stretch")

    st.subheader("Long-only portfolios: risk vs return")
    stats = {k: analytics.portfolio_stats(returns, weights[k], risk_free) for k in weights.columns}
    marks = pd.DataFrame([
        {"Label": f"{k} (Sharpe {v['Sharpe ratio']:.2f})", "Volatility": v["Volatility"],
         "Return": v["Return"]} for k, v in stats.items()])
    frontier_chart(simulation, marks)
    st.caption("Each dot is a random long-only allocation of the selected assets "
               "(colour = Sharpe ratio: red/orange = high, blue = low). White markers are the portfolios above, labelled with their Sharpe ratio.")

    st.subheader("Correlation of daily returns")
    correlation_heatmap(analytics.correlation_matrix(prices[available]).rename(
        index=names, columns=names))

    st.caption("Method: constant weights rebalanced daily on ETF proxies; Max Sharpe and "
               "Min volatility are optimised in-sample on the same period (illustrative, "
               "no out-of-sample guarantee). Educational use only, not investment advice.")
