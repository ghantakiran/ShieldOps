"""SLA violation tracking with breach detection and escalation."""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class ViolationSeverity(enum.StrEnum):
    WARNING = "warning"
    BREACH = "breach"
    CRITICAL_BREACH = "critical_breach"


class SLAMetricType(enum.StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    RESPONSE_TIME = "response_time"


# -- Models --------------------------------------------------------------------


class SLATarget(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service: str
    metric_type: SLAMetricType
    target_value: float
    threshold_warning: float
    threshold_breach: float
    period_hours: int = 24
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class SLAViolation(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    target_id: str
    service: str
    metric_type: SLAMetricType
    current_value: float
    target_value: float
    severity: ViolationSeverity
    message: str = ""
    detected_at: float = Field(default_factory=time.time)
    resolved_at: float | None = None


class SLAReport(BaseModel):
    service: str
    total_targets: int = 0
    violations: int = 0
    compliance_pct: float = 100.0
    active_breaches: int = 0


# -- Tracker -------------------------------------------------------------------


class SLAViolationTracker:
    """Track SLA targets and detect violations for escalation.

    Parameters
    ----------
    max_targets:
        Maximum number of SLA targets to store.
    max_violations:
        Maximum number of violations to retain.
    """

    def __init__(
        self,
        max_targets: int = 500,
        max_violations: int = 10000,
    ) -> None:
        self._targets: dict[str, SLATarget] = {}
        self._violations: list[SLAViolation] = []
        self._max_targets = max_targets
        self._max_violations = max_violations

    def create_target(
        self,
        service: str,
        metric_type: SLAMetricType,
        target_value: float,
        threshold_warning: float,
        threshold_breach: float,
        period_hours: int = 24,
        metadata: dict[str, Any] | None = None,
    ) -> SLATarget:
        if len(self._targets) >= self._max_targets:
            raise ValueError(f"Maximum targets limit reached: {self._max_targets}")
        target = SLATarget(
            service=service,
            metric_type=metric_type,
            target_value=target_value,
            threshold_warning=threshold_warning,
            threshold_breach=threshold_breach,
            period_hours=period_hours,
            metadata=metadata or {},
        )
        self._targets[target.id] = target
        logger.info(
            "sla_target_created",
            target_id=target.id,
            service=service,
            metric_type=metric_type,
        )
        return target

    def check_violation(
        self,
        target_id: str,
        current_value: float,
    ) -> SLAViolation | None:
        target = self._targets.get(target_id)
        if target is None:
            raise ValueError(f"SLA target not found: {target_id}")

        # Determine severity by comparing current_value against thresholds.
        # For metrics where higher is worse (latency, error_rate, response_time)
        # a breach means current_value exceeds the threshold.
        # For metrics where lower is worse (availability, throughput)
        # a breach means current_value falls below the threshold.
        higher_is_worse = target.metric_type in (
            SLAMetricType.LATENCY,
            SLAMetricType.ERROR_RATE,
            SLAMetricType.RESPONSE_TIME,
        )

        severity: ViolationSeverity | None = None
        if higher_is_worse:
            if current_value >= target.threshold_breach * 1.5:
                severity = ViolationSeverity.CRITICAL_BREACH
            elif current_value >= target.threshold_breach:
                severity = ViolationSeverity.BREACH
            elif current_value >= target.threshold_warning:
                severity = ViolationSeverity.WARNING
        else:
            if current_value <= target.threshold_breach * 0.5:
                severity = ViolationSeverity.CRITICAL_BREACH
            elif current_value <= target.threshold_breach:
                severity = ViolationSeverity.BREACH
            elif current_value <= target.threshold_warning:
                severity = ViolationSeverity.WARNING

        if severity is None:
            return None

        message = (
            f"{target.metric_type} for {target.service}: "
            f"current={current_value}, target={target.target_value}, "
            f"severity={severity}"
        )

        violation = SLAViolation(
            target_id=target_id,
            service=target.service,
            metric_type=target.metric_type,
            current_value=current_value,
            target_value=target.target_value,
            severity=severity,
            message=message,
        )

        if len(self._violations) >= self._max_violations:
            self._violations = self._violations[-(self._max_violations // 2) :]

        self._violations.append(violation)
        logger.info(
            "sla_violation_detected",
            violation_id=violation.id,
            service=target.service,
            severity=severity,
        )
        return violation

    def resolve_violation(self, violation_id: str) -> SLAViolation | None:
        for violation in self._violations:
            if violation.id == violation_id:
                violation.resolved_at = time.time()
                logger.info("sla_violation_resolved", violation_id=violation_id)
                return violation
        return None

    def get_target(self, target_id: str) -> SLATarget | None:
        return self._targets.get(target_id)

    def list_targets(
        self,
        service: str | None = None,
    ) -> list[SLATarget]:
        targets = list(self._targets.values())
        if service:
            targets = [t for t in targets if t.service == service]
        return targets

    def delete_target(self, target_id: str) -> bool:
        return self._targets.pop(target_id, None) is not None

    def list_violations(
        self,
        service: str | None = None,
        severity: ViolationSeverity | None = None,
        active_only: bool = False,
    ) -> list[SLAViolation]:
        violations = list(self._violations)
        if service:
            violations = [v for v in violations if v.service == service]
        if severity:
            violations = [v for v in violations if v.severity == severity]
        if active_only:
            violations = [v for v in violations if v.resolved_at is None]
        return violations

    def get_service_report(self, service: str) -> SLAReport:
        targets = [t for t in self._targets.values() if t.service == service]
        total_targets = len(targets)
        service_violations = [v for v in self._violations if v.service == service]
        active_breaches = sum(
            1
            for v in service_violations
            if v.resolved_at is None
            and v.severity in (ViolationSeverity.BREACH, ViolationSeverity.CRITICAL_BREACH)
        )
        total_violations = len(service_violations)
        compliance_pct = (
            round((1 - total_violations / max(total_targets, 1)) * 100, 2)
            if total_targets
            else 100.0
        )
        compliance_pct = max(0.0, compliance_pct)
        return SLAReport(
            service=service,
            total_targets=total_targets,
            violations=total_violations,
            compliance_pct=compliance_pct,
            active_breaches=active_breaches,
        )

    def get_stats(self) -> dict[str, Any]:
        total_violations = len(self._violations)
        active_violations = sum(1 for v in self._violations if v.resolved_at is None)
        warnings = sum(1 for v in self._violations if v.severity == ViolationSeverity.WARNING)
        breaches = sum(1 for v in self._violations if v.severity == ViolationSeverity.BREACH)
        critical_breaches = sum(
            1 for v in self._violations if v.severity == ViolationSeverity.CRITICAL_BREACH
        )
        return {
            "total_targets": len(self._targets),
            "total_violations": total_violations,
            "active_violations": active_violations,
            "warnings": warnings,
            "breaches": breaches,
            "critical_breaches": critical_breaches,
        }
