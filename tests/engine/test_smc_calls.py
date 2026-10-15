import pandas as pd
import pytest

from src.engine.smc import calculate_smc
from src.engine.smc_decision import TradingCall, generate_smc_call
from src.storage.smc_db import SMCDatabase


def test_full_smc_call_pipeline(tmp_path):
    db_file = str(tmp_path / "test_calls.sqlite")
    db = SMCDatabase(db_path=db_file)

    # 1. Simulate a trend with an Order Block
    prices = [100, 102, 101, 105, 108, 112, 110, 107, 104, 101, 102]
    df = pd.DataFrame({
        "open": prices,
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": prices,
        "volume": [1000] * len(prices)
    })

    smc_res = calculate_smc(df, swing_length=3, internal_length=2)
    call = generate_smc_call("TEST_STOCK", smc_res, df)

    # 2. Test CRUD insertion
    dummy_call = TradingCall(
        symbol="RELIANCE",
        timestamp="2026-10-15 10:00:00",
        direction="BUY",
        setup_type="OB_DEMAND_TAP",
        entry_price=2950.0,
        stop_loss=2920.0,
        target_1=3010.0,
        target_2=3070.0,
        risk_reward=2.0,
        status="PENDING",
        notes="Discount zone test"
    )

    call_id = db.create_call(dummy_call)
    assert call_id > 0

    # 3. Read
    active_calls = db.get_calls(status="PENDING")
    assert len(active_calls) == 1
    assert active_calls[0]["symbol"] == "RELIANCE"

    # 4. Update
    db.update_status(call_id, "TRIGGERED", "Filled at 2950")
    updated = db.get_calls(status="TRIGGERED")
    assert len(updated) == 1

    # 5. Delete
    db.delete_call(call_id)
    assert len(db.get_calls()) == 0
