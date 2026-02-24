"""Incident Communication Planner — stakeholder comms management."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class Audience(StrEnum):
    ENGINEERING = "engineering"
    LEADERSHIP = "leadership"
    CUSTOMERS = "customers"
    PARTNERS = "partners"
    REGULATORS = "regulators"


class CommChannel(StrEnum):
    SLACK = "slack"
    EMAIL = "email"
    STATUS_PAGE = "status_page"
    PHONE_BRIDGE = "phone_bridge"
    SMS = "sms"


class CommCadence(StrEnum):
    EVERY_15MIN = "every_15min"
    EVERY_30MIN = "every_30min"
    HOURLY = "hourly"
    ON_UPDATE = "on_update"
    ON_RESOLUTION = "on_resolution"


# --- Models ---


class CommPlan(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    incident_id: str = ""
    audience: Audience = Audience.ENGINEERING
    channel: CommChannel = CommChannel.SLACK
    cadence: CommCadence = CommCadence.HOURLY
    template: str = ""
    last_sent_at: float = 0.0
    send_count: int = 0
    is_active: bool = True
    created_at: float = Field(default_factory=time.time)


class CommMessage(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    plan_id: str = ""
    audience: Audience = Audience.ENGINEERING
    channel: CommChannel = CommChannel.SLACK
    content: str = ""
    sent_by: str = ""
    sent_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class CommPlannerReport(BaseModel):
    total_plans: int = 0
    total_messages: int = 0
    avg_messages_per_incident: float = 0.0
    by_audience: dict[str, int] = Field(
        default_factory=dict,
    )
    by_channel: dict[str, int] = Field(
        default_factory=dict,
    )
    by_cadence: dict[str, int] = Field(
        default_factory=dict,
    )
    late_comms: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Planner ---


class IncidentCommPlanner:
    """Plan and track incident stakeholder communications."""

    def __init__(
        self,
        max_plans: int = 100000,
        max_overdue_minutes: int = 30,
    ) -> None:
        self._max_plans = max_plans
        self._max_overdue_minutes = max_overdue_minutes
        self._items: list[CommPlan] = []
        self._messages: list[CommMessage] = []
        logger.info(
            "comm_planner.initialized",
            max_plans=max_plans,
            max_overdue_minutes=max_overdue_minutes,
        )

    # -- create / get / list --

    def create_plan(
        self,
        incident_id: str = "",
        audience: Audience = Audience.ENGINEERING,
        channel: CommChannel = CommChannel.SLACK,
        cadence: CommCadence = CommCadence.HOURLY,
        template: str = "",
        **kw: Any,
    ) -> CommPlan:
        """Create a communication plan for an incident."""
        plan = CommPlan(
            incident_id=incident_id,
            audience=audience,
            channel=channel,
            cadence=cadence,
            template=template,
            **kw,
        )
        self._items.append(plan)
        if len(self._items) > self._max_plans:
            self._items.pop(0)
        logger.info(
            "comm_planner.plan_created",
            plan_id=plan.id,
            incident_id=incident_id,
            audience=audience,
        )
        return plan

    def get_plan(
        self,
        plan_id: str,
    ) -> CommPlan | None:
        """Get a single plan by ID."""
        for item in self._items:
            if item.id == plan_id:
                return item
        return None

    def list_plans(
        self,
        incident_id: str | None = None,
        audience: Audience | None = None,
        limit: int = 50,
    ) -> list[CommPlan]:
        """List plans with optional filters."""
        results = list(self._items)
        if incident_id is not None:
            results = [p for p in results if p.incident_id == incident_id]
        if audience is not None:
            results = [p for p in results if p.audience == audience]
        return results[-limit:]

    # -- messaging operations --

    def send_message(
        self,
        plan_id: str,
        content: str,
        sent_by: str = "",
    ) -> CommMessage | None:
        """Record a message sent for a plan."""
        plan = self.get_plan(plan_id)
        if plan is None:
            return None
        msg = CommMessage(
            plan_id=plan_id,
            audience=plan.audience,
            channel=plan.channel,
            content=content,
            sent_by=sent_by,
        )
        self._messages.append(msg)
        plan.last_sent_at = msg.sent_at
        plan.send_count += 1
        logger.info(
            "comm_planner.message_sent",
            plan_id=plan_id,
            message_id=msg.id,
        )
        return msg

    def check_overdue_comms(self) -> list[dict[str, Any]]:
        """Find plans whose cadence is overdue."""
        now = time.time()
        overdue: list[dict[str, Any]] = []
        cadence_minutes = {
            CommCadence.EVERY_15MIN: 15,
            CommCadence.EVERY_30MIN: 30,
            CommCadence.HOURLY: 60,
        }
        for plan in self._items:
            if not plan.is_active:
                continue
            interval = cadence_minutes.get(plan.cadence)
            if interval is None:
                continue
            if plan.last_sent_at == 0.0:
                elapsed = (now - plan.created_at) / 60.0
            else:
                elapsed = (now - plan.last_sent_at) / 60.0
            if elapsed > interval:
                overdue.append(
                    {
                        "plan_id": plan.id,
                        "incident_id": plan.incident_id,
                        "audience": plan.audience.value,
                        "cadence": plan.cadence.value,
                        "overdue_minutes": round(elapsed - interval, 1),
                    }
                )
        return overdue

    def calculate_comm_coverage(
        self,
        incident_id: str,
    ) -> dict[str, Any]:
        """Calculate communication coverage for incident."""
        plans = [p for p in self._items if p.incident_id == incident_id]
        audiences_covered = {p.audience.value for p in plans}
        all_audiences = {a.value for a in Audience}
        missing = all_audiences - audiences_covered
        channels_used = {p.channel.value for p in plans}
        coverage_pct = 0.0
        if all_audiences:
            coverage_pct = round(
                len(audiences_covered) / len(all_audiences) * 100,
                2,
            )
        return {
            "incident_id": incident_id,
            "total_plans": len(plans),
            "audiences_covered": sorted(audiences_covered),
            "audiences_missing": sorted(missing),
            "channels_used": sorted(channels_used),
            "coverage_pct": coverage_pct,
        }

    def analyze_response_times(self) -> dict[str, Any]:
        """Analyze time between plan creation and first msg."""
        plan_first_msg: dict[str, float] = {}
        for msg in self._messages:
            if msg.plan_id not in plan_first_msg:
                plan_first_msg[msg.plan_id] = msg.sent_at
            else:
                plan_first_msg[msg.plan_id] = min(
                    plan_first_msg[msg.plan_id],
                    msg.sent_at,
                )
        response_times: list[float] = []
        for plan in self._items:
            first = plan_first_msg.get(plan.id)
            if first is not None:
                delta = first - plan.created_at
                response_times.append(max(0.0, delta))
        avg_time = 0.0
        if response_times:
            avg_time = round(
                sum(response_times) / len(response_times),
                2,
            )
        return {
            "plans_with_messages": len(response_times),
            "avg_response_time_sec": avg_time,
            "min_response_time_sec": (round(min(response_times), 2) if response_times else 0.0),
            "max_response_time_sec": (round(max(response_times), 2) if response_times else 0.0),
        }

    def detect_communication_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Detect incidents missing audience coverage."""
        incident_ids: set[str] = set()
        for p in self._items:
            if p.incident_id:
                incident_ids.add(p.incident_id)
        gaps: list[dict[str, Any]] = []
        all_audiences = {a.value for a in Audience}
        for inc_id in incident_ids:
            plans = [p for p in self._items if p.incident_id == inc_id]
            covered = {p.audience.value for p in plans}
            missing = all_audiences - covered
            if missing:
                gaps.append(
                    {
                        "incident_id": inc_id,
                        "missing_audiences": sorted(missing),
                        "gap_count": len(missing),
                    }
                )
        gaps.sort(key=lambda x: x["gap_count"], reverse=True)
        return gaps

    # -- report --

    def generate_comm_report(self) -> CommPlannerReport:
        """Generate a comprehensive communication report."""
        by_audience: dict[str, int] = {}
        by_channel: dict[str, int] = {}
        by_cadence: dict[str, int] = {}
        for p in self._items:
            a = p.audience.value
            by_audience[a] = by_audience.get(a, 0) + 1
            ch = p.channel.value
            by_channel[ch] = by_channel.get(ch, 0) + 1
            cd = p.cadence.value
            by_cadence[cd] = by_cadence.get(cd, 0) + 1
        incident_ids = {p.incident_id for p in self._items if p.incident_id}
        avg_per_inc = 0.0
        if incident_ids:
            avg_per_inc = round(len(self._messages) / len(incident_ids), 2)
        late = [p.id for p in self._items if p.is_active and p.send_count == 0]
        recs = self._build_recommendations(
            len(self._items),
            len(self._messages),
            len(late),
        )
        return CommPlannerReport(
            total_plans=len(self._items),
            total_messages=len(self._messages),
            avg_messages_per_incident=avg_per_inc,
            by_audience=by_audience,
            by_channel=by_channel,
            by_cadence=by_cadence,
            late_comms=late,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all data. Returns plans cleared."""
        count = len(self._items)
        self._items.clear()
        self._messages.clear()
        logger.info(
            "comm_planner.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        aud_dist: dict[str, int] = {}
        for p in self._items:
            key = p.audience.value
            aud_dist[key] = aud_dist.get(key, 0) + 1
        return {
            "total_plans": len(self._items),
            "total_messages": len(self._messages),
            "max_plans": self._max_plans,
            "max_overdue_minutes": self._max_overdue_minutes,
            "audience_distribution": aud_dist,
        }

    # -- internal helpers --

    def _build_recommendations(
        self,
        total_plans: int,
        total_messages: int,
        late_count: int,
    ) -> list[str]:
        recs: list[str] = []
        if late_count > 0:
            recs.append(f"{late_count} plan(s) with no messages sent - check cadence adherence")
        if total_plans == 0:
            recs.append("No communication plans created - establish templates")
        if total_messages == 0 and total_plans > 0:
            recs.append("Plans exist but no messages sent - begin communications")
        if not recs:
            recs.append("Communication plans on track")
        return recs
