with open("src/nse_live/nse_utils.py") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    # Fix __init__ return type
    if "def __init__(self):" in line:
        lines[i] = line.replace("def __init__(self):", "def __init__(self) -> None:")

    # Replace (self, category, list_only=False):
    if "(self, category, list_only=False) -> typing.Any:" in line:
        lines[i] = line.replace(
            "(self, category, list_only=False) -> typing.Any:",
            "(self, category: str, list_only: bool = False) -> typing.Any:",
        )

    # Replace (self, list_only=False)
    if "(self, list_only=False) -> typing.Any:" in line:
        lines[i] = line.replace(
            "(self, list_only=False) -> typing.Any:",
            "(self, list_only: bool = False) -> typing.Any:",
        )

    # Add : str to symbol, : str to trade_date
    if "def equity_info(self, symbol) ->" in line:
        lines[i] = line.replace("symbol)", "symbol: str)")
    if "def price_info(self, symbol) ->" in line:
        lines[i] = line.replace("symbol)", "symbol: str)")
    if "def get_market_depth(self, symbol) ->" in line:
        lines[i] = line.replace("symbol)", "symbol: str)")
    if "def futures_data(self, symbol, indices=False) ->" in line:
        lines[i] = line.replace(
            "(self, symbol, indices=False)",
            "(self, symbol: str, indices: bool = False)",
        )
    if "def get_option_chain(self, symbol, expiry, indices=False) ->" in line:
        lines[i] = line.replace(
            "(self, symbol, expiry, indices=False)",
            "(self, symbol: str, expiry: str, indices: bool = False)",
        )
    if "def get_52week_high_low(self, stock=None) ->" in line:
        lines[i] = line.replace("stock=None)", "stock: str | None = None)")

    # Fix from_date / to_date reassignment
    if 'from_date = datetime.strptime(from_date, "%d-%m-%Y")' in line:
        lines[i] = line.replace("from_date = datetime", "from_date_obj = datetime")
    if 'to_date = datetime.strptime(to_date, "%d-%m-%Y")' in line:
        lines[i] = line.replace("to_date = datetime", "to_date_obj = datetime")
    if "load_days = (to_date - from_date).days" in line:
        lines[i] = line.replace(
            "(to_date - from_date)", "(to_date_obj - from_date_obj)"
        )
    if "end_date = (from_date + timedelta" in line:
        lines[i] = line.replace("from_date +", "from_date_obj +")
    if "from_date = from_date + timedelta" in line:
        lines[i] = line.replace(
            "from_date = from_date +", "from_date_obj = from_date_obj +"
        )

    if "from_date  = datetime.now()" in line:
        lines[i] = line.replace("from_date  =", "from_date_obj =")
    if "from_date_str = from_date.strftime" in line:
        lines[i] = line.replace("from_date.strftime", "from_date_obj.strftime")

    # Fix missing types for get_live_option_chain
    if "def get_live_option_chain(" in line:
        pass  # It already has types! But wait, `indices=False` needs `: bool`
    if "indices=False" in line and "def get_live_option_chain" not in line:
        lines[i] = line.replace("indices=False", "indices: bool = False")
    if "indices=False" in line and "def get_live_option_chain" in line:
        lines[i] = line.replace("indices=False", "indices: bool = False")

    # Fix 'except e:' to 'except Exception as e:'
    if "except e:" in line:
        lines[i] = line.replace("except e:", "except Exception as e:")

with open("src/nse_live/nse_utils.py", "w") as f:
    f.writelines(lines)
