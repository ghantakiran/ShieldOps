"""Audit Scope Coverage Engine
compute scope coverage ratio, detect untested controls,
rank audit cycles by thoroughness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CoverageLevel(StrEnum):
    COMPLETE = "complete"
    SUBSTANTIAL = "substantial"
    PARTIAL = "partial"
    MINIMAL = "minimal"


class AuditType(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    REGULATORY = "regulatory"
    CERTIFICATION = "certification"


class ScopeArea(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    DATA = "data"
    PROCESS = "process"


# --- Models ---


class AuditScopeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_id: str = ""
    coverage_level: CoverageLevel = CoverageLevel.PARTIAL
    audit_type: AuditType = AuditType.INTERNAL
    scope_area: ScopeArea = ScopeArea.INFRASTRUCTURE
    coverage_ratio: float = 0.0
    total_controls: int = 0
    tested_controls: int = 0
    control_id: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditScopeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_id: str = ""
    coverage_level: CoverageLevel = CoverageLevel.PARTIAL
    computed_ratio: float = 0.0
    untested_count: int = 0
    thoroughness_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditScopeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_coverage_ratio: float = 0.0
    by_coverage_level: dict[str, int] = Field(default_factory=dict)
    by_audit_type: dict[str, int] = Field(default_factory=dict)
    by_scope_area: dict[str, int] = Field(default_factory=dict)
    low_coverage_audits: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditScopeCoverageEngine:
    """Compute scope coverage ratio, detect untested
    controls, rank audit cycles by thoroughness."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AuditScopeRecord] = []
        self._analyses: dict[str, AuditScopeAnalysis] = {}
        logger.info(
            "audit_scope_coverage_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        audit_id: str = "",
        coverage_level: CoverageLevel = CoverageLevel.PARTIAL,
        audit_type: AuditType = AuditType.INTERNAL,
        scope_area: ScopeArea = ScopeArea.INFRASTRUCTURE,
        coverage_ratio: float = 0.0,
        total_controls: int = 0,
        tested_controls: int = 0,
        control_id: str = "",
        description: str = "",
    ) -> AuditScopeRecord:
        record = AuditScopeRecord(
            audit_id=audit_id,
            coverage_level=coverage_level,
            audit_type=audit_type,
            scope_area=scope_area,
            coverage_ratio=coverage_ratio,
            total_controls=total_controls,
            tested_controls=tested_controls,
            control_id=control_id,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_scope_coverage.record_added",
            record_id=record.id,
            audit_id=audit_id,
        )
        return record

    def process(self, key: str) -> AuditScopeAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        untested = rec.total_controls - rec.tested_controls
        thoroughness = round(rec.tested_controls / max(rec.total_controls, 1) * 100, 2)
        analysis = AuditScopeAnalysis(
            audit_id=rec.audit_id,
            coverage_level=rec.coverage_level,
            computed_ratio=round(rec.coverage_ratio, 2),
            untested_count=untested,
            thoroughness_score=thoroughness,
            description=f"Audit {rec.audit_id} coverage {rec.coverage_ratio}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AuditScopeReport:
        by_cl: dict[str, int] = {}
        by_at: dict[str, int] = {}
        by_sa: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.coverage_level.value
            by_cl[k] = by_cl.get(k, 0) + 1
            k2 = r.audit_type.value
            by_at[k2] = by_at.get(k2, 0) + 1
            k3 = r.scope_area.value
            by_sa[k3] = by_sa.get(k3, 0) + 1
            scores.append(r.coverage_ratio)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_cov = list(
            {
                r.audit_id
                for r in self._records
                if r.coverage_level in (CoverageLevel.PARTIAL, CoverageLevel.MINIMAL)
            }
        )[:10]
        recs: list[str] = []
        if low_cov:
            recs.append(f"{len(low_cov)} audits with low coverage detected")
        if not recs:
            recs.append("All audits have adequate coverage")
        return AuditScopeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_coverage_ratio=avg,
            by_coverage_level=by_cl,
            by_audit_type=by_at,
            by_scope_area=by_sa,
            low_coverage_audits=low_cov,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cl_dist: dict[str, int] = {}
        for r in self._records:
            k = r.coverage_level.value
            cl_dist[k] = cl_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "coverage_level_distribution": cl_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("audit_scope_coverage_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_scope_coverage_ratio(
        self,
    ) -> list[dict[str, Any]]:
        """Compute coverage ratio per audit."""
        audit_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.audit_id not in audit_data:
                audit_data[r.audit_id] = {
                    "total": r.total_controls,
                    "tested": r.tested_controls,
                    "audit_type": r.audit_type.value,
                }
            else:
                audit_data[r.audit_id]["total"] += r.total_controls
                audit_data[r.audit_id]["tested"] += r.tested_controls
        results: list[dict[str, Any]] = []
        for aid, data in audit_data.items():
            ratio = round(data["tested"] / max(data["total"], 1) * 100, 2)
            results.append(
                {
                    "audit_id": aid,
                    "audit_type": data["audit_type"],
                    "coverage_ratio": ratio,
                    "total_controls": data["total"],
                    "tested_controls": data["tested"],
                }
            )
        results.sort(key=lambda x: x["coverage_ratio"])
        return results

    def detect_untested_controls(
        self,
    ) -> list[dict[str, Any]]:
        """Detect controls that have not been tested."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.tested_controls == 0 and r.control_id not in seen:
                seen.add(r.control_id)
                results.append(
                    {
                        "control_id": r.control_id,
                        "audit_id": r.audit_id,
                        "scope_area": r.scope_area.value,
                        "total_controls": r.total_controls,
                    }
                )
        results.sort(key=lambda x: x["total_controls"], reverse=True)
        return results

    def rank_audit_cycles_by_thoroughness(
        self,
    ) -> list[dict[str, Any]]:
        """Rank audit cycles by thoroughness score."""
        audit_ratios: dict[str, list[float]] = {}
        audit_types: dict[str, str] = {}
        for r in self._records:
            ratio = r.tested_controls / max(r.total_controls, 1) * 100
            audit_ratios.setdefault(r.audit_id, []).append(ratio)
            audit_types[r.audit_id] = r.audit_type.value
        results: list[dict[str, Any]] = []
        for aid, ratios in audit_ratios.items():
            avg = round(sum(ratios) / len(ratios), 2)
            results.append(
                {
                    "audit_id": aid,
                    "audit_type": audit_types[aid],
                    "thoroughness_score": avg,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["thoroughness_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
