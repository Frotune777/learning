"""Unit tests for Tier 1 and Tier 2 master enrichment loader."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.platform.loaders.master_enrichment import MasterEnrichmentLoader


def test_ingest_equity_l(tmp_path: Path) -> None:
    loader = MasterEnrichmentLoader(landing_root=tmp_path / "landing")
    sample_csv = (
        b"SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, "
        b"PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE\n"
        b"TCS,Tata Consultancy Services Limited,EQ,25-AUG-2004,1,1,INE467B01029,1\n"
    )

    with patch.object(loader, "_download", return_value=sample_csv):
        rows = loader.ingest_equity_l(date(2026, 10, 17))
        assert rows == 1

        # Check landing files created
        batch_dirs = list((tmp_path / "landing" / "nse_equity_l" / "2026-10-17").glob("*"))
        assert len(batch_dirs) == 1
        assert (batch_dirs[0] / "equity_l.csv").is_file()
        assert (batch_dirs[0] / "manifest.json").is_file()

        # Reusing landing should not trigger _download again
        mock_download = MagicMock()
        with patch.object(loader, "_download", mock_download):
            reused_rows = loader.ingest_equity_l(date(2026, 10, 17))
            assert reused_rows == 1
            mock_download.assert_not_called()


def test_ingest_fo_mktlots(tmp_path: Path) -> None:
    loader = MasterEnrichmentLoader(landing_root=tmp_path / "landing")
    sample_csv = b"UNDERLYING,SYMBOL,OCT-2026,NOV-2026\nTATA CONSULTANCY SERVICES,TCS,175,175\n"

    with patch.object(loader, "_download", return_value=sample_csv):
        rows = loader.ingest_fo_mktlots(date(2026, 10, 17))
        assert rows == 1

        batch_dirs = list((tmp_path / "landing" / "nse_fo_mktlots" / "2026-10-17").glob("*"))
        assert len(batch_dirs) == 1
        assert (batch_dirs[0] / "fo_mktlots.csv").is_file()
        assert (batch_dirs[0] / "manifest.json").is_file()


def test_ingest_sec_bhavdata_full(tmp_path: Path) -> None:
    loader = MasterEnrichmentLoader(landing_root=tmp_path / "landing")
    sample_csv = (
        b"SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, "
        b"LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, "
        b"TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER\n"
        b"TCS, EQ, 16-Oct-2026, 3500, 3510, 3550, 3500, 3520, 3525, "
        b"3525, 100000, 3525, 5000, 60000, 60.0\n"
    )

    with patch.object(loader, "_download", return_value=sample_csv):
        rows = loader.ingest_sec_bhavdata_full(date(2026, 10, 16))
        assert rows == 1

        batch_dirs = list(
            (tmp_path / "landing" / "nse_sec_bhavdata_full" / "2026-10-16").glob("*")
        )
        assert len(batch_dirs) == 1
        assert (batch_dirs[0] / "sec_bhavdata_full.csv").is_file()
        assert (batch_dirs[0] / "manifest.json").is_file()
