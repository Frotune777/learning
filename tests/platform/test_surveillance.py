"""Unit tests for surveillance data loaders (ASM, GSM, ESM)."""

from unittest.mock import MagicMock

from src.platform.loaders.surveillance import (
    fetch_asm_list,
    fetch_esm_list,
    fetch_gsm_list,
)


def test_fetch_asm_list_success() -> None:
    session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {"symbol": "TCS", "stage": "STAGE_1", "effectiveDate": "2026-10-01"},
            {"symbol": "INFY", "stage": "STAGE_2", "effectiveDate": "2026-10-05"},
        ]
    }
    session.get.return_value = mock_resp

    df = fetch_asm_list(session)
    assert len(df) == 2
    assert "TCS" in df["symbol"].values
    assert bool(df.loc[df["symbol"] == "TCS", "is_asm"].values[0]) is True


def test_fetch_surveillance_fallback_on_network_error() -> None:
    session = MagicMock()
    session.get.side_effect = Exception("Network timeout")

    asm_df = fetch_asm_list(session)
    gsm_df = fetch_gsm_list(session)
    esm_df = fetch_esm_list(session)

    assert asm_df.empty
    assert gsm_df.empty
    assert esm_df.empty
    assert "symbol" in asm_df.columns
