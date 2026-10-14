import pandas as pd

from dashboard.views.home import last_move


def test_last_move_price():
    value, delta = last_move(pd.Series([100.0, 102.0]), is_yield=False)
    assert value == "102.00" and delta == "+2.00%"


def test_last_move_yield_in_basis_points():
    value, delta = last_move(pd.Series([4.00, 4.10]), is_yield=True)
    assert value == "4.10%" and delta == "+10 bp"


def test_last_move_single_observation_has_no_delta():
    assert last_move(pd.Series([100.0]), is_yield=False) == ("100.00", None)
