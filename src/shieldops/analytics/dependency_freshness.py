"""Dependency Freshness Monitor — dependency version tracking, staleness scoring, update urgency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class UpdateUrgency(StrEnum):
    CURRENT = "current"
    MINOR_BEHIND = "minor_behind"
    MAJOR_BEHIND = "major_behind"
    END_OF_LIFE = "end_of_life"
    SECURITY_UPDATE = "security_update"


class DependencyEcosystem(StrEnum):
    PIP = "pip"
    NPM = "npm"
    MAVEN = "maven"
    CARGO = "cargo"
    GO_MOD = "go_mod"
    NUGET = "nuget"


class FreshnessGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


# --- Models ---


class DependencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    package_name: str = ""
    current_version: str = ""
    latest_version: str = ""
    ecosystem: DependencyEcosystem = DependencyEcosystem.PIP
    service_name: str = ""
    urgency: UpdateUrgency = UpdateUrgency.CURRENT
    is_direct: bool = True
    has_security_advisory: bool = False
    created_at: float = Field(default_factory=time.time)


class FreshnessScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    total_dependencies: int = 0
    up_to_date_count: int = 0
    behind_count: int = 0
    eol_count: int = 0
    security_update_count: int = 0
    freshness_pct: float = 0.0
    grade: FreshnessGrade = FreshnessGrade.C
    calculated_at: float = Field(default_factory=time.time)


class FreshnessReport(BaseModel):
    total_dependencies: int = 0
    total_services: int = 0
    avg_freshness_pct: float = 0.0
    eol_count: int = 0
    security_update_count: int = 0
    ecosystem_distribution: dict[str, int] = Field(default_factory=dict)
    grade_distribution: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyFreshnessMonitor:
    """Track dependency version freshness, staleness scoring, and update urgency across services."""

    def __init__(
        self,
        max_dependencies: int = 200000,
        stale_version_threshold: int = 3,
    ) -> None:
        self._max_dependencies = max_dependencies
        self._stale_version_threshold = stale_version_threshold
        self._dependencies: list[DependencyRecord] = []
        logger.info(
            "dependency_freshness.initialized",
            max_dependencies=max_dependencies,
            stale_version_threshold=stale_version_threshold,
        )

    def register_dependency(
        self,
        package_name: str,
        current_version: str,
        latest_version: str,
        ecosystem: DependencyEcosystem = DependencyEcosystem.PIP,
        service_name: str = "",
        urgency: UpdateUrgency = UpdateUrgency.CURRENT,
        is_direct: bool = True,
        has_security_advisory: bool = False,
    ) -> DependencyRecord:
        """Register a dependency with its current and latest version information."""
        record = DependencyRecord(
            package_name=package_name,
            current_version=current_version,
            latest_version=latest_version,
            ecosystem=ecosystem,
            service_name=service_name,
            urgency=urgency,
            is_direct=is_direct,
            has_security_advisory=has_security_advisory,
        )
        self._dependencies.append(record)
        if len(self._dependencies) > self._max_dependencies:
            self._dependencies = self._dependencies[-self._max_dependencies :]
        logger.info(
            "dependency_freshness.dependency_registered",
            dep_id=record.id,
            package_name=package_name,
            ecosystem=ecosystem,
            service_name=service_name,
            urgency=urgency,
        )
        return record

    def get_dependency(self, dep_id: str) -> DependencyRecord | None:
        """Retrieve a single dependency record by ID."""
        for d in self._dependencies:
            if d.id == dep_id:
                return d
        return None

    def list_dependencies(
        self,
        ecosystem: DependencyEcosystem | None = None,
        urgency: UpdateUrgency | None = None,
        service_name: str | None = None,
        limit: int = 100,
    ) -> list[DependencyRecord]:
        """List dependencies with optional filtering."""
        results = list(self._dependencies)
        if ecosystem is not None:
            results = [d for d in results if d.ecosystem == ecosystem]
        if urgency is not None:
            results = [d for d in results if d.urgency == urgency]
        if service_name is not None:
            results = [d for d in results if d.service_name == service_name]
        return results[-limit:]

    def calculate_freshness_score(self, service_name: str) -> FreshnessScore:
        """Compute the freshness score for all dependencies of a service.

        Grading thresholds based on freshness percentage (up-to-date / total):
            >= 90% -> A
            >= 75% -> B
            >= 60% -> C
            >= 40% -> D
            < 40%  -> F
        """
        deps = [d for d in self._dependencies if d.service_name == service_name]
        total = len(deps)
        if total == 0:
            return FreshnessScore(service_name=service_name)

        up_to_date = sum(1 for d in deps if d.urgency == UpdateUrgency.CURRENT)
        behind = sum(
            1 for d in deps if d.urgency in (UpdateUrgency.MINOR_BEHIND, UpdateUrgency.MAJOR_BEHIND)
        )
        eol = sum(1 for d in deps if d.urgency == UpdateUrgency.END_OF_LIFE)
        security = sum(
            1 for d in deps if d.urgency == UpdateUrgency.SECURITY_UPDATE or d.has_security_advisory
        )

        freshness_pct = round(up_to_date / total * 100, 2)

        if freshness_pct >= 90.0:
            grade = FreshnessGrade.A
        elif freshness_pct >= 75.0:
            grade = FreshnessGrade.B
        elif freshness_pct >= 60.0:
            grade = FreshnessGrade.C
        elif freshness_pct >= 40.0:
            grade = FreshnessGrade.D
        else:
            grade = FreshnessGrade.F

        score = FreshnessScore(
            service_name=service_name,
            total_dependencies=total,
            up_to_date_count=up_to_date,
            behind_count=behind,
            eol_count=eol,
            security_update_count=security,
            freshness_pct=freshness_pct,
            grade=grade,
        )
        logger.info(
            "dependency_freshness.score_calculated",
            service_name=service_name,
            freshness_pct=freshness_pct,
            grade=grade.value,
            total=total,
        )
        return score

    def detect_eol_dependencies(self) -> list[DependencyRecord]:
        """Return all dependencies marked as end-of-life."""
        eol = [d for d in self._dependencies if d.urgency == UpdateUrgency.END_OF_LIFE]
        logger.info(
            "dependency_freshness.eol_detected",
            eol_count=len(eol),
        )
        return eol

    def identify_security_updates(self) -> list[DependencyRecord]:
        """Return dependencies that require security updates.

        Includes both those explicitly marked as SECURITY_UPDATE urgency and those
        with an active security advisory flag.
        """
        security = [
            d
            for d in self._dependencies
            if d.urgency == UpdateUrgency.SECURITY_UPDATE or d.has_security_advisory
        ]
        logger.info(
            "dependency_freshness.security_updates_identified",
            count=len(security),
        )
        return security

    def rank_services_by_freshness(self) -> list[FreshnessScore]:
        """Calculate freshness scores for all services, sorted by freshness_pct descending."""
        service_names: set[str] = {d.service_name for d in self._dependencies}
        scores: list[FreshnessScore] = []
        for svc in service_names:
            score = self.calculate_freshness_score(svc)
            scores.append(score)
        scores.sort(key=lambda s: s.freshness_pct, reverse=True)
        return scores

    def analyze_ecosystem_health(self) -> list[dict[str, Any]]:
        """Analyze dependency health per ecosystem.

        For each ecosystem, computes total dependency count, how many are up-to-date,
        the freshness percentage, and counts of EOL and security-advisory dependencies.
        """
        eco_data: dict[str, dict[str, int]] = {}
        for d in self._dependencies:
            eco = d.ecosystem.value
            if eco not in eco_data:
                eco_data[eco] = {
                    "total": 0,
                    "up_to_date": 0,
                    "eol": 0,
                    "security": 0,
                }
            eco_data[eco]["total"] += 1
            if d.urgency == UpdateUrgency.CURRENT:
                eco_data[eco]["up_to_date"] += 1
            if d.urgency == UpdateUrgency.END_OF_LIFE:
                eco_data[eco]["eol"] += 1
            if d.urgency == UpdateUrgency.SECURITY_UPDATE or d.has_security_advisory:
                eco_data[eco]["security"] += 1

        results: list[dict[str, Any]] = []
        for eco, data in eco_data.items():
            total = data["total"]
            up_to_date = data["up_to_date"]
            freshness_pct = round(up_to_date / total * 100, 2) if total > 0 else 0.0
            results.append(
                {
                    "ecosystem": eco,
                    "total_dependencies": total,
                    "up_to_date_count": up_to_date,
                    "freshness_pct": freshness_pct,
                    "eol_count": data["eol"],
                    "security_advisory_count": data["security"],
                }
            )

        results.sort(key=lambda x: x["freshness_pct"], reverse=True)
        return results

    def generate_freshness_report(self) -> FreshnessReport:
        """Generate a comprehensive dependency freshness report."""
        total = len(self._dependencies)
        service_names: set[str] = {d.service_name for d in self._dependencies}
        total_services = len(service_names)

        # Global EOL and security counts
        eol_count = sum(1 for d in self._dependencies if d.urgency == UpdateUrgency.END_OF_LIFE)
        security_count = sum(
            1
            for d in self._dependencies
            if d.urgency == UpdateUrgency.SECURITY_UPDATE or d.has_security_advisory
        )

        # Ecosystem distribution
        eco_dist: dict[str, int] = {}
        for d in self._dependencies:
            key = d.ecosystem.value
            eco_dist[key] = eco_dist.get(key, 0) + 1

        # Per-service scores and grade distribution
        scores = self.rank_services_by_freshness()
        grade_dist: dict[str, int] = {}
        for s in scores:
            key = s.grade.value
            grade_dist[key] = grade_dist.get(key, 0) + 1

        avg_freshness = (
            round(sum(s.freshness_pct for s in scores) / len(scores), 2) if scores else 0.0
        )

        # Build recommendations
        recommendations: list[str] = []
        if security_count > 0:
            recommendations.append(
                f"{security_count} dependency(ies) have security advisories — "
                f"prioritize patching immediately"
            )

        if eol_count > 0:
            recommendations.append(
                f"{eol_count} dependency(ies) are end-of-life — migrate to supported alternatives"
            )

        f_grade_count = grade_dist.get(FreshnessGrade.F.value, 0)
        d_grade_count = grade_dist.get(FreshnessGrade.D.value, 0)
        if f_grade_count > 0:
            recommendations.append(
                f"{f_grade_count} service(s) have grade F freshness — "
                f"schedule bulk dependency updates"
            )
        if d_grade_count > 0:
            recommendations.append(
                f"{d_grade_count} service(s) have grade D freshness — plan incremental updates"
            )

        eco_health = self.analyze_ecosystem_health()
        for eco in eco_health:
            if eco["freshness_pct"] < 50.0 and eco["total_dependencies"] > 5:
                recommendations.append(
                    f"{eco['ecosystem']} ecosystem has {eco['freshness_pct']}% freshness — "
                    f"review update strategy for this ecosystem"
                )

        major_behind = sum(1 for d in self._dependencies if d.urgency == UpdateUrgency.MAJOR_BEHIND)
        if major_behind > self._stale_version_threshold:
            recommendations.append(
                f"{major_behind} dependency(ies) are a major version behind — "
                f"evaluate breaking changes and plan upgrades"
            )

        report = FreshnessReport(
            total_dependencies=total,
            total_services=total_services,
            avg_freshness_pct=avg_freshness,
            eol_count=eol_count,
            security_update_count=security_count,
            ecosystem_distribution=eco_dist,
            grade_distribution=grade_dist,
            recommendations=recommendations,
        )
        logger.info(
            "dependency_freshness.report_generated",
            total_dependencies=total,
            total_services=total_services,
            avg_freshness_pct=avg_freshness,
            eol_count=eol_count,
            security_count=security_count,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored dependencies."""
        self._dependencies.clear()
        logger.info("dependency_freshness.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about stored dependencies."""
        ecosystems: dict[str, int] = {}
        urgencies: dict[str, int] = {}
        services: set[str] = set()
        direct_count = 0
        transitive_count = 0
        for d in self._dependencies:
            ecosystems[d.ecosystem.value] = ecosystems.get(d.ecosystem.value, 0) + 1
            urgencies[d.urgency.value] = urgencies.get(d.urgency.value, 0) + 1
            services.add(d.service_name)
            if d.is_direct:
                direct_count += 1
            else:
                transitive_count += 1
        return {
            "total_dependencies": len(self._dependencies),
            "unique_services": len(services),
            "direct_count": direct_count,
            "transitive_count": transitive_count,
            "ecosystem_distribution": ecosystems,
            "urgency_distribution": urgencies,
        }
