"""Static configuration: instruments, data sources and colours."""

BLUE, ORANGE, ACCENT = "#4db3e6", "#d95f02", "#ff9f36"  # up / down / accent colours

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

# Instruments available for the strategy backtest
BACKTEST_SYMBOLS = {"^GSPC": "S&P 500", **{t: t for t in STOCK_TICKERS}, **COMMODITY_SYMBOLS}

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

TRAILING_DAYS = {"7-day": 7, "30-day": 30, "90-day": 90, "1-year": 365}
LOOKBACKS = {"1m": 30, "3m": 91, "6m": 182, "1y": 365, "2y": 730, "5y": 1826}

# Portfolio page: ETF proxies for each asset class
PORTFOLIO_UNIVERSE = {
    "URTH": "World equities (MSCI World)",
    "EEM": "Emerging equities",
    "IEF": "Gov. bonds (US Treasuries 7-10y)",
    "TLT": "Gov. bonds (US Treasuries 20y+)",
    "GLD": "Gold",
    "DBC": "Commodities (broad basket)",
}
PORTFOLIO_DEFAULT_ASSETS = ["URTH", "IEF", "DBC"]
# Reference allocation: 40% World equities, 30% Government bonds, 30% Commodities
BENCHMARK_WEIGHTS = {"URTH": 0.40, "IEF": 0.30, "DBC": 0.30}

# Home page: key market indicators (symbol -> label). Yields are shown in % with bp changes.
HOME_ASSETS = {
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq",
    "^TNX": "US 10Y yield",
    "GC=F": "Gold",
    "CL=F": "WTI crude",
    "BTC-USD": "Bitcoin",
    "EURUSD=X": "EUR/USD",
    "JPY=X": "USD/JPY",
}
HOME_YIELD_SYMBOLS = {"^TNX"}
HOME_DEFAULT_CHART = ["^GSPC", "GC=F", "CL=F", "EURUSD=X"]

# Volatility page: instruments
VOL_SYMBOLS = {**BACKTEST_SYMBOLS, "BTC-USD": "Bitcoin", "EURUSD=X": "EUR/USD"}
