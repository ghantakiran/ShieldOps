"""Comprehensive tests for the EscalationEngine.

Covers:
- Policy CRUD: register, get, delete, list, update
- Execution: first step succeeds, first fails / second succeeds, all fail
- Retry logic within a step (retry_count, retry_delay_seconds)
- Timeout enforcement (max_duration_seconds)
- Disabled policy returns delivered=False
- Missing policy returns delivered=False
- execute_for_severity() matches severity_filter
- test_policy() dry-run execution
- History tracking and get_stats()
- No dispatcher configured raises error in attempts
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock

import pytest

from shieldops.integrations.notifications.escalation import (
    EscalationEngine,
    EscalationPolicy,
    EscalationResult,
    EscalationStep,
)

# =========================================================================
# Helpers
# =========================================================================


def _make_step(
    channel: str = "slack",
    delay_seconds: int = 0,
    retry_count: int = 0,
    retry_delay_seconds: int = 0,
    condition: str = "",
) -> EscalationStep:
    return EscalationStep(
        channel=channel,
        delay_seconds=delay_seconds,
        retry_count=retry_count,
        retry_delay_seconds=retry_delay_seconds,
        condition=condition,
    )


def _make_policy(
    name: str = "default",
    steps: list[EscalationStep] | None = None,
    max_duration_seconds: int = 300,
    severity_filter: list[str] | None = None,
    enabled: bool = True,
) -> EscalationPolicy:
    return EscalationPolicy(
        name=name,
        description=f"Test policy {name}",
        steps=[_make_step()] if steps is None else steps,
        max_duration_seconds=max_duration_seconds,
        severity_filter=severity_filter if severity_filter is not None else [],
        enabled=enabled,
    )


def _make_dispatcher(
    side_effect: Any = None,
    return_value: bool = True,
) -> AsyncMock:
    """Return a mock dispatcher whose .send() returns or raises per config."""
    dispatcher = AsyncMock()
    if side_effect is not None:
        dispatcher.send = AsyncMock(side_effect=side_effect)
    else:
        dispatcher.send = AsyncMock(return_value=return_value)
    return dispatcher


# =========================================================================
# Policy CRUD
# =========================================================================


class TestPolicyCRUD:
    """Tests for register / get / delete / list / update."""

    def test_register_policy(self) -> None:
        engine = EscalationEngine()
        policy = _make_policy(name="p1")
        result = engine.register_policy(policy)
        assert result.name == "p1"
        assert engine.get_policy("p1") is not None

    def test_register_overwrites_existing(self) -> None:
        engine = EscalationEngine()
        engine.register_policy(_make_policy(name="p1"))
        replacement = _make_policy(name="p1", max_duration_seconds=999)
        engine.register_policy(replacement)
        assert engine.get_policy("p1") is not None
        assert engine.get_policy("p1").max_duration_seconds == 999

    def test_get_policy_missing(self) -> None:
        engine = EscalationEngine()
        assert engine.get_policy("nonexistent") is None

    def test_delete_policy_existing(self) -> None:
        engine = EscalationEngine()
        engine.register_policy(_make_policy(name="p1"))
        assert engine.delete_policy("p1") is True
        assert engine.get_policy("p1") is None

    def test_delete_policy_missing(self) -> None:
        engine = EscalationEngine()
        assert engine.delete_policy("nonexistent") is False

    def test_list_policies_empty(self) -> None:
        engine = EscalationEngine()
        assert engine.list_policies() == []

    def test_list_policies_multiple(self) -> None:
        engine = EscalationEngine()
        engine.register_policy(_make_policy(name="a"))
        engine.register_policy(_make_policy(name="b"))
        names = {p.name for p in engine.list_policies()}
        assert names == {"a", "b"}

    def test_update_policy_fields(self) -> None:
        engine = EscalationEngine()
        engine.register_policy(_make_policy(name="p1"))
        updated = engine.update_policy("p1", {"description": "new desc", "enabled": False})
        assert updated is not None
        assert updated.description == "new desc"
        assert updated.enabled is False

    def test_update_policy_ignores_name_field(self) -> None:
        engine = EscalationEngine()
        engine.register_policy(_make_policy(name="p1"))
        updated = engine.update_policy("p1", {"name": "renamed"})
        assert updated is not None
        assert updated.name == "p1"  # unchanged

    def test_update_policy_missing(self) -> None:
        engine = EscalationEngine()
        assert engine.update_policy("missing", {"enabled": False}) is None

    def test_update_policy_updates_timestamp(self) -> None:
        engine = EscalationEngine()
        policy = _make_policy(name="p1")
        engine.register_policy(policy)
        before = policy.updated_at
        engine.update_policy("p1", {"description": "changed"})
        assert engine.get_policy("p1").updated_at >= before

    def test_register_policy_updates_timestamp(self) -> None:
        engine = EscalationEngine()
        policy = _make_policy(name="p1")
        old_ts = policy.updated_at
        engine.register_policy(policy)
        assert policy.updated_at >= old_ts


# =========================================================================
# Execution — happy path
# =========================================================================


class TestExecuteHappyPath:
    """First step succeeds immediately."""

    @pytest.mark.asyncio
    async def test_first_step_succeeds(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1"))
        result = await engine.execute("p1", message="alert!")
        assert result.delivered is True
        assert result.escalated is False
        assert result.channel_used == "slack"
        assert len(result.attempts) == 1
        assert result.attempts[0].success is True

    @pytest.mark.asyncio
    async def test_result_has_duration(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1"))
        result = await engine.execute("p1", message="alert!")
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_result_has_execution_id(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1"))
        result = await engine.execute("p1", message="alert!")
        assert result.execution_id != ""

    @pytest.mark.asyncio
    async def test_dispatcher_receives_correct_args(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1"))
        await engine.execute("p1", message="test msg", severity="critical", details={"key": "val"})
        dispatcher.send.assert_called_once_with(
            channel="slack",
            message="test msg",
            severity="critical",
            details={"key": "val"},
        )


# =========================================================================
# Execution — escalation (first fails, second succeeds)
# =========================================================================


class TestExecuteEscalation:
    """First step fails, second step succeeds => delivered=True, escalated=True."""

    @pytest.mark.asyncio
    async def test_escalation_on_first_failure(self) -> None:
        dispatcher = _make_dispatcher(side_effect=[False, True])
        engine = EscalationEngine(dispatcher=dispatcher)
        steps = [_make_step(channel="slack"), _make_step(channel="pagerduty")]
        engine.register_policy(_make_policy(name="p1", steps=steps))
        result = await engine.execute("p1", message="alert!")
        assert result.delivered is True
        assert result.escalated is True
        assert result.channel_used == "pagerduty"

    @pytest.mark.asyncio
    async def test_escalation_records_all_attempts(self) -> None:
        dispatcher = _make_dispatcher(side_effect=[False, True])
        engine = EscalationEngine(dispatcher=dispatcher)
        steps = [_make_step(channel="slack"), _make_step(channel="email")]
        engine.register_policy(_make_policy(name="p1", steps=steps))
        result = await engine.execute("p1", message="alert!")
        assert len(result.attempts) == 2
        assert result.attempts[0].success is False
        assert result.attempts[0].channel == "slack"
        assert result.attempts[1].success is True
        assert result.attempts[1].channel == "email"


# =========================================================================
# Execution — all steps fail
# =========================================================================


class TestExecuteAllFail:
    """Every step fails => delivered=False."""

    @pytest.mark.asyncio
    async def test_all_steps_fail(self) -> None:
        dispatcher = _make_dispatcher(side_effect=[False, False])
        engine = EscalationEngine(dispatcher=dispatcher)
        steps = [_make_step(channel="slack"), _make_step(channel="email")]
        engine.register_policy(_make_policy(name="p1", steps=steps))
        result = await engine.execute("p1", message="alert!")
        assert result.delivered is False

    @pytest.mark.asyncio
    async def test_all_steps_fail_attempts_count(self) -> None:
        dispatcher = _make_dispatcher(side_effect=[False, False, False])
        engine = EscalationEngine(dispatcher=dispatcher)
        steps = [
            _make_step(channel="a"),
            _make_step(channel="b"),
            _make_step(channel="c"),
        ]
        engine.register_policy(_make_policy(name="p1", steps=steps))
        result = await engine.execute("p1", message="alert!")
        assert result.delivered is False
        assert len(result.attempts) == 3


# =========================================================================
# Retry logic
# =========================================================================


class TestRetryWithinStep:
    """Retry on a single step before moving on."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self) -> None:
        dispatcher = _make_dispatcher(side_effect=[False, True])
        engine = EscalationEngine(dispatcher=dispatcher)
        step = _make_step(channel="slack", retry_count=2, retry_delay_seconds=0)
        engine.register_policy(_make_policy(name="p1", steps=[step]))
        result = await engine.execute("p1", message="alert!")
        assert result.delivered is True
        assert result.escalated is False  # still first step
        assert len(result.attempts) == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self) -> None:
        dispatcher = _make_dispatcher(side_effect=[False, False, False])
        engine = EscalationEngine(dispatcher=dispatcher, max_retries=3)
        step = _make_step(channel="slack", retry_count=2, retry_delay_seconds=0)
        engine.register_policy(_make_policy(name="p1", steps=[step]))
        result = await engine.execute("p1", message="alert!")
        assert result.delivered is False
        # retry_count=2 means 2+1=3 attempts total (capped by max_retries=3)
        assert len(result.attempts) == 3

    @pytest.mark.asyncio
    async def test_retry_count_capped_by_max_retries(self) -> None:
        """Step retry_count > engine max_retries => capped."""
        dispatcher = _make_dispatcher(return_value=False)
        engine = EscalationEngine(dispatcher=dispatcher, max_retries=1)
        step = _make_step(channel="slack", retry_count=10, retry_delay_seconds=0)
        engine.register_policy(_make_policy(name="p1", steps=[step]))
        result = await engine.execute("p1", message="alert!")
        # min(10, 1) = 1 retry, so 2 attempts total
        assert len(result.attempts) == 2

    @pytest.mark.asyncio
    async def test_retry_with_exception(self) -> None:
        """Exception during send is captured as a failed attempt."""
        dispatcher = _make_dispatcher(side_effect=RuntimeError("boom"))
        engine = EscalationEngine(dispatcher=dispatcher)
        step = _make_step(channel="slack", retry_count=1, retry_delay_seconds=0)
        engine.register_policy(_make_policy(name="p1", steps=[step]))
        result = await engine.execute("p1", message="alert!")
        assert result.delivered is False
        assert any("boom" in a.error for a in result.attempts)


