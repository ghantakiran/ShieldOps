"""External Asset Discovery — discover and classify externally visible assets."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AssetType(StrEnum):
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP_ADDRESS = "ip_address"
    API_ENDPOINT = "api_endpoint"
    CLOUD_RESOURCE = "cloud_resource"


class DiscoveryMethod(StrEnum):
    DNS_ENUMERATION = "dns_enumeration"
    CERT_TRANSPARENCY = "cert_transparency"
    PORT_SCAN = "port_scan"
    CLOUD_API = "cloud_api"
    PASSIVE_RECON = "passive_recon"  # noqa: S105


class DiscoveryStatus(StrEnum):
    DISCOVERED = "discovered"
    VERIFIED = "verified"
    CLASSIFIED = "classified"
    MONITORED = "monitored"
    RETIRED = "retired"


# --- Models ---


class AssetDiscoveryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_name: str = ""
    asset_type: AssetType = AssetType.DOMAIN
    discovery_method: DiscoveryMethod = DiscoveryMethod.DNS_ENUMERATION
    discovery_status: DiscoveryStatus = DiscoveryStatus.DISCOVERED
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AssetDiscoveryAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_name: str = ""
    asset_type: AssetType = AssetType.DOMAIN
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AssetDiscoveryReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_asset_type: dict[str, int] = Field(default_factory=dict)
    by_discovery_method: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ExternalAssetDiscovery:
    """Discover and classify externally visible assets, track discovery coverage."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._records: list[AssetDiscoveryRecord] = []
        self._analyses: list[AssetDiscoveryAnalysis] = []
        logger.info(
            "external_asset_discovery.initialized",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_asset(
        self,
        asset_name: str,
        asset_type: AssetType = AssetType.DOMAIN,
        discovery_method: DiscoveryMethod = DiscoveryMethod.DNS_ENUMERATION,
        discovery_status: DiscoveryStatus = DiscoveryStatus.DISCOVERED,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AssetDiscoveryRecord:
        record = AssetDiscoveryRecord(
            asset_name=asset_name,
            asset_type=asset_type,
            discovery_method=discovery_method,
            discovery_status=discovery_status,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "external_asset_discovery.asset_recorded",
            record_id=record.id,
            asset_name=asset_name,
            asset_type=asset_type.value,
            discovery_method=discovery_method.value,
        )
        return record

    def get_asset(self, record_id: str) -> AssetDiscoveryRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_assets(
        self,
        asset_type: AssetType | None = None,
        discovery_method: DiscoveryMethod | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AssetDiscoveryRecord]:
        results = list(self._records)
        if asset_type is not None:
            results = [r for r in results if r.asset_type == asset_type]
        if discovery_method is not None:
            results = [r for r in results if r.discovery_method == discovery_method]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        asset_name: str,
        asset_type: AssetType = AssetType.DOMAIN,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AssetDiscoveryAnalysis:
        analysis = AssetDiscoveryAnalysis(
            asset_name=asset_name,
            asset_type=asset_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "external_asset_discovery.analysis_added",
            asset_name=asset_name,
            asset_type=asset_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by asset_type; return count and avg risk_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.asset_type.value
            type_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for asset_type, scores in type_data.items():
            result[asset_type] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score < risk_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._risk_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "asset_name": r.asset_name,
                        "asset_type": r.asset_type.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
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

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AssetDiscoveryReport:
        by_asset_type: dict[str, int] = {}
        by_discovery_method: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_asset_type[r.asset_type.value] = by_asset_type.get(r.asset_type.value, 0) + 1
            by_discovery_method[r.discovery_method.value] = (
                by_discovery_method.get(r.discovery_method.value, 0) + 1
            )
            by_status[r.discovery_status.value] = by_status.get(r.discovery_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.risk_score < self._risk_threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["asset_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} asset(s) below risk threshold ({self._risk_threshold})")
        if self._records and avg_risk_score < self._risk_threshold:
            recs.append(f"Avg risk score {avg_risk_score} below threshold ({self._risk_threshold})")
        if not recs:
            recs.append("External asset discovery coverage is healthy")
        return AssetDiscoveryReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk_score,
            by_asset_type=by_asset_type,
            by_discovery_method=by_discovery_method,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("external_asset_discovery.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.asset_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_threshold": self._risk_threshold,
            "asset_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
