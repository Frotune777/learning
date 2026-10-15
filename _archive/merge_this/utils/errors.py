"""Error handling utilities for Screeni-py."""

import functools
import logging
import sys
import traceback
from enum import Enum
from typing import Any, Callable, TypeVar

from rich.console import Console

console = Console()
F = TypeVar("F", bound=Callable[..., Any])


class ErrorCodes(Enum):
    """Standardized Error Codes for the Application."""
    CONFIG_ERROR = "E001"
    DATA_FETCH_ERROR = "D100"
    DATA_EMPTY = "D102"
    INDICATOR_ERROR = "S201"
    ML_TRAIN_ERROR = "M400"
    UNKNOWN_ERROR = "U999"


class ErrorManager:
    """Centralized Error Handling and Logging with Structured Error Codes."""
    
    _initialized = False
    _logger = None
    
    @classmethod
    def _initialize(cls):
        """Initialize the error manager once."""
        if not cls._initialized:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            cls._logger = logging.getLogger("ErrorManager")
            cls._initialized = True
    
    @classmethod
    def handle_error(cls, e: Exception, context: str = 'General', 
                     code: ErrorCodes = ErrorCodes.UNKNOWN_ERROR, 
                     fatal: bool = False, verbose: bool = False) -> None:
        """Log and display an error with structured code."""
        cls._initialize()
        
        error_msg = f"[{code.value}] {context}: {str(e)}"
        cls._logger.error(error_msg)
        
        if verbose:
            traceback.print_exc()
        
        if fatal:
            console.print(f"\n[bold red]❌ FATAL ERROR: {error_msg}[/bold red]")
            sys.exit(1)
        else:
            console.print(f"\n[bold yellow]⚠️ Error: {error_msg}[/bold yellow]")
    
    @classmethod
    def log_info(cls, message: str, context: str = 'System') -> None:
        """Log Information"""
        cls._initialize()
        cls._logger.info(f"[{context}] {message}")
    
    @classmethod
    def log_debug(cls, message: str, context: str = 'System') -> None:
        """Log Debug Information"""
        cls._initialize()
        cls._logger.debug(f"[{context}] {message}")
    
    @classmethod
    def log_warning(cls, message: str, context: str = 'System') -> None:
        """Log Warning"""
        cls._initialize()
        cls._logger.warning(f"[{context}] {message}")


def safe_execution(func: F) -> F:
    """
    Decorator to catch and display errors gracefully in a CLI environment.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️ Operation cancelled by user[/yellow]")
            return None
        except Exception as e:
            console.print(
                f"\n[bold red]❌ Error in {func.__name__}: {str(e)}[/bold red]"
            )
            logging.exception(f"Exception trapped in {func.__name__}")
            return None
    return wrapper
