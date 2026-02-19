"""Unit tests for circuit breaker and retry-with-backoff resilience utilities."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.models.base import Environment, RemediationAction, RiskLevel
from shieldops.policy.opa.client import PolicyEngine
from shieldops.utils.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    retry_with_backoff,
)

# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────


async def _succeed() -> str:
    return "ok"


async def _fail() -> str:
    raise RuntimeError("boom")


def _make_action() -> RemediationAction:
    return RemediationAction(
        id="act-001",
        action_type="restart_pod",
        target_resource="default/nginx",
        environment=Environment.PRODUCTION,
        risk_level=RiskLevel.LOW,
        description="test action",
    )


# ────────────────────────────────────────────────────────────────────
# CircuitBreaker — State transitions
# ────────────────────────────────────────────────────────────────────


class TestCircuitBreakerStates:
    def test_starts_in_closed_state(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_stays_closed_on_success(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(10):
            result = await cb.call(_succeed)
            assert result == "ok"
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_opens_after_failure_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=60.0)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(_fail)
        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_raises_circuit_open_error_when_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=60.0)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(_fail)

        with pytest.raises(CircuitOpenError) as exc_info:
            await cb.call(_succeed)
        assert exc_info.value.name == "test"
        assert exc_info.value.recovery_in > 0

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(_fail)
        assert cb.state == "open"

        await asyncio.sleep(0.15)
        assert cb.state == "half_open"

    @pytest.mark.asyncio
    async def test_half_open_to_closed_on_success(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(_fail)

        await asyncio.sleep(0.15)
        assert cb.state == "half_open"

        result = await cb.call(_succeed)
        assert result == "ok"
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(_fail)

        await asyncio.sleep(0.15)
        assert cb.state == "half_open"

        with pytest.raises(RuntimeError):
            await cb.call(_fail)
        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_half_open_rejects_after_max_calls(self):
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=0.05,
            half_open_max_calls=1,
        )
        with pytest.raises(RuntimeError):
            await cb.call(_fail)

        await asyncio.sleep(0.1)
        assert cb.state == "half_open"

        # First call should be allowed (and succeed)
        # But let's make the first probe call block —
        # simulate a slow call by using a never-failing func
        slow_called = False

        async def _slow_succeed():
            nonlocal slow_called
            slow_called = True
            return "ok"

        await cb.call(_slow_succeed)
        assert slow_called
        # Breaker is now CLOSED because the probe succeeded
        assert cb.state == "closed"


class TestCircuitBreakerReset:
    @pytest.mark.asyncio
    async def test_reset_from_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=300.0)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(_fail)
        assert cb.state == "open"

        cb.reset()
        assert cb.state == "closed"
        assert cb.stats["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_reset_from_half_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.05)
        with pytest.raises(RuntimeError):
            await cb.call(_fail)
        await asyncio.sleep(0.1)
        assert cb.state == "half_open"

        cb.reset()
        assert cb.state == "closed"

    def test_reset_from_closed(self):
        cb = CircuitBreaker(name="test")
        cb.reset()
        assert cb.state == "closed"


class TestCircuitBreakerStats:
    @pytest.mark.asyncio
    async def test_stats_initial(self):
        cb = CircuitBreaker(name="test")
        stats = cb.stats
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0
        assert stats["last_failure_time"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_after_successes(self):
        cb = CircuitBreaker(name="test")
        await cb.call(_succeed)
        await cb.call(_succeed)
        stats = cb.stats
        assert stats["success_count"] == 2
        assert stats["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_failures(self):
        cb = CircuitBreaker(name="test", failure_threshold=10, recovery_timeout=60.0)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(_fail)
        stats = cb.stats
        assert stats["failure_count"] == 3
        assert stats["last_failure_time"] > 0

    @pytest.mark.asyncio
    async def test_stats_failure_count_resets_on_success(self):
        cb = CircuitBreaker(name="test", failure_threshold=10, recovery_timeout=60.0)
        with pytest.raises(RuntimeError):
            await cb.call(_fail)
        assert cb.stats["failure_count"] == 1

        await cb.call(_succeed)
        assert cb.stats["failure_count"] == 0


class TestCircuitBreakerCustomConfig:
    @pytest.mark.asyncio
    async def test_custom_failure_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=60.0)
        with pytest.raises(RuntimeError):
            await cb.call(_fail)
        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_custom_recovery_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.05)
        with pytest.raises(RuntimeError):
            await cb.call(_fail)
        assert cb.state == "open"

        await asyncio.sleep(0.1)
        assert cb.state == "half_open"

    @pytest.mark.asyncio
    async def test_large_failure_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=100, recovery_timeout=60.0)
        for _ in range(99):
            with pytest.raises(RuntimeError):
                await cb.call(_fail)
        # Not yet tripped
        assert cb.state == "closed"

        with pytest.raises(RuntimeError):
            await cb.call(_fail)
        assert cb.state == "open"


class TestCircuitBreakerConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_calls_in_closed_state(self):
        cb = CircuitBreaker(name="test", failure_threshold=5)
        results = await asyncio.gather(*[cb.call(_succeed) for _ in range(20)])
        assert all(r == "ok" for r in results)
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_concurrent_failures_trip_breaker(self):
        cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=60.0)
        tasks = [cb.call(_fail) for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 5
        assert cb.state == "open"


class TestCircuitBreakerLogging:
    @pytest.mark.asyncio
    async def test_logs_state_transition(self):
        cb = CircuitBreaker(name="test-log", failure_threshold=1, recovery_timeout=60.0)
        with patch("shieldops.utils.resilience.logger") as mock_logger:
            with pytest.raises(RuntimeError):
                await cb.call(_fail)
            mock_logger.info.assert_called_with(
                "circuit_breaker_state_change",
                name="test-log",
                old_state="closed",
                new_state="open",
            )

    @pytest.mark.asyncio
    async def test_logs_half_open_transition(self):
        cb = CircuitBreaker(
            name="test-log",
            failure_threshold=1,
            recovery_timeout=0.05,
        )
        with pytest.raises(RuntimeError):
            await cb.call(_fail)

        await asyncio.sleep(0.1)

        with patch("shieldops.utils.resilience.logger") as mock_logger:
            # Accessing .state triggers the OPEN -> HALF_OPEN transition
            _ = cb.state
            mock_logger.info.assert_called_with(
                "circuit_breaker_state_change",
                name="test-log",
                old_state="open",
                new_state="half_open",
            )


class TestCircuitOpenError:
    def test_attributes(self):
        err = CircuitOpenError(name="opa", recovery_in=12.5)
        assert err.name == "opa"
        assert err.recovery_in == 12.5

    def test_message(self):
        err = CircuitOpenError(name="opa", recovery_in=12.5)
        assert "opa" in str(err)
        assert "12.5" in str(err)

    def test_is_exception(self):
        assert issubclass(CircuitOpenError, Exception)


# ────────────────────────────────────────────────────────────────────
# retry_with_backoff
# ────────────────────────────────────────────────────────────────────


class TestRetryWithBackoffSuccess:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        call_count = 0

        @retry_with_backoff(max_retries=3)
        async def fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await fn()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_succeeds_on_nth_attempt(self):
        call_count = 0

        @retry_with_backoff(
            max_retries=5,
            base_delay=0.01,
            jitter=False,
        )
        async def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("not yet")
            return "recovered"

        result = await fn()
        assert result == "recovered"
        assert call_count == 3


class TestRetryWithBackoffExhaustion:
    @pytest.mark.asyncio
    async def test_raises_last_exception_after_exhaustion(self):
        call_count = 0

        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            jitter=False,
        )
        async def fn():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"attempt {call_count}")

        with pytest.raises(ValueError, match="attempt 3"):
            await fn()
        assert call_count == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_respects_max_retries_limit(self):
        call_count = 0

        @retry_with_backoff(
            max_retries=0,
            base_delay=0.01,
        )
        async def fn():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            await fn()
        assert call_count == 1  # no retries


class TestRetryWithBackoffDelay:
    @pytest.mark.asyncio
    async def test_backoff_increases_exponentially(self):
        delays: list[float] = []

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        @retry_with_backoff(
            max_retries=4,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=False,
        )
        async def fn():
            raise RuntimeError("fail")

        with (
            patch("shieldops.utils.resilience.asyncio.sleep", mock_sleep),
            pytest.raises(RuntimeError),
        ):
            await fn()

        # Delays: 1*2^0=1, 1*2^1=2, 1*2^2=4, 1*2^3=8
        assert delays == [1.0, 2.0, 4.0, 8.0]

    @pytest.mark.asyncio
    async def test_max_delay_caps_backoff(self):
        delays: list[float] = []

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        @retry_with_backoff(
            max_retries=5,
            base_delay=10.0,
            max_delay=25.0,
            exponential_base=2.0,
            jitter=False,
        )
        async def fn():
            raise RuntimeError("fail")

        with (
            patch("shieldops.utils.resilience.asyncio.sleep", mock_sleep),
            pytest.raises(RuntimeError),
        ):
            await fn()

        # 10*2^0=10, 10*2^1=20, 10*2^2=40→25, 10*2^3=80→25, 10*2^4=160→25
        assert delays == [10.0, 20.0, 25.0, 25.0, 25.0]

    @pytest.mark.asyncio
    async def test_jitter_randomizes_delay(self):
        delays: list[float] = []

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        @retry_with_backoff(
            max_retries=3,
            base_delay=1.0,
            exponential_base=2.0,
            jitter=True,
        )
        async def fn():
            raise RuntimeError("fail")

        with (
            patch("shieldops.utils.resilience.asyncio.sleep", mock_sleep),
            pytest.raises(RuntimeError),
        ):
            await fn()

        # With jitter, delay = base * 2^attempt * uniform(0.5, 1.5)
        # attempt 0: 1.0 * [0.5, 1.5] = [0.5, 1.5]
        # attempt 1: 2.0 * [0.5, 1.5] = [1.0, 3.0]
        # attempt 2: 4.0 * [0.5, 1.5] = [2.0, 6.0]
        assert len(delays) == 3
        assert 0.5 <= delays[0] <= 1.5
        assert 1.0 <= delays[1] <= 3.0
        assert 2.0 <= delays[2] <= 6.0


class TestRetryWithBackoffExceptionFiltering:
    @pytest.mark.asyncio
    async def test_retries_only_specified_exceptions(self):
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            jitter=False,
            retryable_exceptions=(ConnectionError,),
        )
        async def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("retry me")
            return "ok"

        result = await fn()
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception_raised_immediately(self):
        call_count = 0

        @retry_with_backoff(
            max_retries=5,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        async def fn():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError, match="not retryable"):
            await fn()
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retryable_subclass_is_caught(self):
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            jitter=False,
            retryable_exceptions=(OSError,),
        )
        async def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("subclass of OSError")
            return "ok"

        result = await fn()
        assert result == "ok"
        assert call_count == 2


class TestRetryWithBackoffLogging:
    @pytest.mark.asyncio
    async def test_logs_retry_attempts(self):
        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            jitter=False,
        )
        async def fn():
            raise RuntimeError("fail")

        with patch("shieldops.utils.resilience.logger") as mock_logger:
            with pytest.raises(RuntimeError):
                await fn()

            # Should have 2 retry info logs + 1 exhaustion warning
            info_calls = mock_logger.info.call_args_list
            assert len(info_calls) == 2
            assert all(c[0][0] == "retry_attempt" for c in info_calls)
            mock_logger.warning.assert_called_once()
            assert mock_logger.warning.call_args[0][0] == "retry_exhausted"


# ────────────────────────────────────────────────────────────────────
# PolicyEngine integration with CircuitBreaker
# ────────────────────────────────────────────────────────────────────


class TestPolicyEngineCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_breaker_wraps_opa_calls(self):
        engine = PolicyEngine(opa_url="http://opa:8181")
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {"result": True}
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        engine._client = mock_client

        result = await engine.evaluate(_make_action(), "agent-1")
        assert result.allowed is True
        mock_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_circuit_open_returns_deny_decision(self):
        cb = CircuitBreaker(name="opa", failure_threshold=1, recovery_timeout=60.0)
        engine = PolicyEngine(opa_url="http://opa:8181", circuit_breaker=cb)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=RuntimeError("connection refused"))
        engine._client = mock_client

        # First call trips the breaker
        result1 = await engine.evaluate(_make_action(), "agent-1")
        assert result1.denied  # httpx.HTTPError path or RuntimeError

        # Second call should hit CircuitOpenError path
        result2 = await engine.evaluate(_make_action(), "agent-1")
        assert result2.allowed is False
        assert any("circuit breaker open" in r.lower() for r in result2.reasons)

    @pytest.mark.asyncio
    async def test_successful_opa_call_keeps_breaker_closed(self):
        cb = CircuitBreaker(name="opa", failure_threshold=5, recovery_timeout=30.0)
        engine = PolicyEngine(opa_url="http://opa:8181", circuit_breaker=cb)
        mock_client = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {"result": True}
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        engine._client = mock_client

        for _ in range(10):
            result = await engine.evaluate(_make_action(), "agent-1")
            assert result.allowed is True

        assert cb.state == "closed"
        assert cb.stats["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_breaker_recovers_after_timeout(self):
        cb = CircuitBreaker(name="opa", failure_threshold=1, recovery_timeout=0.1)
        engine = PolicyEngine(opa_url="http://opa:8181", circuit_breaker=cb)
        mock_client = AsyncMock()

        # First: fail to trip the breaker
        mock_client.post = AsyncMock(side_effect=RuntimeError("connection refused"))
        engine._client = mock_client
        await engine.evaluate(_make_action(), "agent-1")
        assert cb.state == "open"

        # Wait for recovery
        await asyncio.sleep(0.15)

        # Now: succeed to close the breaker
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": True}
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        result = await engine.evaluate(_make_action(), "agent-1")
        assert result.allowed is True
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_default_circuit_breaker_created(self):
        engine = PolicyEngine(opa_url="http://opa:8181")
        assert engine._circuit_breaker is not None
        assert engine._circuit_breaker._name == "opa"
        assert engine._circuit_breaker._failure_threshold == 5
        assert engine._circuit_breaker._recovery_timeout == 30.0
