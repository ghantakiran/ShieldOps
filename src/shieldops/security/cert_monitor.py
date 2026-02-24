"""Certificate Expiry Monitor — TLS/SSL certificate inventory, expiry tracking, renewal alerts."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CertificateType(StrEnum):
    TLS = "tls"
    CODE_SIGNING = "code_signing"
    CLIENT_AUTH = "client_auth"
    CA_ROOT = "ca_root"
    INTERMEDIATE = "intermediate"
    SELF_SIGNED = "self_signed"


class CertStatus(StrEnum):
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class RenewalPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# --- Models ---


class CertificateRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain: str = ""
    cert_type: CertificateType = CertificateType.TLS
    issuer: str = ""
    issued_at: float = Field(default_factory=time.time)
    expires_at: float = 0.0
    status: CertStatus = CertStatus.UNKNOWN
    auto_renew: bool = False
    created_at: float = Field(default_factory=time.time)


class RenewalAlert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    certificate_id: str = ""
    domain: str = ""
    days_until_expiry: int = 0
    priority: RenewalPriority = RenewalPriority.LOW
    acknowledged: bool = False
    created_at: float = Field(default_factory=time.time)


class CertInventorySummary(BaseModel):
    total_certificates: int = 0
    valid_count: int = 0
    expiring_soon_count: int = 0
    expired_count: int = 0
    revoked_count: int = 0
    auto_renew_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CertificateExpiryMonitor:
    """TLS/SSL certificate inventory, expiry tracking, and renewal alerting."""

    def __init__(
        self,
        max_certificates: int = 50000,
        expiry_warning_days: int = 30,
    ) -> None:
        self._max_certificates = max_certificates
        self._expiry_warning_days = expiry_warning_days
        self._certificates: list[CertificateRecord] = []
        self._alerts: list[RenewalAlert] = []
        logger.info(
            "cert_monitor.initialized",
            max_certificates=max_certificates,
            expiry_warning_days=expiry_warning_days,
        )

    def register_certificate(
        self,
        domain: str,
        cert_type: CertificateType,
        issuer: str = "",
        expires_at: float = 0.0,
        auto_renew: bool = False,
    ) -> CertificateRecord:
        now = time.time()
        if expires_at < now and expires_at > 0:
            status = CertStatus.EXPIRED
        elif 0 < expires_at <= now + self._expiry_warning_days * 86400:
            status = CertStatus.EXPIRING_SOON
        elif expires_at > 0:
            status = CertStatus.VALID
        else:
            status = CertStatus.UNKNOWN
        cert = CertificateRecord(
            domain=domain,
            cert_type=cert_type,
            issuer=issuer,
            expires_at=expires_at,
            status=status,
            auto_renew=auto_renew,
        )
        self._certificates.append(cert)
        if len(self._certificates) > self._max_certificates:
            self._certificates = self._certificates[-self._max_certificates :]
        logger.info(
            "cert_monitor.certificate_registered",
            cert_id=cert.id,
            domain=domain,
            cert_type=cert_type,
            status=status,
        )
        return cert

    def get_certificate(self, cert_id: str) -> CertificateRecord | None:
        for c in self._certificates:
            if c.id == cert_id:
                return c
        return None

    def list_certificates(
        self,
        cert_type: CertificateType | None = None,
        status: CertStatus | None = None,
        limit: int = 100,
    ) -> list[CertificateRecord]:
        results = list(self._certificates)
        if cert_type is not None:
            results = [c for c in results if c.cert_type == cert_type]
        if status is not None:
            results = [c for c in results if c.status == status]
        return results[-limit:]

    def check_expiring(
        self,
        days_ahead: int | None = None,
    ) -> list[RenewalAlert]:
        window_days = days_ahead if days_ahead is not None else self._expiry_warning_days
        now = time.time()
        threshold = now + window_days * 86400
        alerts: list[RenewalAlert] = []
        for cert in self._certificates:
            if cert.status == CertStatus.REVOKED:
                continue
            if cert.expires_at <= 0:
                continue
            if cert.expires_at > threshold:
                continue
            days_remaining = int((cert.expires_at - now) / 86400)
            if days_remaining <= 7:
                priority = RenewalPriority.CRITICAL
            elif days_remaining <= 14:
                priority = RenewalPriority.HIGH
            elif days_remaining <= 30:
                priority = RenewalPriority.MEDIUM
            else:
                priority = RenewalPriority.LOW
            alert = RenewalAlert(
                certificate_id=cert.id,
                domain=cert.domain,
                days_until_expiry=max(days_remaining, 0),
                priority=priority,
            )
            alerts.append(alert)
            self._alerts.append(alert)
        logger.info(
            "cert_monitor.expiring_checked",
            window_days=window_days,
            alerts_created=len(alerts),
        )
        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        for a in self._alerts:
            if a.id == alert_id:
                a.acknowledged = True
                logger.info(
                    "cert_monitor.alert_acknowledged",
                    alert_id=alert_id,
                )
                return True
        return False

    def renew_certificate(self, cert_id: str, new_expires_at: float) -> bool:
        cert = self.get_certificate(cert_id)
        if cert is None:
            return False
        cert.expires_at = new_expires_at
        cert.status = CertStatus.VALID
        logger.info(
            "cert_monitor.certificate_renewed",
            cert_id=cert_id,
            domain=cert.domain,
            new_expires_at=new_expires_at,
        )
        return True

    def revoke_certificate(self, cert_id: str) -> bool:
        cert = self.get_certificate(cert_id)
        if cert is None:
            return False
        cert.status = CertStatus.REVOKED
        logger.info(
            "cert_monitor.certificate_revoked",
            cert_id=cert_id,
            domain=cert.domain,
        )
        return True

    def generate_inventory_summary(self) -> CertInventorySummary:
        valid = sum(1 for c in self._certificates if c.status == CertStatus.VALID)
        expiring = sum(1 for c in self._certificates if c.status == CertStatus.EXPIRING_SOON)
        expired = sum(1 for c in self._certificates if c.status == CertStatus.EXPIRED)
        revoked = sum(1 for c in self._certificates if c.status == CertStatus.REVOKED)
        auto_renew = sum(1 for c in self._certificates if c.auto_renew)
        recommendations: list[str] = []
        if expired > 0:
            recommendations.append(
                f"{expired} certificate(s) expired — renew or remove immediately"
            )
        if expiring > 0:
            recommendations.append(f"{expiring} certificate(s) expiring soon — schedule renewals")
        non_auto = len(self._certificates) - auto_renew
        if non_auto > 0:
            recommendations.append(
                f"{non_auto} certificate(s) without auto-renewal — consider enabling"
            )
        logger.info(
            "cert_monitor.inventory_summary_generated",
            total=len(self._certificates),
            valid=valid,
            expiring=expiring,
            expired=expired,
        )
        return CertInventorySummary(
            total_certificates=len(self._certificates),
            valid_count=valid,
            expiring_soon_count=expiring,
            expired_count=expired,
            revoked_count=revoked,
            auto_renew_count=auto_renew,
            recommendations=recommendations,
        )

    def delete_certificate(self, cert_id: str) -> bool:
        for i, c in enumerate(self._certificates):
            if c.id == cert_id:
                self._certificates.pop(i)
                logger.info(
                    "cert_monitor.certificate_deleted",
                    cert_id=cert_id,
                )
                return True
        return False

    def clear_data(self) -> None:
        self._certificates.clear()
        self._alerts.clear()
        logger.info("cert_monitor.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        domains = {c.domain for c in self._certificates}
        status_counts: dict[str, int] = {}
        for c in self._certificates:
            status_counts[c.status] = status_counts.get(c.status, 0) + 1
        return {
            "total_certificates": len(self._certificates),
            "total_alerts": len(self._alerts),
            "unique_domains": len(domains),
            "status_distribution": status_counts,
            "auto_renew_count": sum(1 for c in self._certificates if c.auto_renew),
        }
