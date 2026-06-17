"""
File: tests/test_portfolio.py
Purpose: Unit tests for simulated Portfolio and PortfolioEngine constraints.
Last Modified: 2026-06-01
"""


from src.portfolio.portfolio_engine import Portfolio


def test_portfolio_initialisation() -> None:
    """Verify that simulated Portfolio starts with correct cash and parameters."""
    port = Portfolio(initial_cash=100000.0, max_positions=5)
    assert port.cash == 100000.0
    assert port.get_total_value() == 100000.0
    assert len(port.positions) == 0


def test_portfolio_constraints() -> None:
    """Verify that Portfolio respects cash limits and single position cap checks."""
    port = Portfolio(
        initial_cash=100000.0,
        max_positions=3,
        max_sector_exposure_pct=0.25,
        max_single_position_pct=0.10,
    )

    # Try to add position that exceeds 10% of portfolio (₹10,000)
    # Price = 100, Qty = 150 -> Value = ₹15,000 (15% of total value ₹100,000)
    ok, reason = port.can_add("TCS", "IT", 100.0, 15000.0)
    assert not ok
    assert "exceeds limit" in reason

    # Add a valid position (₹5,000)
    added = port.add_position("TCS", 50, 100.0, 90.0, 120.0, "IT")
    assert added
    assert port.cash == 95000.0
    assert len(port.positions) == 1

    # Check sector limits: IT sector has ₹5,000.
    # Total portfolio value = ₹100,000. IT exposure = 5.0%.
    # Adding another IT position of value ₹25,000 will breach 25% sector limit (since 5k + 25k = 30k = 30%)
    ok, reason = port.can_add("INFY", "IT", 100.0, 25000.0)
    assert not ok
    assert "exceeds limit" in reason
