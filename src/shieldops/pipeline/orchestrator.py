"""Pipeline orchestrator: investigation -> recommendation -> remediation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from shieldops_investigate.models import (  # type: ignore[import-not-found]
    Hypothesis,
    InvestigationResult,
)

from shieldops.pipeline.models import (
    PipelineRun,
    PipelineStatus,
    RemediationRecommendation,
)
from shieldops.pipeline.recommender import RemediationRecommender
from shieldops.remediation.k8s_actions import K8sRemediationExecutor
from shieldops.remediation.models import (
    K8sRemediationRequest,
    RemediationStatus,
)
from shieldops.remediation.policy_gate import PolicyGate

logger = structlog.get_logger()


class PipelineOrchestrator:
    """Drives the full investigation-to-remediation lifecycle.

    1. Creates a ``PipelineRun`` and marks it *investigating*.
    2. Runs (or mocks) an investigation to produce hypotheses.
    3. Generates remediation recommendations via ``RemediationRecommender``.
    4. For auto-approved recommendations, evaluates the policy gate and
       executes the action through ``K8sRemediationExecutor``.
    5. Records results and marks the run *completed* or *failed*.
    """

    def __init__(
        self,
        executor: K8sRemediationExecutor | None = None,
        policy_gate: PolicyGate | None = None,
        recommender: RemediationRecommender | None = None,
    ) -> None:
        self._executor = executor or K8sRemediationExecutor()
        self._policy_gate = policy_gate or PolicyGate()
        self._recommender = recommender or RemediationRecommender()
        self._runs: dict[str, PipelineRun] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_pipeline(
        self,
        alert_name: str,
        namespace: str,
        service: str,
    ) -> PipelineRun:
        """Execute the full investigation-to-remediation pipeline.

        Args:
            alert_name: Name of the triggering alert.
            namespace: Kubernetes namespace for the affected workload.
            service: Name of the affected service / deployment.

        Returns:
            A ``PipelineRun`` with the final status, recommendations,
            and execution results.
        """
        run = PipelineRun(
            alert_name=alert_name,
            namespace=namespace,
            service=service,
        )
        self._runs[run.id] = run

        logger.info(
            "pipeline_started",
            run_id=run.id,
            alert=alert_name,
            namespace=namespace,
            service=service,
        )

        try:
            # Step 1 — Investigate
            run.add_timeline_entry(
                PipelineStatus.INVESTIGATING,
                "Starting investigation",
            )
            investigation = await self._run_investigation(
                alert_name,
                namespace,
                service,
            )
            run.investigation_result = investigation.model_dump(
                mode="json",
            )

            # Step 2 — Recommend
            run.add_timeline_entry(
                PipelineStatus.RECOMMENDING,
                f"Investigation complete with {len(investigation.hypotheses)} hypotheses",
            )
            recommendations = self._recommender.recommend(investigation)
            run.remediation_actions = recommendations

            if not recommendations:
                run.add_timeline_entry(
                    PipelineStatus.COMPLETED,
                    "No actionable recommendations generated",
                )
                run.completed_at = datetime.now(UTC)
                return run

            # Step 3 — Execute auto-approved recommendations
            needs_approval = any(not r.auto_approve for r in recommendations)
            if needs_approval:
                run.add_timeline_entry(
                    PipelineStatus.AWAITING_APPROVAL,
                    "Some recommendations require manual approval",
                )

            run.add_timeline_entry(
                PipelineStatus.REMEDIATING,
                f"Executing {len(recommendations)} recommendation(s)",
            )

            any_failed = False
            for rec in recommendations:
                if not rec.auto_approve:
                    logger.info(
                        "recommendation_skipped_awaiting_approval",
                        run_id=run.id,
                        title=rec.hypothesis_title,
                    )
                    continue

                result = await self._execute_recommendation(
                    rec,
                    namespace,
                )
                if result.get("status") == RemediationStatus.FAILED:
                    any_failed = True

            # Finalise
            final_status = PipelineStatus.FAILED if any_failed else PipelineStatus.COMPLETED
            run.add_timeline_entry(final_status, "Pipeline finished")
            run.completed_at = datetime.now(UTC)

        except Exception as exc:
            logger.error(
                "pipeline_failed",
                run_id=run.id,
                error=str(exc),
            )
            run.add_timeline_entry(
                PipelineStatus.FAILED,
                f"Pipeline error: {exc}",
            )
            run.completed_at = datetime.now(UTC)

        return run

    def get_run(self, run_id: str) -> PipelineRun | None:
        """Retrieve a pipeline run by ID."""
        return self._runs.get(run_id)

    def list_runs(
        self,
        limit: int = 50,
    ) -> list[PipelineRun]:
        """Return recent pipeline runs, newest first."""
        runs = sorted(
            self._runs.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )
        return runs[:limit]

    async def approve_recommendations(
        self,
        run_id: str,
        indices: list[int] | None = None,
    ) -> PipelineRun:
        """Approve and execute pending recommendations for a run.

        Args:
            run_id: The pipeline run identifier.
            indices: Optional list of recommendation indices to approve.
                If ``None``, all non-auto-approved recommendations are
                executed.

        Returns:
            The updated ``PipelineRun``.

        Raises:
            ValueError: If the run is not found or not awaiting approval.
        """
        run = self._runs.get(run_id)
        if run is None:
            raise ValueError(f"Pipeline run {run_id} not found")

        run.add_timeline_entry(
            PipelineStatus.REMEDIATING,
            "Executing approved recommendations",
        )

        targets = (
            [run.remediation_actions[i] for i in indices]
            if indices
            else [r for r in run.remediation_actions if not r.auto_approve and not r.executed]
        )

        any_failed = False
        for rec in targets:
            result = await self._execute_recommendation(
                rec,
                run.namespace,
            )
            if result.get("status") == RemediationStatus.FAILED:
                any_failed = True

        final_status = PipelineStatus.FAILED if any_failed else PipelineStatus.COMPLETED
        run.add_timeline_entry(final_status, "Approved actions executed")
        run.completed_at = datetime.now(UTC)
        return run

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _run_investigation(
        self,
        alert_name: str,
        namespace: str,
        service: str,
    ) -> InvestigationResult:
        """Produce an investigation result.

        In production this would invoke the investigation toolkit. For
        now it returns a placeholder result with common hypotheses so
        the rest of the pipeline can be exercised end-to-end.
        """
        logger.info(
            "investigation_mock",
            alert=alert_name,
            namespace=namespace,
            service=service,
        )
        return InvestigationResult(
            alert_name=alert_name,
            namespace=namespace,
            service=service,
            hypotheses=[
                Hypothesis(
                    title="Deployment Regression",
                    description=(
                        "A recent deployment may have introduced a regression causing the alert."
                    ),
                    confidence=0.85,
                    suggested_action="Rollback to previous revision",
                ),
                Hypothesis(
                    title="Memory Leak / OOM",
                    description=("Container memory usage trending toward the configured limit."),
                    confidence=0.65,
                    suggested_action="Increase memory limit",
                ),
                Hypothesis(
                    title="CPU Resource Exhaustion",
                    description=("CPU throttling detected across pod replicas."),
                    confidence=0.45,
                    suggested_action="Scale deployment horizontally",
                ),
            ],
            summary=(
                f"Investigation for alert '{alert_name}' on "
                f"{namespace}/{service} produced 3 hypotheses."
            ),
            duration_seconds=2.5,
        )

    async def _execute_recommendation(
        self,
        rec: RemediationRecommendation,
        namespace: str,
    ) -> dict[str, Any]:
        """Evaluate policy and execute a single recommendation."""
        # Policy gate check
        decision = await self._policy_gate.evaluate_action(
            action_type=rec.action_type,
            namespace=namespace,
            resource_name=rec.target_resource,
            environment="production",
            parameters=rec.parameters,
        )

        if not decision.allowed:
            logger.warning(
                "recommendation_policy_denied",
                title=rec.hypothesis_title,
                reason=decision.reason,
            )
            rec.executed = True
            rec.execution_result = {
                "status": RemediationStatus.DENIED,
                "reason": decision.reason,
            }
            return rec.execution_result

        # Execute the remediation action
        request = K8sRemediationRequest(
            action_type=rec.action_type,
            namespace=namespace,
            resource_name=rec.target_resource,
            parameters=rec.parameters,
            description=(f"Pipeline auto-remediation for: {rec.hypothesis_title}"),
            initiated_by="pipeline_orchestrator",
        )

        result = await self._executor.execute(request)
        rec.executed = True
        rec.execution_result = {
            "status": result.status,
            "message": result.message,
            "action_id": result.id,
        }

        logger.info(
            "recommendation_executed",
            title=rec.hypothesis_title,
            action=rec.action_type,
            status=result.status,
        )

        return rec.execution_result
