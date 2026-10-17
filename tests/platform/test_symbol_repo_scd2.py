"""Unit tests for SymbolRepo SCD Type 2 dimension management."""

from datetime import date, timedelta
from pathlib import Path

import duckdb

from src.platform.migrations.runner import MigrationRunner
from src.platform.repositories.symbol_repo import SymbolRepo


def _init_repo(db_path: Path) -> SymbolRepo:
    runner = MigrationRunner(db_path=db_path)
    runner.migrate()
    conn = duckdb.connect(str(db_path))
    return SymbolRepo(conn=conn)


def test_initial_insert_scd2(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "test_scd2.duckdb")
    records = [
        {
            "symbol": "ABC",
            "isin": "INE123ABC01",
            "company_name": "ABC Tech Ltd",
            "series": "EQ",
            "sector": "Information Technology",
            "is_active": True,
        }
    ]
    counts = repo.upsert_scd2(records)
    assert counts["inserted"] == 1
    assert counts["updated"] == 0

    sym = repo.get_symbol("ABC")
    assert sym is not None
    assert sym["symbol"] == "ABC"
    assert sym["is_current"] is True
    assert sym["is_active"] is True
    assert sym["is_tradable"] is True
    assert sym["listing_board"] == "Main"
    assert sym["valid_to"] == date(9999, 12, 31)


def test_noop_upsert(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "test_scd2.duckdb")
    rec = {
        "symbol": "ABC",
        "isin": "INE123ABC01",
        "company_name": "ABC Tech Ltd",
        "series": "EQ",
        "sector": "Information Technology",
        "is_active": True,
    }
    repo.upsert_scd2([rec])

    # Re-upsert identical record
    counts = repo.upsert_scd2([rec])
    assert counts["inserted"] == 0
    assert counts["updated"] == 0
    assert counts["unchanged"] == 1


def test_attribute_update_scd2(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "test_scd2.duckdb")
    rec1 = {
        "symbol": "ABC",
        "isin": "INE123ABC01",
        "company_name": "ABC Old Name",
        "series": "EQ",
        "sector": "Old Sector",
        "is_active": True,
        "valid_from": date(2020, 1, 1),
    }
    repo.upsert_scd2([rec1])

    # Update sector and company name
    rec2 = {
        "symbol": "ABC",
        "isin": "INE123ABC01",
        "company_name": "ABC New Name",
        "series": "EQ",
        "sector": "New Sector",
        "is_active": True,
    }
    counts = repo.upsert_scd2([rec2])
    assert counts["updated"] == 1

    # Check database rows for ABC
    query = (
        "SELECT symbol, company_name, is_current, valid_from, valid_to "
        "FROM dim_symbol WHERE symbol = 'ABC' ORDER BY valid_from"
    )
    rows = repo._ensure_conn().execute(query).fetchall()
    assert len(rows) == 2
    # Old version closed
    assert rows[0][1] == "ABC Old Name"
    assert rows[0][2] is False
    assert rows[0][4] == date.today() - timedelta(days=1)
    # New version active
    assert rows[1][1] == "ABC New Name"
    assert rows[1][2] is True
    assert rows[1][4] == date(9999, 12, 31)


def test_tradability_and_board_classification(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "test_scd2.duckdb")
    records = [
        {"symbol": "MAIN_EQ", "series": "EQ", "is_active": True},
        {"symbol": "SME_SM", "series": "SM", "is_active": True},
        {"symbol": "INACTIVE_EQ", "series": "EQ", "is_active": False},
    ]
    repo.upsert_scd2(records)

    main_eq = repo.get_symbol("MAIN_EQ")
    assert main_eq["is_tradable"] is True
    assert main_eq["listing_board"] == "Main"

    sme_sm = repo.get_symbol("SME_SM")
    assert sme_sm["is_tradable"] is False
    assert sme_sm["listing_board"] == "SME"

    # For inactive symbol, is_current was set to False
    all_rows = repo._ensure_conn().execute(
        "SELECT is_tradable, is_active FROM dim_symbol WHERE symbol = 'INACTIVE_EQ'"
    ).fetchone()
    assert all_rows[0] is False
    assert all_rows[1] is False
