"""Service dependency SLA tracking with cascade risk detection.

Tracks SLA compliance between dependent services, evaluates measured values
against SLA targets, and detects cascade failure risks when upstream services
have multiple breached SLAs.
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


class SLAType(enum.StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"


class ComplianceStatus(enum.StrEnum):
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    NOT_MEASURED = "not_measured"


# -- Models --------------------------------------------------------------------


class DependencySLA(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    upstream_service: str
    downstream_service: str
    sla_type: SLAType
    target_value: float
    warning_threshold: float = 0.0
    current_value: float | None = None
    status: ComplianceStatus = ComplianceStatus.NOT_MEASURED
    last_evaluated_at: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class SLAEvaluation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sla_id: str
    measured_value: float
    status: ComplianceStatus
    evaluated_at: float = Field(default_factory=time.time)
    details: str = ""


class CascadeRisk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_service: str
    affected_services: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    sla_breaches: int = 0
    description: str = ""
    detected_at: float = Field(default_factory=time.time)


# -- Tracker ------------------------------------------------------------------


class DependencySLATracker:
    """Track SLA compliance between dependent services with cascade risk detection.

    Parameters
    ----------
    max_slas:
        Maximum number of SLA definitions to store.
    max_evaluations:
        Maximum number of evaluation records to store.
    """

    def __init__(
        self,
        max_slas: int = 2000,
        max_evaluations: int = 100000,
    ) -> None:
        self._slas: dict[str, DependencySLA] = {}
        self._evaluations: list[SLAEvaluation] = []
        self._cascade_risks: list[CascadeRisk] = []
        self._max_slas = max_slas
        self._max_evaluations = max_evaluations

    def create_sla(
        self,
        upstream_service: str,
        downstream_service: str,
        sla_type: SLAType,
        target_value: float,
        **kw: Any,
    ) -> DependencySLA:
        """Create a new dependency SLA.

        If ``warning_threshold`` is not provided (or is 0.0), it defaults to
        ``target_value * 0.9``.

        Raises ``ValueError`` if the maximum number of SLAs has been reached.
        """
        if len(self._slas) >= self._max_slas:
            raise ValueError(f"Maximum SLAs limit reached: {self._max_slas}")

        # Set default warning_threshold if not provided
        warning_threshold = kw.pop("warning_threshold", 0.0)
        if not warning_threshold:
            warning_threshold = target_value * 0.9

        sla = DependencySLA(
            upstream_service=upstream_service,
            downstream_service=downstream_service,
            sla_type=sla_type,
            target_value=target_value,
            warning_threshold=warning_threshold,
            **kw,
        )
        self._slas[sla.id] = sla
        logger.info(
            "dependency_sla_created",
            sla_id=sla.id,
            upstream=upstream_service,
            downstream=downstream_service,
            sla_type=sla_type,
            target=target_value,
        )
        return sla

    def evaluate_sla(
        self,
        sla_id: str,
        measured_value: float,
        details: str = "",
    ) -> SLAEvaluation:
        """Evaluate a measured value against an SLA target.

        For AVAILABILITY and THROUGHPUT: higher is better.
        - >= target = COMPLIANT
        - >= warning_threshold = AT_RISK
        - else BREACHED

        For LATENCY and ERROR_RATE: lower is better.
        - <= target = COMPLIANT
        - <= warning_threshold (target * 1.1) = AT_RISK
        - else BREACHED

        Updates the SLA's current_value, status, and last_evaluated_at.

        Raises ``ValueError`` if the SLA is not found.
        """
        sla = self._slas.get(sla_id)
        if sla is None:
            raise ValueError(f"SLA not found: {sla_id}")

        # Compute compliance status based on SLA type
        if sla.sla_type in (SLAType.AVAILABILITY, SLAType.THROUGHPUT):
            # Higher is better
            if measured_value >= sla.target_value:
                status = ComplianceStatus.COMPLIANT
            elif measured_value >= sla.warning_threshold:
                status = ComplianceStatus.AT_RISK
            else:
                status = ComplianceStatus.BREACHED
        else:
            # LATENCY and ERROR_RATE: lower is better
            warning = sla.target_value * 1.1
            if measured_value <= sla.target_value:
                status = ComplianceStatus.COMPLIANT
            elif measured_value <= warning:
                status = ComplianceStatus.AT_RISK
            else:
                status = ComplianceStatus.BREACHED

        # Update the SLA record
        sla.current_value = measured_value
        sla.status = status
        sla.last_evaluated_at = time.time()

        evaluation = SLAEvaluation(
            sla_id=sla_id,
            measured_value=measured_value,
            status=status,
            details=details,
        )
        self._evaluations.append(evaluation)

        # Trim to max_evaluations
        if len(self._evaluations) > self._max_evaluations:
            self._evaluations = self._evaluations[-self._max_evaluations :]

        logger.info(
            "sla_evaluated",
            sla_id=sla_id,
            measured_value=measured_value,
            status=status,
        )
        return evaluation

    def get_sla(self, sla_id: str) -> DependencySLA | None:
        """Return an SLA by ID, or ``None`` if not found."""
        return self._slas.get(sla_id)

    def list_slas(
        self,
        upstream: str | None = None,
        downstream: str | None = None,
        status: ComplianceStatus | None = None,
    ) -> list[DependencySLA]:
        """List SLAs with optional filters."""
        slas = list(self._slas.values())
        if upstream is not None:
            slas = [s for s in slas if s.upstream_service == upstream]
        if downstream is not None:
            slas = [s for s in slas if s.downstream_service == downstream]
        if status is not None:
            slas = [s for s in slas if s.status == status]
        return slas

    def delete_sla(self, sla_id: str) -> bool:
        """Delete an SLA. Returns ``True`` if the SLA existed."""
        return self._slas.pop(sla_id, None) is not None

    def get_evaluations(
        self,
        sla_id: str | None = None,
        limit: int = 100,
    ) -> list[SLAEvaluation]:
        """Return evaluation records with optional SLA filter, most recent last."""
        evaluations = list(self._evaluations)
        if sla_id is not None:
            evaluations = [e for e in evaluations if e.sla_id == sla_id]
        return evaluations[-limit:]

    def detect_cascade_risks(self) -> list[CascadeRisk]:
        """Detect cascade failure risks from upstream services with multiple breaches.

        Groups breached SLAs by upstream service. If a service has:
        - 2 breaches: risk_level = "medium"
        - 3+ breaches: risk_level = "high"

        Affected services are all downstream services of the breaching upstream.
        """
        # Group breached SLAs by upstream service
        breaches_by_upstream: dict[str, list[DependencySLA]] = {}
        for sla in self._slas.values():
            if sla.status == ComplianceStatus.BREACHED:
                breaches_by_upstream.setdefault(sla.upstream_service, []).append(sla)

        risks: list[CascadeRisk] = []
        for upstream, breached_slas in breaches_by_upstream.items():
            breach_count = len(breached_slas)
            if breach_count < 2:
                continue

            risk_level = "high" if breach_count >= 3 else "medium"

            # Collect all unique downstream services affected
            affected = list({s.downstream_service for s in breached_slas})

            risk = CascadeRisk(
                source_service=upstream,
                affected_services=affected,
                risk_level=risk_level,
                sla_breaches=breach_count,
                description=(
                    f"Service {upstream} has {breach_count} breached SLAs "
                    f"affecting {len(affected)} downstream service(s)"
                ),
            )
            risks.append(risk)
            logger.warning(
                "cascade_risk_detected",
                source_service=upstream,
                risk_level=risk_level,
                breach_count=breach_count,
                affected_services=affected,
            )

        self._cascade_risks = risks
        return risks

    def get_service_report(self, service: str) -> dict[str, Any]:
        """Return a report for a service covering both upstream and downstream SLAs.

        Returns a dict with ``as_upstream``, ``as_downstream``, ``breaches``,
        and ``compliance_rate``.
        """
        as_upstream = [s for s in self._slas.values() if s.upstream_service == service]
        as_downstream = [s for s in self._slas.values() if s.downstream_service == service]

        all_slas = as_upstream + as_downstream
        breaches = sum(1 for s in all_slas if s.status == ComplianceStatus.BREACHED)
        measured = [s for s in all_slas if s.status != ComplianceStatus.NOT_MEASURED]
        compliant_count = sum(1 for s in measured if s.status == ComplianceStatus.COMPLIANT)
        compliance_rate = (compliant_count / len(measured) * 100) if measured else 0.0

        return {
            "as_upstream": as_upstream,
            "as_downstream": as_downstream,
            "breaches": breaches,
            "compliance_rate": compliance_rate,
        }

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        compliant = sum(1 for s in self._slas.values() if s.status == ComplianceStatus.COMPLIANT)
        at_risk = sum(1 for s in self._slas.values() if s.status == ComplianceStatus.AT_RISK)
        breached = sum(1 for s in self._slas.values() if s.status == ComplianceStatus.BREACHED)

        return {
            "total_slas": len(self._slas),
            "total_evaluations": len(self._evaluations),
            "compliant": compliant,
            "at_risk": at_risk,
            "breached": breached,
            "cascade_risks": len(self._cascade_risks),
        }
