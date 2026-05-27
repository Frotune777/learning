"""
File: src/data/fetcher/circuit_breaker.py
Purpose: Stateful circuit breaker implementation to prevent cascading network failures.

Dependencies:
External:
- None
Internal:
- None

Key Components:
Classes:
- CircuitBreaker: Manages closed, open, and half-open failure isolation states.
Functions:
- None

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- [ ] [MEDIUM] Add event dispatcher notifications on state transitions

Related Files:
- src/data/fetcher/prices/nse_charts.py: Calls targets inside the circuit breaker.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    STATEFUL CIRCUIT BREAKER TO PREVENT CASCADING REMOTE TIMEOUTS.

    Design Pattern: Circuit Breaker - Prevents calling an unstable external
    endpoint when successive failures exceed threshold.

    Attributes:
        failure_threshold (int): Failures allowed before opening. | Default 5.
        recovery_timeout (float): Open state duration in seconds. | Default 30.0.
        state (str): Current breaker state ('CLOSED', 'OPEN', 'HALF-OPEN').
        failure_count (int): Count of consecutive failures. | Default 0.
        last_state_change (float): Timestamp of last transition. | Default now.

    Public Methods:
        - call(func, *args, **kwargs): Execute method inside breaker protection.

    Private Methods:
        - _transition_to(new_state): Transition state and update timestamps.

    Usage Flow:
        1. Instantiate CircuitBreaker.
        2. Execute remote calls wrapping them with .call().
        3. Catch raised exceptions if breaker is currently OPEN.

    Example:
        >>> cb = CircuitBreaker(failure_threshold=2)
        >>> def test(): return 1 / 0
        >>> try: cb.call(test)
        ... except ZeroDivisionError: pass

    State Management:
        - Valid states: 'CLOSED', 'OPEN', 'HALF-OPEN'
        - State transitions:
            CLOSED -> OPEN (failure count > threshold)
            OPEN -> HALF-OPEN (recovery timeout elapsed)
            HALF-OPEN -> CLOSED (success)
            HALF-OPEN -> OPEN (failure)

    Thread Safety: Partial - Internal counters are not currently locked.

    Dependencies:
        External: None
        Internal: None
    """

    def __init__(
        self, failure_threshold: int = 5, recovery_timeout: float = 30.0
    ) -> None:
        """Initialize the breaker with failure limits and timeout limits."""
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_state_change = time.time()

    def _transition_to(self, new_state: str) -> None:
        """
        TRANSITION THE CIRCUIT BREAKER TO A NEW STATE SAFELY.

        Logic:
            Step 1: Set internal state variable to the target name.
            Step 2: Log transition info with timestamps.
            Step 3: Update state change tracking clock.

        Parameters:
            new_state (str): Name of target state. | Must be valid string.

        Returns:
            None

        Raises:
            None

        Example:
            >>> cb = CircuitBreaker()
            >>> cb._transition_to("OPEN")

        Performance:
            Time Complexity: O(1) [Immediate assignment]
            Space Complexity: O(1) [No allocations]

        Edge Cases Handled:
            - Handles arbitrary transitions cleanly for debugging.
        """
        logger.info("CircuitBreaker state changed: %s -> %s", self.state, new_state)
        self.state = new_state
        self.last_state_change = time.time()

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        EXECUTE THE CALL UNDER STATEFUL BREAKER PROTECTION.

        Logic:
            Step 1: If OPEN, check if recovery_timeout has elapsed. If yes,
                    transition to HALF-OPEN. If no, fail fast immediately.
            Step 2: Try executing the provided function.
            Step 3: If successful and HALF-OPEN, reset to CLOSED. Return result.
            Step 4: If Exception occurs, increment failures. If CLOSED/HALF-OPEN
                    and count > threshold, transition to OPEN. Re-raise error.

        Parameters:
            func (Callable[..., Any]): Target remote retrieval function.
            *args (Any): Target function arguments.
            **kwargs (Any): Target function keywords.

        Returns:
            Any: Target function response payload.

        Raises:
            Exception: Re-raises the target function failure.
            RuntimeError: Breaker is open and failing fast.

        Example:
            >>> cb = CircuitBreaker()
            >>> res = cb.call(lambda: 42)
            >>> print(res)
            42

        Performance:
            Time Complexity: O(1) [Breaker checking wrapper overhead]
            Space Complexity: O(1) [Wrapper variables]

        Edge Cases Handled:
            - Fast-failing immediately when breaker state is OPEN.
            - Testing recovery in HALF-OPEN state.

        TODO:
            - None

        Notes:
            None
        """
        now = time.time()

        # Step 1: Manage OPEN state recovery timeout checks
        if self.state == "OPEN":
            if now - self.last_state_change >= self.recovery_timeout:
                self._transition_to("HALF-OPEN")
            else:
                rem = self.recovery_timeout - (now - self.last_state_change)
                raise RuntimeError(
                    f"CircuitBreaker is OPEN (Failing fast). "
                    f"Remaining timeout: {rem:.1f}s"
                )

        # Step 2: Attempt remote execution call
        try:
            result = func(*args, **kwargs)

            # Step 3: Success recovery reset
            if self.state == "HALF-OPEN":
                self.failure_count = 0
                self._transition_to("CLOSED")
            elif self.state == "CLOSED":
                self.failure_count = 0

            return result

        except Exception as ex:
            # Step 4: Handle failure transitions
            self.failure_count += 1
            logger.warning(
                "CircuitBreaker observed failure count=%d: %s",
                self.failure_count,
                ex,
            )

            if self.state in ("CLOSED", "HALF-OPEN"):
                if self.failure_count >= self.failure_threshold:
                    self._transition_to("OPEN")

            raise ex
