"""Data quality monitoring with alerting on degradation.

Monitors data quality metrics across pipelines, evaluates quality rules,
and generates alerts when quality scores degrade below configured thresholds.
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


class QualityDimension(enum.StrEnum):
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"


class QualityStatus(enum.StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# -- Models --------------------------------------------------------------------


class QualityRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    dataset: str
    dimension: QualityDimension
    expression: str = ""
    threshold: float = 0.95
    enabled: bool = True
    owner: str = ""
    created_at: float = Field(default_factory=time.time)


class QualityCheckResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str
    dataset: str
    dimension: QualityDimension
    score: float = 1.0
    records_checked: int = 0
    records_failed: int = 0
    status: QualityStatus = QualityStatus.HEALTHY
    details: str = ""
    checked_at: float = Field(default_factory=time.time)


class QualityAlert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str
    dataset: str
    dimension: QualityDimension
    previous_score: float
    current_score: float
    threshold: float
    message: str = ""
    triggered_at: float = Field(default_factory=time.time)


# -- Monitor ------------------------------------------------------------------


class DataQualityMonitor:
    """Monitor data quality metrics across pipelines with alerting on degradation.

    Parameters
    ----------
    max_rules:
        Maximum number of quality rules to store.
    max_results:
        Maximum number of check results to store.
    alert_cooldown_seconds:
        Minimum seconds between alerts for the same rule.
    """

    def __init__(
        self,
        max_rules: int = 1000,
        max_results: int = 100000,
        alert_cooldown_seconds: int = 3600,
    ) -> None:
        self._rules: dict[str, QualityRule] = {}
        self._results: list[QualityCheckResult] = []
        self._alerts: list[QualityAlert] = []
        self._max_rules = max_rules
        self._max_results = max_results
        self._alert_cooldown_seconds = alert_cooldown_seconds
        self._last_alert_time: dict[str, float] = {}

    def create_rule(
        self,
        name: str,
        dataset: str,
        dimension: QualityDimension,
        **kw: Any,
    ) -> QualityRule:
        """Create a new quality rule.

        Raises ``ValueError`` if the maximum number of rules has been reached.
        """
        if len(self._rules) >= self._max_rules:
            raise ValueError(f"Maximum rules limit reached: {self._max_rules}")
        rule = QualityRule(name=name, dataset=dataset, dimension=dimension, **kw)
        self._rules[rule.id] = rule
        logger.info(
            "quality_rule_created",
            rule_id=rule.id,
            name=name,
            dataset=dataset,
            dimension=dimension,
        )
        return rule

    def run_check(
        self,
        rule_id: str,
        score: float,
        records_checked: int = 0,
        records_failed: int = 0,
        details: str = "",
    ) -> QualityCheckResult:
        """Run a quality check against a rule and generate alerts on degradation.

        Raises ``ValueError`` if the rule is not found.
        """
        rule = self._rules.get(rule_id)
        if rule is None:
            raise ValueError(f"Rule not found: {rule_id}")

        # Compute status based on score vs threshold
        if score >= rule.threshold:
            status = QualityStatus.HEALTHY
        elif score >= rule.threshold * 0.8:
            status = QualityStatus.WARNING
        else:
            status = QualityStatus.CRITICAL

        result = QualityCheckResult(
            rule_id=rule_id,
            dataset=rule.dataset,
            dimension=rule.dimension,
            score=score,
            records_checked=records_checked,
            records_failed=records_failed,
            status=status,
            details=details,
        )
        self._results.append(result)

        # Trim results to max_results
        if len(self._results) > self._max_results:
            self._results = self._results[-self._max_results :]

        # Generate alert if status is not HEALTHY and cooldown has elapsed
        if status != QualityStatus.HEALTHY:
            now = time.time()
            last_alert = self._last_alert_time.get(rule_id, 0.0)
            if now - last_alert >= self._alert_cooldown_seconds:
                # Find previous score for this rule
                previous_score = self._get_previous_score(rule_id, result.id)
                alert = QualityAlert(
                    rule_id=rule_id,
                    dataset=rule.dataset,
                    dimension=rule.dimension,
                    previous_score=previous_score,
                    current_score=score,
                    threshold=rule.threshold,
                    message=(
                        f"Quality degradation on {rule.dataset}/{rule.dimension}: "
                        f"score={score:.3f}, threshold={rule.threshold:.3f}, status={status}"
                    ),
                )
                self._alerts.append(alert)
                self._last_alert_time[rule_id] = now
                logger.warning(
                    "quality_alert_triggered",
                    rule_id=rule_id,
                    dataset=rule.dataset,
                    score=score,
                    status=status,
                )

        logger.info(
            "quality_check_completed",
            rule_id=rule_id,
            score=score,
            status=status,
        )
        return result

    def get_rule(self, rule_id: str) -> QualityRule | None:
        """Return a rule by ID, or ``None`` if not found."""
        return self._rules.get(rule_id)

    def list_rules(
        self,
        dataset: str | None = None,
        dimension: QualityDimension | None = None,
    ) -> list[QualityRule]:
        """List rules with optional filters."""
        rules = list(self._rules.values())
        if dataset is not None:
            rules = [r for r in rules if r.dataset == dataset]
        if dimension is not None:
            rules = [r for r in rules if r.dimension == dimension]
        return rules

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule. Returns ``True`` if the rule existed."""
        return self._rules.pop(rule_id, None) is not None

    def get_check_history(
        self,
        rule_id: str | None = None,
        dataset: str | None = None,
        limit: int = 100,
    ) -> list[QualityCheckResult]:
        """Return check results with optional filters, most recent last."""
        results = list(self._results)
        if rule_id is not None:
            results = [r for r in results if r.rule_id == rule_id]
        if dataset is not None:
            results = [r for r in results if r.dataset == dataset]
        return results[-limit:]

    def list_alerts(
        self,
        dataset: str | None = None,
        limit: int = 50,
    ) -> list[QualityAlert]:
        """Return alerts with optional dataset filter, most recent last."""
        alerts = list(self._alerts)
        if dataset is not None:
            alerts = [a for a in alerts if a.dataset == dataset]
        return alerts[-limit:]

    def get_dataset_health(self, dataset: str) -> dict[str, Any]:
        """Return aggregated health for a dataset across all dimensions.

        Returns a dict with ``dimensions``, ``overall_status``,
        ``total_checks``, and ``last_check_at``.
        """
        # Collect latest check result per dimension for this dataset
        latest_by_dim: dict[QualityDimension, QualityCheckResult] = {}
        total_checks = 0
        last_check_at: float | None = None

        for result in self._results:
            if result.dataset != dataset:
                continue
            total_checks += 1
            if last_check_at is None or result.checked_at > last_check_at:
                last_check_at = result.checked_at
            existing = latest_by_dim.get(result.dimension)
            if existing is None or result.checked_at > existing.checked_at:
                latest_by_dim[result.dimension] = result

        dimensions: dict[str, float] = {dim: res.score for dim, res in latest_by_dim.items()}

        # Worst status wins
        status_priority = {
            QualityStatus.CRITICAL: 3,
            QualityStatus.WARNING: 2,
            QualityStatus.UNKNOWN: 1,
            QualityStatus.HEALTHY: 0,
        }
        overall_status = QualityStatus.HEALTHY
        for res in latest_by_dim.values():
            if status_priority.get(res.status, 0) > status_priority.get(overall_status, 0):
                overall_status = res.status

        return {
            "dimensions": dimensions,
            "overall_status": overall_status,
            "total_checks": total_checks,
            "last_check_at": last_check_at,
        }

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        datasets: set[str] = set()
        dimension_distribution: dict[str, int] = {}
        status_distribution: dict[str, int] = {}

        for rule in self._rules.values():
            datasets.add(rule.dataset)
            dim_key = rule.dimension.value
            dimension_distribution[dim_key] = dimension_distribution.get(dim_key, 0) + 1

        for result in self._results:
            st_key = result.status.value
            status_distribution[st_key] = status_distribution.get(st_key, 0) + 1

        return {
            "total_rules": len(self._rules),
            "total_checks": len(self._results),
            "total_alerts": len(self._alerts),
            "datasets_monitored": len(datasets),
            "dimension_distribution": dimension_distribution,
            "status_distribution": status_distribution,
        }

    # -- Private helpers -------------------------------------------------------

    def _get_previous_score(self, rule_id: str, exclude_id: str) -> float:
        """Find the most recent score for a rule, excluding the given result."""
        for result in reversed(self._results):
            if result.rule_id == rule_id and result.id != exclude_id:
                return result.score
        return 1.0
