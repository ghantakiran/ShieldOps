"""Audit Evidence Mapper — map compliance controls to evidence sources."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ControlFramework(StrEnum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"
    NIST = "nist"


class MappingStatus(StrEnum):
    FULLY_MAPPED = "fully_mapped"
    PARTIALLY_MAPPED = "partially_mapped"
    UNMAPPED = "unmapped"
    STALE = "stale"
    UNDER_REVIEW = "under_review"


class EvidenceType(StrEnum):
    AUTOMATED = "automated"
    MANUAL = "manual"
    HYBRID = "hybrid"
    ATTESTATION = "attestation"
    OBSERVATION = "observation"


# --- Models ---


class EvidenceMappingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    control_framework: ControlFramework = ControlFramework.SOC2
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    evidence_type: EvidenceType = EvidenceType.MANUAL
    mapping_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MappingGap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    control_framework: ControlFramework = ControlFramework.SOC2
    gap_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditEvidenceMapperReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_gaps: int = 0
    unmapped_controls: int = 0
    avg_mapping_score: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_evidence_type: dict[str, int] = Field(default_factory=dict)
    top_unmapped: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditEvidenceMapper:
    """Map compliance controls to evidence sources; automate evidence collection mapping."""

    def __init__(
        self,
        max_records: int = 200000,
        min_mapping_coverage_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_mapping_coverage_pct = min_mapping_coverage_pct
        self._records: list[EvidenceMappingRecord] = []
        self._gaps: list[MappingGap] = []
        logger.info(
            "audit_evidence_mapper.initialized",
            max_records=max_records,
            min_mapping_coverage_pct=min_mapping_coverage_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_mapping(
        self,
        control_id: str,
        control_framework: ControlFramework = ControlFramework.SOC2,
        mapping_status: MappingStatus = MappingStatus.UNMAPPED,
        evidence_type: EvidenceType = EvidenceType.MANUAL,
        mapping_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EvidenceMappingRecord:
        record = EvidenceMappingRecord(
            control_id=control_id,
            control_framework=control_framework,
            mapping_status=mapping_status,
            evidence_type=evidence_type,
            mapping_score=mapping_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_evidence_mapper.mapping_recorded",
            record_id=record.id,
            control_id=control_id,
            control_framework=control_framework.value,
            mapping_status=mapping_status.value,
        )
        return record

    def get_mapping(self, record_id: str) -> EvidenceMappingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_mappings(
        self,
        framework: ControlFramework | None = None,
        status: MappingStatus | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EvidenceMappingRecord]:
        results = list(self._records)
        if framework is not None:
            results = [r for r in results if r.control_framework == framework]
        if status is not None:
            results = [r for r in results if r.mapping_status == status]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_gap(
        self,
        control_id: str,
        control_framework: ControlFramework = ControlFramework.SOC2,
        gap_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MappingGap:
        gap = MappingGap(
            control_id=control_id,
            control_framework=control_framework,
            gap_score=gap_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._gaps.append(gap)
        if len(self._gaps) > self._max_records:
            self._gaps = self._gaps[-self._max_records :]
        logger.info(
            "audit_evidence_mapper.gap_added",
            control_id=control_id,
            control_framework=control_framework.value,
            gap_score=gap_score,
        )
        return gap

    # -- domain operations --------------------------------------------------

    def analyze_mapping_coverage(self) -> dict[str, Any]:
        """Group by framework; return count and avg mapping score."""
        fw_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.control_framework.value
            fw_data.setdefault(key, []).append(r.mapping_score)
        result: dict[str, Any] = {}
        for fw, scores in fw_data.items():
            result[fw] = {
                "count": len(scores),
                "avg_mapping_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_unmapped_controls(self) -> list[dict[str, Any]]:
        """Return records where status is UNMAPPED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.mapping_status == MappingStatus.UNMAPPED:
                results.append(
                    {
                        "record_id": r.id,
                        "control_id": r.control_id,
                        "control_framework": r.control_framework.value,
                        "evidence_type": r.evidence_type.value,
                        "mapping_score": r.mapping_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_mapping_score(self) -> list[dict[str, Any]]:
        """Group by service, avg mapping score, sort ascending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.mapping_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_mapping_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_mapping_score"])
        return results

    def detect_mapping_trends(self) -> dict[str, Any]:
        """Split-half comparison on gap_score; delta threshold 5.0."""
        if len(self._gaps) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [g.gap_score for g in self._gaps]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> AuditEvidenceMapperReport:
        by_framework: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_evidence_type: dict[str, int] = {}
        for r in self._records:
            by_framework[r.control_framework.value] = (
                by_framework.get(r.control_framework.value, 0) + 1
            )
            by_status[r.mapping_status.value] = by_status.get(r.mapping_status.value, 0) + 1
            by_evidence_type[r.evidence_type.value] = (
                by_evidence_type.get(r.evidence_type.value, 0) + 1
            )
        unmapped_controls = sum(
            1 for r in self._records if r.mapping_status == MappingStatus.UNMAPPED
        )
        avg_mapping_score = (
            round(
                sum(r.mapping_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        unmapped = self.identify_unmapped_controls()
        top_unmapped = [u["control_id"] for u in unmapped[:5]]
        recs: list[str] = []
        if unmapped_controls > 0:
            recs.append(
                f"{unmapped_controls} unmapped control(s) — map evidence sources immediately"
            )
        low_score = sum(
            1 for r in self._records if r.mapping_score < self._min_mapping_coverage_pct
        )
        if low_score > 0:
            recs.append(
                f"{low_score} control(s) below mapping coverage threshold"
                f" ({self._min_mapping_coverage_pct}%)"
            )
        if not recs:
            recs.append("Audit evidence mapping levels are healthy")
        return AuditEvidenceMapperReport(
            total_records=len(self._records),
            total_gaps=len(self._gaps),
            unmapped_controls=unmapped_controls,
            avg_mapping_score=avg_mapping_score,
            by_framework=by_framework,
            by_status=by_status,
            by_evidence_type=by_evidence_type,
            top_unmapped=top_unmapped,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._gaps.clear()
        logger.info("audit_evidence_mapper.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        fw_dist: dict[str, int] = {}
        for r in self._records:
            key = r.control_framework.value
            fw_dist[key] = fw_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_gaps": len(self._gaps),
            "min_mapping_coverage_pct": self._min_mapping_coverage_pct,
            "framework_distribution": fw_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
