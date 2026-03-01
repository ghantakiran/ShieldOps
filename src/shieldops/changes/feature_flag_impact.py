"""Feature Flag Impact Analyzer — track feature flag impacts, measurements, and regressions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FlagImpactType(StrEnum):
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    ERROR_RATE = "error_rate"
    LATENCY = "latency"
    USER_EXPERIENCE = "user_experience"


class FlagStatus(StrEnum):
    ACTIVE = "active"
    ROLLING_OUT = "rolling_out"
    STABLE = "stable"
    DEGRADING = "degrading"
    DISABLED = "disabled"


class FlagRisk(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"
    NONE = "none"


# --- Models ---


class FlagImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flag_id: str = ""
    flag_impact_type: FlagImpactType = FlagImpactType.PERFORMANCE
    flag_status: FlagStatus = FlagStatus.ACTIVE
    flag_risk: FlagRisk = FlagRisk.LOW
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactMeasurement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flag_id: str = ""
    flag_impact_type: FlagImpactType = FlagImpactType.PERFORMANCE
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FeatureFlagImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_measurements: int = 0
    negative_flags: int = 0
    avg_impact_score: float = 0.0
    by_impact_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_impactful: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class FeatureFlagImpactTracker:
    """Track feature flag impacts, identify negative flags, and detect regressions."""

    def __init__(
        self,
        max_records: int = 200000,
        max_negative_impact_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_negative_impact_pct = max_negative_impact_pct
        self._records: list[FlagImpactRecord] = []
        self._measurements: list[ImpactMeasurement] = []
        logger.info(
            "feature_flag_impact.initialized",
            max_records=max_records,
            max_negative_impact_pct=max_negative_impact_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_impact(
        self,
        flag_id: str,
        flag_impact_type: FlagImpactType = FlagImpactType.PERFORMANCE,
        flag_status: FlagStatus = FlagStatus.ACTIVE,
        flag_risk: FlagRisk = FlagRisk.LOW,
        impact_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> FlagImpactRecord:
        record = FlagImpactRecord(
            flag_id=flag_id,
            flag_impact_type=flag_impact_type,
            flag_status=flag_status,
            flag_risk=flag_risk,
            impact_score=impact_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "feature_flag_impact.impact_recorded",
            record_id=record.id,
            flag_id=flag_id,
            flag_impact_type=flag_impact_type.value,
            flag_status=flag_status.value,
        )
        return record

    def get_impact(self, record_id: str) -> FlagImpactRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_impacts(
        self,
        impact_type: FlagImpactType | None = None,
        status: FlagStatus | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FlagImpactRecord]:
        results = list(self._records)
        if impact_type is not None:
            results = [r for r in results if r.flag_impact_type == impact_type]
        if status is not None:
            results = [r for r in results if r.flag_status == status]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_measurement(
        self,
        flag_id: str,
        flag_impact_type: FlagImpactType = FlagImpactType.PERFORMANCE,
        value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ImpactMeasurement:
        measurement = ImpactMeasurement(
            flag_id=flag_id,
            flag_impact_type=flag_impact_type,
            value=value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._measurements.append(measurement)
        if len(self._measurements) > self._max_records:
            self._measurements = self._measurements[-self._max_records :]
        logger.info(
            "feature_flag_impact.measurement_added",
            flag_id=flag_id,
            flag_impact_type=flag_impact_type.value,
            value=value,
        )
        return measurement

    # -- domain operations --------------------------------------------------

    def analyze_flag_performance(self) -> dict[str, Any]:
        """Group by impact type; return count and avg impact score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.flag_impact_type.value
            type_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for impact_type, scores in type_data.items():
            result[impact_type] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_negative_flags(self) -> list[dict[str, Any]]:
        """Return records where status == DEGRADING or DISABLED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.flag_status in (
                FlagStatus.DEGRADING,
                FlagStatus.DISABLED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "flag_id": r.flag_id,
                        "flag_impact_type": r.flag_impact_type.value,
                        "flag_status": r.flag_status.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_impact_score(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg score."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(scores),
                    "avg_impact_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"], reverse=True)
        return results

    def detect_impact_regressions(self) -> dict[str, Any]:
        """Split-half on value; delta threshold 5.0."""
        if len(self._measurements) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [m.value for m in self._measurements]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> FeatureFlagImpactReport:
        by_impact_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_impact_type[r.flag_impact_type.value] = (
                by_impact_type.get(r.flag_impact_type.value, 0) + 1
            )
            by_status[r.flag_status.value] = by_status.get(r.flag_status.value, 0) + 1
            by_risk[r.flag_risk.value] = by_risk.get(r.flag_risk.value, 0) + 1
        negative_count = sum(
            1 for r in self._records if r.flag_status in (FlagStatus.DEGRADING, FlagStatus.DISABLED)
        )
        scores = [r.impact_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        rankings = self.rank_by_impact_score()
        top_impactful = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        negative_rate = (
            round(negative_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        if negative_rate > self._max_negative_impact_pct:
            recs.append(
                f"Negative impact rate {negative_rate}% exceeds threshold"
                f" ({self._max_negative_impact_pct}%)"
            )
        if negative_count > 0:
            recs.append(f"{negative_count} negative flag(s) detected — review impact")
        if not recs:
            recs.append("Feature flag impact is acceptable")
        return FeatureFlagImpactReport(
            total_records=len(self._records),
            total_measurements=len(self._measurements),
            negative_flags=negative_count,
            avg_impact_score=avg_score,
            by_impact_type=by_impact_type,
            by_status=by_status,
            by_risk=by_risk,
            top_impactful=top_impactful,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._measurements.clear()
        logger.info("feature_flag_impact.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.flag_impact_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_measurements": len(self._measurements),
            "max_negative_impact_pct": self._max_negative_impact_pct,
            "impact_type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_flags": len({r.flag_id for r in self._records}),
        }
