"""Portfolio page: all-weather benchmark vs custom and optimised long-only portfolios."""

from datetime import date

import pandas as pd
import streamlit as st

from dashboard import analytics
from dashboard.charts import (correlation_heatmap, frontier_chart, multi_line_chart,
                              return_bars, show_returns_table, weights_bars)
from dashboard.config import (ACCENT, BENCHMARK_WEIGHTS, BLUE, PORTFOLIO_DEFAULT_ASSETS,
                              PORTFOLIO_UNIVERSE, STRESS_PROXIES, STRESS_SCENARIOS)
from dashboard.data import download_close_prices
from dashboard.views.common import sidebar_controls

BENCHMARK = "Benchmark 40/30/30"
COLOURS = {BENCHMARK: "#9aa0a6", "Custom": BLUE, "Max Sharpe": ACCENT,
           "Min volatility": "#7bc67b", "Inverse volatility": "#b48ead"}


@st.cache_data(show_spinner=False, ttl=3600)
def cached_simulation(returns, risk_free):
    """20,000 random long-only portfolios, kept in memory between reruns."""
    return analytics.simulate_portfolios(returns, risk_free=risk_free)


@st.cache_data(show_spinner=False, ttl=3600)
def cached_walk_forward(returns, window, step, risk_free, cost_bps):
    """Out-of-sample returns of the four rebalanced strategies (kept in memory)."""
    strategies = {"Max Sharpe": "max_sharpe", "Min volatility": "min_volatility",
                  "Inverse volatility": "inverse_volatility", "Equal weight": "equal_weight"}
    return pd.DataFrame({name: analytics.walk_forward_returns(
        returns, kind, window, step, risk_free, cost_bps) for name, kind in strategies.items()})


def out_of_sample_section(returns, selected, available, metrics, risk_free):
    """Walk-forward test: weights re-estimated on past data only, applied to the future."""
    st.subheader("Out-of-sample test (walk-forward)")
    st.caption("The optimised portfolios above use the whole period to choose their weights, "
               "which flatters them. Here the weights are re-estimated every few weeks on "
               "the previous years only and applied to the following weeks: a fairer test.")
    col_a, col_b, col_c = st.columns(3)
    years = col_a.number_input("Estimation window (years)", 1.0, 5.0, 2.0, 0.5, key="pf_oos_years")
    step = int(col_b.number_input("Rebalance every (trading days)", 5, 126, 21, key="pf_oos_step"))
    cost_bps = col_c.number_input("Cost (bps of turnover)", 0.0, 100.0, 5.0, key="pf_oos_cost")
    window = int(years * 252)
    if len(returns) < window + 126:
        st.info("Not enough history for this test: choose the 5y lookback in the sidebar "
                "or a shorter estimation window.")
        return
    with st.spinner("Running the walk-forward test..."):
        oos = cached_walk_forward(returns[selected], window, step, risk_free, cost_bps)
    if all(a in available for a in BENCHMARK_WEIGHTS):
        bench = returns[list(BENCHMARK_WEIGHTS)].mul(pd.Series(BENCHMARK_WEIGHTS), axis=1).sum(axis=1)
        oos[BENCHMARK] = bench.reindex(oos.index)
    equity = (1 + oos).cumprod() * 100
    multi_line_chart(equity, "Out-of-sample value (base 100)",
                     colors={**COLOURS, "Equal weight": "#d9a441"})
    out_metrics = analytics.risk_metrics(equity, risk_free)
    out_metrics.insert(0, "Total return", equity.iloc[-1] / 100 - 1)
    st.dataframe(
        out_metrics.style.format({"Total return": "{:+.1%}", "Annual return": "{:+.1%}",
                                  "Annual volatility": "{:.1%}", "Sharpe ratio": "{:.2f}",
                                  "Max drawdown": "{:.1%}"}, na_rep="n/a"),
        width="stretch")
    sharpe_out = out_metrics["Sharpe ratio"]
    best = sharpe_out.idxmax()
    message = f"Out-of-sample, the best Sharpe ratio is **{best}** ({sharpe_out[best]:.2f})"
    if BENCHMARK in sharpe_out.index and best != BENCHMARK:
        message += f" versus {sharpe_out[BENCHMARK]:.2f} for the benchmark"
    if "Max Sharpe" in metrics.index:
        message += (f". The in-sample Max Sharpe portfolio showed {metrics.loc['Max Sharpe', 'Sharpe ratio']:.2f}"
                    f" over the whole period but only {sharpe_out['Max Sharpe']:.2f} out-of-sample: "
                    "the gap is the price of optimising on the same data you evaluate")
    st.info(message + ".")


@st.cache_data(show_spinner=False, ttl=24 * 3600)
def stress_prices(symbols):
    """Long price history for the stress scenarios (proxies replace young ETFs)."""
    proxied = tuple(sorted({STRESS_PROXIES.get(s, s) for s in symbols}))
    prices = download_close_prices(proxied, date(2007, 1, 1), date.today())
    inverse = {STRESS_PROXIES[s]: s for s in symbols if s in STRESS_PROXIES}
    return prices.rename(columns=inverse)


def stress_section(weights, available):
    """How each portfolio would have behaved in past crises."""
    st.subheader("Stress tests (historical crises)")
    st.caption("Constant weights applied to past crises. "
               + ", ".join(f"{k} replaces {v}" for k, v in STRESS_PROXIES.items())
               + " because the original ETF did not exist yet.")
    with st.spinner("Loading long price history..."):
        try:
            prices = stress_prices(tuple(available))
        except Exception as error:
            st.error(f"The long history could not be loaded: {error}")
            return
    if prices.empty:
        st.warning("No long history was returned.")
        return
    returns_table, drawdown_table = {}, {}
    for scenario, (start, end) in STRESS_SCENARIOS.items():
        results = {portfolio: analytics.scenario_result(prices, weights[portfolio], start, end)
                   for portfolio in weights.columns}
        returns_table[scenario] = {p: r[0] * 100 for p, r in results.items()}
        drawdown_table[scenario] = {p: r[1] * 100 for p, r in results.items()}
    returns_table, drawdown_table = pd.DataFrame(returns_table), pd.DataFrame(drawdown_table)
    return_bars(returns_table, list(returns_table.columns))
    st.write("**Total return over each crisis (%)**")
    show_returns_table(returns_table)
    st.write("**Worst drawdown during each crisis (%)**")
    show_returns_table(drawdown_table)


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
    simulation = cached_simulation(returns[selected], risk_free)
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

    out_of_sample_section(returns, selected, available, metrics, risk_free)
    stress_section(weights, available)

    st.caption("Method: constant weights rebalanced daily on ETF proxies; the portfolios in the "
               "first sections are optimised in-sample (illustrative); the out-of-sample test above "
               "is the fair comparison. Educational use only, not investment advice.")
