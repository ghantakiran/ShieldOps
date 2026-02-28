"""Twilio Voice Alert System — voice calls for critical alerts with IVR acknowledgment."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CallPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CallStatus(StrEnum):
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    ESCALATED = "escalated"


class IVRAction(StrEnum):
    ACKNOWLEDGE = "acknowledge"
    ESCALATE = "escalate"
    SNOOZE = "snooze"
    REJECT = "reject"
    TRANSFER = "transfer"


# --- Models ---


class VoiceCallRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recipient_number: str = ""
    call_priority: CallPriority = CallPriority.HIGH
    call_status: CallStatus = CallStatus.COMPLETED
    ivr_action: IVRAction = IVRAction.ACKNOWLEDGE
    duration_seconds: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class IVRResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    response_label: str = ""
    ivr_action: IVRAction = IVRAction.ACKNOWLEDGE
    call_status: CallStatus = CallStatus.COMPLETED
    confidence_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class TwilioVoiceReport(BaseModel):
    total_calls: int = 0
    total_responses: int = 0
    answer_rate_pct: float = 0.0
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    escalation_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TwilioVoiceAlertSystem:
    """Voice calls for critical alerts with IVR acknowledgment."""

    def __init__(
        self,
        max_records: int = 200000,
        max_ring_seconds: int = 30,
    ) -> None:
        self._max_records = max_records
        self._max_ring_seconds = max_ring_seconds
        self._records: list[VoiceCallRecord] = []
        self._responses: list[IVRResponse] = []
        logger.info(
            "twilio_voice.initialized",
            max_records=max_records,
            max_ring_seconds=max_ring_seconds,
        )

    # -- record / get / list ---------------------------------------------

    def record_call(
        self,
        recipient_number: str,
        call_priority: CallPriority = CallPriority.HIGH,
        call_status: CallStatus = CallStatus.COMPLETED,
        ivr_action: IVRAction = IVRAction.ACKNOWLEDGE,
        duration_seconds: float = 0.0,
        details: str = "",
    ) -> VoiceCallRecord:
        record = VoiceCallRecord(
            recipient_number=recipient_number,
            call_priority=call_priority,
            call_status=call_status,
            ivr_action=ivr_action,
            duration_seconds=duration_seconds,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "twilio_voice.call_recorded",
            record_id=record.id,
            recipient_number=recipient_number,
            call_priority=call_priority.value,
            call_status=call_status.value,
        )
        return record

    def get_call(self, record_id: str) -> VoiceCallRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_calls(
        self,
        recipient_number: str | None = None,
        call_priority: CallPriority | None = None,
        limit: int = 50,
    ) -> list[VoiceCallRecord]:
        results = list(self._records)
        if recipient_number is not None:
            results = [r for r in results if r.recipient_number == recipient_number]
        if call_priority is not None:
            results = [r for r in results if r.call_priority == call_priority]
        return results[-limit:]

    def add_ivr_response(
        self,
        response_label: str,
        ivr_action: IVRAction = IVRAction.ACKNOWLEDGE,
        call_status: CallStatus = CallStatus.COMPLETED,
        confidence_score: float = 0.0,
    ) -> IVRResponse:
        response = IVRResponse(
            response_label=response_label,
            ivr_action=ivr_action,
            call_status=call_status,
            confidence_score=confidence_score,
        )
        self._responses.append(response)
        if len(self._responses) > self._max_records:
            self._responses = self._responses[-self._max_records :]
        logger.info(
            "twilio_voice.ivr_response_added",
            response_label=response_label,
            ivr_action=ivr_action.value,
            call_status=call_status.value,
        )
        return response

    # -- domain operations -----------------------------------------------

    def analyze_answer_rates(self, recipient_number: str) -> dict[str, Any]:
        """Analyze answer rates for a specific recipient."""
        records = [r for r in self._records if r.recipient_number == recipient_number]
        if not records:
            return {"recipient_number": recipient_number, "status": "no_data"}
        completed = sum(1 for r in records if r.call_status == CallStatus.COMPLETED)
        answer_rate = round(completed / len(records) * 100, 2)
        avg_duration = round(sum(r.duration_seconds for r in records) / len(records), 2)
        return {
            "recipient_number": recipient_number,
            "total_calls": len(records),
            "completed_count": completed,
            "answer_rate_pct": answer_rate,
            "avg_duration_seconds": avg_duration,
            "meets_threshold": answer_rate >= (100.0 - self._max_ring_seconds),
        }

    def identify_unanswered_calls(self) -> list[dict[str, Any]]:
        """Find recipients with repeated unanswered calls."""
        failure_counts: dict[str, int] = {}
        for r in self._records:
            if r.call_status in (
                CallStatus.NO_ANSWER,
                CallStatus.BUSY,
                CallStatus.FAILED,
            ):
                failure_counts[r.recipient_number] = failure_counts.get(r.recipient_number, 0) + 1
        results: list[dict[str, Any]] = []
        for recipient, count in failure_counts.items():
            if count > 1:
                results.append(
                    {
                        "recipient_number": recipient,
                        "unanswered_count": count,
                    }
                )
        results.sort(key=lambda x: x["unanswered_count"], reverse=True)
        return results

    def rank_by_call_volume(self) -> list[dict[str, Any]]:
        """Rank recipients by call volume descending."""
        freq: dict[str, int] = {}
        for r in self._records:
            freq[r.recipient_number] = freq.get(r.recipient_number, 0) + 1
        results: list[dict[str, Any]] = []
        for recipient, count in freq.items():
            results.append(
                {
                    "recipient_number": recipient,
                    "call_count": count,
                }
            )
        results.sort(key=lambda x: x["call_count"], reverse=True)
        return results

    def detect_escalation_patterns(self) -> list[dict[str, Any]]:
        """Detect recipients with escalation patterns (>3 non-completed)."""
        non_completed: dict[str, int] = {}
        for r in self._records:
            if r.call_status != CallStatus.COMPLETED:
                non_completed[r.recipient_number] = non_completed.get(r.recipient_number, 0) + 1
        results: list[dict[str, Any]] = []
        for recipient, count in non_completed.items():
            if count > 3:
                results.append(
                    {
                        "recipient_number": recipient,
                        "non_completed_count": count,
                        "escalation_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_completed_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> TwilioVoiceReport:
        by_priority: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_priority[r.call_priority.value] = by_priority.get(r.call_priority.value, 0) + 1
            by_status[r.call_status.value] = by_status.get(r.call_status.value, 0) + 1
        completed_count = sum(1 for r in self._records if r.call_status == CallStatus.COMPLETED)
        answer_rate = round(completed_count / len(self._records) * 100, 2) if self._records else 0.0
        unanswered = sum(1 for d in self.identify_unanswered_calls())
        recs: list[str] = []
        if answer_rate < 80.0:
            recs.append(f"Answer rate {answer_rate}% is below 80.0% threshold")
        if unanswered > 0:
            recs.append(f"{unanswered} recipient(s) with repeated unanswered calls")
        escalations = len(self.detect_escalation_patterns())
        if escalations > 0:
            recs.append(f"{escalations} recipient(s) detected with escalation patterns")
        if not recs:
            recs.append("Voice alert performance meets targets")
        return TwilioVoiceReport(
            total_calls=len(self._records),
            total_responses=len(self._responses),
            answer_rate_pct=answer_rate,
            by_priority=by_priority,
            by_status=by_status,
            escalation_count=escalations,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._responses.clear()
        logger.info("twilio_voice.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        priority_dist: dict[str, int] = {}
        for r in self._records:
            key = r.call_priority.value
            priority_dist[key] = priority_dist.get(key, 0) + 1
        return {
            "total_calls": len(self._records),
            "total_responses": len(self._responses),
            "max_ring_seconds": self._max_ring_seconds,
            "priority_distribution": priority_dist,
            "unique_recipients": len({r.recipient_number for r in self._records}),
        }
