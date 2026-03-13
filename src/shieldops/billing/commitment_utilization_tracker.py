"""Commitment Utilization Tracker
measure commitment utilization, detect underutilized,
recommend adjustments."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CommitmentType(StrEnum):
    RESERVED_INSTANCE = "reserved_instance"
    SAVINGS_PLAN = "savings_plan"
    CUD = "cud"
    ENTERPRISE_AGREEMENT = "enterprise_agreement"


class UtilizationLevel(StrEnum):
    OPTIMAL = "optimal"
    ACCEPTABLE = "acceptable"
    LOW = "low"
    CRITICAL = "critical"


class AdjustmentAction(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    EXCHANGE = "exchange"
    TERMINATE = "terminate"


# --- Models ---


class CommitmentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    commitment_id: str = ""
    commitment_type: CommitmentType = CommitmentType.RESERVED_INSTANCE
    utilization_level: UtilizationLevel = UtilizationLevel.ACCEPTABLE
    adjustment_action: AdjustmentAction = AdjustmentAction.INCREASE
    utilization_pct: float = 0.0
    monthly_commitment: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CommitmentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    commitment_id: str = ""
    commitment_type: CommitmentType = CommitmentType.RESERVED_INSTANCE
    utilization_pct: float = 0.0
    utilization_level: UtilizationLevel = UtilizationLevel.ACCEPTABLE
    waste_amount: float = 0.0
    recommended_action: AdjustmentAction = AdjustmentAction.INCREASE
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CommitmentReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_utilization: float = 0.0
    by_commitment_type: dict[str, int] = Field(default_factory=dict)
    by_utilization_level: dict[str, int] = Field(default_factory=dict)
    by_adjustment_action: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CommitmentUtilizationTracker:
    """Measure commitment utilization, detect
    underutilized, recommend adjustments."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CommitmentRecord] = []
        self._analyses: dict[str, CommitmentAnalysis] = {}
        logger.info(
            "commitment_utilization.init",
            max_records=max_records,
        )

    def add_record(
        self,
        commitment_id: str = "",
        commitment_type: CommitmentType = (CommitmentType.RESERVED_INSTANCE),
        utilization_level: UtilizationLevel = (UtilizationLevel.ACCEPTABLE),
        adjustment_action: AdjustmentAction = (AdjustmentAction.INCREASE),
        utilization_pct: float = 0.0,
        monthly_commitment: float = 0.0,
        description: str = "",
    ) -> CommitmentRecord:
        record = CommitmentRecord(
            commitment_id=commitment_id,
            commitment_type=commitment_type,
            utilization_level=utilization_level,
            adjustment_action=adjustment_action,
            utilization_pct=utilization_pct,
            monthly_commitment=monthly_commitment,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "commitment_utilization.record_added",
            record_id=record.id,
            commitment_id=commitment_id,
        )
        return record

    def process(self, key: str) -> CommitmentAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        waste = round(
            rec.monthly_commitment * (1 - rec.utilization_pct / 100),
            2,
        )
        analysis = CommitmentAnalysis(
            commitment_id=rec.commitment_id,
            commitment_type=rec.commitment_type,
            utilization_pct=rec.utilization_pct,
            utilization_level=rec.utilization_level,
            waste_amount=waste,
            recommended_action=(rec.adjustment_action),
            description=(f"Commitment {rec.commitment_id} util {rec.utilization_pct}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CommitmentReport:
        by_ct: dict[str, int] = {}
        by_ul: dict[str, int] = {}
        by_aa: dict[str, int] = {}
        utils: list[float] = []
        for r in self._records:
            k = r.commitment_type.value
            by_ct[k] = by_ct.get(k, 0) + 1
            k2 = r.utilization_level.value
            by_ul[k2] = by_ul.get(k2, 0) + 1
            k3 = r.adjustment_action.value
            by_aa[k3] = by_aa.get(k3, 0) + 1
            utils.append(r.utilization_pct)
        avg = round(sum(utils) / len(utils), 2) if utils else 0.0
        recs: list[str] = []
        low = [
            r
            for r in self._records
            if r.utilization_level
            in (
                UtilizationLevel.LOW,
                UtilizationLevel.CRITICAL,
            )
        ]
        if low:
            recs.append(f"{len(low)} underutilized commitments need review")
        if not recs:
            recs.append("Commitment utilization healthy")
        return CommitmentReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_utilization=avg,
            by_commitment_type=by_ct,
            by_utilization_level=by_ul,
            by_adjustment_action=by_aa,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ct_dist: dict[str, int] = {}
        for r in self._records:
            k = r.commitment_type.value
            ct_dist[k] = ct_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "commitment_type_dist": ct_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("commitment_utilization.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def measure_commitment_utilization(
        self,
    ) -> list[dict[str, Any]]:
        """Measure utilization per commitment."""
        cmt_utils: dict[str, list[float]] = {}
        cmt_types: dict[str, str] = {}
        for r in self._records:
            cmt_utils.setdefault(r.commitment_id, []).append(r.utilization_pct)
            cmt_types[r.commitment_id] = r.commitment_type.value
        results: list[dict[str, Any]] = []
        for cid, utils in cmt_utils.items():
            avg = round(sum(utils) / len(utils), 2)
            results.append(
                {
                    "commitment_id": cid,
                    "type": cmt_types[cid],
                    "avg_utilization": avg,
                    "samples": len(utils),
                }
            )
        results.sort(
            key=lambda x: x["avg_utilization"],
        )
        return results

    def detect_underutilized_commitments(
        self,
    ) -> list[dict[str, Any]]:
        """Detect underutilized commitments."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.utilization_pct < 70 and r.commitment_id not in seen:
                seen.add(r.commitment_id)
                waste = round(
                    r.monthly_commitment * (1 - r.utilization_pct / 100),
                    2,
                )
                results.append(
                    {
                        "commitment_id": (r.commitment_id),
                        "type": (r.commitment_type.value),
                        "utilization": (r.utilization_pct),
                        "monthly_waste": waste,
                    }
                )
        results.sort(
            key=lambda x: x["monthly_waste"],
            reverse=True,
        )
        return results

    def recommend_commitment_adjustments(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend adjustments for commitments."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.commitment_id not in seen:
                seen.add(r.commitment_id)
                action = "maintain"
                if r.utilization_pct < 50:
                    action = "terminate"
                elif r.utilization_pct < 70:
                    action = "decrease"
                elif r.utilization_pct > 95:
                    action = "increase"
                results.append(
                    {
                        "commitment_id": (r.commitment_id),
                        "type": (r.commitment_type.value),
                        "utilization": (r.utilization_pct),
                        "action": action,
                    }
                )
        return results
