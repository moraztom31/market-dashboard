from datetime import date

import pandas as pd

from dashboard.data import download_fred


def test_download_fred_filters_to_requested_window(fake_fred):
    start, end = date(2025, 1, 1), date(2025, 6, 30)
    data = download_fred(("DGS10", "DGS2"), start, end)
    assert data.index.min() >= pd.Timestamp(start)
    assert data.index.max() <= pd.Timestamp(end)
    assert list(data.columns) == ["DGS10", "DGS2"]
