"""Risk Compliance Bridge
map risk findings to compliance controls, compute
compliance risk scores, detect unmapped risks."""

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
    NIST = "nist"
    CIS = "cis"
    ISO27001 = "iso27001"
    SOC2 = "soc2"


class RiskToControlMapping(StrEnum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    PARTIAL = "partial"
    UNMAPPED = "unmapped"


class ComplianceImpact(StrEnum):
    VIOLATION = "violation"
    WARNING = "warning"
    OBSERVATION = "observation"
    COMPLIANT = "compliant"


# --- Models ---


class RiskComplianceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    risk_id: str = ""
    framework: ComplianceFramework = ComplianceFramework.NIST
    mapping: RiskToControlMapping = RiskToControlMapping.DIRECT
    impact: ComplianceImpact = ComplianceImpact.OBSERVATION
    control_id: str = ""
    risk_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskComplianceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    risk_id: str = ""
    framework: ComplianceFramework = ComplianceFramework.NIST
    compliance_score: float = 0.0
    unmapped_count: int = 0
    violation_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_mapping: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    unmapped_risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RiskComplianceBridge:
    """Map risks to controls, compute compliance
    risk scores, detect unmapped risks."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RiskComplianceRecord] = []
        self._analyses: dict[str, RiskComplianceAnalysis] = {}
        logger.info(
            "risk_compliance_bridge.init",
            max_records=max_records,
        )

    def add_record(
        self,
        risk_id: str = "",
        framework: ComplianceFramework = (ComplianceFramework.NIST),
        mapping: RiskToControlMapping = (RiskToControlMapping.DIRECT),
        impact: ComplianceImpact = (ComplianceImpact.OBSERVATION),
        control_id: str = "",
        risk_score: float = 0.0,
        description: str = "",
    ) -> RiskComplianceRecord:
        record = RiskComplianceRecord(
            risk_id=risk_id,
            framework=framework,
            mapping=mapping,
            impact=impact,
            control_id=control_id,
            risk_score=risk_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_compliance_bridge.record_added",
            record_id=record.id,
            risk_id=risk_id,
        )
        return record

    def process(self, key: str) -> RiskComplianceAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        unmapped = sum(1 for r in self._records if r.mapping == RiskToControlMapping.UNMAPPED)
        violations = sum(1 for r in self._records if r.impact == ComplianceImpact.VIOLATION)
        comp_score = (
            round(
                (1 - unmapped / len(self._records)) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        analysis = RiskComplianceAnalysis(
            risk_id=rec.risk_id,
            framework=rec.framework,
            compliance_score=comp_score,
            unmapped_count=unmapped,
            violation_count=violations,
            description=(f"Risk {rec.risk_id} compliance={comp_score}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> RiskComplianceReport:
        by_fw: dict[str, int] = {}
        by_mp: dict[str, int] = {}
        by_im: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.framework.value
            by_fw[k] = by_fw.get(k, 0) + 1
            k2 = r.mapping.value
            by_mp[k2] = by_mp.get(k2, 0) + 1
            k3 = r.impact.value
            by_im[k3] = by_im.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        unmapped = [r.risk_id for r in self._records if r.mapping == RiskToControlMapping.UNMAPPED][
            :10
        ]
        recs: list[str] = []
        if unmapped:
            recs.append(f"{len(unmapped)} unmapped risks")
        violations = by_im.get("violation", 0)
        if violations > 0:
            recs.append(f"{violations} compliance violations")
        if not recs:
            recs.append("Compliance posture healthy")
        return RiskComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_framework=by_fw,
            by_mapping=by_mp,
            by_impact=by_im,
            unmapped_risks=unmapped,
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
            "framework_distribution": fw_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("risk_compliance_bridge.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def map_risk_to_controls(
        self,
    ) -> list[dict[str, Any]]:
        """Map risks to their controls."""
        risk_controls: dict[str, list[str]] = {}
        for r in self._records:
            risk_controls.setdefault(r.risk_id, []).append(r.control_id)
        results: list[dict[str, Any]] = []
        for rid, controls in risk_controls.items():
            results.append(
                {
                    "risk_id": rid,
                    "controls": sorted(set(controls)),
                    "control_count": len(set(controls)),
                }
            )
        return results

    def compute_compliance_risk_score(
        self,
    ) -> dict[str, Any]:
        """Compute compliance risk per framework."""
        if not self._records:
            return {
                "overall_score": 0.0,
                "by_framework": {},
            }
        fw_scores: dict[str, list[float]] = {}
        for r in self._records:
            k = r.framework.value
            fw_scores.setdefault(k, []).append(r.risk_score)
        by_fw: dict[str, float] = {}
        all_scores: list[float] = []
        for fw, scores in fw_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            by_fw[fw] = avg
            all_scores.extend(scores)
        overall = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0
        return {
            "overall_score": overall,
            "by_framework": by_fw,
        }

    def detect_unmapped_risks(
        self,
    ) -> list[dict[str, Any]]:
        """Find risks not mapped to controls."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.mapping == RiskToControlMapping.UNMAPPED:
                results.append(
                    {
                        "risk_id": r.risk_id,
                        "framework": (r.framework.value),
                        "risk_score": r.risk_score,
                        "impact": r.impact.value,
                    }
                )
        results.sort(
            key=lambda x: x["risk_score"],
            reverse=True,
        )
        return results
