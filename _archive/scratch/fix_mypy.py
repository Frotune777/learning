with open("src/nse_live/nse_utils.py") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    # Fix datetime reassignment
    if 'trade_date = datetime.strptime(trade_date, "%d-%m-%Y")' in line:
        lines[i] = line.replace(
            "trade_date = datetime.strptime", "trade_date_obj = datetime.strptime"
        )
    if "trade_date = datetime.strptime(trade_date, dd_mm_yyyy)" in line:
        lines[i] = line.replace("trade_date = datetime", "trade_date_obj = datetime")
    if "use_date = trade_date.strftime" in line:
        lines[i] = line.replace("trade_date.strftime", "trade_date_obj.strftime")
    if 'f"{trade_date.strftime' in line:
        lines[i] = line.replace("trade_date.strftime", "trade_date_obj.strftime")

    # Add return type Any to defs that don't have ->
    if line.strip().startswith("def ") and "->" not in line:
        # Check if line ends with :
        if line.rstrip("\n").endswith(":"):
            lines[i] = line.rstrip("\n")[:-1] + " -> typing.Any:\n"

with open("src/nse_live/nse_utils.py", "w") as f:
    f.writelines(lines)
