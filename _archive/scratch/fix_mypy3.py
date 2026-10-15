with open("src/nse_live/nse_utils.py") as f:
    c = f.read()

# Fix __init__
c = c.replace("def __init__(self):", "def __init__(self) -> None:")

# Fix pre_market_info
c = c.replace(
    'def pre_market_info(self, category="All"):',
    'def pre_market_info(self, category: str = "All") -> typing.Any:',
)
c = c.replace(
    'def pre_market_info(self, category="All") -> typing.Any:',
    'def pre_market_info(self, category: str = "All") -> typing.Any:',
)

# Fix is_nse_trading_holiday
c = c.replace(
    "def is_nse_trading_holiday(self, date_str=None):",
    "def is_nse_trading_holiday(self, date_str: str | None = None) -> typing.Any:",
)
c = c.replace(
    "def is_nse_trading_holiday(self, date_str=None) -> typing.Any:",
    "def is_nse_trading_holiday(self, date_str: str | None = None) -> typing.Any:",
)

# Fix is_nse_clearing_holiday
c = c.replace(
    "def is_nse_clearing_holiday(self, date_str=None):",
    "def is_nse_clearing_holiday(self, date_str: str | None = None) -> typing.Any:",
)
c = c.replace(
    "def is_nse_clearing_holiday(self, date_str=None) -> typing.Any:",
    "def is_nse_clearing_holiday(self, date_str: str | None = None) -> typing.Any:",
)

# Fix futures_data
c = c.replace(
    "def futures_data(self, symbol: str, indices: bool = False):",
    "def futures_data(self, symbol: str, indices: bool = False) -> typing.Any:",
)

# Fix get_option_chain
c = c.replace(
    "def get_option_chain(self, symbol: str, expiry: str, indices: bool = False):",
    "def get_option_chain(self, symbol: str, expiry: str, indices: bool = False) -> typing.Any:",
)

# Fix get_live_option_chain missing return type
c = c.replace(
    "indices: bool = False,\n    ):", "indices: bool = False,\n    ) -> typing.Any:"
)

# Fix get_index_historic_data
c = c.replace(
    "def get_index_historic_data(\n        self, index: str, from_date: str | None = None, to_date: str | None = None\n    ):",
    "def get_index_historic_data(\n        self, index: str, from_date: str | None = None, to_date: str | None = None\n    ) -> typing.Any:",
)

# Fix missing trade_date_obj
c = c.replace("trade_date.strftime", "trade_date_obj.strftime")

# Fix missing from_date_obj
c = c.replace(
    'from_date = datetime.strptime(from_date, "%d-%m-%Y")',
    'from_date_obj = datetime.strptime(from_date, "%d-%m-%Y")',
)
c = c.replace(
    'to_date = datetime.strptime(to_date, "%d-%m-%Y")',
    'to_date_obj = datetime.strptime(to_date, "%d-%m-%Y")',
)

# Replace except: with except Exception as e:
c = c.replace("except:\n", "except Exception as e:\n")

# Fix the from_date_str = from_date.strftime
c = c.replace(
    "from_date_str = from_date.strftime",
    "if from_date is not None:\n                from_date_str = from_date\n",
)

# Fix insider trading
c = c.replace(
    "def get_insider_trading(self, from_date: str = None, to_date: str = None):",
    "def get_insider_trading(self, from_date: str | None = None, to_date: str | None = None) -> typing.Any:",
)

with open("src/nse_live/nse_utils.py", "w") as f:
    f.write(c)
