"""Artifact Scanning Orchestrator — orchestrate multi-dimensional artifact scans."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ScanType(StrEnum):
    VULNERABILITY = "vulnerability"
    LICENSE = "license"
    SECRET = "secret"  # noqa: S105
    MALWARE = "malware"
    COMPLIANCE = "compliance"


class ScanPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"


class OrchestratorAction(StrEnum):
    SCAN = "scan"
    RESCAN = "rescan"
    SKIP = "skip"
    QUARANTINE = "quarantine"
    APPROVE = "approve"


# --- Models ---


class ScanRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_name: str = ""
    scan_type: ScanType = ScanType.VULNERABILITY
    scan_priority: ScanPriority = ScanPriority.MEDIUM
    orchestrator_action: OrchestratorAction = OrchestratorAction.SCAN
    scan_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ScanAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_name: str = ""
    scan_type: ScanType = ScanType.VULNERABILITY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ArtifactScanningReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_scan_score: float = 0.0
    by_scan_type: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ArtifactScanningOrchestrator:
    """Orchestrate vulnerability, license, secret, malware, and compliance scans."""

    def __init__(
        self,
        max_records: int = 200000,
        scan_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._scan_gap_threshold = scan_gap_threshold
        self._records: list[ScanRecord] = []
        self._analyses: list[ScanAnalysis] = []
        logger.info(
            "artifact_scanning_orchestrator.initialized",
            max_records=max_records,
            scan_gap_threshold=scan_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_scan(
        self,
        artifact_name: str,
        scan_type: ScanType = ScanType.VULNERABILITY,
        scan_priority: ScanPriority = ScanPriority.MEDIUM,
        orchestrator_action: OrchestratorAction = OrchestratorAction.SCAN,
        scan_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ScanRecord:
        record = ScanRecord(
            artifact_name=artifact_name,
            scan_type=scan_type,
            scan_priority=scan_priority,
            orchestrator_action=orchestrator_action,
            scan_score=scan_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "artifact_scanning_orchestrator.scan_recorded",
            record_id=record.id,
            artifact_name=artifact_name,
            scan_type=scan_type.value,
            scan_priority=scan_priority.value,
        )
        return record

    def get_scan(self, record_id: str) -> ScanRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_scans(
        self,
        scan_type: ScanType | None = None,
        scan_priority: ScanPriority | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ScanRecord]:
        results = list(self._records)
        if scan_type is not None:
            results = [r for r in results if r.scan_type == scan_type]
        if scan_priority is not None:
            results = [r for r in results if r.scan_priority == scan_priority]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        artifact_name: str,
        scan_type: ScanType = ScanType.VULNERABILITY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ScanAnalysis:
        analysis = ScanAnalysis(
            artifact_name=artifact_name,
            scan_type=scan_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "artifact_scanning_orchestrator.analysis_added",
            artifact_name=artifact_name,
            scan_type=scan_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_scan_type_distribution(self) -> dict[str, Any]:
        """Group by scan_type; return count and avg scan_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.scan_type.value
            type_data.setdefault(key, []).append(r.scan_score)
        result: dict[str, Any] = {}
        for stype, scores in type_data.items():
            result[stype] = {
                "count": len(scores),
                "avg_scan_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_scan_gaps(self) -> list[dict[str, Any]]:
        """Return records where scan_score < scan_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.scan_score < self._scan_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "artifact_name": r.artifact_name,
                        "scan_type": r.scan_type.value,
                        "scan_score": r.scan_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["scan_score"])

    def rank_by_scan_score(self) -> list[dict[str, Any]]:
        """Group by service, avg scan_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.scan_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_scan_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_scan_score"])
        return results

    def detect_scan_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
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

    def generate_report(self) -> ArtifactScanningReport:
        by_scan_type: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_scan_type[r.scan_type.value] = by_scan_type.get(r.scan_type.value, 0) + 1
            by_priority[r.scan_priority.value] = by_priority.get(r.scan_priority.value, 0) + 1
            by_action[r.orchestrator_action.value] = (
                by_action.get(r.orchestrator_action.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.scan_score < self._scan_gap_threshold)
        scores = [r.scan_score for r in self._records]
        avg_scan_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_scan_gaps()
        top_gaps = [o["artifact_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} artifact(s) below scan threshold ({self._scan_gap_threshold})"
            )
        if self._records and avg_scan_score < self._scan_gap_threshold:
            recs.append(
                f"Avg scan score {avg_scan_score} below threshold ({self._scan_gap_threshold})"
            )
        if not recs:
            recs.append("Artifact scanning coverage is healthy")
        return ArtifactScanningReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_scan_score=avg_scan_score,
            by_scan_type=by_scan_type,
            by_priority=by_priority,
            by_action=by_action,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("artifact_scanning_orchestrator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.scan_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "scan_gap_threshold": self._scan_gap_threshold,
            "scan_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
