"""Circuit breaker pattern for resilient external provider invocation."""

import enum
import time
from typing import Callable, Dict, Optional
from gaswise.domain.ports import ProviderUnavailableError


class CircuitState(str, enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Manages failure tracking and short-circuiting for an individual external provider."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.clock = clock
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.last_state_change = self.clock()
        self.last_error: Optional[str] = None

    def can_execute(self) -> bool:
        """Determines if a request is allowed to proceed."""
        now = self.clock()
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if now - self.last_state_change >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                return True
            return False
        # HALF_OPEN allows probe
        return True

    def record_success(self) -> None:
        """Records a successful upstream call, resetting the breaker to CLOSED."""
        self.failure_count = 0
        self.last_error = None
        if self.state != CircuitState.CLOSED:
            self.state = CircuitState.CLOSED
            self.last_state_change = self.clock()

    def record_failure(self, error: Exception) -> None:
        """Records a provider failure and transitions to OPEN if threshold reached."""
        now = self.clock()
        self.last_failure_time = now
        self.last_error = str(error)
        self.failure_count += 1

        if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = now


class CircuitBreakerRegistry:
    """Registry of circuit breakers per upstream provider/source."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.clock = clock
        self.breakers: Dict[str, CircuitBreaker] = {}

    def get(self, name: str) -> CircuitBreaker:
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=self.failure_threshold,
                recovery_timeout=self.recovery_timeout,
                clock=self.clock,
            )
        return self.breakers[name]

    def can_execute(self, name: str) -> bool:
        return self.get(name).can_execute()

    def record_success(self, name: str) -> None:
        self.get(name).record_success()

    def record_failure(self, name: str, error: Exception) -> None:
        self.get(name).record_failure(error)

    def is_open(self, name: str) -> bool:
        breaker = self.breakers.get(name)
        if breaker is None:
            return False
        return not breaker.can_execute()

    def clear(self) -> None:
        self.breakers.clear()
