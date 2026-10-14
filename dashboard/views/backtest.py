"""Backtest page: moving-average crossover strategy versus buy & hold."""

import pandas as pd
import streamlit as st

from dashboard import analytics
from dashboard.charts import multi_line_chart
from dashboard.config import BACKTEST_SYMBOLS
from dashboard.data import download_close_prices
from dashboard.views.common import sidebar_controls


def backtest_page():
    st.title("🧪 Strategy backtest")
    st.write("Long-only moving-average crossover: hold the asset while the short "
             "moving average is above the long one, stay in cash otherwise. "
             "The signal is lagged by one day (no look-ahead bias).")

    start, end = sidebar_controls()
    with st.sidebar:
        symbol = st.selectbox("Instrument", list(BACKTEST_SYMBOLS),
                              format_func=lambda s: BACKTEST_SYMBOLS[s], key="bt_symbol")
        short_window = st.number_input("Short window (days)", 2, 100, 20, key="bt_short")
        long_window = st.number_input("Long window (days)", 3, 250, 50, key="bt_long")
        cost_bps = st.number_input("Cost per position change (bps)", 0.0, 100.0, 5.0,
                                   step=1.0, key="bt_cost")

    if short_window >= long_window:
        st.error("The short window must be smaller than the long window.")
        return

    with st.spinner("Loading quotations..."):
        try:
            prices = download_close_prices((symbol,), start, end)
        except Exception as error:
            st.error(f"The quotations could not be loaded: {error}")
            return
    if prices.empty or symbol not in prices.columns or prices[symbol].dropna().empty:
        st.warning("No quotations were returned. Check the instrument and date range.")
        return
    price = prices[symbol].dropna()
    if len(price) <= long_window:
        st.warning(f"Only {len(price)} observations: widen the period or shorten the "
                   "long window.")
        return

    equity, position, n_trades = analytics.backtest_crossover(
        price, int(short_window), int(long_window), cost_bps)
    metrics = analytics.risk_metrics(equity)

    st.subheader("Results")
    final = equity.iloc[-1]
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Strategy", f"{final['Strategy'] - 100:+.1f}%")
    col_b.metric("Buy & hold", f"{final['Buy & hold'] - 100:+.1f}%")
    col_c.metric("Position changes", n_trades)
    st.dataframe(
        metrics.style.format({"Annual return": "{:+.1%}", "Annual volatility": "{:.1%}",
                              "Sharpe ratio": "{:.2f}", "Max drawdown": "{:.1%}"},
                             na_rep="n/a"),
        width="stretch")

    st.subheader("Equity curves (base 100)")
    multi_line_chart(equity, "Value (base 100)")

    st.subheader("Price and moving averages")
    multi_line_chart(pd.DataFrame({
        BACKTEST_SYMBOLS[symbol]: price,
        f"MA {int(short_window)}": price.rolling(int(short_window)).mean(),
        f"MA {int(long_window)}": price.rolling(int(long_window)).mean(),
    }), "Price")

    st.caption("Educational backtest on historical data: it ignores taxes, slippage "
               "and liquidity. Past performance does not predict future results.")
