import pytest

import pandas as pd

from dashboard.charts import line_figure, y_axis_range


def test_zoom_one_covers_the_data():
    low, high = y_axis_range([100, 120], zoom=1)
    assert low < 100 and high > 120


def test_zoom_narrows_the_range_around_the_centre():
    low1, high1 = y_axis_range([100, 120], zoom=1)
    low2, high2 = y_axis_range([100, 120], zoom=2)
    assert (high2 - low2) == pytest.approx((high1 - low1) / 2)
    assert (low2 + high2) / 2 == pytest.approx(110)


def test_constant_data_has_no_range():
    assert y_axis_range([5, 5, 5], zoom=1) is None


def test_line_figure_locks_x_and_zooms_vertically():
    table = pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=pd.date_range("2024-01-01", periods=3))
    figure = line_figure(table, "Value", y_range=(0.5, 3.5))
    assert figure.layout.dragmode == "zoom"
    assert figure.layout.xaxis.fixedrange is True      # a drag selects a vertical band
    assert figure.layout.yaxis.fixedrange is False
    assert list(figure.layout.yaxis.range) == [0.5, 3.5]
    assert len(figure.data) == 1
