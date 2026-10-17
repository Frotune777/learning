"""Parity and integrity tests for Phase B.5 (Master Enrichment + Delivery + Surveillance)."""

from pathlib import Path

import duckdb


def _get_wh_conn() -> duckdb.DuckDBPyConnection:
    wh_path = Path("data/warehouse.duckdb")
    assert wh_path.exists(), "Warehouse database data/warehouse.duckdb must exist"
    return duckdb.connect(str(wh_path), read_only=True)


def test_dim_symbol_row_count_and_scope() -> None:
    """Target dim_symbol count must be >= 2,948 and <= 3,500 distinct symbols."""
    conn = _get_wh_conn()
    try:
        query = "SELECT count(DISTINCT symbol) FROM dim_symbol"
        distinct_syms = conn.execute(query).fetchone()[0]
        assert 2948 <= distinct_syms <= 3500, (
            f"Expected 2948-3500 distinct symbols, got {distinct_syms}"
        )
    finally:
        conn.close()


def test_dim_symbol_isin_completeness() -> None:
    """100% of is_current = TRUE symbols must have a valid non-null ISIN."""
    conn = _get_wh_conn()
    try:
        query = (
            "SELECT count(*) FROM dim_symbol "
            "WHERE is_current = TRUE AND (isin IS NULL OR isin = '')"
        )
        null_isin_count = conn.execute(query).fetchone()[0]
        assert null_isin_count == 0, f"Found {null_isin_count} active symbols with NULL ISIN"
    finally:
        conn.close()


def test_all_historical_symbols_in_dim_symbol() -> None:
    """Every historical parquet file in data/historical/1d must have a matching dim_symbol."""
    conn = _get_wh_conn()
    try:
        sql = "SELECT DISTINCT symbol FROM dim_symbol"
        wh_symbols = {r[0] for r in conn.execute(sql).fetchall()}
        hist_symbols = {f.stem.upper() for f in Path("data/historical/1d").glob("*.parquet")}
        missing = hist_symbols - wh_symbols
        assert not missing, f"Historical symbols missing: {sorted(list(missing))[:10]}"
    finally:
        conn.close()


def test_delisted_symbols_classification() -> None:
    """Delisted symbols must be marked is_active=FALSE, is_tradable=FALSE."""
    conn = _get_wh_conn()
    try:
        query = """
        SELECT symbol, is_active, is_tradable, delisting_date
        FROM dim_symbol
        WHERE is_active = FALSE
        """
        rows = conn.execute(query).fetchall()
        assert len(rows) >= 135, f"Expected at least 135 delisted symbols, got {len(rows)}"
        for sym, is_act, is_trad, del_date in rows:
            assert is_act is False, f"Delisted symbol {sym} has is_active=True"
            assert is_trad is False, f"Delisted symbol {sym} has is_tradable=True"
            assert del_date is not None, f"Delisted symbol {sym} has null delisting_date"
    finally:
        conn.close()


def test_sme_symbols_tradability() -> None:
    """SME symbols (series=SM) must have listing_board='SME' and is_tradable=FALSE."""
    conn = _get_wh_conn()
    try:
        query = """
        SELECT count(*)
        FROM dim_symbol
        WHERE series = 'SM' AND (listing_board != 'SME' OR is_tradable = TRUE)
        """
        rows = conn.execute(query).fetchone()[0]
        assert rows == 0, f"Found {rows} SME symbols violating listing_board/is_tradable"
    finally:
        conn.close()


def test_zero_orphan_foreign_keys_b5() -> None:
    """Verify zero orphan foreign keys in all warehouse fact tables."""
    conn = _get_wh_conn()
    try:
        fact_tables = [
            "fact_price_daily",
            "fact_ta_daily",
            "fact_delivery_daily",
            "fact_index_membership",
            "fact_symbol_health",
            "fact_symbol_surveillance",
        ]
        for tbl in fact_tables:
            query = f"""
            SELECT count(*)
            FROM {tbl} f
            LEFT JOIN dim_symbol d ON f.symbol_sk = d.symbol_sk
            WHERE d.symbol_sk IS NULL
            """
            orphan_count = conn.execute(query).fetchone()[0]
            assert orphan_count == 0, f"Found {orphan_count} orphan FKs in {tbl}"
    finally:
        conn.close()


def test_delivery_data_tcs_verification() -> None:
    """Verify delivery data for TCS on 2026-10-16 exists with realistic volume and delivery pct."""
    conn = _get_wh_conn()
    try:
        query = """
        SELECT symbol, trade_date, traded_qty, deliverable_qty, delivery_pct
        FROM fact_delivery_daily
        WHERE symbol = 'TCS' AND trade_date = '2026-10-16'
        """
        row = conn.execute(query).fetchone()
        assert row is not None, "Missing delivery row for TCS on 2026-10-16"
        assert row[2] > 0, "Traded quantity should be > 0"
        assert row[3] > 0, "Deliverable quantity should be > 0"
        assert 0.0 <= row[4] <= 100.0, "Delivery percentage should be within [0, 100]"
    finally:
        conn.close()


def test_index_membership_coverage() -> None:
    """Verify index membership is populated with standard benchmark indices."""
    conn = _get_wh_conn()
    try:
        sql = "SELECT DISTINCT index_code FROM dim_index"
        indices = [r[0] for r in conn.execute(sql).fetchall()]
        assert len(indices) >= 20, f"Expected at least 20 indices, got {len(indices)}"

        query = "SELECT count(*) FROM fact_index_membership"
        membership_count = conn.execute(query).fetchone()[0]
        assert membership_count > 1500, f"Expected >1500 index memberships, got {membership_count}"
    finally:
        conn.close()


def test_symbol_health_and_surveillance_populated() -> None:
    """Verify fact_symbol_health and fact_symbol_surveillance are populated."""
    conn = _get_wh_conn()
    try:
        h_query = "SELECT count(*) FROM fact_symbol_health"
        health_cnt = conn.execute(h_query).fetchone()[0]
        assert health_cnt > 2500, f"Expected >2500 health records, got {health_cnt}"

        s_query = "SELECT count(*) FROM fact_symbol_surveillance"
        surv_cnt = conn.execute(s_query).fetchone()[0]
        assert surv_cnt > 2500, f"Expected >2500 surveillance records, got {surv_cnt}"
    finally:
        conn.close()
