from datetime import date, timedelta

from dashboard.validation import validate_inputs

TODAY = date.today()
START, END = TODAY - timedelta(days=30), TODAY


def test_valid_inputs():
    assert validate_inputs(["AAPL"], START, END, True, True, 20, 50) is None


def test_no_ticker():
    assert "at least one" in validate_inputs([], START, END, False, False, None, None)


def test_start_after_end():
    assert "earlier" in validate_inputs(["AAPL"], END, START, False, False, None, None)


def test_future_end_date():
    assert "future" in validate_inputs(["AAPL"], START, TODAY + timedelta(days=5),
                                       False, False, None, None)


def test_short_window_must_be_smaller():
    assert "smaller" in validate_inputs(["AAPL"], START, END, True, True, 50, 20)


def test_single_moving_average_has_no_window_constraint():
    assert validate_inputs(["AAPL"], START, END, True, False, 50, None) is None
