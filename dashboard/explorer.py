"""Interactive explorer: form -> validation -> download -> table, charts and metrics."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from dashboard import analytics
from dashboard.charts import correlation_heatmap, multi_line_chart
from dashboard.data import download_close_prices
from dashboard.validation import validate_inputs


def explorer(prefix, options, default, price_name, labels=None):
    """Render a complete 'select -> download -> table + chart' explorer.

    prefix  : unique string used for widget keys and session_state
    options : list of Yahoo symbols
    labels  : optional dict symbol -> readable name
    """
    labels = labels or {}
    name = lambda symbol: labels.get(symbol, symbol)  # noqa: E731

    # Moving-average toggles are OUTSIDE the form: widgets inside a form do not
    # rerun the script before submission, so the window inputs below could not
    # appear/disappear as soon as a box is ticked.
    st.subheader("Options")
    col_short, col_long = st.columns(2)
    with col_short:
        show_short_ma = st.checkbox("Show short moving average", value=True,
                                    key=f"{prefix}_short_on")
    with col_long:
        show_long_ma = st.checkbox("Show long moving average", value=True,
                                   key=f"{prefix}_long_on")

    # ---- input form: nothing is processed until the button is clicked ----
    with st.form(f"{prefix}_form"):
        selected = st.multiselect(
            price_name, options=options, default=default,
            format_func=name, key=f"{prefix}_selection",
        )
        start_date = st.date_input("Start date", key=f"{prefix}_start",
                                   value=date.today() - timedelta(days=365))
        end_date = st.date_input("End date", value=date.today(), key=f"{prefix}_end")
        normalize = st.checkbox("Normalize prices to 100", value=False,
                                key=f"{prefix}_norm")

        short_window = long_window = None
        if show_short_ma:
            short_window = st.number_input(
                "Short moving-average window (days)", min_value=2, max_value=100,
                value=20, step=1, key=f"{prefix}_short_w")
        if show_long_ma:
            long_window = st.number_input(
                "Long moving-average window (days)", min_value=3, max_value=250,
                value=50, step=1, key=f"{prefix}_long_w")
        submitted = st.form_submit_button("Load quotations")

    # ---- validate; accepted values are kept so results survive later toggles ----
    state_key = f"{prefix}_params"
    if submitted:
        error_message = validate_inputs(
            selected, start_date, end_date,
            show_short_ma, show_long_ma, short_window, long_window)
        if error_message:
            st.session_state.pop(state_key, None)
            st.error(error_message)
        else:
            st.session_state[state_key] = {
                "selected": tuple(selected),
                "start": start_date,
                "end": end_date,
                "normalize": normalize,
                "short_window": int(short_window) if show_short_ma else None,
                "long_window": int(long_window) if show_long_ma else None,
            }

    params = st.session_state.get(state_key)
    if not params:
        return

    # ---- download ----
    with st.spinner("Loading quotations..."):
        try:
            close_prices = download_close_prices(
                params["selected"], params["start"], params["end"])
        except Exception as error:
            st.error(f"The quotations could not be loaded: {error}")
            return

    if close_prices.empty:
        st.warning("No quotations were returned. Check the selection and date range.")
        return

    missing = [s for s in params["selected"]
               if s not in close_prices.columns or close_prices[s].dropna().empty]
    if missing:
        st.warning(f"No data returned for: {', '.join(name(s) for s in missing)}.")
    close_prices = close_prices.drop(columns=missing, errors="ignore")
    if close_prices.empty:
        st.warning("No closing prices were returned.")
        return

    # ---- calculations ----
    windows = {}
    if params["short_window"]:
        windows["short"] = params["short_window"]
    if params["long_window"]:
        windows["long"] = params["long_window"]

    if params["normalize"]:
        first_valid = close_prices.apply(lambda col: col.dropna().iloc[0])
        display_prices = close_prices.divide(first_valid).multiply(100)
        axis_label = "Normalized value (base 100)"
    else:
        display_prices = close_prices
        axis_label = "Price"

    moving_averages = {n: display_prices.rolling(window=w).mean()
                       for n, w in windows.items()}

    too_long = [w for w in windows.values() if w > len(display_prices)]
    if too_long:
        st.warning(
            f"Window(s) {', '.join(map(str, too_long))} exceed the "
            f"{len(display_prices)} available observations: "
            "the corresponding moving average cannot be drawn.")

    # ---- output ----
    st.success(f"Loaded {len(close_prices)} daily observations for "
               f"{', '.join(name(s) for s in close_prices.columns)}.")

    # Key figures: last close and change over the period (raw prices)
    st.subheader("Key figures")
    metric_cols = st.columns(min(len(close_prices.columns), 4))
    for i, symbol in enumerate(close_prices.columns):
        series = close_prices[symbol].dropna()
        change = (series.iloc[-1] / series.iloc[0] - 1) * 100
        with metric_cols[i % len(metric_cols)]:
            st.metric(name(symbol), f"{series.iloc[-1]:,.4f}", f"{change:+.2f}%")

    st.subheader("Closing-price data")
    st.dataframe(display_prices.rename(columns=name), width="stretch")

    st.subheader("Closing prices and selected moving averages")
    chart_data = pd.DataFrame(index=display_prices.index)
    for symbol in display_prices.columns:
        chart_data[f"{name(symbol)} Close"] = display_prices[symbol]
        for key, ma in moving_averages.items():
            chart_data[f"{name(symbol)} MA {windows[key]}"] = ma[symbol]
    multi_line_chart(chart_data, axis_label)

    # ---- risk and return indicators ----
    st.subheader("Risk and return metrics")
    metrics = analytics.risk_metrics(close_prices).rename(index=name)
    st.dataframe(
        metrics.style.format({"Annual return": "{:+.1%}", "Annual volatility": "{:.1%}",
                              "Sharpe ratio": "{:.2f}", "Max drawdown": "{:.1%}"},
                             na_rep="n/a"),
        width="stretch")
    st.caption("Annualised on 252 trading days; Sharpe ratio uses a 0% risk-free rate. "
               "Past performance does not predict future results.")

    if len(close_prices.columns) >= 2:
        st.subheader("Correlation of daily returns")
        correlation_heatmap(analytics.correlation_matrix(close_prices).rename(
            index=name, columns=name))

    st.subheader("Drawdown from previous highs (%)")
    multi_line_chart(analytics.drawdown_series(close_prices).rename(columns=name) * 100,
                     "Drawdown (%)")

    st.download_button("Download table as CSV",
                       display_prices.rename(columns=name).to_csv().encode("utf-8"),
                       f"{prefix}_quotations.csv", "text/csv", key=f"{prefix}_dl")
