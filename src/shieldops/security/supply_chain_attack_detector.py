"""Supply Chain Attack Detector — dependency confusion, typosquatting, build compromise."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AttackType(StrEnum):
    DEPENDENCY_CONFUSION = "dependency_confusion"
    TYPOSQUATTING = "typosquatting"
    BUILD_COMPROMISE = "build_compromise"
    MALICIOUS_UPDATE = "malicious_update"
    COMPROMISED_REGISTRY = "compromised_registry"


class ComponentType(StrEnum):
    NPM_PACKAGE = "npm_package"
    PYPI_PACKAGE = "pypi_package"
    DOCKER_IMAGE = "docker_image"
    GIT_REPO = "git_repo"
    BINARY_ARTIFACT = "binary_artifact"


class DetectionConfidence(StrEnum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SUSPECTED = "suspected"


# --- Models ---


class SupplyChainRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    component_name: str = ""
    attack_type: AttackType = AttackType.DEPENDENCY_CONFUSION
    component_type: ComponentType = ComponentType.NPM_PACKAGE
    detection_confidence: DetectionConfidence = DetectionConfidence.CONFIRMED
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SupplyChainAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    component_name: str = ""
    attack_type: AttackType = AttackType.DEPENDENCY_CONFUSION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SupplyChainReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_confidence_count: int = 0
    avg_risk_score: float = 0.0
    by_attack_type: dict[str, int] = Field(default_factory=dict)
    by_component_type: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_low_confidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SupplyChainAttackDetector:
    """Detect supply chain attacks including dependency confusion and typosquatting."""

    def __init__(
        self,
        max_records: int = 200000,
        supply_chain_risk_threshold: float = 55.0,
    ) -> None:
        self._max_records = max_records
        self._supply_chain_risk_threshold = supply_chain_risk_threshold
        self._records: list[SupplyChainRecord] = []
        self._analyses: list[SupplyChainAnalysis] = []
        logger.info(
            "supply_chain_attack_detector.initialized",
            max_records=max_records,
            supply_chain_risk_threshold=supply_chain_risk_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_detection(
        self,
        component_name: str,
        attack_type: AttackType = AttackType.DEPENDENCY_CONFUSION,
        component_type: ComponentType = ComponentType.NPM_PACKAGE,
        detection_confidence: DetectionConfidence = DetectionConfidence.CONFIRMED,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SupplyChainRecord:
        record = SupplyChainRecord(
            component_name=component_name,
            attack_type=attack_type,
            component_type=component_type,
            detection_confidence=detection_confidence,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "supply_chain_attack_detector.detection_recorded",
            record_id=record.id,
            component_name=component_name,
            attack_type=attack_type.value,
            component_type=component_type.value,
        )
        return record

    def get_detection(self, record_id: str) -> SupplyChainRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_detections(
        self,
        attack_type: AttackType | None = None,
        component_type: ComponentType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SupplyChainRecord]:
        results = list(self._records)
        if attack_type is not None:
            results = [r for r in results if r.attack_type == attack_type]
        if component_type is not None:
            results = [r for r in results if r.component_type == component_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        component_name: str,
        attack_type: AttackType = AttackType.DEPENDENCY_CONFUSION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SupplyChainAnalysis:
        analysis = SupplyChainAnalysis(
            component_name=component_name,
            attack_type=attack_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "supply_chain_attack_detector.analysis_added",
            component_name=component_name,
            attack_type=attack_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_attack_distribution(self) -> dict[str, Any]:
        """Group by attack_type; return count and avg risk_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.attack_type.value
            type_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for atype, scores in type_data.items():
            result[atype] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_confidence_detections(self) -> list[dict[str, Any]]:
        """Return records where risk_score < supply_chain_risk_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._supply_chain_risk_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "component_name": r.component_name,
                        "attack_type": r.attack_type.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"])
        return results

    def detect_risk_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> SupplyChainReport:
        by_attack_type: dict[str, int] = {}
        by_component_type: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_attack_type[r.attack_type.value] = by_attack_type.get(r.attack_type.value, 0) + 1
            by_component_type[r.component_type.value] = (
                by_component_type.get(r.component_type.value, 0) + 1
            )
            by_confidence[r.detection_confidence.value] = (
                by_confidence.get(r.detection_confidence.value, 0) + 1
            )
        low_confidence_count = sum(
            1 for r in self._records if r.risk_score < self._supply_chain_risk_threshold
        )
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_confidence_detections()
        top_low_confidence = [o["component_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_confidence_count > 0:
            recs.append(
                f"{low_confidence_count} detection(s) below risk threshold "
                f"({self._supply_chain_risk_threshold})"
            )
        if self._records and avg_risk_score < self._supply_chain_risk_threshold:
            recs.append(
                f"Avg risk score {avg_risk_score} below threshold "
                f"({self._supply_chain_risk_threshold})"
            )
        if not recs:
            recs.append("Supply chain attack detection posture is healthy")
        return SupplyChainReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_confidence_count=low_confidence_count,
            avg_risk_score=avg_risk_score,
            by_attack_type=by_attack_type,
            by_component_type=by_component_type,
            by_confidence=by_confidence,
            top_low_confidence=top_low_confidence,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("supply_chain_attack_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        attack_dist: dict[str, int] = {}
        for r in self._records:
            key = r.attack_type.value
            attack_dist[key] = attack_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "supply_chain_risk_threshold": self._supply_chain_risk_threshold,
            "attack_type_distribution": attack_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
