"""Tests for the investigation-to-remediation pipeline module.

Covers:
- shieldops.pipeline.models (PipelineStatus, PipelineRun, RemediationRecommendation, TimelineEntry)
- shieldops.pipeline.recommender (RemediationRecommender)
- shieldops.pipeline.orchestrator (PipelineOrchestrator)
"""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.pipeline.models import (
    PipelineRun,
    PipelineStatus,
    RemediationRecommendation,
    TimelineEntry,
)
from shieldops.pipeline.recommender import (
    AUTO_APPROVE_THRESHOLD,
    RemediationRecommender,
)
from shieldops.remediation.models import (
    K8sActionType,
    PolicyDecision,
    RemediationResult,
    RemediationStatus,
    RiskLevel,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hypothesis(title: str, confidence: float) -> MagicMock:
    """Create a mock Hypothesis with the given title and confidence."""
    h = MagicMock()
    h.title = title
    h.confidence = confidence
    return h


def _make_investigation_result(
    hypotheses: list[MagicMock] | None = None,
    service: str = "my-service",
) -> MagicMock:
    """Create a mock InvestigationResult."""
    result = MagicMock()
    result.hypotheses = hypotheses or []
    result.service = service
    result.model_dump = MagicMock(return_value={"alert_name": "test", "hypotheses": []})
    return result


def _make_policy_decision(allowed: bool = True) -> PolicyDecision:
    return PolicyDecision(
        allowed=allowed,
        reason="all policies passed" if allowed else "denied by policy",
        risk_level=RiskLevel.MEDIUM,
    )


def _make_remediation_result(
    status: RemediationStatus = RemediationStatus.SUCCESS,
) -> RemediationResult:
    return RemediationResult(
        action_type=K8sActionType.RESTART_DEPLOYMENT,
        namespace="default",
        resource_name="my-service",
        environment="production",
        status=status,
        message="ok",
    )


# ---------------------------------------------------------------------------
# PipelineStatus enum tests
# ---------------------------------------------------------------------------


class TestPipelineStatus:
    def test_pending(self) -> None:
        assert PipelineStatus.PENDING == "pending"

    def test_investigating(self) -> None:
        assert PipelineStatus.INVESTIGATING == "investigating"

    def test_recommending(self) -> None:
        assert PipelineStatus.RECOMMENDING == "recommending"

    def test_awaiting_approval(self) -> None:
        assert PipelineStatus.AWAITING_APPROVAL == "awaiting_approval"

    def test_remediating(self) -> None:
        assert PipelineStatus.REMEDIATING == "remediating"

    def test_verifying(self) -> None:
        assert PipelineStatus.VERIFYING == "verifying"

    def test_completed(self) -> None:
        assert PipelineStatus.COMPLETED == "completed"

    def test_failed(self) -> None:
        assert PipelineStatus.FAILED == "failed"

    def test_all_values_present(self) -> None:
        expected = {
            "pending",
            "investigating",
            "recommending",
            "awaiting_approval",
            "remediating",
            "verifying",
            "completed",
            "failed",
        }
        assert {s.value for s in PipelineStatus} == expected


# ---------------------------------------------------------------------------
# TimelineEntry tests
# ---------------------------------------------------------------------------


class TestTimelineEntry:
    def test_default_timestamp_is_utc(self) -> None:
        entry = TimelineEntry(status=PipelineStatus.PENDING)
        assert entry.timestamp.tzinfo is not None
        assert entry.timestamp.tzinfo == UTC

    def test_default_message_is_empty(self) -> None:
        entry = TimelineEntry(status=PipelineStatus.INVESTIGATING)
        assert entry.message == ""

    def test_custom_message(self) -> None:
        entry = TimelineEntry(
            status=PipelineStatus.COMPLETED,
            message="All done",
        )
        assert entry.message == "All done"
        assert entry.status == PipelineStatus.COMPLETED


# ---------------------------------------------------------------------------
# RemediationRecommendation tests
# ---------------------------------------------------------------------------


class TestRemediationRecommendation:
    def test_defaults(self) -> None:
        rec = RemediationRecommendation(
            hypothesis_title="Memory Leak / OOM",
            confidence=0.9,
            action_type=K8sActionType.UPDATE_RESOURCE_LIMITS,
        )
        assert rec.auto_approve is False
        assert rec.executed is False
        assert rec.execution_result == {}
        assert rec.target_resource == ""
        assert rec.parameters == {}

    def test_auto_approve_can_be_set(self) -> None:
        rec = RemediationRecommendation(
            hypothesis_title="Deployment Regression",
            confidence=0.85,
            action_type=K8sActionType.ROLLBACK_DEPLOYMENT,
            auto_approve=True,
        )
        assert rec.auto_approve is True

    def test_confidence_above_1_raises_validation_error(self) -> None:
        with pytest.raises(ValueError):
            RemediationRecommendation(
                hypothesis_title="Bad",
                confidence=1.5,
                action_type=K8sActionType.RESTART_DEPLOYMENT,
            )

    def test_confidence_below_0_raises_validation_error(self) -> None:
        with pytest.raises(ValueError):
            RemediationRecommendation(
                hypothesis_title="Bad",
                confidence=-0.1,
                action_type=K8sActionType.RESTART_DEPLOYMENT,
            )


# ---------------------------------------------------------------------------
# PipelineRun tests
# ---------------------------------------------------------------------------


class TestPipelineRun:
    def test_creation_defaults(self) -> None:
        run = PipelineRun(
            alert_name="HighCPU",
            namespace="default",
        )
        assert run.status == PipelineStatus.PENDING
        assert run.service is None
        assert run.investigation_result == {}
        assert run.remediation_actions == []
        assert run.timeline == []
        assert run.completed_at is None
        assert run.id  # UUID should be non-empty

    def test_id_is_unique(self) -> None:
        r1 = PipelineRun(alert_name="A", namespace="ns")
        r2 = PipelineRun(alert_name="A", namespace="ns")
        assert r1.id != r2.id

    def test_created_at_is_utc(self) -> None:
        run = PipelineRun(alert_name="A", namespace="ns")
        assert run.created_at.tzinfo == UTC

    def test_add_timeline_entry(self) -> None:
        run = PipelineRun(alert_name="Test", namespace="default")
        run.add_timeline_entry(PipelineStatus.INVESTIGATING, "Starting")
        assert run.status == PipelineStatus.INVESTIGATING
        assert len(run.timeline) == 1
        assert run.timeline[0].status == PipelineStatus.INVESTIGATING
        assert run.timeline[0].message == "Starting"

    def test_add_multiple_timeline_entries(self) -> None:
        run = PipelineRun(alert_name="Test", namespace="default")
        run.add_timeline_entry(PipelineStatus.INVESTIGATING, "Step 1")
        run.add_timeline_entry(PipelineStatus.RECOMMENDING, "Step 2")
        run.add_timeline_entry(PipelineStatus.COMPLETED, "Done")
        assert len(run.timeline) == 3
        assert run.status == PipelineStatus.COMPLETED


# ---------------------------------------------------------------------------
# RemediationRecommender tests
# ---------------------------------------------------------------------------


class TestRemediationRecommender:
    def setup_method(self) -> None:
        self.recommender = RemediationRecommender()

    def test_deployment_regression_maps_to_rollback(self) -> None:
        investigation = _make_investigation_result(
            hypotheses=[_make_hypothesis("Deployment Regression", 0.9)],
        )
        recs = self.recommender.recommend(investigation)
        assert len(recs) == 1
        assert recs[0].action_type == K8sActionType.ROLLBACK_DEPLOYMENT
        assert recs[0].hypothesis_title == "Deployment Regression"

    def test_memory_leak_maps_to_update_resource_limits(self) -> None:
        investigation = _make_investigation_result(
            hypotheses=[_make_hypothesis("Memory Leak / OOM", 0.7)],
        )
        recs = self.recommender.recommend(investigation)
        assert len(recs) == 1
        assert recs[0].action_type == K8sActionType.UPDATE_RESOURCE_LIMITS

    def test_crashloopbackoff_maps_to_restart(self) -> None:
        investigation = _make_investigation_result(
            hypotheses=[_make_hypothesis("CrashLoopBackOff", 0.6)],
        )
        recs = self.recommender.recommend(investigation)
        assert len(recs) == 1
        assert recs[0].action_type == K8sActionType.RESTART_DEPLOYMENT

    def test_cpu_exhaustion_maps_to_scale(self) -> None:
        investigation = _make_investigation_result(
            hypotheses=[_make_hypothesis("CPU Resource Exhaustion", 0.5)],
        )
        recs = self.recommender.recommend(investigation)
        assert len(recs) == 1
        assert recs[0].action_type == K8sActionType.SCALE_DEPLOYMENT
        assert recs[0].parameters.get("replicas") == 3

    def test_unknown_hypothesis_yields_no_recommendation(self) -> None:
        investigation = _make_investigation_result(
            hypotheses=[_make_hypothesis("Cosmic Ray Bit Flip", 0.3)],
        )
        recs = self.recommender.recommend(investigation)
        assert len(recs) == 0

    def test_high_confidence_sets_auto_approve_true(self) -> None:
        investigation = _make_investigation_result(
            hypotheses=[_make_hypothesis("Deployment Regression", 0.85)],
        )
        recs = self.recommender.recommend(investigation)
        assert len(recs) == 1
        assert recs[0].confidence == 0.85
        assert recs[0].confidence > AUTO_APPROVE_THRESHOLD
        assert recs[0].auto_approve is True

    def test_low_confidence_sets_auto_approve_false(self) -> None:
        investigation = _make_investigation_result(
            hypotheses=[_make_hypothesis("Memory Leak / OOM", 0.8)],
        )
        recs = self.recommender.recommend(investigation)
        assert len(recs) == 1
        assert recs[0].confidence == 0.8
        assert recs[0].confidence <= AUTO_APPROVE_THRESHOLD
        assert recs[0].auto_approve is False

    def test_threshold_boundary_exactly_0_8_is_not_auto_approved(self) -> None:
        """Confidence must be strictly > 0.8 to be auto-approved."""
        investigation = _make_investigation_result(
            hypotheses=[_make_hypothesis("Deployment Regression", 0.8)],
        )
        recs = self.recommender.recommend(investigation)
        assert recs[0].auto_approve is False

    def test_multiple_hypotheses_sorted_by_confidence(self) -> None:
        investigation = _make_investigation_result(
            hypotheses=[
                _make_hypothesis("CPU Resource Exhaustion", 0.45),
                _make_hypothesis("Deployment Regression", 0.85),
                _make_hypothesis("Memory Leak / OOM", 0.65),
            ],
        )
        recs = self.recommender.recommend(investigation)
        assert len(recs) == 3
        # Should be sorted highest confidence first
        assert recs[0].confidence == 0.85
        assert recs[1].confidence == 0.65
        assert recs[2].confidence == 0.45

    def test_target_resource_uses_service_name(self) -> None:
        investigation = _make_investigation_result(
            hypotheses=[_make_hypothesis("Deployment Regression", 0.9)],
            service="payment-svc",
        )
        recs = self.recommender.recommend(investigation)
        assert recs[0].target_resource == "payment-svc"

    def test_service_none_uses_unknown(self) -> None:
        investigation = _make_investigation_result(
            hypotheses=[_make_hypothesis("Deployment Regression", 0.9)],
            service=None,
        )
        # service=None means investigation_result.service returns None
        # The recommender falls back to "unknown"
        investigation.service = None
        recs = self.recommender.recommend(investigation)
        assert recs[0].target_resource == "unknown"


# ---------------------------------------------------------------------------
# PipelineOrchestrator tests
# ---------------------------------------------------------------------------


class TestPipelineOrchestrator:
    def setup_method(self) -> None:
        self.mock_executor = MagicMock()
        self.mock_executor.execute = AsyncMock(
            return_value=_make_remediation_result(),
        )
        self.mock_policy_gate = MagicMock()
        self.mock_policy_gate.evaluate_action = AsyncMock(
            return_value=_make_policy_decision(allowed=True),
        )
        self.mock_recommender = MagicMock(spec=RemediationRecommender)

    def _make_orchestrator(self):  # -> PipelineOrchestrator
        from shieldops.pipeline.orchestrator import PipelineOrchestrator

        return PipelineOrchestrator(
            executor=self.mock_executor,
            policy_gate=self.mock_policy_gate,
            recommender=self.mock_recommender,
        )

    @pytest.mark.asyncio
    async def test_run_pipeline_creates_pipeline_run(self) -> None:
        self.mock_recommender.recommend.return_value = []
        orch = self._make_orchestrator()
        run = await orch.run_pipeline(
            alert_name="HighCPU",
            namespace="default",
            service="api-server",
        )
        assert isinstance(run, PipelineRun)
        assert run.alert_name == "HighCPU"
        assert run.namespace == "default"
        assert run.service == "api-server"

    @pytest.mark.asyncio
    async def test_run_pipeline_sets_status_through_lifecycle(self) -> None:
        """Pipeline should progress through INVESTIGATING -> RECOMMENDING -> ... -> COMPLETED."""
        self.mock_recommender.recommend.return_value = []
        orch = self._make_orchestrator()
        run = await orch.run_pipeline(
            alert_name="TestAlert",
            namespace="default",
            service="svc",
        )
        # With no recommendations, the pipeline ends at COMPLETED
        assert run.status == PipelineStatus.COMPLETED
        assert run.completed_at is not None
        # Timeline should contain INVESTIGATING, RECOMMENDING, COMPLETED
        statuses = [e.status for e in run.timeline]
        assert PipelineStatus.INVESTIGATING in statuses
        assert PipelineStatus.RECOMMENDING in statuses
        assert PipelineStatus.COMPLETED in statuses

    @pytest.mark.asyncio
    async def test_run_pipeline_with_auto_approved_recommendations(self) -> None:
        rec = RemediationRecommendation(
            hypothesis_title="Deployment Regression",
            confidence=0.9,
            action_type=K8sActionType.ROLLBACK_DEPLOYMENT,
            target_resource="my-svc",
            auto_approve=True,
        )
        self.mock_recommender.recommend.return_value = [rec]
        orch = self._make_orchestrator()
        run = await orch.run_pipeline(
            alert_name="HighErrorRate",
            namespace="default",
            service="my-svc",
        )
        assert run.status == PipelineStatus.COMPLETED
        self.mock_policy_gate.evaluate_action.assert_awaited_once()
        self.mock_executor.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_pipeline_skips_non_auto_approved(self) -> None:
        rec = RemediationRecommendation(
            hypothesis_title="Memory Leak / OOM",
            confidence=0.6,
            action_type=K8sActionType.UPDATE_RESOURCE_LIMITS,
            target_resource="my-svc",
            auto_approve=False,
        )
        self.mock_recommender.recommend.return_value = [rec]
        orch = self._make_orchestrator()
        run = await orch.run_pipeline(
            alert_name="OOM",
            namespace="default",
            service="my-svc",
        )
        assert run.status == PipelineStatus.COMPLETED
        # Non-auto-approved should NOT be executed
        self.mock_executor.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_pipeline_sets_awaiting_approval_when_needed(self) -> None:
        rec = RemediationRecommendation(
            hypothesis_title="Memory Leak / OOM",
            confidence=0.6,
            action_type=K8sActionType.UPDATE_RESOURCE_LIMITS,
            auto_approve=False,
        )
        self.mock_recommender.recommend.return_value = [rec]
        orch = self._make_orchestrator()
        run = await orch.run_pipeline(
            alert_name="OOM",
            namespace="default",
            service="my-svc",
        )
        statuses = [e.status for e in run.timeline]
        assert PipelineStatus.AWAITING_APPROVAL in statuses

    @pytest.mark.asyncio
    async def test_run_pipeline_marks_failed_on_execution_failure(self) -> None:
        rec = RemediationRecommendation(
            hypothesis_title="Deployment Regression",
            confidence=0.9,
            action_type=K8sActionType.ROLLBACK_DEPLOYMENT,
            target_resource="my-svc",
            auto_approve=True,
        )
        self.mock_recommender.recommend.return_value = [rec]
        self.mock_executor.execute = AsyncMock(
            return_value=_make_remediation_result(status=RemediationStatus.FAILED),
        )
        orch = self._make_orchestrator()
        run = await orch.run_pipeline(
            alert_name="Err",
            namespace="default",
            service="my-svc",
        )
        assert run.status == PipelineStatus.FAILED

    @pytest.mark.asyncio
    async def test_run_pipeline_handles_exception(self) -> None:
        self.mock_recommender.recommend.side_effect = RuntimeError("boom")
        orch = self._make_orchestrator()
        run = await orch.run_pipeline(
            alert_name="Err",
            namespace="default",
            service="svc",
        )
        assert run.status == PipelineStatus.FAILED
        assert run.completed_at is not None

    def test_get_run_returns_none_for_unknown_id(self) -> None:
        orch = self._make_orchestrator()
        assert orch.get_run("nonexistent-id-123") is None

    @pytest.mark.asyncio
    async def test_get_run_returns_existing_run(self) -> None:
        self.mock_recommender.recommend.return_value = []
        orch = self._make_orchestrator()
        run = await orch.run_pipeline(
            alert_name="Test",
            namespace="default",
            service="svc",
        )
        retrieved = orch.get_run(run.id)
        assert retrieved is not None
        assert retrieved.id == run.id

    @pytest.mark.asyncio
    async def test_list_runs_returns_recent_runs(self) -> None:
        self.mock_recommender.recommend.return_value = []
        orch = self._make_orchestrator()
        ids = []
        for i in range(3):
            run = await orch.run_pipeline(
                alert_name=f"Alert-{i}",
                namespace="default",
                service="svc",
            )
            ids.append(run.id)

        runs = orch.list_runs()
        assert len(runs) == 3
        # Newest first
        returned_ids = [r.id for r in runs]
        assert returned_ids == list(reversed(ids))

    @pytest.mark.asyncio
    async def test_list_runs_respects_limit(self) -> None:
        self.mock_recommender.recommend.return_value = []
        orch = self._make_orchestrator()
        for i in range(5):
            await orch.run_pipeline(
                alert_name=f"Alert-{i}",
                namespace="default",
                service="svc",
            )
        runs = orch.list_runs(limit=2)
        assert len(runs) == 2

    @pytest.mark.asyncio
    async def test_approve_recommendations_raises_for_unknown_run(self) -> None:
        orch = self._make_orchestrator()
        with pytest.raises(ValueError, match="not found"):
            await orch.approve_recommendations("nonexistent-id")

    @pytest.mark.asyncio
    async def test_approve_recommendations_executes_pending(self) -> None:
        rec = RemediationRecommendation(
            hypothesis_title="Memory Leak / OOM",
            confidence=0.6,
            action_type=K8sActionType.UPDATE_RESOURCE_LIMITS,
            target_resource="my-svc",
            auto_approve=False,
        )
        self.mock_recommender.recommend.return_value = [rec]
        orch = self._make_orchestrator()
        run = await orch.run_pipeline(
            alert_name="OOM",
            namespace="default",
            service="my-svc",
        )
        # The recommendation was not executed during run_pipeline
        self.mock_executor.execute.assert_not_awaited()

        # Now approve it
        updated = await orch.approve_recommendations(run.id)
        assert updated.status == PipelineStatus.COMPLETED
        self.mock_policy_gate.evaluate_action.assert_awaited()
        self.mock_executor.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_policy_denied_sets_denied_result(self) -> None:
        rec = RemediationRecommendation(
            hypothesis_title="Deployment Regression",
            confidence=0.9,
            action_type=K8sActionType.ROLLBACK_DEPLOYMENT,
            target_resource="my-svc",
            auto_approve=True,
        )
        self.mock_recommender.recommend.return_value = [rec]
        self.mock_policy_gate.evaluate_action = AsyncMock(
            return_value=_make_policy_decision(allowed=False),
        )
        orch = self._make_orchestrator()
        run = await orch.run_pipeline(
            alert_name="Err",
            namespace="default",
            service="my-svc",
        )
        # Policy denied does not call executor
        self.mock_executor.execute.assert_not_awaited()
        # The recommendation should be marked executed with DENIED status
        assert run.remediation_actions[0].executed is True
        assert run.remediation_actions[0].execution_result["status"] == RemediationStatus.DENIED
