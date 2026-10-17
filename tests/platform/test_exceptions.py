"""Unit tests for platform domain exception hierarchy."""

import pytest

from src.platform.exceptions import (
    DataQualityHaltError,
    EntityNotFoundError,
    LineageIntegrityError,
    LockAcquisitionError,
    MigrationError,
    PlatformError,
    SchemaValidationError,
    WarehouseConstraintViolation,
)


def test_exception_inheritance() -> None:
    """Verify that all platform exceptions inherit from PlatformError."""
    assert issubclass(SchemaValidationError, PlatformError)
    assert issubclass(LineageIntegrityError, PlatformError)
    assert issubclass(WarehouseConstraintViolation, PlatformError)
    assert issubclass(DataQualityHaltError, PlatformError)
    assert issubclass(EntityNotFoundError, PlatformError)
    assert issubclass(LockAcquisitionError, PlatformError)
    assert issubclass(MigrationError, PlatformError)


def test_catch_by_base_class() -> None:
    """Verify that any platform exception can be trapped via PlatformError."""
    with pytest.raises(PlatformError):
        raise SchemaValidationError("Invalid column type")

    with pytest.raises(PlatformError):
        raise LineageIntegrityError("Checksum mismatch")

    with pytest.raises(PlatformError):
        raise DataQualityHaltError("Quality halt triggered")
