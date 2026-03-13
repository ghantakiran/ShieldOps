"""Format Compliance Reward Engine —
structural rewards for agent output format adherence,
scores compliance, identifies violations, computes reward impact."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FormatStandard(StrEnum):
    STRUCTURED_JSON = "structured_json"
    MITRE_MAPPED = "mitre_mapped"
    STIX_COMPLIANT = "stix_compliant"
    CUSTOM_TEMPLATE = "custom_template"


class ComplianceLevel(StrEnum):
    FULL_COMPLIANCE = "full_compliance"
    MINOR_DEVIATION = "minor_deviation"
    MAJOR_DEVIATION = "major_deviation"
    NON_COMPLIANT = "non_compliant"


class RewardComponent(StrEnum):
    STRUCTURE = "structure"
    COMPLETENESS = "completeness"
    CORRECTNESS = "correctness"
    PARSABILITY = "parsability"


# --- Models ---


class FormatComplianceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    format_standard: FormatStandard = FormatStandard.STRUCTURED_JSON
    compliance_level: ComplianceLevel = ComplianceLevel.FULL_COMPLIANCE
    reward_component: RewardComponent = RewardComponent.STRUCTURE
    compliance_score: float = 0.0
    reward_value: float = 0.0
    violation_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FormatComplianceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    format_standard: FormatStandard = FormatStandard.STRUCTURED_JSON
    compliance_level: ComplianceLevel = ComplianceLevel.FULL_COMPLIANCE
    total_reward: float = 0.0
    penalty_applied: float = 0.0
    net_reward: float = 0.0
    is_passing: bool = True
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FormatComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_compliance_score: float = 0.0
    by_format_standard: dict[str, int] = Field(default_factory=dict)
    by_compliance_level: dict[str, int] = Field(default_factory=dict)
    by_reward_component: dict[str, int] = Field(default_factory=dict)
    non_compliant_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class FormatComplianceRewardEngine:
    """Structural rewards for agent output format adherence."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[FormatComplianceRecord] = []
        self._analyses: dict[str, FormatComplianceAnalysis] = {}
        logger.info(
            "format_compliance_reward_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        format_standard: FormatStandard = FormatStandard.STRUCTURED_JSON,
        compliance_level: ComplianceLevel = ComplianceLevel.FULL_COMPLIANCE,
        reward_component: RewardComponent = RewardComponent.STRUCTURE,
        compliance_score: float = 0.0,
        reward_value: float = 0.0,
        violation_count: int = 0,
        description: str = "",
    ) -> FormatComplianceRecord:
        record = FormatComplianceRecord(
            agent_id=agent_id,
            format_standard=format_standard,
            compliance_level=compliance_level,
            reward_component=reward_component,
            compliance_score=compliance_score,
            reward_value=reward_value,
            violation_count=violation_count,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "format_compliance_reward.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> FormatComplianceAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        penalty_map = {
            ComplianceLevel.FULL_COMPLIANCE: 0.0,
            ComplianceLevel.MINOR_DEVIATION: 0.1,
            ComplianceLevel.MAJOR_DEVIATION: 0.4,
            ComplianceLevel.NON_COMPLIANT: 1.0,
        }
        penalty = penalty_map.get(rec.compliance_level, 0.0) * rec.reward_value
        net = round(rec.reward_value - penalty, 4)
        analysis = FormatComplianceAnalysis(
            agent_id=rec.agent_id,
            format_standard=rec.format_standard,
            compliance_level=rec.compliance_level,
            total_reward=round(rec.reward_value, 4),
            penalty_applied=round(penalty, 4),
            net_reward=net,
            is_passing=rec.compliance_level
            in (ComplianceLevel.FULL_COMPLIANCE, ComplianceLevel.MINOR_DEVIATION),
            description=(f"Agent {rec.agent_id} net reward {net:.4f} after penalty {penalty:.4f}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> FormatComplianceReport:
        by_fs: dict[str, int] = {}
        by_cl: dict[str, int] = {}
        by_rc: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.format_standard.value
            by_fs[k] = by_fs.get(k, 0) + 1
            k2 = r.compliance_level.value
            by_cl[k2] = by_cl.get(k2, 0) + 1
            k3 = r.reward_component.value
            by_rc[k3] = by_rc.get(k3, 0) + 1
            scores.append(r.compliance_score)
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        non_compliant = list(
            {
                r.agent_id
                for r in self._records
                if r.compliance_level == ComplianceLevel.NON_COMPLIANT
            }
        )[:10]
        recs_list: list[str] = []
        if non_compliant:
            recs_list.append(f"{len(non_compliant)} agents producing non-compliant output")
        if not recs_list:
            recs_list.append("Format compliance within acceptable bounds")
        return FormatComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_compliance_score=avg_score,
            by_format_standard=by_fs,
            by_compliance_level=by_cl,
            by_reward_component=by_rc,
            non_compliant_agents=non_compliant,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            k = r.compliance_level.value
            level_dist[k] = level_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "compliance_level_distribution": level_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("format_compliance_reward_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def score_format_compliance(self) -> list[dict[str, Any]]:
        """Score format compliance per agent, aggregated across records."""
        agent_data: dict[str, list[float]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r.compliance_score)
        results: list[dict[str, Any]] = []
        for agent_id, scores in agent_data.items():
            mean_score = sum(scores) / len(scores)
            results.append(
                {
                    "agent_id": agent_id,
                    "mean_compliance_score": round(mean_score, 4),
                    "sample_count": len(scores),
                    "min_score": round(min(scores), 4),
                    "max_score": round(max(scores), 4),
                }
            )
        results.sort(key=lambda x: x["mean_compliance_score"], reverse=True)
        return results

    def identify_format_violations(self) -> list[dict[str, Any]]:
        """Identify records with compliance violations."""
        violation_recs = [
            r
            for r in self._records
            if r.compliance_level
            in (ComplianceLevel.MAJOR_DEVIATION, ComplianceLevel.NON_COMPLIANT)
        ]
        results: list[dict[str, Any]] = []
        for r in violation_recs:
            results.append(
                {
                    "record_id": r.id,
                    "agent_id": r.agent_id,
                    "compliance_level": r.compliance_level.value,
                    "format_standard": r.format_standard.value,
                    "violation_count": r.violation_count,
                    "compliance_score": r.compliance_score,
                }
            )
        results.sort(key=lambda x: x["violation_count"], reverse=True)
        return results

    def compute_format_reward_impact(self) -> dict[str, Any]:
        """Compute how much format compliance impacts total reward."""
        if not self._records:
            return {"total_reward": 0.0, "avg_penalty_pct": 0.0}
        penalty_map = {
            ComplianceLevel.FULL_COMPLIANCE.value: 0.0,
            ComplianceLevel.MINOR_DEVIATION.value: 0.1,
            ComplianceLevel.MAJOR_DEVIATION.value: 0.4,
            ComplianceLevel.NON_COMPLIANT.value: 1.0,
        }
        total_reward = sum(r.reward_value for r in self._records)
        total_penalty = sum(
            penalty_map.get(r.compliance_level.value, 0.0) * r.reward_value for r in self._records
        )
        avg_penalty_pct = (
            round(total_penalty / total_reward * 100, 2) if total_reward != 0.0 else 0.0
        )
        return {
            "total_reward": round(total_reward, 4),
            "total_penalty": round(total_penalty, 4),
            "avg_penalty_pct": avg_penalty_pct,
            "record_count": len(self._records),
        }
