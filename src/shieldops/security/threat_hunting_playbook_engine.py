"""Threat Hunting Playbook Engine
generate hunt hypotheses, evaluate playbook coverage,
score hunt effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HuntType(StrEnum):
    HYPOTHESIS_DRIVEN = "hypothesis_driven"
    INDICATOR_BASED = "indicator_based"
    BEHAVIORAL = "behavioral"
    AUTOMATED = "automated"


class PlaybookMaturity(StrEnum):
    DRAFT = "draft"
    TESTED = "tested"
    VALIDATED = "validated"
    PRODUCTION = "production"


class HuntOutcome(StrEnum):
    CONFIRMED = "confirmed"
    SUSPICIOUS = "suspicious"
    BENIGN = "benign"
    INCONCLUSIVE = "inconclusive"


# --- Models ---


class HuntPlaybookRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hunt_id: str = ""
    hunt_type: HuntType = HuntType.HYPOTHESIS_DRIVEN
    maturity: PlaybookMaturity = PlaybookMaturity.DRAFT
    outcome: HuntOutcome = HuntOutcome.INCONCLUSIVE
    effectiveness_score: float = 0.0
    coverage_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class HuntPlaybookAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hunt_id: str = ""
    hunt_type: HuntType = HuntType.HYPOTHESIS_DRIVEN
    analysis_score: float = 0.0
    hypothesis_strength: float = 0.0
    coverage_gap: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class HuntPlaybookReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_effectiveness: float = 0.0
    avg_coverage: float = 0.0
    by_hunt_type: dict[str, int] = Field(default_factory=dict)
    by_maturity: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    low_coverage_hunts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatHuntingPlaybookEngine:
    """Generate hunt hypotheses, evaluate playbook
    coverage, score hunt effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        coverage_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._coverage_threshold = coverage_threshold
        self._records: list[HuntPlaybookRecord] = []
        self._analyses: list[HuntPlaybookAnalysis] = []
        logger.info(
            "threat_hunting_playbook_engine.init",
            max_records=max_records,
            coverage_threshold=coverage_threshold,
        )

    def add_record(
        self,
        hunt_id: str,
        hunt_type: HuntType = (HuntType.HYPOTHESIS_DRIVEN),
        maturity: PlaybookMaturity = (PlaybookMaturity.DRAFT),
        outcome: HuntOutcome = (HuntOutcome.INCONCLUSIVE),
        effectiveness_score: float = 0.0,
        coverage_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> HuntPlaybookRecord:
        record = HuntPlaybookRecord(
            hunt_id=hunt_id,
            hunt_type=hunt_type,
            maturity=maturity,
            outcome=outcome,
            effectiveness_score=effectiveness_score,
            coverage_pct=coverage_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_hunting_playbook.record_added",
            record_id=record.id,
            hunt_id=hunt_id,
        )
        return record

    def process(self, key: str) -> HuntPlaybookAnalysis | None:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return None
        score = (
            round(
                rec.effectiveness_score * (rec.coverage_pct / 100.0),
                2,
            )
            if rec.coverage_pct > 0
            else 0.0
        )
        gap = round(
            max(
                0,
                self._coverage_threshold - rec.coverage_pct,
            ),
            2,
        )
        analysis = HuntPlaybookAnalysis(
            hunt_id=rec.hunt_id,
            hunt_type=rec.hunt_type,
            analysis_score=score,
            hypothesis_strength=round(rec.effectiveness_score, 2),
            coverage_gap=gap,
            description=(f"Hunt {rec.hunt_id} score {score}"),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return analysis

    def generate_report(self) -> HuntPlaybookReport:
        by_ht: dict[str, int] = {}
        by_mat: dict[str, int] = {}
        by_out: dict[str, int] = {}
        effs: list[float] = []
        covs: list[float] = []
        for r in self._records:
            h = r.hunt_type.value
            by_ht[h] = by_ht.get(h, 0) + 1
            m = r.maturity.value
            by_mat[m] = by_mat.get(m, 0) + 1
            o = r.outcome.value
            by_out[o] = by_out.get(o, 0) + 1
            effs.append(r.effectiveness_score)
            covs.append(r.coverage_pct)
        avg_e = round(sum(effs) / len(effs), 2) if effs else 0.0
        avg_c = round(sum(covs) / len(covs), 2) if covs else 0.0
        low_cov = [r.hunt_id for r in self._records if r.coverage_pct < self._coverage_threshold][
            :5
        ]
        recs: list[str] = []
        if low_cov:
            recs.append(f"{len(low_cov)} hunts below coverage threshold")
        if not recs:
            recs.append("Hunt coverage is adequate")
        return HuntPlaybookReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_effectiveness=avg_e,
            avg_coverage=avg_c,
            by_hunt_type=by_ht,
            by_maturity=by_mat,
            by_outcome=by_out,
            low_coverage_hunts=low_cov,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ht_dist: dict[str, int] = {}
        for r in self._records:
            k = r.hunt_type.value
            ht_dist[k] = ht_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "coverage_threshold": (self._coverage_threshold),
            "hunt_type_distribution": ht_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("threat_hunting_playbook_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def generate_hunt_hypothesis(
        self,
    ) -> list[dict[str, Any]]:
        """Generate hunt hypotheses by type."""
        type_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            k = r.hunt_type.value
            type_data.setdefault(k, []).append(
                {
                    "hunt_id": r.hunt_id,
                    "maturity": r.maturity.value,
                    "outcome": r.outcome.value,
                    "effectiveness": (r.effectiveness_score),
                }
            )
        results: list[dict[str, Any]] = []
        for ht, items in type_data.items():
            avg_eff = round(
                sum(i["effectiveness"] for i in items) / len(items),
                2,
            )
            results.append(
                {
                    "hunt_type": ht,
                    "hypothesis_count": len(items),
                    "avg_effectiveness": avg_eff,
                    "hypotheses": items[:10],
                }
            )
        return results

    def evaluate_playbook_coverage(
        self,
    ) -> dict[str, Any]:
        """Evaluate playbook coverage by maturity."""
        if not self._records:
            return {
                "overall_coverage": 0.0,
                "by_maturity": {},
            }
        mat_covs: dict[str, list[float]] = {}
        for r in self._records:
            k = r.maturity.value
            mat_covs.setdefault(k, []).append(r.coverage_pct)
        by_mat: dict[str, float] = {}
        for m, vals in mat_covs.items():
            by_mat[m] = round(sum(vals) / len(vals), 2)
        all_c = [r.coverage_pct for r in self._records]
        return {
            "overall_coverage": round(sum(all_c) / len(all_c), 2),
            "by_maturity": by_mat,
        }

    def score_hunt_effectiveness(
        self,
    ) -> dict[str, Any]:
        """Score hunt effectiveness by outcome."""
        if not self._records:
            return {
                "overall_effectiveness": 0.0,
                "by_outcome": {},
            }
        out_scores: dict[str, list[float]] = {}
        for r in self._records:
            k = r.outcome.value
            out_scores.setdefault(k, []).append(r.effectiveness_score)
        by_out: dict[str, float] = {}
        for o, vals in out_scores.items():
            by_out[o] = round(sum(vals) / len(vals), 2)
        all_e = [r.effectiveness_score for r in self._records]
        return {
            "overall_effectiveness": round(sum(all_e) / len(all_e), 2),
            "by_outcome": by_out,
        }
