"""Altair charts and styled tables."""

import altair as alt
import pandas as pd
import plotly.graph_objects as go
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


PLOTLY_CONFIG = {"scrollZoom": True, "displaylogo": False,
                 "modeBarButtonsToRemove": ["lasso2d", "select2d"]}


def multi_line_chart(table, y_title, step=False, colors=None, x_title="Date", **_unused):
    """Interactive multi-line chart (Plotly).

    Stretch the vertical axis by clicking on it and dragging (drag its middle to move
    it); box-select on the chart to zoom, mouse wheel to zoom, double-click to reset.
    colors: optional dict series name -> colour.
    """
    colors = colors or {}
    figure = go.Figure()
    for column in table.columns:
        series = table[column].dropna()
        figure.add_trace(go.Scatter(
            x=series.index, y=series.to_numpy(), mode="lines", name=str(column),
            line={"shape": "hv" if step else "linear", "width": 2,
                  **({"color": colors[column]} if column in colors else {})},
            hovertemplate="%{y:.3f}<extra>%{fullData.name}</extra>"))
    figure.update_layout(
        hovermode="x unified", xaxis_title=x_title, yaxis_title=y_title,
        margin={"l": 10, "r": 10, "t": 10, "b": 10}, height=430,
        legend={"orientation": "v", "yanchor": "top", "y": 1, "xanchor": "left", "x": 1.01},
        yaxis={"fixedrange": False, "automargin": True},
        xaxis={"fixedrange": False})
    st.plotly_chart(figure, width="stretch", config=PLOTLY_CONFIG)
    st.caption("Tip: click on the vertical axis and drag to stretch it · mouse wheel to "
               "zoom · double-click to reset.")


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
