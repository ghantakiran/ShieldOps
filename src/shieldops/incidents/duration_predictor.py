"""Incident Duration Predictor — predict how long an active incident will last."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DurationBucket(StrEnum):
    MINUTES_0_15 = "minutes_0_15"
    MINUTES_15_60 = "minutes_15_60"
    HOURS_1_4 = "hours_1_4"
    HOURS_4_12 = "hours_4_12"
    HOURS_12_PLUS = "hours_12_plus"


class IncidentComplexity(StrEnum):
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CATASTROPHIC = "catastrophic"


class ResolutionPath(StrEnum):
    AUTOMATED_FIX = "automated_fix"
    KNOWN_RUNBOOK = "known_runbook"
    INVESTIGATION_NEEDED = "investigation_needed"
    ESCALATION_REQUIRED = "escalation_required"
    VENDOR_DEPENDENCY = "vendor_dependency"


# --- Models ---


class DurationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    service_name: str = ""
    severity: str = ""
    complexity: IncidentComplexity = IncidentComplexity.MODERATE
    resolution_path: ResolutionPath = ResolutionPath.INVESTIGATION_NEEDED
    predicted_bucket: DurationBucket = DurationBucket.HOURS_1_4
    predicted_minutes: float = 0.0
    actual_minutes: float = 0.0
    responder_count: int = 1
    is_business_hours: bool = True
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class DurationBenchmark(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    avg_duration_minutes: float = 0.0
    p50_minutes: float = 0.0
    p90_minutes: float = 0.0
    p99_minutes: float = 0.0
    sample_count: int = 0
    by_complexity: dict[str, float] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class DurationReport(BaseModel):
    total_predictions: int = 0
    accuracy_pct: float = 0.0
    avg_predicted_minutes: float = 0.0
    avg_actual_minutes: float = 0.0
    by_bucket: dict[str, int] = Field(default_factory=dict)
    by_complexity: dict[str, int] = Field(default_factory=dict)
    slow_resolving_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Bucket ranges ---

_BUCKET_RANGES: dict[DurationBucket, tuple[float, float]] = {
    DurationBucket.MINUTES_0_15: (0.0, 15.0),
    DurationBucket.MINUTES_15_60: (15.0, 60.0),
    DurationBucket.HOURS_1_4: (60.0, 240.0),
    DurationBucket.HOURS_4_12: (240.0, 720.0),
    DurationBucket.HOURS_12_PLUS: (720.0, float("inf")),
}

_BASE_MINUTES: dict[IncidentComplexity, float] = {
    IncidentComplexity.TRIVIAL: 10.0,
    IncidentComplexity.SIMPLE: 30.0,
    IncidentComplexity.MODERATE: 90.0,
    IncidentComplexity.COMPLEX: 240.0,
    IncidentComplexity.CATASTROPHIC: 720.0,
}

_PATH_MULTIPLIER: dict[ResolutionPath, float] = {
    ResolutionPath.AUTOMATED_FIX: 0.3,
    ResolutionPath.KNOWN_RUNBOOK: 0.7,
    ResolutionPath.INVESTIGATION_NEEDED: 1.0,
    ResolutionPath.ESCALATION_REQUIRED: 1.5,
    ResolutionPath.VENDOR_DEPENDENCY: 2.5,
}


# --- Engine ---


class IncidentDurationPredictor:
    """Predict how long an active incident will last."""

    def __init__(
        self,
        max_records: int = 200000,
        accuracy_target_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._accuracy_target_pct = accuracy_target_pct
        self._records: list[DurationRecord] = []
        logger.info(
            "duration_predictor.initialized",
            max_records=max_records,
            accuracy_target_pct=accuracy_target_pct,
        )

    # -- CRUD --

    def record_prediction(
        self,
        incident_id: str,
        service_name: str,
        severity: str,
        complexity: IncidentComplexity,
        resolution_path: ResolutionPath,
        responder_count: int = 1,
        is_business_hours: bool = True,
    ) -> DurationRecord:
        bucket, minutes = self._predict(
            complexity, resolution_path, responder_count, is_business_hours
        )
        record = DurationRecord(
            incident_id=incident_id,
            service_name=service_name,
            severity=severity,
            complexity=complexity,
            resolution_path=resolution_path,
            predicted_bucket=bucket,
            predicted_minutes=minutes,
            responder_count=responder_count,
            is_business_hours=is_business_hours,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "duration_predictor.recorded",
            record_id=record.id,
            incident_id=incident_id,
            predicted_bucket=bucket.value,
            predicted_minutes=minutes,
        )
        return record

    def get_prediction(self, record_id: str) -> DurationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_predictions(
        self,
        service_name: str | None = None,
        complexity: IncidentComplexity | None = None,
        limit: int = 50,
    ) -> list[DurationRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if complexity is not None:
            results = [r for r in results if r.complexity == complexity]
        return results[-limit:]

    # -- Domain operations --

    def predict_duration(
        self,
        complexity: IncidentComplexity,
        resolution_path: ResolutionPath,
        responder_count: int = 1,
        is_business_hours: bool = True,
    ) -> dict[str, Any]:
        bucket, minutes = self._predict(
            complexity, resolution_path, responder_count, is_business_hours
        )
        return {
            "predicted_bucket": bucket.value,
            "predicted_minutes": minutes,
            "complexity": complexity.value,
            "resolution_path": resolution_path.value,
            "responder_count": responder_count,
            "is_business_hours": is_business_hours,
        }

    def record_actual_duration(
        self,
        record_id: str,
        actual_minutes: float,
    ) -> dict[str, Any]:
        record = self.get_prediction(record_id)
        if record is None:
            return {"error": "record_not_found"}
        record.actual_minutes = actual_minutes
        low, high = _BUCKET_RANGES[record.predicted_bucket]
        accurate = low <= actual_minutes < high
        logger.info(
            "duration_predictor.actual_recorded",
            record_id=record_id,
            predicted_minutes=record.predicted_minutes,
            actual_minutes=actual_minutes,
            accurate=accurate,
        )
        return {
            "record_id": record_id,
            "predicted_minutes": record.predicted_minutes,
            "actual_minutes": actual_minutes,
            "predicted_bucket": record.predicted_bucket.value,
            "accurate": accurate,
        }

    def calculate_accuracy(self) -> dict[str, Any]:
        completed = [r for r in self._records if r.actual_minutes > 0]
        if not completed:
            return {"accuracy_pct": 0.0, "total": 0}
        correct = 0
        for r in completed:
            low, high = _BUCKET_RANGES[r.predicted_bucket]
            if low <= r.actual_minutes < high:
                correct += 1
        accuracy = round(correct / len(completed) * 100.0, 2)
        return {
            "accuracy_pct": accuracy,
            "total": len(completed),
            "correct": correct,
            "meets_target": accuracy >= self._accuracy_target_pct,
        }

    def compute_benchmarks(
        self,
        service_name: str | None = None,
    ) -> DurationBenchmark:
        records = [r for r in self._records if r.actual_minutes > 0]
        if service_name is not None:
            records = [r for r in records if r.service_name == service_name]
        if not records:
            return DurationBenchmark(service_name=service_name or "")
        durations = sorted(r.actual_minutes for r in records)
        n = len(durations)
        avg_dur = round(sum(durations) / n, 2)
        p50 = durations[int(n * 0.50)] if n > 0 else 0.0
        p90 = durations[min(int(n * 0.90), n - 1)] if n > 0 else 0.0
        p99 = durations[min(int(n * 0.99), n - 1)] if n > 0 else 0.0
        by_complexity: dict[str, float] = {}
        for cx in IncidentComplexity:
            cx_records = [r for r in records if r.complexity == cx]
            if cx_records:
                cx_avg = round(sum(r.actual_minutes for r in cx_records) / len(cx_records), 2)
                by_complexity[cx.value] = cx_avg
        return DurationBenchmark(
            service_name=service_name or "",
            avg_duration_minutes=avg_dur,
            p50_minutes=p50,
            p90_minutes=p90,
            p99_minutes=p99,
            sample_count=n,
            by_complexity=by_complexity,
        )

    def identify_slow_resolving_services(
        self,
        threshold_minutes: float = 60.0,
    ) -> list[dict[str, Any]]:
        by_service: dict[str, list[DurationRecord]] = {}
        for r in self._records:
            if r.actual_minutes > 0:
                by_service.setdefault(r.service_name, []).append(r)
        slow: list[dict[str, Any]] = []
        for svc, records in sorted(by_service.items()):
            avg = sum(r.actual_minutes for r in records) / len(records)
            if avg > threshold_minutes:
                slow.append(
                    {
                        "service_name": svc,
                        "avg_duration_minutes": round(avg, 2),
                        "incident_count": len(records),
                    }
                )
        slow.sort(key=lambda x: x["avg_duration_minutes"], reverse=True)
        return slow

    # -- Report --

    def generate_duration_report(self) -> DurationReport:
        by_bucket: dict[str, int] = {}
        by_complexity: dict[str, int] = {}
        for r in self._records:
            by_bucket[r.predicted_bucket.value] = by_bucket.get(r.predicted_bucket.value, 0) + 1
            by_complexity[r.complexity.value] = by_complexity.get(r.complexity.value, 0) + 1
        total = len(self._records)
        avg_predicted = (
            round(sum(r.predicted_minutes for r in self._records) / total, 2) if total else 0.0
        )
        completed = [r for r in self._records if r.actual_minutes > 0]
        avg_actual = (
            round(sum(r.actual_minutes for r in completed) / len(completed), 2)
            if completed
            else 0.0
        )
        accuracy_info = self.calculate_accuracy()
        slow_services = self.identify_slow_resolving_services()
        slow_names = [s["service_name"] for s in slow_services[:10]]
        recs: list[str] = []
        if accuracy_info["accuracy_pct"] < self._accuracy_target_pct:
            recs.append("Prediction accuracy below target — review estimation model")
        if slow_names:
            recs.append(f"{len(slow_names)} service(s) consistently slow to resolve")
        if not recs:
            recs.append("Duration predictions within acceptable accuracy")
        return DurationReport(
            total_predictions=total,
            accuracy_pct=accuracy_info["accuracy_pct"],
            avg_predicted_minutes=avg_predicted,
            avg_actual_minutes=avg_actual,
            by_bucket=by_bucket,
            by_complexity=by_complexity,
            slow_resolving_services=slow_names,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        accuracy_info = self.calculate_accuracy()
        return {
            "total_records": len(self._records),
            "accuracy_pct": accuracy_info["accuracy_pct"],
            "unique_services": len({r.service_name for r in self._records}),
            "unique_incidents": len({r.incident_id for r in self._records}),
        }

    # -- Internal helpers --

    def _predict(
        self,
        complexity: IncidentComplexity,
        resolution_path: ResolutionPath,
        responder_count: int,
        is_business_hours: bool,
    ) -> tuple[DurationBucket, float]:
        base = _BASE_MINUTES[complexity]
        multiplier = _PATH_MULTIPLIER[resolution_path]
        minutes = base * multiplier
        minutes = minutes / max(responder_count * 0.7, 1.0)
        if not is_business_hours:
            minutes *= 1.5
        minutes = round(minutes, 2)
        if minutes < 15.0:
            bucket = DurationBucket.MINUTES_0_15
        elif minutes < 60.0:
            bucket = DurationBucket.MINUTES_15_60
        elif minutes < 240.0:
            bucket = DurationBucket.HOURS_1_4
        elif minutes < 720.0:
            bucket = DurationBucket.HOURS_4_12
        else:
            bucket = DurationBucket.HOURS_12_PLUS
        return bucket, minutes
