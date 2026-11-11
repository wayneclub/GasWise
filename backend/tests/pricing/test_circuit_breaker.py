import pytest
from gaswise.domain.ports import ProviderError, ProviderUnavailableError
from gaswise.services.pricing.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitState,
)


def test_circuit_breaker_starts_closed():
    breaker = CircuitBreaker("gasbuddy", failure_threshold=3, recovery_timeout=30.0)
    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute() is True
    assert breaker.failure_count == 0


def test_circuit_breaker_trips_to_open_after_threshold_failures():
    now = 100.0
    breaker = CircuitBreaker("gasbuddy", failure_threshold=3, recovery_timeout=30.0, clock=lambda: now)

    breaker.record_failure(ProviderError("fail 1"))
    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute() is True

    breaker.record_failure(ProviderError("fail 2"))
    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute() is True

    breaker.record_failure(ProviderError("fail 3"))
    assert breaker.state == CircuitState.OPEN
    assert breaker.can_execute() is False
    assert breaker.last_error == "fail 3"


def test_circuit_breaker_transitions_to_half_open_and_recovers():
    now = 100.0
    breaker = CircuitBreaker("gasbuddy", failure_threshold=2, recovery_timeout=30.0, clock=lambda: now)

    breaker.record_failure(ProviderError("fail 1"))
    breaker.record_failure(ProviderError("fail 2"))
    assert breaker.state == CircuitState.OPEN
    assert breaker.can_execute() is False

    # Within cooldown
    now = 120.0
    assert breaker.can_execute() is False

    # After cooldown: enters HALF_OPEN
    now = 131.0
    assert breaker.can_execute() is True
    assert breaker.state == CircuitState.HALF_OPEN

    # Success in HALF_OPEN resets to CLOSED
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0
    assert breaker.can_execute() is True


def test_circuit_breaker_reopens_on_half_open_failure():
    now = 100.0
    breaker = CircuitBreaker("gasbuddy", failure_threshold=2, recovery_timeout=30.0, clock=lambda: now)

    breaker.record_failure(ProviderError("fail 1"))
    breaker.record_failure(ProviderError("fail 2"))
    assert breaker.state == CircuitState.OPEN

    now = 131.0
    assert breaker.can_execute() is True
    assert breaker.state == CircuitState.HALF_OPEN

    # Failure in HALF_OPEN immediately re-opens the breaker
    breaker.record_failure(ProviderError("probe failed"))
    assert breaker.state == CircuitState.OPEN
    assert breaker.can_execute() is False


def test_circuit_breaker_registry():
    registry = CircuitBreakerRegistry(failure_threshold=2, recovery_timeout=15.0)

    assert registry.can_execute("waze") is True
    registry.record_failure("waze", ProviderError("timeout"))
    registry.record_failure("waze", ProviderError("timeout"))
    assert registry.is_open("waze") is True
    assert registry.can_execute("waze") is False

    # Other providers are unaffected
    assert registry.can_execute("maps") is True
    assert registry.is_open("maps") is False

    # Clear resets all
    registry.clear()
    assert registry.can_execute("waze") is True
