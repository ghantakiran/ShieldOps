"""Canary deployment tracking with progressive traffic shifting and rollback decisions.

Tracks canary deployments through progressive traffic ramp-up stages, records
health metrics comparing canary vs baseline, and provides automatic rollback
recommendations when canary metrics degrade.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class CanaryPhase(enum.StrEnum):
    INITIALIZED = "initialized"
    RAMPING = "ramping"
    STABLE = "stable"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"
    PAUSED = "paused"


class CanaryMetricResult(enum.StrEnum):
    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


# -- Models --------------------------------------------------------------------


class CanaryDeployment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    version: str
    baseline_version: str = ""
    traffic_pct: float = 0.0
    target_traffic_pct: float = 100.0
    phase: CanaryPhase = CanaryPhase.INITIALIZED
    steps: list[float] = Field(default_factory=lambda: [5.0, 25.0, 50.0, 75.0, 100.0])
    current_step_index: int = 0
    success_threshold: float = 0.95
    error_rate_limit: float = 0.05
    started_at: float | None = None
    completed_at: float | None = None
    owner: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class CanaryMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str
    metric_name: str
    baseline_value: float = 0.0
    canary_value: float = 0.0
    result: CanaryMetricResult = CanaryMetricResult.PASS
    recorded_at: float = Field(default_factory=time.time)


# -- Tracker ------------------------------------------------------------------


class CanaryDeploymentTracker:
    """Track canary deployments with progressive traffic shifting and rollback decisions.

    Parameters
    ----------
    max_deployments:
        Maximum number of canary deployments to store.
    max_metrics:
        Maximum number of metric records to store.
    """

    def __init__(
        self,
        max_deployments: int = 1000,
        max_metrics: int = 50000,
    ) -> None:
        self._deployments: dict[str, CanaryDeployment] = {}
        self._metrics: list[CanaryMetric] = []
        self._max_deployments = max_deployments
        self._max_metrics = max_metrics

    def create_deployment(
        self,
        service: str,
        version: str,
        **kw: Any,
    ) -> CanaryDeployment:
        """Create a new canary deployment.

        Raises ``ValueError`` if the maximum number of deployments has been reached.
        """
        if len(self._deployments) >= self._max_deployments:
            raise ValueError(f"Maximum deployments limit reached: {self._max_deployments}")
        deployment = CanaryDeployment(service=service, version=version, **kw)
        self._deployments[deployment.id] = deployment
        logger.info(
            "canary_deployment_created",
            deployment_id=deployment.id,
            service=service,
            version=version,
        )
        return deployment

    def start_canary(self, deployment_id: str) -> CanaryDeployment | None:
        """Start a canary deployment by setting it to RAMPING phase.

        Returns ``None`` if the deployment is not found.
        """
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            return None
        deployment.phase = CanaryPhase.RAMPING
        deployment.started_at = time.time()
        if deployment.steps:
            deployment.traffic_pct = deployment.steps[0]
            deployment.current_step_index = 0
        logger.info(
            "canary_started",
            deployment_id=deployment_id,
            traffic_pct=deployment.traffic_pct,
        )
        return deployment

    def advance_canary(self, deployment_id: str) -> CanaryDeployment | None:
        """Advance the canary to the next traffic step.

        Returns ``None`` if the deployment is not found or is already in a
        terminal phase (PROMOTED or ROLLED_BACK).
        """
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            return None
        if deployment.phase in (CanaryPhase.PROMOTED, CanaryPhase.ROLLED_BACK):
            return None

        next_index = deployment.current_step_index + 1
        if next_index >= len(deployment.steps):
            # Already at last step — mark as STABLE
            deployment.phase = CanaryPhase.STABLE
            logger.info(
                "canary_stable",
                deployment_id=deployment_id,
                traffic_pct=deployment.traffic_pct,
            )
            return deployment

        deployment.current_step_index = next_index
        deployment.traffic_pct = deployment.steps[next_index]

        # If we've reached the last step, set to STABLE
        if next_index >= len(deployment.steps) - 1:
            deployment.phase = CanaryPhase.STABLE
        else:
            deployment.phase = CanaryPhase.RAMPING

        logger.info(
            "canary_advanced",
            deployment_id=deployment_id,
            step_index=next_index,
            traffic_pct=deployment.traffic_pct,
            phase=deployment.phase,
        )
        return deployment

    def promote_canary(self, deployment_id: str) -> CanaryDeployment | None:
        """Promote the canary to full traffic (100%).

        Returns ``None`` if the deployment is not found.
        """
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            return None
        deployment.phase = CanaryPhase.PROMOTED
        deployment.traffic_pct = 100.0
        deployment.completed_at = time.time()
        logger.info("canary_promoted", deployment_id=deployment_id)
        return deployment

    def rollback_canary(self, deployment_id: str) -> CanaryDeployment | None:
        """Roll back the canary deployment to zero traffic.

        Returns ``None`` if the deployment is not found.
        """
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            return None
        deployment.phase = CanaryPhase.ROLLED_BACK
        deployment.traffic_pct = 0.0
        deployment.completed_at = time.time()
        logger.info("canary_rolled_back", deployment_id=deployment_id)
        return deployment

    def pause_canary(self, deployment_id: str) -> CanaryDeployment | None:
        """Pause the canary deployment.

        Returns ``None`` if the deployment is not found.
        """
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            return None
        deployment.phase = CanaryPhase.PAUSED
        logger.info("canary_paused", deployment_id=deployment_id)
        return deployment

    def record_metric(
        self,
        deployment_id: str,
        metric_name: str,
        baseline_value: float,
        canary_value: float,
    ) -> CanaryMetric:
        """Record a metric comparison between canary and baseline.

        The result is computed by comparing the canary value against the
        baseline value using the deployment's error_rate_limit:
        - FAIL if canary_value > baseline_value * (1 + error_rate_limit)
        - INCONCLUSIVE if canary_value > baseline_value * (1 + error_rate_limit * 0.5)
        - PASS otherwise

        Raises ``ValueError`` if the deployment is not found.
        """
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            raise ValueError(f"Deployment not found: {deployment_id}")

        # Compute result
        fail_threshold = baseline_value * (1 + deployment.error_rate_limit)
        warn_threshold = baseline_value * (1 + deployment.error_rate_limit * 0.5)

        if canary_value > fail_threshold:
            result = CanaryMetricResult.FAIL
        elif canary_value > warn_threshold:
            result = CanaryMetricResult.INCONCLUSIVE
        else:
            result = CanaryMetricResult.PASS

        metric = CanaryMetric(
            deployment_id=deployment_id,
            metric_name=metric_name,
            baseline_value=baseline_value,
            canary_value=canary_value,
            result=result,
        )
        self._metrics.append(metric)

        # Trim to max_metrics
        if len(self._metrics) > self._max_metrics:
            self._metrics = self._metrics[-self._max_metrics :]

        logger.info(
            "canary_metric_recorded",
            deployment_id=deployment_id,
            metric_name=metric_name,
            result=result,
        )
        return metric

    def get_deployment(self, deployment_id: str) -> CanaryDeployment | None:
        """Return a deployment by ID, or ``None`` if not found."""
        return self._deployments.get(deployment_id)

    def list_deployments(
        self,
        service: str | None = None,
        phase: CanaryPhase | None = None,
    ) -> list[CanaryDeployment]:
        """List deployments with optional filters."""
        deployments = list(self._deployments.values())
        if service is not None:
            deployments = [d for d in deployments if d.service == service]
        if phase is not None:
            deployments = [d for d in deployments if d.phase == phase]
        return deployments

    def get_metrics(self, deployment_id: str) -> list[CanaryMetric]:
        """Return all metrics for a deployment."""
        return [m for m in self._metrics if m.deployment_id == deployment_id]

    def should_rollback(self, deployment_id: str) -> bool:
        """Return ``True`` if any metric for this deployment has result=FAIL."""
        for metric in self._metrics:
            if metric.deployment_id == deployment_id and metric.result == CanaryMetricResult.FAIL:
                return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about canary deployments."""
        by_phase: dict[str, int] = {}
        for deployment in self._deployments.values():
            phase_key = deployment.phase.value
            by_phase[phase_key] = by_phase.get(phase_key, 0) + 1

        promoted = by_phase.get(CanaryPhase.PROMOTED.value, 0)
        rolled_back = by_phase.get(CanaryPhase.ROLLED_BACK.value, 0)
        completed = promoted + rolled_back
        promotion_rate = (promoted / completed * 100) if completed > 0 else 0.0
        rollback_rate = (rolled_back / completed * 100) if completed > 0 else 0.0

        return {
            "total_deployments": len(self._deployments),
            "by_phase": by_phase,
            "total_metrics": len(self._metrics),
            "promotion_rate": promotion_rate,
            "rollback_rate": rollback_rate,
        }
