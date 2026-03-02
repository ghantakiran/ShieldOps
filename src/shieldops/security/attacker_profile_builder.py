"""Attacker Profile Builder — build attacker profiles from evidence + TI."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ProfileType(StrEnum):
    NATION_STATE = "nation_state"
    APT_GROUP = "apt_group"
    CYBERCRIMINAL = "cybercriminal"
    HACKTIVIST = "hacktivist"
    INSIDER = "insider"


class ProfileConfidence(StrEnum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SPECULATIVE = "speculative"


class AttributionSource(StrEnum):
    THREAT_INTEL = "threat_intel"
    FORENSIC_EVIDENCE = "forensic_evidence"
    BEHAVIORAL_ANALYSIS = "behavioral_analysis"
    OSINT = "osint"
    HONEYPOT_DATA = "honeypot_data"


# --- Models ---


class ProfileRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    profile_name: str = ""
    profile_type: ProfileType = ProfileType.NATION_STATE
    profile_confidence: ProfileConfidence = ProfileConfidence.CONFIRMED
    attribution_source: AttributionSource = AttributionSource.THREAT_INTEL
    profile_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ProfileAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    profile_name: str = ""
    profile_type: ProfileType = ProfileType.NATION_STATE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ProfileReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_confidence_count: int = 0
    avg_profile_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    top_low_confidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AttackerProfileBuilder:
    """Build attacker profiles from evidence and threat intelligence."""

    def __init__(
        self,
        max_records: int = 200000,
        profile_confidence_threshold: float = 65.0,
    ) -> None:
        self._max_records = max_records
        self._profile_confidence_threshold = profile_confidence_threshold
        self._records: list[ProfileRecord] = []
        self._analyses: list[ProfileAnalysis] = []
        logger.info(
            "attacker_profile_builder.initialized",
            max_records=max_records,
            profile_confidence_threshold=profile_confidence_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_profile(
        self,
        profile_name: str,
        profile_type: ProfileType = ProfileType.NATION_STATE,
        profile_confidence: ProfileConfidence = ProfileConfidence.CONFIRMED,
        attribution_source: AttributionSource = AttributionSource.THREAT_INTEL,
        profile_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ProfileRecord:
        record = ProfileRecord(
            profile_name=profile_name,
            profile_type=profile_type,
            profile_confidence=profile_confidence,
            attribution_source=attribution_source,
            profile_score=profile_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "attacker_profile_builder.profile_recorded",
            record_id=record.id,
            profile_name=profile_name,
            profile_type=profile_type.value,
            profile_confidence=profile_confidence.value,
        )
        return record

    def get_profile(self, record_id: str) -> ProfileRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_profiles(
        self,
        profile_type: ProfileType | None = None,
        profile_confidence: ProfileConfidence | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ProfileRecord]:
        results = list(self._records)
        if profile_type is not None:
            results = [r for r in results if r.profile_type == profile_type]
        if profile_confidence is not None:
            results = [r for r in results if r.profile_confidence == profile_confidence]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        profile_name: str,
        profile_type: ProfileType = ProfileType.NATION_STATE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ProfileAnalysis:
        analysis = ProfileAnalysis(
            profile_name=profile_name,
            profile_type=profile_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "attacker_profile_builder.analysis_added",
            profile_name=profile_name,
            profile_type=profile_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_profile_distribution(self) -> dict[str, Any]:
        """Group by profile_type; return count and avg profile_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.profile_type.value
            type_data.setdefault(key, []).append(r.profile_score)
        result: dict[str, Any] = {}
        for ptype, scores in type_data.items():
            result[ptype] = {
                "count": len(scores),
                "avg_profile_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_confidence_profiles(self) -> list[dict[str, Any]]:
        """Return records where profile_score < profile_confidence_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.profile_score < self._profile_confidence_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "profile_name": r.profile_name,
                        "profile_type": r.profile_type.value,
                        "profile_score": r.profile_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["profile_score"])

    def rank_by_profile(self) -> list[dict[str, Any]]:
        """Group by service, avg profile_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.profile_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_profile_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_profile_score"])
        return results

    def detect_profile_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ProfileReport:
        by_type: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in self._records:
            by_type[r.profile_type.value] = by_type.get(r.profile_type.value, 0) + 1
            by_confidence[r.profile_confidence.value] = (
                by_confidence.get(r.profile_confidence.value, 0) + 1
            )
            by_source[r.attribution_source.value] = by_source.get(r.attribution_source.value, 0) + 1
        low_confidence_count = sum(
            1 for r in self._records if r.profile_score < self._profile_confidence_threshold
        )
        scores = [r.profile_score for r in self._records]
        avg_profile_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_confidence_profiles()
        top_low_confidence = [o["profile_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_confidence_count > 0:
            recs.append(
                f"{low_confidence_count} profile(s) below confidence threshold "
                f"({self._profile_confidence_threshold})"
            )
        if self._records and avg_profile_score < self._profile_confidence_threshold:
            recs.append(
                f"Avg profile score {avg_profile_score} below threshold "
                f"({self._profile_confidence_threshold})"
            )
        if not recs:
            recs.append("Attacker profile confidence is healthy")
        return ProfileReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_confidence_count=low_confidence_count,
            avg_profile_score=avg_profile_score,
            by_type=by_type,
            by_confidence=by_confidence,
            by_source=by_source,
            top_low_confidence=top_low_confidence,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("attacker_profile_builder.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.profile_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "profile_confidence_threshold": self._profile_confidence_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
