"""Tests for learning cycle persistence — DB model, repository, and runner integration."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.learning.models import (
    LearningState,
    LearningStep,
    PatternInsight,
    PlaybookUpdate,
    ThresholdAdjustment,
)
from shieldops.agents.learning.runner import LearningRunner
from shieldops.db.models import LearningCycleRecord

# ── Helpers ───────────────────────────────────────────────────


def _make_learning_state(
    learning_id: str = "learn-test001",
    learning_type: str = "full",
    current_step: str = "complete",
    **overrides,
) -> LearningState:
    """Build a realistic LearningState for tests."""
    defaults = dict(
        learning_id=learning_id,
        learning_type=learning_type,
        target_period="30d",
        current_step=current_step,
        total_incidents_analyzed=12,
        recurring_pattern_count=2,
        improvement_score=78.5,
        automation_accuracy=85.0,
        learning_duration_ms=4500,
        pattern_insights=[
            PatternInsight(
                pattern_id="p1",
                alert_type="high_cpu",
                description="Recurring CPU spikes",
                frequency=5,
                common_root_cause="memory leak",
                common_resolution="restart_pod",
                confidence=0.9,
            ),
        ],
        playbook_updates=[
            PlaybookUpdate(
                playbook_id="pb1",
                alert_type="high_cpu",
                update_type="modify_step",
                title="Improve CPU playbook",
                steps=["Drain node", "Restart pod"],
            ),
        ],
        threshold_adjustments=[
            ThresholdAdjustment(
                adjustment_id="adj1",
                metric_name="cpu_usage_percent",
                current_threshold=80.0,
                recommended_threshold=88.0,
                direction="increase",
                reason="Too many false positives",
            ),
        ],
        reasoning_chain=[
            LearningStep(
                step_number=1,
                action="gather_outcomes",
                input_summary="period=30d",
                output_summary="12 incidents loaded",
                duration_ms=500,
            ),
        ],
        error=None,
        learning_start=datetime.now(UTC),
    )
    defaults.update(overrides)
    return LearningState(**defaults)


# ===========================================================================
# LearningCycleRecord Model Tests
# ===========================================================================


class TestLearningCycleRecord:
    """Tests for the SQLAlchemy ORM model."""

    def test_create_record_with_all_fields(self):
        record = LearningCycleRecord(
            id="learn-abc123",
            learning_type="full",
            target_period="30d",
            status="complete",
            total_incidents_analyzed=10,
            recurring_pattern_count=2,
            improvement_score=75.0,
            automation_accuracy=90.0,
            pattern_insights=[{"pattern_id": "p1", "alert_type": "high_cpu"}],
            playbook_updates=[{"playbook_id": "pb1"}],
            threshold_adjustments=[{"adjustment_id": "adj1"}],
            reasoning_chain=[{"step_number": 1, "action": "gather"}],
            error=None,
            duration_ms=3000,
        )
        assert record.id == "learn-abc123"
        assert record.learning_type == "full"
        assert record.status == "complete"
        assert record.total_incidents_analyzed == 10
        assert record.improvement_score == 75.0
        assert record.automation_accuracy == 90.0
        assert len(record.pattern_insights) == 1
        assert len(record.playbook_updates) == 1
        assert len(record.threshold_adjustments) == 1
        assert len(record.reasoning_chain) == 1
        assert record.error is None
        assert record.duration_ms == 3000

    def test_default_values(self):
        """Column defaults apply at DB flush time; verify they exist on the schema."""
        record = LearningCycleRecord(
            id="learn-defaults",
            learning_type="pattern_only",
        )
        # Nullable field has no value before flush
        assert record.error is None

        # Verify column-level defaults are declared in the mapping.
        # These apply at INSERT time, not on Python construction.
        table = LearningCycleRecord.__table__
        assert table.c.target_period.default.arg == "30d"
        assert table.c.status.default.arg == "init"
        assert table.c.total_incidents_analyzed.default.arg == 0
        assert table.c.recurring_pattern_count.default.arg == 0
        assert table.c.improvement_score.default.arg == 0.0
        assert table.c.automation_accuracy.default.arg == 0.0
        assert table.c.duration_ms.default.arg == 0

    def test_json_fields_accept_complex_data(self):
        insights = [
            {
                "pattern_id": "p1",
                "alert_type": "high_cpu",
                "description": "Recurring spikes",
                "frequency": 5,
                "environments": ["production", "staging"],
            },
            {
                "pattern_id": "p2",
                "alert_type": "oom_kill",
                "description": "Memory pressure",
                "frequency": 3,
            },
        ]
        record = LearningCycleRecord(
            id="learn-json",
            learning_type="full",
            pattern_insights=insights,
        )
        assert len(record.pattern_insights) == 2
        assert record.pattern_insights[0]["environments"] == [
            "production",
            "staging",
        ]

    def test_error_field_stores_text(self):
        record = LearningCycleRecord(
            id="learn-err",
            learning_type="full",
            error="LLM timeout after 30s",
        )
        assert record.error == "LLM timeout after 30s"

    def test_tablename(self):
        assert LearningCycleRecord.__tablename__ == "learning_cycles"


# ===========================================================================
# Repository.save_learning_cycle Tests
# ===========================================================================


class TestRepositorySaveLearningCycle:
    """Tests for Repository.save_learning_cycle."""

    @pytest.mark.asyncio
    async def test_save_creates_record_with_correct_fields(self):
        from shieldops.db.repository import Repository

        mock_session = AsyncMock()
        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        repo = Repository(session_factory=mock_sf)
        state = _make_learning_state()

        result = await repo.save_learning_cycle(state)

        assert result == state.learning_id
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

        # Verify the record passed to session.add
        added_record = mock_session.add.call_args[0][0]
        assert isinstance(added_record, LearningCycleRecord)
        assert added_record.id == state.learning_id
        assert added_record.learning_type == "full"
        assert added_record.target_period == "30d"
        assert added_record.status == "complete"
        assert added_record.total_incidents_analyzed == 12
        assert added_record.recurring_pattern_count == 2
        assert added_record.improvement_score == 78.5
        assert added_record.automation_accuracy == 85.0
        assert added_record.duration_ms == 4500
        assert added_record.error is None

    @pytest.mark.asyncio
    async def test_save_serializes_pydantic_models(self):
        from shieldops.db.repository import Repository

        mock_session = AsyncMock()
        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        repo = Repository(session_factory=mock_sf)
        state = _make_learning_state()

        await repo.save_learning_cycle(state)

        added_record = mock_session.add.call_args[0][0]

        # Pattern insights should be serialized dicts, not Pydantic objects
        assert isinstance(added_record.pattern_insights, list)
        assert isinstance(added_record.pattern_insights[0], dict)
        assert added_record.pattern_insights[0]["pattern_id"] == "p1"
        assert added_record.pattern_insights[0]["alert_type"] == "high_cpu"

        # Playbook updates should be serialized
        assert isinstance(added_record.playbook_updates[0], dict)
        assert added_record.playbook_updates[0]["playbook_id"] == "pb1"

        # Threshold adjustments should be serialized
        assert isinstance(added_record.threshold_adjustments[0], dict)
        assert added_record.threshold_adjustments[0]["adjustment_id"] == "adj1"

        # Reasoning chain should be serialized
        assert isinstance(added_record.reasoning_chain[0], dict)
        assert added_record.reasoning_chain[0]["step_number"] == 1

    @pytest.mark.asyncio
    async def test_save_handles_none_duration(self):
        from shieldops.db.repository import Repository

        mock_session = AsyncMock()
        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        repo = Repository(session_factory=mock_sf)
        # learning_duration_ms defaults to 0, but test the or-fallback
        state = _make_learning_state(learning_duration_ms=0)

        await repo.save_learning_cycle(state)

        added_record = mock_session.add.call_args[0][0]
        assert added_record.duration_ms == 0

    @pytest.mark.asyncio
    async def test_save_uses_current_step_as_status(self):
        from shieldops.db.repository import Repository

        mock_session = AsyncMock()
        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        repo = Repository(session_factory=mock_sf)
        state = _make_learning_state(current_step="analyze_patterns")

        await repo.save_learning_cycle(state)

        added_record = mock_session.add.call_args[0][0]
        assert added_record.status == "analyze_patterns"


# ===========================================================================
# Repository.query_learning_cycles Tests
# ===========================================================================


class TestRepositoryQueryLearningCycles:
    """Tests for Repository.query_learning_cycles."""

    @pytest.mark.asyncio
    async def test_query_returns_formatted_dicts(self):
        from shieldops.db.repository import Repository

        mock_record = MagicMock()
        mock_record.id = "learn-q1"
        mock_record.learning_type = "full"
        mock_record.target_period = "30d"
        mock_record.status = "complete"
        mock_record.total_incidents_analyzed = 8
        mock_record.improvement_score = 72.0
        mock_record.duration_ms = 2000
        mock_record.created_at = datetime(2026, 1, 15, 10, 30, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_record]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        repo = Repository(session_factory=mock_sf)
        results = await repo.query_learning_cycles()

        assert len(results) == 1
        assert results[0]["id"] == "learn-q1"
        assert results[0]["learning_type"] == "full"
        assert results[0]["target_period"] == "30d"
        assert results[0]["status"] == "complete"
        assert results[0]["total_incidents_analyzed"] == 8
        assert results[0]["improvement_score"] == 72.0
        assert results[0]["duration_ms"] == 2000
        assert results[0]["created_at"] is not None

    @pytest.mark.asyncio
    async def test_query_with_learning_type_filter(self):
        from shieldops.db.repository import Repository

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        repo = Repository(session_factory=mock_sf)
        results = await repo.query_learning_cycles(learning_type="pattern_only")

        assert results == []
        # Verify execute was called (the filter is applied to the statement)
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_respects_limit(self):
        from shieldops.db.repository import Repository

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        repo = Repository(session_factory=mock_sf)
        await repo.query_learning_cycles(limit=5)

        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_handles_none_created_at(self):
        from shieldops.db.repository import Repository

        mock_record = MagicMock()
        mock_record.id = "learn-none-ts"
        mock_record.learning_type = "full"
        mock_record.target_period = "30d"
        mock_record.status = "complete"
        mock_record.total_incidents_analyzed = 0
        mock_record.improvement_score = 0.0
        mock_record.duration_ms = 0
        mock_record.created_at = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_record]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        repo = Repository(session_factory=mock_sf)
        results = await repo.query_learning_cycles()

        assert results[0]["created_at"] is None


# ===========================================================================
# LearningRunner Persistence Tests
# ===========================================================================


class TestLearningRunnerPersistence:
    """Tests for runner calling save_learning_cycle after learn()."""

    @pytest.mark.asyncio
    async def test_learn_calls_save_on_success(self):
        mock_repo = AsyncMock()
        mock_repo.save_learning_cycle = AsyncMock(return_value="learn-persisted")

        runner = LearningRunner(repository=mock_repo)

        completed_state = LearningState(
            learning_id="learn-xyz",
            learning_type="full",
            current_step="complete",
            total_incidents_analyzed=10,
            learning_start=datetime.now(UTC),
        )

        with patch.object(runner, "_app") as mock_app:
            mock_app.ainvoke = AsyncMock(return_value=completed_state.model_dump())
            result = await runner.learn()

        assert result.current_step == "complete"
        mock_repo.save_learning_cycle.assert_awaited_once()

        # Verify the state passed to save_learning_cycle is a LearningState
        saved_state = mock_repo.save_learning_cycle.call_args[0][0]
        assert isinstance(saved_state, LearningState)
        assert saved_state.total_incidents_analyzed == 10

    @pytest.mark.asyncio
    async def test_learn_stores_repository_reference(self):
        mock_repo = AsyncMock()
        runner = LearningRunner(repository=mock_repo)
        assert runner._repository is mock_repo

    @pytest.mark.asyncio
    async def test_learn_still_returns_state_on_persist_success(self):
        mock_repo = AsyncMock()
        mock_repo.save_learning_cycle = AsyncMock(return_value="id")

        runner = LearningRunner(repository=mock_repo)

        with patch.object(runner, "_app") as mock_app:
            mock_app.ainvoke = AsyncMock(
                return_value=LearningState(
                    learning_id="learn-ret",
                    current_step="complete",
                    learning_start=datetime.now(UTC),
                    improvement_score=80.0,
                ).model_dump()
            )
            result = await runner.learn()

        assert result.improvement_score == 80.0
        assert len(runner.list_cycles()) == 1


# ===========================================================================
# LearningRunner Persistence Failure Tests
# ===========================================================================


class TestLearningRunnerPersistenceFailure:
    """Tests that persistence failures do not crash the runner."""

    @pytest.mark.asyncio
    async def test_persist_failure_does_not_crash_learn(self):
        mock_repo = AsyncMock()
        mock_repo.save_learning_cycle = AsyncMock(side_effect=RuntimeError("DB connection lost"))

        runner = LearningRunner(repository=mock_repo)

        with patch.object(runner, "_app") as mock_app:
            mock_app.ainvoke = AsyncMock(
                return_value=LearningState(
                    learning_id="learn-fail",
                    current_step="complete",
                    learning_start=datetime.now(UTC),
                ).model_dump()
            )
            result = await runner.learn()

        # Runner should still return the state successfully
        assert result.current_step == "complete"
        assert len(runner.list_cycles()) == 1

    @pytest.mark.asyncio
    async def test_persist_failure_logs_warning(self):
        mock_repo = AsyncMock()
        mock_repo.save_learning_cycle = AsyncMock(side_effect=ConnectionError("connection refused"))

        runner = LearningRunner(repository=mock_repo)

        with (
            patch.object(runner, "_app") as mock_app,
            patch("shieldops.agents.learning.runner.logger") as mock_logger,
        ):
            mock_app.ainvoke = AsyncMock(
                return_value=LearningState(
                    learning_id="learn-warn",
                    current_step="complete",
                    learning_start=datetime.now(UTC),
                ).model_dump()
            )
            await runner.learn()

        # Should have logged a warning about persistence failure
        mock_logger.warning.assert_called()
        call_kwargs = mock_logger.warning.call_args
        assert "learning_cycle_persist_failed" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_graph_error_does_not_attempt_persist(self):
        """When the graph itself fails, we should not try to persist."""
        mock_repo = AsyncMock()
        mock_repo.save_learning_cycle = AsyncMock()

        runner = LearningRunner(repository=mock_repo)

        with patch.object(runner, "_app") as mock_app:
            mock_app.ainvoke = AsyncMock(side_effect=RuntimeError("graph exploded"))
            result = await runner.learn()

        assert result.current_step == "failed"
        # save_learning_cycle should NOT be called on graph failure
        mock_repo.save_learning_cycle.assert_not_awaited()


# ===========================================================================
# LearningRunner No Repository Tests (backward compatibility)
# ===========================================================================


class TestLearningRunnerNoRepository:
    """Tests that the runner works fine without a repository (backward compat)."""

    def test_init_without_repository(self):
        runner = LearningRunner()
        assert runner._repository is None

    @pytest.mark.asyncio
    async def test_learn_without_repository_skips_persist(self):
        runner = LearningRunner()  # No repository

        with patch.object(runner, "_app") as mock_app:
            mock_app.ainvoke = AsyncMock(
                return_value=LearningState(
                    learning_id="learn-norepo",
                    current_step="complete",
                    learning_start=datetime.now(UTC),
                ).model_dump()
            )
            result = await runner.learn()

        # Should complete successfully without any DB calls
        assert result.current_step == "complete"
        assert len(runner.list_cycles()) == 1

    @pytest.mark.asyncio
    async def test_learn_error_without_repository(self):
        runner = LearningRunner()

        with patch.object(runner, "_app") as mock_app:
            mock_app.ainvoke = AsyncMock(side_effect=RuntimeError("graph error"))
            result = await runner.learn()

        assert result.current_step == "failed"
        assert result.error == "graph error"
        assert len(runner.list_cycles()) == 1

    def test_explicit_none_repository(self):
        runner = LearningRunner(repository=None)
        assert runner._repository is None
