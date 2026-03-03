"""Bulk Export Detector — detect bulk data export attempts and exfiltration risks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExportMethod(StrEnum):
    API_BULK = "api_bulk"
    DATABASE_DUMP = "database_dump"
    FILE_DOWNLOAD = "file_download"
    CLOUD_SYNC = "cloud_sync"
    SCREEN_CAPTURE = "screen_capture"


class ExportVolume(StrEnum):
    MASSIVE = "massive"
    LARGE = "large"
    MEDIUM = "medium"
    SMALL = "small"
    NORMAL = "normal"


class ExportRisk(StrEnum):
    EXFILTRATION = "exfiltration"
    SUSPICIOUS = "suspicious"
    ELEVATED = "elevated"
    NORMAL = "normal"
    APPROVED = "approved"


# --- Models ---


class BulkExportRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    export_id: str = ""
    export_method: ExportMethod = ExportMethod.API_BULK
    export_volume: ExportVolume = ExportVolume.NORMAL
    export_risk: ExportRisk = ExportRisk.NORMAL
    export_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BulkExportAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    export_id: str = ""
    export_method: ExportMethod = ExportMethod.API_BULK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BulkExportReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_export_score: float = 0.0
    by_method: dict[str, int] = Field(default_factory=dict)
    by_volume: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class BulkExportDetector:
    """Detect bulk data export attempts and assess exfiltration risk."""

    def __init__(
        self,
        max_records: int = 200000,
        export_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._export_threshold = export_threshold
        self._records: list[BulkExportRecord] = []
        self._analyses: list[BulkExportAnalysis] = []
        logger.info(
            "bulk_export_detector.initialized",
            max_records=max_records,
            export_threshold=export_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_export(
        self,
        export_id: str,
        export_method: ExportMethod = ExportMethod.API_BULK,
        export_volume: ExportVolume = ExportVolume.NORMAL,
        export_risk: ExportRisk = ExportRisk.NORMAL,
        export_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BulkExportRecord:
        record = BulkExportRecord(
            export_id=export_id,
            export_method=export_method,
            export_volume=export_volume,
            export_risk=export_risk,
            export_score=export_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "bulk_export_detector.export_recorded",
            record_id=record.id,
            export_id=export_id,
            export_method=export_method.value,
            export_volume=export_volume.value,
        )
        return record

    def get_export(self, record_id: str) -> BulkExportRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_exports(
        self,
        export_method: ExportMethod | None = None,
        export_volume: ExportVolume | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BulkExportRecord]:
        results = list(self._records)
        if export_method is not None:
            results = [r for r in results if r.export_method == export_method]
        if export_volume is not None:
            results = [r for r in results if r.export_volume == export_volume]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        export_id: str,
        export_method: ExportMethod = ExportMethod.API_BULK,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BulkExportAnalysis:
        analysis = BulkExportAnalysis(
            export_id=export_id,
            export_method=export_method,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "bulk_export_detector.analysis_added",
            export_id=export_id,
            export_method=export_method.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_method_distribution(self) -> dict[str, Any]:
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.export_method.value
            method_data.setdefault(key, []).append(r.export_score)
        result: dict[str, Any] = {}
        for method, scores in method_data.items():
            result[method] = {
                "count": len(scores),
                "avg_export_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_export_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.export_score < self._export_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "export_id": r.export_id,
                        "export_method": r.export_method.value,
                        "export_score": r.export_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["export_score"])

    def rank_by_export(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.export_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_export_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_export_score"])
        return results

    def detect_export_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> BulkExportReport:
        by_method: dict[str, int] = {}
        by_volume: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_method[r.export_method.value] = by_method.get(r.export_method.value, 0) + 1
            by_volume[r.export_volume.value] = by_volume.get(r.export_volume.value, 0) + 1
            by_risk[r.export_risk.value] = by_risk.get(r.export_risk.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.export_score < self._export_threshold)
        scores = [r.export_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_export_gaps()
        top_gaps = [o["export_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} export(s) below threshold ({self._export_threshold})")
        if self._records and avg_score < self._export_threshold:
            recs.append(f"Avg export score {avg_score} below threshold ({self._export_threshold})")
        if not recs:
            recs.append("Bulk export detection is healthy")
        return BulkExportReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_export_score=avg_score,
            by_method=by_method,
            by_volume=by_volume,
            by_risk=by_risk,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("bulk_export_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            key = r.export_method.value
            method_dist[key] = method_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "export_threshold": self._export_threshold,
            "method_distribution": method_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
