"""Purple Team Campaign Engine
exercise planning, attack simulation, detection validation, coverage gaps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CampaignPhase(StrEnum):
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"
    REPORTING = "reporting"
    REMEDIATION = "remediation"


class AttackTechnique(StrEnum):
    INITIAL_ACCESS = "initial_access"
    LATERAL_MOVEMENT = "lateral_movement"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    PERSISTENCE = "persistence"


class DetectionOutcome(StrEnum):
    DETECTED = "detected"
    PARTIALLY_DETECTED = "partially_detected"
    MISSED = "missed"
    BLOCKED = "blocked"
    ALERTED = "alerted"


# --- Models ---


class CampaignRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_name: str = ""
    campaign_phase: CampaignPhase = CampaignPhase.PLANNING
    attack_technique: AttackTechnique = AttackTechnique.INITIAL_ACCESS
    detection_outcome: DetectionOutcome = DetectionOutcome.MISSED
    mitre_tactic_id: str = ""
    detection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CampaignAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_name: str = ""
    attack_technique: AttackTechnique = AttackTechnique.INITIAL_ACCESS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CampaignReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_detection_score: float = 0.0
    detection_rate: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_technique: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    coverage_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PurpleTeamCampaignEngine:
    """Purple team exercise planning, attack simulation, detection validation, coverage gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[CampaignRecord] = []
        self._analyses: list[CampaignAnalysis] = []
        logger.info(
            "purple_team_campaign_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def add_record(
        self,
        campaign_name: str,
        campaign_phase: CampaignPhase = CampaignPhase.PLANNING,
        attack_technique: AttackTechnique = AttackTechnique.INITIAL_ACCESS,
        detection_outcome: DetectionOutcome = DetectionOutcome.MISSED,
        mitre_tactic_id: str = "",
        detection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CampaignRecord:
        record = CampaignRecord(
            campaign_name=campaign_name,
            campaign_phase=campaign_phase,
            attack_technique=attack_technique,
            detection_outcome=detection_outcome,
            mitre_tactic_id=mitre_tactic_id,
            detection_score=detection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "purple_team_campaign_engine.record_added",
            record_id=record.id,
            campaign_name=campaign_name,
            attack_technique=attack_technique.value,
        )
        return record

    def get_record(self, record_id: str) -> CampaignRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        attack_technique: AttackTechnique | None = None,
        detection_outcome: DetectionOutcome | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CampaignRecord]:
        results = list(self._records)
        if attack_technique is not None:
            results = [r for r in results if r.attack_technique == attack_technique]
        if detection_outcome is not None:
            results = [r for r in results if r.detection_outcome == detection_outcome]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        campaign_name: str,
        attack_technique: AttackTechnique = AttackTechnique.INITIAL_ACCESS,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CampaignAnalysis:
        analysis = CampaignAnalysis(
            campaign_name=campaign_name,
            attack_technique=attack_technique,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "purple_team_campaign_engine.analysis_added",
            campaign_name=campaign_name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def compute_detection_rate(self) -> dict[str, Any]:
        if not self._records:
            return {"detection_rate": 0.0, "total_tests": 0}
        detected = sum(
            1
            for r in self._records
            if r.detection_outcome in (DetectionOutcome.DETECTED, DetectionOutcome.BLOCKED)
        )
        partial = sum(
            1 for r in self._records if r.detection_outcome == DetectionOutcome.PARTIALLY_DETECTED
        )
        total = len(self._records)
        rate = round((detected + partial * 0.5) / total * 100, 2)
        return {
            "detection_rate": rate,
            "fully_detected": detected,
            "partially_detected": partial,
            "missed": total - detected - partial,
            "total_tests": total,
        }

    def identify_coverage_gaps(self) -> list[dict[str, Any]]:
        technique_results: dict[str, dict[str, int]] = {}
        for r in self._records:
            key = r.attack_technique.value
            technique_results.setdefault(key, {"detected": 0, "missed": 0, "total": 0})
            technique_results[key]["total"] += 1
            if r.detection_outcome == DetectionOutcome.MISSED:
                technique_results[key]["missed"] += 1
            else:
                technique_results[key]["detected"] += 1
        gaps: list[dict[str, Any]] = []
        for tech, counts in technique_results.items():
            miss_rate = counts["missed"] / counts["total"] * 100 if counts["total"] else 0
            if miss_rate > (100 - self._threshold):
                gaps.append(
                    {
                        "technique": tech,
                        "miss_rate": round(miss_rate, 2),
                        "missed_count": counts["missed"],
                        "total_count": counts["total"],
                    }
                )
        return sorted(gaps, key=lambda x: x["miss_rate"], reverse=True)

    def rank_by_score(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.detection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                    "test_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

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

    def generate_report(self) -> CampaignReport:
        by_phase: dict[str, int] = {}
        by_technique: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_phase[r.campaign_phase.value] = by_phase.get(r.campaign_phase.value, 0) + 1
            by_technique[r.attack_technique.value] = (
                by_technique.get(r.attack_technique.value, 0) + 1
            )
            by_outcome[r.detection_outcome.value] = by_outcome.get(r.detection_outcome.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.detection_score < self._threshold)
        scores = [r.detection_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        det_info = self.compute_detection_rate()
        gap_list = self.identify_coverage_gaps()
        coverage_gaps = [g["technique"] for g in gap_list[:5]]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(f"{gap_count} test(s) below detection threshold ({self._threshold})")
        if det_info["detection_rate"] < self._threshold:
            recs.append(
                f"Detection rate {det_info['detection_rate']}% below target {self._threshold}%"
            )
        if coverage_gaps:
            recs.append(f"Coverage gaps in techniques: {', '.join(coverage_gaps)}")
        if not recs:
            recs.append("Purple team detection coverage is healthy")
        return CampaignReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_detection_score=avg_score,
            detection_rate=det_info["detection_rate"],
            by_phase=by_phase,
            by_technique=by_technique,
            by_outcome=by_outcome,
            coverage_gaps=coverage_gaps,
            recommendations=recs,
        )

    def process(self, campaign_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.campaign_name == campaign_name]
        if not matching:
            return {"campaign_name": campaign_name, "status": "no_data"}
        detected = sum(
            1
            for r in matching
            if r.detection_outcome in (DetectionOutcome.DETECTED, DetectionOutcome.BLOCKED)
        )
        scores = [r.detection_score for r in matching]
        return {
            "campaign_name": campaign_name,
            "total_tests": len(matching),
            "detection_rate": round(detected / len(matching) * 100, 2),
            "avg_score": round(sum(scores) / len(scores), 2),
        }

    def get_stats(self) -> dict[str, Any]:
        tech_dist: dict[str, int] = {}
        for r in self._records:
            key = r.attack_technique.value
            tech_dist[key] = tech_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "technique_distribution": tech_dist,
            "unique_campaigns": len({r.campaign_name for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("purple_team_campaign_engine.cleared")
        return {"status": "cleared"}
