"""Commitment Utilization Tracker — track commitment usage, waste, and risks."""

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
    COMMITTED_USE = "committed_use"
    ENTERPRISE_AGREEMENT = "enterprise_agreement"
    SPOT_FLEET = "spot_fleet"


class UtilizationLevel(StrEnum):
    OPTIMAL = "optimal"
    GOOD = "good"
    UNDERUTILIZED = "underutilized"
    WASTED = "wasted"
    EXPIRED = "expired"


class CommitmentRisk(StrEnum):
    OVERCOMMITTED = "overcommitted"
    WELL_BALANCED = "well_balanced"
    UNDERCOMMITTED = "undercommitted"
    EXPIRING_SOON = "expiring_soon"
    MISMATCHED = "mismatched"


# --- Models ---


class CommitmentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    commitment_id: str = ""
    commitment_type: CommitmentType = CommitmentType.RESERVED_INSTANCE
    utilization_level: UtilizationLevel = UtilizationLevel.GOOD
    commitment_risk: CommitmentRisk = CommitmentRisk.WELL_BALANCED
    utilization_pct: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class UtilizationDetail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detail_name: str = ""
    commitment_type: CommitmentType = CommitmentType.RESERVED_INSTANCE
    utilization_threshold: float = 0.0
    avg_utilization_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CommitmentUtilizationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_details: int = 0
    underutilized_commitments: int = 0
    avg_utilization_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CommitmentUtilizationTracker:
    """Track commitment usage, waste, and risks to optimize cloud spending."""

    def __init__(
        self,
        max_records: int = 200000,
        min_utilization_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_utilization_pct = min_utilization_pct
        self._records: list[CommitmentRecord] = []
        self._details: list[UtilizationDetail] = []
        logger.info(
            "commitment_tracker.initialized",
            max_records=max_records,
            min_utilization_pct=min_utilization_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_commitment(
        self,
        commitment_id: str,
        commitment_type: CommitmentType = CommitmentType.RESERVED_INSTANCE,
        utilization_level: UtilizationLevel = UtilizationLevel.GOOD,
        commitment_risk: CommitmentRisk = CommitmentRisk.WELL_BALANCED,
        utilization_pct: float = 0.0,
        team: str = "",
    ) -> CommitmentRecord:
        record = CommitmentRecord(
            commitment_id=commitment_id,
            commitment_type=commitment_type,
            utilization_level=utilization_level,
            commitment_risk=commitment_risk,
            utilization_pct=utilization_pct,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "commitment_tracker.recorded",
            record_id=record.id,
            commitment_id=commitment_id,
            commitment_type=commitment_type.value,
            utilization_level=utilization_level.value,
        )
        return record

    def get_commitment(self, record_id: str) -> CommitmentRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_commitments(
        self,
        ctype: CommitmentType | None = None,
        level: UtilizationLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CommitmentRecord]:
        results = list(self._records)
        if ctype is not None:
            results = [r for r in results if r.commitment_type == ctype]
        if level is not None:
            results = [r for r in results if r.utilization_level == level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_utilization(
        self,
        detail_name: str,
        commitment_type: CommitmentType = CommitmentType.RESERVED_INSTANCE,
        utilization_threshold: float = 0.0,
        avg_utilization_pct: float = 0.0,
        description: str = "",
    ) -> UtilizationDetail:
        detail = UtilizationDetail(
            detail_name=detail_name,
            commitment_type=commitment_type,
            utilization_threshold=utilization_threshold,
            avg_utilization_pct=avg_utilization_pct,
            description=description,
        )
        self._details.append(detail)
        if len(self._details) > self._max_records:
            self._details = self._details[-self._max_records :]
        logger.info(
            "commitment_tracker.detail_added",
            detail_name=detail_name,
            commitment_type=commitment_type.value,
            utilization_threshold=utilization_threshold,
        )
        return detail

    # -- domain operations --------------------------------------------------

    def analyze_utilization_patterns(self) -> dict[str, Any]:
        """Group by type; return count and avg utilization pct per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.commitment_type.value
            type_data.setdefault(key, []).append(r.utilization_pct)
        result: dict[str, Any] = {}
        for ctype, pcts in type_data.items():
            result[ctype] = {
                "count": len(pcts),
                "avg_utilization_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_underutilized_commitments(self) -> list[dict[str, Any]]:
        """Return records where level is WASTED or UNDERUTILIZED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.utilization_level in (
                UtilizationLevel.WASTED,
                UtilizationLevel.UNDERUTILIZED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "commitment_id": r.commitment_id,
                        "utilization_level": r.utilization_level.value,
                        "utilization_pct": r.utilization_pct,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_utilization_pct(self) -> list[dict[str, Any]]:
        """Group by team, avg utilization pct, sort descending."""
        team_pcts: dict[str, list[float]] = {}
        for r in self._records:
            team_pcts.setdefault(r.team, []).append(r.utilization_pct)
        results: list[dict[str, Any]] = []
        for team, pcts in team_pcts.items():
            results.append(
                {
                    "team": team,
                    "avg_utilization_pct": round(sum(pcts) / len(pcts), 2),
                    "count": len(pcts),
                }
            )
        results.sort(key=lambda x: x["avg_utilization_pct"], reverse=True)
        return results

    def detect_commitment_risks(self) -> dict[str, Any]:
        """Split-half on avg_utilization_pct; delta threshold 5.0."""
        if len(self._details) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        pcts = [d.avg_utilization_pct for d in self._details]
        mid = len(pcts) // 2
        first_half = pcts[:mid]
        second_half = pcts[mid:]
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

    def generate_report(self) -> CommitmentUtilizationReport:
        by_type: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_type[r.commitment_type.value] = by_type.get(r.commitment_type.value, 0) + 1
            by_level[r.utilization_level.value] = by_level.get(r.utilization_level.value, 0) + 1
            by_risk[r.commitment_risk.value] = by_risk.get(r.commitment_risk.value, 0) + 1
        underutilized_count = sum(
            1
            for r in self._records
            if r.utilization_level in (UtilizationLevel.WASTED, UtilizationLevel.UNDERUTILIZED)
        )
        avg_pct = (
            round(sum(r.utilization_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_utilization_pct()
        top_items = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if avg_pct < self._min_utilization_pct:
            recs.append(
                f"Avg utilization {avg_pct}% is below threshold ({self._min_utilization_pct}%)"
            )
        if underutilized_count > 0:
            recs.append(
                f"{underutilized_count} underutilized commitment(s) detected — review usage"
            )
        if not recs:
            recs.append("Commitment utilization is within acceptable limits")
        return CommitmentUtilizationReport(
            total_records=len(self._records),
            total_details=len(self._details),
            underutilized_commitments=underutilized_count,
            avg_utilization_pct=avg_pct,
            by_type=by_type,
            by_level=by_level,
            by_risk=by_risk,
            top_items=top_items,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._details.clear()
        logger.info("commitment_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.commitment_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_details": len(self._details),
            "min_utilization_pct": self._min_utilization_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_commitments": len({r.commitment_id for r in self._records}),
        }
