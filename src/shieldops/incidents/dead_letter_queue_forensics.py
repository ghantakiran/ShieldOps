"""Dead Letter Queue Forensics —
classify failure patterns, compute reprocessing
success rate, rank DLQs by urgency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FailureReason(StrEnum):
    DESERIALIZATION = "deserialization"
    VALIDATION = "validation"
    TIMEOUT = "timeout"
    DEPENDENCY = "dependency"


class ReprocessingOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class UrgencyLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class DlqRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dlq_name: str = ""
    failure_reason: FailureReason = FailureReason.VALIDATION
    reprocessing_outcome: ReprocessingOutcome = ReprocessingOutcome.FAILED
    urgency_level: UrgencyLevel = UrgencyLevel.MEDIUM
    message_count: int = 0
    age_hours: float = 0.0
    source_topic: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DlqAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dlq_name: str = ""
    failure_reason: FailureReason = FailureReason.VALIDATION
    reprocessing_rate: float = 0.0
    urgency_score: float = 0.0
    pattern_type: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DlqReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_message_count: float = 0.0
    by_failure_reason: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_urgency: dict[str, int] = Field(default_factory=dict)
    critical_dlqs: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeadLetterQueueForensics:
    """Classify failure patterns, compute reprocessing
    success rate, rank DLQs by urgency."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[DlqRecord] = []
        self._analyses: dict[str, DlqAnalysis] = {}
        logger.info(
            "dead_letter_queue_forensics.init",
            max_records=max_records,
        )

    def add_record(
        self,
        dlq_name: str = "",
        failure_reason: FailureReason = (FailureReason.VALIDATION),
        reprocessing_outcome: ReprocessingOutcome = (ReprocessingOutcome.FAILED),
        urgency_level: UrgencyLevel = (UrgencyLevel.MEDIUM),
        message_count: int = 0,
        age_hours: float = 0.0,
        source_topic: str = "",
        description: str = "",
    ) -> DlqRecord:
        record = DlqRecord(
            dlq_name=dlq_name,
            failure_reason=failure_reason,
            reprocessing_outcome=reprocessing_outcome,
            urgency_level=urgency_level,
            message_count=message_count,
            age_hours=age_hours,
            source_topic=source_topic,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dlq_forensics.record_added",
            record_id=record.id,
            dlq_name=dlq_name,
        )
        return record

    def process(self, key: str) -> DlqAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.dlq_name == rec.dlq_name]
        success_ct = sum(
            1 for r in related if r.reprocessing_outcome == ReprocessingOutcome.SUCCESS
        )
        rate = round(success_ct / len(related) * 100, 2) if related else 0.0
        urgency_score = round(
            rec.message_count * 0.1 + rec.age_hours * 0.5,
            2,
        )
        analysis = DlqAnalysis(
            dlq_name=rec.dlq_name,
            failure_reason=rec.failure_reason,
            reprocessing_rate=rate,
            urgency_score=urgency_score,
            pattern_type=rec.failure_reason.value,
            description=(f"DLQ {rec.dlq_name} rate {rate}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> DlqReport:
        by_fr: dict[str, int] = {}
        by_out: dict[str, int] = {}
        by_urg: dict[str, int] = {}
        counts: list[int] = []
        for r in self._records:
            k = r.failure_reason.value
            by_fr[k] = by_fr.get(k, 0) + 1
            k2 = r.reprocessing_outcome.value
            by_out[k2] = by_out.get(k2, 0) + 1
            k3 = r.urgency_level.value
            by_urg[k3] = by_urg.get(k3, 0) + 1
            counts.append(r.message_count)
        avg = round(sum(counts) / len(counts), 2) if counts else 0.0
        crit = list(
            {
                r.dlq_name
                for r in self._records
                if r.urgency_level
                in (
                    UrgencyLevel.CRITICAL,
                    UrgencyLevel.HIGH,
                )
            }
        )[:10]
        recs: list[str] = []
        if crit:
            recs.append(f"{len(crit)} critical DLQs detected")
        if not recs:
            recs.append("No urgent DLQ issues")
        return DlqReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_message_count=avg,
            by_failure_reason=by_fr,
            by_outcome=by_out,
            by_urgency=by_urg,
            critical_dlqs=crit,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        fr_dist: dict[str, int] = {}
        for r in self._records:
            k = r.failure_reason.value
            fr_dist[k] = fr_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "failure_reason_distribution": fr_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("dead_letter_queue_forensics.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def classify_failure_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Classify DLQ failure patterns."""
        pattern_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            pattern_data.setdefault(r.dlq_name, {})
            reason = r.failure_reason.value
            pattern_data[r.dlq_name][reason] = pattern_data[r.dlq_name].get(reason, 0) + 1
        results: list[dict[str, Any]] = []
        for dlq, patterns in pattern_data.items():
            dominant = max(
                patterns,
                key=lambda x: patterns[x],
            )
            results.append(
                {
                    "dlq_name": dlq,
                    "dominant_pattern": dominant,
                    "pattern_counts": patterns,
                    "total_failures": sum(patterns.values()),
                }
            )
        results.sort(
            key=lambda x: x["total_failures"],
            reverse=True,
        )
        return results

    def compute_reprocessing_success_rate(
        self,
    ) -> list[dict[str, Any]]:
        """Compute reprocessing success rate per DLQ."""
        dlq_data: dict[str, list[str]] = {}
        for r in self._records:
            dlq_data.setdefault(r.dlq_name, []).append(r.reprocessing_outcome.value)
        results: list[dict[str, Any]] = []
        for dlq, outcomes in dlq_data.items():
            success = outcomes.count("success")
            rate = round(success / len(outcomes) * 100, 2)
            results.append(
                {
                    "dlq_name": dlq,
                    "success_rate": rate,
                    "total_attempts": len(outcomes),
                    "successes": success,
                }
            )
        results.sort(
            key=lambda x: x["success_rate"],
            reverse=True,
        )
        return results

    def rank_dlqs_by_urgency(
        self,
    ) -> list[dict[str, Any]]:
        """Rank DLQs by urgency score."""
        urgency_weights = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
        }
        dlq_scores: dict[str, float] = {}
        dlq_counts: dict[str, int] = {}
        for r in self._records:
            w = urgency_weights.get(r.urgency_level.value, 1)
            score = w * r.message_count
            dlq_scores[r.dlq_name] = dlq_scores.get(r.dlq_name, 0.0) + score
            dlq_counts[r.dlq_name] = dlq_counts.get(r.dlq_name, 0) + 1
        results: list[dict[str, Any]] = []
        for dlq, total_score in dlq_scores.items():
            results.append(
                {
                    "dlq_name": dlq,
                    "urgency_score": round(total_score, 2),
                    "record_count": dlq_counts[dlq],
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["urgency_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
