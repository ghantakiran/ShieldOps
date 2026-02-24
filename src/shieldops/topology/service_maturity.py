"""Service Maturity Model — assess service operational maturity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MaturityLevel(StrEnum):
    INITIAL = "initial"
    DEVELOPING = "developing"
    DEFINED = "defined"
    MANAGED = "managed"
    OPTIMIZED = "optimized"


class MaturityDimension(StrEnum):
    OBSERVABILITY = "observability"
    RELIABILITY = "reliability"
    SECURITY = "security"
    OPERATIONS = "operations"
    DOCUMENTATION = "documentation"


class AssessmentStatus(StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    ARCHIVED = "archived"


# --- Models ---


class MaturityAssessment(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    service_name: str = ""
    dimension: MaturityDimension = MaturityDimension.OBSERVABILITY
    level: MaturityLevel = MaturityLevel.INITIAL
    score: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    assessor: str = ""
    status: AssessmentStatus = AssessmentStatus.DRAFT
    assessed_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class MaturityScore(BaseModel):
    service_name: str = ""
    overall_level: MaturityLevel = MaturityLevel.INITIAL
    overall_score: float = 0.0
    by_dimension: dict[str, float] = Field(
        default_factory=dict,
    )
    gaps: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class MaturityModelReport(BaseModel):
    total_assessments: int = 0
    total_services: int = 0
    avg_maturity_score: float = 0.0
    by_level: dict[str, int] = Field(
        default_factory=dict,
    )
    by_dimension: dict[str, int] = Field(
        default_factory=dict,
    )
    low_maturity_services: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Model ---

_LEVEL_SCORES: dict[MaturityLevel, float] = {
    MaturityLevel.INITIAL: 1.0,
    MaturityLevel.DEVELOPING: 2.0,
    MaturityLevel.DEFINED: 3.0,
    MaturityLevel.MANAGED: 4.0,
    MaturityLevel.OPTIMIZED: 5.0,
}


class ServiceMaturityModel:
    """Assess service maturity across multiple dimensions."""

    def __init__(
        self,
        max_assessments: int = 100000,
        target_maturity_level: int = 3,
    ) -> None:
        self._max_assessments = max_assessments
        self._target_maturity_level = target_maturity_level
        self._items: list[MaturityAssessment] = []
        logger.info(
            "service_maturity.initialized",
            max_assessments=max_assessments,
            target_level=target_maturity_level,
        )

    # -- create / get / list --

    def create_assessment(
        self,
        service_name: str = "",
        dimension: MaturityDimension = (MaturityDimension.OBSERVABILITY),
        level: MaturityLevel = MaturityLevel.INITIAL,
        score: float = 0.0,
        evidence: list[str] | None = None,
        assessor: str = "",
        status: AssessmentStatus = AssessmentStatus.DRAFT,
        **kw: Any,
    ) -> MaturityAssessment:
        """Create a maturity assessment for a service."""
        assessment = MaturityAssessment(
            service_name=service_name,
            dimension=dimension,
            level=level,
            score=score or _LEVEL_SCORES.get(level, 1.0),
            evidence=evidence or [],
            assessor=assessor,
            status=status,
            **kw,
        )
        self._items.append(assessment)
        if len(self._items) > self._max_assessments:
            self._items.pop(0)
        logger.info(
            "service_maturity.assessment_created",
            assessment_id=assessment.id,
            service=service_name,
            dimension=dimension,
        )
        return assessment

    def get_assessment(
        self,
        assessment_id: str,
    ) -> MaturityAssessment | None:
        """Get a single assessment by ID."""
        for item in self._items:
            if item.id == assessment_id:
                return item
        return None

    def list_assessments(
        self,
        service_name: str | None = None,
        dimension: MaturityDimension | None = None,
        limit: int = 50,
    ) -> list[MaturityAssessment]:
        """List assessments with optional filters."""
        results = list(self._items)
        if service_name is not None:
            results = [a for a in results if a.service_name == service_name]
        if dimension is not None:
            results = [a for a in results if a.dimension == dimension]
        return results[-limit:]

    # -- scoring operations --

    def calculate_maturity_score(
        self,
        service_name: str,
    ) -> MaturityScore:
        """Calculate overall maturity score for a service."""
        assessments = [a for a in self._items if a.service_name == service_name]
        by_dim: dict[str, float] = {}
        for a in assessments:
            key = a.dimension.value
            if key not in by_dim or a.assessed_at > by_dim.get(f"_ts_{key}", 0.0):
                by_dim[key] = a.score
                by_dim[f"_ts_{key}"] = a.assessed_at
        clean_dim = {k: v for k, v in by_dim.items() if not k.startswith("_ts_")}
        overall = 0.0
        if clean_dim:
            overall = round(
                sum(clean_dim.values()) / len(clean_dim),
                2,
            )
        overall_level = self._score_to_level(overall)
        gaps = self._identify_gaps(clean_dim)
        return MaturityScore(
            service_name=service_name,
            overall_level=overall_level,
            overall_score=overall,
            by_dimension=clean_dim,
            gaps=gaps,
        )

    def identify_maturity_gaps(
        self,
        service_name: str,
    ) -> list[dict[str, Any]]:
        """Identify maturity gaps for a service."""
        score = self.calculate_maturity_score(service_name)
        target = float(self._target_maturity_level)
        gaps: list[dict[str, Any]] = []
        for dim, val in score.by_dimension.items():
            if val < target:
                gaps.append(
                    {
                        "dimension": dim,
                        "current_score": val,
                        "target_score": target,
                        "gap": round(target - val, 2),
                    }
                )
        all_dims = {d.value for d in MaturityDimension}
        assessed_dims = set(score.by_dimension.keys())
        for dim in all_dims - assessed_dims:
            gaps.append(
                {
                    "dimension": dim,
                    "current_score": 0.0,
                    "target_score": target,
                    "gap": target,
                }
            )
        gaps.sort(key=lambda x: x["gap"], reverse=True)
        return gaps

    def rank_services_by_maturity(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all services by maturity score."""
        services: set[str] = set()
        for a in self._items:
            if a.service_name:
                services.add(a.service_name)
        rankings: list[dict[str, Any]] = []
        for svc in services:
            score = self.calculate_maturity_score(svc)
            rankings.append(
                {
                    "service_name": svc,
                    "overall_score": score.overall_score,
                    "overall_level": (score.overall_level.value),
                    "dimensions_assessed": len(score.by_dimension),
                }
            )
        rankings.sort(key=lambda x: x["overall_score"], reverse=True)
        return rankings

    def track_maturity_trend(
        self,
        service_name: str,
    ) -> list[dict[str, Any]]:
        """Track maturity trend over time for a service."""
        assessments = [a for a in self._items if a.service_name == service_name]
        assessments.sort(key=lambda a: a.assessed_at)
        trend: list[dict[str, Any]] = []
        for a in assessments:
            trend.append(
                {
                    "assessment_id": a.id,
                    "dimension": a.dimension.value,
                    "level": a.level.value,
                    "score": a.score,
                    "assessed_at": a.assessed_at,
                }
            )
        return trend

    def generate_improvement_plan(
        self,
        service_name: str,
    ) -> dict[str, Any]:
        """Generate an improvement plan for a service."""
        gaps = self.identify_maturity_gaps(service_name)
        score = self.calculate_maturity_score(service_name)
        actions: list[dict[str, Any]] = []
        for gap in gaps:
            actions.append(
                {
                    "dimension": gap["dimension"],
                    "action": (
                        f"Improve {gap['dimension']} "
                        f"from {gap['current_score']} "
                        f"to {gap['target_score']}"
                    ),
                    "priority": (
                        "high" if gap["gap"] >= 2.0 else "medium" if gap["gap"] >= 1.0 else "low"
                    ),
                    "gap": gap["gap"],
                }
            )
        actions.sort(key=lambda x: x["gap"], reverse=True)
        return {
            "service_name": service_name,
            "current_score": score.overall_score,
            "target_score": float(self._target_maturity_level),
            "total_gaps": len(gaps),
            "actions": actions,
        }

    # -- report --

    def generate_maturity_report(
        self,
    ) -> MaturityModelReport:
        """Generate a comprehensive maturity report."""
        services: set[str] = set()
        by_level: dict[str, int] = {}
        by_dimension: dict[str, int] = {}
        scores: list[float] = []
        for a in self._items:
            if a.service_name:
                services.add(a.service_name)
            lv = a.level.value
            by_level[lv] = by_level.get(lv, 0) + 1
            dim = a.dimension.value
            by_dimension[dim] = by_dimension.get(dim, 0) + 1
            scores.append(a.score)
        avg_score = 0.0
        if scores:
            avg_score = round(sum(scores) / len(scores), 2)
        low_services: list[str] = []
        target = float(self._target_maturity_level)
        for svc in services:
            ms = self.calculate_maturity_score(svc)
            if ms.overall_score < target:
                low_services.append(svc)
        recs = self._build_recommendations(
            len(self._items),
            avg_score,
            len(low_services),
        )
        return MaturityModelReport(
            total_assessments=len(self._items),
            total_services=len(services),
            avg_maturity_score=avg_score,
            by_level=by_level,
            by_dimension=by_dimension,
            low_maturity_services=sorted(low_services),
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all data. Returns assessments cleared."""
        count = len(self._items)
        self._items.clear()
        logger.info(
            "service_maturity.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        dim_dist: dict[str, int] = {}
        for a in self._items:
            key = a.dimension.value
            dim_dist[key] = dim_dist.get(key, 0) + 1
        services = {a.service_name for a in self._items if a.service_name}
        return {
            "total_assessments": len(self._items),
            "total_services": len(services),
            "max_assessments": self._max_assessments,
            "target_maturity_level": (self._target_maturity_level),
            "dimension_distribution": dim_dist,
        }

    # -- internal helpers --

    def _score_to_level(
        self,
        score: float,
    ) -> MaturityLevel:
        if score >= 4.5:
            return MaturityLevel.OPTIMIZED
        if score >= 3.5:
            return MaturityLevel.MANAGED
        if score >= 2.5:
            return MaturityLevel.DEFINED
        if score >= 1.5:
            return MaturityLevel.DEVELOPING
        return MaturityLevel.INITIAL

    def _identify_gaps(
        self,
        by_dim: dict[str, float],
    ) -> list[str]:
        target = float(self._target_maturity_level)
        gaps: list[str] = []
        for dim, val in by_dim.items():
            if val < target:
                gaps.append(f"{dim}: {val} (target {target})")
        all_dims = {d.value for d in MaturityDimension}
        for dim in all_dims - set(by_dim.keys()):
            gaps.append(f"{dim}: not assessed")
        return gaps

    def _build_recommendations(
        self,
        total: int,
        avg_score: float,
        low_count: int,
    ) -> list[str]:
        recs: list[str] = []
        if low_count > 0:
            recs.append(f"{low_count} service(s) below target maturity level")
        if total == 0:
            recs.append("No assessments recorded - begin maturity evaluation")
        if avg_score > 0 and avg_score < 3.0:
            recs.append(f"Average maturity at {avg_score} - target 3.0+")
        if not recs:
            recs.append("Service maturity levels are on track")
        return recs
