"""Comprehensive tests for the Learning Agent."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from shieldops.agents.learning.graph import (
    create_learning_graph,
    should_recommend_playbooks,
    should_recommend_thresholds,
)
from shieldops.agents.learning.models import (
    IncidentOutcome,
    LearningState,
    LearningStep,
    PatternInsight,
    PlaybookUpdate,
    ThresholdAdjustment,
)
from shieldops.agents.learning.nodes import (
    analyze_patterns,
    gather_outcomes,
    recommend_playbooks,
    recommend_thresholds,
    set_toolkit,
    synthesize_improvements,
)
from shieldops.agents.learning.runner import LearningRunner
from shieldops.agents.learning.tools import LearningToolkit
from shieldops.models.base import Environment

# ===========================================================================
# Toolkit Tests
# ===========================================================================


class TestLearningToolkit:
    """Tests for LearningToolkit."""

    @pytest.mark.asyncio
    async def test_get_incident_outcomes_with_store(self):
        store = AsyncMock()
        store.query.return_value = {
            "total_incidents": 5,
            "outcomes": [
                {
                    "incident_id": "inc-1",
                    "alert_type": "high_cpu",
                    "was_automated": True,
                    "was_correct": True,
                },
            ],
        }
        toolkit = LearningToolkit(incident_store=store)
        result = await toolkit.get_incident_outcomes(period="7d")
        assert result["total_incidents"] == 5
        store.query.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_incident_outcomes_no_store(self):
        toolkit = LearningToolkit()
        result = await toolkit.get_incident_outcomes()
        assert result["total_incidents"] > 0
        assert len(result["outcomes"]) > 0

    @pytest.mark.asyncio
    async def test_get_incident_outcomes_store_failure(self):
        store = AsyncMock()
        store.query.side_effect = RuntimeError("DB down")
        toolkit = LearningToolkit(incident_store=store)
        result = await toolkit.get_incident_outcomes()
        # Falls back to stub data
        assert result["total_incidents"] > 0

    @pytest.mark.asyncio
    async def test_get_current_playbooks_no_store(self):
        toolkit = LearningToolkit()
        result = await toolkit.get_current_playbooks()
        assert result["total"] > 0
        assert len(result["playbooks"]) > 0

    @pytest.mark.asyncio
    async def test_get_alert_thresholds_no_store(self):
        toolkit = LearningToolkit()
        result = await toolkit.get_alert_thresholds()
        assert result["total"] > 0
        assert len(result["thresholds"]) > 0

    @pytest.mark.asyncio
    async def test_compute_effectiveness_metrics(self):
        toolkit = LearningToolkit()
        outcomes = [
            {
                "incident_id": "1",
                "alert_type": "high_cpu",
                "was_automated": True,
                "was_correct": True,
                "investigation_duration_ms": 30000,
                "remediation_duration_ms": 10000,
            },
            {
                "incident_id": "2",
                "alert_type": "high_cpu",
                "was_automated": True,
                "was_correct": False,
                "investigation_duration_ms": 40000,
                "remediation_duration_ms": 15000,
            },
            {
                "incident_id": "3",
                "alert_type": "oom_kill",
                "was_automated": False,
                "was_correct": True,
                "investigation_duration_ms": 60000,
                "remediation_duration_ms": 20000,
            },
        ]
        result = await toolkit.compute_effectiveness_metrics(outcomes)
        assert result["total_incidents"] == 3
        assert result["automated_count"] == 2
        assert result["accuracy"] == 50.0  # 1 correct out of 2 automated
        assert "high_cpu" in result["by_alert_type"]

    @pytest.mark.asyncio
    async def test_compute_effectiveness_empty(self):
        toolkit = LearningToolkit()
        result = await toolkit.compute_effectiveness_metrics([])
        assert result["total_incidents"] == 0
        assert result["automation_rate"] == 0.0


# ===========================================================================
# Node Tests
# ===========================================================================


class TestGatherOutcomesNode:
    """Tests for gather_outcomes node."""

    @pytest.mark.asyncio
    async def test_gather_outcomes(self):
        toolkit = LearningToolkit()
        set_toolkit(toolkit)

        state = LearningState(learning_id="test-001", target_period="30d")
        result = await gather_outcomes(state)

        assert result["total_incidents_analyzed"] > 0
        assert len(result["incident_outcomes"]) > 0
        assert result["current_step"] == "gather_outcomes"
        assert len(result["reasoning_chain"]) == 1

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_gather_outcomes_builds_models(self):
        toolkit = LearningToolkit()
        set_toolkit(toolkit)

        state = LearningState(learning_id="test-002")
        result = await gather_outcomes(state)

        for outcome in result["incident_outcomes"]:
            assert isinstance(outcome, IncidentOutcome)

        set_toolkit(None)


class TestAnalyzePatternsNode:
    """Tests for analyze_patterns node."""

    @pytest.mark.asyncio
    async def test_analyze_with_recurring_incidents(self):
        toolkit = LearningToolkit()
        set_toolkit(toolkit)

        state = LearningState(
            learning_id="test-003",
            incident_outcomes=[
                IncidentOutcome(
                    incident_id="1",
                    alert_type="high_cpu",
                    root_cause="memory leak",
                    resolution_action="restart_pod",
                    was_automated=True,
                ),
                IncidentOutcome(
                    incident_id="2",
                    alert_type="high_cpu",
                    root_cause="memory leak",
                    resolution_action="restart_pod",
                    was_automated=True,
                ),
                IncidentOutcome(
                    incident_id="3",
                    alert_type="oom_kill",
                    root_cause="bad config",
                    resolution_action="increase_resources",
                    was_automated=False,
                ),
            ],
            automation_accuracy=100.0,
            reasoning_chain=[],
        )
        result = await analyze_patterns(state)

        assert len(result["pattern_insights"]) > 0
        assert result["current_step"] == "analyze_patterns"
        # high_cpu appears 2x, so should be a recurring pattern
        cpu_patterns = [p for p in result["pattern_insights"] if p.alert_type == "high_cpu"]
        assert len(cpu_patterns) == 1
        assert cpu_patterns[0].frequency == 2

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_analyze_no_recurring(self):
        toolkit = LearningToolkit()
        set_toolkit(toolkit)

        state = LearningState(
            learning_id="test-004",
            incident_outcomes=[
                IncidentOutcome(incident_id="1", alert_type="high_cpu", root_cause="leak"),
                IncidentOutcome(incident_id="2", alert_type="oom_kill", root_cause="config"),
            ],
            reasoning_chain=[],
        )
        result = await analyze_patterns(state)
        # Each alert type appears once — no recurring patterns
        assert result["recurring_pattern_count"] == 0

        set_toolkit(None)


class TestRecommendPlaybooksNode:
    """Tests for recommend_playbooks node."""

    @pytest.mark.asyncio
    async def test_recommend_new_playbook(self):
        toolkit = LearningToolkit()
        set_toolkit(toolkit)

        state = LearningState(
            learning_id="test-005",
            incident_outcomes=[],
            pattern_insights=[
                PatternInsight(
                    pattern_id="p1",
                    alert_type="latency_spike",
                    description="Recurring latency",
                    frequency=3,
                    common_root_cause="db pool",
                    common_resolution="scale_horizontal",
                ),
            ],
            reasoning_chain=[],
        )
        result = await recommend_playbooks(state)

        # latency_spike is not in default playbooks, so should get new_playbook recommendation
        new_pbs = [u for u in result["playbook_updates"] if u.update_type == "new_playbook"]
        assert len(new_pbs) > 0

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_recommend_fix_for_incorrect_automation(self):
        toolkit = LearningToolkit()
        set_toolkit(toolkit)

        state = LearningState(
            learning_id="test-006",
            incident_outcomes=[
                IncidentOutcome(
                    incident_id="inc-1",
                    alert_type="high_cpu",
                    root_cause="cron job",
                    resolution_action="restart_pod",
                    was_automated=True,
                    was_correct=False,
                ),
            ],
            pattern_insights=[],
            reasoning_chain=[],
        )
        result = await recommend_playbooks(state)

        # Should recommend fixing the incorrect automation
        fix_updates = [u for u in result["playbook_updates"] if u.update_type == "modify_step"]
        assert len(fix_updates) > 0
        assert "incorrect" in fix_updates[0].title.lower() or "fix" in fix_updates[0].title.lower()

        set_toolkit(None)


class TestRecommendThresholdsNode:
    """Tests for recommend_thresholds node."""

    @pytest.mark.asyncio
    async def test_recommend_with_false_positives(self):
        toolkit = LearningToolkit()
        set_toolkit(toolkit)

        state = LearningState(
            learning_id="test-007",
            incident_outcomes=[
                IncidentOutcome(
                    incident_id="1", alert_type="high_cpu", was_automated=True, was_correct=False
                ),
                IncidentOutcome(
                    incident_id="2", alert_type="high_cpu", was_automated=True, was_correct=False
                ),
                IncidentOutcome(
                    incident_id="3", alert_type="high_cpu", was_automated=True, was_correct=True
                ),
            ],
            reasoning_chain=[],
        )

        with patch(
            "shieldops.agents.learning.nodes.llm_structured", side_effect=RuntimeError("skip")
        ):
            result = await recommend_thresholds(state)

        # 2/3 high_cpu automations were wrong (66% error rate) — should suggest adjustment
        assert len(result["threshold_adjustments"]) > 0
        cpu_adj = [
            a for a in result["threshold_adjustments"] if a.metric_name == "cpu_usage_percent"
        ]
        assert len(cpu_adj) > 0

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_recommend_no_adjustments_needed(self):
        toolkit = LearningToolkit()
        set_toolkit(toolkit)

        state = LearningState(
            learning_id="test-008",
            incident_outcomes=[
                IncidentOutcome(
                    incident_id="1", alert_type="high_cpu", was_automated=True, was_correct=True
                ),
                IncidentOutcome(
                    incident_id="2", alert_type="high_cpu", was_automated=True, was_correct=True
                ),
            ],
            reasoning_chain=[],
        )

        with patch(
            "shieldops.agents.learning.nodes.llm_structured", side_effect=RuntimeError("skip")
        ):
            result = await recommend_thresholds(state)

        # All correct — no adjustments needed
        assert len(result["threshold_adjustments"]) == 0

        set_toolkit(None)


class TestSynthesizeImprovementsNode:
    """Tests for synthesize_improvements node."""

    @pytest.mark.asyncio
    async def test_synthesize_full(self):
        toolkit = LearningToolkit()
        set_toolkit(toolkit)

        state = LearningState(
            learning_id="test-009",
            learning_start=datetime.now(UTC) - timedelta(seconds=5),
            total_incidents_analyzed=10,
            automation_accuracy=85.0,
            avg_resolution_time_ms=50000,
            pattern_insights=[
                PatternInsight(
                    pattern_id="p1",
                    alert_type="high_cpu",
                    description="test",
                    frequency=3,
                    common_root_cause="leak",
                ),
            ],
            recurring_pattern_count=1,
            playbook_updates=[
                PlaybookUpdate(
                    playbook_id="pb1",
                    alert_type="high_cpu",
                    update_type="modify_step",
                    title="Fix CPU playbook",
                ),
            ],
            threshold_adjustments=[],
            reasoning_chain=[],
        )

        with patch(
            "shieldops.agents.learning.nodes.llm_structured", side_effect=RuntimeError("skip")
        ):
            result = await synthesize_improvements(state)

        assert result["improvement_score"] > 0
        assert result["current_step"] == "complete"
        assert result["learning_duration_ms"] > 0

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_synthesize_high_accuracy_boosts_score(self):
        toolkit = LearningToolkit()
        set_toolkit(toolkit)

        state = LearningState(
            learning_id="test-010",
            learning_start=datetime.now(UTC),
            automation_accuracy=95.0,
            recurring_pattern_count=0,
            playbook_updates=[
                PlaybookUpdate(playbook_id="pb1", alert_type="x", update_type="new", title="t")
            ],
            reasoning_chain=[],
        )

        with patch(
            "shieldops.agents.learning.nodes.llm_structured", side_effect=RuntimeError("skip")
        ):
            result = await synthesize_improvements(state)

        # High accuracy + no recurring patterns + actionable updates = high score
        assert result["improvement_score"] >= 90

        set_toolkit(None)


# ===========================================================================
# Graph Routing Tests
# ===========================================================================


class TestGraphRouting:
    """Tests for conditional routing functions."""

    def test_should_recommend_playbooks_full(self):
        state = LearningState(learning_type="full")
        assert should_recommend_playbooks(state) == "recommend_playbooks"

    def test_should_skip_playbooks_pattern_only(self):
        state = LearningState(learning_type="pattern_only")
        assert should_recommend_playbooks(state) == "synthesize_improvements"

    def test_should_skip_playbooks_threshold_only(self):
        state = LearningState(learning_type="threshold_only")
        assert should_recommend_playbooks(state) == "recommend_thresholds"

    def test_should_skip_playbooks_on_error(self):
        state = LearningState(learning_type="full", error="broken")
        assert should_recommend_playbooks(state) == "synthesize_improvements"

    def test_should_recommend_thresholds_full(self):
        state = LearningState(learning_type="full")
        assert should_recommend_thresholds(state) == "recommend_thresholds"

    def test_should_skip_thresholds_pattern_only(self):
        state = LearningState(learning_type="pattern_only")
        assert should_recommend_thresholds(state) == "synthesize_improvements"

    def test_should_skip_thresholds_playbook_only(self):
        state = LearningState(learning_type="playbook_only")
        assert should_recommend_thresholds(state) == "synthesize_improvements"

    def test_should_skip_thresholds_on_error(self):
        state = LearningState(learning_type="full", error="broken")
        assert should_recommend_thresholds(state) == "synthesize_improvements"


class TestGraphConstruction:
    """Tests for graph construction."""

    def test_create_learning_graph(self):
        graph = create_learning_graph()
        compiled = graph.compile()
        assert compiled is not None


# ===========================================================================
# Runner Tests
# ===========================================================================


class TestLearningRunner:
    """Tests for LearningRunner."""

    def test_runner_init(self):
        runner = LearningRunner()
        assert runner.list_cycles() == []

    @pytest.mark.asyncio
    async def test_learn_returns_state(self):
        runner = LearningRunner()

        with patch.object(runner, "_app") as mock_app:
            mock_app.ainvoke = AsyncMock(
                return_value=LearningState(
                    learning_id="learn-test",
                    learning_type="full",
                    current_step="complete",
                    total_incidents_analyzed=10,
                    learning_start=datetime.now(UTC),
                ).model_dump()
            )

            result = await runner.learn()

        assert result.current_step == "complete"
        assert len(runner.list_cycles()) == 1

    @pytest.mark.asyncio
    async def test_learn_handles_error(self):
        runner = LearningRunner()

        with patch.object(runner, "_app") as mock_app:
            mock_app.ainvoke = AsyncMock(side_effect=RuntimeError("graph failed"))
            result = await runner.learn()

        assert result.current_step == "failed"
        assert result.error == "graph failed"
        assert len(runner.list_cycles()) == 1

    def test_list_cycles_empty(self):
        runner = LearningRunner()
        assert runner.list_cycles() == []

    def test_get_cycle_not_found(self):
        runner = LearningRunner()
        assert runner.get_cycle("nonexistent") is None


# ===========================================================================
# API Tests
# ===========================================================================


class TestLearningAPI:
    """Tests for learning API endpoints."""

    def _make_app(self):
        from shieldops.api.routes import learning as learning_module

        runner = LearningRunner()
        learning_module.set_runner(runner)

        from shieldops.api.app import create_app
        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole

        app = create_app()

        def _mock_admin_user():
            return UserResponse(
                id="test-admin",
                email="admin@test.com",
                name="Test Admin",
                role=UserRole.ADMIN,
                is_active=True,
            )

        app.dependency_overrides[get_current_user] = _mock_admin_user

        return TestClient(app), runner

    def test_list_cycles(self):
        client, _ = self._make_app()
        resp = client.get("/api/v1/learning/cycles")
        assert resp.status_code == 200
        assert resp.json()["cycles"] == []

    def test_get_cycle_not_found(self):
        client, _ = self._make_app()
        resp = client.get("/api/v1/learning/cycles/nonexistent")
        assert resp.status_code == 404

    def test_get_cycle_found(self):
        client, runner = self._make_app()
        state = LearningState(
            learning_id="learn-123",
            learning_type="full",
            current_step="complete",
            total_incidents_analyzed=10,
        )
        runner._cycles["learn-123"] = state

        resp = client.get("/api/v1/learning/cycles/learn-123")
        assert resp.status_code == 200
        assert resp.json()["learning_id"] == "learn-123"

    def test_trigger_cycle_async(self):
        client, _ = self._make_app()
        resp = client.post(
            "/api/v1/learning/cycles",
            json={
                "learning_type": "full",
                "period": "30d",
            },
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"

    def test_trigger_cycle_sync(self):
        client, runner = self._make_app()

        async def mock_learn(**kwargs):
            return LearningState(
                learning_id="learn-sync",
                current_step="complete",
                total_incidents_analyzed=5,
            )

        runner.learn = mock_learn

        resp = client.post(
            "/api/v1/learning/cycles/sync",
            json={
                "learning_type": "full",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["current_step"] == "complete"

    def test_list_patterns_no_cycles(self):
        client, _ = self._make_app()
        resp = client.get("/api/v1/learning/patterns")
        assert resp.status_code == 200
        assert resp.json()["patterns"] == []

    def test_list_patterns_with_data(self):
        client, runner = self._make_app()
        state = LearningState(
            learning_id="learn-pat",
            current_step="complete",
            pattern_insights=[
                PatternInsight(
                    pattern_id="p1",
                    alert_type="high_cpu",
                    description="Recurring CPU",
                    frequency=3,
                    common_root_cause="leak",
                ),
                PatternInsight(
                    pattern_id="p2",
                    alert_type="oom_kill",
                    description="OOM pattern",
                    frequency=2,
                    common_root_cause="limits",
                ),
            ],
        )
        runner._cycles["learn-pat"] = state

        resp = client.get("/api/v1/learning/patterns")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_list_patterns_filter_type(self):
        client, runner = self._make_app()
        state = LearningState(
            learning_id="learn-pat2",
            current_step="complete",
            pattern_insights=[
                PatternInsight(
                    pattern_id="p1",
                    alert_type="high_cpu",
                    description="CPU",
                    frequency=3,
                    common_root_cause="leak",
                ),
                PatternInsight(
                    pattern_id="p2",
                    alert_type="oom_kill",
                    description="OOM",
                    frequency=2,
                    common_root_cause="limits",
                ),
            ],
        )
        runner._cycles["learn-pat2"] = state

        resp = client.get("/api/v1/learning/patterns?alert_type=high_cpu")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_playbook_updates(self):
        client, runner = self._make_app()
        state = LearningState(
            learning_id="learn-pb",
            current_step="complete",
            playbook_updates=[
                PlaybookUpdate(
                    playbook_id="pb1",
                    alert_type="high_cpu",
                    update_type="new_playbook",
                    title="New CPU playbook",
                ),
            ],
        )
        runner._cycles["learn-pb"] = state

        resp = client.get("/api/v1/learning/playbook-updates")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_playbook_updates_filter(self):
        client, runner = self._make_app()
        state = LearningState(
            learning_id="learn-pb2",
            current_step="complete",
            playbook_updates=[
                PlaybookUpdate(
                    playbook_id="pb1",
                    alert_type="high_cpu",
                    update_type="new_playbook",
                    title="New",
                ),
                PlaybookUpdate(
                    playbook_id="pb2", alert_type="high_cpu", update_type="modify_step", title="Fix"
                ),
            ],
        )
        runner._cycles["learn-pb2"] = state

        resp = client.get("/api/v1/learning/playbook-updates?update_type=modify_step")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_threshold_adjustments(self):
        client, runner = self._make_app()
        state = LearningState(
            learning_id="learn-th",
            current_step="complete",
            threshold_adjustments=[
                ThresholdAdjustment(
                    adjustment_id="adj1",
                    metric_name="cpu_usage_percent",
                    current_threshold=80.0,
                    recommended_threshold=88.0,
                    direction="increase",
                    reason="too sensitive",
                ),
            ],
            estimated_false_positive_reduction=15.0,
        )
        runner._cycles["learn-th"] = state

        resp = client.get("/api/v1/learning/threshold-adjustments")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["estimated_fp_reduction"] == 15.0

    def test_list_threshold_adjustments_no_cycles(self):
        client, _ = self._make_app()
        resp = client.get("/api/v1/learning/threshold-adjustments")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ===========================================================================
# Model Tests
# ===========================================================================


class TestLearningModels:
    """Tests for learning data models."""

    def test_incident_outcome(self):
        o = IncidentOutcome(
            incident_id="inc-1",
            alert_type="high_cpu",
            root_cause="memory leak",
            resolution_action="restart_pod",
            was_automated=True,
            was_correct=True,
        )
        assert o.was_automated is True
        assert o.environment == Environment.PRODUCTION

    def test_pattern_insight(self):
        p = PatternInsight(
            pattern_id="p1",
            alert_type="high_cpu",
            description="Recurring CPU issues",
            frequency=5,
            common_root_cause="memory leak",
        )
        assert p.frequency == 5

    def test_playbook_update(self):
        pb = PlaybookUpdate(
            playbook_id="pb1",
            alert_type="high_cpu",
            update_type="new_playbook",
            title="New playbook",
            steps=["Step 1", "Step 2"],
        )
        assert len(pb.steps) == 2

    def test_threshold_adjustment(self):
        adj = ThresholdAdjustment(
            adjustment_id="adj1",
            metric_name="cpu_usage_percent",
            current_threshold=80.0,
            recommended_threshold=88.0,
            direction="increase",
        )
        assert adj.recommended_threshold > adj.current_threshold

    def test_learning_step(self):
        step = LearningStep(
            step_number=1,
            action="gather_outcomes",
            input_summary="test",
            output_summary="test",
        )
        assert step.step_number == 1

    def test_learning_state_defaults(self):
        state = LearningState()
        assert state.learning_type == "full"
        assert state.incident_outcomes == []
        assert state.pattern_insights == []
        assert state.playbook_updates == []
        assert state.threshold_adjustments == []
        assert state.current_step == "pending"
        assert state.error is None
