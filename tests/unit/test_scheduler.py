"""Comprehensive tests for the async job scheduler and predefined jobs."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.scheduler.jobs import (
    daily_cost_analysis,
    nightly_learning_cycle,
    periodic_security_scan,
)
from shieldops.scheduler.scheduler import JobScheduler, ScheduledJob

# ===========================================================================
# ScheduledJob dataclass
# ===========================================================================


class TestScheduledJob:
    """Tests for the ScheduledJob dataclass."""

    def test_defaults(self):
        job = ScheduledJob(
            name="test",
            func=AsyncMock(),
            interval_seconds=60,
        )
        assert job.name == "test"
        assert job.interval_seconds == 60
        assert job.enabled is True
        assert job.last_run is None
        assert job.run_count == 0
        assert job.error_count == 0
        assert job.kwargs == {}
        assert job._task is None

    def test_custom_kwargs(self):
        job = ScheduledJob(
            name="custom",
            func=AsyncMock(),
            interval_seconds=3600,
            kwargs={"env": "production"},
            enabled=False,
        )
        assert job.kwargs == {"env": "production"}
        assert job.enabled is False

    def test_repr_excludes_task(self):
        job = ScheduledJob(
            name="repr_test",
            func=AsyncMock(),
            interval_seconds=10,
        )
        r = repr(job)
        assert "repr_test" in r
        assert "_task" not in r


# ===========================================================================
# JobScheduler.add_job
# ===========================================================================


class TestAddJob:
    """Tests for registering jobs."""

    def test_add_job_registers_correctly(self):
        scheduler = JobScheduler()
        coro = AsyncMock()
        scheduler.add_job("my_job", coro, interval_seconds=300, foo="bar")

        jobs = scheduler.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["name"] == "my_job"
        assert jobs[0]["interval_seconds"] == 300
        assert jobs[0]["enabled"] is True
        assert jobs[0]["run_count"] == 0

    def test_add_job_disabled(self):
        scheduler = JobScheduler()
        scheduler.add_job("disabled", AsyncMock(), 60, enabled=False)

        jobs = scheduler.list_jobs()
        assert jobs[0]["enabled"] is False

    def test_add_job_replaces_existing(self):
        scheduler = JobScheduler()
        scheduler.add_job("dup", AsyncMock(), 60)
        scheduler.add_job("dup", AsyncMock(), 120)

        jobs = scheduler.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["interval_seconds"] == 120

    def test_add_job_invalid_interval_raises(self):
        scheduler = JobScheduler()
        with pytest.raises(ValueError, match="positive"):
            scheduler.add_job("bad", AsyncMock(), interval_seconds=0)

    def test_add_job_negative_interval_raises(self):
        scheduler = JobScheduler()
        with pytest.raises(ValueError, match="positive"):
            scheduler.add_job("bad", AsyncMock(), interval_seconds=-10)

    def test_add_multiple_jobs(self):
        scheduler = JobScheduler()
        scheduler.add_job("a", AsyncMock(), 60)
        scheduler.add_job("b", AsyncMock(), 120)
        scheduler.add_job("c", AsyncMock(), 180)
        assert len(scheduler.list_jobs()) == 3


# ===========================================================================
# JobScheduler.remove_job
# ===========================================================================


class TestRemoveJob:
    """Tests for removing jobs."""

    def test_remove_existing(self):
        scheduler = JobScheduler()
        scheduler.add_job("removable", AsyncMock(), 60)
        assert scheduler.remove_job("removable") is True
        assert len(scheduler.list_jobs()) == 0

    def test_remove_nonexistent(self):
        scheduler = JobScheduler()
        assert scheduler.remove_job("ghost") is False


# ===========================================================================
# JobScheduler.start / stop
# ===========================================================================


class TestStartStop:
    """Tests for scheduler lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_tasks(self):
        scheduler = JobScheduler()
        scheduler.add_job("j1", AsyncMock(), 3600)
        scheduler.add_job("j2", AsyncMock(), 3600)
        await scheduler.start()

        try:
            assert scheduler.running is True
            jobs = scheduler.list_jobs()
            assert all(j["running"] for j in jobs)
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_start_skips_disabled_jobs(self):
        scheduler = JobScheduler()
        scheduler.add_job("enabled", AsyncMock(), 3600, enabled=True)
        scheduler.add_job("disabled", AsyncMock(), 3600, enabled=False)
        await scheduler.start()

        try:
            jobs = {j["name"]: j for j in scheduler.list_jobs()}
            assert jobs["enabled"]["running"] is True
            assert jobs["disabled"]["running"] is False
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_double_start_is_idempotent(self):
        scheduler = JobScheduler()
        scheduler.add_job("once", AsyncMock(), 3600)
        await scheduler.start()
        await scheduler.start()  # second call should be a no-op

        try:
            assert scheduler.running is True
            assert len(scheduler.list_jobs()) == 1
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self):
        scheduler = JobScheduler()
        scheduler.add_job("cancel_me", AsyncMock(), 3600)
        await scheduler.start()
        assert scheduler.running is True

        await scheduler.stop()
        assert scheduler.running is False
        jobs = scheduler.list_jobs()
        assert all(not j["running"] for j in jobs)

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self):
        scheduler = JobScheduler()
        scheduler.add_job("no_start", AsyncMock(), 60)
        await scheduler.stop()  # should not raise
        assert scheduler.running is False


