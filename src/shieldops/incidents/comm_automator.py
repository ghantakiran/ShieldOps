"""Incident Communication Automator — auto-generate status updates."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CommChannel(StrEnum):
    SLACK = "slack"
    EMAIL = "email"
    TEAMS = "teams"
    STATUS_PAGE = "status_page"
    EXECUTIVE_BRIEF = "executive_brief"


class CommType(StrEnum):
    INITIAL_NOTIFICATION = "initial_notification"
    STATUS_UPDATE = "status_update"
    ESCALATION = "escalation"
    RESOLUTION = "resolution"
    POST_MORTEM = "post_mortem"


class CommAudience(StrEnum):
    ENGINEERING = "engineering"
    MANAGEMENT = "management"
    CUSTOMERS = "customers"
    EXECUTIVES = "executives"
    ALL_HANDS = "all_hands"


# --- Models ---


class CommRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_name: str = ""
    channel: CommChannel = CommChannel.SLACK
    comm_type: CommType = CommType.INITIAL_NOTIFICATION
    audience: CommAudience = CommAudience.ENGINEERING
    delivery_success: bool = True
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CommTemplate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    template_name: str = ""
    channel: CommChannel = CommChannel.SLACK
    comm_type: CommType = CommType.INITIAL_NOTIFICATION
    audience: CommAudience = CommAudience.ENGINEERING
    auto_send: bool = False
    delay_minutes: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CommAutomatorReport(BaseModel):
    total_comms: int = 0
    total_templates: int = 0
    delivery_rate_pct: float = 0.0
    by_channel: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    failed_delivery_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentCommunicationAutomator:
    """Auto-generate incident status updates."""

    def __init__(
        self,
        max_records: int = 200000,
        min_delivery_rate_pct: float = 95.0,
    ) -> None:
        self._max_records = max_records
        self._min_delivery_rate_pct = min_delivery_rate_pct
        self._records: list[CommRecord] = []
        self._templates: list[CommTemplate] = []
        logger.info(
            "comm_automator.initialized",
            max_records=max_records,
            min_delivery_rate_pct=min_delivery_rate_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_comm(
        self,
        incident_name: str,
        channel: CommChannel = CommChannel.SLACK,
        comm_type: CommType = (CommType.INITIAL_NOTIFICATION),
        audience: CommAudience = (CommAudience.ENGINEERING),
        delivery_success: bool = True,
        details: str = "",
    ) -> CommRecord:
        record = CommRecord(
            incident_name=incident_name,
            channel=channel,
            comm_type=comm_type,
            audience=audience,
            delivery_success=delivery_success,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "comm_automator.recorded",
            record_id=record.id,
            incident_name=incident_name,
            channel=channel.value,
            comm_type=comm_type.value,
        )
        return record

    def get_comm(self, record_id: str) -> CommRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_comms(
        self,
        incident_name: str | None = None,
        channel: CommChannel | None = None,
        limit: int = 50,
    ) -> list[CommRecord]:
        results = list(self._records)
        if incident_name is not None:
            results = [r for r in results if r.incident_name == incident_name]
        if channel is not None:
            results = [r for r in results if r.channel == channel]
        return results[-limit:]

    def add_template(
        self,
        template_name: str,
        channel: CommChannel = CommChannel.SLACK,
        comm_type: CommType = (CommType.INITIAL_NOTIFICATION),
        audience: CommAudience = (CommAudience.ENGINEERING),
        auto_send: bool = False,
        delay_minutes: float = 0.0,
    ) -> CommTemplate:
        template = CommTemplate(
            template_name=template_name,
            channel=channel,
            comm_type=comm_type,
            audience=audience,
            auto_send=auto_send,
            delay_minutes=delay_minutes,
        )
        self._templates.append(template)
        if len(self._templates) > self._max_records:
            self._templates = self._templates[-self._max_records :]
        logger.info(
            "comm_automator.template_added",
            template_name=template_name,
            channel=channel.value,
            comm_type=comm_type.value,
        )
        return template

    # -- domain operations -------------------------------------------

    def analyze_comm_effectiveness(self, incident_name: str) -> dict[str, Any]:
        """Analyze communication effectiveness."""
        records = [r for r in self._records if r.incident_name == incident_name]
        if not records:
            return {
                "incident_name": incident_name,
                "status": "no_data",
            }
        delivered = sum(1 for r in records if r.delivery_success)
        delivery_rate = round(delivered / len(records) * 100, 2)
        channel_dist: dict[str, int] = {}
        for r in records:
            channel_dist[r.channel.value] = channel_dist.get(r.channel.value, 0) + 1
        return {
            "incident_name": incident_name,
            "comm_count": len(records),
            "delivered_count": delivered,
            "delivery_rate": delivery_rate,
            "channel_distribution": channel_dist,
            "meets_threshold": (delivery_rate >= self._min_delivery_rate_pct),
        }

    def identify_failed_deliveries(
        self,
    ) -> list[dict[str, Any]]:
        """Find incidents with failed deliveries."""
        fail_counts: dict[str, int] = {}
        for r in self._records:
            if not r.delivery_success:
                fail_counts[r.incident_name] = fail_counts.get(r.incident_name, 0) + 1
        results: list[dict[str, Any]] = []
        for inc, count in fail_counts.items():
            if count > 1:
                results.append(
                    {
                        "incident_name": inc,
                        "failed_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["failed_count"],
            reverse=True,
        )
        return results

    def rank_by_comm_volume(
        self,
    ) -> list[dict[str, Any]]:
        """Rank incidents by communication volume desc."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.incident_name] = freq.get(r.incident_name, 0) + 1
        results: list[dict[str, Any]] = []
        for inc, count in freq.items():
            results.append(
                {
                    "incident_name": inc,
                    "comm_count": count,
                }
            )
        results.sort(
            key=lambda x: x["comm_count"],
            reverse=True,
        )
        return results

    def detect_comm_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Detect incidents with comm gaps (>3 failed)."""
        non_delivered: dict[str, int] = {}
        for r in self._records:
            if not r.delivery_success:
                non_delivered[r.incident_name] = non_delivered.get(r.incident_name, 0) + 1
        results: list[dict[str, Any]] = []
        for inc, count in non_delivered.items():
            if count > 3:
                results.append(
                    {
                        "incident_name": inc,
                        "non_delivered_count": count,
                        "gap_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_delivered_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> CommAutomatorReport:
        by_channel: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in self._records:
            by_channel[r.channel.value] = by_channel.get(r.channel.value, 0) + 1
            by_type[r.comm_type.value] = by_type.get(r.comm_type.value, 0) + 1
        delivered = sum(1 for r in self._records if r.delivery_success)
        delivery_rate = (
            round(
                delivered / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        failed_deliveries = sum(1 for d in self.identify_failed_deliveries())
        recs: list[str] = []
        if delivery_rate < self._min_delivery_rate_pct:
            recs.append(
                f"Delivery rate {delivery_rate}% is below {self._min_delivery_rate_pct}% threshold"
            )
        if failed_deliveries > 0:
            recs.append(f"{failed_deliveries} incident(s) with failed deliveries")
        gaps = len(self.detect_comm_gaps())
        if gaps > 0:
            recs.append(f"{gaps} incident(s) with communication gaps")
        if not recs:
            recs.append("Communication delivery is healthy")
        return CommAutomatorReport(
            total_comms=len(self._records),
            total_templates=len(self._templates),
            delivery_rate_pct=delivery_rate,
            by_channel=by_channel,
            by_type=by_type,
            failed_delivery_count=failed_deliveries,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._templates.clear()
        logger.info("comm_automator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        channel_dist: dict[str, int] = {}
        for r in self._records:
            key = r.channel.value
            channel_dist[key] = channel_dist.get(key, 0) + 1
        return {
            "total_comms": len(self._records),
            "total_templates": len(self._templates),
            "min_delivery_rate_pct": (self._min_delivery_rate_pct),
            "channel_distribution": channel_dist,
            "unique_incidents": len({r.incident_name for r in self._records}),
        }
