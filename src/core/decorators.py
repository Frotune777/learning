"""
File: src/core/decorators.py
Purpose: Reusable CLI and validation decorators for the NSE pipeline.
Last Modified: 2026-05-31
"""

from collections.abc import Callable
from functools import wraps

import structlog
from tqdm import tqdm

logger = structlog.get_logger("nse_pipeline")


def validate_symbol(func: Callable) -> Callable:
    """
    Validate that a stock symbol argument is non-empty and alphanumeric.

    Parameters:
        func (Callable): Function whose first positional arg is a symbol string.

    Returns:
        Callable: Wrapped function that raises ValueError on bad symbols.

    Raises:
        ValueError: If symbol is empty or contains non-alphanumeric characters.

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> @validate_symbol
        ... def process(symbol: str) -> str:
        ...     return symbol
        >>> process("TCS")
        'TCS'
    """

    @wraps(func)
    def wrapper(symbol: str, *args: object, **kwargs: object) -> object:
        """Inner wrapper that performs symbol validation."""
        if not symbol or not symbol.replace(".", "").replace("^", "").isalnum():
            raise ValueError(f"Invalid symbol format: {symbol}")
        return func(symbol.upper(), *args, **kwargs)

    return wrapper


def with_progress_bar(description: str = "Processing") -> Callable:
    """
    Decorator factory that wraps an iterator function with a tqdm progress bar.

    Parameters:
        description (str): Label shown beside the progress bar. | Default: "Processing"

    Returns:
        Callable: Decorator that yields items from the wrapped function with progress.

    Complexity:
        Time: O(N) [N = items in iterator]
        Space: O(1) [streaming]

    Example:
        >>> @with_progress_bar("Loading")
        ... def gen_items() -> list[int]:
        ...     return [1, 2, 3]
    """

    def decorator(func: Callable) -> Callable:
        """Apply tqdm progress bar to iterator functions."""

        @wraps(func)
        def wrapper(*args: object, **kwargs: object) -> object:
            """Inner wrapper that displays a progress bar."""
            result = func(*args, **kwargs)
            if isinstance(result, list | dict) and len(result) > 0:
                yield from tqdm(result, desc=description)
            else:
                yield from result

        return wrapper

    return decorator


def dry_run_capable(func: Callable) -> Callable:
    """
    Decorator that adds a dry_run keyword argument to any function.

    Parameters:
        func (Callable): Function to wrap with dry-run capability.

    Returns:
        Callable: Wrapped function that short-circuits when dry_run=True.

    Complexity:
        Time: O(1) on dry-run path
        Space: O(1)

    Example:
        >>> @dry_run_capable
        ... def sync(symbols: list[str]) -> None:
        ...     pass
        >>> sync(["TCS"], dry_run=True)  # prints DRY RUN, returns None
    """

    @wraps(func)
    def wrapper(*args: object, dry_run: bool = False, **kwargs: object) -> object:
        """Inner wrapper that handles dry-run mode."""
        if dry_run:
            logger.info("dry_run_mode", function=func.__name__)
            print(f"\n  [DRY RUN] Would execute: {func.__name__}")
            return None
        return func(*args, **kwargs)

    return wrapper