# ===========================================================================
# JobScheduler._run_loop (integration-style)
# ===========================================================================


class TestRunLoop:
    """Tests for the internal job execution loop."""

    @pytest.mark.asyncio
    async def test_run_loop_executes_function(self):
        func = AsyncMock()
        scheduler = JobScheduler()
        scheduler.add_job("fast", func, interval_seconds=1, key="value")
        await scheduler.start()

        # Wait long enough for at least one execution
        await asyncio.sleep(1.5)
        await scheduler.stop()

        func.assert_awaited()
        func.assert_called_with(key="value")

    @pytest.mark.asyncio
    async def test_run_loop_increments_run_count(self):
        func = AsyncMock()
        scheduler = JobScheduler()
        scheduler.add_job("counter", func, interval_seconds=1)
        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        jobs = scheduler.list_jobs()
        assert jobs[0]["run_count"] >= 1

    @pytest.mark.asyncio
    async def test_run_loop_sets_last_run(self):
        func = AsyncMock()
        scheduler = JobScheduler()
        scheduler.add_job("timestamp", func, interval_seconds=1)
        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        jobs = scheduler.list_jobs()
        assert jobs[0]["last_run"] is not None

    @pytest.mark.asyncio
    async def test_run_loop_error_handling(self):
        func = AsyncMock(side_effect=RuntimeError("boom"))
        scheduler = JobScheduler()
        scheduler.add_job("exploder", func, interval_seconds=1)
        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        jobs = scheduler.list_jobs()
        assert jobs[0]["error_count"] >= 1
        # run_count should NOT have incremented on failure
        assert jobs[0]["run_count"] == 0

    @pytest.mark.asyncio
    async def test_run_loop_continues_after_error(self):
        """A failing job should not stop the loop -- it keeps retrying."""
        call_count = 0

        async def flaky(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise RuntimeError("first call fails")

        scheduler = JobScheduler()
        scheduler.add_job("flaky", flaky, interval_seconds=1)
        await scheduler.start()

        # Wait for two iterations
        await asyncio.sleep(2.5)
        await scheduler.stop()

        assert call_count >= 2


# ===========================================================================
# JobScheduler.list_jobs / get_job
# ===========================================================================


class TestIntrospection:
    """Tests for job status introspection."""

    def test_list_jobs_empty(self):
        scheduler = JobScheduler()
        assert scheduler.list_jobs() == []

    def test_list_jobs_returns_all_fields(self):
        scheduler = JobScheduler()
        scheduler.add_job("full", AsyncMock(), 600)

        jobs = scheduler.list_jobs()
        j = jobs[0]
        expected_keys = {
            "name",
            "interval_seconds",
            "enabled",
            "last_run",
            "run_count",
            "error_count",
            "running",
        }
        assert set(j.keys()) == expected_keys

    def test_get_job_existing(self):
        scheduler = JobScheduler()
        scheduler.add_job("find_me", AsyncMock(), 42)

        result = scheduler.get_job("find_me")
        assert result is not None
        assert result["name"] == "find_me"
        assert result["interval_seconds"] == 42

    def test_get_job_missing(self):
        scheduler = JobScheduler()
        assert scheduler.get_job("nope") is None

    def test_running_property_default(self):
        scheduler = JobScheduler()
        assert scheduler.running is False


# ===========================================================================
# Job functions -- nightly_learning_cycle
# ===========================================================================


class TestNightlyLearningCycle:
    """Tests for the nightly_learning_cycle job function."""

    @pytest.mark.asyncio
    async def test_calls_learn_with_correct_params(self):
        runner = AsyncMock()
        runner.learn.return_value = MagicMock(
            learning_id="learn-abc",
            total_incidents_analyzed=10,
            pattern_insights=[MagicMock(), MagicMock()],
        )

        await nightly_learning_cycle(learning_runner=runner)

        runner.learn.assert_awaited_once_with(learning_type="full", period="7d")

    @pytest.mark.asyncio
    async def test_skips_when_no_runner(self):
        # Should not raise when runner is None
        await nightly_learning_cycle(learning_runner=None)

    @pytest.mark.asyncio
    async def test_skips_with_default_args(self):
        # Called with no arguments at all
        await nightly_learning_cycle()


# ===========================================================================
# Job functions -- periodic_security_scan
# ===========================================================================


class TestPeriodicSecurityScan:
    """Tests for the periodic_security_scan job function."""

    @pytest.mark.asyncio
    async def test_calls_scan_with_correct_params(self):
        runner = AsyncMock()
        runner.scan.return_value = MagicMock(
            scan_id="sec-xyz",
            cve_findings=[MagicMock()],
        )

        await periodic_security_scan(security_runner=runner, environment="production")

        from shieldops.models.base import Environment

        runner.scan.assert_awaited_once_with(
            scan_type="full",
            environment=Environment.PRODUCTION,
        )

    @pytest.mark.asyncio
    async def test_handles_staging_environment(self):
        runner = AsyncMock()
        runner.scan.return_value = MagicMock(
            scan_id="sec-stg",
            cve_findings=[],
        )

        await periodic_security_scan(security_runner=runner, environment="staging")

        from shieldops.models.base import Environment

        runner.scan.assert_awaited_once_with(
            scan_type="full",
            environment=Environment.STAGING,
        )

    @pytest.mark.asyncio
    async def test_invalid_environment_falls_back(self):
        runner = AsyncMock()
        runner.scan.return_value = MagicMock(
            scan_id="sec-fallback",
            cve_findings=[],
        )

        await periodic_security_scan(security_runner=runner, environment="invalid_env")

        from shieldops.models.base import Environment

        runner.scan.assert_awaited_once_with(
            scan_type="full",
            environment=Environment.PRODUCTION,
        )

    @pytest.mark.asyncio
    async def test_skips_when_no_runner(self):
        await periodic_security_scan(security_runner=None)

    @pytest.mark.asyncio
    async def test_skips_with_default_args(self):
        await periodic_security_scan()


# ===========================================================================
# Job functions -- daily_cost_analysis
# ===========================================================================


class TestDailyCostAnalysis:
    """Tests for the daily_cost_analysis job function."""

    @pytest.mark.asyncio
    async def test_calls_analyze_with_correct_params(self):
        runner = AsyncMock()
        runner.analyze.return_value = MagicMock(analysis_id="cost-abc")

        await daily_cost_analysis(cost_runner=runner, environment="production")

        from shieldops.models.base import Environment

        runner.analyze.assert_awaited_once_with(
            environment=Environment.PRODUCTION,
        )

    @pytest.mark.asyncio
    async def test_handles_development_environment(self):
        runner = AsyncMock()
        runner.analyze.return_value = MagicMock(analysis_id="cost-dev")

        await daily_cost_analysis(cost_runner=runner, environment="development")

        from shieldops.models.base import Environment

        runner.analyze.assert_awaited_once_with(
            environment=Environment.DEVELOPMENT,
        )

    @pytest.mark.asyncio
    async def test_invalid_environment_falls_back(self):
        runner = AsyncMock()
        runner.analyze.return_value = MagicMock(analysis_id="cost-fb")

        await daily_cost_analysis(cost_runner=runner, environment="bogus")

        from shieldops.models.base import Environment

        runner.analyze.assert_awaited_once_with(
            environment=Environment.PRODUCTION,
        )

    @pytest.mark.asyncio
    async def test_skips_when_no_runner(self):
        await daily_cost_analysis(cost_runner=None)

    @pytest.mark.asyncio
    async def test_skips_with_default_args(self):
        await daily_cost_analysis()


# ===========================================================================
# Integration: scheduler + job functions wired together
# ===========================================================================


class TestSchedulerJobIntegration:
    """End-to-end tests wiring the scheduler with predefined job functions."""

    @pytest.mark.asyncio
    async def test_scheduler_runs_learning_job(self):
        runner = AsyncMock()
        runner.learn.return_value = MagicMock(
            learning_id="learn-int",
            total_incidents_analyzed=5,
            pattern_insights=[],
        )

        scheduler = JobScheduler()
        scheduler.add_job(
            "learning",
            nightly_learning_cycle,
            interval_seconds=1,
            learning_runner=runner,
        )
        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        runner.learn.assert_awaited()

    @pytest.mark.asyncio
    async def test_scheduler_runs_security_job(self):
        runner = AsyncMock()
        runner.scan.return_value = MagicMock(
            scan_id="sec-int",
            cve_findings=[],
        )

        scheduler = JobScheduler()
        scheduler.add_job(
            "security",
            periodic_security_scan,
            interval_seconds=1,
            security_runner=runner,
            environment="production",
        )
        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        runner.scan.assert_awaited()

    @pytest.mark.asyncio
    async def test_scheduler_runs_cost_job(self):
        runner = AsyncMock()
        runner.analyze.return_value = MagicMock(analysis_id="cost-int")

        scheduler = JobScheduler()
        scheduler.add_job(
            "cost",
            daily_cost_analysis,
            interval_seconds=1,
            cost_runner=runner,
            environment="production",
        )
        await scheduler.start()
        await asyncio.sleep(1.5)
        await scheduler.stop()

        runner.analyze.assert_awaited()
