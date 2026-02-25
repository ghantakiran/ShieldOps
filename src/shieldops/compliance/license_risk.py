"""Dependency License Risk Analyzer — analyze transitive dependency license risks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LicenseCategory(StrEnum):
    PERMISSIVE = "permissive"
    WEAK_COPYLEFT = "weak_copyleft"
    STRONG_COPYLEFT = "strong_copyleft"
    PROPRIETARY = "proprietary"
    UNKNOWN = "unknown"


class CompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    CONDITIONAL = "conditional"
    INCOMPATIBLE = "incompatible"
    REQUIRES_REVIEW = "requires_review"
    UNASSESSED = "unassessed"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ACCEPTABLE = "acceptable"


# --- Models ---


class LicenseRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_name: str = ""
    version: str = ""
    license_name: str = ""
    category: LicenseCategory = LicenseCategory.UNKNOWN
    risk_level: RiskLevel = RiskLevel.MEDIUM
    transitive_depth: int = 0
    compatibility: CompatibilityStatus = CompatibilityStatus.UNASSESSED
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class LicenseConflict(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_a: str = ""
    package_b: str = ""
    license_a: str = ""
    license_b: str = ""
    conflict_reason: str = ""
    risk_level: RiskLevel = RiskLevel.HIGH
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class LicenseRiskReport(BaseModel):
    total_licenses: int = 0
    total_conflicts: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    copyleft_count: int = 0
    conflict_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyLicenseRiskAnalyzer:
    """Analyze transitive dependency license risks."""

    def __init__(
        self,
        max_records: int = 200000,
        max_transitive_depth: int = 5,
    ) -> None:
        self._max_records = max_records
        self._max_transitive_depth = max_transitive_depth
        self._records: list[LicenseRiskRecord] = []
        self._conflicts: list[LicenseConflict] = []
        logger.info(
            "license_risk.initialized",
            max_records=max_records,
            max_transitive_depth=max_transitive_depth,
        )

    # -- record / get / list -------------------------------------------------

    def record_license(
        self,
        package_name: str,
        version: str = "",
        license_name: str = "",
        category: LicenseCategory = LicenseCategory.UNKNOWN,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        transitive_depth: int = 0,
        compatibility: CompatibilityStatus = CompatibilityStatus.UNASSESSED,
        details: str = "",
    ) -> LicenseRiskRecord:
        record = LicenseRiskRecord(
            package_name=package_name,
            version=version,
            license_name=license_name,
            category=category,
            risk_level=risk_level,
            transitive_depth=transitive_depth,
            compatibility=compatibility,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "license_risk.license_recorded",
            record_id=record.id,
            package_name=package_name,
            category=category.value,
        )
        return record

    def get_license(self, record_id: str) -> LicenseRiskRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_licenses(
        self,
        package_name: str | None = None,
        category: LicenseCategory | None = None,
        limit: int = 50,
    ) -> list[LicenseRiskRecord]:
        results = list(self._records)
        if package_name is not None:
            results = [r for r in results if r.package_name == package_name]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    def record_conflict(
        self,
        package_a: str,
        package_b: str,
        license_a: str = "",
        license_b: str = "",
        conflict_reason: str = "",
        risk_level: RiskLevel = RiskLevel.HIGH,
        details: str = "",
    ) -> LicenseConflict:
        conflict = LicenseConflict(
            package_a=package_a,
            package_b=package_b,
            license_a=license_a,
            license_b=license_b,
            conflict_reason=conflict_reason,
            risk_level=risk_level,
            details=details,
        )
        self._conflicts.append(conflict)
        if len(self._conflicts) > self._max_records:
            self._conflicts = self._conflicts[-self._max_records :]
        logger.info(
            "license_risk.conflict_recorded",
            package_a=package_a,
            package_b=package_b,
        )
        return conflict

    # -- domain operations ---------------------------------------------------

    def analyze_license_risk(self, package_name: str) -> dict[str, Any]:
        """Analyze license risk for a specific package."""
        records = [r for r in self._records if r.package_name == package_name]
        if not records:
            return {"package_name": package_name, "status": "no_data"}
        latest = records[-1]
        return {
            "package_name": package_name,
            "license_name": latest.license_name,
            "category": latest.category.value,
            "risk_level": latest.risk_level.value,
            "transitive_depth": latest.transitive_depth,
            "compatibility": latest.compatibility.value,
        }

    def identify_copyleft_contamination(self) -> list[dict[str, Any]]:
        """Find packages with copyleft licenses."""
        copyleft = {LicenseCategory.WEAK_COPYLEFT, LicenseCategory.STRONG_COPYLEFT}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.category in copyleft:
                results.append(
                    {
                        "package_name": r.package_name,
                        "license_name": r.license_name,
                        "category": r.category.value,
                        "risk_level": r.risk_level.value,
                        "transitive_depth": r.transitive_depth,
                    }
                )
        results.sort(key=lambda x: x["transitive_depth"])
        return results

    def detect_license_conflicts(self) -> list[dict[str, Any]]:
        """Return all recorded license conflicts."""
        results: list[dict[str, Any]] = []
        for c in self._conflicts:
            results.append(
                {
                    "package_a": c.package_a,
                    "package_b": c.package_b,
                    "license_a": c.license_a,
                    "license_b": c.license_b,
                    "conflict_reason": c.conflict_reason,
                    "risk_level": c.risk_level.value,
                }
            )
        results.sort(
            key=lambda x: ["critical", "high", "medium", "low", "acceptable"].index(x["risk_level"])
        )
        return results

    def rank_by_risk(self) -> list[dict[str, Any]]:
        """Rank all packages by risk level."""
        risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "acceptable": 4}
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "package_name": r.package_name,
                    "license_name": r.license_name,
                    "risk_level": r.risk_level.value,
                    "category": r.category.value,
                }
            )
        results.sort(key=lambda x: risk_order.get(x["risk_level"], 99))
        return results

    # -- report / stats ------------------------------------------------------

    def generate_report(self) -> LicenseRiskReport:
        by_category: dict[str, int] = {}
        by_risk_level: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_risk_level[r.risk_level.value] = by_risk_level.get(r.risk_level.value, 0) + 1
        copyleft_cats = {LicenseCategory.WEAK_COPYLEFT, LicenseCategory.STRONG_COPYLEFT}
        copyleft_count = sum(1 for r in self._records if r.category in copyleft_cats)
        recs: list[str] = []
        if copyleft_count > 0:
            recs.append(f"{copyleft_count} package(s) with copyleft licenses detected")
        if len(self._conflicts) > 0:
            recs.append(f"{len(self._conflicts)} license conflict(s) detected")
        if not recs:
            recs.append("License risk profile meets targets")
        return LicenseRiskReport(
            total_licenses=len(self._records),
            total_conflicts=len(self._conflicts),
            by_category=by_category,
            by_risk_level=by_risk_level,
            copyleft_count=copyleft_count,
            conflict_count=len(self._conflicts),
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._conflicts.clear()
        logger.info("license_risk.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_licenses": len(self._records),
            "total_conflicts": len(self._conflicts),
            "max_transitive_depth": self._max_transitive_depth,
            "category_distribution": category_dist,
            "unique_packages": len({r.package_name for r in self._records}),
        }
