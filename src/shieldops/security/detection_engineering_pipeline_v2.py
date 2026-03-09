"""Detection Engineering Pipeline V2
rule lifecycle, testing automation, effectiveness, deployment."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RuleLifecycleStage(StrEnum):
    DRAFT = "draft"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"


class RuleEffectiveness(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNTESTED = "untested"
    DEGRADED = "degraded"


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    SCHEDULED = "scheduled"


# --- Models ---


class RuleRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    lifecycle_stage: RuleLifecycleStage = RuleLifecycleStage.DRAFT
    effectiveness: RuleEffectiveness = RuleEffectiveness.UNTESTED
    deployment_status: DeploymentStatus = DeploymentStatus.PENDING
    true_positive_rate: float = 0.0
    false_positive_rate: float = 0.0
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RuleAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    lifecycle_stage: RuleLifecycleStage = RuleLifecycleStage.DRAFT
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RulePipelineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_effectiveness: float = 0.0
    avg_false_positive_rate: float = 0.0
    by_lifecycle: dict[str, int] = Field(default_factory=dict)
    by_effectiveness: dict[str, int] = Field(default_factory=dict)
    by_deployment: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DetectionEngineeringPipelineV2:
    """Detection rule lifecycle, testing automation, effectiveness scoring
    deployment management."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[RuleRecord] = []
        self._analyses: list[RuleAnalysis] = []
        logger.info(
            "detection_engineering_pipeline_v2.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def add_record(
        self,
        rule_name: str,
        lifecycle_stage: RuleLifecycleStage = RuleLifecycleStage.DRAFT,
        effectiveness: RuleEffectiveness = RuleEffectiveness.UNTESTED,
        deployment_status: DeploymentStatus = DeploymentStatus.PENDING,
        true_positive_rate: float = 0.0,
        false_positive_rate: float = 0.0,
        effectiveness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RuleRecord:
        record = RuleRecord(
            rule_name=rule_name,
            lifecycle_stage=lifecycle_stage,
            effectiveness=effectiveness,
            deployment_status=deployment_status,
            true_positive_rate=true_positive_rate,
            false_positive_rate=false_positive_rate,
            effectiveness_score=effectiveness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "detection_engineering_pipeline_v2.record_added",
            record_id=record.id,
            rule_name=rule_name,
            lifecycle_stage=lifecycle_stage.value,
        )
        return record

    def get_record(self, record_id: str) -> RuleRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        lifecycle_stage: RuleLifecycleStage | None = None,
        effectiveness: RuleEffectiveness | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RuleRecord]:
        results = list(self._records)
        if lifecycle_stage is not None:
            results = [r for r in results if r.lifecycle_stage == lifecycle_stage]
        if effectiveness is not None:
            results = [r for r in results if r.effectiveness == effectiveness]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        rule_name: str,
        lifecycle_stage: RuleLifecycleStage = RuleLifecycleStage.DRAFT,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RuleAnalysis:
        analysis = RuleAnalysis(
            rule_name=rule_name,
            lifecycle_stage=lifecycle_stage,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "detection_engineering_pipeline_v2.analysis_added",
            rule_name=rule_name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def compute_effectiveness_metrics(self) -> dict[str, Any]:
        if not self._records:
            return {"avg_tp_rate": 0.0, "avg_fp_rate": 0.0, "rule_count": 0}
        tp_rates = [r.true_positive_rate for r in self._records]
        fp_rates = [r.false_positive_rate for r in self._records]
        high_fp = [r for r in self._records if r.false_positive_rate > 30.0]
        return {
            "avg_tp_rate": round(sum(tp_rates) / len(tp_rates), 2),
            "avg_fp_rate": round(sum(fp_rates) / len(fp_rates), 2),
            "rule_count": len(self._records),
            "high_fp_rules": len(high_fp),
            "production_rules": sum(
                1 for r in self._records if r.lifecycle_stage == RuleLifecycleStage.PRODUCTION
            ),
        }

    def identify_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "rule_name": r.rule_name,
                        "lifecycle_stage": r.lifecycle_stage.value,
                        "effectiveness_score": r.effectiveness_score,
                        "false_positive_rate": r.false_positive_rate,
                        "service": r.service,
                    }
                )
        return sorted(results, key=lambda x: x["effectiveness_score"])

    def compute_deployment_readiness(self) -> list[dict[str, Any]]:
        staging = [r for r in self._records if r.lifecycle_stage == RuleLifecycleStage.STAGING]
        results: list[dict[str, Any]] = []
        for r in staging:
            ready = (
                r.effectiveness_score >= self._threshold
                and r.false_positive_rate < 20.0
                and r.true_positive_rate > 70.0
            )
            results.append(
                {
                    "rule_name": r.rule_name,
                    "ready_for_production": ready,
                    "effectiveness_score": r.effectiveness_score,
                    "true_positive_rate": r.true_positive_rate,
                    "false_positive_rate": r.false_positive_rate,
                }
            )
        return sorted(results, key=lambda x: x["effectiveness_score"], reverse=True)

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
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

    def process(self, rule_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.rule_name == rule_name]
        if not matching:
            return {"rule_name": rule_name, "status": "no_data"}
        scores = [r.effectiveness_score for r in matching]
        fp_rates = [r.false_positive_rate for r in matching]
        return {
            "rule_name": rule_name,
            "versions": len(matching),
            "avg_effectiveness": round(sum(scores) / len(scores), 2),
            "avg_false_positive_rate": round(sum(fp_rates) / len(fp_rates), 2),
            "latest_stage": matching[-1].lifecycle_stage.value,
        }

    def generate_report(self) -> RulePipelineReport:
        by_lc: dict[str, int] = {}
        by_eff: dict[str, int] = {}
        by_dep: dict[str, int] = {}
        for r in self._records:
            by_lc[r.lifecycle_stage.value] = by_lc.get(r.lifecycle_stage.value, 0) + 1
            by_eff[r.effectiveness.value] = by_eff.get(r.effectiveness.value, 0) + 1
            by_dep[r.deployment_status.value] = by_dep.get(r.deployment_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.effectiveness_score < self._threshold)
        scores = [r.effectiveness_score for r in self._records]
        avg_eff = round(sum(scores) / len(scores), 2) if scores else 0.0
        fp_rates = [r.false_positive_rate for r in self._records]
        avg_fp = round(sum(fp_rates) / len(fp_rates), 2) if fp_rates else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [g["rule_name"] for g in gap_list[:5]]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(f"{gap_count} rule(s) below effectiveness threshold ({self._threshold})")
        if avg_fp > 25.0:
            recs.append(f"Average false positive rate {avg_fp}% is high — tune noisy rules")
        if avg_eff < self._threshold:
            recs.append(f"Avg effectiveness {avg_eff} below threshold ({self._threshold})")
        if not recs:
            recs.append("Detection engineering pipeline V2 is healthy")
        return RulePipelineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_effectiveness=avg_eff,
            avg_false_positive_rate=avg_fp,
            by_lifecycle=by_lc,
            by_effectiveness=by_eff,
            by_deployment=by_dep,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        lc_dist: dict[str, int] = {}
        for r in self._records:
            key = r.lifecycle_stage.value
            lc_dist[key] = lc_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "lifecycle_distribution": lc_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("detection_engineering_pipeline_v2.cleared")
        return {"status": "cleared"}
