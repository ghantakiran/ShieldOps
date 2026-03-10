"""Automated Incident Classifier
classify incidents, compute classification confidence,
detect misclassifications."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IncidentCategory(StrEnum):
    MALWARE = "malware"
    PHISHING = "phishing"
    DATA_BREACH = "data_breach"
    INSIDER_THREAT = "insider_threat"


class ClassificationMethod(StrEnum):
    RULE_BASED = "rule_based"
    ML_MODEL = "ml_model"
    HYBRID = "hybrid"
    MANUAL = "manual"


class SeverityAssessment(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class IncidentClassifierRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    category: IncidentCategory = IncidentCategory.MALWARE
    method: ClassificationMethod = ClassificationMethod.RULE_BASED
    severity: SeverityAssessment = SeverityAssessment.MEDIUM
    confidence_score: float = 0.0
    is_verified: bool = False
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentClassifierAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    category: IncidentCategory = IncidentCategory.MALWARE
    analysis_score: float = 0.0
    misclassification_risk: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentClassifierReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_confidence: float = 0.0
    verified_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    low_confidence_incidents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutomatedIncidentClassifier:
    """Classify incidents, compute classification
    confidence, detect misclassifications."""

    def __init__(
        self,
        max_records: int = 200000,
        confidence_threshold: float = 0.75,
    ) -> None:
        self._max_records = max_records
        self._confidence_threshold = confidence_threshold
        self._records: list[IncidentClassifierRecord] = []
        self._analyses: list[IncidentClassifierAnalysis] = []
        logger.info(
            "automated_incident_classifier.init",
            max_records=max_records,
            confidence_threshold=confidence_threshold,
        )

    def add_record(
        self,
        incident_id: str,
        category: IncidentCategory = (IncidentCategory.MALWARE),
        method: ClassificationMethod = (ClassificationMethod.RULE_BASED),
        severity: SeverityAssessment = (SeverityAssessment.MEDIUM),
        confidence_score: float = 0.0,
        is_verified: bool = False,
        service: str = "",
        team: str = "",
    ) -> IncidentClassifierRecord:
        record = IncidentClassifierRecord(
            incident_id=incident_id,
            category=category,
            method=method,
            severity=severity,
            confidence_score=confidence_score,
            is_verified=is_verified,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "automated_incident_classifier.added",
            record_id=record.id,
            incident_id=incident_id,
        )
        return record

    def process(self, key: str) -> IncidentClassifierAnalysis | None:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return None
        score = rec.confidence_score * 100.0
        misclass_risk = round(1.0 - rec.confidence_score, 4)
        analysis = IncidentClassifierAnalysis(
            incident_id=rec.incident_id,
            category=rec.category,
            analysis_score=round(score, 2),
            misclassification_risk=misclass_risk,
            description=(f"Incident {rec.incident_id} confidence {score:.1f}%"),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return analysis

    def generate_report(
        self,
    ) -> IncidentClassifierReport:
        by_cat: dict[str, int] = {}
        by_meth: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        confs: list[float] = []
        verified = 0
        for r in self._records:
            c = r.category.value
            by_cat[c] = by_cat.get(c, 0) + 1
            m = r.method.value
            by_meth[m] = by_meth.get(m, 0) + 1
            s = r.severity.value
            by_sev[s] = by_sev.get(s, 0) + 1
            confs.append(r.confidence_score)
            if r.is_verified:
                verified += 1
        avg_conf = round(sum(confs) / len(confs), 4) if confs else 0.0
        ver_pct = round(verified / len(self._records) * 100, 2) if self._records else 0.0
        low_conf = [
            r.incident_id for r in self._records if r.confidence_score < self._confidence_threshold
        ][:5]
        recs: list[str] = []
        if low_conf:
            recs.append(f"{len(low_conf)} incidents with low classification confidence")
        if not recs:
            recs.append("Classification accuracy OK")
        return IncidentClassifierReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_confidence=avg_conf,
            verified_pct=ver_pct,
            by_category=by_cat,
            by_method=by_meth,
            by_severity=by_sev,
            low_confidence_incidents=low_conf,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            k = r.category.value
            cat_dist[k] = cat_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "confidence_threshold": (self._confidence_threshold),
            "category_distribution": cat_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("automated_incident_classifier.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def classify_incident(
        self,
    ) -> list[dict[str, Any]]:
        """Classify incidents by category with
        confidence stats."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            k = r.category.value
            cat_data.setdefault(k, []).append(r.confidence_score)
        results: list[dict[str, Any]] = []
        for cat, scores in cat_data.items():
            avg = round(sum(scores) / len(scores), 4)
            results.append(
                {
                    "category": cat,
                    "count": len(scores),
                    "avg_confidence": avg,
                    "below_threshold": sum(1 for s in scores if s < self._confidence_threshold),
                }
            )
        results.sort(
            key=lambda x: x["avg_confidence"],
        )
        return results

    def compute_classification_confidence(
        self,
    ) -> dict[str, Any]:
        """Compute classification confidence by
        method."""
        if not self._records:
            return {
                "overall_confidence": 0.0,
                "by_method": {},
            }
        meth_scores: dict[str, list[float]] = {}
        for r in self._records:
            k = r.method.value
            meth_scores.setdefault(k, []).append(r.confidence_score)
        by_meth: dict[str, float] = {}
        for m, scores in meth_scores.items():
            by_meth[m] = round(sum(scores) / len(scores), 4)
        all_s = [r.confidence_score for r in self._records]
        return {
            "overall_confidence": round(sum(all_s) / len(all_s), 4),
            "by_method": by_meth,
        }

    def detect_misclassifications(
        self,
    ) -> list[dict[str, Any]]:
        """Detect potential misclassifications:
        low confidence and not verified."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.confidence_score < self._confidence_threshold and not r.is_verified:
                risk = round(1.0 - r.confidence_score, 4)
                results.append(
                    {
                        "incident_id": r.incident_id,
                        "category": r.category.value,
                        "method": r.method.value,
                        "confidence": r.confidence_score,
                        "misclassification_risk": risk,
                    }
                )
        results.sort(
            key=lambda x: x["misclassification_risk"],
            reverse=True,
        )
        return results
