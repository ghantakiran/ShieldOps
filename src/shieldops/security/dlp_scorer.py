"""DLP Scorer — data loss prevention posture and exfiltration risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DataChannel(StrEnum):
    EMAIL = "email"
    CLOUD_STORAGE = "cloud_storage"
    USB = "usb"
    WEB_UPLOAD = "web_upload"
    API_TRANSFER = "api_transfer"


class DataSensitivity(StrEnum):
    TOP_SECRET = "top_secret"  # noqa: S105
    CONFIDENTIAL = "confidential"
    INTERNAL = "internal"
    PUBLIC = "public"
    UNCLASSIFIED = "unclassified"


class PolicyAction(StrEnum):
    BLOCK = "block"
    ENCRYPT = "encrypt"
    ALERT = "alert"
    LOG = "log"
    ALLOW = "allow"


# --- Models ---


class DLPRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    data_channel: DataChannel = DataChannel.EMAIL
    data_sensitivity: DataSensitivity = DataSensitivity.TOP_SECRET
    policy_action: PolicyAction = PolicyAction.BLOCK
    protection_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DLPAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    data_channel: DataChannel = DataChannel.EMAIL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DLPReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_protection_count: int = 0
    avg_protection_score: float = 0.0
    by_channel: dict[str, int] = Field(default_factory=dict)
    by_sensitivity: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_low_protection: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DLPScorer:
    """Data loss prevention posture scoring and exfiltration risk assessment."""

    def __init__(
        self,
        max_records: int = 200000,
        protection_threshold: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._protection_threshold = protection_threshold
        self._records: list[DLPRecord] = []
        self._analyses: list[DLPAnalysis] = []
        logger.info(
            "dlp_scorer.initialized",
            max_records=max_records,
            protection_threshold=protection_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_policy(
        self,
        policy_name: str,
        data_channel: DataChannel = DataChannel.EMAIL,
        data_sensitivity: DataSensitivity = DataSensitivity.TOP_SECRET,
        policy_action: PolicyAction = PolicyAction.BLOCK,
        protection_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DLPRecord:
        record = DLPRecord(
            policy_name=policy_name,
            data_channel=data_channel,
            data_sensitivity=data_sensitivity,
            policy_action=policy_action,
            protection_score=protection_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dlp_scorer.policy_recorded",
            record_id=record.id,
            policy_name=policy_name,
            data_channel=data_channel.value,
            data_sensitivity=data_sensitivity.value,
        )
        return record

    def get_policy(self, record_id: str) -> DLPRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_policies(
        self,
        data_channel: DataChannel | None = None,
        data_sensitivity: DataSensitivity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DLPRecord]:
        results = list(self._records)
        if data_channel is not None:
            results = [r for r in results if r.data_channel == data_channel]
        if data_sensitivity is not None:
            results = [r for r in results if r.data_sensitivity == data_sensitivity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        policy_name: str,
        data_channel: DataChannel = DataChannel.EMAIL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DLPAnalysis:
        analysis = DLPAnalysis(
            policy_name=policy_name,
            data_channel=data_channel,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "dlp_scorer.analysis_added",
            policy_name=policy_name,
            data_channel=data_channel.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_channel_distribution(self) -> dict[str, Any]:
        """Group by data_channel; return count and avg protection_score."""
        ch_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.data_channel.value
            ch_data.setdefault(key, []).append(r.protection_score)
        result: dict[str, Any] = {}
        for ch, scores in ch_data.items():
            result[ch] = {
                "count": len(scores),
                "avg_protection_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_protection_policies(self) -> list[dict[str, Any]]:
        """Return records where protection_score < protection_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.protection_score < self._protection_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "policy_name": r.policy_name,
                        "data_channel": r.data_channel.value,
                        "protection_score": r.protection_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["protection_score"])

    def rank_by_protection_score(self) -> list[dict[str, Any]]:
        """Group by service, avg protection_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.protection_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_protection_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_protection_score"])
        return results

    def detect_protection_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> DLPReport:
        by_channel: dict[str, int] = {}
        by_sensitivity: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_channel[r.data_channel.value] = by_channel.get(r.data_channel.value, 0) + 1
            by_sensitivity[r.data_sensitivity.value] = (
                by_sensitivity.get(r.data_sensitivity.value, 0) + 1
            )
            by_action[r.policy_action.value] = by_action.get(r.policy_action.value, 0) + 1
        low_protection_count = sum(
            1 for r in self._records if r.protection_score < self._protection_threshold
        )
        scores = [r.protection_score for r in self._records]
        avg_protection_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_protection_policies()
        top_low_protection = [o["policy_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_protection_count > 0:
            recs.append(
                f"{low_protection_count} policy(ies) below protection threshold "
                f"({self._protection_threshold})"
            )
        if self._records and avg_protection_score < self._protection_threshold:
            recs.append(
                f"Avg protection score {avg_protection_score} below threshold "
                f"({self._protection_threshold})"
            )
        if not recs:
            recs.append("DLP protection posture is healthy")
        return DLPReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_protection_count=low_protection_count,
            avg_protection_score=avg_protection_score,
            by_channel=by_channel,
            by_sensitivity=by_sensitivity,
            by_action=by_action,
            top_low_protection=top_low_protection,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("dlp_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        channel_dist: dict[str, int] = {}
        for r in self._records:
            key = r.data_channel.value
            channel_dist[key] = channel_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "protection_threshold": self._protection_threshold,
            "channel_distribution": channel_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
