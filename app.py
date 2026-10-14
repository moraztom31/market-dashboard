"""Market Dashboard: cross-asset market explorer built with Streamlit.

Run with:  python3 -m streamlit run app.py
"""

import streamlit as st

from dashboard.views.assets import commodities_page, stocks_page
from dashboard.views.backtest import backtest_page
from dashboard.views.bonds import bonds_page
from dashboard.views.currencies import currencies_page
from dashboard.views.home import home_page
from dashboard.views.portfolio import portfolio_page

st.set_page_config(page_title="Cross-Asset Market Monitor", page_icon="📊", layout="wide")

navigation = st.navigation([
    st.Page(home_page, title="Overview", icon=":material/home:", url_path="overview", default=True),
    st.Page(stocks_page, title="Stocks", icon=":material/table_chart_view:", url_path="stocks"),
    st.Page(bonds_page, title="Bonds", icon=":material/stacked_line_chart:", url_path="bonds"),
    st.Page(commodities_page, title="Commodities", icon=":material/oil_barrel:", url_path="commodities"),
    st.Page(currencies_page, title="Currencies", icon=":material/euro_symbol:", url_path="currencies"),
    st.Page(portfolio_page, title="Portfolio", icon=":material/pie_chart:", url_path="portfolio"),
    st.Page(backtest_page, title="Backtest", icon=":material/science:", url_path="backtest"),
])
navigation.run()
