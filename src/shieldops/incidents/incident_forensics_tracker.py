"""Incident Forensics Tracker — digital evidence chain of custody, integrity hashing."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EvidenceCategory(StrEnum):
    MEMORY_DUMP = "memory_dump"
    DISK_IMAGE = "disk_image"
    NETWORK_CAPTURE = "network_capture"
    LOG_ARTIFACT = "log_artifact"
    REGISTRY_SNAPSHOT = "registry_snapshot"


class CustodyStatus(StrEnum):
    PRESERVED = "preserved"
    IN_ANALYSIS = "in_analysis"
    TRANSFERRED = "transferred"
    ARCHIVED = "archived"
    COMPROMISED = "compromised"


class IntegrityLevel(StrEnum):
    VERIFIED = "verified"
    PENDING_VERIFICATION = "pending_verification"
    TAMPER_DETECTED = "tamper_detected"
    HASH_MISMATCH = "hash_mismatch"
    UNKNOWN = "unknown"


# --- Models ---


class ForensicRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_name: str = ""
    evidence_category: EvidenceCategory = EvidenceCategory.MEMORY_DUMP
    custody_status: CustodyStatus = CustodyStatus.PRESERVED
    integrity_level: IntegrityLevel = IntegrityLevel.VERIFIED
    integrity_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ForensicAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_name: str = ""
    evidence_category: EvidenceCategory = EvidenceCategory.MEMORY_DUMP
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ForensicsReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_integrity_count: int = 0
    avg_integrity_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_custody: dict[str, int] = Field(default_factory=dict)
    by_integrity: dict[str, int] = Field(default_factory=dict)
    top_low_integrity: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentForensicsTracker:
    """Digital evidence chain of custody, integrity hashing."""

    def __init__(
        self,
        max_records: int = 200000,
        integrity_threshold: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._integrity_threshold = integrity_threshold
        self._records: list[ForensicRecord] = []
        self._analyses: list[ForensicAnalysis] = []
        logger.info(
            "incident_forensics_tracker.initialized",
            max_records=max_records,
            integrity_threshold=integrity_threshold,
        )

    def record_artifact(
        self,
        artifact_name: str,
        evidence_category: EvidenceCategory = EvidenceCategory.MEMORY_DUMP,
        custody_status: CustodyStatus = CustodyStatus.PRESERVED,
        integrity_level: IntegrityLevel = IntegrityLevel.VERIFIED,
        integrity_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ForensicRecord:
        record = ForensicRecord(
            artifact_name=artifact_name,
            evidence_category=evidence_category,
            custody_status=custody_status,
            integrity_level=integrity_level,
            integrity_score=integrity_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_forensics_tracker.artifact_recorded",
            record_id=record.id,
            artifact_name=artifact_name,
            evidence_category=evidence_category.value,
            custody_status=custody_status.value,
        )
        return record

    def get_artifact(self, record_id: str) -> ForensicRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_artifacts(
        self,
        evidence_category: EvidenceCategory | None = None,
        custody_status: CustodyStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ForensicRecord]:
        results = list(self._records)
        if evidence_category is not None:
            results = [r for r in results if r.evidence_category == evidence_category]
        if custody_status is not None:
            results = [r for r in results if r.custody_status == custody_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        artifact_name: str,
        evidence_category: EvidenceCategory = EvidenceCategory.MEMORY_DUMP,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ForensicAnalysis:
        analysis = ForensicAnalysis(
            artifact_name=artifact_name,
            evidence_category=evidence_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "incident_forensics_tracker.analysis_added",
            artifact_name=artifact_name,
            evidence_category=evidence_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_category_distribution(self) -> dict[str, Any]:
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.evidence_category.value
            cat_data.setdefault(key, []).append(r.integrity_score)
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_integrity_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_integrity_artifacts(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.integrity_score < self._integrity_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "artifact_name": r.artifact_name,
                        "evidence_category": r.evidence_category.value,
                        "integrity_score": r.integrity_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["integrity_score"])

    def rank_by_integrity(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.integrity_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {"service": svc, "avg_integrity_score": round(sum(scores) / len(scores), 2)}
            )
        results.sort(key=lambda x: x["avg_integrity_score"])
        return results

    def detect_integrity_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ForensicsReport:
        by_category: dict[str, int] = {}
        by_custody: dict[str, int] = {}
        by_integrity: dict[str, int] = {}
        for r in self._records:
            by_category[r.evidence_category.value] = (
                by_category.get(r.evidence_category.value, 0) + 1
            )
            by_custody[r.custody_status.value] = by_custody.get(r.custody_status.value, 0) + 1
            by_integrity[r.integrity_level.value] = by_integrity.get(r.integrity_level.value, 0) + 1
        low_integrity_count = sum(
            1 for r in self._records if r.integrity_score < self._integrity_threshold
        )
        scores = [r.integrity_score for r in self._records]
        avg_integrity_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_integrity_artifacts()
        top_low_integrity = [o["artifact_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_integrity_count > 0:
            recs.append(
                f"{low_integrity_count} artifact(s) below integrity threshold "
                f"({self._integrity_threshold})"
            )
        if self._records and avg_integrity_score < self._integrity_threshold:
            recs.append(
                f"Avg integrity score {avg_integrity_score} below threshold "
                f"({self._integrity_threshold})"
            )
        if not recs:
            recs.append("Forensic evidence integrity is healthy")
        return ForensicsReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_integrity_count=low_integrity_count,
            avg_integrity_score=avg_integrity_score,
            by_category=by_category,
            by_custody=by_custody,
            by_integrity=by_integrity,
            top_low_integrity=top_low_integrity,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("incident_forensics_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.evidence_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "integrity_threshold": self._integrity_threshold,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
