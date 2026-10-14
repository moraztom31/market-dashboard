"""Stocks and Commodities pages."""

from dashboard.config import COMMODITY_SYMBOLS, STOCK_TICKERS
from dashboard.views.common import asset_page


def stocks_page():
    asset_page(
        prefix="stocks",
        title=":material/table_chart_view: Stocks",
        intro="Latest prices, trailing and calendar returns of large US companies.",
        options=STOCK_TICKERS,
        default=["AAPL", "MSFT"],
        selector_label="Tickers",
    )


def commodities_page():
    asset_page(
        prefix="commodities",
        title=":material/oil_barrel: Commodities",
        intro="Metals, energy and grains — trailing and calendar returns.",
        options=list(COMMODITY_SYMBOLS),
        default=list(COMMODITY_SYMBOLS),
        selector_label="Commodities",
        labels=COMMODITY_SYMBOLS,
    )
