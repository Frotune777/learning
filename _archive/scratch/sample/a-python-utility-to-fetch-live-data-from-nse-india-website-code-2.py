# -------------------------------------------------------------------------
#              FabTrader Algorithmic Trading - Tutorials
# -------------------------------------------------------------------------
# CONTACT:
# - Website: https://fabtrader.in
# - Email: fabtraderinc@gmail.com
#
# Usage: Educational Purposes & training use only. Not for commercial redistribution.
# ------------------------------------------------------------------------


import NseUtility
import pandas as pd

# Create a NSE instance of NSEUtility
nse = NseUtility.NseUtils()

# Display settings
pd.set_option("display.max_rows", None, "display.max_columns", None)

# Input Reference
# Following Indices exist - To be used as input within NseUtility
"""
equity_market_list = ['NIFTY 50', 'NIFTY NEXT 50', 'NIFTY MIDCAP 50', 'NIFTY MIDCAP 100', 'NIFTY MIDCAP 150',
                      'NIFTY SMALLCAP 50',
                      'NIFTY SMALLCAP 100', 'NIFTY SMALLCAP 250', 'NIFTY MIDSMALLCAP 400', 'NIFTY 100', 'NIFTY 200',
                      'NIFTY AUTO',
                      'NIFTY BANK', 'NIFTY ENERGY', 'NIFTY FINANCIAL SERVICES', 'NIFTY FINANCIAL SERVICES 25/50',
                      'NIFTY FMCG',
                      'NIFTY IT', 'NIFTY MEDIA', 'NIFTY METAL', 'NIFTY PHARMA', 'NIFTY PSU BANK', 'NIFTY REALTY',
                      'NIFTY PRIVATE BANK', 'Securities in F&O', 'Permitted to Trade',
                      'NIFTY DIVIDEND OPPORTUNITIES 50',
                      'NIFTY50 VALUE 20', 'NIFTY100 QUALITY 30', 'NIFTY50 EQUAL WEIGHT', 'NIFTY100 EQUAL WEIGHT',
                      'NIFTY100 LOW VOLATILITY 30', 'NIFTY ALPHA 50', 'NIFTY200 QUALITY 30',
                      'NIFTY ALPHA LOW-VOLATILITY 30',
                      'NIFTY200 MOMENTUM 30', 'NIFTY COMMODITIES', 'NIFTY INDIA CONSUMPTION', 'NIFTY CPSE',
                      'NIFTY INFRASTRUCTURE',
                      'NIFTY MNC', 'NIFTY GROWTH SECTORS 15', 'NIFTY PSE', 'NIFTY SERVICES SECTOR',
                      'NIFTY100 LIQUID 15',
                      'NIFTY MIDCAP LIQUID 15']
pre_market_list = ['NIFTY 50', 'Nifty Bank', 'Emerge', 'Securities in F&O', 'Others', 'All']
"""

# ---------------------  Full List of Equity Symbols --------------------#
# print(nse.get_equity_full_list())
# print(nse.get_equity_full_list(list_only=True))

# ------------------------  Full List of FNO Symbols --------------------#
# print(nse.get_fno_full_list())
# print(nse.get_fno_full_list(list_only=True))

# ---------------------------  Pre Market Data  -------------------------#
# pprint(nse.pre_market_info('All'))
# pprint(nse.pre_market_info('NIFTY 50'))
# pprint(nse.pre_market_info('Nifty Bank'))
# pprint(nse.pre_market_info('Emerge'))
# pprint(nse.pre_market_info('Securities in F&O'))
# pprint(nse.pre_market_info('Others'))

# --------------------------  Index Symbol List  ------------------------#
# pprint(nse.get_index_details('NIFTY 50'))
# pprint(nse.get_index_details('NIFTY 100'))
# pprint(nse.get_index_details('NIFTY 200'))
# pprint(nse.get_index_details('NIFTY MIDSMALLCAP 400'))
# pprint(nse.get_index_details('NIFTY AUTO'))
# print(nse.get_index_details('NIFTY IT', list_only=True))
# pprint(nse.get_index_details('NIFTY 50', list_only=True))

# -----------------------------  NSE Holiday ---------------------------#
# print(nse.clearing_holidays())
# print(nse.clearing_holidays(list_only=True))
# print(nse.trading_holidays())
# print(nse.trading_holidays(list_only=True))
# print(nse.is_nse_clearing_holiday())
# print(nse.is_nse_clearing_holiday('19-FEB-2025'))
# print(nse.is_nse_trading_holiday())
# print(nse.is_nse_trading_holiday('26-JAN-2025'))

# -----------------------------  Equity Info  ---------------------------#
# pprint(nse.equity_info('INFY'))

# -----------------------------  Price Info   ---------------------------#
# pprint(nse.price_info('INFY'))
# pprint(nse.get_52week_high_low('INFY'))

