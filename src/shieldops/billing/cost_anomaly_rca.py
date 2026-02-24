"""Cost Anomaly Root Cause Analyzer — trace cost spikes to resources and changes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RootCauseCategory(StrEnum):
    SCALING_EVENT = "scaling_event"
    MISCONFIGURATION = "misconfiguration"
    TRAFFIC_SPIKE = "traffic_spike"
    DATA_TRANSFER = "data_transfer"
    NEW_RESOURCE = "new_resource"
    PRICING_CHANGE = "pricing_change"


class InvestigationStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    ROOT_CAUSE_FOUND = "root_cause_found"
    REMEDIATED = "remediated"
    FALSE_POSITIVE = "false_positive"


class ImpactSeverity(StrEnum):
    TRIVIAL = "trivial"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    SEVERE = "severe"


# --- Models ---


class CostSpike(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    resource_id: str = ""
    spike_amount: float = 0.0
    baseline_amount: float = 0.0
    deviation_pct: float = 0.0
    detected_at: float = 0.0
    status: InvestigationStatus = InvestigationStatus.OPEN
    root_cause_category: RootCauseCategory | None = None
    created_at: float = Field(default_factory=time.time)


class RootCauseFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    spike_id: str = ""
    category: RootCauseCategory = RootCauseCategory.SCALING_EVENT
    description: str = ""
    confidence_pct: float = 0.0
    excess_spend: float = 0.0
    remediation_suggestion: str = ""
    created_at: float = Field(default_factory=time.time)


class CostRCAReport(BaseModel):
    total_spikes: int = 0
    open_investigations: int = 0
    resolved_count: int = 0
    total_excess_spend: float = 0.0
    avg_deviation_pct: float = 0.0
    category_distribution: dict[str, int] = Field(default_factory=dict)
    severity_distribution: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostAnomalyRootCauseAnalyzer:
    """Trace cost spikes to specific resources, services, and infrastructure changes."""

    def __init__(
        self,
        max_spikes: int = 100000,
        deviation_threshold_pct: float = 25.0,
    ) -> None:
        self._max_spikes = max_spikes
        self._deviation_threshold_pct = deviation_threshold_pct
        self._spikes: list[CostSpike] = []
        self._findings: list[RootCauseFinding] = []
        logger.info(
            "cost_anomaly_rca.initialized",
            max_spikes=max_spikes,
            deviation_threshold_pct=deviation_threshold_pct,
        )

    def record_spike(
        self,
        service_name: str,
        resource_id: str,
        spike_amount: float,
        baseline_amount: float,
        detected_at: float = 0.0,
    ) -> CostSpike:
        """Record a cost spike and auto-calculate the deviation percentage."""
        deviation_pct = 0.0
        if baseline_amount > 0:
            deviation_pct = round((spike_amount - baseline_amount) / baseline_amount * 100, 2)

        spike = CostSpike(
            service_name=service_name,
            resource_id=resource_id,
            spike_amount=spike_amount,
            baseline_amount=baseline_amount,
            deviation_pct=deviation_pct,
            detected_at=detected_at if detected_at > 0 else time.time(),
        )
        self._spikes.append(spike)
        if len(self._spikes) > self._max_spikes:
            self._spikes = self._spikes[-self._max_spikes :]
        logger.info(
            "cost_anomaly_rca.spike_recorded",
            spike_id=spike.id,
            service_name=service_name,
            resource_id=resource_id,
            deviation_pct=deviation_pct,
        )
        return spike

    def get_spike(self, spike_id: str) -> CostSpike | None:
        """Retrieve a single spike by ID."""
        for s in self._spikes:
            if s.id == spike_id:
                return s
        return None

    def list_spikes(
        self,
        status: InvestigationStatus | None = None,
        service_name: str | None = None,
        limit: int = 100,
    ) -> list[CostSpike]:
        """List spikes with optional filtering by status and service name."""
        results = list(self._spikes)
        if status is not None:
            results = [s for s in results if s.status == status]
        if service_name is not None:
            results = [s for s in results if s.service_name == service_name]
        return results[-limit:]

    def analyze_root_cause(self, spike_id: str) -> RootCauseFinding | None:
        """Determine root cause category based on deviation magnitude.

        Category logic:
        - >200% deviation -> MISCONFIGURATION (likely runaway or wrong config)
        - >100% deviation -> SCALING_EVENT (doubled cost indicates scaling)
        - >50% deviation  -> TRAFFIC_SPIKE (moderate spike from traffic)
        - else            -> NEW_RESOURCE (small deviations from new provisions)

        Confidence scales with deviation magnitude.
        """
        spike = self.get_spike(spike_id)
        if spike is None:
            return None

        deviation = abs(spike.deviation_pct)
        excess_spend = max(0.0, spike.spike_amount - spike.baseline_amount)

        # Determine category based on deviation thresholds
        if deviation > 200:
            category = RootCauseCategory.MISCONFIGURATION
            description = (
                f"Extreme cost deviation of {spike.deviation_pct:.1f}% on "
                f"{spike.service_name}/{spike.resource_id} suggests misconfiguration "
                f"or runaway resource"
            )
            confidence = min(95.0, 70.0 + deviation * 0.05)
            remediation = (
                "Audit resource configuration immediately. Check for oversized instances, "
                "disabled auto-scaling limits, or accidental multi-region deployment."
            )
        elif deviation > 100:
            category = RootCauseCategory.SCALING_EVENT
            description = (
                f"Cost doubled ({spike.deviation_pct:.1f}% deviation) on "
                f"{spike.service_name}/{spike.resource_id} — likely auto-scaling or "
                f"manual scale-up event"
            )
            confidence = min(90.0, 60.0 + deviation * 0.1)
            remediation = (
                "Review scaling policies and recent deployments. Confirm the scale-up "
                "was intentional and set budget alerts for this service."
            )
        elif deviation > 50:
            category = RootCauseCategory.TRAFFIC_SPIKE
            description = (
                f"Moderate cost increase ({spike.deviation_pct:.1f}% deviation) on "
                f"{spike.service_name}/{spike.resource_id} correlates with traffic spike"
            )
            confidence = min(85.0, 50.0 + deviation * 0.2)
            remediation = (
                "Validate traffic patterns and consider CDN caching, request throttling, "
                "or reserved capacity to reduce spike impact."
            )
        else:
            category = RootCauseCategory.NEW_RESOURCE
            description = (
                f"Minor cost increase ({spike.deviation_pct:.1f}% deviation) on "
                f"{spike.service_name}/{spike.resource_id} — possibly a new resource "
                f"or service tier change"
            )
            confidence = min(75.0, 40.0 + deviation * 0.3)
            remediation = (
                "Review recent provisioning activity. Tag the new resource for cost "
                "tracking and ensure it is included in budget forecasts."
            )

        confidence = round(confidence, 1)

        finding = RootCauseFinding(
            spike_id=spike_id,
            category=category,
            description=description,
            confidence_pct=confidence,
            excess_spend=round(excess_spend, 2),
            remediation_suggestion=remediation,
        )
        self._findings.append(finding)
        if len(self._findings) > self._max_spikes:
            self._findings = self._findings[-self._max_spikes :]

        # Update spike status
        spike.status = InvestigationStatus.ROOT_CAUSE_FOUND
        spike.root_cause_category = category

        logger.info(
            "cost_anomaly_rca.root_cause_analyzed",
            spike_id=spike_id,
            category=category,
            confidence_pct=confidence,
            excess_spend=round(excess_spend, 2),
        )
        return finding

    def correlate_with_changes(self, spike_id: str) -> list[dict[str, Any]]:
        """Find other spikes within +/-1 hour of this spike's detected_at time.

        Returns correlated spikes grouped by whether they share the same service.
        """
        spike = self.get_spike(spike_id)
        if spike is None:
            return []

        window_seconds = 3600  # 1 hour
        lower_bound = spike.detected_at - window_seconds
        upper_bound = spike.detected_at + window_seconds

        correlations: list[dict[str, Any]] = []
        for other in self._spikes:
            if other.id == spike_id:
                continue
            if lower_bound <= other.detected_at <= upper_bound:
                correlations.append(
                    {
                        "spike_id": other.id,
                        "service_name": other.service_name,
                        "resource_id": other.resource_id,
                        "deviation_pct": other.deviation_pct,
                        "spike_amount": other.spike_amount,
                        "same_service": other.service_name == spike.service_name,
                        "time_offset_seconds": round(other.detected_at - spike.detected_at, 1),
                    }
                )

        correlations.sort(key=lambda c: abs(c["time_offset_seconds"]))
        logger.info(
            "cost_anomaly_rca.correlations_found",
            spike_id=spike_id,
            correlated_count=len(correlations),
        )
        return correlations

    def identify_top_offenders(self, limit: int = 20) -> list[dict[str, Any]]:
        """Group spikes by service_name, sum excess spend, and sort descending."""
        service_totals: dict[str, dict[str, Any]] = {}
        for spike in self._spikes:
            excess = max(0.0, spike.spike_amount - spike.baseline_amount)
            if spike.service_name not in service_totals:
                service_totals[spike.service_name] = {
                    "service_name": spike.service_name,
                    "spike_count": 0,
                    "total_excess_spend": 0.0,
                    "avg_deviation_pct": 0.0,
                    "max_deviation_pct": 0.0,
                }
            entry = service_totals[spike.service_name]
            entry["spike_count"] += 1
            entry["total_excess_spend"] += excess
            entry["max_deviation_pct"] = max(entry["max_deviation_pct"], spike.deviation_pct)

        # Calculate averages
        for entry in service_totals.values():
            service_spikes = [s for s in self._spikes if s.service_name == entry["service_name"]]
            if service_spikes:
                entry["avg_deviation_pct"] = round(
                    sum(s.deviation_pct for s in service_spikes) / len(service_spikes), 2
                )
            entry["total_excess_spend"] = round(entry["total_excess_spend"], 2)

        offenders = sorted(
            service_totals.values(), key=lambda x: x["total_excess_spend"], reverse=True
        )
        return offenders[:limit]

    def calculate_excess_spend(self, service_name: str | None = None) -> dict[str, Any]:
        """Calculate total excess spend (spike_amount - baseline_amount).

        Optionally filter by service_name.
        """
        spikes = list(self._spikes)
        if service_name is not None:
            spikes = [s for s in spikes if s.service_name == service_name]

        total_spike = sum(s.spike_amount for s in spikes)
        total_baseline = sum(s.baseline_amount for s in spikes)
        total_excess = max(0.0, total_spike - total_baseline)

        # Per-service breakdown
        service_breakdown: dict[str, float] = {}
        for s in spikes:
            excess = max(0.0, s.spike_amount - s.baseline_amount)
            service_breakdown[s.service_name] = service_breakdown.get(s.service_name, 0.0) + excess

        return {
            "total_spike_amount": round(total_spike, 2),
            "total_baseline_amount": round(total_baseline, 2),
            "total_excess_spend": round(total_excess, 2),
            "spike_count": len(spikes),
            "service_breakdown": {k: round(v, 2) for k, v in service_breakdown.items()},
            "filter_service": service_name,
        }

    def update_spike_status(
        self,
        spike_id: str,
        status: InvestigationStatus,
        root_cause_category: RootCauseCategory | None = None,
    ) -> bool:
        """Update the investigation status and optional root cause category of a spike."""
        spike = self.get_spike(spike_id)
        if spike is None:
            return False
        spike.status = status
        if root_cause_category is not None:
            spike.root_cause_category = root_cause_category
        logger.info(
            "cost_anomaly_rca.spike_status_updated",
            spike_id=spike_id,
            status=status,
            root_cause_category=root_cause_category,
        )
        return True

    def _classify_severity(self, spike: CostSpike) -> ImpactSeverity:
        """Classify impact severity based on deviation percentage and excess amount."""
        excess = max(0.0, spike.spike_amount - spike.baseline_amount)
        deviation = abs(spike.deviation_pct)

        if deviation > 200 or excess > 10000:
            return ImpactSeverity.SEVERE
        if deviation > 100 or excess > 5000:
            return ImpactSeverity.MAJOR
        if deviation > 50 or excess > 1000:
            return ImpactSeverity.MODERATE
        if deviation > 25 or excess > 100:
            return ImpactSeverity.MINOR
        return ImpactSeverity.TRIVIAL

    def generate_rca_report(self) -> CostRCAReport:
        """Generate a comprehensive root cause analysis report across all spikes."""
        total = len(self._spikes)
        open_count = sum(
            1
            for s in self._spikes
            if s.status in (InvestigationStatus.OPEN, InvestigationStatus.INVESTIGATING)
        )
        resolved_count = sum(
            1
            for s in self._spikes
            if s.status
            in (
                InvestigationStatus.ROOT_CAUSE_FOUND,
                InvestigationStatus.REMEDIATED,
                InvestigationStatus.FALSE_POSITIVE,
            )
        )

        total_excess = sum(max(0.0, s.spike_amount - s.baseline_amount) for s in self._spikes)
        avg_deviation = 0.0
        if self._spikes:
            avg_deviation = round(sum(s.deviation_pct for s in self._spikes) / len(self._spikes), 2)

        # Category distribution from findings
        category_dist: dict[str, int] = {}
        for f in self._findings:
            key = f.category.value
            category_dist[key] = category_dist.get(key, 0) + 1

        # Severity distribution
        severity_dist: dict[str, int] = {}
        for spike in self._spikes:
            severity = self._classify_severity(spike)
            severity_dist[severity.value] = severity_dist.get(severity.value, 0) + 1

        # Build recommendations
        recommendations: list[str] = []
        if open_count > 0:
            recommendations.append(
                f"{open_count} spike(s) still open — prioritize investigation for "
                f"SEVERE and MAJOR severity items"
            )

        misc_count = category_dist.get(RootCauseCategory.MISCONFIGURATION, 0)
        if misc_count > 0:
            recommendations.append(
                f"{misc_count} spike(s) attributed to misconfiguration — implement "
                f"configuration validation checks in CI/CD pipeline"
            )

        severe_count = severity_dist.get(ImpactSeverity.SEVERE, 0)
        major_count = severity_dist.get(ImpactSeverity.MAJOR, 0)
        if severe_count + major_count > 0:
            recommendations.append(
                f"{severe_count + major_count} high-impact spike(s) detected — "
                f"set up proactive budget alerts at 75% of baseline"
            )

        top_offenders = self.identify_top_offenders(limit=3)
        if top_offenders:
            top_service = top_offenders[0]["service_name"]
            top_excess = top_offenders[0]["total_excess_spend"]
            recommendations.append(
                f"Top cost offender is {top_service} with ${top_excess:,.2f} excess spend — "
                f"deep-dive recommended"
            )

        report = CostRCAReport(
            total_spikes=total,
            open_investigations=open_count,
            resolved_count=resolved_count,
            total_excess_spend=round(total_excess, 2),
            avg_deviation_pct=avg_deviation,
            category_distribution=category_dist,
            severity_distribution=severity_dist,
            recommendations=recommendations,
        )
        logger.info(
            "cost_anomaly_rca.report_generated",
            total_spikes=total,
            open_investigations=open_count,
            total_excess_spend=round(total_excess, 2),
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored spikes and findings."""
        self._spikes.clear()
        self._findings.clear()
        logger.info("cost_anomaly_rca.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about spikes and findings."""
        status_counts: dict[str, int] = {}
        service_counts: dict[str, int] = {}
        for s in self._spikes:
            status_counts[s.status.value] = status_counts.get(s.status.value, 0) + 1
            service_counts[s.service_name] = service_counts.get(s.service_name, 0) + 1

        category_counts: dict[str, int] = {}
        for f in self._findings:
            category_counts[f.category.value] = category_counts.get(f.category.value, 0) + 1

        return {
            "total_spikes": len(self._spikes),
            "total_findings": len(self._findings),
            "status_distribution": status_counts,
            "service_distribution": service_counts,
            "category_distribution": category_counts,
            "max_spikes": self._max_spikes,
            "deviation_threshold_pct": self._deviation_threshold_pct,
        }
