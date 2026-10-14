# Market Dashboard

Interactive Streamlit dashboard (PGE M1 Python project) to explore stocks,
bonds, commodities and currencies with data from Yahoo Finance and FRED.

## Pages
- **Stocks / Commodities**: latest prices, trailing and calendar returns, indexed chart.
- **Bonds**: U.S. Treasury curve and OECD 10-year yields (FRED).
- **Currencies**: clickable spot cross-rate matrix and pair chart.
- **Explorer tab** (Stocks, Bonds, Commodities): form with instrument selection,
  date range, normalisation to base 100 and configurable moving averages.

## Run locally
    pip install -r requirements.txt
    python3 -m streamlit run app.py
