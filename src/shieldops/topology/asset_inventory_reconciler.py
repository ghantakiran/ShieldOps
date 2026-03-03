"""Asset Inventory Reconciler — reconcile asset inventories across multiple sources."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReconciliationStatus(StrEnum):
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    MISSING = "missing"
    STALE = "stale"
    UNKNOWN = "unknown"


class AssetSource(StrEnum):
    CMDB = "cmdb"
    CLOUD_API = "cloud_api"
    SCANNER = "scanner"
    AGENT = "agent"
    MANUAL = "manual"


class DiscrepancyType(StrEnum):
    MISSING_ASSET = "missing_asset"
    EXTRA_ASSET = "extra_asset"
    ATTRIBUTE_MISMATCH = "attribute_mismatch"
    STALE_DATA = "stale_data"
    CLASSIFICATION_ERROR = "classification_error"


# --- Models ---


class ReconciliationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_name: str = ""
    reconciliation_status: ReconciliationStatus = ReconciliationStatus.MATCHED
    asset_source: AssetSource = AssetSource.CMDB
    discrepancy_type: DiscrepancyType = DiscrepancyType.MISSING_ASSET
    reconciliation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ReconciliationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_name: str = ""
    reconciliation_status: ReconciliationStatus = ReconciliationStatus.MATCHED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReconciliationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_discrepancy: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AssetInventoryReconciler:
    """Reconcile asset inventories across multiple sources to identify discrepancies."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ReconciliationRecord] = []
        self._analyses: list[ReconciliationAnalysis] = []
        logger.info(
            "asset_inventory_reconciler.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_reconciliation(
        self,
        asset_name: str,
        reconciliation_status: ReconciliationStatus = ReconciliationStatus.MATCHED,
        asset_source: AssetSource = AssetSource.CMDB,
        discrepancy_type: DiscrepancyType = DiscrepancyType.MISSING_ASSET,
        reconciliation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ReconciliationRecord:
        record = ReconciliationRecord(
            asset_name=asset_name,
            reconciliation_status=reconciliation_status,
            asset_source=asset_source,
            discrepancy_type=discrepancy_type,
            reconciliation_score=reconciliation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "asset_inventory_reconciler.recorded",
            record_id=record.id,
            asset_name=asset_name,
        )
        return record

    def get_reconciliation(self, record_id: str) -> ReconciliationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_reconciliations(
        self,
        reconciliation_status: ReconciliationStatus | None = None,
        asset_source: AssetSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ReconciliationRecord]:
        results = list(self._records)
        if reconciliation_status is not None:
            results = [r for r in results if r.reconciliation_status == reconciliation_status]
        if asset_source is not None:
            results = [r for r in results if r.asset_source == asset_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        asset_name: str,
        reconciliation_status: ReconciliationStatus = ReconciliationStatus.MATCHED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ReconciliationAnalysis:
        analysis = ReconciliationAnalysis(
            asset_name=asset_name,
            reconciliation_status=reconciliation_status,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "asset_inventory_reconciler.analysis_added",
            asset_name=asset_name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.reconciliation_status.value
            type_data.setdefault(key, []).append(r.reconciliation_score)
        result: dict[str, Any] = {}
        for k, scores in type_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.reconciliation_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "asset_name": r.asset_name,
                        "reconciliation_status": r.reconciliation_status.value,
                        "reconciliation_score": r.reconciliation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["reconciliation_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.reconciliation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
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

    def generate_report(self) -> ReconciliationReport:
        by_status_d: dict[str, int] = {}
        by_source_d: dict[str, int] = {}
        by_discrepancy_d: dict[str, int] = {}
        for r in self._records:
            st = r.reconciliation_status.value
            by_status_d[st] = by_status_d.get(st, 0) + 1
            src = r.asset_source.value
            by_source_d[src] = by_source_d.get(src, 0) + 1
            disc = r.discrepancy_type.value
            by_discrepancy_d[disc] = by_discrepancy_d.get(disc, 0) + 1
        gap_count = sum(1 for r in self._records if r.reconciliation_score < self._threshold)
        scores = [r.reconciliation_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["asset_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} reconciliation(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Asset inventory reconciliation is healthy")
        return ReconciliationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_status=by_status_d,
            by_source=by_source_d,
            by_discrepancy=by_discrepancy_d,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("asset_inventory_reconciler.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            key = r.reconciliation_status.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "distribution": dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
