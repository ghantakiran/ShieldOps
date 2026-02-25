"""Incident Recurrence Predictor — predict recurring incidents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RecurrenceRisk(StrEnum):
    NEGLIGIBLE = "negligible"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    ALMOST_CERTAIN = "almost_certain"


class FixCompleteness(StrEnum):
    FULL_FIX = "full_fix"
    PARTIAL_FIX = "partial_fix"
    WORKAROUND = "workaround"
    MONITORING_ONLY = "monitoring_only"
    UNRESOLVED = "unresolved"


class SimilarityBasis(StrEnum):
    ROOT_CAUSE = "root_cause"
    SYMPTOMS = "symptoms"
    AFFECTED_SERVICE = "affected_service"
    TIME_PATTERN = "time_pattern"
    CHANGE_RELATED = "change_related"


# --- Models ---


class RecurrenceRecord(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    incident_id: str = ""
    service_name: str = ""
    root_cause: str = ""
    fix_completeness: FixCompleteness = FixCompleteness.UNRESOLVED
    recurrence_risk: RecurrenceRisk = RecurrenceRisk.NEGLIGIBLE
    similarity_score: float = 0.0
    predicted_recurrence_days: int = 0
    actual_recurred: bool = False
    created_at: float = Field(default_factory=time.time)


class RecurrencePattern(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    pattern_name: str = ""
    occurrence_count: int = 0
    avg_interval_days: float = 0.0
    services: list[str] = Field(default_factory=list)
    last_seen_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class RecurrenceReport(BaseModel):
    total_records: int = 0
    total_patterns: int = 0
    prediction_accuracy_pct: float = 0.0
    by_risk: dict[str, int] = Field(
        default_factory=dict,
    )
    by_fix: dict[str, int] = Field(
        default_factory=dict,
    )
    high_risk_incidents: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Predictor ---


class IncidentRecurrencePredictor:
    """Predict which incidents are likely to recur based
    on root cause patterns, fix completeness, and
    historical similarity."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 0.6,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._items: list[RecurrenceRecord] = []
        self._patterns: list[RecurrencePattern] = []
        logger.info(
            "recurrence_predictor.initialized",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    # -- record / get / list -----------------------------------------

    def record_incident(
        self,
        incident_id: str,
        service_name: str = "",
        root_cause: str = "",
        fix_completeness: FixCompleteness = (FixCompleteness.UNRESOLVED),
        similarity_score: float = 0.0,
        predicted_recurrence_days: int = 0,
        **kw: Any,
    ) -> RecurrenceRecord:
        """Record an incident for recurrence tracking."""
        risk = self._compute_risk(
            fix_completeness,
            similarity_score,
        )
        record = RecurrenceRecord(
            incident_id=incident_id,
            service_name=service_name,
            root_cause=root_cause,
            fix_completeness=fix_completeness,
            recurrence_risk=risk,
            similarity_score=similarity_score,
            predicted_recurrence_days=(predicted_recurrence_days),
            **kw,
        )
        self._items.append(record)
        if len(self._items) > self._max_records:
            self._items = self._items[-self._max_records :]
        logger.info(
            "recurrence_predictor.recorded",
            record_id=record.id,
            incident_id=incident_id,
            risk=risk,
        )
        return record

    def get_record(
        self,
        record_id: str,
    ) -> RecurrenceRecord | None:
        """Get a record by ID."""
        for item in self._items:
            if item.id == record_id:
                return item
        return None

    def list_records(
        self,
        service_name: str | None = None,
        recurrence_risk: RecurrenceRisk | None = None,
        limit: int = 50,
    ) -> list[RecurrenceRecord]:
        """List records with optional filters."""
        results = list(self._items)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if recurrence_risk is not None:
            results = [r for r in results if r.recurrence_risk == recurrence_risk]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def predict_recurrence(
        self,
        record_id: str,
    ) -> dict[str, Any] | None:
        """Predict recurrence for a specific record."""
        rec = self.get_record(record_id)
        if rec is None:
            return None
        fix_weight = self._fix_weight(
            rec.fix_completeness,
        )
        score = round((fix_weight + rec.similarity_score) / 2, 4)
        risk = self._score_to_risk(score)
        rec.recurrence_risk = risk
        days = self._estimate_days(score)
        rec.predicted_recurrence_days = days
        logger.info(
            "recurrence_predictor.predicted",
            record_id=record_id,
            risk=risk,
            days=days,
        )
        return {
            "record_id": record_id,
            "recurrence_risk": risk.value,
            "predicted_days": days,
            "score": score,
        }

    def detect_patterns(
        self,
    ) -> list[RecurrencePattern]:
        """Detect recurrence patterns from records."""
        by_cause: dict[str, list[RecurrenceRecord]] = {}
        for r in self._items:
            if r.root_cause:
                by_cause.setdefault(r.root_cause, []).append(r)
        new_patterns: list[RecurrencePattern] = []
        for cause, records in sorted(by_cause.items()):
            if len(records) < 2:
                continue
            services = sorted({r.service_name for r in records})
            intervals: list[float] = []
            for i in range(1, len(records)):
                diff = records[i].created_at - records[i - 1].created_at
                intervals.append(diff / 86400)
            avg_interval = round(sum(intervals) / len(intervals), 2) if intervals else 0.0
            pattern = RecurrencePattern(
                pattern_name=cause,
                occurrence_count=len(records),
                avg_interval_days=avg_interval,
                services=services,
                last_seen_at=records[-1].created_at,
            )
            new_patterns.append(pattern)
        self._patterns = new_patterns
        logger.info(
            "recurrence_predictor.patterns_detected",
            count=len(new_patterns),
        )
        return new_patterns

    def mark_recurred(
        self,
        record_id: str,
    ) -> RecurrenceRecord | None:
        """Mark a record as having actually recurred."""
        rec = self.get_record(record_id)
        if rec is None:
            return None
        rec.actual_recurred = True
        logger.info(
            "recurrence_predictor.marked_recurred",
            record_id=record_id,
        )
        return rec

    def calculate_prediction_accuracy(self) -> float:
        """Calculate prediction accuracy percentage."""
        predicted_high = [
            r
            for r in self._items
            if r.recurrence_risk
            in (
                RecurrenceRisk.HIGH,
                RecurrenceRisk.ALMOST_CERTAIN,
            )
        ]
        if not predicted_high:
            return 100.0
        correct = sum(1 for r in predicted_high if r.actual_recurred)
        return round(correct / len(predicted_high) * 100, 2)

    def identify_chronic_incidents(
        self,
    ) -> list[dict[str, Any]]:
        """Identify chronically recurring incidents."""
        by_svc: dict[str, list[RecurrenceRecord]] = {}
        for r in self._items:
            by_svc.setdefault(r.service_name, []).append(r)
        chronic: list[dict[str, Any]] = []
        for svc, records in sorted(by_svc.items()):
            recurred = [r for r in records if r.actual_recurred]
            if len(recurred) >= 2:
                chronic.append(
                    {
                        "service_name": svc,
                        "total_incidents": len(records),
                        "recurred_count": len(recurred),
                        "recurrence_rate": round(
                            len(recurred) / len(records) * 100,
                            2,
                        ),
                    }
                )
        chronic.sort(
            key=lambda x: x["recurrence_rate"],
            reverse=True,
        )
        return chronic

    # -- report / stats ----------------------------------------------

    def generate_recurrence_report(
        self,
    ) -> RecurrenceReport:
        """Generate a comprehensive recurrence report."""
        by_risk: dict[str, int] = {}
        for r in self._items:
            key = r.recurrence_risk.value
            by_risk[key] = by_risk.get(key, 0) + 1
        by_fix: dict[str, int] = {}
        for r in self._items:
            key = r.fix_completeness.value
            by_fix[key] = by_fix.get(key, 0) + 1
        high_risk = [
            r.id
            for r in self._items
            if r.recurrence_risk
            in (
                RecurrenceRisk.HIGH,
                RecurrenceRisk.ALMOST_CERTAIN,
            )
        ]
        recs = self._build_recommendations(
            by_risk,
            by_fix,
        )
        return RecurrenceReport(
            total_records=len(self._items),
            total_patterns=len(self._patterns),
            prediction_accuracy_pct=(self.calculate_prediction_accuracy()),
            by_risk=by_risk,
            by_fix=by_fix,
            high_risk_incidents=high_risk,
            recommendations=recs,
        )

    def clear_data(self) -> int:
        """Clear all data. Returns count cleared."""
        count = len(self._items)
        self._items.clear()
        self._patterns.clear()
        logger.info(
            "recurrence_predictor.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        risk_dist: dict[str, int] = {}
        for r in self._items:
            key = r.recurrence_risk.value
            risk_dist[key] = risk_dist.get(key, 0) + 1
        return {
            "total_records": len(self._items),
            "total_patterns": len(self._patterns),
            "risk_threshold": self._risk_threshold,
            "risk_distribution": risk_dist,
        }

    # -- internal helpers --------------------------------------------

    def _compute_risk(
        self,
        fix: FixCompleteness,
        similarity: float,
    ) -> RecurrenceRisk:
        weight = self._fix_weight(fix)
        score = (weight + similarity) / 2
        return self._score_to_risk(score)

    def _fix_weight(
        self,
        fix: FixCompleteness,
    ) -> float:
        weights = {
            FixCompleteness.FULL_FIX: 0.1,
            FixCompleteness.PARTIAL_FIX: 0.4,
            FixCompleteness.WORKAROUND: 0.6,
            FixCompleteness.MONITORING_ONLY: 0.8,
            FixCompleteness.UNRESOLVED: 1.0,
        }
        return weights.get(fix, 0.5)

    def _score_to_risk(
        self,
        score: float,
    ) -> RecurrenceRisk:
        if score >= 0.8:
            return RecurrenceRisk.ALMOST_CERTAIN
        if score >= 0.6:
            return RecurrenceRisk.HIGH
        if score >= 0.4:
            return RecurrenceRisk.MODERATE
        if score >= 0.2:
            return RecurrenceRisk.LOW
        return RecurrenceRisk.NEGLIGIBLE

    def _estimate_days(self, score: float) -> int:
        if score >= 0.8:
            return 7
        if score >= 0.6:
            return 14
        if score >= 0.4:
            return 30
        if score >= 0.2:
            return 60
        return 90

    def _build_recommendations(
        self,
        by_risk: dict[str, int],
        by_fix: dict[str, int],
    ) -> list[str]:
        recs: list[str] = []
        high = by_risk.get(RecurrenceRisk.ALMOST_CERTAIN.value, 0)
        if high > 0:
            recs.append(f"{high} incident(s) almost certain to recur — prioritize permanent fixes")
        unresolved = by_fix.get(FixCompleteness.UNRESOLVED.value, 0)
        if unresolved > 0:
            recs.append(f"{unresolved} unresolved incident(s) — assign engineering resources")
        if not recs:
            recs.append("Incident recurrence risk is well managed")
        return recs
