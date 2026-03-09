"""Platform Observability Score

Comprehensive observability maturity scoring, coverage gap identification,
improvement roadmap generation, and benchmark comparison across services.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ObservabilityPillar(StrEnum):
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"
    EVENTS = "events"
    PROFILING = "profiling"
    SYNTHETICS = "synthetics"


class MaturityLevel(StrEnum):
    NONE = "none"
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# --- Models ---


class ObservabilityScoreRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    pillar: ObservabilityPillar = ObservabilityPillar.METRICS
    maturity_level: MaturityLevel = MaturityLevel.NONE
    coverage_pct: float = 0.0
    instrumentation_score: float = 0.0
    alert_coverage_pct: float = 0.0
    dashboard_count: int = 0
    slo_defined: bool = False
    runbook_linked: bool = False
    on_call_configured: bool = False
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CoverageGap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    pillar: ObservabilityPillar = ObservabilityPillar.METRICS
    gap_severity: GapSeverity = GapSeverity.MEDIUM
    gap_description: str = ""
    remediation: str = ""
    effort_hours: float = 0.0
    impact_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class PlatformScoreReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_gaps: int = 0
    overall_score: float = 0.0
    avg_coverage_pct: float = 0.0
    avg_instrumentation: float = 0.0
    slo_adoption_pct: float = 0.0
    by_pillar: dict[str, int] = Field(default_factory=dict)
    by_maturity_level: dict[str, int] = Field(default_factory=dict)
    pillar_scores: dict[str, float] = Field(default_factory=dict)
    service_scores: list[dict[str, Any]] = Field(default_factory=list)
    top_gaps: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PlatformObservabilityScore:
    """Platform Observability Score

    Comprehensive observability maturity scoring, coverage gaps, improvement
    roadmap, and benchmark comparison.
    """

    MATURITY_WEIGHTS: dict[str, float] = {
        "none": 0.0,
        "basic": 25.0,
        "intermediate": 50.0,
        "advanced": 75.0,
        "expert": 100.0,
    }

    def __init__(
        self,
        max_records: int = 200000,
        target_score: float = 75.0,
        min_pillar_coverage: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._target_score = target_score
        self._min_pillar_coverage = min_pillar_coverage
        self._records: list[ObservabilityScoreRecord] = []
        self._gaps: list[CoverageGap] = []
        logger.info(
            "platform_observability_score.initialized",
            max_records=max_records,
            target_score=target_score,
        )

    def add_record(
        self,
        service: str,
        pillar: ObservabilityPillar,
        maturity_level: MaturityLevel = MaturityLevel.NONE,
        coverage_pct: float = 0.0,
        instrumentation_score: float = 0.0,
        alert_coverage_pct: float = 0.0,
        dashboard_count: int = 0,
        slo_defined: bool = False,
        runbook_linked: bool = False,
        on_call_configured: bool = False,
        team: str = "",
    ) -> ObservabilityScoreRecord:
        record = ObservabilityScoreRecord(
            service=service,
            pillar=pillar,
            maturity_level=maturity_level,
            coverage_pct=coverage_pct,
            instrumentation_score=instrumentation_score,
            alert_coverage_pct=alert_coverage_pct,
            dashboard_count=dashboard_count,
            slo_defined=slo_defined,
            runbook_linked=runbook_linked,
            on_call_configured=on_call_configured,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        if coverage_pct < self._min_pillar_coverage:
            severity = (
                GapSeverity.CRITICAL
                if coverage_pct < 20
                else (GapSeverity.HIGH if coverage_pct < 40 else GapSeverity.MEDIUM)
            )
            gap = CoverageGap(
                service=service,
                pillar=pillar,
                gap_severity=severity,
                gap_description=(
                    f"{pillar.value} coverage at {coverage_pct}% "
                    f"(target: {self._min_pillar_coverage}%)"
                ),
                remediation=f"Increase {pillar.value} instrumentation for {service}",
                impact_score=round((self._min_pillar_coverage - coverage_pct) / 100, 4),
            )
            self._gaps.append(gap)
            if len(self._gaps) > self._max_records:
                self._gaps = self._gaps[-self._max_records :]
        logger.info(
            "platform_observability_score.record_added",
            record_id=record.id,
            service=service,
            pillar=pillar.value,
            maturity_level=maturity_level.value,
        )
        return record

    def get_record(self, record_id: str) -> ObservabilityScoreRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        pillar: ObservabilityPillar | None = None,
        maturity_level: MaturityLevel | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[ObservabilityScoreRecord]:
        results = list(self._records)
        if pillar is not None:
            results = [r for r in results if r.pillar == pillar]
        if maturity_level is not None:
            results = [r for r in results if r.maturity_level == maturity_level]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def compute_service_score(self, service: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {"service": service, "status": "no_data"}
        pillar_scores: dict[str, float] = {}
        for r in matching:
            maturity_weight = self.MATURITY_WEIGHTS.get(r.maturity_level.value, 0.0)
            combined = (
                maturity_weight * 0.3
                + r.coverage_pct * 0.3
                + r.instrumentation_score * 0.2
                + r.alert_coverage_pct * 0.1
                + (10.0 if r.slo_defined else 0.0)
                + (5.0 if r.runbook_linked else 0.0)
                + (5.0 if r.on_call_configured else 0.0)
            )
            pillar_scores[r.pillar.value] = round(min(100.0, combined), 2)
        overall = round(sum(pillar_scores.values()) / max(1, len(pillar_scores)), 2)
        covered_pillars = len(pillar_scores)
        total_pillars = len(ObservabilityPillar)
        pillar_coverage = round(covered_pillars / total_pillars * 100, 2)
        return {
            "service": service,
            "overall_score": overall,
            "pillar_scores": pillar_scores,
            "pillar_coverage_pct": pillar_coverage,
            "covered_pillars": covered_pillars,
            "total_pillars": total_pillars,
            "meets_target": overall >= self._target_score,
        }

    def compute_pillar_benchmark(self) -> dict[str, Any]:
        pillar_data: dict[str, list[float]] = {}
        for r in self._records:
            pillar_data.setdefault(r.pillar.value, []).append(r.coverage_pct)
        benchmarks: dict[str, dict[str, float]] = {}
        for pillar, coverages in pillar_data.items():
            sorted_covs = sorted(coverages)
            n = len(sorted_covs)
            benchmarks[pillar] = {
                "avg": round(sum(sorted_covs) / n, 2),
                "min": sorted_covs[0],
                "max": sorted_covs[-1],
                "p50": sorted_covs[n // 2],
                "services_measured": n,
            }
        return {"pillar_benchmarks": benchmarks}

    def generate_roadmap(self, service: str) -> list[dict[str, Any]]:
        gaps = [g for g in self._gaps if g.service == service]
        if not gaps:
            return [
                {
                    "service": service,
                    "status": "no_gaps",
                    "recommendation": "Maintain current observability posture",
                }
            ]
        roadmap: list[dict[str, Any]] = []
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        sorted_gaps = sorted(gaps, key=lambda g: severity_order.get(g.gap_severity.value, 5))
        for i, gap in enumerate(sorted_gaps[:10], 1):
            roadmap.append(
                {
                    "priority": i,
                    "pillar": gap.pillar.value,
                    "severity": gap.gap_severity.value,
                    "description": gap.gap_description,
                    "remediation": gap.remediation,
                    "effort_hours": gap.effort_hours,
                    "impact_score": gap.impact_score,
                }
            )
        return roadmap

    def process(self, service: str) -> dict[str, Any]:
        score_data = self.compute_service_score(service)
        if score_data.get("status") == "no_data":
            return {"service": service, "status": "no_data"}
        return score_data

    def generate_report(self) -> PlatformScoreReport:
        by_pillar: dict[str, int] = {}
        by_maturity: dict[str, int] = {}
        for r in self._records:
            by_pillar[r.pillar.value] = by_pillar.get(r.pillar.value, 0) + 1
            by_maturity[r.maturity_level.value] = by_maturity.get(r.maturity_level.value, 0) + 1
        coverages = [r.coverage_pct for r in self._records]
        instrumentations = [r.instrumentation_score for r in self._records]
        slo_count = sum(1 for r in self._records if r.slo_defined)
        slo_adoption = round(slo_count / max(1, len(self._records)) * 100, 2)
        pillar_scores: dict[str, float] = {}
        for pillar in ObservabilityPillar:
            p_recs = [r for r in self._records if r.pillar == pillar]
            if p_recs:
                avg_cov = sum(r.coverage_pct for r in p_recs) / len(p_recs)
                pillar_scores[pillar.value] = round(avg_cov, 2)
        services = {r.service for r in self._records}
        svc_scores: list[dict[str, Any]] = []
        for svc in sorted(services):
            score_data = self.compute_service_score(svc)
            if score_data.get("status") != "no_data":
                svc_scores.append(
                    {
                        "service": svc,
                        "overall_score": score_data["overall_score"],
                        "meets_target": score_data["meets_target"],
                    }
                )
        svc_scores.sort(key=lambda x: x["overall_score"])
        overall_scores = [s["overall_score"] for s in svc_scores]
        overall = (
            round(sum(overall_scores) / max(1, len(overall_scores)), 2) if overall_scores else 0.0
        )
        top_gaps_raw = sorted(self._gaps, key=lambda g: g.impact_score, reverse=True)[:5]
        top_gaps = [
            {
                "service": g.service,
                "pillar": g.pillar.value,
                "severity": g.gap_severity.value,
                "description": g.gap_description,
            }
            for g in top_gaps_raw
        ]
        recs: list[str] = []
        below_target = [s for s in svc_scores if not s["meets_target"]]
        if below_target:
            recs.append(f"{len(below_target)} service(s) below target score ({self._target_score})")
        if slo_adoption < 50:
            recs.append(f"SLO adoption at {slo_adoption}% — define SLOs for all services")
        weak_pillars = [p for p, s in pillar_scores.items() if s < self._min_pillar_coverage]
        if weak_pillars:
            recs.append(f"Weak pillars: {', '.join(weak_pillars)} — increase coverage")
        if not recs:
            recs.append("Platform observability maturity is on target")
        return PlatformScoreReport(
            total_records=len(self._records),
            total_gaps=len(self._gaps),
            overall_score=overall,
            avg_coverage_pct=round(sum(coverages) / max(1, len(coverages)), 2),
            avg_instrumentation=round(sum(instrumentations) / max(1, len(instrumentations)), 2),
            slo_adoption_pct=slo_adoption,
            by_pillar=by_pillar,
            by_maturity_level=by_maturity,
            pillar_scores=pillar_scores,
            service_scores=svc_scores[:20],
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        pillar_dist: dict[str, int] = {}
        for r in self._records:
            pillar_dist[r.pillar.value] = pillar_dist.get(r.pillar.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_gaps": len(self._gaps),
            "target_score": self._target_score,
            "min_pillar_coverage": self._min_pillar_coverage,
            "pillar_distribution": pillar_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._gaps.clear()
        logger.info("platform_observability_score.cleared")
        return {"status": "cleared"}
