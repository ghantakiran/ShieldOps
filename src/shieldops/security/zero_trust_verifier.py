"""Zero Trust Verifier — continuous trust verification and micro-segmentation compliance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VerificationType(StrEnum):
    IDENTITY = "identity"
    DEVICE = "device"
    NETWORK = "network"
    APPLICATION = "application"
    DATA = "data"


class TrustLevel(StrEnum):
    FULLY_TRUSTED = "fully_trusted"
    CONDITIONALLY_TRUSTED = "conditionally_trusted"
    LIMITED = "limited"
    UNTRUSTED = "untrusted"
    BLOCKED = "blocked"


class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    EXEMPT = "exempt"
    PENDING_REVIEW = "pending_review"


# --- Models ---


class VerificationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    verification_type: VerificationType = VerificationType.IDENTITY
    trust_level: TrustLevel = TrustLevel.CONDITIONALLY_TRUSTED
    compliance_status: ComplianceStatus = ComplianceStatus.PENDING_REVIEW
    trust_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class TrustPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    verification_type: VerificationType = VerificationType.NETWORK
    trust_level: TrustLevel = TrustLevel.LIMITED
    min_trust_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ZeroTrustReport(BaseModel):
    total_verifications: int = 0
    total_policies: int = 0
    compliance_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_trust_level: dict[str, int] = Field(default_factory=dict)
    non_compliant_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ZeroTrustVerifier:
    """Continuous trust verification and micro-segmentation compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        min_trust_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_trust_score = min_trust_score
        self._records: list[VerificationRecord] = []
        self._policies: list[TrustPolicy] = []
        logger.info(
            "zero_trust.initialized",
            max_records=max_records,
            min_trust_score=min_trust_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_verification(
        self,
        service_name: str,
        verification_type: VerificationType = VerificationType.IDENTITY,
        trust_level: TrustLevel = TrustLevel.CONDITIONALLY_TRUSTED,
        compliance_status: ComplianceStatus = ComplianceStatus.PENDING_REVIEW,
        trust_score: float = 0.0,
        details: str = "",
    ) -> VerificationRecord:
        record = VerificationRecord(
            service_name=service_name,
            verification_type=verification_type,
            trust_level=trust_level,
            compliance_status=compliance_status,
            trust_score=trust_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "zero_trust.verification_recorded",
            record_id=record.id,
            service_name=service_name,
            verification_type=verification_type.value,
            trust_level=trust_level.value,
        )
        return record

    def get_verification(self, record_id: str) -> VerificationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_verifications(
        self,
        service_name: str | None = None,
        verification_type: VerificationType | None = None,
        limit: int = 50,
    ) -> list[VerificationRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if verification_type is not None:
            results = [r for r in results if r.verification_type == verification_type]
        return results[-limit:]

    def add_policy(
        self,
        policy_name: str,
        verification_type: VerificationType = VerificationType.NETWORK,
        trust_level: TrustLevel = TrustLevel.LIMITED,
        min_trust_score: float = 0.0,
    ) -> TrustPolicy:
        policy = TrustPolicy(
            policy_name=policy_name,
            verification_type=verification_type,
            trust_level=trust_level,
            min_trust_score=min_trust_score,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "zero_trust.policy_added",
            policy_name=policy_name,
            verification_type=verification_type.value,
            trust_level=trust_level.value,
        )
        return policy

    # -- domain operations -----------------------------------------------

    def analyze_service_trust(self, service_name: str) -> dict[str, Any]:
        """Analyze trust posture for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        compliant = sum(1 for r in records if r.compliance_status == ComplianceStatus.COMPLIANT)
        compliance_rate = round(compliant / len(records) * 100, 2)
        avg_trust = round(sum(r.trust_score for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "total_verifications": len(records),
            "compliant_count": compliant,
            "compliance_rate_pct": compliance_rate,
            "avg_trust_score": avg_trust,
            "meets_threshold": avg_trust >= self._min_trust_score,
        }

    def identify_untrusted_services(self) -> list[dict[str, Any]]:
        """Find services with untrusted or blocked trust levels."""
        untrusted_counts: dict[str, int] = {}
        for r in self._records:
            if r.trust_level in (TrustLevel.UNTRUSTED, TrustLevel.BLOCKED):
                untrusted_counts[r.service_name] = untrusted_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in untrusted_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "untrusted_count": count,
                    }
                )
        results.sort(key=lambda x: x["untrusted_count"], reverse=True)
        return results

    def rank_by_trust_score(self) -> list[dict[str, Any]]:
        """Rank services by average trust score descending."""
        totals: dict[str, list[float]] = {}
        for r in self._records:
            totals.setdefault(r.service_name, []).append(r.trust_score)
        results: list[dict[str, Any]] = []
        for svc, scores in totals.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_trust_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_trust_score"], reverse=True)
        return results

    def detect_trust_violations(self) -> list[dict[str, Any]]:
        """Detect services with >3 non-compliant verifications."""
        svc_non_compliant: dict[str, int] = {}
        for r in self._records:
            if r.compliance_status == ComplianceStatus.NON_COMPLIANT:
                svc_non_compliant[r.service_name] = svc_non_compliant.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_non_compliant.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "non_compliant_count": count,
                        "violation_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_compliant_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ZeroTrustReport:
        by_type: dict[str, int] = {}
        by_trust_level: dict[str, int] = {}
        for r in self._records:
            by_type[r.verification_type.value] = by_type.get(r.verification_type.value, 0) + 1
            by_trust_level[r.trust_level.value] = by_trust_level.get(r.trust_level.value, 0) + 1
        compliant_count = sum(
            1 for r in self._records if r.compliance_status == ComplianceStatus.COMPLIANT
        )
        compliance_rate = (
            round(compliant_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        non_compliant = sum(
            1 for r in self._records if r.compliance_status == ComplianceStatus.NON_COMPLIANT
        )
        recs: list[str] = []
        avg_score = (
            round(sum(r.trust_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        if avg_score < self._min_trust_score:
            recs.append(
                f"Average trust score {avg_score} is below {self._min_trust_score} threshold"
            )
        untrusted = sum(1 for d in self.identify_untrusted_services())
        if untrusted > 0:
            recs.append(f"{untrusted} service(s) with untrusted status")
        violations = len(self.detect_trust_violations())
        if violations > 0:
            recs.append(f"{violations} service(s) with trust violations")
        if not recs:
            recs.append("Zero trust posture meets targets")
        return ZeroTrustReport(
            total_verifications=len(self._records),
            total_policies=len(self._policies),
            compliance_rate_pct=compliance_rate,
            by_type=by_type,
            by_trust_level=by_trust_level,
            non_compliant_count=non_compliant,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("zero_trust.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.verification_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_verifications": len(self._records),
            "total_policies": len(self._policies),
            "min_trust_score": self._min_trust_score,
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
