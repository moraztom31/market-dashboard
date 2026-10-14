# -*- coding: utf-8 -*-
"""
Market Dashboard - PGE M1 Python final project.

Multi-page Streamlit app (Stocks / Bonds / Commodities / Currencies) in one file.
Run with:  python3 -m streamlit run app.py
"""

import io
from datetime import date, timedelta

import altair as alt
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# ---------------------------------------------------------------------------
# 1. Constants
# ---------------------------------------------------------------------------
BLUE, ORANGE = "#4db3e6", "#d95f02"  # positive / negative colours (as in the demo)

STOCK_TICKERS = ["AAPL", "TSLA", "MSFT", "NVDA", "ORCL", "IBM"]

BOND_SYMBOLS = {
    "^IRX": "US 13-week yield",
    "^FVX": "US 5-year yield",
    "^TNX": "US 10-year yield",
    "^TYX": "US 30-year yield",
}

COMMODITY_SYMBOLS = {
    "GC=F": "Gold",
    "SI=F": "Silver",
    "CL=F": "WTI crude oil",
    "BZ=F": "Brent crude oil",
    "NG=F": "Natural gas",
    "HG=F": "Copper",
    "ZW=F": "Wheat",
    "ZC=F": "Corn",
}

# FRED series (public CSV, no API key): U.S. Treasury curve and OECD 10-year yields
UST_TENORS = {
    "1M": "DGS1MO", "3M": "DGS3MO", "6M": "DGS6MO", "1Y": "DGS1", "2Y": "DGS2",
    "3Y": "DGS3", "5Y": "DGS5", "7Y": "DGS7", "10Y": "DGS10", "20Y": "DGS20",
    "30Y": "DGS30",
}
OECD_COUNTRIES = {
    "United States": "IRLTLT01USM156N", "Germany": "IRLTLT01DEM156N",
    "France": "IRLTLT01FRM156N", "Italy": "IRLTLT01ITM156N",
    "United Kingdom": "IRLTLT01GBM156N", "Japan": "IRLTLT01JPM156N",
    "Spain": "IRLTLT01ESM156N", "Portugal": "IRLTLT01PTM156N",
    "Greece": "IRLTLT01GRM156N",
}
TRAILING_DAYS = {"7-day": 7, "30-day": 30, "90-day": 90, "1-year": 365}

# Currencies of the spot matrix -> (candidate Yahoo symbols, True if the symbols
# quote "USD per 1 unit of the currency", False if "currency per 1 USD").
# The first symbol is tried first; the others are fallbacks if Yahoo returns nothing.
FX_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD"]
FX_SYMBOLS = {
    "EUR": (["EURUSD=X"], True),
    "GBP": (["GBPUSD=X"], True),
    "AUD": (["AUDUSD=X"], True),
    "NZD": (["NZDUSD=X"], True),
    "JPY": (["JPY=X", "USDJPY=X"], False),
    "CHF": (["CHF=X", "USDCHF=X"], False),
    "CAD": (["CAD=X", "USDCAD=X"], False),
}
LOOKBACKS = {"1m": 30, "3m": 91, "6m": 182, "1y": 365, "2y": 730, "5y": 1826}


# ---------------------------------------------------------------------------
# 2. Helper functions (shared by several pages)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def download_close_prices(tickers, start, end):
    """Download daily closing prices (cached: identical requests are not repeated)."""
    data = yf.download(
        list(tickers),
        start=start,
        end=end + timedelta(days=1),  # yfinance treats `end` as exclusive
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
    if data.empty:
        return pd.DataFrame()

    # Depending on the yfinance version, one ticker may come back as a
    # Series or as a one-column DataFrame: normalise to a DataFrame.
    close = data["Close"].copy()
    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])
    elif len(tickers) == 1:
        close.columns = [tickers[0]]
    return close.dropna(how="all")


def validate_inputs(tickers, start, end, short_on, long_on, short_w, long_w):
    """Return an error message, or None when all inputs are valid."""
    if not tickers:
        return "Please select at least one instrument."
    if start >= end:
        return "The start date must be earlier than the end date."
    if end > date.today():
        return "The end date cannot be in the future."
    if short_on and long_on and short_w >= long_w:
        return "The short moving-average window must be smaller than the long window."
    return None


