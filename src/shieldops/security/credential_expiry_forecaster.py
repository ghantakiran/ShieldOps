"""Credential Expiry Forecaster — unified expiry timeline
across all credential types with proactive renewal."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CredentialType(StrEnum):
    API_KEY = "api_key"
    SERVICE_ACCOUNT_TOKEN = "service_account_token"  # noqa: S105
    OAUTH_SECRET = "oauth_secret"  # noqa: S105
    DATABASE_PASSWORD = "database_password"  # noqa: S105
    TLS_PRIVATE_KEY = "tls_private_key"


class ExpiryStatus(StrEnum):
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    RENEWED = "renewed"
    REVOKED = "revoked"


class RenewalUrgency(StrEnum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EMERGENCY = "emergency"


# --- Models ---


class CredentialRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    credential_name: str = ""
    credential_type: CredentialType = CredentialType.API_KEY
    service_name: str = ""
    status: ExpiryStatus = ExpiryStatus.ACTIVE
    issued_at: float = Field(default_factory=time.time)
    expires_at: float = 0.0
    owner: str = ""
    created_at: float = Field(default_factory=time.time)


class RenewalForecast(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    credential_id: str = ""
    days_until_expiry: float = 0.0
    urgency: RenewalUrgency = RenewalUrgency.NONE
    recommended_renewal_date: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ExpiryReport(BaseModel):
    total_credentials: int = 0
    total_expired: int = 0
    total_expiring_soon: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_urgency: dict[str, int] = Field(default_factory=dict)
    urgent_renewals: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CredentialExpiryForecaster:
    """Unified expiry timeline across all credential types with proactive renewal windows."""

    def __init__(
        self,
        max_records: int = 200000,
        warning_days: int = 30,
    ) -> None:
        self._max_records = max_records
        self._warning_days = warning_days
        self._credentials: list[CredentialRecord] = []
        self._forecasts: list[RenewalForecast] = []
        logger.info(
            "credential_expiry_forecaster.initialized",
            max_records=max_records,
            warning_days=warning_days,
        )

    # -- register / get / list ---------------------------------------

    def register_credential(
        self,
        credential_name: str,
        credential_type: CredentialType = CredentialType.API_KEY,
        service_name: str = "",
        expires_at: float = 0.0,
        owner: str = "",
        **kw: Any,
    ) -> CredentialRecord:
        record = CredentialRecord(
            credential_name=credential_name,
            credential_type=credential_type,
            service_name=service_name,
            expires_at=expires_at,
            owner=owner,
            **kw,
        )
        self._credentials.append(record)
        if len(self._credentials) > self._max_records:
            self._credentials = self._credentials[-self._max_records :]
        logger.info(
            "credential_expiry_forecaster.credential_registered",
            credential_id=record.id,
            credential_name=credential_name,
        )
        return record

    def get_credential(self, credential_id: str) -> CredentialRecord | None:
        for c in self._credentials:
            if c.id == credential_id:
                return c
        return None

    def list_credentials(
        self,
        credential_type: CredentialType | None = None,
        status: ExpiryStatus | None = None,
        limit: int = 50,
    ) -> list[CredentialRecord]:
        results = list(self._credentials)
        if credential_type is not None:
            results = [r for r in results if r.credential_type == credential_type]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    # -- forecasts ---------------------------------------------------

    def forecast_renewal(
        self,
        credential_id: str,
    ) -> RenewalForecast | None:
        """Forecast renewal timeline for a credential."""
        cred = self.get_credential(credential_id)
        if cred is None:
            return None
        now = time.time()
        if cred.expires_at <= 0:
            days_until = float("inf")
            urgency = RenewalUrgency.NONE
        else:
            days_until = round((cred.expires_at - now) / 86400, 2)
            urgency = self._days_to_urgency(days_until)
        renewal_date = (
            cred.expires_at - (self._warning_days * 86400) if cred.expires_at > 0 else 0.0
        )
        forecast = RenewalForecast(
            credential_id=credential_id,
            days_until_expiry=days_until,
            urgency=urgency,
            recommended_renewal_date=renewal_date,
        )
        self._forecasts.append(forecast)
        if len(self._forecasts) > self._max_records:
            self._forecasts = self._forecasts[-self._max_records :]
        logger.info(
            "credential_expiry_forecaster.forecast_created",
            forecast_id=forecast.id,
            credential_id=credential_id,
        )
        return forecast

    def list_forecasts(
        self,
        credential_id: str | None = None,
        limit: int = 50,
    ) -> list[RenewalForecast]:
        results = list(self._forecasts)
        if credential_id is not None:
            results = [r for r in results if r.credential_id == credential_id]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def update_status(
        self,
        credential_id: str,
        status: ExpiryStatus,
    ) -> bool:
        cred = self.get_credential(credential_id)
        if cred is None:
            return False
        cred.status = status
        logger.info(
            "credential_expiry_forecaster.status_updated",
            credential_id=credential_id,
            status=status.value,
        )
        return True

    def find_expired_unrotated(self) -> list[CredentialRecord]:
        """Find credentials that have expired but not been renewed/revoked."""
        now = time.time()
        return [
            c
            for c in self._credentials
            if c.expires_at > 0
            and c.expires_at < now
            and c.status not in (ExpiryStatus.RENEWED, ExpiryStatus.REVOKED)
        ]

    def calculate_urgency(
        self,
        credential_id: str,
    ) -> dict[str, Any]:
        """Calculate renewal urgency for a credential."""
        cred = self.get_credential(credential_id)
        if cred is None:
            return {"found": False, "urgency": RenewalUrgency.NONE.value}
        now = time.time()
        if cred.expires_at <= 0:
            return {
                "found": True,
                "credential_id": credential_id,
                "urgency": RenewalUrgency.NONE.value,
                "reason": "No expiry date set",
            }
        days_until = (cred.expires_at - now) / 86400
        urgency = self._days_to_urgency(days_until)
        return {
            "found": True,
            "credential_id": credential_id,
            "days_until_expiry": round(days_until, 2),
            "urgency": urgency.value,
            "status": cred.status.value,
        }

    # -- report / stats ----------------------------------------------

    def generate_expiry_report(self) -> ExpiryReport:
        by_type: dict[str, int] = {}
        for c in self._credentials:
            key = c.credential_type.value
            by_type[key] = by_type.get(key, 0) + 1
        by_status: dict[str, int] = {}
        for c in self._credentials:
            key = c.status.value
            by_status[key] = by_status.get(key, 0) + 1
        by_urgency: dict[str, int] = {}
        for f in self._forecasts:
            key = f.urgency.value
            by_urgency[key] = by_urgency.get(key, 0) + 1
        expired = self.find_expired_unrotated()
        now = time.time()
        expiring_soon = [
            c
            for c in self._credentials
            if c.expires_at > 0
            and 0 < (c.expires_at - now) / 86400 <= self._warning_days
            and c.status == ExpiryStatus.ACTIVE
        ]
        urgent = [c.credential_name for c in expired[:5]]
        recs: list[str] = []
        if expired:
            recs.append(f"{len(expired)} credential(s) expired but not rotated")
        if expiring_soon:
            recs.append(
                f"{len(expiring_soon)} credential(s) expiring within {self._warning_days} days"
            )
        if not recs:
            recs.append("All credentials within acceptable lifecycle")
        return ExpiryReport(
            total_credentials=len(self._credentials),
            total_expired=len(expired),
            total_expiring_soon=len(expiring_soon),
            by_type=by_type,
            by_status=by_status,
            by_urgency=by_urgency,
            urgent_renewals=urgent,
            recommendations=recs,
        )

    def clear_data(self) -> int:
        count = len(self._credentials)
        self._credentials.clear()
        self._forecasts.clear()
        logger.info("credential_expiry_forecaster.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for c in self._credentials:
            key = c.credential_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_credentials": len(self._credentials),
            "total_forecasts": len(self._forecasts),
            "warning_days": self._warning_days,
            "type_distribution": type_dist,
        }

    # -- internal helpers --------------------------------------------

    def _days_to_urgency(self, days: float) -> RenewalUrgency:
        if days <= 0:
            return RenewalUrgency.EMERGENCY
        if days <= 7:
            return RenewalUrgency.HIGH
        if days <= 30:
            return RenewalUrgency.MODERATE
        if days <= 90:
            return RenewalUrgency.LOW
        return RenewalUrgency.NONE
