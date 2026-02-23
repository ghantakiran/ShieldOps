"""Tests for shieldops.utils.circuit_breaker module.

Covers CircuitState enum, CircuitStats model, CircuitOpenError exception,
CircuitBreaker state machine, and CircuitBreakerRegistry.
"""

from __future__ import annotations

import asyncio

import pytest

from shieldops.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitOpenError,
    CircuitState,
    CircuitStats,
)

# ---------------------------------------------------------------------------
# CircuitState enum
# ---------------------------------------------------------------------------


class TestCircuitState:
    """Tests for the CircuitState StrEnum."""

    def test_closed_value(self) -> None:
        assert CircuitState.CLOSED == "closed"

    def test_open_value(self) -> None:
        assert CircuitState.OPEN == "open"

    def test_half_open_value(self) -> None:
        assert CircuitState.HALF_OPEN == "half_open"

    def test_all_members(self) -> None:
        members = set(CircuitState)
        assert members == {CircuitState.CLOSED, CircuitState.OPEN, CircuitState.HALF_OPEN}

    def test_is_str_subclass(self) -> None:
        assert isinstance(CircuitState.CLOSED, str)


# ---------------------------------------------------------------------------
# CircuitStats model
# ---------------------------------------------------------------------------


class TestCircuitStats:
    """Tests for the CircuitStats Pydantic model."""

    def test_defaults(self) -> None:
        stats = CircuitStats(name="test", state=CircuitState.CLOSED)
        assert stats.failure_count == 0
        assert stats.success_count == 0
        assert stats.total_calls == 0
        assert stats.last_failure_time is None
        assert stats.last_success_time is None
        assert stats.opened_at is None
        assert stats.half_open_calls == 0
        assert stats.failure_threshold == 5
        assert stats.reset_timeout_seconds == 30.0
        assert stats.half_open_max_calls == 3

    def test_custom_values(self) -> None:
        stats = CircuitStats(
            name="opa",
            state=CircuitState.OPEN,
            failure_count=10,
            success_count=200,
            total_calls=210,
            failure_threshold=8,
            reset_timeout_seconds=60.0,
            half_open_max_calls=5,
        )
        assert stats.name == "opa"
        assert stats.state == CircuitState.OPEN
        assert stats.failure_count == 10
        assert stats.failure_threshold == 8
        assert stats.reset_timeout_seconds == 60.0

    def test_model_serialization(self) -> None:
        stats = CircuitStats(name="db", state=CircuitState.CLOSED)
        data = stats.model_dump()
        assert data["name"] == "db"
        assert data["state"] == "closed"


# ---------------------------------------------------------------------------
# CircuitOpenError
# ---------------------------------------------------------------------------


class TestCircuitOpenError:
    """Tests for CircuitOpenError exception."""

    def test_attributes(self) -> None:
        err = CircuitOpenError("opa", retry_after=15.0)
        assert err.name == "opa"
        assert err.retry_after == 15.0

    def test_message_format(self) -> None:
        err = CircuitOpenError("redis", retry_after=5.5)
        assert "redis" in str(err)
        assert "OPEN" in str(err)
        assert "5.5s" in str(err)

    def test_default_retry_after(self) -> None:
        err = CircuitOpenError("kafka")
        assert err.retry_after == 0.0

    def test_is_exception(self) -> None:
        err = CircuitOpenError("x")
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# CircuitBreaker — initial state
# ---------------------------------------------------------------------------


class TestCircuitBreakerInit:
    """Tests for CircuitBreaker construction and initial state."""

    def test_starts_closed(self) -> None:
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_name(self) -> None:
        cb = CircuitBreaker("my-service")
        assert cb.name == "my-service"

    def test_default_thresholds(self) -> None:
        cb = CircuitBreaker("svc")
        assert cb.failure_threshold == 5
        assert cb.reset_timeout == 30.0
        assert cb.half_open_max_calls == 3

    def test_custom_thresholds(self) -> None:
        cb = CircuitBreaker("svc", failure_threshold=3, reset_timeout=10.0, half_open_max_calls=1)
        assert cb.failure_threshold == 3
        assert cb.reset_timeout == 10.0
        assert cb.half_open_max_calls == 1


