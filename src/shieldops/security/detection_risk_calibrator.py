"""Detection Risk Calibrator
calibrate detection risk scores, compute false
positive impact, recommend risk adjustments."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CalibrationMethod(StrEnum):
    HISTORICAL = "historical"
    PEER_BENCHMARK = "peer_benchmark"
    EXPERT = "expert"
    AUTOMATED = "automated"


class DetectionAccuracy(StrEnum):
    PRECISE = "precise"
    ACCEPTABLE = "acceptable"
    NOISY = "noisy"
    UNRELIABLE = "unreliable"


class RiskAdjustment(StrEnum):
    INCREASE = "increase"
    MAINTAIN = "maintain"
    DECREASE = "decrease"
    SUPPRESS = "suppress"


# --- Models ---


class DetectionCalibrationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detection_id: str = ""
    method: CalibrationMethod = CalibrationMethod.HISTORICAL
    accuracy: DetectionAccuracy = DetectionAccuracy.ACCEPTABLE
    adjustment: RiskAdjustment = RiskAdjustment.MAINTAIN
    original_score: float = 0.0
    calibrated_score: float = 0.0
    false_positive_rate: float = 0.0
    total_fires: int = 0
    true_positives: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DetectionCalibrationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detection_id: str = ""
    accuracy: DetectionAccuracy = DetectionAccuracy.ACCEPTABLE
    fp_impact_score: float = 0.0
    recommended_adjustment: RiskAdjustment = RiskAdjustment.MAINTAIN
    calibration_delta: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DetectionCalibrationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_fp_rate: float = 0.0
    by_method: dict[str, int] = Field(default_factory=dict)
    by_accuracy: dict[str, int] = Field(default_factory=dict)
    by_adjustment: dict[str, int] = Field(default_factory=dict)
    noisy_detections: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DetectionRiskCalibrator:
    """Calibrate detection risk, compute FP impact,
    recommend risk adjustments."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[DetectionCalibrationRecord] = []
        self._analyses: dict[str, DetectionCalibrationAnalysis] = {}
        logger.info(
            "detection_risk_calibrator.init",
            max_records=max_records,
        )

    def add_record(
        self,
        detection_id: str = "",
        method: CalibrationMethod = (CalibrationMethod.HISTORICAL),
        accuracy: DetectionAccuracy = (DetectionAccuracy.ACCEPTABLE),
        adjustment: RiskAdjustment = (RiskAdjustment.MAINTAIN),
        original_score: float = 0.0,
        calibrated_score: float = 0.0,
        false_positive_rate: float = 0.0,
        total_fires: int = 0,
        true_positives: int = 0,
        description: str = "",
    ) -> DetectionCalibrationRecord:
        record = DetectionCalibrationRecord(
            detection_id=detection_id,
            method=method,
            accuracy=accuracy,
            adjustment=adjustment,
            original_score=original_score,
            calibrated_score=calibrated_score,
            false_positive_rate=false_positive_rate,
            total_fires=total_fires,
            true_positives=true_positives,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "detection_risk_calibrator.record_added",
            record_id=record.id,
            detection_id=detection_id,
        )
        return record

    def process(self, key: str) -> DetectionCalibrationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        delta = round(
            rec.calibrated_score - rec.original_score,
            2,
        )
        fp_impact = round(rec.false_positive_rate * 10, 2)
        if rec.false_positive_rate > 0.5:
            adj = RiskAdjustment.DECREASE
        elif rec.false_positive_rate > 0.8:
            adj = RiskAdjustment.SUPPRESS
        elif rec.false_positive_rate < 0.1:
            adj = RiskAdjustment.INCREASE
        else:
            adj = RiskAdjustment.MAINTAIN
        analysis = DetectionCalibrationAnalysis(
            detection_id=rec.detection_id,
            accuracy=rec.accuracy,
            fp_impact_score=fp_impact,
            recommended_adjustment=adj,
            calibration_delta=delta,
            description=(f"Detection {rec.detection_id} delta={delta}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> DetectionCalibrationReport:
        by_m: dict[str, int] = {}
        by_a: dict[str, int] = {}
        by_adj: dict[str, int] = {}
        fp_rates: list[float] = []
        for r in self._records:
            k = r.method.value
            by_m[k] = by_m.get(k, 0) + 1
            k2 = r.accuracy.value
            by_a[k2] = by_a.get(k2, 0) + 1
            k3 = r.adjustment.value
            by_adj[k3] = by_adj.get(k3, 0) + 1
            fp_rates.append(r.false_positive_rate)
        avg_fp = round(sum(fp_rates) / len(fp_rates), 2) if fp_rates else 0.0
        noisy = [
            r.detection_id
            for r in self._records
            if r.accuracy
            in (
                DetectionAccuracy.NOISY,
                DetectionAccuracy.UNRELIABLE,
            )
        ][:10]
        recs: list[str] = []
        if noisy:
            recs.append(f"{len(noisy)} noisy detections need calibration")
        if not recs:
            recs.append("Detection accuracy healthy")
        return DetectionCalibrationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_fp_rate=avg_fp,
            by_method=by_m,
            by_accuracy=by_a,
            by_adjustment=by_adj,
            noisy_detections=noisy,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        acc_dist: dict[str, int] = {}
        for r in self._records:
            k = r.accuracy.value
            acc_dist[k] = acc_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "accuracy_distribution": acc_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("detection_risk_calibrator.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def calibrate_detection_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Calibrate risk per detection."""
        det_data: dict[str, list[DetectionCalibrationRecord]] = {}
        for r in self._records:
            det_data.setdefault(r.detection_id, []).append(r)
        results: list[dict[str, Any]] = []
        for did, recs in det_data.items():
            avg_orig = round(
                sum(r.original_score for r in recs) / len(recs),
                2,
            )
            avg_cal = round(
                sum(r.calibrated_score for r in recs) / len(recs),
                2,
            )
            results.append(
                {
                    "detection_id": did,
                    "avg_original": avg_orig,
                    "avg_calibrated": avg_cal,
                    "delta": round(avg_cal - avg_orig, 2),
                    "sample_count": len(recs),
                }
            )
        return results

    def compute_false_positive_impact(
        self,
    ) -> list[dict[str, Any]]:
        """Compute FP impact per detection."""
        det_fp: dict[str, list[float]] = {}
        for r in self._records:
            det_fp.setdefault(r.detection_id, []).append(r.false_positive_rate)
        results: list[dict[str, Any]] = []
        for did, rates in det_fp.items():
            avg = round(sum(rates) / len(rates), 2)
            results.append(
                {
                    "detection_id": did,
                    "avg_fp_rate": avg,
                    "fp_impact": round(avg * 10, 2),
                    "is_noisy": avg > 0.5,
                }
            )
        results.sort(
            key=lambda x: x["fp_impact"],
            reverse=True,
        )
        return results

    def recommend_risk_adjustment(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend risk adjustments."""
        det_data: dict[str, list[float]] = {}
        for r in self._records:
            det_data.setdefault(r.detection_id, []).append(r.false_positive_rate)
        results: list[dict[str, Any]] = []
        for did, rates in det_data.items():
            avg = sum(rates) / len(rates)
            if avg > 0.8:
                adj = "suppress"
            elif avg > 0.5:
                adj = "decrease"
            elif avg < 0.1:
                adj = "increase"
            else:
                adj = "maintain"
            results.append(
                {
                    "detection_id": did,
                    "avg_fp_rate": round(avg, 2),
                    "recommendation": adj,
                }
            )
        return results