# -------------------------- Market Depth --------------------------------#
# pprint(nse.get_market_depth("INFY"))

# ----------------------  Futures Instrument /Details -------------------#
# print(nse.futures_data('INFY'))
# print(nse.futures_data('NIFTY', indices=True))

# -----------------------------  Options Data ---------------------------#
# In case of indices, use the indices=True parameter
# print(nse.get_option_chain('INFY','30-Dec-2025').head())
# print(nse.get_option_chain('NIFTY', '16-Dec-2025', indices=True).head())
# print(nse.get_option_chain('BANKNIFTY', '30-Dec-2025', indices=True).head())

# -----------------------------  OI Data ---------------------------#
# (oi_underlying, rise_oi_rise_price,
#  rise_oi_slide_price, slide_oi_slide_price,
#  slide_oi_rise_price) = nse.change_in_oi()

# print("------- Chane in OI By Underlying ------------")
# print(oi_underlying.head(2))
# print("------- Change in OI By Contract : Rise in OI Rise in Price  ------------")
# print(rise_oi_rise_price.head(2))
# print("------- Change in OI By Contract : Rise in OI Slide in Price  ------------")
# print(rise_oi_slide_price.head(2))
# print("------- Change in OI By Contract : Slide in OI Slide in Price  ------------")
# print(slide_oi_slide_price.head(2))
# print("------- Change in OI By Contract : Slide in OI Rise in Price  ------------")
# print(slide_oi_rise_price.head(2))

# ----------------------------  Bhav Copy Download  ---------------------#
# Delivery Bhav Copy
# print(nse.bhav_copy_with_delivery('09-12-2025').head())

# Equity Bhav Copy
# print(nse.equity_bhav_copy('09-12-2025').head())

# Indices Bhav Copy
# print(nse.bhav_copy_indices('09-12-2025').head())

# FNO Bhav Copy
# print(nse.fno_bhav_copy('09-12-2025').head())

# ------------------------  FII  / DII Activity ---------------------------#
# print(nse.fii_dii_activity())

# ----------------- Index Historic Data (Daily Data) ----------------------#
# print(nse.get_index_historic_data('NIFTY 50', '01-01-2025', '31-01-2025'))

# ---------------------------- Top Gainers / Losers  ----------------------#
# pprint(nse.get_gainers_losers())

# ----- Corporate Actions / Bonus / Dividend / Splits / Buy Back-----------#
# print(nse.get_corporate_action().head())  # To download corp actions in the last one month
# print(nse.get_corporate_action('01-01-2025','31-01-2025').head())  # To download for specific period
# print(nse.get_corporate_action('01-01-2025','31-01-2025', "Bonus"))  # To download Bonus data only
# print(nse.get_corporate_action('01-01-2025','31-01-2025', "Dividend"))  # To download Dividend data only
# print(nse.get_corporate_action('01-01-2025','31-01-2025', "Split"))  # To download Split data only
# print(nse.get_corporate_action('01-01-2025','31-03-2025', "Buy Back"))  # To download Buy Back data only

# ---------------------------- Corporate Announcements  ------------------#
# print(nse.get_corporate_announcement().head())  # To download Corp announcements in the last one month
# print(nse.get_corporate_announcement('01-03-2025','31-03-2025').head())  # To download for specific period

# ----------------------------- ADVANCES AND DECLINES ---------------------#
# print(nse.get_advance_decline())

# ----------------------------- PE / PB / Div Yield  ---------------------#
# print(nse.get_index_pe_ratio().head())
# print(nse.get_index_pb_ratio().head())
# print(nse.get_index_div_yield().head())

# -----------------------    MOST ACTIVE EQUITIES    -------------------#
# print(nse.most_active_equity_stocks_by_volume())
# print(nse.most_active_equity_stocks_by_value())

# -----------------------    MOST ACTIVE DERIVATIVES    -------------------#
# print(nse.most_active_index_calls())
# print(nse.most_active_index_puts())
# print(nse.most_active_stock_calls())
# print(nse.most_active_stock_puts())
# print(nse.most_active_contracts_by_oi())
# print(nse.most_active_contracts_by_volume())
# print(nse.most_active_futures_contracts_by_volume())
# print(nse.most_active_options_contracts_by_volume())

# -----------------------  Get Insider Trading / Promoter Trading Data  -------------------#
# print(nse.get_insider_trading())   # Will extract all insider trading info for last 30 days
# print(nse.get_insider_trading(from_date='24-03-2025', to_date='26-03-2025'))

# -----------------------  Get Upcoming Company Results Calendar      -------------------#
# print(nse.get_upcoming_results_calendar())

# ----------------------------      Get List of ETFs    --------------------------#
# print(nse.get_etf_list())
