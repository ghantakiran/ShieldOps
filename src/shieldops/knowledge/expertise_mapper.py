"""Team Expertise Mapper — map team expertise, identify gaps, track skill coverage."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExpertiseArea(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    SECURITY = "security"
    DATABASE = "database"
    NETWORKING = "networking"


class ExpertiseLevel(StrEnum):
    EXPERT = "expert"
    ADVANCED = "advanced"
    INTERMEDIATE = "intermediate"
    BEGINNER = "beginner"
    NONE = "none"


class ExpertiseGap(StrEnum):
    CRITICAL_GAP = "critical_gap"
    SINGLE_POINT_OF_FAILURE = "single_point_of_failure"
    UNDERSTAFFED = "understaffed"
    ADEQUATE = "adequate"
    WELL_COVERED = "well_covered"


# --- Models ---


class ExpertiseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_member: str = ""
    expertise_area: ExpertiseArea = ExpertiseArea.INFRASTRUCTURE
    expertise_level: ExpertiseLevel = ExpertiseLevel.NONE
    expertise_gap: ExpertiseGap = ExpertiseGap.CRITICAL_GAP
    coverage_pct: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SkillAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_name: str = ""
    expertise_area: ExpertiseArea = ExpertiseArea.INFRASTRUCTURE
    skill_score: float = 0.0
    assessed_members: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TeamExpertiseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    covered_areas: int = 0
    avg_coverage_pct: float = 0.0
    by_area: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_gap: dict[str, int] = Field(default_factory=dict)
    gap_areas: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamExpertiseMapper:
    """Map team expertise, identify gaps, track skill coverage across areas."""

    def __init__(
        self,
        max_records: int = 200000,
        min_expertise_coverage_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_expertise_coverage_pct = min_expertise_coverage_pct
        self._records: list[ExpertiseRecord] = []
        self._assessments: list[SkillAssessment] = []
        logger.info(
            "expertise_mapper.initialized",
            max_records=max_records,
            min_expertise_coverage_pct=min_expertise_coverage_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_expertise(
        self,
        team_member: str,
        expertise_area: ExpertiseArea = ExpertiseArea.INFRASTRUCTURE,
        expertise_level: ExpertiseLevel = ExpertiseLevel.NONE,
        expertise_gap: ExpertiseGap = ExpertiseGap.CRITICAL_GAP,
        coverage_pct: float = 0.0,
        team: str = "",
    ) -> ExpertiseRecord:
        record = ExpertiseRecord(
            team_member=team_member,
            expertise_area=expertise_area,
            expertise_level=expertise_level,
            expertise_gap=expertise_gap,
            coverage_pct=coverage_pct,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "expertise_mapper.expertise_recorded",
            record_id=record.id,
            team_member=team_member,
            expertise_area=expertise_area.value,
            expertise_level=expertise_level.value,
        )
        return record

    def get_expertise(self, record_id: str) -> ExpertiseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_expertise(
        self,
        expertise_area: ExpertiseArea | None = None,
        expertise_level: ExpertiseLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ExpertiseRecord]:
        results = list(self._records)
        if expertise_area is not None:
            results = [r for r in results if r.expertise_area == expertise_area]
        if expertise_level is not None:
            results = [r for r in results if r.expertise_level == expertise_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        assessment_name: str,
        expertise_area: ExpertiseArea = ExpertiseArea.INFRASTRUCTURE,
        skill_score: float = 0.0,
        assessed_members: int = 0,
        description: str = "",
    ) -> SkillAssessment:
        assessment = SkillAssessment(
            assessment_name=assessment_name,
            expertise_area=expertise_area,
            skill_score=skill_score,
            assessed_members=assessed_members,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "expertise_mapper.assessment_added",
            assessment_name=assessment_name,
            expertise_area=expertise_area.value,
            skill_score=skill_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_expertise_distribution(self) -> dict[str, Any]:
        """Group by expertise_area; return count and avg coverage_pct per area."""
        area_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.expertise_area.value
            area_data.setdefault(key, []).append(r.coverage_pct)
        result: dict[str, Any] = {}
        for area, pcts in area_data.items():
            result[area] = {
                "count": len(pcts),
                "avg_coverage_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_expertise_gaps(self) -> list[dict[str, Any]]:
        """Return records where coverage_pct < min_expertise_coverage_pct."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_pct < self._min_expertise_coverage_pct:
                results.append(
                    {
                        "record_id": r.id,
                        "team_member": r.team_member,
                        "coverage_pct": r.coverage_pct,
                        "expertise_area": r.expertise_area.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_coverage_score(self) -> list[dict[str, Any]]:
        """Group by team, total coverage_pct, sort descending."""
        team_scores: dict[str, float] = {}
        for r in self._records:
            team_scores[r.team] = team_scores.get(r.team, 0) + r.coverage_pct
        results: list[dict[str, Any]] = []
        for team, total in team_scores.items():
            results.append(
                {
                    "team": team,
                    "total_coverage": total,
                }
            )
        results.sort(key=lambda x: x["total_coverage"], reverse=True)
        return results

    def detect_expertise_trends(self) -> dict[str, Any]:
        """Split-half on coverage_pct; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [r.coverage_pct for r in self._records]
        mid = len(counts) // 2
        first_half = counts[:mid]
        second_half = counts[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> TeamExpertiseReport:
        by_area: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_gap: dict[str, int] = {}
        for r in self._records:
            by_area[r.expertise_area.value] = by_area.get(r.expertise_area.value, 0) + 1
            by_level[r.expertise_level.value] = by_level.get(r.expertise_level.value, 0) + 1
            by_gap[r.expertise_gap.value] = by_gap.get(r.expertise_gap.value, 0) + 1
        gap_count = sum(
            1 for r in self._records if r.coverage_pct < self._min_expertise_coverage_pct
        )
        covered_areas = len({r.expertise_area for r in self._records if r.coverage_pct > 0})
        avg_cov = (
            round(sum(r.coverage_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        gap_area_ids = [
            r.team_member
            for r in self._records
            if r.coverage_pct < self._min_expertise_coverage_pct
        ][:5]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(
                f"{gap_count} member(s) below minimum coverage"
                f" ({self._min_expertise_coverage_pct}%)"
            )
        if self._records and avg_cov < self._min_expertise_coverage_pct:
            recs.append(
                f"Average coverage {avg_cov}% is below threshold"
                f" ({self._min_expertise_coverage_pct}%)"
            )
        if not recs:
            recs.append("Team expertise coverage levels are healthy")
        return TeamExpertiseReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            covered_areas=covered_areas,
            avg_coverage_pct=avg_cov,
            by_area=by_area,
            by_level=by_level,
            by_gap=by_gap,
            gap_areas=gap_area_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("expertise_mapper.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        area_dist: dict[str, int] = {}
        for r in self._records:
            key = r.expertise_area.value
            area_dist[key] = area_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "min_expertise_coverage_pct": self._min_expertise_coverage_pct,
            "area_distribution": area_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_members": len({r.team_member for r in self._records}),
        }
