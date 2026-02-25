"""Escalation Effectiveness Tracker — measure whether escalations worked."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EscalationResult(StrEnum):
    RESOLVED = "resolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    RE_ESCALATED = "re_escalated"
    TIMED_OUT = "timed_out"
    FALSE_ESCALATION = "false_escalation"


class ResponderTier(StrEnum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    MANAGEMENT = "management"
    VENDOR = "vendor"


class AcknowledgmentSpeed(StrEnum):
    IMMEDIATE = "immediate"
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"
    MISSED = "missed"


# --- Models ---


class EscalationEffectivenessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    responder_id: str = ""
    responder_tier: ResponderTier = ResponderTier.TIER_1
    result: EscalationResult = EscalationResult.RESOLVED
    ack_speed: AcknowledgmentSpeed = AcknowledgmentSpeed.NORMAL
    ack_time_minutes: float = 0.0
    resolution_time_minutes: float = 0.0
    was_correct_target: bool = True
    created_at: float = Field(default_factory=time.time)


class ResponderProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    responder_id: str = ""
    tier: ResponderTier = ResponderTier.TIER_1
    total_escalations: int = 0
    resolved_count: int = 0
    avg_ack_minutes: float = 0.0
    avg_resolution_minutes: float = 0.0
    effectiveness_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class EscalationEffectivenessReport(BaseModel):
    total_escalations: int = 0
    resolved_count: int = 0
    false_escalation_count: int = 0
    false_escalation_rate_pct: float = 0.0
    by_result: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    top_responders: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EscalationEffectivenessTracker:
    """Measure whether escalations worked (MTTR reduction, right person, false rate)."""

    def __init__(
        self,
        max_records: int = 200000,
        false_rate_threshold: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._false_rate_threshold = false_rate_threshold
        self._records: list[EscalationEffectivenessRecord] = []
        self._profiles: dict[str, ResponderProfile] = {}
        logger.info(
            "escalation_effectiveness.initialized",
            max_records=max_records,
            false_rate_threshold=false_rate_threshold,
        )

    # -- internal helpers ------------------------------------------------

    def _ack_to_speed(self, minutes: float) -> AcknowledgmentSpeed:
        if minutes < 2:
            return AcknowledgmentSpeed.IMMEDIATE
        if minutes < 5:
            return AcknowledgmentSpeed.FAST
        if minutes < 15:
            return AcknowledgmentSpeed.NORMAL
        if minutes < 30:
            return AcknowledgmentSpeed.SLOW
        return AcknowledgmentSpeed.MISSED

    # -- record / get / list ---------------------------------------------

    def record_escalation(
        self,
        incident_id: str,
        responder_id: str,
        responder_tier: ResponderTier = ResponderTier.TIER_1,
        result: EscalationResult = EscalationResult.RESOLVED,
        ack_time_minutes: float = 5.0,
        resolution_time_minutes: float = 30.0,
        was_correct_target: bool = True,
    ) -> EscalationEffectivenessRecord:
        ack_speed = self._ack_to_speed(ack_time_minutes)
        record = EscalationEffectivenessRecord(
            incident_id=incident_id,
            responder_id=responder_id,
            responder_tier=responder_tier,
            result=result,
            ack_speed=ack_speed,
            ack_time_minutes=ack_time_minutes,
            resolution_time_minutes=resolution_time_minutes,
            was_correct_target=was_correct_target,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "escalation_effectiveness.escalation_recorded",
            record_id=record.id,
            incident_id=incident_id,
            responder_id=responder_id,
            result=result.value,
        )
        return record

    def get_escalation(self, record_id: str) -> EscalationEffectivenessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_escalations(
        self,
        responder_id: str | None = None,
        result: EscalationResult | None = None,
        limit: int = 50,
    ) -> list[EscalationEffectivenessRecord]:
        results = list(self._records)
        if responder_id is not None:
            results = [r for r in results if r.responder_id == responder_id]
        if result is not None:
            results = [r for r in results if r.result == result]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def build_responder_profile(self, responder_id: str) -> ResponderProfile:
        """Build or update a profile for a responder."""
        records = [r for r in self._records if r.responder_id == responder_id]
        if not records:
            profile = ResponderProfile(responder_id=responder_id)
            self._profiles[responder_id] = profile
            return profile
        total = len(records)
        resolved = sum(1 for r in records if r.result == EscalationResult.RESOLVED)
        avg_ack = round(sum(r.ack_time_minutes for r in records) / total, 2)
        avg_res = round(sum(r.resolution_time_minutes for r in records) / total, 2)
        correct = sum(1 for r in records if r.was_correct_target)
        # Effectiveness = weighted score of resolution rate, ack speed, correct targeting
        eff = round(
            (resolved / total * 0.5 + correct / total * 0.3 + min(1, 15 / max(avg_ack, 1)) * 0.2),
            4,
        )
        profile = ResponderProfile(
            responder_id=responder_id,
            tier=records[-1].responder_tier,
            total_escalations=total,
            resolved_count=resolved,
            avg_ack_minutes=avg_ack,
            avg_resolution_minutes=avg_res,
            effectiveness_score=eff,
        )
        self._profiles[responder_id] = profile
        logger.info(
            "escalation_effectiveness.profile_built",
            responder_id=responder_id,
            effectiveness_score=eff,
        )
        return profile

    def calculate_effectiveness_score(self, responder_id: str) -> dict[str, Any]:
        """Calculate effectiveness score for a responder."""
        profile = self.build_responder_profile(responder_id)
        return {
            "responder_id": responder_id,
            "effectiveness_score": profile.effectiveness_score,
            "total_escalations": profile.total_escalations,
            "resolved_count": profile.resolved_count,
            "avg_ack_minutes": profile.avg_ack_minutes,
            "avg_resolution_minutes": profile.avg_resolution_minutes,
        }

    def identify_false_escalations(self) -> list[dict[str, Any]]:
        """Find escalations that were false/unnecessary."""
        false_esc = [r for r in self._records if r.result == EscalationResult.FALSE_ESCALATION]
        return [
            {
                "record_id": r.id,
                "incident_id": r.incident_id,
                "responder_id": r.responder_id,
                "responder_tier": r.responder_tier.value,
                "ack_time_minutes": r.ack_time_minutes,
            }
            for r in false_esc
        ]

    def rank_responders_by_effectiveness(self) -> list[dict[str, Any]]:
        """Rank all responders by their effectiveness score."""
        responder_ids = {r.responder_id for r in self._records}
        for rid in responder_ids:
            self.build_responder_profile(rid)
        ranked = sorted(self._profiles.values(), key=lambda p: p.effectiveness_score, reverse=True)
        return [
            {
                "responder_id": p.responder_id,
                "tier": p.tier.value,
                "effectiveness_score": p.effectiveness_score,
                "total_escalations": p.total_escalations,
                "resolved_count": p.resolved_count,
            }
            for p in ranked
        ]

    def detect_re_escalation_patterns(self) -> list[dict[str, Any]]:
        """Detect incidents that were re-escalated multiple times."""
        incident_counts: dict[str, int] = {}
        for r in self._records:
            if r.result == EscalationResult.RE_ESCALATED:
                incident_counts[r.incident_id] = incident_counts.get(r.incident_id, 0) + 1
        return [
            {"incident_id": iid, "re_escalation_count": count}
            for iid, count in sorted(incident_counts.items(), key=lambda x: x[1], reverse=True)
            if count > 0
        ]

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> EscalationEffectivenessReport:
        by_result: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        for r in self._records:
            by_result[r.result.value] = by_result.get(r.result.value, 0) + 1
            by_tier[r.responder_tier.value] = by_tier.get(r.responder_tier.value, 0) + 1
        total = len(self._records)
        resolved = by_result.get(EscalationResult.RESOLVED.value, 0)
        false_count = by_result.get(EscalationResult.FALSE_ESCALATION.value, 0)
        false_rate = round(false_count / total * 100, 2) if total > 0 else 0.0
        ranked = self.rank_responders_by_effectiveness()
        top_resp = [r["responder_id"] for r in ranked[:5]]
        recs: list[str] = []
        if false_rate > self._false_rate_threshold:
            recs.append(
                f"False escalation rate {false_rate}% exceeds threshold"
                f" {self._false_rate_threshold}%"
            )
        re_esc = by_result.get(EscalationResult.RE_ESCALATED.value, 0)
        if re_esc > 0:
            recs.append(f"{re_esc} re-escalation(s) detected — review routing rules")
        timed_out = by_result.get(EscalationResult.TIMED_OUT.value, 0)
        if timed_out > 0:
            recs.append(f"{timed_out} escalation(s) timed out")
        if not recs:
            recs.append("Escalation effectiveness within normal parameters")
        return EscalationEffectivenessReport(
            total_escalations=total,
            resolved_count=resolved,
            false_escalation_count=false_count,
            false_escalation_rate_pct=false_rate,
            by_result=by_result,
            by_tier=by_tier,
            top_responders=top_resp,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._profiles.clear()
        logger.info("escalation_effectiveness.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        result_dist: dict[str, int] = {}
        for r in self._records:
            key = r.result.value
            result_dist[key] = result_dist.get(key, 0) + 1
        return {
            "total_escalations": len(self._records),
            "total_profiles": len(self._profiles),
            "false_rate_threshold": self._false_rate_threshold,
            "result_distribution": result_dist,
            "unique_responders": len({r.responder_id for r in self._records}),
        }
