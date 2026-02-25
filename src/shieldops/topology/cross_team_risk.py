"""Cross-Team Dependency Risk — analyze cross-team risks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RiskLevel(StrEnum):
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class DependencyDirection(StrEnum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    BIDIRECTIONAL = "bidirectional"
    TRANSITIVE = "transitive"
    CIRCULAR = "circular"


class CoordinationNeed(StrEnum):
    NONE = "none"
    NOTIFICATION = "notification"
    REVIEW_REQUIRED = "review_required"
    JOINT_PLANNING = "joint_planning"
    FREEZE_REQUIRED = "freeze_required"


# --- Models ---


class CrossTeamDep(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    source_team: str = ""
    target_team: str = ""
    source_service: str = ""
    target_service: str = ""
    direction: DependencyDirection = DependencyDirection.DOWNSTREAM
    risk_level: RiskLevel = RiskLevel.LOW
    coordination_need: CoordinationNeed = CoordinationNeed.NOTIFICATION
    sla_impact_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class RiskAssessment(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    dep_id: str = ""
    change_description: str = ""
    blast_radius_teams: list[str] = Field(
        default_factory=list,
    )
    risk_level: RiskLevel = RiskLevel.LOW
    mitigation: str = ""
    assessed_by: str = ""
    created_at: float = Field(default_factory=time.time)


class CrossTeamReport(BaseModel):
    total_deps: int = 0
    total_assessments: int = 0
    high_risk_count: int = 0
    by_risk: dict[str, int] = Field(
        default_factory=dict,
    )
    by_direction: dict[str, int] = Field(
        default_factory=dict,
    )
    by_coordination: dict[str, int] = Field(
        default_factory=dict,
    )
    critical_paths: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CrossTeamDependencyRisk:
    """Analyze cross-team service dependency risks."""

    def __init__(
        self,
        max_deps: int = 100000,
        critical_risk_threshold: float = 0.8,
    ) -> None:
        self._max_deps = max_deps
        self._critical_risk_threshold = critical_risk_threshold
        self._items: list[CrossTeamDep] = []
        self._assessments: list[RiskAssessment] = []
        logger.info(
            "cross_team_risk.initialized",
            max_deps=max_deps,
            critical_risk_threshold=critical_risk_threshold,
        )

    # -- register / get / list --

    def register_dependency(
        self,
        source_team: str = "",
        target_team: str = "",
        source_service: str = "",
        target_service: str = "",
        direction: DependencyDirection = (DependencyDirection.DOWNSTREAM),
        risk_level: RiskLevel = RiskLevel.LOW,
        coordination_need: CoordinationNeed = (CoordinationNeed.NOTIFICATION),
        sla_impact_pct: float = 0.0,
        **kw: Any,
    ) -> CrossTeamDep:
        """Register a cross-team dependency."""
        dep = CrossTeamDep(
            source_team=source_team,
            target_team=target_team,
            source_service=source_service,
            target_service=target_service,
            direction=direction,
            risk_level=risk_level,
            coordination_need=coordination_need,
            sla_impact_pct=sla_impact_pct,
            **kw,
        )
        self._items.append(dep)
        if len(self._items) > self._max_deps:
            self._items.pop(0)
        logger.info(
            "cross_team_risk.dependency_registered",
            dep_id=dep.id,
            source_team=source_team,
            target_team=target_team,
        )
        return dep

    def get_dependency(
        self,
        dep_id: str,
    ) -> CrossTeamDep | None:
        """Get a single dependency by ID."""
        for item in self._items:
            if item.id == dep_id:
                return item
        return None

    def list_dependencies(
        self,
        source_team: str | None = None,
        target_team: str | None = None,
        limit: int = 50,
    ) -> list[CrossTeamDep]:
        """List dependencies with optional filters."""
        results = list(self._items)
        if source_team is not None:
            results = [r for r in results if r.source_team == source_team]
        if target_team is not None:
            results = [r for r in results if r.target_team == target_team]
        return results[-limit:]

    # -- domain operations --

    def assess_change_risk(
        self,
        dep_id: str,
        change_description: str = "",
        assessed_by: str = "",
        **kw: Any,
    ) -> RiskAssessment | None:
        """Assess risk of a change on a dependency."""
        dep = self.get_dependency(dep_id)
        if dep is None:
            return None
        blast = self._compute_blast_radius(dep)
        risk = self._determine_risk(dep, blast)
        mitigation = self._suggest_mitigation(risk)
        assessment = RiskAssessment(
            dep_id=dep_id,
            change_description=change_description,
            blast_radius_teams=blast,
            risk_level=risk,
            mitigation=mitigation,
            assessed_by=assessed_by,
            **kw,
        )
        self._assessments.append(assessment)
        logger.info(
            "cross_team_risk.assessed",
            assessment_id=assessment.id,
            dep_id=dep_id,
        )
        return assessment

    def calculate_blast_radius(
        self,
        team: str,
    ) -> dict[str, Any]:
        """Calculate blast radius for a team."""
        affected: set[str] = set()
        for dep in self._items:
            if dep.source_team == team:
                affected.add(dep.target_team)
            if dep.target_team == team:
                affected.add(dep.source_team)
        affected.discard(team)
        return {
            "team": team,
            "affected_teams": sorted(affected),
            "affected_count": len(affected),
        }

    def identify_critical_paths(
        self,
    ) -> list[dict[str, Any]]:
        """Identify high/critical risk dependency paths."""
        critical: list[dict[str, Any]] = []
        for dep in self._items:
            if dep.risk_level in (
                RiskLevel.HIGH,
                RiskLevel.CRITICAL,
            ):
                critical.append(
                    {
                        "dep_id": dep.id,
                        "source_team": dep.source_team,
                        "target_team": dep.target_team,
                        "risk_level": dep.risk_level.value,
                        "sla_impact_pct": dep.sla_impact_pct,
                    }
                )
        critical.sort(
            key=lambda x: x.get("sla_impact_pct", 0),
            reverse=True,
        )
        return critical

    def detect_circular_dependencies(
        self,
    ) -> list[dict[str, Any]]:
        """Detect circular dependency patterns."""
        circular: list[dict[str, Any]] = []
        seen: set[str] = set()
        for dep in self._items:
            if dep.direction == DependencyDirection.CIRCULAR:
                key = f"{dep.source_team}-{dep.target_team}"
                if key not in seen:
                    circular.append(
                        {
                            "dep_id": dep.id,
                            "teams": [
                                dep.source_team,
                                dep.target_team,
                            ],
                        }
                    )
                    seen.add(key)
        # Also detect implicit circular deps
        for dep_a in self._items:
            for dep_b in self._items:
                if (
                    dep_a.id != dep_b.id
                    and dep_a.source_team == dep_b.target_team
                    and dep_a.target_team == dep_b.source_team
                ):
                    key = "-".join(
                        sorted(
                            [
                                dep_a.source_team,
                                dep_a.target_team,
                            ]
                        )
                    )
                    if key not in seen:
                        circular.append(
                            {
                                "dep_ids": [
                                    dep_a.id,
                                    dep_b.id,
                                ],
                                "teams": [
                                    dep_a.source_team,
                                    dep_a.target_team,
                                ],
                            }
                        )
                        seen.add(key)
        return circular

    def rank_teams_by_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank teams by aggregate risk score."""
        scores: dict[str, float] = {}
        risk_weights = {
            RiskLevel.MINIMAL: 0.1,
            RiskLevel.LOW: 0.3,
            RiskLevel.MODERATE: 0.5,
            RiskLevel.HIGH: 0.8,
            RiskLevel.CRITICAL: 1.0,
        }
        for dep in self._items:
            w = risk_weights.get(dep.risk_level, 0.3)
            for t in (dep.source_team, dep.target_team):
                if t:
                    scores[t] = scores.get(t, 0.0) + w
        ranked = [{"team": t, "risk_score": round(s, 2)} for t, s in scores.items()]
        ranked.sort(
            key=lambda x: float(x.get("risk_score", 0)),  # type: ignore[arg-type]
            reverse=True,
        )
        return ranked

    # -- report --

    def generate_risk_report(
        self,
    ) -> CrossTeamReport:
        """Generate a comprehensive risk report."""
        by_risk: dict[str, int] = {}
        by_direction: dict[str, int] = {}
        by_coordination: dict[str, int] = {}
        high_risk = 0
        for dep in self._items:
            r = dep.risk_level.value
            by_risk[r] = by_risk.get(r, 0) + 1
            d = dep.direction.value
            by_direction[d] = by_direction.get(d, 0) + 1
            c = dep.coordination_need.value
            by_coordination[c] = by_coordination.get(c, 0) + 1
            if dep.risk_level in (
                RiskLevel.HIGH,
                RiskLevel.CRITICAL,
            ):
                high_risk += 1
        critical_paths = self.identify_critical_paths()
        cp_ids = [p.get("dep_id", "") for p in critical_paths]
        recs = self._build_recommendations(
            len(self._items),
            high_risk,
        )
        return CrossTeamReport(
            total_deps=len(self._items),
            total_assessments=len(self._assessments),
            high_risk_count=high_risk,
            by_risk=by_risk,
            by_direction=by_direction,
            by_coordination=by_coordination,
            critical_paths=cp_ids,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all data. Returns records cleared."""
        count = len(self._items)
        self._items.clear()
        self._assessments.clear()
        logger.info(
            "cross_team_risk.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        risk_dist: dict[str, int] = {}
        for dep in self._items:
            key = dep.risk_level.value
            risk_dist[key] = risk_dist.get(key, 0) + 1
        return {
            "total_deps": len(self._items),
            "total_assessments": len(self._assessments),
            "max_deps": self._max_deps,
            "critical_risk_threshold": (self._critical_risk_threshold),
            "risk_distribution": risk_dist,
        }

    # -- internal helpers --

    def _compute_blast_radius(
        self,
        dep: CrossTeamDep,
    ) -> list[str]:
        affected: set[str] = set()
        affected.add(dep.source_team)
        affected.add(dep.target_team)
        for other in self._items:
            if other.source_team in affected:
                affected.add(other.target_team)
            if other.target_team in affected:
                affected.add(other.source_team)
        return sorted(t for t in affected if t)

    def _determine_risk(
        self,
        dep: CrossTeamDep,
        blast: list[str],
    ) -> RiskLevel:
        if len(blast) > 3:
            return RiskLevel.CRITICAL
        if dep.sla_impact_pct >= (self._critical_risk_threshold * 100):
            return RiskLevel.HIGH
        if dep.risk_level in (
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ):
            return dep.risk_level
        return RiskLevel.MODERATE

    def _suggest_mitigation(
        self,
        risk: RiskLevel,
    ) -> str:
        mitigations = {
            RiskLevel.CRITICAL: ("Freeze changes; joint planning required"),
            RiskLevel.HIGH: ("Schedule review with affected teams"),
            RiskLevel.MODERATE: ("Notify dependent teams before change"),
            RiskLevel.LOW: "Standard notification",
            RiskLevel.MINIMAL: "No action needed",
        }
        return mitigations.get(risk, "Review required")

    def _build_recommendations(
        self,
        total: int,
        high_risk: int,
    ) -> list[str]:
        recs: list[str] = []
        if high_risk > 0:
            recs.append(f"{high_risk} high/critical risk dependency(ies) need review")
        if total == 0:
            recs.append("No cross-team dependencies tracked")
        if total > 0 and high_risk == 0:
            recs.append("Cross-team risk within acceptable limits")
        if not recs:
            recs.append("Cross-team dependencies well managed")
        return recs
