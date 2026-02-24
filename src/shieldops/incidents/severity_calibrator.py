"""Incident Severity Calibrator — calibrate severity from actual impact."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SeverityLevel(StrEnum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"
    SEV5 = "sev5"


class CalibrationResult(StrEnum):
    CORRECT = "correct"
    OVER_CLASSIFIED = "over_classified"
    UNDER_CLASSIFIED = "under_classified"
    NEEDS_REVIEW = "needs_review"
    AMBIGUOUS = "ambiguous"


class ImpactDimension(StrEnum):
    USER_COUNT = "user_count"
    REVENUE = "revenue"
    DURATION = "duration"
    SERVICE_COUNT = "service_count"
    DATA_LOSS = "data_loss"


# --- Models ---


class SeverityRecord(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    incident_id: str = ""
    initial_severity: SeverityLevel = SeverityLevel.SEV3
    calibrated_severity: SeverityLevel = SeverityLevel.SEV3
    calibration_result: CalibrationResult = CalibrationResult.NEEDS_REVIEW
    users_affected: int = 0
    revenue_impact: float = 0.0
    duration_minutes: int = 0
    impact_scores: dict[str, float] = Field(
        default_factory=dict,
    )
    created_at: float = Field(default_factory=time.time)


class CalibrationRule(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    dimension: ImpactDimension = ImpactDimension.USER_COUNT
    threshold: float = 0.0
    maps_to_severity: SeverityLevel = SeverityLevel.SEV3
    weight: float = 1.0
    created_at: float = Field(default_factory=time.time)


class CalibrationReport(BaseModel):
    total_records: int = 0
    accuracy_pct: float = 0.0
    over_classified_pct: float = 0.0
    under_classified_pct: float = 0.0
    by_severity: dict[str, int] = Field(
        default_factory=dict,
    )
    by_result: dict[str, int] = Field(
        default_factory=dict,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Severity ordering helper ---

_SEV_ORDER = {
    SeverityLevel.SEV1: 1,
    SeverityLevel.SEV2: 2,
    SeverityLevel.SEV3: 3,
    SeverityLevel.SEV4: 4,
    SeverityLevel.SEV5: 5,
}


# --- Engine ---


class IncidentSeverityCalibrator:
    """Calibrate incident severity from actual impact metrics."""

    def __init__(
        self,
        max_records: int = 200000,
        accuracy_target_pct: float = 85.0,
    ) -> None:
        self._max_records = max_records
        self._accuracy_target_pct = accuracy_target_pct
        self._records: list[SeverityRecord] = []
        self._rules: list[CalibrationRule] = []
        logger.info(
            "severity_calibrator.initialized",
            max_records=max_records,
            accuracy_target_pct=accuracy_target_pct,
        )

    # -- CRUD --

    def record_severity(
        self,
        incident_id: str,
        initial_severity: SeverityLevel,
        users_affected: int = 0,
        revenue_impact: float = 0.0,
        duration_minutes: int = 0,
    ) -> SeverityRecord:
        record = SeverityRecord(
            incident_id=incident_id,
            initial_severity=initial_severity,
            users_affected=users_affected,
            revenue_impact=revenue_impact,
            duration_minutes=duration_minutes,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "severity_calibrator.recorded",
            record_id=record.id,
            incident_id=incident_id,
        )
        return record

    def get_record(self, record_id: str) -> SeverityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        incident_id: str | None = None,
        calibration_result: CalibrationResult | None = None,
        limit: int = 50,
    ) -> list[SeverityRecord]:
        results = list(self._records)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        if calibration_result is not None:
            results = [r for r in results if r.calibration_result == calibration_result]
        return results[-limit:]

    # -- Domain operations --

    def calibrate_severity(self, record_id: str) -> dict[str, Any]:
        record = self.get_record(record_id)
        if record is None:
            return {"error": "record_not_found"}
        cal_sev = self._compute_severity(record)
        record.calibrated_severity = cal_sev
        initial_ord = _SEV_ORDER[record.initial_severity]
        cal_ord = _SEV_ORDER[cal_sev]
        if initial_ord == cal_ord:
            record.calibration_result = CalibrationResult.CORRECT
        elif initial_ord < cal_ord:
            record.calibration_result = CalibrationResult.OVER_CLASSIFIED
        else:
            record.calibration_result = CalibrationResult.UNDER_CLASSIFIED
        logger.info(
            "severity_calibrator.calibrated",
            record_id=record_id,
            result=record.calibration_result.value,
        )
        return {
            "record_id": record_id,
            "initial": record.initial_severity.value,
            "calibrated": cal_sev.value,
            "result": record.calibration_result.value,
        }

    def add_calibration_rule(
        self,
        dimension: ImpactDimension,
        threshold: float,
        maps_to_severity: SeverityLevel,
        weight: float = 1.0,
    ) -> CalibrationRule:
        rule = CalibrationRule(
            dimension=dimension,
            threshold=threshold,
            maps_to_severity=maps_to_severity,
            weight=weight,
        )
        self._rules.append(rule)
        logger.info(
            "severity_calibrator.rule_added",
            rule_id=rule.id,
            dimension=dimension.value,
        )
        return rule

    def calculate_accuracy(self) -> dict[str, Any]:
        if not self._records:
            return {"accuracy_pct": 0.0, "total": 0}
        calibrated = [
            r for r in self._records if r.calibration_result != CalibrationResult.NEEDS_REVIEW
        ]
        if not calibrated:
            return {"accuracy_pct": 0.0, "total": 0}
        correct = sum(1 for r in calibrated if r.calibration_result == CalibrationResult.CORRECT)
        accuracy = round(correct / len(calibrated) * 100.0, 2)
        return {
            "accuracy_pct": accuracy,
            "total": len(calibrated),
            "correct": correct,
            "meets_target": (accuracy >= self._accuracy_target_pct),
        }

    def detect_classification_drift(
        self,
    ) -> dict[str, Any]:
        if len(self._records) < 10:
            return {"drift_detected": False, "reason": ""}
        recent = self._records[-10:]
        over = sum(1 for r in recent if r.calibration_result == CalibrationResult.OVER_CLASSIFIED)
        under = sum(1 for r in recent if r.calibration_result == CalibrationResult.UNDER_CLASSIFIED)
        drift = over >= 5 or under >= 5
        reason = ""
        if over >= 5:
            reason = "Trend toward over-classification"
        elif under >= 5:
            reason = "Trend toward under-classification"
        return {
            "drift_detected": drift,
            "over_classified_recent": over,
            "under_classified_recent": under,
            "reason": reason,
        }

    def identify_miscalibrated_services(
        self,
    ) -> list[dict[str, Any]]:
        by_incident: dict[str, list[SeverityRecord]] = {}
        for r in self._records:
            by_incident.setdefault(r.incident_id, []).append(r)
        results: list[dict[str, Any]] = []
        for inc_id, records in by_incident.items():
            miscal = [
                r
                for r in records
                if r.calibration_result
                in (
                    CalibrationResult.OVER_CLASSIFIED,
                    CalibrationResult.UNDER_CLASSIFIED,
                )
            ]
            if miscal:
                results.append(
                    {
                        "incident_id": inc_id,
                        "total_records": len(records),
                        "miscalibrated": len(miscal),
                        "types": [r.calibration_result.value for r in miscal],
                    }
                )
        return results

    # -- Reports --

    def generate_calibration_report(
        self,
    ) -> CalibrationReport:
        by_sev: dict[str, int] = {}
        by_result: dict[str, int] = {}
        for r in self._records:
            by_sev[r.initial_severity.value] = by_sev.get(r.initial_severity.value, 0) + 1
            by_result[r.calibration_result.value] = by_result.get(r.calibration_result.value, 0) + 1
        total = len(self._records)
        correct = by_result.get(CalibrationResult.CORRECT.value, 0)
        over = by_result.get(CalibrationResult.OVER_CLASSIFIED.value, 0)
        under = by_result.get(CalibrationResult.UNDER_CLASSIFIED.value, 0)
        accuracy = round(correct / total * 100.0, 2) if total > 0 else 0.0
        over_pct = round(over / total * 100.0, 2) if total > 0 else 0.0
        under_pct = round(under / total * 100.0, 2) if total > 0 else 0.0
        recs: list[str] = []
        if accuracy < self._accuracy_target_pct:
            recs.append("Accuracy below target — review rules")
        if over_pct > 30.0:
            recs.append("High over-classification — lower thresholds")
        if under_pct > 30.0:
            recs.append("High under-classification — raise thresholds")
        return CalibrationReport(
            total_records=total,
            accuracy_pct=accuracy,
            over_classified_pct=over_pct,
            under_classified_pct=under_pct,
            by_severity=by_sev,
            by_result=by_result,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        accuracy_info = self.calculate_accuracy()
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "accuracy_pct": accuracy_info["accuracy_pct"],
            "unique_incidents": len({r.incident_id for r in self._records}),
        }

    # -- Internal helpers --

    def _compute_severity(self, record: SeverityRecord) -> SeverityLevel:
        if self._rules:
            return self._apply_rules(record)
        if (
            record.users_affected >= 10000
            or record.revenue_impact >= 100000
            or record.duration_minutes >= 240
        ):
            return SeverityLevel.SEV1
        if (
            record.users_affected >= 1000
            or record.revenue_impact >= 10000
            or record.duration_minutes >= 60
        ):
            return SeverityLevel.SEV2
        if (
            record.users_affected >= 100
            or record.revenue_impact >= 1000
            or record.duration_minutes >= 30
        ):
            return SeverityLevel.SEV3
        if (
            record.users_affected >= 10
            or record.revenue_impact >= 100
            or record.duration_minutes >= 10
        ):
            return SeverityLevel.SEV4
        return SeverityLevel.SEV5

    def _apply_rules(self, record: SeverityRecord) -> SeverityLevel:
        best_sev = SeverityLevel.SEV5
        best_ord = _SEV_ORDER[best_sev]
        dim_values = {
            ImpactDimension.USER_COUNT: float(record.users_affected),
            ImpactDimension.REVENUE: record.revenue_impact,
            ImpactDimension.DURATION: float(record.duration_minutes),
        }
        for rule in self._rules:
            val = dim_values.get(rule.dimension, 0.0)
            if val >= rule.threshold:
                rule_ord = _SEV_ORDER[rule.maps_to_severity]
                if rule_ord < best_ord:
                    best_sev = rule.maps_to_severity
                    best_ord = rule_ord
        return best_sev
