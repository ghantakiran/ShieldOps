"""Security Compliance Bridge — bridge security controls to compliance frameworks."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BridgeStatus(StrEnum):
    ALIGNED = "aligned"
    PARTIAL_ALIGNMENT = "partial_alignment"
    MISALIGNED = "misaligned"
    GAP_DETECTED = "gap_detected"
    NOT_ASSESSED = "not_assessed"


class SecurityFramework(StrEnum):
    NIST = "nist"
    CIS = "cis"
    ISO27001 = "iso27001"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"


class MappingConfidence(StrEnum):
    EXACT = "exact"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNMAPPED = "unmapped"


# --- Models ---


class BridgeRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    control_id: str = ""
    control_name: str = ""
    framework: SecurityFramework = SecurityFramework.NIST
    bridge_status: BridgeStatus = BridgeStatus.NOT_ASSESSED
    alignment_score_pct: float = 0.0
    gap_description: str = ""
    created_at: float = Field(default_factory=time.time)


class FrameworkMapping(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    source_framework: SecurityFramework = SecurityFramework.NIST
    target_framework: SecurityFramework = SecurityFramework.CIS
    source_control_id: str = ""
    target_control_id: str = ""
    mapping_confidence: MappingConfidence = MappingConfidence.MODERATE
    notes: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceBridgeReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_bridges: int = 0
    total_mappings: int = 0
    avg_alignment_score_pct: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    gap_count: int = 0
    aligned_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityComplianceBridge:
    """Bridge security controls to compliance frameworks."""

    def __init__(
        self,
        max_records: int = 200000,
        min_alignment_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_alignment_pct = min_alignment_pct
        self._records: list[BridgeRecord] = []
        self._mappings: list[FrameworkMapping] = []
        logger.info(
            "compliance_bridge.initialized",
            max_records=max_records,
            min_alignment_pct=min_alignment_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_bridge(
        self,
        control_id: str,
        control_name: str = "",
        framework: SecurityFramework = SecurityFramework.NIST,
        bridge_status: BridgeStatus = BridgeStatus.NOT_ASSESSED,
        alignment_score_pct: float = 0.0,
        gap_description: str = "",
    ) -> BridgeRecord:
        record = BridgeRecord(
            control_id=control_id,
            control_name=control_name,
            framework=framework,
            bridge_status=bridge_status,
            alignment_score_pct=alignment_score_pct,
            gap_description=gap_description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_bridge.bridge_recorded",
            record_id=record.id,
            control_id=control_id,
            framework=framework.value,
            bridge_status=bridge_status.value,
        )
        return record

    def get_bridge(self, record_id: str) -> BridgeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_bridges(
        self,
        framework: SecurityFramework | None = None,
        bridge_status: BridgeStatus | None = None,
        limit: int = 50,
    ) -> list[BridgeRecord]:
        results = list(self._records)
        if framework is not None:
            results = [r for r in results if r.framework == framework]
        if bridge_status is not None:
            results = [r for r in results if r.bridge_status == bridge_status]
        return results[-limit:]

    def add_mapping(
        self,
        source_framework: SecurityFramework = SecurityFramework.NIST,
        target_framework: SecurityFramework = SecurityFramework.CIS,
        source_control_id: str = "",
        target_control_id: str = "",
        mapping_confidence: MappingConfidence = MappingConfidence.MODERATE,
        notes: str = "",
    ) -> FrameworkMapping:
        mapping = FrameworkMapping(
            source_framework=source_framework,
            target_framework=target_framework,
            source_control_id=source_control_id,
            target_control_id=target_control_id,
            mapping_confidence=mapping_confidence,
            notes=notes,
        )
        self._mappings.append(mapping)
        if len(self._mappings) > self._max_records:
            self._mappings = self._mappings[-self._max_records :]
        logger.info(
            "compliance_bridge.mapping_added",
            source_framework=source_framework.value,
            target_framework=target_framework.value,
            mapping_confidence=mapping_confidence.value,
        )
        return mapping

    # -- domain operations -----------------------------------------------

    def analyze_alignment_by_framework(self, framework: SecurityFramework) -> dict[str, Any]:
        """Analyze alignment scores for controls in a specific framework."""
        records = [r for r in self._records if r.framework == framework]
        if not records:
            return {"framework": framework.value, "status": "no_data"}
        avg_score = round(sum(r.alignment_score_pct for r in records) / len(records), 2)
        return {
            "framework": framework.value,
            "record_count": len(records),
            "avg_alignment_score_pct": avg_score,
            "meets_threshold": avg_score >= self._min_alignment_pct,
        }

    def identify_security_gaps(self) -> list[dict[str, Any]]:
        """Find controls with GAP_DETECTED or MISALIGNED status."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.bridge_status in (BridgeStatus.GAP_DETECTED, BridgeStatus.MISALIGNED):
                results.append(
                    {
                        "record_id": r.id,
                        "control_id": r.control_id,
                        "framework": r.framework.value,
                        "bridge_status": r.bridge_status.value,
                        "alignment_score_pct": r.alignment_score_pct,
                        "gap_description": r.gap_description,
                    }
                )
        results.sort(key=lambda x: x["alignment_score_pct"])
        return results

    def rank_by_alignment_score(self) -> list[dict[str, Any]]:
        """Rank controls by alignment score descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "record_id": r.id,
                    "control_id": r.control_id,
                    "framework": r.framework.value,
                    "alignment_score_pct": r.alignment_score_pct,
                    "bridge_status": r.bridge_status.value,
                }
            )
        results.sort(key=lambda x: x["alignment_score_pct"], reverse=True)
        return results

    def detect_alignment_drift(self) -> list[dict[str, Any]]:
        """Detect frameworks where average alignment is below threshold."""
        framework_scores: dict[str, list[float]] = {}
        for r in self._records:
            framework_scores.setdefault(r.framework.value, []).append(r.alignment_score_pct)
        results: list[dict[str, Any]] = []
        for fw, scores in framework_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            if avg < self._min_alignment_pct:
                results.append(
                    {
                        "framework": fw,
                        "avg_alignment_pct": avg,
                        "threshold_pct": self._min_alignment_pct,
                        "drift_detected": True,
                    }
                )
        results.sort(key=lambda x: x["avg_alignment_pct"])
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ComplianceBridgeReport:
        by_framework: dict[str, int] = {}
        by_status: dict[str, int] = {}
        total_score = 0.0
        for r in self._records:
            by_framework[r.framework.value] = by_framework.get(r.framework.value, 0) + 1
            by_status[r.bridge_status.value] = by_status.get(r.bridge_status.value, 0) + 1
            total_score += r.alignment_score_pct
        avg_score = round(total_score / len(self._records), 2) if self._records else 0.0
        gap_count = sum(
            1
            for r in self._records
            if r.bridge_status in (BridgeStatus.GAP_DETECTED, BridgeStatus.MISALIGNED)
        )
        aligned_count = sum(1 for r in self._records if r.bridge_status == BridgeStatus.ALIGNED)
        recs: list[str] = []
        if avg_score < self._min_alignment_pct and self._records:
            recs.append(
                f"Average alignment {avg_score}% is below threshold {self._min_alignment_pct}%"
            )
        if gap_count > 0:
            recs.append(f"{gap_count} control(s) have detected security gaps requiring remediation")
        if not recs:
            recs.append("Security compliance bridge alignment meets targets")
        return ComplianceBridgeReport(
            total_bridges=len(self._records),
            total_mappings=len(self._mappings),
            avg_alignment_score_pct=avg_score,
            by_framework=by_framework,
            by_status=by_status,
            gap_count=gap_count,
            aligned_count=aligned_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._mappings.clear()
        logger.info("compliance_bridge.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        framework_dist: dict[str, int] = {}
        for r in self._records:
            key = r.framework.value
            framework_dist[key] = framework_dist.get(key, 0) + 1
        return {
            "total_bridges": len(self._records),
            "total_mappings": len(self._mappings),
            "min_alignment_pct": self._min_alignment_pct,
            "framework_distribution": framework_dist,
            "unique_controls": len({r.control_id for r in self._records}),
        }