# =========================================================================
# Timeout enforcement
# =========================================================================


class TestTimeout:
    """max_duration_seconds stops execution early."""

    @pytest.mark.asyncio
    async def test_timeout_stops_iteration(self) -> None:
        """When elapsed time exceeds the timeout, further steps are skipped.

        Note: ``max_duration_seconds=0`` is treated as falsy and falls back
        to ``default_timeout``, so we instead set default_timeout=0 on the
        engine constructor *and* a tiny policy timeout to trigger the guard.
        We simulate elapsed time by patching time.time to advance.
        """
        call_count = 0

        async def _slow_send(**kwargs: Any) -> bool:
            nonlocal call_count
            call_count += 1
            return False  # always fail so engine wants to escalate

        dispatcher = AsyncMock()
        dispatcher.send = _slow_send  # type: ignore[assignment]

        engine = EscalationEngine(dispatcher=dispatcher, default_timeout=0)
        steps = [
            _make_step(channel="slack", retry_count=0),
            _make_step(channel="email", retry_count=0),
        ]
        # Use a very small timeout; the first step will succeed in consuming
        # most of it, and by the second step the timeout should trigger.
        policy = _make_policy(name="p1", steps=steps, max_duration_seconds=1)
        engine.register_policy(policy)

        # Patch time.time so that after the first step completes, elapsed > 1s
        original_time = time.time
        times_iter = iter([100.0, 100.0, 102.0, 102.0, 102.0])

        def fake_time() -> float:
            return next(times_iter, original_time())

        import shieldops.integrations.notifications.escalation as esc_mod

        original_time_fn = esc_mod.time.time
        esc_mod.time.time = fake_time  # type: ignore[assignment]
        try:
            result = await engine.execute("p1", message="alert!")
        finally:
            esc_mod.time.time = original_time_fn  # type: ignore[assignment]

        # Only the first step should have been tried; second is skipped by timeout
        assert call_count == 1
        assert result.delivered is False

    @pytest.mark.asyncio
    async def test_timeout_with_generous_limit(self) -> None:
        """A generous timeout allows all steps."""
        dispatcher = _make_dispatcher(side_effect=[False, True])
        engine = EscalationEngine(dispatcher=dispatcher)
        steps = [_make_step(channel="slack"), _make_step(channel="email")]
        policy = _make_policy(name="p1", steps=steps, max_duration_seconds=600)
        engine.register_policy(policy)
        result = await engine.execute("p1", message="alert!")
        assert result.delivered is True


