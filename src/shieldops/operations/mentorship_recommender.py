"""Mentorship Recommender — match mentors and mentees for skill development."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SkillArea(StrEnum):
    INCIDENT_RESPONSE = "incident_response"
    CLOUD_INFRA = "cloud_infra"
    SECURITY_OPS = "security_ops"
    AUTOMATION = "automation"
    ARCHITECTURE = "architecture"


class MentorshipType(StrEnum):
    FORMAL = "formal"
    INFORMAL = "informal"
    PEER = "peer"
    REVERSE = "reverse"
    GROUP = "group"


class MatchQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    INCOMPATIBLE = "incompatible"


# --- Models ---


class MentorshipRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mentor: str = ""
    mentee: str = ""
    team: str = ""
    skill_area: SkillArea = SkillArea.INCIDENT_RESPONSE
    mentorship_type: MentorshipType = MentorshipType.FORMAL
    match_quality: MatchQuality = MatchQuality.GOOD
    match_score: float = 0.0
    sessions_completed: int = 0
    created_at: float = Field(default_factory=time.time)


class MentorshipAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mentor: str = ""
    skill_area: SkillArea = SkillArea.INCIDENT_RESPONSE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MentorshipReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_match_score: float = 0.0
    by_skill_area: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MentorshipRecommender:
    """Match mentors and mentees based on skill areas and team composition."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[MentorshipRecord] = []
        self._analyses: list[MentorshipAnalysis] = []
        logger.info(
            "mentorship_recommender.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_mentorship(
        self,
        mentor: str,
        mentee: str = "",
        team: str = "",
        skill_area: SkillArea = SkillArea.INCIDENT_RESPONSE,
        mentorship_type: MentorshipType = MentorshipType.FORMAL,
        match_quality: MatchQuality = MatchQuality.GOOD,
        match_score: float = 0.0,
        sessions_completed: int = 0,
    ) -> MentorshipRecord:
        record = MentorshipRecord(
            mentor=mentor,
            mentee=mentee,
            team=team,
            skill_area=skill_area,
            mentorship_type=mentorship_type,
            match_quality=match_quality,
            match_score=match_score,
            sessions_completed=sessions_completed,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "mentorship_recommender.mentorship_recorded",
            record_id=record.id,
            mentor=mentor,
            skill_area=skill_area.value,
            match_quality=match_quality.value,
        )
        return record

    def get_mentorship(self, record_id: str) -> MentorshipRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_mentorships(
        self,
        skill_area: SkillArea | None = None,
        mentorship_type: MentorshipType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MentorshipRecord]:
        results = list(self._records)
        if skill_area is not None:
            results = [r for r in results if r.skill_area == skill_area]
        if mentorship_type is not None:
            results = [r for r in results if r.mentorship_type == mentorship_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        mentor: str,
        skill_area: SkillArea = SkillArea.INCIDENT_RESPONSE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MentorshipAnalysis:
        analysis = MentorshipAnalysis(
            mentor=mentor,
            skill_area=skill_area,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "mentorship_recommender.analysis_added",
            mentor=mentor,
            skill_area=skill_area.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by skill_area; return count and avg match_score."""
        area_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.skill_area.value
            area_data.setdefault(key, []).append(r.match_score)
        result: dict[str, Any] = {}
        for area, scores in area_data.items():
            result[area] = {
                "count": len(scores),
                "avg_match_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_mentorship_gaps(self) -> list[dict[str, Any]]:
        """Return records where match_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.match_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "mentor": r.mentor,
                        "mentee": r.mentee,
                        "skill_area": r.skill_area.value,
                        "match_score": r.match_score,
                    }
                )
        return sorted(results, key=lambda x: x["match_score"])

    def rank_by_match(self) -> list[dict[str, Any]]:
        """Group by mentor, avg match_score, sort descending."""
        mentor_scores: dict[str, list[float]] = {}
        for r in self._records:
            mentor_scores.setdefault(r.mentor, []).append(r.match_score)
        results: list[dict[str, Any]] = []
        for mentor, scores in mentor_scores.items():
            results.append(
                {
                    "mentor": mentor,
                    "avg_match_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_match_score"], reverse=True)
        return results

    def detect_mentorship_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> MentorshipReport:
        by_skill_area: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_quality: dict[str, int] = {}
        for r in self._records:
            by_skill_area[r.skill_area.value] = by_skill_area.get(r.skill_area.value, 0) + 1
            by_type[r.mentorship_type.value] = by_type.get(r.mentorship_type.value, 0) + 1
            by_quality[r.match_quality.value] = by_quality.get(r.match_quality.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.match_score < self._threshold)
        scores = [r.match_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_mentorship_gaps()
        top_gaps = [o["mentor"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} mentorship pair(s) below match threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg match score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Mentorship program is healthy")
        return MentorshipReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_match_score=avg_score,
            by_skill_area=by_skill_area,
            by_type=by_type,
            by_quality=by_quality,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("mentorship_recommender.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        area_dist: dict[str, int] = {}
        for r in self._records:
            key = r.skill_area.value
            area_dist[key] = area_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "skill_area_distribution": area_dist,
            "unique_mentors": len({r.mentor for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
