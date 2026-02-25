"""Incident Learning Tracker — track lessons learned and verify adoption."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LessonStatus(StrEnum):
    IDENTIFIED = "identified"
    DOCUMENTED = "documented"
    SHARED = "shared"
    APPLIED = "applied"
    VERIFIED = "verified"


class LessonCategory(StrEnum):
    ROOT_CAUSE = "root_cause"
    DETECTION = "detection"
    RESPONSE = "response"
    COMMUNICATION = "communication"
    ARCHITECTURE = "architecture"


class AdoptionLevel(StrEnum):
    NOT_ADOPTED = "not_adopted"
    PARTIALLY_ADOPTED = "partially_adopted"
    MOSTLY_ADOPTED = "mostly_adopted"
    FULLY_ADOPTED = "fully_adopted"
    EXCEEDS = "exceeds"


# --- Models ---


class LessonRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    title: str = ""
    category: LessonCategory = LessonCategory.ROOT_CAUSE
    status: LessonStatus = LessonStatus.IDENTIFIED
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class LessonApplication(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lesson_id: str = ""
    team: str = ""
    adoption_level: AdoptionLevel = AdoptionLevel.NOT_ADOPTED
    evidence: str = ""
    created_at: float = Field(default_factory=time.time)


class LearningTrackerReport(BaseModel):
    total_lessons: int = 0
    total_applications: int = 0
    adoption_rate_pct: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    unapplied_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentLearningTracker:
    """Track lessons learned from incidents and verify adoption."""

    def __init__(
        self,
        max_records: int = 200000,
        min_adoption_rate_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_adoption_rate_pct = min_adoption_rate_pct
        self._records: list[LessonRecord] = []
        self._applications: list[LessonApplication] = []
        logger.info(
            "learning_tracker.initialized",
            max_records=max_records,
            min_adoption_rate_pct=min_adoption_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_lesson(
        self,
        incident_id: str,
        title: str,
        category: LessonCategory = LessonCategory.ROOT_CAUSE,
        status: LessonStatus = LessonStatus.IDENTIFIED,
        team: str = "",
        details: str = "",
    ) -> LessonRecord:
        record = LessonRecord(
            incident_id=incident_id,
            title=title,
            category=category,
            status=status,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "learning_tracker.lesson_recorded",
            record_id=record.id,
            incident_id=incident_id,
            title=title,
            category=category.value,
        )
        return record

    def get_lesson(self, record_id: str) -> LessonRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_lessons(
        self,
        incident_id: str | None = None,
        category: LessonCategory | None = None,
        status: LessonStatus | None = None,
        limit: int = 50,
    ) -> list[LessonRecord]:
        results = list(self._records)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        if category is not None:
            results = [r for r in results if r.category == category]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    def record_application(
        self,
        lesson_id: str,
        team: str = "",
        adoption_level: AdoptionLevel = AdoptionLevel.NOT_ADOPTED,
        evidence: str = "",
    ) -> LessonApplication:
        app = LessonApplication(
            lesson_id=lesson_id,
            team=team,
            adoption_level=adoption_level,
            evidence=evidence,
        )
        self._applications.append(app)
        if len(self._applications) > self._max_records:
            self._applications = self._applications[-self._max_records :]
        logger.info(
            "learning_tracker.application_recorded",
            lesson_id=lesson_id,
            team=team,
            adoption_level=adoption_level.value,
        )
        return app

    def update_lesson_status(self, record_id: str, status: LessonStatus) -> LessonRecord | None:
        for r in self._records:
            if r.id == record_id:
                r.status = status
                logger.info(
                    "learning_tracker.status_updated",
                    record_id=record_id,
                    new_status=status.value,
                )
                return r
        return None

    # -- domain operations -----------------------------------------------

    def calculate_adoption_rate(self) -> dict[str, Any]:
        """Calculate overall lesson adoption rate."""
        if not self._records:
            return {"total": 0, "applied": 0, "adoption_rate_pct": 0.0}
        applied = sum(
            1 for r in self._records if r.status in (LessonStatus.APPLIED, LessonStatus.VERIFIED)
        )
        rate = round((applied / len(self._records)) * 100, 2)
        return {
            "total": len(self._records),
            "applied": applied,
            "adoption_rate_pct": rate,
        }

    def identify_unapplied_lessons(self) -> list[dict[str, Any]]:
        """Find lessons that haven't been applied."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.status in (
                LessonStatus.IDENTIFIED,
                LessonStatus.DOCUMENTED,
                LessonStatus.SHARED,
            ):
                results.append(
                    {
                        "lesson_id": r.id,
                        "incident_id": r.incident_id,
                        "title": r.title,
                        "category": r.category.value,
                        "status": r.status.value,
                        "team": r.team,
                    }
                )
        return results

    def analyze_team_learning(self) -> list[dict[str, Any]]:
        """Analyze learning adoption per team."""
        team_total: dict[str, int] = {}
        team_applied: dict[str, int] = {}
        for r in self._records:
            if r.team:
                team_total[r.team] = team_total.get(r.team, 0) + 1
                if r.status in (LessonStatus.APPLIED, LessonStatus.VERIFIED):
                    team_applied[r.team] = team_applied.get(r.team, 0) + 1
        results: list[dict[str, Any]] = []
        for team, total in team_total.items():
            applied = team_applied.get(team, 0)
            rate = round((applied / total) * 100, 2)
            results.append(
                {
                    "team": team,
                    "total_lessons": total,
                    "applied": applied,
                    "adoption_rate_pct": rate,
                }
            )
        results.sort(key=lambda x: x["adoption_rate_pct"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> LearningTrackerReport:
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
        adoption = self.calculate_adoption_rate()
        unapplied = len(self.identify_unapplied_lessons())
        recs: list[str] = []
        if adoption["adoption_rate_pct"] < self._min_adoption_rate_pct:
            recs.append(
                f"Adoption rate {adoption['adoption_rate_pct']}% below "
                f"target of {self._min_adoption_rate_pct}%"
            )
        if unapplied > 0:
            recs.append(f"{unapplied} lesson(s) not yet applied")
        if not recs:
            recs.append("Incident learning adoption meets targets")
        return LearningTrackerReport(
            total_lessons=len(self._records),
            total_applications=len(self._applications),
            adoption_rate_pct=adoption["adoption_rate_pct"],
            by_status=by_status,
            by_category=by_category,
            unapplied_count=unapplied,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._applications.clear()
        logger.info("learning_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_lessons": len(self._records),
            "total_applications": len(self._applications),
            "min_adoption_rate_pct": self._min_adoption_rate_pct,
            "status_distribution": status_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
