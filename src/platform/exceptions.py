"""Platform typed domain exception hierarchy."""

from __future__ import annotations


class PlatformError(Exception):
    """Base exception for all platform errors."""


class SchemaValidationError(PlatformError):
    """Raised when data or file schema violates contract specifications."""


class LineageIntegrityError(PlatformError):
    """Raised when batch ID, SHA-256 checksum, or manifest validation fails."""


class WarehouseConstraintViolation(PlatformError):
    """Raised when a unique, foreign key, or check constraint is violated."""


class DataQualityHaltError(PlatformError):
    """Raised when data quality gate checks exceed failure halt threshold."""


class EntityNotFoundError(PlatformError):
    """Raised when a requested domain entity is not found in the repository."""


class LockAcquisitionError(PlatformError):
    """Raised when process-level or database file lock cannot be acquired."""


class MigrationError(PlatformError):
    """Raised when a database schema migration step fails."""
