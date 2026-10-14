"""Input validation (pure Python, no Streamlit)."""

from datetime import date


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
