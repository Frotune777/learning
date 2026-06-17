import os
import subprocess

moves = {
    "pair_scanner.py": "scanners",
    "rsi_scanner.py": "scanners",
    "darvas_box.py": "scanners",
    "momentum_squeeze.py": "scanners",
    "etf_screener.py": "scanners",
    "minervini_screener.py": "scanners",
    "historical_sync.py": "storage",
    "bhavcopy_incremental.py": "storage",
    "downloader.py": "storage",
    "equity_master.py": "storage",
    "sync_registry.py": "storage",
    "ml_gatekeeper.py": "ml",
    "ml_classifier.py": "ml",
    "mmi_scraper.py": "scrapers",
    "nifty_index_fetcher.py": "scrapers",
    "fo_ban.py": "scrapers",
    "daily_signal_reporter.py": "presentation",
    "consensus_engine.py": "core"
}

# Create dirs
for d in set(moves.values()):
    os.makedirs(f"src/{d}", exist_ok=True)
    open(f"src/{d}/__init__.py", "a").close()

# Git mv
for f, d in moves.items():
    src = f"src/nse_bhavcopy/{f}"
    dest = f"src/{d}/{f}"
    if os.path.exists(src):
        subprocess.run(["git", "mv", src, dest])

# Refactor imports across all py files
py_files = []
for root, _, files in os.walk("src"):
    for file in files:
        if file.endswith(".py"):
            py_files.append(os.path.join(root, file))
for root, _, files in os.walk("tests"):
    for file in files:
        if file.endswith(".py"):
            py_files.append(os.path.join(root, file))
py_files.append("main.py")

for path in py_files:
    with open(path) as f:
        content = f.read()

    modified = False
    for mod_file, d in moves.items():
        mod_name = mod_file[:-3]
        old_import = f"src.nse_bhavcopy.{mod_name}"
        new_import = f"src.{d}.{mod_name}"
        if old_import in content:
            content = content.replace(old_import, new_import)
            modified = True

        old_import2 = f"from src.nse_bhavcopy import {mod_name}"
        new_import2 = f"from src.{d} import {mod_name}"
        if old_import2 in content:
            content = content.replace(old_import2, new_import2)
            modified = True

    if modified:
        with open(path, "w") as f:
            f.write(content)

print("Refactoring complete.")
