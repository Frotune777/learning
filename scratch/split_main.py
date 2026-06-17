
with open('main.py') as f:
    lines = f.readlines()

# Collect imports
imports = lines[0:96]

# formatters.py
# 97-200, 894-902 (_print_banner), 1184-1250 (_display_csv)
formatters_lines = (
    imports +
    ["import rich\nfrom rich.console import Console\nfrom rich.table import Table\nfrom rich.panel import Panel\nfrom rich.text import Text\n"] +
    lines[96:200] +
    lines[893:902] +
    lines[1183:1250]
)

# actions.py
# 208-886
actions_lines = (
    imports +
    ["from src.cli.formatters import _c, dim, bold, green, yellow, red, cyan, white, blue, _rule, _header, _subheader, ok, warn, err, tip, _pause, _confirm, _ask, _ask_float\n"] +
    lines[207:886]
)

# menus.py
# 905-1181, 1253-3126
menus_lines = (
    imports +
    ["from src.cli.formatters import _c, dim, bold, green, yellow, red, cyan, white, blue, _rule, _header, _subheader, ok, warn, err, tip, _pause, _confirm, _ask, _ask_float, _print_banner, _display_csv\n"] +
    ["from src.cli.actions import *\n"] +
    lines[904:1181] +
    lines[1252:3126]
)

with open('src/cli/formatters.py', 'w') as f:
    f.writelines(formatters_lines)

with open('src/cli/actions.py', 'w') as f:
    f.writelines(actions_lines)

with open('src/cli/menus.py', 'w') as f:
    f.writelines(menus_lines)

main_new = (
    imports +
    ["from src.cli.menus import interactive_menu, _build_parser\n"] +
    lines[3128:3166]
)

with open('main.py', 'w') as f:
    f.writelines(main_new)

print("Split completed.")
