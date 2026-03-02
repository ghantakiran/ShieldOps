"""Compliance Evidence Automator V2 — SOC-specific automated evidence collection."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EvidenceType(StrEnum):
    LOG_EXPORT = "log_export"
    CONFIGURATION_SNAPSHOT = "configuration_snapshot"
    ACCESS_REVIEW = "access_review"
    VULNERABILITY_SCAN = "vulnerability_scan"
    POLICY_DOCUMENT = "policy_document"


class ComplianceFramework(StrEnum):
    SOC2 = "soc2"
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    NIST_CSF = "nist_csf"


class CollectionStatus(StrEnum):
    COLLECTED = "collected"
    PENDING = "pending"
    FAILED = "failed"
    EXPIRED = "expired"
    VALIDATED = "validated"


# --- Models ---


class EvidenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_name: str = ""
    evidence_type: EvidenceType = EvidenceType.LOG_EXPORT
    compliance_framework: ComplianceFramework = ComplianceFramework.SOC2
    collection_status: CollectionStatus = CollectionStatus.COLLECTED
    completeness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_name: str = ""
    evidence_type: EvidenceType = EvidenceType.LOG_EXPORT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceEvidenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    incomplete_count: int = 0
    avg_completeness_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_incomplete: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceEvidenceAutomatorV2:
    """SOC-specific automated evidence collection."""

    def __init__(
        self,
        max_records: int = 200000,
        completeness_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._completeness_threshold = completeness_threshold
        self._records: list[EvidenceRecord] = []
        self._analyses: list[EvidenceAnalysis] = []
        logger.info(
            "compliance_evidence_automator_v2.initialized",
            max_records=max_records,
            completeness_threshold=completeness_threshold,
        )

    def record_evidence(
        self,
        evidence_name: str,
        evidence_type: EvidenceType = EvidenceType.LOG_EXPORT,
        compliance_framework: ComplianceFramework = ComplianceFramework.SOC2,
        collection_status: CollectionStatus = CollectionStatus.COLLECTED,
        completeness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EvidenceRecord:
        record = EvidenceRecord(
            evidence_name=evidence_name,
            evidence_type=evidence_type,
            compliance_framework=compliance_framework,
            collection_status=collection_status,
            completeness_score=completeness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_evidence_automator_v2.evidence_recorded",
            record_id=record.id,
            evidence_name=evidence_name,
            evidence_type=evidence_type.value,
            compliance_framework=compliance_framework.value,
        )
        return record

    def get_evidence(self, record_id: str) -> EvidenceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_evidence(
        self,
        evidence_type: EvidenceType | None = None,
        compliance_framework: ComplianceFramework | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EvidenceRecord]:
        results = list(self._records)
        if evidence_type is not None:
            results = [r for r in results if r.evidence_type == evidence_type]
        if compliance_framework is not None:
            results = [r for r in results if r.compliance_framework == compliance_framework]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        evidence_name: str,
        evidence_type: EvidenceType = EvidenceType.LOG_EXPORT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EvidenceAnalysis:
        analysis = EvidenceAnalysis(
            evidence_name=evidence_name,
            evidence_type=evidence_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "compliance_evidence_automator_v2.analysis_added",
            evidence_name=evidence_name,
            evidence_type=evidence_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_evidence_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.evidence_type.value
            type_data.setdefault(key, []).append(r.completeness_score)
        result: dict[str, Any] = {}
        for etype, scores in type_data.items():
            result[etype] = {
                "count": len(scores),
                "avg_completeness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_incomplete_evidence(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.completeness_score < self._completeness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "evidence_name": r.evidence_name,
                        "evidence_type": r.evidence_type.value,
                        "completeness_score": r.completeness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["completeness_score"])

    def rank_by_completeness(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.completeness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {"service": svc, "avg_completeness_score": round(sum(scores) / len(scores), 2)}
            )
        results.sort(key=lambda x: x["avg_completeness_score"])
        return results

    def detect_evidence_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ComplianceEvidenceReport:
        by_type: dict[str, int] = {}
        by_framework: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.evidence_type.value] = by_type.get(r.evidence_type.value, 0) + 1
            by_framework[r.compliance_framework.value] = (
                by_framework.get(r.compliance_framework.value, 0) + 1
            )
            by_status[r.collection_status.value] = by_status.get(r.collection_status.value, 0) + 1
        incomplete_count = sum(
            1 for r in self._records if r.completeness_score < self._completeness_threshold
        )
        scores = [r.completeness_score for r in self._records]
        avg_completeness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        incomplete_list = self.identify_incomplete_evidence()
        top_incomplete = [o["evidence_name"] for o in incomplete_list[:5]]
        recs: list[str] = []
        if self._records and incomplete_count > 0:
            recs.append(
                f"{incomplete_count} evidence item(s) below completeness threshold "
                f"({self._completeness_threshold})"
            )
        if self._records and avg_completeness_score < self._completeness_threshold:
            recs.append(
                f"Avg completeness score {avg_completeness_score} below threshold "
                f"({self._completeness_threshold})"
            )
        if not recs:
            recs.append("Compliance evidence collection is healthy")
        return ComplianceEvidenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            incomplete_count=incomplete_count,
            avg_completeness_score=avg_completeness_score,
            by_type=by_type,
            by_framework=by_framework,
            by_status=by_status,
            top_incomplete=top_incomplete,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("compliance_evidence_automator_v2.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.evidence_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "completeness_threshold": self._completeness_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
