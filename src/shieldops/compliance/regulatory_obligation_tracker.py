"""Regulatory Obligation Tracker
compute obligation completion rate, detect approaching
deadlines, rank obligations by penalty risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ObligationStatus(StrEnum):
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    NON_COMPLIANT = "non_compliant"
    EXEMPT = "exempt"


class ObligationType(StrEnum):
    REPORTING = "reporting"
    CERTIFICATION = "certification"
    ASSESSMENT = "assessment"
    DISCLOSURE = "disclosure"


class PenaltyRisk(StrEnum):
    SEVERE = "severe"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# --- Models ---


class ObligationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    obligation_id: str = ""
    obligation_status: ObligationStatus = ObligationStatus.COMPLIANT
    obligation_type: ObligationType = ObligationType.REPORTING
    penalty_risk: PenaltyRisk = PenaltyRisk.LOW
    completion_rate: float = 0.0
    days_to_deadline: float = 30.0
    penalty_amount: float = 0.0
    regulation: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ObligationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    obligation_id: str = ""
    obligation_status: ObligationStatus = ObligationStatus.COMPLIANT
    computed_completion: float = 0.0
    is_approaching_deadline: bool = False
    penalty_exposure: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ObligationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_completion_rate: float = 0.0
    by_obligation_status: dict[str, int] = Field(default_factory=dict)
    by_obligation_type: dict[str, int] = Field(default_factory=dict)
    by_penalty_risk: dict[str, int] = Field(default_factory=dict)
    at_risk_obligations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RegulatoryObligationTracker:
    """Compute obligation completion rate, detect approaching
    deadlines, rank obligations by penalty risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ObligationRecord] = []
        self._analyses: dict[str, ObligationAnalysis] = {}
        logger.info(
            "regulatory_obligation_tracker.init",
            max_records=max_records,
        )

    def add_record(
        self,
        obligation_id: str = "",
        obligation_status: ObligationStatus = ObligationStatus.COMPLIANT,
        obligation_type: ObligationType = ObligationType.REPORTING,
        penalty_risk: PenaltyRisk = PenaltyRisk.LOW,
        completion_rate: float = 0.0,
        days_to_deadline: float = 30.0,
        penalty_amount: float = 0.0,
        regulation: str = "",
        description: str = "",
    ) -> ObligationRecord:
        record = ObligationRecord(
            obligation_id=obligation_id,
            obligation_status=obligation_status,
            obligation_type=obligation_type,
            penalty_risk=penalty_risk,
            completion_rate=completion_rate,
            days_to_deadline=days_to_deadline,
            penalty_amount=penalty_amount,
            regulation=regulation,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "regulatory_obligation.record_added",
            record_id=record.id,
            obligation_id=obligation_id,
        )
        return record

    def process(self, key: str) -> ObligationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        approaching = rec.days_to_deadline <= 14
        exposure = round(rec.penalty_amount * (1.0 - rec.completion_rate / 100.0), 2)
        analysis = ObligationAnalysis(
            obligation_id=rec.obligation_id,
            obligation_status=rec.obligation_status,
            computed_completion=round(rec.completion_rate, 2),
            is_approaching_deadline=approaching,
            penalty_exposure=exposure,
            description=f"Obligation {rec.obligation_id} completion {rec.completion_rate}%",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ObligationReport:
        by_os: dict[str, int] = {}
        by_ot: dict[str, int] = {}
        by_pr: dict[str, int] = {}
        rates: list[float] = []
        for r in self._records:
            k = r.obligation_status.value
            by_os[k] = by_os.get(k, 0) + 1
            k2 = r.obligation_type.value
            by_ot[k2] = by_ot.get(k2, 0) + 1
            k3 = r.penalty_risk.value
            by_pr[k3] = by_pr.get(k3, 0) + 1
            rates.append(r.completion_rate)
        avg = round(sum(rates) / len(rates), 2) if rates else 0.0
        at_risk = list(
            {
                r.obligation_id
                for r in self._records
                if r.obligation_status in (ObligationStatus.AT_RISK, ObligationStatus.NON_COMPLIANT)
            }
        )[:10]
        recs: list[str] = []
        if at_risk:
            recs.append(f"{len(at_risk)} at-risk obligations detected")
        if not recs:
            recs.append("All obligations are compliant")
        return ObligationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_completion_rate=avg,
            by_obligation_status=by_os,
            by_obligation_type=by_ot,
            by_penalty_risk=by_pr,
            at_risk_obligations=at_risk,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        os_dist: dict[str, int] = {}
        for r in self._records:
            k = r.obligation_status.value
            os_dist[k] = os_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "obligation_status_distribution": os_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("regulatory_obligation_tracker.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_obligation_completion_rate(
        self,
    ) -> list[dict[str, Any]]:
        """Compute completion rate per obligation."""
        ob_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.obligation_id not in ob_data:
                ob_data[r.obligation_id] = {
                    "type": r.obligation_type.value,
                    "completion": r.completion_rate,
                    "status": r.obligation_status.value,
                }
        results: list[dict[str, Any]] = []
        for oid, data in ob_data.items():
            results.append(
                {
                    "obligation_id": oid,
                    "obligation_type": data["type"],
                    "completion_rate": data["completion"],
                    "status": data["status"],
                }
            )
        results.sort(key=lambda x: x["completion_rate"])
        return results

    def detect_approaching_deadlines(
        self,
    ) -> list[dict[str, Any]]:
        """Detect obligations with approaching deadlines."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.days_to_deadline <= 14 and r.obligation_id not in seen:
                seen.add(r.obligation_id)
                results.append(
                    {
                        "obligation_id": r.obligation_id,
                        "obligation_type": r.obligation_type.value,
                        "days_to_deadline": r.days_to_deadline,
                        "completion_rate": r.completion_rate,
                    }
                )
        results.sort(key=lambda x: x["days_to_deadline"])
        return results

    def rank_obligations_by_penalty_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank obligations by penalty risk exposure."""
        ob_exposure: dict[str, float] = {}
        ob_types: dict[str, str] = {}
        for r in self._records:
            exposure = r.penalty_amount * (1.0 - r.completion_rate / 100.0)
            ob_exposure[r.obligation_id] = max(ob_exposure.get(r.obligation_id, 0.0), exposure)
            ob_types[r.obligation_id] = r.obligation_type.value
        results: list[dict[str, Any]] = []
        for oid, exposure in ob_exposure.items():
            results.append(
                {
                    "obligation_id": oid,
                    "obligation_type": ob_types[oid],
                    "penalty_exposure": round(exposure, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["penalty_exposure"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