def explorer(prefix, options, default, price_name, labels=None):
    """Render a complete 'select -> download -> table + chart' page.

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
    if show_short_ma and params["short_window"]:
        windows["short"] = params["short_window"]
    if show_long_ma and params["long_window"]:
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
    st.line_chart(chart_data, y_label=axis_label)

    st.download_button("Download table as CSV",
                       display_prices.rename(columns=name).to_csv().encode("utf-8"),
                       f"{prefix}_quotations.csv", "text/csv", key=f"{prefix}_dl")


# ---------------------------------------------------------------------------
# 3. Shared sidebar, FRED download, returns and chart helpers
# ---------------------------------------------------------------------------
def apply_lookback():
    """Callback: choosing a lookback period moves the start date."""
    st.session_state["start"] = date.today() - timedelta(
        days=LOOKBACKS[st.session_state["lookback"]])
    st.session_state["end"] = date.today()


def sidebar_controls():
    """Lookback / start / end widgets shared by every page. Returns (start, end)."""
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


@st.cache_data(show_spinner=False, ttl=3600)
def download_fred(series_ids, start, end):
    """Download FRED series through the public CSV endpoint (one column per series)."""
    url = ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + ",".join(series_ids)
           + f"&cosd={start:%Y-%m-%d}&coed={end:%Y-%m-%d}")
    # requests ships its own certificates (pandas/urllib can fail with
    # CERTIFICATE_VERIFY_FAILED on some macOS Python installs)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = pd.read_csv(io.StringIO(response.text), na_values=["."])
    data = data.set_index(data.columns[0])
    data.index = pd.to_datetime(data.index)
    return data.apply(pd.to_numeric, errors="coerce").dropna(how="all")


def period_return(series, reference_date):
    """Return in % between the value at reference_date (or before) and the last value."""
    reference = series.asof(reference_date)
    if pd.isna(reference) or reference == 0:
        return float("nan")
    return (series.iloc[-1] / reference - 1) * 100


def compute_returns(prices):
    """Trailing and calendar returns (in %) -> two DataFrames, one row per asset."""
    trailing, calendar = {}, {}
    for asset in prices.columns:
        series = prices[asset].dropna()
        last_day = series.index[-1]
        quarter_start = pd.Timestamp(last_day.year, 3 * ((last_day.month - 1) // 3) + 1, 1)
        references = {
            "Week to date": last_day.normalize() - timedelta(days=last_day.weekday() + 1),
            "Month to date": last_day.replace(day=1).normalize() - timedelta(days=1),
            "Quarter to date": quarter_start - timedelta(days=1),
            "Year to date": pd.Timestamp(last_day.year, 1, 1) - timedelta(days=1),
        }
        trailing[asset] = {label: period_return(series, last_day - timedelta(days=days))
                           for label, days in TRAILING_DAYS.items()}
        calendar[asset] = {label: period_return(series, ref)
                           for label, ref in references.items()}
    return pd.DataFrame(trailing).T, pd.DataFrame(calendar).T


def show_returns_table(table):
    """Display a returns table: positive in blue, negative in orange."""
    def colour(value):
        if pd.isna(value) or value == 0:
            return ""
        return f"color: {BLUE}" if value > 0 else f"color: {ORANGE}"
    st.dataframe(table.style.map(colour).format("{:+.1f}%", na_rep="n/a"), width="stretch")


def return_bars(table, columns):
    """Bar charts (2 per row) of the returns of every asset, one chart per column."""
    for row_start in range(0, len(columns), 2):
        for slot, column in zip(st.columns(2), columns[row_start:row_start + 2]):
            data = table[column].dropna().rename("value").rename_axis("Asset").reset_index()
            chart = (
                alt.Chart(data, title=column)
                .mark_bar()
                .encode(
                    x=alt.X("Asset:N", sort=None, title=None, axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y("value:Q", title="Return (%)"),
                    color=alt.condition("datum.value >= 0", alt.value(BLUE), alt.value(ORANGE)),
                    tooltip=["Asset:N", alt.Tooltip("value:Q", title="Return (%)", format="+.2f")],
                )
            )
            slot.altair_chart(chart, width="stretch")


def multi_line_chart(table, y_title, step=False):
    """Interactive multi-line Altair chart (y-axis fitted to the data)."""
    long = (table.rename_axis("Date").reset_index()
            .melt("Date", var_name="Series", value_name="Value").dropna())
    chart = (
        alt.Chart(long)
        .mark_line(interpolate="step-after" if step else "linear")
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("Value:Q", title=y_title, scale=alt.Scale(zero=False, nice=True)),
            color=alt.Color("Series:N", legend=alt.Legend(title=None)),
            tooltip=["Date:T", "Series:N", alt.Tooltip("Value:Q", format=".3f")],
        )
        .interactive()
    )
    st.altair_chart(chart, width="stretch")


def overview(symbols, labels, start, end):
    """Demo-style overview: latest prices, trailing/calendar returns, indexed chart."""
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
        st.warning("No data returned for: "
                   + ", ".join(labels.get(s, s) for s in missing) + ".")
    if prices.empty:
        st.warning("No quotations were returned. Check the selection and date range.")
        return
    prices = prices.sort_index().ffill().rename(columns=lambda s: labels.get(s, s))

    st.subheader("Latest prices")
    latest = prices.iloc[-1]
    st.dataframe(pd.DataFrame([latest.values], columns=latest.index)
                 .style.format("{:,.2f}"), hide_index=True, width="stretch")
    st.caption(f"Observed at {prices.index[-1]:%Y-%m-%d}")

    trailing, calendar = compute_returns(prices)
    st.subheader("Trailing returns")
    return_bars(trailing, list(TRAILING_DAYS))
    show_returns_table(trailing)
    st.subheader("Calendar returns")
    return_bars(calendar, list(calendar.columns))
    show_returns_table(calendar)

    window = prices.loc[pd.Timestamp(start):pd.Timestamp(end)].dropna(how="all")
    if len(window) > 1:
        st.subheader("Price history (indexed to 100 at the start of the period)")
        first_valid = window.apply(lambda col: col.dropna().iloc[0] if col.notna().any() else float("nan"))
        multi_line_chart(window.divide(first_valid).multiply(100), "Index (base 100)")


def asset_page(prefix, title, intro, options, default, selector_label, labels=None):
    """Page with an Overview tab (demo style) and an Explorer tab (form-based)."""
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


# ---------------------------------------------------------------------------
# 4. Currencies page: spot cross matrix + pair chart (sidebar controls)
# ---------------------------------------------------------------------------
def usd_value_table(start, end):
    """Value of 1 unit of each currency expressed in USD.

    Returns (DataFrame, list of currencies for which no data could be loaded).
    """
    table = pd.DataFrame()
    missing = []
    for currency, (candidates, quoted_in_usd) in FX_SYMBOLS.items():
        series = None
        for symbol in candidates:  # try the fallbacks until one returns data
            try:
                quotes = download_close_prices((symbol,), start, end)
            except Exception:
                continue
            if not quotes.empty and not quotes[symbol].dropna().empty:
                series = quotes[symbol].dropna()
                break
        if series is None:
            missing.append(currency)
        else:
            table[currency] = series if quoted_in_usd else 1.0 / series
    if table.empty:
        return table, missing
    table = table.sort_index().ffill().dropna(how="any")  # common dates only
    table.insert(0, "USD", 1.0)
    return table[[c for c in FX_CURRENCIES if c in table.columns]], missing


def select_pair(base, quote):
    """Callback: clicking a matrix cell selects that pair."""
    st.session_state["fx_base"] = base
    st.session_state["fx_quote"] = quote


def currencies_page():
    st.title("💱 Currencies")
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
    # Altair chart: the y-axis fits the data (zero=False) so small moves stay visible
    pair_df = pair.rename("rate").rename_axis("Date").reset_index()
    pair_chart = (
        alt.Chart(pair_df)
        .mark_line(color="#ff9f36")
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
    st.metric(f"{base}/{quote} (last)", f"{pair.iloc[-1]:,.4f}", f"{change:+.2f}% over the period")
    st.download_button("Download series as CSV", pair.to_csv().encode("utf-8"),
                       f"{base}{quote}.csv", "text/csv", key="fx_dl")


# ---------------------------------------------------------------------------
# 5. Stocks / Bonds / Commodities pages
# ---------------------------------------------------------------------------
def stocks_page():
    asset_page(
        prefix="stocks",
        title="📈 Stocks",
        intro="Latest prices, trailing and calendar returns of large US companies.",
        options=STOCK_TICKERS,
        default=["AAPL", "MSFT"],
        selector_label="Tickers",
    )


def commodities_page():
    asset_page(
        prefix="commodities",
        title="🛢️ Commodities",
        intro="Metals, energy and grains — trailing and calendar returns.",
        options=list(COMMODITY_SYMBOLS),
        default=list(COMMODITY_SYMBOLS),
        selector_label="Commodities",
        labels=COMMODITY_SYMBOLS,
    )


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
            base_chart = alt.Chart(curve).encode(
                x=alt.X("Tenor:N", sort=list(UST_TENORS), title="Tenor",
                        axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Yield:Q", title="Yield (%)", scale=alt.Scale(zero=False)),
                tooltip=["Tenor:N", alt.Tooltip("Yield:Q", format=".2f")])
            st.altair_chart(base_chart.mark_line(color="#ff9f36")
                            + base_chart.mark_point(color="#ff9f36", filled=True, size=60),
                            width="stretch")
            st.subheader("U.S. Treasury yield curve over time")
            if maturities:
                multi_line_chart(ust[maturities], "Yield (%)")
            else:
                st.info("Select at least one maturity in the sidebar.")

    with tab_explorer:
        st.write("Build your own comparison of U.S. Treasury yields (in %): choose "
                 "instruments and dates in the form, then add normalisation and moving averages.")
        explorer("bonds", list(BOND_SYMBOLS), ["^FVX", "^TNX"], "Yields", BOND_SYMBOLS)


# ---------------------------------------------------------------------------
# 6. Navigation (sidebar menu; each page gets its own URL, e.g. /currencies)
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Cross-Asset Market Monitor", page_icon="📊", layout="wide")

navigation = st.navigation([
    st.Page(stocks_page, title="Stocks", icon="📈", url_path="stocks", default=True),
    st.Page(bonds_page, title="Bonds", icon="📉", url_path="bonds"),
    st.Page(commodities_page, title="Commodities", icon="🛢️", url_path="commodities"),
    st.Page(currencies_page, title="Currencies", icon="💱", url_path="currencies"),
])
navigation.run()
