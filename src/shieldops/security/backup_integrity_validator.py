"""Backup Integrity Validator — validate backup integrity across types and methods."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BackupType(StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"
    CONTINUOUS = "continuous"


class IntegrityCheck(StrEnum):
    CHECKSUM = "checksum"
    RESTORE_TEST = "restore_test"
    ENCRYPTION_VERIFY = "encryption_verify"
    SIZE_VALIDATION = "size_validation"
    METADATA_CHECK = "metadata_check"


class BackupStatus(StrEnum):
    VALID = "valid"
    CORRUPTED = "corrupted"
    INCOMPLETE = "incomplete"
    EXPIRED = "expired"
    UNTESTED = "untested"


# --- Models ---


class BackupIntegrityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    backup_id: str = ""
    backup_type: BackupType = BackupType.FULL
    integrity_check: IntegrityCheck = IntegrityCheck.CHECKSUM
    backup_status: BackupStatus = BackupStatus.VALID
    integrity_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BackupIntegrityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    backup_id: str = ""
    backup_type: BackupType = BackupType.FULL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BackupIntegrityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_integrity_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_check: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class BackupIntegrityValidator:
    """Validate backup integrity across backup types, check methods, and statuses."""

    def __init__(
        self,
        max_records: int = 200000,
        integrity_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._integrity_threshold = integrity_threshold
        self._records: list[BackupIntegrityRecord] = []
        self._analyses: list[BackupIntegrityAnalysis] = []
        logger.info(
            "backup_integrity_validator.initialized",
            max_records=max_records,
            integrity_threshold=integrity_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_backup(
        self,
        backup_id: str,
        backup_type: BackupType = BackupType.FULL,
        integrity_check: IntegrityCheck = IntegrityCheck.CHECKSUM,
        backup_status: BackupStatus = BackupStatus.VALID,
        integrity_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BackupIntegrityRecord:
        record = BackupIntegrityRecord(
            backup_id=backup_id,
            backup_type=backup_type,
            integrity_check=integrity_check,
            backup_status=backup_status,
            integrity_score=integrity_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "backup_integrity_validator.backup_recorded",
            record_id=record.id,
            backup_id=backup_id,
            backup_type=backup_type.value,
            integrity_check=integrity_check.value,
        )
        return record

    def get_backup(self, record_id: str) -> BackupIntegrityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_backups(
        self,
        backup_type: BackupType | None = None,
        integrity_check: IntegrityCheck | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BackupIntegrityRecord]:
        results = list(self._records)
        if backup_type is not None:
            results = [r for r in results if r.backup_type == backup_type]
        if integrity_check is not None:
            results = [r for r in results if r.integrity_check == integrity_check]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        backup_id: str,
        backup_type: BackupType = BackupType.FULL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BackupIntegrityAnalysis:
        analysis = BackupIntegrityAnalysis(
            backup_id=backup_id,
            backup_type=backup_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "backup_integrity_validator.analysis_added",
            backup_id=backup_id,
            backup_type=backup_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.backup_type.value
            type_data.setdefault(key, []).append(r.integrity_score)
        result: dict[str, Any] = {}
        for btype, scores in type_data.items():
            result[btype] = {
                "count": len(scores),
                "avg_integrity_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_integrity_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.integrity_score < self._integrity_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "backup_id": r.backup_id,
                        "backup_type": r.backup_type.value,
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
                {
                    "service": svc,
                    "avg_integrity_score": round(sum(scores) / len(scores), 2),
                }
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

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> BackupIntegrityReport:
        by_type: dict[str, int] = {}
        by_check: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.backup_type.value] = by_type.get(r.backup_type.value, 0) + 1
            by_check[r.integrity_check.value] = by_check.get(r.integrity_check.value, 0) + 1
            by_status[r.backup_status.value] = by_status.get(r.backup_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.integrity_score < self._integrity_threshold)
        scores = [r.integrity_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_integrity_gaps()
        top_gaps = [o["backup_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} backup(s) below integrity threshold ({self._integrity_threshold})"
            )
        if self._records and avg_score < self._integrity_threshold:
            recs.append(
                f"Avg integrity score {avg_score} below threshold ({self._integrity_threshold})"
            )
        if not recs:
            recs.append("Backup integrity is healthy")
        return BackupIntegrityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_integrity_score=avg_score,
            by_type=by_type,
            by_check=by_check,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("backup_integrity_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.backup_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "integrity_threshold": self._integrity_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
