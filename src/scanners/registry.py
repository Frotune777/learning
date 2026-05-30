"""
File: src/scanners/registry.py
Purpose: Central registry for all scanner strategies.
Last Modified: 2026-05-30
"""

from typing import Callable, Any
from src.core.signal import Signal

# Internal registry
_REGISTRY: list[Callable[..., list[Signal]]] = []

def register_scanner(fn: Callable[..., list[Signal]]) -> Callable[..., list[Signal]]:
    """Decorator to register a scanner function."""
    _REGISTRY.append(fn)
    return fn

def get_all_scanners() -> list[Callable[..., list[Signal]]]:
    """
    Returns a list of all active scanner functions that adhere to the Signal protocol.
    """
    return _REGISTRY.copy()
