"""Incident Learning Tracker — tracks lessons learned and feeds back into agents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LessonCategory(StrEnum):
    ROOT_CAUSE = "root_cause"
    DETECTION = "detection"
    RESPONSE = "response"
    PREVENTION = "prevention"
    PROCESS = "process"


class LessonPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class IncidentLesson(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    title: str
    description: str = ""
    category: LessonCategory
    priority: LessonPriority = LessonPriority.MEDIUM
    action_items: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    learned_by: str = ""
    created_at: float = Field(default_factory=time.time)


class LessonApplication(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lesson_id: str
    applied_to: str = ""
    result: str = ""
    success: bool = False
    applied_at: float = Field(default_factory=time.time)


# --- Tracker ---


class IncidentLearningTracker:
    """Tracks incident lessons and feeds them back into agent behaviour."""

    def __init__(
        self,
        max_lessons: int = 10000,
        max_applications: int = 50000,
    ) -> None:
        self._max_lessons = max_lessons
        self._max_applications = max_applications
        self._lessons: dict[str, IncidentLesson] = {}
        self._applications: list[LessonApplication] = []
        logger.info(
            "incident_learning_tracker.initialized",
            max_lessons=max_lessons,
            max_applications=max_applications,
        )

    def record_lesson(
        self,
        incident_id: str,
        title: str,
        category: LessonCategory,
        **kw: Any,
    ) -> IncidentLesson:
        """Record a lesson learned from an incident."""
        lesson = IncidentLesson(
            incident_id=incident_id,
            title=title,
            category=category,
            **kw,
        )
        self._lessons[lesson.id] = lesson
        if len(self._lessons) > self._max_lessons:
            oldest = next(iter(self._lessons))
            del self._lessons[oldest]
        logger.info(
            "incident_learning_tracker.lesson_recorded",
            lesson_id=lesson.id,
            incident_id=incident_id,
            title=title,
            category=category,
        )
        return lesson

    def apply_lesson(
        self,
        lesson_id: str,
        applied_to: str,
        result: str = "",
        success: bool = False,
    ) -> LessonApplication:
        """Record that a lesson was applied somewhere."""
        app = LessonApplication(
            lesson_id=lesson_id,
            applied_to=applied_to,
            result=result,
            success=success,
        )
        self._applications.append(app)
        if len(self._applications) > self._max_applications:
            self._applications = self._applications[-self._max_applications :]
        logger.info(
            "incident_learning_tracker.lesson_applied",
            application_id=app.id,
            lesson_id=lesson_id,
            applied_to=applied_to,
            success=success,
        )
        return app

    def get_lesson(self, lesson_id: str) -> IncidentLesson | None:
        """Retrieve a lesson by ID."""
        return self._lessons.get(lesson_id)

    def list_lessons(
        self,
        category: LessonCategory | None = None,
        priority: LessonPriority | None = None,
        tag: str | None = None,
    ) -> list[IncidentLesson]:
        """List lessons with optional filters."""
        results = list(self._lessons.values())
        if category is not None:
            results = [les for les in results if les.category == category]
        if priority is not None:
            results = [les for les in results if les.priority == priority]
        if tag is not None:
            results = [les for les in results if tag in les.tags]
        return results

    def search_lessons(self, query: str) -> list[IncidentLesson]:
        """Search lessons by substring match on title + description."""
        q = query.lower()
        return [
            les
            for les in self._lessons.values()
            if q in les.title.lower() or q in les.description.lower()
        ]

    def get_applications(
        self,
        lesson_id: str | None = None,
    ) -> list[LessonApplication]:
        """List applications, optionally filtered by lesson ID."""
        if lesson_id is not None:
            return [a for a in self._applications if a.lesson_id == lesson_id]
        return list(self._applications)

    def get_effective_lessons(self) -> list[IncidentLesson]:
        """Lessons that have been successfully applied at least once."""
        successful_ids: set[str] = {a.lesson_id for a in self._applications if a.success}
        return [les for les in self._lessons.values() if les.id in successful_ids]

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        category_counts: dict[str, int] = {}
        priority_counts: dict[str, int] = {}
        for les in self._lessons.values():
            category_counts[les.category] = category_counts.get(les.category, 0) + 1
            priority_counts[les.priority] = priority_counts.get(les.priority, 0) + 1
        total_apps = len(self._applications)
        successful_apps = sum(1 for a in self._applications if a.success)
        effective = len(self.get_effective_lessons())
        return {
            "total_lessons": len(self._lessons),
            "total_applications": total_apps,
            "successful_applications": successful_apps,
            "effective_lessons": effective,
            "category_distribution": category_counts,
            "priority_distribution": priority_counts,
            "application_success_rate": (
                round(successful_apps / total_apps, 4) if total_apps else 0.0
            ),
        }
