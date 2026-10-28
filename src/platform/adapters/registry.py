"""Registry and lookup for schema adapters."""

from src.platform.adapters.base import SchemaAdapter
from src.platform.adapters.era_legacy import EraLegacyAdapter
from src.platform.adapters.era_mid import EraMidAdapter
from src.platform.adapters.era_modern import EraModernAdapter
from src.platform.adapters.sec_bhavdata import SecBhavdataAdapter


class AdapterError(Exception):
    """Base exception for adapter errors."""
    pass


class AdapterNotFound(AdapterError):
    """Raised when no registered adapter matches the given headers."""
    pass


class AdapterAmbiguous(AdapterError):
    """Raised when more than one adapter matches the given headers (contract violation)."""
    pass


ADAPTERS: list[SchemaAdapter] = [
    EraLegacyAdapter(),
    EraMidAdapter(),
    EraModernAdapter(),
    SecBhavdataAdapter(),
]


def find_adapter(headers: list[str]) -> SchemaAdapter:
    """Find the single matching adapter for the given headers.
    
    Args:
        headers: List of column names from the raw file.
        
    Returns:
        Matching SchemaAdapter instance.
        
    Raises:
        AdapterNotFound: If zero adapters match.
        AdapterAmbiguous: If more than one adapter matches.
    """
    clean_headers = [h.strip() for h in headers if h and not h.strip().startswith("Unnamed")]
    matches = [adapter for adapter in ADAPTERS if adapter.match(clean_headers)]

    if not matches:
        raise AdapterNotFound(f"No adapter matched headers: {clean_headers[:10]}...")
    if len(matches) > 1:
        names = [m.name for m in matches]
        raise AdapterAmbiguous(f"Multiple adapters matched headers {clean_headers[:10]}: {names}")

    return matches[0]
