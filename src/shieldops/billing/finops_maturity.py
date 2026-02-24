"""FinOps Maturity Scorer — score maturity across visibility, optimization, operations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MaturityDimension(StrEnum):
    VISIBILITY = "visibility"
    ALLOCATION = "allocation"
    OPTIMIZATION = "optimization"
    GOVERNANCE = "governance"
    CULTURE = "culture"


class MaturityLevel(StrEnum):
    CRAWL = "crawl"
    WALK = "walk"
    RUN = "run"
    SPRINT = "sprint"
    LEAD = "lead"


class AssessmentArea(StrEnum):
    TAGGING = "tagging"
    FORECASTING = "forecasting"
    RIGHTSIZING = "rightsizing"
    COMMITMENT_USAGE = "commitment_usage"
    ANOMALY_DETECTION = "anomaly_detection"


# --- Models ---


class MaturityAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    organization: str = ""
    assessor: str = ""
    overall_score: float = 0.0
    overall_level: MaturityLevel = MaturityLevel.CRAWL
    dimension_scores: list[str] = Field(default_factory=list)
    notes: str = ""
    created_at: float = Field(default_factory=time.time)


class DimensionScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_id: str = ""
    dimension: MaturityDimension = MaturityDimension.VISIBILITY
    area: AssessmentArea = AssessmentArea.TAGGING
    score: float = 0.0
    level: MaturityLevel = MaturityLevel.CRAWL
    findings: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class MaturityReport(BaseModel):
    total_assessments: int = 0
    avg_overall_score: float = 0.0
    avg_level: str = ""
    by_dimension: dict[str, float] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    improvement_areas: list[str] = Field(default_factory=list)
    benchmarks: dict[str, float] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


_BENCHMARKS: dict[MaturityDimension, float] = {
    MaturityDimension.VISIBILITY: 65.0,
    MaturityDimension.ALLOCATION: 55.0,
    MaturityDimension.OPTIMIZATION: 50.0,
    MaturityDimension.GOVERNANCE: 45.0,
    MaturityDimension.CULTURE: 40.0,
}


def _score_to_level(score: float) -> MaturityLevel:
    """Convert a numeric score to a maturity level."""
    if score >= 80.0:
        return MaturityLevel.LEAD
    if score >= 60.0:
        return MaturityLevel.SPRINT
    if score >= 40.0:
        return MaturityLevel.RUN
    if score >= 20.0:
        return MaturityLevel.WALK
    return MaturityLevel.CRAWL


class FinOpsMaturityScorer:
    """Score FinOps maturity across visibility, optimization, and operations."""

    def __init__(
        self,
        max_assessments: int = 50000,
        target_level: int = 3,
    ) -> None:
        self._max_assessments = max_assessments
        self._target_level = target_level
        self._assessments: list[MaturityAssessment] = []
        self._dimension_scores: list[DimensionScore] = []
        logger.info(
            "finops_maturity.initialized",
            max_assessments=max_assessments,
            target_level=target_level,
        )

    def create_assessment(
        self,
        organization: str = "",
        assessor: str = "",
        notes: str = "",
    ) -> MaturityAssessment:
        """Create a new maturity assessment."""
        assessment = MaturityAssessment(
            organization=organization,
            assessor=assessor,
            notes=notes,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_assessments:
            self._assessments = self._assessments[-self._max_assessments :]
        logger.info(
            "finops_maturity.assessment_created",
            assessment_id=assessment.id,
            organization=organization,
            assessor=assessor,
        )
        return assessment

    def get_assessment(self, assessment_id: str) -> MaturityAssessment | None:
        """Retrieve a single assessment by ID."""
        for a in self._assessments:
            if a.id == assessment_id:
                return a
        return None

    def list_assessments(
        self,
        organization: str | None = None,
        limit: int = 100,
    ) -> list[MaturityAssessment]:
        """List assessments with optional filtering by organization."""
        results = list(self._assessments)
        if organization is not None:
            results = [a for a in results if a.organization == organization]
        return results[-limit:]

    def score_dimension(
        self,
        assessment_id: str,
        dimension: MaturityDimension,
        area: AssessmentArea,
        score: float,
        findings: list[str] | None = None,
    ) -> DimensionScore | None:
        """Score a dimension for an assessment.

        Determines maturity level from score:
        >=80 -> LEAD, >=60 -> SPRINT, >=40 -> RUN, >=20 -> WALK, <20 -> CRAWL.
        Updates the assessment's overall_score as the average of all dimension scores.
        """
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            logger.warning(
                "finops_maturity.assessment_not_found",
                assessment_id=assessment_id,
            )
            return None

        level = _score_to_level(score)

        dim_score = DimensionScore(
            assessment_id=assessment_id,
            dimension=dimension,
            area=area,
            score=score,
            level=level,
            findings=findings or [],
        )
        self._dimension_scores.append(dim_score)

        # Add dimension score ID to assessment
        assessment.dimension_scores.append(dim_score.id)

        # Recalculate overall score as average of all dimension scores for this assessment
        assessment_dims = [d for d in self._dimension_scores if d.assessment_id == assessment_id]
        if assessment_dims:
            avg_score = sum(d.score for d in assessment_dims) / len(assessment_dims)
            assessment.overall_score = round(avg_score, 2)
            assessment.overall_level = _score_to_level(assessment.overall_score)

        logger.info(
            "finops_maturity.dimension_scored",
            assessment_id=assessment_id,
            dimension=dimension,
            area=area,
            score=score,
            level=level,
        )
        return dim_score

    def calculate_overall_maturity(self, assessment_id: str) -> dict[str, Any]:
        """Recalculate overall maturity from dimension scores."""
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return {
                "assessment_id": assessment_id,
                "overall_score": 0.0,
                "overall_level": MaturityLevel.CRAWL.value,
                "dimension_breakdown": [],
            }

        assessment_dims = [d for d in self._dimension_scores if d.assessment_id == assessment_id]

        dimension_breakdown: list[dict[str, Any]] = []
        for d in assessment_dims:
            dimension_breakdown.append(
                {
                    "dimension": d.dimension.value,
                    "score": d.score,
                    "level": d.level.value,
                }
            )

        if assessment_dims:
            avg_score = sum(d.score for d in assessment_dims) / len(assessment_dims)
            assessment.overall_score = round(avg_score, 2)
            assessment.overall_level = _score_to_level(assessment.overall_score)

        return {
            "assessment_id": assessment_id,
            "overall_score": assessment.overall_score,
            "overall_level": assessment.overall_level.value,
            "dimension_breakdown": dimension_breakdown,
        }

    def identify_improvement_areas(self, assessment_id: str) -> list[dict[str, Any]]:
        """Identify dimensions scoring below the target level threshold.

        Target score threshold = target_level * 20.
        """
        target_score = self._target_level * 20.0
        assessment_dims = [d for d in self._dimension_scores if d.assessment_id == assessment_id]

        improvements: list[dict[str, Any]] = []
        for d in assessment_dims:
            if d.score < target_score:
                improvements.append(
                    {
                        "dimension": d.dimension.value,
                        "current_score": d.score,
                        "target_score": target_score,
                        "gap": round(target_score - d.score, 2),
                    }
                )
        return improvements

    def track_maturity_trend(self, organization: str) -> list[dict[str, Any]]:
        """Track maturity trend for an organization over time."""
        org_assessments = [a for a in self._assessments if a.organization == organization]
        org_assessments.sort(key=lambda a: a.created_at)

        trend: list[dict[str, Any]] = []
        for a in org_assessments:
            trend.append(
                {
                    "assessment_id": a.id,
                    "overall_score": a.overall_score,
                    "overall_level": a.overall_level.value,
                    "assessed_at": a.created_at,
                }
            )
        return trend

    def compare_with_benchmarks(self, assessment_id: str) -> dict[str, Any]:
        """Compare an assessment's dimension scores against industry benchmarks."""
        assessment_dims = [d for d in self._dimension_scores if d.assessment_id == assessment_id]

        comparisons: list[dict[str, Any]] = []
        for d in assessment_dims:
            benchmark = _BENCHMARKS.get(d.dimension, 50.0)
            comparisons.append(
                {
                    "dimension": d.dimension.value,
                    "score": d.score,
                    "benchmark": benchmark,
                    "delta": round(d.score - benchmark, 2),
                }
            )

        return {
            "assessment_id": assessment_id,
            "comparisons": comparisons,
        }

    def generate_maturity_report(self) -> MaturityReport:
        """Generate a comprehensive maturity report across all assessments."""
        avg_score = 0.0
        if self._assessments:
            avg_score = round(
                sum(a.overall_score for a in self._assessments) / len(self._assessments),
                2,
            )
        avg_level = _score_to_level(avg_score).value

        # By dimension — average score per dimension
        dim_totals: dict[str, list[float]] = {}
        for d in self._dimension_scores:
            key = d.dimension.value
            if key not in dim_totals:
                dim_totals[key] = []
            dim_totals[key].append(d.score)
        by_dimension: dict[str, float] = {}
        for key, scores in dim_totals.items():
            by_dimension[key] = round(sum(scores) / len(scores), 2)

        # By level — count assessments per level
        by_level: dict[str, int] = {}
        for a in self._assessments:
            key = a.overall_level.value
            by_level[key] = by_level.get(key, 0) + 1

        # Improvement areas — dimensions below benchmark on average
        improvement_areas: list[str] = []
        for dim, benchmark in _BENCHMARKS.items():
            avg_dim = by_dimension.get(dim.value, 0.0)
            if avg_dim < benchmark:
                improvement_areas.append(
                    f"{dim.value}: avg score {avg_dim:.1f} below benchmark {benchmark:.1f}"
                )

        # Benchmarks for report
        benchmarks = {k.value: v for k, v in _BENCHMARKS.items()}

        # Recommendations
        recommendations: list[str] = []
        crawl_count = by_level.get(MaturityLevel.CRAWL.value, 0)
        if crawl_count > 0:
            recommendations.append(
                f"{crawl_count} assessment(s) at CRAWL level — "
                f"prioritize foundational FinOps practices"
            )

        if improvement_areas:
            recommendations.append(
                f"{len(improvement_areas)} dimension(s) below industry benchmarks — "
                f"focus on lowest-scoring areas first"
            )

        if avg_score >= 60.0:
            recommendations.append(
                "Average maturity at SPRINT level or above — focus on automation and optimization"
            )

        if not self._assessments:
            recommendations.append(
                "No assessments recorded — create assessments to track FinOps maturity"
            )

        report = MaturityReport(
            total_assessments=len(self._assessments),
            avg_overall_score=avg_score,
            avg_level=avg_level,
            by_dimension=by_dimension,
            by_level=by_level,
            improvement_areas=improvement_areas,
            benchmarks=benchmarks,
            recommendations=recommendations,
        )
        logger.info(
            "finops_maturity.report_generated",
            total_assessments=len(self._assessments),
            avg_overall_score=avg_score,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored assessments and dimension scores."""
        self._assessments.clear()
        self._dimension_scores.clear()
        logger.info("finops_maturity.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about assessments and dimension scores."""
        org_counts: dict[str, int] = {}
        level_counts: dict[str, int] = {}
        for a in self._assessments:
            org_counts[a.organization] = org_counts.get(a.organization, 0) + 1
            level_counts[a.overall_level.value] = level_counts.get(a.overall_level.value, 0) + 1

        dim_counts: dict[str, int] = {}
        for d in self._dimension_scores:
            dim_counts[d.dimension.value] = dim_counts.get(d.dimension.value, 0) + 1

        return {
            "total_assessments": len(self._assessments),
            "total_dimension_scores": len(self._dimension_scores),
            "organization_distribution": org_counts,
            "level_distribution": level_counts,
            "dimension_distribution": dim_counts,
            "max_assessments": self._max_assessments,
            "target_level": self._target_level,
        }
