"""Policy as Code Effectiveness Scorer
score policy coverage, detect blind spots,
rank policies by enforcement effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PolicyLanguage(StrEnum):
    REGO = "rego"
    SENTINEL = "sentinel"
    CUE = "cue"
    CUSTOM = "custom"


class CoverageLevel(StrEnum):
    COMPREHENSIVE = "comprehensive"
    ADEQUATE = "adequate"
    PARTIAL = "partial"
    MINIMAL = "minimal"


class EnforcementMode(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"
    AUDIT = "audit"
    DISABLED = "disabled"


# --- Models ---


class PolicyEffectivenessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    policy_name: str = ""
    policy_language: PolicyLanguage = PolicyLanguage.REGO
    coverage_level: CoverageLevel = CoverageLevel.PARTIAL
    enforcement_mode: EnforcementMode = EnforcementMode.AUDIT
    effectiveness_score: float = 0.0
    violations_caught: int = 0
    violations_missed: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyEffectivenessAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    computed_score: float = 0.0
    coverage_level: CoverageLevel = CoverageLevel.PARTIAL
    catch_rate: float = 0.0
    blind_spot_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PolicyEffectivenessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_effectiveness: float = 0.0
    by_policy_language: dict[str, int] = Field(default_factory=dict)
    by_coverage_level: dict[str, int] = Field(default_factory=dict)
    by_enforcement_mode: dict[str, int] = Field(default_factory=dict)
    top_policies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PolicyAsCodeEffectivenessScorer:
    """Score policy coverage, detect blind spots,
    rank policies by enforcement effectiveness."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[PolicyEffectivenessRecord] = []
        self._analyses: dict[str, PolicyEffectivenessAnalysis] = {}
        logger.info(
            "policy_as_code_effectiveness_scorer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        policy_id: str = "",
        policy_name: str = "",
        policy_language: PolicyLanguage = (PolicyLanguage.REGO),
        coverage_level: CoverageLevel = (CoverageLevel.PARTIAL),
        enforcement_mode: EnforcementMode = (EnforcementMode.AUDIT),
        effectiveness_score: float = 0.0,
        violations_caught: int = 0,
        violations_missed: int = 0,
        description: str = "",
    ) -> PolicyEffectivenessRecord:
        record = PolicyEffectivenessRecord(
            policy_id=policy_id,
            policy_name=policy_name,
            policy_language=policy_language,
            coverage_level=coverage_level,
            enforcement_mode=enforcement_mode,
            effectiveness_score=effectiveness_score,
            violations_caught=violations_caught,
            violations_missed=violations_missed,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "policy_effectiveness.record_added",
            record_id=record.id,
            policy_id=policy_id,
        )
        return record

    def process(self, key: str) -> PolicyEffectivenessAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        total = rec.violations_caught + rec.violations_missed
        catch_rate = round(rec.violations_caught / total, 2) if total > 0 else 0.0
        analysis = PolicyEffectivenessAnalysis(
            policy_id=rec.policy_id,
            computed_score=round(rec.effectiveness_score, 2),
            coverage_level=rec.coverage_level,
            catch_rate=catch_rate,
            blind_spot_count=rec.violations_missed,
            description=(f"Policy {rec.policy_id} score {rec.effectiveness_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> PolicyEffectivenessReport:
        by_pl: dict[str, int] = {}
        by_cl: dict[str, int] = {}
        by_em: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.policy_language.value
            by_pl[k] = by_pl.get(k, 0) + 1
            k2 = r.coverage_level.value
            by_cl[k2] = by_cl.get(k2, 0) + 1
            k3 = r.enforcement_mode.value
            by_em[k3] = by_em.get(k3, 0) + 1
            scores.append(r.effectiveness_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        top = list(
            {
                r.policy_id
                for r in self._records
                if r.coverage_level
                in (
                    CoverageLevel.COMPREHENSIVE,
                    CoverageLevel.ADEQUATE,
                )
            }
        )[:10]
        recs: list[str] = []
        if top:
            recs.append(f"{len(top)} effective policies found")
        if not recs:
            recs.append("No effective policies found")
        return PolicyEffectivenessReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_effectiveness=avg,
            by_policy_language=by_pl,
            by_coverage_level=by_cl,
            by_enforcement_mode=by_em,
            top_policies=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        pl_dist: dict[str, int] = {}
        for r in self._records:
            k = r.policy_language.value
            pl_dist[k] = pl_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "policy_language_distribution": pl_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("policy_as_code_effectiveness.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def score_policy_coverage(
        self,
    ) -> list[dict[str, Any]]:
        """Score coverage per policy."""
        policy_data: dict[str, list[float]] = {}
        for r in self._records:
            policy_data.setdefault(r.policy_id, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for pid, scores in policy_data.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "policy_id": pid,
                    "avg_effectiveness": avg,
                    "evaluation_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["avg_effectiveness"],
            reverse=True,
        )
        return results

    def detect_policy_blind_spots(
        self,
    ) -> list[dict[str, Any]]:
        """Detect policies with high miss rates."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.violations_missed > 0 and r.policy_id not in seen:
                seen.add(r.policy_id)
                total = r.violations_caught + r.violations_missed
                miss_rate = round(r.violations_missed / total, 2) if total > 0 else 0.0
                results.append(
                    {
                        "policy_id": r.policy_id,
                        "violations_missed": (r.violations_missed),
                        "miss_rate": miss_rate,
                        "coverage_level": (r.coverage_level.value),
                    }
                )
        results.sort(
            key=lambda x: x["miss_rate"],
            reverse=True,
        )
        return results

    def rank_policies_by_enforcement_effectiveness(
        self,
    ) -> list[dict[str, Any]]:
        """Rank policies by enforcement effectiveness."""
        policy_scores: dict[str, float] = {}
        for r in self._records:
            policy_scores[r.policy_id] = policy_scores.get(r.policy_id, 0.0) + r.effectiveness_score
        results: list[dict[str, Any]] = []
        for pid, total in policy_scores.items():
            results.append(
                {
                    "policy_id": pid,
                    "aggregate_score": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["aggregate_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