# ---------------------------------------------------------------------------
# CircuitBreaker — CLOSED state behavior
# ---------------------------------------------------------------------------


class TestCircuitBreakerClosed:
    """Tests for CircuitBreaker in the CLOSED state."""

    @pytest.mark.asyncio
    async def test_successful_call_stays_closed(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3)
        async with cb.call():
            pass  # success
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_successful_call_increments_success_count(self) -> None:
        cb = CircuitBreaker("test")
        async with cb.call():
            pass
        assert cb.stats.success_count == 1

    @pytest.mark.asyncio
    async def test_successful_call_increments_total_calls(self) -> None:
        cb = CircuitBreaker("test")
        async with cb.call():
            pass
        assert cb.stats.total_calls == 1

    @pytest.mark.asyncio
    async def test_multiple_successes_stay_closed(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(10):
            async with cb.call():
                pass
        assert cb.state == CircuitState.CLOSED
        assert cb.stats.success_count == 10
        assert cb.stats.total_calls == 10

    @pytest.mark.asyncio
    async def test_success_sets_last_success_time(self) -> None:
        cb = CircuitBreaker("test")
        async with cb.call():
            pass
        assert cb.stats.last_success_time is not None

    @pytest.mark.asyncio
    async def test_failure_increments_failure_count(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=5)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("boom")
        assert cb.stats.failure_count == 1
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_sets_last_failure_time(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=5)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("boom")
        assert cb.stats.last_failure_time is not None

    @pytest.mark.asyncio
    async def test_failure_propagates_original_exception(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=5)
        with pytest.raises(RuntimeError, match="specific"):
            async with cb.call():
                raise RuntimeError("specific error")

    @pytest.mark.asyncio
    async def test_failures_below_threshold_stay_closed(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=5)
        for _ in range(4):
            with pytest.raises(ValueError):
                async with cb.call():
                    raise ValueError("fail")
        assert cb.state == CircuitState.CLOSED
        assert cb.stats.failure_count == 4


# ---------------------------------------------------------------------------
# CircuitBreaker — CLOSED -> OPEN transition
# ---------------------------------------------------------------------------


class TestCircuitBreakerTripping:
    """Tests for the CLOSED -> OPEN transition when failures reach threshold."""

    @pytest.mark.asyncio
    async def test_opens_at_threshold(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            with pytest.raises(ValueError):
                async with cb.call():
                    raise ValueError("fail")
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_opens_at_exact_threshold(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_opened_at_is_set(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        assert cb.stats.opened_at is not None


# ---------------------------------------------------------------------------
# CircuitBreaker — OPEN state behavior
# ---------------------------------------------------------------------------


class TestCircuitBreakerOpen:
    """Tests for the CircuitBreaker in OPEN state."""

    @pytest.fixture
    async def open_breaker(self) -> CircuitBreaker:
        """Create a breaker that is already OPEN."""
        cb = CircuitBreaker("test", failure_threshold=2, reset_timeout=60.0)
        for _ in range(2):
            with pytest.raises(ValueError):
                async with cb.call():
                    raise ValueError("fail")
        assert cb.state == CircuitState.OPEN
        return cb

    @pytest.mark.asyncio
    async def test_open_raises_circuit_open_error(self, open_breaker: CircuitBreaker) -> None:
        with pytest.raises(CircuitOpenError):
            async with open_breaker.call():
                pass  # should not reach here

    @pytest.mark.asyncio
    async def test_open_error_has_name(self, open_breaker: CircuitBreaker) -> None:
        with pytest.raises(CircuitOpenError) as exc_info:
            async with open_breaker.call():
                pass
        assert exc_info.value.name == "test"

    @pytest.mark.asyncio
    async def test_open_error_has_positive_retry_after(self, open_breaker: CircuitBreaker) -> None:
        with pytest.raises(CircuitOpenError) as exc_info:
            async with open_breaker.call():
                pass
        assert exc_info.value.retry_after > 0.0

    @pytest.mark.asyncio
    async def test_open_does_not_increment_total_calls(self, open_breaker: CircuitBreaker) -> None:
        calls_before = open_breaker.stats.total_calls
        with pytest.raises(CircuitOpenError):
            async with open_breaker.call():
                pass
        assert open_breaker.stats.total_calls == calls_before


# ---------------------------------------------------------------------------
# CircuitBreaker — OPEN -> HALF_OPEN transition (timeout)
# ---------------------------------------------------------------------------


class TestCircuitBreakerHalfOpenTransition:
    """Tests for the OPEN -> HALF_OPEN transition via reset timeout."""

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.1)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_state_property_reflects_timeout_transition(self) -> None:
        """The .state property should dynamically detect the timeout."""
        cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.05)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")

        # _state is still OPEN internally, but .state accounts for timeout
        await asyncio.sleep(0.1)
        assert cb._state == CircuitState.OPEN  # internal raw state
        assert cb.state == CircuitState.HALF_OPEN  # computed state


# ---------------------------------------------------------------------------
# CircuitBreaker — HALF_OPEN state behavior
# ---------------------------------------------------------------------------


class TestCircuitBreakerHalfOpen:
    """Tests for the CircuitBreaker in HALF_OPEN state."""

    @pytest.fixture
    async def half_open_breaker(self) -> CircuitBreaker:
        """Create a breaker that is in HALF_OPEN state."""
        cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.05, half_open_max_calls=2)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        await asyncio.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN
        return cb

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(
        self, half_open_breaker: CircuitBreaker
    ) -> None:
        async with half_open_breaker.call():
            pass  # success
        assert half_open_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_success_resets_failure_count(
        self, half_open_breaker: CircuitBreaker
    ) -> None:
        async with half_open_breaker.call():
            pass
        assert half_open_breaker.stats.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(
        self, half_open_breaker: CircuitBreaker
    ) -> None:
        with pytest.raises(RuntimeError):
            async with half_open_breaker.call():
                raise RuntimeError("fail again")
        assert half_open_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_max_calls_exceeded(self) -> None:
        """Exceeding max calls in HALF_OPEN raises CircuitOpenError."""
        cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.05, half_open_max_calls=1)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        await asyncio.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        # First half-open call — allowed (succeeds, which closes circuit)
        # We need to test the limit path, so we use a different approach:
        # Open the breaker, wait for half-open, then exhaust the call budget
        cb2 = CircuitBreaker(
            "test2", failure_threshold=1, reset_timeout=0.05, half_open_max_calls=1
        )
        # Trip the breaker
        with pytest.raises(ValueError):
            async with cb2.call():
                raise ValueError("trip")
        await asyncio.sleep(0.1)
        assert cb2.state == CircuitState.HALF_OPEN

        # Simulate the half_open_calls counter reaching the limit by directly setting it
        cb2._half_open_calls = 1
        with pytest.raises(CircuitOpenError):
            async with cb2.call():
                pass

    @pytest.mark.asyncio
    async def test_half_open_increments_half_open_calls(
        self, half_open_breaker: CircuitBreaker
    ) -> None:
        """Each call in HALF_OPEN should increment the half_open_calls counter."""
        assert half_open_breaker.stats.half_open_calls == 0
        # The call will succeed and close the circuit, but the counter should have been
        # incremented during the call.
        async with half_open_breaker.call():
            # Inside the context manager, _half_open_calls should be incremented
            assert half_open_breaker._half_open_calls == 1


