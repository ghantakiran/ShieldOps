"""Compliance Violation Predictor
predict violation risk, identify control weaknesses,
recommend preventive actions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplianceFramework(StrEnum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"


class ViolationLikelihood(StrEnum):
    CERTAIN = "certain"
    LIKELY = "likely"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"


class ControlGap(StrEnum):
    MISSING = "missing"
    WEAK = "weak"
    PARTIAL = "partial"
    STRONG = "strong"


# --- Models ---


class ViolationPredictorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    framework: ComplianceFramework = ComplianceFramework.SOC2
    likelihood: ViolationLikelihood = ViolationLikelihood.POSSIBLE
    gap: ControlGap = ControlGap.PARTIAL
    risk_score: float = 0.0
    control_effectiveness: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ViolationPredictorAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str = ""
    framework: ComplianceFramework = ComplianceFramework.SOC2
    analysis_score: float = 0.0
    violation_probability: float = 0.0
    preventive_actions: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ViolationPredictorReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    avg_effectiveness: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_likelihood: dict[str, int] = Field(default_factory=dict)
    by_gap: dict[str, int] = Field(default_factory=dict)
    high_risk_controls: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceViolationPredictor:
    """Predict violation risk, identify control
    weaknesses, recommend preventive actions."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._records: list[ViolationPredictorRecord] = []
        self._analyses: list[ViolationPredictorAnalysis] = []
        logger.info(
            "compliance_violation_predictor.init",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    def add_record(
        self,
        control_id: str,
        framework: ComplianceFramework = (ComplianceFramework.SOC2),
        likelihood: ViolationLikelihood = (ViolationLikelihood.POSSIBLE),
        gap: ControlGap = ControlGap.PARTIAL,
        risk_score: float = 0.0,
        control_effectiveness: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ViolationPredictorRecord:
        record = ViolationPredictorRecord(
            control_id=control_id,
            framework=framework,
            likelihood=likelihood,
            gap=gap,
            risk_score=risk_score,
            control_effectiveness=(control_effectiveness),
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "compliance_violation_predictor.added",
            record_id=record.id,
            control_id=control_id,
        )
        return record

    def process(self, key: str) -> ViolationPredictorAnalysis | None:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return None
        likelihood_w = {
            "certain": 1.0,
            "likely": 0.75,
            "possible": 0.5,
            "unlikely": 0.25,
        }
        prob = likelihood_w.get(rec.likelihood.value, 0.5)
        score = round(rec.risk_score * prob, 2)
        actions = 3 if rec.gap in (ControlGap.MISSING, ControlGap.WEAK) else 1
        analysis = ViolationPredictorAnalysis(
            control_id=rec.control_id,
            framework=rec.framework,
            analysis_score=score,
            violation_probability=prob,
            preventive_actions=actions,
            description=(f"Control {rec.control_id} violation prob {prob:.0%}"),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return analysis

    def generate_report(
        self,
    ) -> ViolationPredictorReport:
        by_fw: dict[str, int] = {}
        by_lk: dict[str, int] = {}
        by_gp: dict[str, int] = {}
        risks: list[float] = []
        effs: list[float] = []
        for r in self._records:
            f = r.framework.value
            by_fw[f] = by_fw.get(f, 0) + 1
            lk = r.likelihood.value
            by_lk[lk] = by_lk.get(lk, 0) + 1
            g = r.gap.value
            by_gp[g] = by_gp.get(g, 0) + 1
            risks.append(r.risk_score)
            effs.append(r.control_effectiveness)
        avg_r = round(sum(risks) / len(risks), 2) if risks else 0.0
        avg_e = round(sum(effs) / len(effs), 2) if effs else 0.0
        high_risk = [r.control_id for r in self._records if r.risk_score >= self._risk_threshold][
            :5
        ]
        recs: list[str] = []
        if high_risk:
            recs.append(f"{len(high_risk)} controls above risk threshold")
        if not recs:
            recs.append("Compliance risk is acceptable")
        return ViolationPredictorReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg_r,
            avg_effectiveness=avg_e,
            by_framework=by_fw,
            by_likelihood=by_lk,
            by_gap=by_gp,
            high_risk_controls=high_risk,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        fw_dist: dict[str, int] = {}
        for r in self._records:
            k = r.framework.value
            fw_dist[k] = fw_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_threshold": self._risk_threshold,
            "framework_distribution": fw_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("compliance_violation_predictor.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def predict_violation_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Predict violation risk per framework."""
        fw_data: dict[str, list[float]] = {}
        for r in self._records:
            k = r.framework.value
            fw_data.setdefault(k, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for fw, scores in fw_data.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "framework": fw,
                    "avg_risk_score": avg,
                    "max_risk_score": round(max(scores), 2),
                    "count": len(scores),
                    "high_risk": avg >= self._risk_threshold,
                }
            )
        results.sort(
            key=lambda x: x["avg_risk_score"],
            reverse=True,
        )
        return results

    def identify_control_weaknesses(
        self,
    ) -> list[dict[str, Any]]:
        """Identify weak or missing controls."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.gap in (
                ControlGap.MISSING,
                ControlGap.WEAK,
            ):
                results.append(
                    {
                        "control_id": r.control_id,
                        "framework": r.framework.value,
                        "gap": r.gap.value,
                        "risk_score": r.risk_score,
                        "effectiveness": (r.control_effectiveness),
                    }
                )
        results.sort(
            key=lambda x: x["risk_score"],
            reverse=True,
        )
        return results

    def recommend_preventive_actions(
        self,
    ) -> dict[str, Any]:
        """Recommend actions per gap type."""
        if not self._records:
            return {
                "total_actions": 0,
                "by_gap": {},
            }
        gap_counts: dict[str, int] = {}
        gap_risks: dict[str, list[float]] = {}
        for r in self._records:
            k = r.gap.value
            gap_counts[k] = gap_counts.get(k, 0) + 1
            gap_risks.setdefault(k, []).append(r.risk_score)
        by_gap: dict[str, dict[str, Any]] = {}
        total = 0
        action_map = {
            "missing": 3,
            "weak": 2,
            "partial": 1,
            "strong": 0,
        }
        for g, cnt in gap_counts.items():
            actions = action_map.get(g, 1) * cnt
            total += actions
            avg_r = round(
                sum(gap_risks[g]) / len(gap_risks[g]),
                2,
            )
            by_gap[g] = {
                "count": cnt,
                "recommended_actions": actions,
                "avg_risk": avg_r,
            }
        return {
            "total_actions": total,
            "by_gap": by_gap,
        }
