"""Investigation Completeness Engine —
verify investigation completeness and thoroughness,
enumerate open gaps, recommend completion actions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CompletenessLevel(StrEnum):
    THOROUGH = "thorough"
    ADEQUATE = "adequate"
    INCOMPLETE = "incomplete"
    SUPERFICIAL = "superficial"


class GapType(StrEnum):
    UNEXPLORED_HYPOTHESIS = "unexplored_hypothesis"
    UNVERIFIED_ASSUMPTION = "unverified_assumption"
    MISSING_DATA = "missing_data"
    UNTESTED_ALTERNATIVE = "untested_alternative"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"


# --- Models ---


class InvestigationCompletenessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    completeness_level: CompletenessLevel = CompletenessLevel.ADEQUATE
    gap_type: GapType = GapType.MISSING_DATA
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    completeness_score: float = 0.0
    open_gap_count: int = 0
    hypothesis_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InvestigationCompletenessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    completeness_level: CompletenessLevel = CompletenessLevel.ADEQUATE
    gap_type: GapType = GapType.MISSING_DATA
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    is_complete: bool = False
    completeness_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InvestigationCompletenessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_completeness_score: float = 0.0
    by_completeness_level: dict[str, int] = Field(default_factory=dict)
    by_gap_type: dict[str, int] = Field(default_factory=dict)
    by_verification_status: dict[str, int] = Field(default_factory=dict)
    incomplete_investigations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class InvestigationCompletenessEngine:
    """Verify investigation completeness and thoroughness,
    enumerate open gaps, recommend completion actions."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[InvestigationCompletenessRecord] = []
        self._analyses: dict[str, InvestigationCompletenessAnalysis] = {}
        logger.info("investigation_completeness_engine.init", max_records=max_records)

    def add_record(
        self,
        investigation_id: str = "",
        completeness_level: CompletenessLevel = CompletenessLevel.ADEQUATE,
        gap_type: GapType = GapType.MISSING_DATA,
        verification_status: VerificationStatus = VerificationStatus.UNVERIFIED,
        completeness_score: float = 0.0,
        open_gap_count: int = 0,
        hypothesis_count: int = 0,
        description: str = "",
    ) -> InvestigationCompletenessRecord:
        record = InvestigationCompletenessRecord(
            investigation_id=investigation_id,
            completeness_level=completeness_level,
            gap_type=gap_type,
            verification_status=verification_status,
            completeness_score=completeness_score,
            open_gap_count=open_gap_count,
            hypothesis_count=hypothesis_count,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "investigation_completeness.record_added",
            record_id=record.id,
            investigation_id=investigation_id,
        )
        return record

    def process(self, key: str) -> InvestigationCompletenessAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_complete = (
            rec.completeness_level
            in (
                CompletenessLevel.THOROUGH,
                CompletenessLevel.ADEQUATE,
            )
            and rec.open_gap_count == 0
        )
        analysis = InvestigationCompletenessAnalysis(
            investigation_id=rec.investigation_id,
            completeness_level=rec.completeness_level,
            gap_type=rec.gap_type,
            verification_status=rec.verification_status,
            is_complete=is_complete,
            completeness_score=round(rec.completeness_score, 4),
            description=(
                f"Investigation {rec.investigation_id} "
                f"level={rec.completeness_level.value} "
                f"gaps={rec.open_gap_count}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> InvestigationCompletenessReport:
        by_cl: dict[str, int] = {}
        by_gt: dict[str, int] = {}
        by_vs: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.completeness_level.value
            by_cl[k] = by_cl.get(k, 0) + 1
            k2 = r.gap_type.value
            by_gt[k2] = by_gt.get(k2, 0) + 1
            k3 = r.verification_status.value
            by_vs[k3] = by_vs.get(k3, 0) + 1
            scores.append(r.completeness_score)
        avg_comp = round(sum(scores) / len(scores), 4) if scores else 0.0
        incomplete: list[str] = list(
            {
                r.investigation_id
                for r in self._records
                if r.completeness_level
                in (
                    CompletenessLevel.INCOMPLETE,
                    CompletenessLevel.SUPERFICIAL,
                )
            }
        )[:10]
        recs: list[str] = []
        superficial = by_cl.get("superficial", 0)
        if superficial:
            recs.append(f"{superficial} superficial investigations need deeper analysis")
        contradicted = by_vs.get("contradicted", 0)
        if contradicted:
            recs.append(f"{contradicted} contradicted findings need re-investigation")
        if not recs:
            recs.append("Investigation completeness is satisfactory")
        return InvestigationCompletenessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_completeness_score=avg_comp,
            by_completeness_level=by_cl,
            by_gap_type=by_gt,
            by_verification_status=by_vs,
            incomplete_investigations=incomplete,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.completeness_level.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "completeness_level_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("investigation_completeness_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def assess_investigation_completeness(self) -> list[dict[str, Any]]:
        """Assess completeness level per investigation."""
        inv_map: dict[str, list[InvestigationCompletenessRecord]] = {}
        for r in self._records:
            inv_map.setdefault(r.investigation_id, []).append(r)
        level_order = {
            "thorough": 4,
            "adequate": 3,
            "incomplete": 2,
            "superficial": 1,
        }
        results: list[dict[str, Any]] = []
        for inv_id, inv_recs in inv_map.items():
            avg_score = sum(r.completeness_score for r in inv_recs) / len(inv_recs)
            worst = min(inv_recs, key=lambda r: level_order.get(r.completeness_level.value, 0))
            total_gaps = sum(r.open_gap_count for r in inv_recs)
            results.append(
                {
                    "investigation_id": inv_id,
                    "avg_completeness_score": round(avg_score, 4),
                    "worst_level": worst.completeness_level.value,
                    "total_open_gaps": total_gaps,
                    "record_count": len(inv_recs),
                }
            )
        results.sort(key=lambda x: x["avg_completeness_score"], reverse=True)
        return results

    def enumerate_open_gaps(self) -> list[dict[str, Any]]:
        """Enumerate all open gaps grouped by type."""
        gap_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            gv = r.gap_type.value
            gap_data.setdefault(gv, {"count": 0, "total_gaps": 0, "investigations": set()})
            gap_data[gv]["count"] += 1
            gap_data[gv]["total_gaps"] += r.open_gap_count
            gap_data[gv]["investigations"].add(r.investigation_id)
        results: list[dict[str, Any]] = []
        for gv, gd in gap_data.items():
            results.append(
                {
                    "gap_type": gv,
                    "record_count": gd["count"],
                    "total_open_gaps": gd["total_gaps"],
                    "affected_investigations": len(gd["investigations"]),
                }
            )
        results.sort(key=lambda x: x["total_open_gaps"], reverse=True)
        return results

    def recommend_completion_actions(self) -> list[dict[str, Any]]:
        """Recommend specific actions to complete each investigation."""
        inv_map: dict[str, list[InvestigationCompletenessRecord]] = {}
        for r in self._records:
            inv_map.setdefault(r.investigation_id, []).append(r)
        action_map = {
            "unexplored_hypothesis": "Explore remaining hypotheses with data gathering",
            "unverified_assumption": "Collect evidence to verify assumptions",
            "missing_data": "Query additional data sources",
            "untested_alternative": "Test alternative root causes",
        }
        results: list[dict[str, Any]] = []
        for inv_id, inv_recs in inv_map.items():
            gaps = list({r.gap_type.value for r in inv_recs if r.open_gap_count > 0})
            actions = [action_map.get(g, "Review investigation scope") for g in gaps]
            avg_score = sum(r.completeness_score for r in inv_recs) / len(inv_recs)
            results.append(
                {
                    "investigation_id": inv_id,
                    "completeness_score": round(avg_score, 4),
                    "open_gap_types": gaps,
                    "recommended_actions": actions,
                }
            )
        results.sort(key=lambda x: x["completeness_score"])
        return results