# ---------------------------------------------------------------------------
# CircuitBreaker — force reset
# ---------------------------------------------------------------------------


class TestCircuitBreakerReset:
    """Tests for CircuitBreaker.reset()."""

    @pytest.mark.asyncio
    async def test_reset_from_open(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        assert cb.state == CircuitState.OPEN

        await cb.reset()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reset_clears_failure_count(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=5)
        for _ in range(3):
            with pytest.raises(ValueError):
                async with cb.call():
                    raise ValueError("fail")
        assert cb.stats.failure_count == 3

        await cb.reset()
        assert cb.stats.failure_count == 0

    @pytest.mark.asyncio
    async def test_reset_clears_opened_at(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        assert cb.stats.opened_at is not None

        await cb.reset()
        assert cb.stats.opened_at is None

    @pytest.mark.asyncio
    async def test_reset_clears_half_open_calls(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.05)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        await asyncio.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        await cb.reset()
        assert cb.stats.half_open_calls == 0
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reset_on_already_closed_is_safe(self) -> None:
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        await cb.reset()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reset_allows_calls_again(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        assert cb.state == CircuitState.OPEN

        await cb.reset()
        async with cb.call():
            pass  # Should succeed without CircuitOpenError
        assert cb.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# CircuitBreaker — stats property
# ---------------------------------------------------------------------------


class TestCircuitBreakerStats:
    """Tests for the CircuitBreaker.stats property."""

    def test_stats_returns_circuit_stats_model(self) -> None:
        cb = CircuitBreaker("svc")
        stats = cb.stats
        assert isinstance(stats, CircuitStats)

    def test_stats_name_matches(self) -> None:
        cb = CircuitBreaker("my-svc")
        assert cb.stats.name == "my-svc"

    def test_stats_reflects_config(self) -> None:
        cb = CircuitBreaker("svc", failure_threshold=7, reset_timeout=15.0, half_open_max_calls=2)
        stats = cb.stats
        assert stats.failure_threshold == 7
        assert stats.reset_timeout_seconds == 15.0
        assert stats.half_open_max_calls == 2

    @pytest.mark.asyncio
    async def test_stats_reflect_state_changes(self) -> None:
        cb = CircuitBreaker("svc", failure_threshold=1)
        assert cb.stats.state == CircuitState.CLOSED

        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        assert cb.stats.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# CircuitBreakerRegistry
# ---------------------------------------------------------------------------


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry."""

    def test_register_returns_breaker(self) -> None:
        reg = CircuitBreakerRegistry()
        cb = reg.register("opa")
        assert isinstance(cb, CircuitBreaker)
        assert cb.name == "opa"

    def test_register_same_name_returns_same_instance(self) -> None:
        reg = CircuitBreakerRegistry()
        cb1 = reg.register("opa")
        cb2 = reg.register("opa")
        assert cb1 is cb2

    def test_register_different_names(self) -> None:
        reg = CircuitBreakerRegistry()
        cb1 = reg.register("opa")
        cb2 = reg.register("redis")
        assert cb1 is not cb2
        assert cb1.name == "opa"
        assert cb2.name == "redis"

    def test_register_with_custom_params(self) -> None:
        reg = CircuitBreakerRegistry()
        cb = reg.register("db", failure_threshold=10, reset_timeout=60.0, half_open_max_calls=5)
        assert cb.failure_threshold == 10
        assert cb.reset_timeout == 60.0
        assert cb.half_open_max_calls == 5

    def test_get_existing(self) -> None:
        reg = CircuitBreakerRegistry()
        registered = reg.register("opa")
        retrieved = reg.get("opa")
        assert retrieved is registered

    def test_get_nonexistent(self) -> None:
        reg = CircuitBreakerRegistry()
        assert reg.get("nonexistent") is None

    def test_names_empty(self) -> None:
        reg = CircuitBreakerRegistry()
        assert reg.names == []

    def test_names_populated(self) -> None:
        reg = CircuitBreakerRegistry()
        reg.register("opa")
        reg.register("redis")
        reg.register("kafka")
        assert sorted(reg.names) == ["kafka", "opa", "redis"]

    def test_all_stats_empty(self) -> None:
        reg = CircuitBreakerRegistry()
        assert reg.all_stats() == []

    def test_all_stats_returns_list_of_circuit_stats(self) -> None:
        reg = CircuitBreakerRegistry()
        reg.register("opa")
        reg.register("redis")
        stats = reg.all_stats()
        assert len(stats) == 2
        assert all(isinstance(s, CircuitStats) for s in stats)
        names = {s.name for s in stats}
        assert names == {"opa", "redis"}

    @pytest.mark.asyncio
    async def test_reset_existing(self) -> None:
        reg = CircuitBreakerRegistry()
        cb = reg.register("opa", failure_threshold=1)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        assert cb.state == CircuitState.OPEN

        result = await reg.reset("opa")
        assert result is True
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reset_nonexistent(self) -> None:
        reg = CircuitBreakerRegistry()
        result = await reg.reset("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_reset_all(self) -> None:
        reg = CircuitBreakerRegistry()
        cb1 = reg.register("a", failure_threshold=1)
        cb2 = reg.register("b", failure_threshold=1)

        with pytest.raises(ValueError):
            async with cb1.call():
                raise ValueError("fail")
        with pytest.raises(ValueError):
            async with cb2.call():
                raise ValueError("fail")
        assert cb1.state == CircuitState.OPEN
        assert cb2.state == CircuitState.OPEN

        await reg.reset_all()
        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reset_all_on_empty_registry(self) -> None:
        reg = CircuitBreakerRegistry()
        await reg.reset_all()  # Should not raise


# ---------------------------------------------------------------------------
# Edge cases and integration-like tests
# ---------------------------------------------------------------------------


class TestCircuitBreakerEdgeCases:
    """Edge-case and behavioral tests."""

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self) -> None:
        """Successes do not decrement failure count in CLOSED state."""
        cb = CircuitBreaker("test", failure_threshold=5)
        # 3 failures
        for _ in range(3):
            with pytest.raises(ValueError):
                async with cb.call():
                    raise ValueError("fail")
        # 2 successes
        for _ in range(2):
            async with cb.call():
                pass
        # Failure count should still be 3 (successes don't reset in CLOSED)
        assert cb.stats.failure_count == 3
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_threshold_exactly_met_with_interleaved_successes(self) -> None:
        """Interleaved successes should not prevent tripping at threshold."""
        cb = CircuitBreaker("test", failure_threshold=3)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail 1")
        async with cb.call():
            pass  # success
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail 2")
        async with cb.call():
            pass  # success
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail 3")
        # 3 failures total should trip the breaker
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_rapid_calls_after_trip(self) -> None:
        """Multiple calls to an open breaker all raise CircuitOpenError."""
        cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=60.0)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        for _ in range(5):
            with pytest.raises(CircuitOpenError):
                async with cb.call():
                    pass

    @pytest.mark.asyncio
    async def test_failure_threshold_of_one(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("single failure")
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_large_failure_threshold(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=100)
        for i in range(99):
            with pytest.raises(ValueError):
                async with cb.call():
                    raise ValueError(f"fail {i}")
        assert cb.state == CircuitState.CLOSED
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail 100")
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_zero_reset_timeout_immediate_half_open(self) -> None:
        """With reset_timeout=0, breaker should immediately go to HALF_OPEN."""
        cb = CircuitBreaker("test", failure_threshold=1, reset_timeout=0.0)
        with pytest.raises(ValueError):
            async with cb.call():
                raise ValueError("fail")
        # With a 0s timeout, state property should show HALF_OPEN immediately
        assert cb.state == CircuitState.HALF_OPEN
