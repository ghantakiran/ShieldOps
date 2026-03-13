"""Team Capability Gap Analyzer —
identify capability gaps, compute gap criticality,
rank gaps by business impact."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CapabilityDomain(StrEnum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    SIGNIFICANT = "significant"
    MODERATE = "moderate"
    MINOR = "minor"


class RemediationPath(StrEnum):
    HIRING = "hiring"
    TRAINING = "training"
    TOOLING = "tooling"
    OUTSOURCING = "outsourcing"


# --- Models ---


class CapabilityGapRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_id: str = ""
    team_id: str = ""
    domain: CapabilityDomain = CapabilityDomain.BACKEND
    severity: GapSeverity = GapSeverity.MODERATE
    remediation: RemediationPath = RemediationPath.TRAINING
    impact_score: float = 0.0
    current_level: float = 0.0
    required_level: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CapabilityGapAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_id: str = ""
    gap_size: float = 0.0
    severity: GapSeverity = GapSeverity.MODERATE
    criticality_score: float = 0.0
    affected_teams: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CapabilityGapReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_gap_size: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_remediation: dict[str, int] = Field(default_factory=dict)
    critical_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamCapabilityGapAnalyzer:
    """Identify capability gaps, compute criticality,
    rank gaps by business impact."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CapabilityGapRecord] = []
        self._analyses: dict[str, CapabilityGapAnalysis] = {}
        logger.info(
            "team_capability_gap_analyzer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        gap_id: str = "",
        team_id: str = "",
        domain: CapabilityDomain = (CapabilityDomain.BACKEND),
        severity: GapSeverity = GapSeverity.MODERATE,
        remediation: RemediationPath = (RemediationPath.TRAINING),
        impact_score: float = 0.0,
        current_level: float = 0.0,
        required_level: float = 0.0,
        description: str = "",
    ) -> CapabilityGapRecord:
        record = CapabilityGapRecord(
            gap_id=gap_id,
            team_id=team_id,
            domain=domain,
            severity=severity,
            remediation=remediation,
            impact_score=impact_score,
            current_level=current_level,
            required_level=required_level,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capability_gap.record_added",
            record_id=record.id,
            gap_id=gap_id,
        )
        return record

    def process(self, key: str) -> CapabilityGapAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        gap_recs = [r for r in self._records if r.gap_id == rec.gap_id]
        teams = {r.team_id for r in gap_recs}
        gap_size = round(
            max(
                rec.required_level - rec.current_level,
                0.0,
            ),
            2,
        )
        criticality = round(gap_size * rec.impact_score, 2)
        analysis = CapabilityGapAnalysis(
            gap_id=rec.gap_id,
            gap_size=gap_size,
            severity=rec.severity,
            criticality_score=criticality,
            affected_teams=len(teams),
            description=(f"Gap {rec.gap_id} size={gap_size}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CapabilityGapReport:
        by_d: dict[str, int] = {}
        by_s: dict[str, int] = {}
        by_r: dict[str, int] = {}
        gaps: list[float] = []
        for r in self._records:
            k = r.domain.value
            by_d[k] = by_d.get(k, 0) + 1
            k2 = r.severity.value
            by_s[k2] = by_s.get(k2, 0) + 1
            k3 = r.remediation.value
            by_r[k3] = by_r.get(k3, 0) + 1
            gaps.append(
                max(
                    r.required_level - r.current_level,
                    0.0,
                )
            )
        avg = round(sum(gaps) / len(gaps), 2) if gaps else 0.0
        critical = list(
            {
                r.gap_id
                for r in self._records
                if r.severity
                in (
                    GapSeverity.CRITICAL,
                    GapSeverity.SIGNIFICANT,
                )
            }
        )[:10]
        recs: list[str] = []
        if critical:
            recs.append(f"{len(critical)} critical gaps found")
        if not recs:
            recs.append("No critical capability gaps")
        return CapabilityGapReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_gap_size=avg,
            by_domain=by_d,
            by_severity=by_s,
            by_remediation=by_r,
            critical_gaps=critical,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        d_dist: dict[str, int] = {}
        for r in self._records:
            k = r.domain.value
            d_dist[k] = d_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "domain_distribution": d_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("team_capability_gap_analyzer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def identify_capability_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Identify capability gaps per team."""
        team_gaps: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            gap_size = max(
                r.required_level - r.current_level,
                0.0,
            )
            if gap_size > 0:
                team_gaps.setdefault(r.team_id, []).append(
                    {
                        "gap_id": r.gap_id,
                        "domain": r.domain.value,
                        "gap_size": round(gap_size, 2),
                    }
                )
        results: list[dict[str, Any]] = []
        for tid, gaps_list in team_gaps.items():
            results.append(
                {
                    "team_id": tid,
                    "gap_count": len(gaps_list),
                    "gaps": gaps_list[:5],
                }
            )
        results.sort(
            key=lambda x: x["gap_count"],
            reverse=True,
        )
        return results

    def compute_gap_criticality(
        self,
    ) -> list[dict[str, Any]]:
        """Compute criticality score per gap."""
        gap_data: dict[str, list[float]] = {}
        gap_impacts: dict[str, float] = {}
        for r in self._records:
            size = max(
                r.required_level - r.current_level,
                0.0,
            )
            gap_data.setdefault(r.gap_id, []).append(size)
            gap_impacts[r.gap_id] = max(
                gap_impacts.get(r.gap_id, 0.0),
                r.impact_score,
            )
        results: list[dict[str, Any]] = []
        for gid, sizes in gap_data.items():
            avg_size = sum(sizes) / len(sizes)
            criticality = round(
                avg_size * gap_impacts.get(gid, 0.0),
                2,
            )
            results.append(
                {
                    "gap_id": gid,
                    "criticality": criticality,
                    "avg_gap_size": round(avg_size, 2),
                    "impact": gap_impacts.get(gid, 0.0),
                }
            )
        results.sort(
            key=lambda x: x["criticality"],
            reverse=True,
        )
        return results

    def rank_gaps_by_business_impact(
        self,
    ) -> list[dict[str, Any]]:
        """Rank gaps by business impact."""
        gap_impact: dict[str, float] = {}
        gap_teams: dict[str, set[str]] = {}
        for r in self._records:
            gap_impact[r.gap_id] = gap_impact.get(r.gap_id, 0.0) + r.impact_score
            gap_teams.setdefault(r.gap_id, set()).add(r.team_id)
        results: list[dict[str, Any]] = []
        for gid, impact in gap_impact.items():
            results.append(
                {
                    "gap_id": gid,
                    "business_impact": round(impact, 2),
                    "affected_teams": len(gap_teams.get(gid, set())),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["business_impact"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
