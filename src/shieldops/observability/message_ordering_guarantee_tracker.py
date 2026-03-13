"""Message Ordering Guarantee Tracker —
detect ordering violations, compute consistency
score, rank consumers by ordering risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class OrderingGuarantee(StrEnum):
    STRICT = "strict"
    PARTITION = "partition"
    CAUSAL = "causal"
    NONE = "none"


class ViolationType(StrEnum):
    REORDER = "reorder"
    DUPLICATE = "duplicate"
    GAP = "gap"
    TIMESTAMP_SKEW = "timestamp_skew"


class ConsistencyLevel(StrEnum):
    PERFECT = "perfect"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# --- Models ---


class OrderingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    consumer_id: str = ""
    ordering_guarantee: OrderingGuarantee = OrderingGuarantee.PARTITION
    violation_type: ViolationType = ViolationType.REORDER
    consistency_level: ConsistencyLevel = ConsistencyLevel.HIGH
    violation_count: int = 0
    message_count: int = 0
    topic: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OrderingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    consumer_id: str = ""
    ordering_guarantee: OrderingGuarantee = OrderingGuarantee.PARTITION
    consistency_score: float = 0.0
    violation_rate: float = 0.0
    ordering_risk: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OrderingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_consistency_score: float = 0.0
    by_guarantee: dict[str, int] = Field(default_factory=dict)
    by_violation: dict[str, int] = Field(default_factory=dict)
    by_consistency: dict[str, int] = Field(default_factory=dict)
    risky_consumers: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MessageOrderingGuaranteeTracker:
    """Detect ordering violations, compute consistency
    score, rank consumers by ordering risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[OrderingRecord] = []
        self._analyses: dict[str, OrderingAnalysis] = {}
        logger.info(
            "message_ordering_tracker.init",
            max_records=max_records,
        )

    def add_record(
        self,
        consumer_id: str = "",
        ordering_guarantee: OrderingGuarantee = (OrderingGuarantee.PARTITION),
        violation_type: ViolationType = (ViolationType.REORDER),
        consistency_level: ConsistencyLevel = (ConsistencyLevel.HIGH),
        violation_count: int = 0,
        message_count: int = 0,
        topic: str = "",
        description: str = "",
    ) -> OrderingRecord:
        record = OrderingRecord(
            consumer_id=consumer_id,
            ordering_guarantee=ordering_guarantee,
            violation_type=violation_type,
            consistency_level=consistency_level,
            violation_count=violation_count,
            message_count=message_count,
            topic=topic,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "ordering_tracker.record_added",
            record_id=record.id,
            consumer_id=consumer_id,
        )
        return record

    def process(self, key: str) -> OrderingAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        viol_rate = round(
            rec.violation_count / max(rec.message_count, 1) * 100,
            2,
        )
        consistency = round(100.0 - viol_rate, 2)
        risk = round(viol_rate * 0.5, 2)
        analysis = OrderingAnalysis(
            consumer_id=rec.consumer_id,
            ordering_guarantee=rec.ordering_guarantee,
            consistency_score=consistency,
            violation_rate=viol_rate,
            ordering_risk=risk,
            description=(f"Consumer {rec.consumer_id} consistency {consistency}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> OrderingReport:
        by_g: dict[str, int] = {}
        by_v: dict[str, int] = {}
        by_c: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.ordering_guarantee.value
            by_g[k] = by_g.get(k, 0) + 1
            k2 = r.violation_type.value
            by_v[k2] = by_v.get(k2, 0) + 1
            k3 = r.consistency_level.value
            by_c[k3] = by_c.get(k3, 0) + 1
            rate = r.violation_count / max(r.message_count, 1) * 100
            scores.append(100.0 - rate)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        risky = list(
            {
                r.consumer_id
                for r in self._records
                if r.consistency_level
                in (
                    ConsistencyLevel.LOW,
                    ConsistencyLevel.MODERATE,
                )
            }
        )[:10]
        recs: list[str] = []
        if risky:
            recs.append(f"{len(risky)} risky consumers detected")
        if not recs:
            recs.append("Ordering guarantees stable")
        return OrderingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_consistency_score=avg,
            by_guarantee=by_g,
            by_violation=by_v,
            by_consistency=by_c,
            risky_consumers=risky,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        g_dist: dict[str, int] = {}
        for r in self._records:
            k = r.ordering_guarantee.value
            g_dist[k] = g_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "guarantee_distribution": g_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("message_ordering_tracker.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def detect_ordering_violations(
        self,
    ) -> list[dict[str, Any]]:
        """Detect consumers with ordering violations."""
        consumer_viols: dict[str, int] = {}
        consumer_msgs: dict[str, int] = {}
        for r in self._records:
            consumer_viols[r.consumer_id] = consumer_viols.get(r.consumer_id, 0) + r.violation_count
            consumer_msgs[r.consumer_id] = consumer_msgs.get(r.consumer_id, 0) + r.message_count
        results: list[dict[str, Any]] = []
        for cid, viols in consumer_viols.items():
            if viols > 0:
                rate = round(
                    viols / max(consumer_msgs[cid], 1) * 100,
                    2,
                )
                results.append(
                    {
                        "consumer_id": cid,
                        "violations": viols,
                        "messages": (consumer_msgs[cid]),
                        "violation_rate": rate,
                    }
                )
        results.sort(
            key=lambda x: x["violations"],
            reverse=True,
        )
        return results

    def compute_ordering_consistency_score(
        self,
    ) -> list[dict[str, Any]]:
        """Compute consistency score per consumer."""
        consumer_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            d = consumer_data.setdefault(
                r.consumer_id,
                {"viols": 0, "msgs": 0},
            )
            d["viols"] += r.violation_count
            d["msgs"] += r.message_count
        results: list[dict[str, Any]] = []
        for cid, d in consumer_data.items():
            rate = d["viols"] / max(d["msgs"], 1) * 100
            score = round(100.0 - rate, 2)
            results.append(
                {
                    "consumer_id": cid,
                    "consistency_score": score,
                    "total_violations": d["viols"],
                    "total_messages": d["msgs"],
                }
            )
        results.sort(
            key=lambda x: x["consistency_score"],
            reverse=True,
        )
        return results

    def rank_consumers_by_ordering_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank consumers by ordering risk."""
        consumer_risk: dict[str, float] = {}
        for r in self._records:
            risk = r.violation_count * 2.0 + (r.violation_count / max(r.message_count, 1)) * 50
            consumer_risk[r.consumer_id] = consumer_risk.get(r.consumer_id, 0.0) + risk
        results: list[dict[str, Any]] = []
        for cid, risk in consumer_risk.items():
            results.append(
                {
                    "consumer_id": cid,
                    "risk_score": round(risk, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["risk_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