# =========================================================================
# Disabled and missing policies
# =========================================================================


class TestDisabledAndMissing:
    """Edge cases where execution is not possible."""

    @pytest.mark.asyncio
    async def test_disabled_policy(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1", enabled=False))
        result = await engine.execute("p1", message="alert!")
        assert result.delivered is False

    @pytest.mark.asyncio
    async def test_missing_policy(self) -> None:
        engine = EscalationEngine()
        result = await engine.execute("nonexistent", message="alert!")
        assert result.delivered is False
        assert result.policy_name == "nonexistent"

    @pytest.mark.asyncio
    async def test_disabled_policy_not_called(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1", enabled=False))
        await engine.execute("p1", message="alert!")
        dispatcher.send.assert_not_called()


# =========================================================================
# execute_for_severity
# =========================================================================


class TestExecuteForSeverity:
    """execute_for_severity matches policies by severity_filter."""

    @pytest.mark.asyncio
    async def test_matches_severity_filter(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="critical_policy", severity_filter=["critical"]))
        result = await engine.execute_for_severity("critical", message="down!")
        assert result is not None
        assert result.delivered is True

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="critical_policy", severity_filter=["critical"]))
        result = await engine.execute_for_severity("info", message="just fyi")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_filter_matches_all(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="catch_all", severity_filter=[]))
        result = await engine.execute_for_severity("warning", message="heads up")
        assert result is not None
        assert result.delivered is True

    @pytest.mark.asyncio
    async def test_skips_disabled_policies(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(
            _make_policy(name="off", severity_filter=["critical"], enabled=False)
        )
        result = await engine.execute_for_severity("critical", message="down!")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_policies_returns_none(self) -> None:
        engine = EscalationEngine()
        result = await engine.execute_for_severity("critical", message="down!")
        assert result is None


# =========================================================================
# test_policy (dry-run)
# =========================================================================


class TestTestPolicy:
    """test_policy() sends a test message through the real pipeline."""

    @pytest.mark.asyncio
    async def test_dry_run_succeeds(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1"))
        result = await engine.test_policy("p1")
        assert result.delivered is True
        call_kwargs = dispatcher.send.call_args
        assert "[TEST]" in call_kwargs.kwargs.get("message", call_kwargs[1].get("message", ""))

    @pytest.mark.asyncio
    async def test_dry_run_missing_policy(self) -> None:
        engine = EscalationEngine()
        result = await engine.test_policy("no_such")
        assert result.delivered is False


# =========================================================================
# History and stats
# =========================================================================


class TestHistoryAndStats:
    """get_history() and get_stats() track execution results."""

    @pytest.mark.asyncio
    async def test_history_recorded(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1"))
        await engine.execute("p1", message="one")
        await engine.execute("p1", message="two")
        assert len(engine.get_history()) == 2

    @pytest.mark.asyncio
    async def test_history_limit(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1"))
        await engine.execute("p1", message="m")
        await engine.execute("p1", message="m")
        history = engine.get_history(limit=1)
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_stats_after_executions(self) -> None:
        dispatcher = _make_dispatcher(side_effect=[True, False])
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1"))
        await engine.execute("p1", message="ok")
        await engine.execute("p1", message="fail")
        stats = engine.get_stats()
        assert stats["total_executions"] == 2
        assert stats["delivered"] == 1
        assert stats["failed"] == 1

    def test_stats_empty(self) -> None:
        engine = EscalationEngine()
        stats = engine.get_stats()
        assert stats["total_executions"] == 0
        assert stats["delivery_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_total_policies(self) -> None:
        engine = EscalationEngine()
        engine.register_policy(_make_policy(name="a"))
        engine.register_policy(_make_policy(name="b"))
        stats = engine.get_stats()
        assert stats["total_policies"] == 2

    @pytest.mark.asyncio
    async def test_stats_escalated_count(self) -> None:
        dispatcher = _make_dispatcher(side_effect=[False, True])
        engine = EscalationEngine(dispatcher=dispatcher)
        steps = [_make_step(channel="a"), _make_step(channel="b")]
        engine.register_policy(_make_policy(name="p1", steps=steps))
        await engine.execute("p1", message="alert!")
        stats = engine.get_stats()
        assert stats["escalated"] == 1

    @pytest.mark.asyncio
    async def test_stats_delivery_rate(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1"))
        await engine.execute("p1", message="m")
        stats = engine.get_stats()
        assert stats["delivery_rate"] == 100.0


# =========================================================================
# No dispatcher configured
# =========================================================================


class TestNoDispatcher:
    """Engine with no dispatcher records errors in attempts."""

    @pytest.mark.asyncio
    async def test_no_dispatcher_error(self) -> None:
        engine = EscalationEngine(dispatcher=None)
        engine.register_policy(_make_policy(name="p1"))
        result = await engine.execute("p1", message="alert!")
        assert result.delivered is False
        assert len(result.attempts) >= 1
        assert any("No dispatcher" in a.error for a in result.attempts)

    @pytest.mark.asyncio
    async def test_no_dispatcher_retries_all_fail(self) -> None:
        engine = EscalationEngine(dispatcher=None)
        step = _make_step(channel="slack", retry_count=2, retry_delay_seconds=0)
        engine.register_policy(_make_policy(name="p1", steps=[step]))
        result = await engine.execute("p1", message="alert!")
        assert result.delivered is False
        # All attempts should have errors
        assert all(a.error != "" for a in result.attempts)


# =========================================================================
# Edge cases
# =========================================================================


class TestEdgeCases:
    """Miscellaneous edge cases."""

    @pytest.mark.asyncio
    async def test_policy_with_no_steps(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        policy = _make_policy(name="empty", steps=[])
        engine.register_policy(policy)
        result = await engine.execute("empty", message="alert!")
        assert result.delivered is False
        assert len(result.attempts) == 0

    @pytest.mark.asyncio
    async def test_execute_passes_severity(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1"))
        await engine.execute("p1", message="msg", severity="critical")
        call_kwargs = dispatcher.send.call_args
        assert call_kwargs.kwargs.get("severity") == "critical"

    @pytest.mark.asyncio
    async def test_execute_passes_details(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1"))
        await engine.execute("p1", message="msg", details={"host": "srv1"})
        call_kwargs = dispatcher.send.call_args
        assert call_kwargs.kwargs.get("details") == {"host": "srv1"}

    @pytest.mark.asyncio
    async def test_multiple_policies_independent(self) -> None:
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="a"))
        engine.register_policy(_make_policy(name="b"))
        r1 = await engine.execute("a", message="m1")
        r2 = await engine.execute("b", message="m2")
        assert r1.delivered is True
        assert r2.delivered is True
        assert r1.execution_id != r2.execution_id

    @pytest.mark.asyncio
    async def test_history_bounded(self) -> None:
        """After 1000+ entries history is pruned."""
        dispatcher = _make_dispatcher(return_value=True)
        engine = EscalationEngine(dispatcher=dispatcher)
        engine.register_policy(_make_policy(name="p1"))
        # Manually fill history to trigger pruning
        for _ in range(1002):
            engine._history.append(EscalationResult(policy_name="p1", delivered=True))
        # One more execution triggers the prune
        await engine.execute("p1", message="trigger prune")
        assert len(engine._history) <= 501
