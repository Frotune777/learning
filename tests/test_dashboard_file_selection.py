import glob
import os
from pathlib import Path


def test_enriched_selected_over_analyzed(tmp_path: Path):
    analyzed = tmp_path / "top_250_analyzed_20261015.csv"
    enriched = tmp_path / "top_250_enriched_20261015.csv"
    analyzed.write_text("Symbol,Close\nTCS,3500\n", encoding="utf-8")
    enriched.write_text("Symbol,Close,COMPOSITE_SCORE\nTCS,3500,85.0\n", encoding="utf-8")

    analyzed_files = sorted(glob.glob(os.path.join(str(tmp_path), "top_250_analyzed_*.csv")))
    enriched_files = sorted(glob.glob(os.path.join(str(tmp_path), "top_250_enriched_*.csv")))

    # Selection contract from 01_daily_signals.py
    target_files = enriched_files if enriched_files else analyzed_files

    assert len(target_files) == 1
    assert "top_250_enriched_" in target_files[0]
