"""Altair charts and styled tables."""

import hashlib

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from dashboard.config import ACCENT, BLUE, ORANGE


def show_returns_table(table):
    """Display a returns table (in %): positive in blue, negative in orange."""
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


def y_range_control(values, seed):
    """Slider (in an expander) to stretch or squeeze the vertical axis of a chart.

    Returns (low, high) or None when the data has no usable range. The widget key
    depends on the data bounds, so the slider resets when the data changes.
    """
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size < 2 or finite.max() == finite.min():
        return None
    low, high = float(finite.min()), float(finite.max())
    span = high - low
    key = "yr_" + hashlib.md5(f"{seed}|{low:.6g}|{high:.6g}".encode()).hexdigest()[:12]
    with st.expander("Vertical scale"):
        return st.slider("Y-axis range", low - span, high + span,
                         (low - 0.05 * span, high + 0.05 * span), step=span / 400, key=key,
                         help="Narrow the range to zoom in on small moves, widen it to zoom out. "
                              "You can also zoom with the mouse wheel and drag on the chart.")


def multi_line_chart(table, y_title, step=False, colors=None, x_title="Date", temporal=True,
                     y_control=True):
    """Interactive multi-line chart (y-axis fitted to the data, zoom and tooltip).

    colors: optional dict series name -> colour. temporal=False draws a numeric x axis
    (index named x_title) instead of dates. y_control adds a vertical-scale slider.
    """
    colour_scale = (alt.Scale(domain=list(colors), range=list(colors.values()))
                    if colors else alt.Undefined)
    y_scale = alt.Scale(zero=False, nice=True)
    y_range = None
    long = (table.rename_axis("Date").reset_index()
            .melt("Date", var_name="Series", value_name="Value").dropna())
    x_type = "T" if temporal else "Q"
    if y_control:
        y_range = y_range_control(long["Value"], f"{y_title}|{list(table.columns)}")
        if y_range is not None:
            y_scale = alt.Scale(domain=list(y_range), zero=False, nice=False)
    chart = (
        alt.Chart(long)
        .mark_line(interpolate="step-after" if step else "linear", clip=True)
        .encode(
            x=alt.X(f"Date:{x_type}", title=x_title),
            y=alt.Y("Value:Q", title=y_title, scale=y_scale),
            color=alt.Color("Series:N", scale=colour_scale, legend=alt.Legend(title=None)),
            tooltip=[f"Date:{x_type}", "Series:N", alt.Tooltip("Value:Q", format=".3f")],
        )
        .interactive()
    )
    st.altair_chart(chart, width="stretch")


def correlation_heatmap(corr):
    """Annotated heatmap of a correlation matrix."""
    long = (corr.rename_axis("A").reset_index()
            .melt("A", var_name="B", value_name="correlation"))
    base = alt.Chart(long).encode(
        x=alt.X("B:N", title=None, sort=None, axis=alt.Axis(labelAngle=-45)),
        y=alt.Y("A:N", title=None, sort=None),
    )
    heat = base.mark_rect().encode(
        color=alt.Color("correlation:Q", legend=None,
                        scale=alt.Scale(domain=[-1, 1], scheme="blueorange")),
        tooltip=["A:N", "B:N", alt.Tooltip("correlation:Q", format=".2f")],
    )
    labels = base.mark_text(color="black").encode(text=alt.Text("correlation:Q", format=".2f"))
    st.altair_chart(heat + labels, width="stretch")


def line_with_points(table, x, y, y_title):
    """Single orange line with points (used for the yield curve)."""
    base = alt.Chart(table).encode(
        x=alt.X(f"{x}:N", sort=list(table[x]), title=x, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{y}:Q", title=y_title, scale=alt.Scale(zero=False)),
        tooltip=[f"{x}:N", alt.Tooltip(f"{y}:Q", format=".2f")],
    )
    st.altair_chart(base.mark_line(color=ACCENT) + base.mark_point(color=ACCENT, filled=True, size=60),
                    width="stretch")


def frontier_chart(simulation, marks):
    """Scatter of simulated long-only portfolios (colour = Sharpe) with highlighted portfolios.

    marks: DataFrame with columns Label, Volatility, Return (one row per portfolio).
    """
    sample = simulation.sample(min(len(simulation), 4000), random_state=0)
    low, high = sample["Sharpe ratio"].quantile([0.02, 0.98])  # ignore extreme outliers
    cloud = alt.Chart(sample).mark_circle(size=22, opacity=0.65).encode(
        x=alt.X("Volatility:Q", title="Annual volatility", axis=alt.Axis(format=".0%", grid=False),
                scale=alt.Scale(zero=False)),
        y=alt.Y("Return:Q", title="Expected annual return", axis=alt.Axis(format=".0%"),
                scale=alt.Scale(zero=False)),
        color=alt.Color("Sharpe ratio:Q",
                        scale=alt.Scale(scheme="turbo", domain=[float(low), float(high)], clamp=True),
                        legend=alt.Legend(title="Sharpe ratio", gradientLength=260,
                                          gradientThickness=16, titleFontSize=13,
                                          labelFontSize=12, format=".1f")),
        tooltip=[alt.Tooltip("Volatility:Q", format=".1%"), alt.Tooltip("Return:Q", format=".1%"),
                 alt.Tooltip("Sharpe ratio:Q", format=".2f")],
    )
    points = alt.Chart(marks).mark_point(filled=True, size=150, color="white",
                                         stroke="black", strokeWidth=2).encode(
        x="Volatility:Q", y="Return:Q",
        tooltip=["Label:N", alt.Tooltip("Volatility:Q", format=".1%"),
                 alt.Tooltip("Return:Q", format=".1%")])
    # labels go to the right of the marker, alternately above and below to avoid overlaps
    marks = marks.reset_index(drop=True)
    layers = [cloud, points]
    for parity, dy in ((0, -16), (1, 18)):
        subset = marks.iloc[parity::2]
        if not subset.empty:
            layers.append(alt.Chart(subset).mark_text(
                align="left", dx=10, dy=dy, color="white", fontSize=12, fontWeight="bold",
            ).encode(x="Volatility:Q", y="Return:Q", text="Label:N"))
    st.altair_chart(alt.layer(*layers).interactive(), width="stretch")


def weights_bars(weights):
    """Stacked bars of portfolio weights (rows = assets, columns = portfolios)."""
    long = (weights.rename_axis("Asset").reset_index()
            .melt("Asset", var_name="Portfolio", value_name="Weight"))
    chart = alt.Chart(long).mark_bar().encode(
        x=alt.X("Portfolio:N", sort=None, title=None, axis=alt.Axis(labelAngle=-20)),
        y=alt.Y("Weight:Q", title="Weight", axis=alt.Axis(format="%"), stack="normalize"),
        color=alt.Color("Asset:N", legend=alt.Legend(title=None)),
        tooltip=["Portfolio:N", "Asset:N", alt.Tooltip("Weight:Q", format=".0%")],
    )
    st.altair_chart(chart, width="stretch")
