"""Unit tests for staging YAML schema contracts."""


import pytest

from src.platform.exceptions import SchemaValidationError
from src.platform.schemas import load, load_schema

ALL_SCHEMAS = [
    "price_daily",
    "delivery_daily",
    "corporate_actions",
    "equity_master",
    "surveillance",
    "index_membership",
]


@pytest.mark.parametrize("name", ALL_SCHEMAS)
def test_all_schemas_load_cleanly(name: str) -> None:
    """Verify that every canonical staging schema loads without error."""
    schema = load(name)
    assert schema.name == name
    assert schema.target_table != ""
    assert len(schema.columns) > 0
    assert len(schema.primary_key) > 0


def test_price_daily_columns_contract() -> None:
    """Validate explicit field contracts in price_daily schema."""
    schema = load("price_daily")
    assert schema.target_table == "fact_price_daily"
    expected_fields = {
        "symbol", "trade_date", "open", "high", "low", "close", "volume", "turnover", "batch_id"
    }
    assert expected_fields.issubset(set(schema.columns.keys()))
    assert "symbol" in schema.primary_key
    assert "trade_date" in schema.primary_key


def test_missing_schema_raises_error() -> None:
    """Verify SchemaValidationError on non-existent schema file."""
    with pytest.raises(SchemaValidationError):
        load_schema("schemas/staging/non_existent_table.yaml")
