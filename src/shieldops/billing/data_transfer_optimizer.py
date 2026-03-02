"""Data Transfer Optimizer — minimize data transfer costs across cloud boundaries."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TransferType(StrEnum):
    INTER_REGION = "inter_region"
    INTER_AZ = "inter_az"
    INTERNET = "internet"
    VPN = "vpn"
    DIRECT_CONNECT = "direct_connect"


class OptimizationAction(StrEnum):
    COMPRESS = "compress"
    CACHE = "cache"
    RELOCATE = "relocate"
    BATCH = "batch"
    DEDUPLICATE = "deduplicate"


class TransferDirection(StrEnum):
    INGRESS = "ingress"
    EGRESS = "egress"
    INTRA = "intra"
    CROSS_CLOUD = "cross_cloud"
    HYBRID = "hybrid"


# --- Models ---


class DataTransferRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transfer_type: TransferType = TransferType.INTERNET
    optimization_action: OptimizationAction = OptimizationAction.COMPRESS
    transfer_direction: TransferDirection = TransferDirection.EGRESS
    transfer_gb: float = 0.0
    cost_before: float = 0.0
    cost_after: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TransferAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transfer_type: TransferType = TransferType.INTERNET
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DataTransferReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    optimized_count: int = 0
    avg_cost_reduction: float = 0.0
    by_transfer_type: dict[str, int] = Field(default_factory=dict)
    by_optimization_action: dict[str, int] = Field(default_factory=dict)
    by_transfer_direction: dict[str, int] = Field(default_factory=dict)
    top_optimizations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataTransferOptimizer:
    """Minimize data transfer costs across cloud regions and boundaries."""

    def __init__(
        self,
        max_records: int = 200000,
        cost_reduction_threshold: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._cost_reduction_threshold = cost_reduction_threshold
        self._records: list[DataTransferRecord] = []
        self._analyses: list[TransferAnalysis] = []
        logger.info(
            "data_transfer_optimizer.initialized",
            max_records=max_records,
            cost_reduction_threshold=cost_reduction_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_transfer(
        self,
        transfer_type: TransferType = TransferType.INTERNET,
        optimization_action: OptimizationAction = OptimizationAction.COMPRESS,
        transfer_direction: TransferDirection = TransferDirection.EGRESS,
        transfer_gb: float = 0.0,
        cost_before: float = 0.0,
        cost_after: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DataTransferRecord:
        record = DataTransferRecord(
            transfer_type=transfer_type,
            optimization_action=optimization_action,
            transfer_direction=transfer_direction,
            transfer_gb=transfer_gb,
            cost_before=cost_before,
            cost_after=cost_after,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_transfer_optimizer.transfer_recorded",
            record_id=record.id,
            transfer_type=transfer_type.value,
            transfer_gb=transfer_gb,
        )
        return record

    def get_transfer(self, record_id: str) -> DataTransferRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_transfers(
        self,
        transfer_type: TransferType | None = None,
        transfer_direction: TransferDirection | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DataTransferRecord]:
        results = list(self._records)
        if transfer_type is not None:
            results = [r for r in results if r.transfer_type == transfer_type]
        if transfer_direction is not None:
            results = [r for r in results if r.transfer_direction == transfer_direction]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        transfer_type: TransferType = TransferType.INTERNET,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TransferAnalysis:
        analysis = TransferAnalysis(
            transfer_type=transfer_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "data_transfer_optimizer.analysis_added",
            transfer_type=transfer_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        """Group by transfer_type; return count and avg cost reduction."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.transfer_type.value
            reduction = r.cost_before - r.cost_after
            type_data.setdefault(key, []).append(reduction)
        result: dict[str, Any] = {}
        for ttype, reductions in type_data.items():
            result[ttype] = {
                "count": len(reductions),
                "avg_cost_reduction": round(sum(reductions) / len(reductions), 2),
            }
        return result

    def identify_high_cost_transfers(self) -> list[dict[str, Any]]:
        """Return records where cost_before >= cost_reduction_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.cost_before >= self._cost_reduction_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "transfer_type": r.transfer_type.value,
                        "transfer_gb": r.transfer_gb,
                        "cost_before": r.cost_before,
                        "cost_after": r.cost_after,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["cost_before"], reverse=True)

    def rank_by_transfer_cost(self) -> list[dict[str, Any]]:
        """Group by service, total cost_before, sort descending."""
        svc_costs: dict[str, float] = {}
        for r in self._records:
            svc_costs[r.service] = svc_costs.get(r.service, 0.0) + r.cost_before
        results: list[dict[str, Any]] = [
            {"service": svc, "total_transfer_cost": round(cost, 2)}
            for svc, cost in svc_costs.items()
        ]
        results.sort(key=lambda x: x["total_transfer_cost"], reverse=True)
        return results

    def detect_transfer_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DataTransferReport:
        by_type: dict[str, int] = {}
        by_action: dict[str, int] = {}
        by_direction: dict[str, int] = {}
        for r in self._records:
            by_type[r.transfer_type.value] = by_type.get(r.transfer_type.value, 0) + 1
            by_action[r.optimization_action.value] = (
                by_action.get(r.optimization_action.value, 0) + 1
            )
            by_direction[r.transfer_direction.value] = (
                by_direction.get(r.transfer_direction.value, 0) + 1
            )
        optimized_count = sum(1 for r in self._records if r.cost_after < r.cost_before)
        reductions = [r.cost_before - r.cost_after for r in self._records]
        avg_cost_reduction = round(sum(reductions) / len(reductions), 2) if reductions else 0.0
        top_list = self.identify_high_cost_transfers()
        top_optimizations = [o["record_id"] for o in top_list[:5]]
        recs: list[str] = []
        if optimized_count > 0:
            recs.append(f"{optimized_count} transfer route(s) successfully optimized")
        if avg_cost_reduction > 0:
            recs.append(f"Avg transfer cost reduction ${avg_cost_reduction:.2f}")
        if not recs:
            recs.append("Data transfer optimization is healthy")
        return DataTransferReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            optimized_count=optimized_count,
            avg_cost_reduction=avg_cost_reduction,
            by_transfer_type=by_type,
            by_optimization_action=by_action,
            by_transfer_direction=by_direction,
            top_optimizations=top_optimizations,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("data_transfer_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.transfer_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "cost_reduction_threshold": self._cost_reduction_threshold,
            "transfer_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
