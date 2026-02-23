"""Incident retrospective management with action item tracking."""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class RetroStatus(enum.StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ActionItemPriority(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# -- Models --------------------------------------------------------------------


class ActionItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str
    assignee: str = ""
    priority: ActionItemPriority = ActionItemPriority.MEDIUM
    status: str = "open"
    due_date: float | None = None
    completed_at: float | None = None
    created_at: float = Field(default_factory=time.time)


class Retrospective(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    incident_id: str
    title: str
    status: RetroStatus = RetroStatus.SCHEDULED
    scheduled_at: float | None = None
    timeline: str = ""
    root_cause: str = ""
    impact_summary: str = ""
    lessons_learned: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    facilitator: str = ""
    participants: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = None


# -- Manager -------------------------------------------------------------------


class RetrospectiveManager:
    """Manage incident retrospectives and follow-up action items.

    Parameters
    ----------
    max_retros:
        Maximum number of retrospectives to store.
    default_schedule_hours:
        Default hours from now to schedule a retrospective if no time given.
    """

    def __init__(
        self,
        max_retros: int = 500,
        default_schedule_hours: int = 48,
    ) -> None:
        self._retros: dict[str, Retrospective] = {}
        self._max_retros = max_retros
        self._default_schedule_hours = default_schedule_hours

    def create_retrospective(
        self,
        incident_id: str,
        title: str,
        scheduled_at: float | None = None,
        facilitator: str = "",
        participants: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Retrospective:
        if len(self._retros) >= self._max_retros:
            raise ValueError(f"Maximum retrospectives limit reached: {self._max_retros}")
        if scheduled_at is None:
            scheduled_at = time.time() + self._default_schedule_hours * 3600
        retro = Retrospective(
            incident_id=incident_id,
            title=title,
            scheduled_at=scheduled_at,
            facilitator=facilitator,
            participants=participants or [],
            metadata=metadata or {},
        )
        self._retros[retro.id] = retro
        logger.info(
            "retrospective_created",
            retro_id=retro.id,
            incident_id=incident_id,
        )
        return retro

    def start_retrospective(self, retro_id: str) -> Retrospective | None:
        retro = self._retros.get(retro_id)
        if retro is None:
            return None
        retro.status = RetroStatus.IN_PROGRESS
        logger.info("retrospective_started", retro_id=retro_id)
        return retro

    def complete_retrospective(
        self,
        retro_id: str,
        timeline: str = "",
        root_cause: str = "",
        impact_summary: str = "",
        lessons_learned: list[str] | None = None,
    ) -> Retrospective | None:
        retro = self._retros.get(retro_id)
        if retro is None:
            return None
        retro.status = RetroStatus.COMPLETED
        retro.completed_at = time.time()
        if timeline:
            retro.timeline = timeline
        if root_cause:
            retro.root_cause = root_cause
        if impact_summary:
            retro.impact_summary = impact_summary
        if lessons_learned:
            retro.lessons_learned = lessons_learned
        logger.info("retrospective_completed", retro_id=retro_id)
        return retro

    def cancel_retrospective(self, retro_id: str) -> Retrospective | None:
        retro = self._retros.get(retro_id)
        if retro is None:
            return None
        retro.status = RetroStatus.CANCELLED
        logger.info("retrospective_cancelled", retro_id=retro_id)
        return retro

    def add_action_item(
        self,
        retro_id: str,
        description: str,
        assignee: str = "",
        priority: ActionItemPriority = ActionItemPriority.MEDIUM,
        due_date: float | None = None,
    ) -> ActionItem | None:
        retro = self._retros.get(retro_id)
        if retro is None:
            return None
        item = ActionItem(
            description=description,
            assignee=assignee,
            priority=priority,
            due_date=due_date,
        )
        retro.action_items.append(item)
        logger.info(
            "retrospective_action_item_added",
            retro_id=retro_id,
            item_id=item.id,
        )
        return item

    def complete_action_item(
        self,
        retro_id: str,
        item_id: str,
    ) -> ActionItem | None:
        retro = self._retros.get(retro_id)
        if retro is None:
            return None
        for item in retro.action_items:
            if item.id == item_id:
                item.status = "completed"
                item.completed_at = time.time()
                logger.info(
                    "retrospective_action_item_completed",
                    retro_id=retro_id,
                    item_id=item_id,
                )
                return item
        return None

    def get_retrospective(self, retro_id: str) -> Retrospective | None:
        return self._retros.get(retro_id)

    def list_retrospectives(
        self,
        status: RetroStatus | None = None,
        incident_id: str | None = None,
    ) -> list[Retrospective]:
        retros = list(self._retros.values())
        if status:
            retros = [r for r in retros if r.status == status]
        if incident_id:
            retros = [r for r in retros if r.incident_id == incident_id]
        return retros

    def get_overdue_actions(self) -> list[dict[str, Any]]:
        now = time.time()
        overdue: list[dict[str, Any]] = []
        for retro in self._retros.values():
            for item in retro.action_items:
                if item.status == "open" and item.due_date is not None and now > item.due_date:
                    overdue.append(
                        {
                            "retro_id": retro.id,
                            "incident_id": retro.incident_id,
                            "item_id": item.id,
                            "description": item.description,
                            "assignee": item.assignee,
                            "priority": item.priority,
                            "due_date": item.due_date,
                            "overdue_seconds": now - item.due_date,
                        }
                    )
        return overdue

    def get_stats(self) -> dict[str, Any]:
        scheduled = sum(1 for r in self._retros.values() if r.status == RetroStatus.SCHEDULED)
        in_progress = sum(1 for r in self._retros.values() if r.status == RetroStatus.IN_PROGRESS)
        completed = sum(1 for r in self._retros.values() if r.status == RetroStatus.COMPLETED)
        total_action_items = sum(len(r.action_items) for r in self._retros.values())
        open_action_items = sum(
            1 for r in self._retros.values() for item in r.action_items if item.status == "open"
        )
        overdue_action_items = len(self.get_overdue_actions())
        return {
            "total_retrospectives": len(self._retros),
            "scheduled": scheduled,
            "in_progress": in_progress,
            "completed": completed,
            "total_action_items": total_action_items,
            "open_action_items": open_action_items,
            "overdue_action_items": overdue_action_items,
        }
