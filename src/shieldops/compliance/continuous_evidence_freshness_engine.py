"""Continuous Evidence Freshness Engine
compute evidence freshness scores, detect stale evidence,
rank controls by evidence urgency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FreshnessStatus(StrEnum):
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"
    EXPIRED = "expired"


class EvidenceType(StrEnum):
    AUTOMATED = "automated"
    MANUAL = "manual"
    HYBRID = "hybrid"
    EXTERNAL = "external"


class ControlCategory(StrEnum):
    ACCESS = "access"
    ENCRYPTION = "encryption"
    MONITORING = "monitoring"
    GOVERNANCE = "governance"


# --- Models ---


class EvidenceFreshnessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_id: str = ""
    freshness_status: FreshnessStatus = FreshnessStatus.CURRENT
    evidence_type: EvidenceType = EvidenceType.AUTOMATED
    control_category: ControlCategory = ControlCategory.ACCESS
    freshness_score: float = 0.0
    age_days: float = 0.0
    control_id: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceFreshnessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_id: str = ""
    freshness_status: FreshnessStatus = FreshnessStatus.CURRENT
    computed_score: float = 0.0
    is_stale: bool = False
    urgency_level: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceFreshnessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_freshness_score: float = 0.0
    by_freshness_status: dict[str, int] = Field(default_factory=dict)
    by_evidence_type: dict[str, int] = Field(default_factory=dict)
    by_control_category: dict[str, int] = Field(default_factory=dict)
    stale_evidence_ids: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ContinuousEvidenceFreshnessEngine:
    """Compute evidence freshness scores, detect stale
    evidence, rank controls by evidence urgency."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[EvidenceFreshnessRecord] = []
        self._analyses: dict[str, EvidenceFreshnessAnalysis] = {}
        logger.info(
            "continuous_evidence_freshness_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        evidence_id: str = "",
        freshness_status: FreshnessStatus = FreshnessStatus.CURRENT,
        evidence_type: EvidenceType = EvidenceType.AUTOMATED,
        control_category: ControlCategory = ControlCategory.ACCESS,
        freshness_score: float = 0.0,
        age_days: float = 0.0,
        control_id: str = "",
        description: str = "",
    ) -> EvidenceFreshnessRecord:
        record = EvidenceFreshnessRecord(
            evidence_id=evidence_id,
            freshness_status=freshness_status,
            evidence_type=evidence_type,
            control_category=control_category,
            freshness_score=freshness_score,
            age_days=age_days,
            control_id=control_id,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "continuous_evidence_freshness.record_added",
            record_id=record.id,
            evidence_id=evidence_id,
        )
        return record

    def process(self, key: str) -> EvidenceFreshnessAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_stale = rec.freshness_status in (
            FreshnessStatus.STALE,
            FreshnessStatus.EXPIRED,
        )
        urgency = round(rec.age_days / max(rec.freshness_score, 1.0), 2)
        analysis = EvidenceFreshnessAnalysis(
            evidence_id=rec.evidence_id,
            freshness_status=rec.freshness_status,
            computed_score=round(rec.freshness_score, 2),
            is_stale=is_stale,
            urgency_level=urgency,
            description=f"Evidence {rec.evidence_id} freshness {rec.freshness_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> EvidenceFreshnessReport:
        by_fs: dict[str, int] = {}
        by_et: dict[str, int] = {}
        by_cc: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.freshness_status.value
            by_fs[k] = by_fs.get(k, 0) + 1
            k2 = r.evidence_type.value
            by_et[k2] = by_et.get(k2, 0) + 1
            k3 = r.control_category.value
            by_cc[k3] = by_cc.get(k3, 0) + 1
            scores.append(r.freshness_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        stale = list(
            {
                r.evidence_id
                for r in self._records
                if r.freshness_status in (FreshnessStatus.STALE, FreshnessStatus.EXPIRED)
            }
        )[:10]
        recs: list[str] = []
        if stale:
            recs.append(f"{len(stale)} stale evidence items detected")
        if not recs:
            recs.append("All evidence is current")
        return EvidenceFreshnessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_freshness_score=avg,
            by_freshness_status=by_fs,
            by_evidence_type=by_et,
            by_control_category=by_cc,
            stale_evidence_ids=stale,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        fs_dist: dict[str, int] = {}
        for r in self._records:
            k = r.freshness_status.value
            fs_dist[k] = fs_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "freshness_status_distribution": fs_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("continuous_evidence_freshness_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_evidence_freshness_scores(
        self,
    ) -> list[dict[str, Any]]:
        """Compute freshness score per evidence item."""
        evidence_scores: dict[str, list[float]] = {}
        evidence_types: dict[str, str] = {}
        for r in self._records:
            evidence_scores.setdefault(r.evidence_id, []).append(r.freshness_score)
            evidence_types[r.evidence_id] = r.evidence_type.value
        results: list[dict[str, Any]] = []
        for eid, scores in evidence_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "evidence_id": eid,
                    "evidence_type": evidence_types[eid],
                    "avg_freshness_score": avg,
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_freshness_score"])
        return results

    def detect_stale_evidence(
        self,
    ) -> list[dict[str, Any]]:
        """Detect evidence items that are stale or expired."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.freshness_status in (FreshnessStatus.STALE, FreshnessStatus.EXPIRED)
                and r.evidence_id not in seen
            ):
                seen.add(r.evidence_id)
                results.append(
                    {
                        "evidence_id": r.evidence_id,
                        "freshness_status": r.freshness_status.value,
                        "age_days": r.age_days,
                        "control_id": r.control_id,
                    }
                )
        results.sort(key=lambda x: x["age_days"], reverse=True)
        return results

    def rank_controls_by_evidence_urgency(
        self,
    ) -> list[dict[str, Any]]:
        """Rank controls by urgency of evidence refresh."""
        control_ages: dict[str, list[float]] = {}
        control_cats: dict[str, str] = {}
        for r in self._records:
            control_ages.setdefault(r.control_id, []).append(r.age_days)
            control_cats[r.control_id] = r.control_category.value
        results: list[dict[str, Any]] = []
        for cid, ages in control_ages.items():
            max_age = max(ages)
            avg_age = round(sum(ages) / len(ages), 2)
            results.append(
                {
                    "control_id": cid,
                    "control_category": control_cats[cid],
                    "max_age_days": max_age,
                    "avg_age_days": avg_age,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["max_age_days"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
