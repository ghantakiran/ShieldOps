"""Data Exfiltration Risk Scorer Engine —
score data exfiltration risk,
detect exfil indicators, rank channels by risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExfilChannel(StrEnum):
    EMAIL = "email"
    CLOUD_STORAGE = "cloud_storage"
    USB = "usb"
    NETWORK = "network"


class DataSensitivity(StrEnum):
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"
    INTERNAL = "internal"
    PUBLIC = "public"


class ExfilIndicator(StrEnum):
    VOLUME_SPIKE = "volume_spike"
    UNUSUAL_DESTINATION = "unusual_destination"
    OFF_HOURS = "off_hours"
    COMPRESSION = "compression"


# --- Models ---


class ExfiltrationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    exfil_channel: ExfilChannel = ExfilChannel.NETWORK
    data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    exfil_indicator: ExfilIndicator = ExfilIndicator.VOLUME_SPIKE
    risk_score: float = 0.0
    data_volume_mb: float = 0.0
    destination: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ExfiltrationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    exfil_channel: ExfilChannel = ExfilChannel.NETWORK
    composite_risk: float = 0.0
    exfil_confirmed: bool = False
    sensitivity_level: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ExfiltrationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_exfil_channel: dict[str, int] = Field(default_factory=dict)
    by_data_sensitivity: dict[str, int] = Field(default_factory=dict)
    by_exfil_indicator: dict[str, int] = Field(default_factory=dict)
    high_risk_users: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataExfiltrationRiskScorerEngine:
    """Score data exfiltration risk, detect exfil indicators,
    and rank channels by risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ExfiltrationRecord] = []
        self._analyses: dict[str, ExfiltrationAnalysis] = {}
        logger.info(
            "data_exfiltration_risk_scorer_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        user_id: str = "",
        exfil_channel: ExfilChannel = ExfilChannel.NETWORK,
        data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL,
        exfil_indicator: ExfilIndicator = ExfilIndicator.VOLUME_SPIKE,
        risk_score: float = 0.0,
        data_volume_mb: float = 0.0,
        destination: str = "",
        description: str = "",
    ) -> ExfiltrationRecord:
        record = ExfiltrationRecord(
            user_id=user_id,
            exfil_channel=exfil_channel,
            data_sensitivity=data_sensitivity,
            exfil_indicator=exfil_indicator,
            risk_score=risk_score,
            data_volume_mb=data_volume_mb,
            destination=destination,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_exfiltration_risk.record_added",
            record_id=record.id,
            user_id=user_id,
        )
        return record

    def process(self, key: str) -> ExfiltrationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        sens_weights = {"restricted": 4, "confidential": 3, "internal": 2, "public": 1}
        w = sens_weights.get(rec.data_sensitivity.value, 1)
        composite = round(w * rec.risk_score * (1 + rec.data_volume_mb / 1000), 2)
        confirmed = (
            rec.data_sensitivity
            in (
                DataSensitivity.RESTRICTED,
                DataSensitivity.CONFIDENTIAL,
            )
            and rec.risk_score > 0.6
        )
        analysis = ExfiltrationAnalysis(
            user_id=rec.user_id,
            exfil_channel=rec.exfil_channel,
            composite_risk=composite,
            exfil_confirmed=confirmed,
            sensitivity_level=rec.data_sensitivity.value,
            description=(
                f"User {rec.user_id} exfil via {rec.exfil_channel.value} vol={rec.data_volume_mb}MB"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ExfiltrationReport:
        by_ec: dict[str, int] = {}
        by_ds: dict[str, int] = {}
        by_ei: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.exfil_channel.value
            by_ec[k] = by_ec.get(k, 0) + 1
            k2 = r.data_sensitivity.value
            by_ds[k2] = by_ds.get(k2, 0) + 1
            k3 = r.exfil_indicator.value
            by_ei[k3] = by_ei.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_risk = list(
            {
                r.user_id
                for r in self._records
                if r.data_sensitivity in (DataSensitivity.RESTRICTED, DataSensitivity.CONFIDENTIAL)
                and r.risk_score > 0.6
            }
        )[:10]
        recs: list[str] = []
        if high_risk:
            recs.append(f"{len(high_risk)} users with high exfiltration risk")
        if not recs:
            recs.append("Data exfiltration risk within acceptable thresholds")
        return ExfiltrationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_exfil_channel=by_ec,
            by_data_sensitivity=by_ds,
            by_exfil_indicator=by_ei,
            high_risk_users=high_risk,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ec_dist: dict[str, int] = {}
        for r in self._records:
            k = r.exfil_channel.value
            ec_dist[k] = ec_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "channel_distribution": ec_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("data_exfiltration_risk_scorer_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def score_exfiltration_risk(self) -> list[dict[str, Any]]:
        """Score exfiltration risk aggregated per user and channel."""
        user_channel_data: dict[str, dict[str, Any]] = {}
        sens_weights = {"restricted": 4, "confidential": 3, "internal": 2, "public": 1}
        for r in self._records:
            uc_key = f"{r.user_id}:{r.exfil_channel.value}"
            if uc_key not in user_channel_data:
                user_channel_data[uc_key] = {
                    "user_id": r.user_id,
                    "channel": r.exfil_channel.value,
                    "total_risk": 0.0,
                    "total_volume": 0.0,
                    "count": 0,
                }
            entry = user_channel_data[uc_key]
            w = sens_weights.get(r.data_sensitivity.value, 1)
            entry["total_risk"] += w * r.risk_score
            entry["total_volume"] += r.data_volume_mb
            entry["count"] += 1
        results: list[dict[str, Any]] = []
        for uc_key, data in user_channel_data.items():
            results.append(
                {
                    "key": uc_key,
                    "user_id": data["user_id"],
                    "channel": data["channel"],
                    "composite_risk": round(data["total_risk"], 2),
                    "total_volume_mb": round(data["total_volume"], 2),
                    "event_count": data["count"],
                }
            )
        results.sort(key=lambda x: x["composite_risk"], reverse=True)
        return results

    def detect_exfil_indicators(self) -> list[dict[str, Any]]:
        """Detect active exfiltration indicators."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            ind_key = f"{r.user_id}:{r.exfil_indicator.value}"
            if r.risk_score > 0.5 and ind_key not in seen:
                seen.add(ind_key)
                results.append(
                    {
                        "user_id": r.user_id,
                        "indicator": r.exfil_indicator.value,
                        "channel": r.exfil_channel.value,
                        "sensitivity": r.data_sensitivity.value,
                        "risk_score": r.risk_score,
                        "destination": r.destination,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_channels_by_risk(self) -> list[dict[str, Any]]:
        """Rank exfiltration channels by total risk score."""
        channel_scores: dict[str, float] = {}
        sens_weights = {"restricted": 4, "confidential": 3, "internal": 2, "public": 1}
        for r in self._records:
            ch = r.exfil_channel.value
            w = sens_weights.get(r.data_sensitivity.value, 1)
            channel_scores[ch] = channel_scores.get(ch, 0.0) + (w * r.risk_score)
        results: list[dict[str, Any]] = []
        for ch, score in channel_scores.items():
            results.append(
                {
                    "channel": ch,
                    "total_risk_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["total_risk_score"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
