"""Consent Management Engine — manage user consents across purposes and systems."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ConsentType(StrEnum):
    OPT_IN = "opt_in"
    OPT_OUT = "opt_out"
    EXPLICIT = "explicit"
    IMPLIED = "implied"
    WITHDRAWN = "withdrawn"


class ConsentPurpose(StrEnum):
    MARKETING = "marketing"
    ANALYTICS = "analytics"
    PERSONALIZATION = "personalization"
    THIRD_PARTY = "third_party"
    ESSENTIAL = "essential"


class ConsentStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"
    INVALID = "invalid"


# --- Models ---


class ConsentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject_id: str = ""
    consent_type: ConsentType = ConsentType.OPT_IN
    consent_purpose: ConsentPurpose = ConsentPurpose.ESSENTIAL
    consent_status: ConsentStatus = ConsentStatus.ACTIVE
    validity_score: float = 0.0
    channel: str = ""
    data_controller: str = ""
    created_at: float = Field(default_factory=time.time)


class ConsentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject_id: str = ""
    consent_purpose: ConsentPurpose = ConsentPurpose.ESSENTIAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConsentComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_validity_score: float = 0.0
    by_consent_type: dict[str, int] = Field(default_factory=dict)
    by_purpose: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ConsentManagementEngine:
    """Manage and audit user consents; detect invalid or expired consent coverage."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ConsentRecord] = []
        self._analyses: list[ConsentAnalysis] = []
        logger.info(
            "consent_management_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_consent(
        self,
        subject_id: str,
        consent_type: ConsentType = ConsentType.OPT_IN,
        consent_purpose: ConsentPurpose = ConsentPurpose.ESSENTIAL,
        consent_status: ConsentStatus = ConsentStatus.ACTIVE,
        validity_score: float = 0.0,
        channel: str = "",
        data_controller: str = "",
    ) -> ConsentRecord:
        record = ConsentRecord(
            subject_id=subject_id,
            consent_type=consent_type,
            consent_purpose=consent_purpose,
            consent_status=consent_status,
            validity_score=validity_score,
            channel=channel,
            data_controller=data_controller,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "consent_management_engine.consent_recorded",
            record_id=record.id,
            subject_id=subject_id,
            consent_type=consent_type.value,
            consent_purpose=consent_purpose.value,
        )
        return record

    def get_consent(self, record_id: str) -> ConsentRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_consents(
        self,
        consent_type: ConsentType | None = None,
        consent_purpose: ConsentPurpose | None = None,
        data_controller: str | None = None,
        limit: int = 50,
    ) -> list[ConsentRecord]:
        results = list(self._records)
        if consent_type is not None:
            results = [r for r in results if r.consent_type == consent_type]
        if consent_purpose is not None:
            results = [r for r in results if r.consent_purpose == consent_purpose]
        if data_controller is not None:
            results = [r for r in results if r.data_controller == data_controller]
        return results[-limit:]

    def add_analysis(
        self,
        subject_id: str,
        consent_purpose: ConsentPurpose = ConsentPurpose.ESSENTIAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ConsentAnalysis:
        analysis = ConsentAnalysis(
            subject_id=subject_id,
            consent_purpose=consent_purpose,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "consent_management_engine.analysis_added",
            subject_id=subject_id,
            consent_purpose=consent_purpose.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_purpose_distribution(self) -> dict[str, Any]:
        """Group by consent_purpose; return count and avg validity_score."""
        purpose_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.consent_purpose.value
            purpose_data.setdefault(key, []).append(r.validity_score)
        result: dict[str, Any] = {}
        for purpose, scores in purpose_data.items():
            result[purpose] = {
                "count": len(scores),
                "avg_validity_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_consent_gaps(self) -> list[dict[str, Any]]:
        """Return records where validity_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.validity_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "subject_id": r.subject_id,
                        "consent_purpose": r.consent_purpose.value,
                        "validity_score": r.validity_score,
                        "channel": r.channel,
                        "data_controller": r.data_controller,
                    }
                )
        return sorted(results, key=lambda x: x["validity_score"])

    def rank_by_validity(self) -> list[dict[str, Any]]:
        """Group by data_controller, avg validity_score, sort ascending."""
        ctrl_scores: dict[str, list[float]] = {}
        for r in self._records:
            ctrl_scores.setdefault(r.data_controller, []).append(r.validity_score)
        results: list[dict[str, Any]] = []
        for ctrl, scores in ctrl_scores.items():
            results.append(
                {
                    "data_controller": ctrl,
                    "avg_validity_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_validity_score"])
        return results

    def detect_consent_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
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

    def generate_report(self) -> ConsentComplianceReport:
        by_consent_type: dict[str, int] = {}
        by_purpose: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_consent_type[r.consent_type.value] = by_consent_type.get(r.consent_type.value, 0) + 1
            by_purpose[r.consent_purpose.value] = by_purpose.get(r.consent_purpose.value, 0) + 1
            by_status[r.consent_status.value] = by_status.get(r.consent_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.validity_score < self._threshold)
        scores = [r.validity_score for r in self._records]
        avg_validity_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_consent_gaps()
        top_gaps = [o["subject_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} consent(s) below validity threshold ({self._threshold})")
        if self._records and avg_validity_score < self._threshold:
            recs.append(
                f"Avg validity score {avg_validity_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Consent management coverage is healthy")
        return ConsentComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_validity_score=avg_validity_score,
            by_consent_type=by_consent_type,
            by_purpose=by_purpose,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("consent_management_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        purpose_dist: dict[str, int] = {}
        for r in self._records:
            key = r.consent_purpose.value
            purpose_dist[key] = purpose_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "purpose_distribution": purpose_dist,
            "unique_controllers": len({r.data_controller for r in self._records}),
            "unique_channels": len({r.channel for r in self._records}),
        }
