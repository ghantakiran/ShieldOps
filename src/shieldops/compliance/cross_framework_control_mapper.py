"""Cross Framework Control Mapper
compute control overlap matrix, detect unmapped controls,
rank frameworks by coverage."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class Framework(StrEnum):
    SOC2 = "soc2"
    ISO27001 = "iso27001"
    NIST = "nist"
    PCI_DSS = "pci_dss"


class MappingConfidence(StrEnum):
    EXACT = "exact"
    STRONG = "strong"
    PARTIAL = "partial"
    WEAK = "weak"


class ControlDomain(StrEnum):
    ACCESS = "access"
    ENCRYPTION = "encryption"
    MONITORING = "monitoring"
    INCIDENT_RESPONSE = "incident_response"


# --- Models ---


class ControlMappingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    framework: Framework = Framework.SOC2
    mapping_confidence: MappingConfidence = MappingConfidence.PARTIAL
    control_domain: ControlDomain = ControlDomain.ACCESS
    coverage_score: float = 0.0
    mapped_to_framework: str = ""
    mapped_to_control: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlMappingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    framework: Framework = Framework.SOC2
    computed_coverage: float = 0.0
    is_unmapped: bool = False
    mapping_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ControlMappingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_coverage_score: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_mapping_confidence: dict[str, int] = Field(default_factory=dict)
    by_control_domain: dict[str, int] = Field(default_factory=dict)
    unmapped_controls: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CrossFrameworkControlMapper:
    """Compute control overlap matrix, detect unmapped
    controls, rank frameworks by coverage."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ControlMappingRecord] = []
        self._analyses: dict[str, ControlMappingAnalysis] = {}
        logger.info(
            "cross_framework_control_mapper.init",
            max_records=max_records,
        )

    def add_record(
        self,
        control_id: str = "",
        framework: Framework = Framework.SOC2,
        mapping_confidence: MappingConfidence = MappingConfidence.PARTIAL,
        control_domain: ControlDomain = ControlDomain.ACCESS,
        coverage_score: float = 0.0,
        mapped_to_framework: str = "",
        mapped_to_control: str = "",
        description: str = "",
    ) -> ControlMappingRecord:
        record = ControlMappingRecord(
            control_id=control_id,
            framework=framework,
            mapping_confidence=mapping_confidence,
            control_domain=control_domain,
            coverage_score=coverage_score,
            mapped_to_framework=mapped_to_framework,
            mapped_to_control=mapped_to_control,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cross_framework_control_mapper.record_added",
            record_id=record.id,
            control_id=control_id,
        )
        return record

    def process(self, key: str) -> ControlMappingAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        mappings = sum(1 for r in self._records if r.control_id == rec.control_id)
        is_unmapped = rec.coverage_score == 0.0
        analysis = ControlMappingAnalysis(
            control_id=rec.control_id,
            framework=rec.framework,
            computed_coverage=round(rec.coverage_score, 2),
            is_unmapped=is_unmapped,
            mapping_count=mappings,
            description=f"Control {rec.control_id} coverage {rec.coverage_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ControlMappingReport:
        by_f: dict[str, int] = {}
        by_mc: dict[str, int] = {}
        by_cd: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.framework.value
            by_f[k] = by_f.get(k, 0) + 1
            k2 = r.mapping_confidence.value
            by_mc[k2] = by_mc.get(k2, 0) + 1
            k3 = r.control_domain.value
            by_cd[k3] = by_cd.get(k3, 0) + 1
            scores.append(r.coverage_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        unmapped = list({r.control_id for r in self._records if r.coverage_score == 0.0})[:10]
        recs: list[str] = []
        if unmapped:
            recs.append(f"{len(unmapped)} unmapped controls detected")
        if not recs:
            recs.append("All controls are mapped across frameworks")
        return ControlMappingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_coverage_score=avg,
            by_framework=by_f,
            by_mapping_confidence=by_mc,
            by_control_domain=by_cd,
            unmapped_controls=unmapped,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        f_dist: dict[str, int] = {}
        for r in self._records:
            k = r.framework.value
            f_dist[k] = f_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "framework_distribution": f_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("cross_framework_control_mapper.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_control_overlap_matrix(
        self,
    ) -> list[dict[str, Any]]:
        """Compute overlap matrix between frameworks."""
        pairs: dict[str, int] = {}
        for r in self._records:
            if r.mapped_to_framework:
                pair_key = f"{r.framework.value}->{r.mapped_to_framework}"
                pairs[pair_key] = pairs.get(pair_key, 0) + 1
        results: list[dict[str, Any]] = []
        for pair, count in pairs.items():
            src, tgt = pair.split("->")
            results.append(
                {
                    "source_framework": src,
                    "target_framework": tgt,
                    "overlap_count": count,
                }
            )
        results.sort(key=lambda x: x["overlap_count"], reverse=True)
        return results

    def detect_unmapped_controls(
        self,
    ) -> list[dict[str, Any]]:
        """Detect controls with no cross-framework mapping."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.coverage_score == 0.0 and r.control_id not in seen:
                seen.add(r.control_id)
                results.append(
                    {
                        "control_id": r.control_id,
                        "framework": r.framework.value,
                        "control_domain": r.control_domain.value,
                        "coverage_score": r.coverage_score,
                    }
                )
        results.sort(key=lambda x: x["control_id"])
        return results

    def rank_frameworks_by_coverage(
        self,
    ) -> list[dict[str, Any]]:
        """Rank frameworks by average coverage score."""
        fw_scores: dict[str, list[float]] = {}
        for r in self._records:
            fw_scores.setdefault(r.framework.value, []).append(r.coverage_score)
        results: list[dict[str, Any]] = []
        for fw, scores in fw_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "framework": fw,
                    "avg_coverage": avg,
                    "control_count": len(scores),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_coverage"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
