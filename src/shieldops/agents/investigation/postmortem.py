"""Incident post-mortem report generator.

Auto-generates structured post-mortem reports from incident data, tracks
action items and contributing factors for continuous improvement.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class PostMortemStatus(enum.StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ActionItemStatus(enum.StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WONT_FIX = "wont_fix"


class Severity(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# -- Models --------------------------------------------------------------------


class ContributingFactor(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str
    category: str = ""
    is_root_cause: bool = False


class ActionItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    description: str = ""
    assignee: str = ""
    status: ActionItemStatus = ActionItemStatus.OPEN
    priority: str = "medium"
    due_date: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class PostMortemReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    incident_id: str
    title: str
    summary: str = ""
    severity: Severity = Severity.MEDIUM
    status: PostMortemStatus = PostMortemStatus.DRAFT
    contributing_factors: list[ContributingFactor] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    timeline_summary: str = ""
    impact_description: str = ""
    detection_method: str = ""
    resolution_summary: str = ""
    lessons_learned: list[str] = Field(default_factory=list)
    attendees: list[str] = Field(default_factory=list)
    duration_minutes: float = 0.0
    services_affected: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    published_at: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# -- Generator -----------------------------------------------------------------


class PostMortemGenerator:
    """Generate and manage incident post-mortem reports.

    Parameters
    ----------
    max_reports:
        Maximum number of reports to store.
    """

    def __init__(self, max_reports: int = 1000) -> None:
        self._reports: dict[str, PostMortemReport] = {}
        self._max_reports = max_reports

    def generate(
        self,
        incident_id: str,
        title: str,
        summary: str = "",
        severity: Severity = Severity.MEDIUM,
        contributing_factors: list[dict[str, Any]] | None = None,
        timeline_summary: str = "",
        impact_description: str = "",
        detection_method: str = "",
        resolution_summary: str = "",
        lessons_learned: list[str] | None = None,
        services_affected: list[str] | None = None,
        duration_minutes: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> PostMortemReport:
        if len(self._reports) >= self._max_reports:
            logger.warning("postmortem_limit_reached", max=self._max_reports)
            raise ValueError(f"Maximum reports limit reached: {self._max_reports}")

        factors = [ContributingFactor(**f) for f in (contributing_factors or [])]
        report = PostMortemReport(
            incident_id=incident_id,
            title=title,
            summary=summary,
            severity=severity,
            contributing_factors=factors,
            timeline_summary=timeline_summary,
            impact_description=impact_description,
            detection_method=detection_method,
            resolution_summary=resolution_summary,
            lessons_learned=lessons_learned or [],
            services_affected=services_affected or [],
            duration_minutes=duration_minutes,
            metadata=metadata or {},
        )
        self._reports[report.id] = report
        logger.info("postmortem_generated", report_id=report.id, incident_id=incident_id)
        return report

    def get_report(self, report_id: str) -> PostMortemReport | None:
        return self._reports.get(report_id)

    def list_reports(
        self,
        status: PostMortemStatus | None = None,
        limit: int = 50,
    ) -> list[PostMortemReport]:
        reports = sorted(self._reports.values(), key=lambda r: r.created_at, reverse=True)
        if status:
            reports = [r for r in reports if r.status == status]
        return reports[:limit]

    def update_status(
        self,
        report_id: str,
        status: PostMortemStatus,
    ) -> PostMortemReport | None:
        report = self._reports.get(report_id)
        if report is None:
            return None
        report.status = status
        report.updated_at = time.time()
        if status == PostMortemStatus.PUBLISHED:
            report.published_at = time.time()
        logger.info("postmortem_status_updated", report_id=report_id, status=status)
        return report

    def add_action_item(
        self,
        report_id: str,
        title: str,
        description: str = "",
        assignee: str = "",
        priority: str = "medium",
        due_date: str = "",
    ) -> ActionItem | None:
        report = self._reports.get(report_id)
        if report is None:
            return None
        item = ActionItem(
            title=title,
            description=description,
            assignee=assignee,
            priority=priority,
            due_date=due_date,
        )
        report.action_items.append(item)
        report.updated_at = time.time()
        logger.info("postmortem_action_item_added", report_id=report_id, item_id=item.id)
        return item

    def update_action_item(
        self,
        report_id: str,
        item_id: str,
        status: ActionItemStatus | None = None,
        assignee: str | None = None,
    ) -> ActionItem | None:
        report = self._reports.get(report_id)
        if report is None:
            return None
        for item in report.action_items:
            if item.id == item_id:
                if status is not None:
                    item.status = status
                if assignee is not None:
                    item.assignee = assignee
                item.updated_at = time.time()
                report.updated_at = time.time()
                return item
        return None

    def get_open_action_items(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for report in self._reports.values():
            for item in report.action_items:
                if item.status in (ActionItemStatus.OPEN, ActionItemStatus.IN_PROGRESS):
                    result.append(
                        {
                            "report_id": report.id,
                            "incident_id": report.incident_id,
                            **item.model_dump(),
                        }
                    )
        return result

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        total_action_items = 0
        open_action_items = 0
        for r in self._reports.values():
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            total_action_items += len(r.action_items)
            open_action_items += sum(
                1
                for ai in r.action_items
                if ai.status in (ActionItemStatus.OPEN, ActionItemStatus.IN_PROGRESS)
            )
        return {
            "total_reports": len(self._reports),
            "by_status": by_status,
            "total_action_items": total_action_items,
            "open_action_items": open_action_items,
        }
