"""Compliance Evidence Correlation Engine
compute evidence reuse ratio, detect redundant collections,
rank evidence by cross-control value."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CorrelationType(StrEnum):
    EXACT_MATCH = "exact_match"
    PARTIAL_OVERLAP = "partial_overlap"
    DERIVED = "derived"
    INDEPENDENT = "independent"


class EvidenceScope(StrEnum):
    SINGLE_CONTROL = "single_control"
    MULTI_CONTROL = "multi_control"
    CROSS_FRAMEWORK = "cross_framework"
    UNIVERSAL = "universal"


class CorrelationStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


# --- Models ---


class EvidenceCorrelationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_id: str = ""
    correlation_type: CorrelationType = CorrelationType.INDEPENDENT
    evidence_scope: EvidenceScope = EvidenceScope.SINGLE_CONTROL
    correlation_strength: CorrelationStrength = CorrelationStrength.NONE
    reuse_count: int = 0
    control_count: int = 1
    collection_cost: float = 0.0
    control_id: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceCorrelationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_id: str = ""
    correlation_type: CorrelationType = CorrelationType.INDEPENDENT
    computed_reuse_ratio: float = 0.0
    is_redundant: bool = False
    cross_control_value: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceCorrelationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_reuse_count: float = 0.0
    by_correlation_type: dict[str, int] = Field(default_factory=dict)
    by_evidence_scope: dict[str, int] = Field(default_factory=dict)
    by_correlation_strength: dict[str, int] = Field(default_factory=dict)
    high_value_evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceEvidenceCorrelationEngine:
    """Compute evidence reuse ratio, detect redundant
    collections, rank evidence by cross-control value."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[EvidenceCorrelationRecord] = []
        self._analyses: dict[str, EvidenceCorrelationAnalysis] = {}
        logger.info(
            "compliance_evidence_correlation_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        evidence_id: str = "",
        correlation_type: CorrelationType = CorrelationType.INDEPENDENT,
        evidence_scope: EvidenceScope = EvidenceScope.SINGLE_CONTROL,
        correlation_strength: CorrelationStrength = CorrelationStrength.NONE,
        reuse_count: int = 0,
        control_count: int = 1,
        collection_cost: float = 0.0,
        control_id: str = "",
        description: str = "",
    ) -> EvidenceCorrelationRecord:
        record = EvidenceCorrelationRecord(
            evidence_id=evidence_id,
            correlation_type=correlation_type,
            evidence_scope=evidence_scope,
            correlation_strength=correlation_strength,
            reuse_count=reuse_count,
            control_count=control_count,
            collection_cost=collection_cost,
            control_id=control_id,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_evidence_correlation.record_added",
            record_id=record.id,
            evidence_id=evidence_id,
        )
        return record

    def process(self, key: str) -> EvidenceCorrelationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        reuse_ratio = round(rec.reuse_count / max(rec.control_count, 1), 2)
        is_redundant = rec.correlation_type == CorrelationType.EXACT_MATCH and rec.reuse_count > 1
        cross_value = round(rec.control_count * rec.reuse_count, 2)
        analysis = EvidenceCorrelationAnalysis(
            evidence_id=rec.evidence_id,
            correlation_type=rec.correlation_type,
            computed_reuse_ratio=reuse_ratio,
            is_redundant=is_redundant,
            cross_control_value=cross_value,
            description=f"Evidence {rec.evidence_id} reuse {rec.reuse_count}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> EvidenceCorrelationReport:
        by_ct: dict[str, int] = {}
        by_es: dict[str, int] = {}
        by_cs: dict[str, int] = {}
        reuse_counts: list[float] = []
        for r in self._records:
            k = r.correlation_type.value
            by_ct[k] = by_ct.get(k, 0) + 1
            k2 = r.evidence_scope.value
            by_es[k2] = by_es.get(k2, 0) + 1
            k3 = r.correlation_strength.value
            by_cs[k3] = by_cs.get(k3, 0) + 1
            reuse_counts.append(float(r.reuse_count))
        avg = round(sum(reuse_counts) / len(reuse_counts), 2) if reuse_counts else 0.0
        high_val = list(
            {
                r.evidence_id
                for r in self._records
                if r.evidence_scope in (EvidenceScope.CROSS_FRAMEWORK, EvidenceScope.UNIVERSAL)
            }
        )[:10]
        recs: list[str] = []
        if high_val:
            recs.append(f"{len(high_val)} high-value reusable evidence items found")
        if not recs:
            recs.append("No significant evidence reuse opportunities detected")
        return EvidenceCorrelationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_reuse_count=avg,
            by_correlation_type=by_ct,
            by_evidence_scope=by_es,
            by_correlation_strength=by_cs,
            high_value_evidence=high_val,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ct_dist: dict[str, int] = {}
        for r in self._records:
            k = r.correlation_type.value
            ct_dist[k] = ct_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "correlation_type_distribution": ct_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("compliance_evidence_correlation_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_evidence_reuse_ratio(
        self,
    ) -> list[dict[str, Any]]:
        """Compute reuse ratio per evidence item."""
        evidence_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.evidence_id not in evidence_data:
                evidence_data[r.evidence_id] = {
                    "reuse_count": r.reuse_count,
                    "control_count": r.control_count,
                    "scope": r.evidence_scope.value,
                }
            else:
                evidence_data[r.evidence_id]["reuse_count"] = max(
                    evidence_data[r.evidence_id]["reuse_count"], r.reuse_count
                )
                evidence_data[r.evidence_id]["control_count"] = max(
                    evidence_data[r.evidence_id]["control_count"], r.control_count
                )
        results: list[dict[str, Any]] = []
        for eid, data in evidence_data.items():
            ratio = round(data["reuse_count"] / max(data["control_count"], 1), 2)
            results.append(
                {
                    "evidence_id": eid,
                    "evidence_scope": data["scope"],
                    "reuse_ratio": ratio,
                    "reuse_count": data["reuse_count"],
                }
            )
        results.sort(key=lambda x: x["reuse_ratio"], reverse=True)
        return results

    def detect_redundant_collections(
        self,
    ) -> list[dict[str, Any]]:
        """Detect redundant evidence collections."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.correlation_type == CorrelationType.EXACT_MATCH
                and r.reuse_count > 1
                and r.evidence_id not in seen
            ):
                seen.add(r.evidence_id)
                results.append(
                    {
                        "evidence_id": r.evidence_id,
                        "correlation_type": r.correlation_type.value,
                        "reuse_count": r.reuse_count,
                        "collection_cost": r.collection_cost,
                    }
                )
        results.sort(key=lambda x: x["collection_cost"], reverse=True)
        return results

    def rank_evidence_by_cross_control_value(
        self,
    ) -> list[dict[str, Any]]:
        """Rank evidence by cross-control value."""
        evidence_value: dict[str, float] = {}
        evidence_scopes: dict[str, str] = {}
        for r in self._records:
            value = float(r.control_count * r.reuse_count)
            evidence_value[r.evidence_id] = max(evidence_value.get(r.evidence_id, 0.0), value)
            evidence_scopes[r.evidence_id] = r.evidence_scope.value
        results: list[dict[str, Any]] = []
        for eid, value in evidence_value.items():
            results.append(
                {
                    "evidence_id": eid,
                    "evidence_scope": evidence_scopes[eid],
                    "cross_control_value": round(value, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["cross_control_value"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
