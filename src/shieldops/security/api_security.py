"""API Security Monitor — endpoint risk scoring, suspicious access detection, data exposure."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThreatType(StrEnum):
    CREDENTIAL_STUFFING = "credential_stuffing"
    RATE_ABUSE = "rate_abuse"
    DATA_EXFILTRATION = "data_exfiltration"
    INJECTION_ATTEMPT = "injection_attempt"
    BROKEN_AUTH = "broken_auth"
    ENUMERATION = "enumeration"


class RiskLevel(StrEnum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MonitoringMode(StrEnum):
    PASSIVE = "passive"
    ACTIVE = "active"
    BLOCKING = "blocking"


# --- Models ---


class APIEndpointProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    path: str = ""
    method: str = "GET"
    service: str = ""
    risk_level: RiskLevel = RiskLevel.SAFE
    monitoring_mode: MonitoringMode = MonitoringMode.PASSIVE
    total_requests: int = 0
    suspicious_requests: int = 0
    last_assessed: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class SecurityAlert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    endpoint_id: str = ""
    threat_type: ThreatType = ThreatType.RATE_ABUSE
    risk_level: RiskLevel = RiskLevel.LOW
    source_ip: str = ""
    description: str = ""
    acknowledged: bool = False
    created_at: float = Field(default_factory=time.time)


class ThreatAssessment(BaseModel):
    endpoint_id: str = ""
    path: str = ""
    overall_risk: RiskLevel = RiskLevel.SAFE
    threat_types: list[ThreatType] = Field(default_factory=list)
    suspicious_pct: float = 0.0
    recommendation: str = ""


# --- Engine ---


class APISecurityMonitor:
    """API endpoint risk scoring, suspicious access pattern detection, data exposure monitoring."""

    def __init__(
        self,
        max_endpoints: int = 50000,
        alert_threshold: float = 0.75,
    ) -> None:
        self._max_endpoints = max_endpoints
        self._alert_threshold = alert_threshold
        self._endpoints: list[APIEndpointProfile] = []
        self._alerts: list[SecurityAlert] = []
        self._requests: list[dict[str, Any]] = []
        logger.info(
            "api_security.initialized",
            max_endpoints=max_endpoints,
            alert_threshold=alert_threshold,
        )

    def register_endpoint(
        self,
        path: str,
        method: str = "GET",
        service: str = "",
        monitoring_mode: MonitoringMode = MonitoringMode.PASSIVE,
    ) -> APIEndpointProfile:
        ep = APIEndpointProfile(
            path=path,
            method=method,
            service=service,
            monitoring_mode=monitoring_mode,
        )
        self._endpoints.append(ep)
        if len(self._endpoints) > self._max_endpoints:
            self._endpoints = self._endpoints[-self._max_endpoints :]
        logger.info(
            "api_security.endpoint_registered",
            endpoint_id=ep.id,
            path=path,
            method=method,
        )
        return ep

    def get_endpoint(self, endpoint_id: str) -> APIEndpointProfile | None:
        for ep in self._endpoints:
            if ep.id == endpoint_id:
                return ep
        return None

    def list_endpoints(
        self,
        service: str | None = None,
        risk_level: RiskLevel | None = None,
        limit: int = 100,
    ) -> list[APIEndpointProfile]:
        results = list(self._endpoints)
        if service is not None:
            results = [ep for ep in results if ep.service == service]
        if risk_level is not None:
            results = [ep for ep in results if ep.risk_level == risk_level]
        return results[-limit:]

    def report_request(
        self,
        endpoint_id: str,
        source_ip: str = "",
        suspicious: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ep = self.get_endpoint(endpoint_id)
        if ep is None:
            return {"error": "endpoint_not_found"}
        ep.total_requests += 1
        if suspicious:
            ep.suspicious_requests += 1
        req = {
            "endpoint_id": endpoint_id,
            "source_ip": source_ip,
            "suspicious": suspicious,
            "metadata": metadata or {},
            "reported_at": time.time(),
        }
        self._requests.append(req)
        # Update risk level based on suspicious ratio
        if ep.total_requests > 0:
            ratio = ep.suspicious_requests / ep.total_requests
            if ratio > 0.5:
                ep.risk_level = RiskLevel.CRITICAL
            elif ratio > 0.3:
                ep.risk_level = RiskLevel.HIGH
            elif ratio > 0.1:
                ep.risk_level = RiskLevel.MEDIUM
            elif ratio > 0.05:
                ep.risk_level = RiskLevel.LOW
            else:
                ep.risk_level = RiskLevel.SAFE
        return {"endpoint_id": endpoint_id, "total_requests": ep.total_requests}

    def detect_threats(self, endpoint_id: str | None = None) -> list[SecurityAlert]:
        targets = self._endpoints
        if endpoint_id:
            targets = [ep for ep in targets if ep.id == endpoint_id]
        new_alerts: list[SecurityAlert] = []
        for ep in targets:
            if ep.total_requests == 0:
                continue
            ratio = ep.suspicious_requests / ep.total_requests
            if ratio >= self._alert_threshold:
                alert = SecurityAlert(
                    endpoint_id=ep.id,
                    threat_type=ThreatType.RATE_ABUSE,
                    risk_level=RiskLevel.CRITICAL if ratio > 0.9 else RiskLevel.HIGH,
                    description=f"High suspicious ratio: {ratio:.1%} on {ep.path}",
                )
                new_alerts.append(alert)
                self._alerts.append(alert)
            # Check for potential credential stuffing on auth endpoints
            is_auth = "auth" in ep.path.lower() or "login" in ep.path.lower()
            if is_auth and ep.suspicious_requests > 10:
                alert = SecurityAlert(
                    endpoint_id=ep.id,
                    threat_type=ThreatType.CREDENTIAL_STUFFING,
                    risk_level=RiskLevel.HIGH,
                    description=f"Potential credential stuffing on {ep.path}",
                )
                new_alerts.append(alert)
                self._alerts.append(alert)
        return new_alerts

    def get_alerts(
        self,
        endpoint_id: str | None = None,
        threat_type: ThreatType | None = None,
        limit: int = 100,
    ) -> list[SecurityAlert]:
        results = list(self._alerts)
        if endpoint_id is not None:
            results = [a for a in results if a.endpoint_id == endpoint_id]
        if threat_type is not None:
            results = [a for a in results if a.threat_type == threat_type]
        return results[-limit:]

    def acknowledge_alert(self, alert_id: str) -> bool:
        for a in self._alerts:
            if a.id == alert_id:
                a.acknowledged = True
                return True
        return False

    def get_risk_score(self, endpoint_id: str) -> dict[str, Any] | None:
        ep = self.get_endpoint(endpoint_id)
        if ep is None:
            return None
        ratio = ep.suspicious_requests / ep.total_requests if ep.total_requests > 0 else 0.0
        return {
            "endpoint_id": ep.id,
            "path": ep.path,
            "risk_level": ep.risk_level.value,
            "suspicious_ratio": round(ratio, 3),
            "total_requests": ep.total_requests,
        }

    def get_top_threats(self, limit: int = 10) -> list[dict[str, Any]]:
        threat_counts: dict[str, int] = {}
        for a in self._alerts:
            threat_counts[a.threat_type] = threat_counts.get(a.threat_type, 0) + 1
        sorted_threats = sorted(threat_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"threat_type": t, "count": c} for t, c in sorted_threats[:limit]]

    def get_stats(self) -> dict[str, Any]:
        risk_counts: dict[str, int] = {}
        total_requests = 0
        total_suspicious = 0
        for ep in self._endpoints:
            risk_counts[ep.risk_level] = risk_counts.get(ep.risk_level, 0) + 1
            total_requests += ep.total_requests
            total_suspicious += ep.suspicious_requests
        return {
            "total_endpoints": len(self._endpoints),
            "total_alerts": len(self._alerts),
            "unacknowledged_alerts": sum(1 for a in self._alerts if not a.acknowledged),
            "total_requests": total_requests,
            "total_suspicious": total_suspicious,
            "risk_distribution": risk_counts,
        }
