"""Altair charts and styled tables."""

import altair as alt
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


def multi_line_chart(table, y_title, step=False, colors=None):
    """Interactive multi-line chart (y-axis fitted to the data, zoom and tooltip).

    colors: optional dict series name -> colour.
    """
    colour_scale = (alt.Scale(domain=list(colors), range=list(colors.values()))
                    if colors else alt.Undefined)
    long = (table.rename_axis("Date").reset_index()
            .melt("Date", var_name="Series", value_name="Value").dropna())
    chart = (
        alt.Chart(long)
        .mark_line(interpolate="step-after" if step else "linear")
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("Value:Q", title=y_title, scale=alt.Scale(zero=False, nice=True)),
            color=alt.Color("Series:N", scale=colour_scale, legend=alt.Legend(title=None)),
            tooltip=["Date:T", "Series:N", alt.Tooltip("Value:Q", format=".3f")],
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
