"""Team Skill Matrix — map skills, identify gaps, plan training."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SkillLevel(StrEnum):
    NOVICE = "novice"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SkillDomain(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    OBSERVABILITY = "observability"
    SECURITY = "security"
    DATABASE = "database"
    NETWORKING = "networking"


class GapSeverity(StrEnum):
    COVERED = "covered"
    THIN = "thin"
    AT_RISK = "at_risk"
    CRITICAL_GAP = "critical_gap"
    NO_COVERAGE = "no_coverage"


# --- Models ---


_LEVEL_SCORES: dict[SkillLevel, int] = {
    SkillLevel.NOVICE: 1,
    SkillLevel.BEGINNER: 2,
    SkillLevel.INTERMEDIATE: 3,
    SkillLevel.ADVANCED: 4,
    SkillLevel.EXPERT: 5,
}


class SkillEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    member_name: str = ""
    team: str = ""
    skill_name: str = ""
    domain: SkillDomain = SkillDomain.INFRASTRUCTURE
    level: SkillLevel = SkillLevel.NOVICE
    last_assessed: float = Field(default_factory=time.time)
    certifications: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class SkillGap(BaseModel):
    domain: SkillDomain = SkillDomain.INFRASTRUCTURE
    skill_name: str = ""
    required_level: SkillLevel = SkillLevel.INTERMEDIATE
    current_max_level: SkillLevel = SkillLevel.NOVICE
    gap_severity: GapSeverity = GapSeverity.NO_COVERAGE
    team: str = ""
    members_with_skill: int = 0
    created_at: float = Field(default_factory=time.time)


class SkillMatrixReport(BaseModel):
    total_members: int = 0
    total_skills: int = 0
    total_gaps: int = 0
    avg_skill_level: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    critical_gaps: list[str] = Field(default_factory=list)
    training_recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamSkillMatrix:
    """Map team members to skills, identify gaps, plan training."""

    def __init__(
        self,
        max_entries: int = 100000,
        min_coverage_per_domain: int = 2,
    ) -> None:
        self._max_entries = max_entries
        self._min_coverage_per_domain = min_coverage_per_domain
        self._items: list[SkillEntry] = []
        self._gaps: dict[str, SkillGap] = {}
        logger.info(
            "team_skill_matrix.initialized",
            max_entries=max_entries,
            min_coverage_per_domain=(min_coverage_per_domain),
        )

    # -- CRUD -------------------------------------------------------

    def register_skill(
        self,
        member_name: str,
        team: str = "",
        skill_name: str = "",
        domain: SkillDomain = (SkillDomain.INFRASTRUCTURE),
        level: SkillLevel = SkillLevel.NOVICE,
        certifications: list[str] | None = None,
    ) -> SkillEntry:
        entry = SkillEntry(
            member_name=member_name,
            team=team,
            skill_name=skill_name,
            domain=domain,
            level=level,
            certifications=certifications or [],
        )
        self._items.append(entry)
        if len(self._items) > self._max_entries:
            self._items = self._items[-self._max_entries :]
        logger.info(
            "team_skill_matrix.skill_registered",
            entry_id=entry.id,
            member_name=member_name,
            skill_name=skill_name,
            domain=domain,
            level=level,
        )
        return entry

    def get_skill(self, entry_id: str) -> SkillEntry | None:
        for e in self._items:
            if e.id == entry_id:
                return e
        return None

    def list_skills(
        self,
        member_name: str | None = None,
        team: str | None = None,
        domain: SkillDomain | None = None,
        limit: int = 50,
    ) -> list[SkillEntry]:
        results = list(self._items)
        if member_name is not None:
            results = [e for e in results if e.member_name == member_name]
        if team is not None:
            results = [e for e in results if e.team == team]
        if domain is not None:
            results = [e for e in results if e.domain == domain]
        return results[-limit:]

    # -- Assessment -------------------------------------------------

    def assess_skill(
        self,
        entry_id: str,
        new_level: SkillLevel,
    ) -> SkillEntry | None:
        entry = self.get_skill(entry_id)
        if entry is None:
            return None
        entry.level = new_level
        entry.last_assessed = time.time()
        logger.info(
            "team_skill_matrix.skill_assessed",
            entry_id=entry_id,
            member_name=entry.member_name,
            new_level=new_level,
        )
        return entry

    # -- Gap analysis -----------------------------------------------

    def identify_skill_gaps(self, team: str | None = None) -> list[SkillGap]:
        entries = list(self._items)
        if team is not None:
            entries = [e for e in entries if e.team == team]

        # Group by domain + skill_name
        skill_map: dict[tuple[str, str], list[SkillEntry]] = {}
        for e in entries:
            key = (e.domain.value, e.skill_name)
            skill_map.setdefault(key, []).append(e)

        gaps: list[SkillGap] = []
        required = SkillLevel.INTERMEDIATE
        required_score = _LEVEL_SCORES[required]

        for (dom, skill), members in skill_map.items():
            max_level = max(
                members,
                key=lambda m: _LEVEL_SCORES.get(m.level, 0),
            ).level
            max_score = _LEVEL_SCORES.get(max_level, 0)
            count = len(members)

            if count == 0:
                severity = GapSeverity.NO_COVERAGE
            elif max_score < required_score:
                severity = GapSeverity.CRITICAL_GAP
            elif count < self._min_coverage_per_domain:
                severity = GapSeverity.AT_RISK
            elif max_score == required_score:
                severity = GapSeverity.THIN
            else:
                severity = GapSeverity.COVERED

            gap = SkillGap(
                domain=SkillDomain(dom),
                skill_name=skill,
                required_level=required,
                current_max_level=max_level,
                gap_severity=severity,
                team=team or "",
                members_with_skill=count,
            )
            gaps.append(gap)
            self._gaps[f"{dom}:{skill}"] = gap

        gaps.sort(
            key=lambda g: [
                GapSeverity.NO_COVERAGE,
                GapSeverity.CRITICAL_GAP,
                GapSeverity.AT_RISK,
                GapSeverity.THIN,
                GapSeverity.COVERED,
            ].index(g.gap_severity),
        )
        logger.info(
            "team_skill_matrix.gaps_identified",
            gap_count=len(gaps),
            team=team,
        )
        return gaps

    def calculate_team_coverage(self, team: str) -> dict[str, Any]:
        entries = [e for e in self._items if e.team == team]
        if not entries:
            return {
                "team": team,
                "total_members": 0,
                "domains_covered": 0,
                "avg_level": 0.0,
                "coverage_pct": 0.0,
            }

        members = {e.member_name for e in entries}
        domains = {e.domain.value for e in entries}
        total_domains = len(SkillDomain)
        scores = [_LEVEL_SCORES.get(e.level, 0) for e in entries]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        coverage = round(len(domains) / total_domains * 100, 2)

        logger.info(
            "team_skill_matrix.coverage_calculated",
            team=team,
            coverage_pct=coverage,
        )
        return {
            "team": team,
            "total_members": len(members),
            "domains_covered": len(domains),
            "avg_level": avg,
            "coverage_pct": coverage,
        }

    def find_single_points_of_failure(self, team: str | None = None) -> list[dict[str, Any]]:
        """Find skills where only one person has coverage."""
        entries = list(self._items)
        if team is not None:
            entries = [e for e in entries if e.team == team]

        skill_members: dict[str, set[str]] = {}
        for e in entries:
            key = f"{e.domain.value}:{e.skill_name}"
            skill_members.setdefault(key, set()).add(e.member_name)

        spofs: list[dict[str, Any]] = []
        for key, members in skill_members.items():
            if len(members) == 1:
                parts = key.split(":", 1)
                spofs.append(
                    {
                        "domain": parts[0],
                        "skill_name": (parts[1] if len(parts) > 1 else ""),
                        "sole_member": list(members)[0],
                        "team": team or "",
                    }
                )

        logger.info(
            "team_skill_matrix.spofs_found",
            spof_count=len(spofs),
            team=team,
        )
        return spofs

    def recommend_training(self, team: str | None = None) -> list[dict[str, Any]]:
        gaps = self.identify_skill_gaps(team=team)
        recs: list[dict[str, Any]] = []

        for gap in gaps:
            if gap.gap_severity in (
                GapSeverity.NO_COVERAGE,
                GapSeverity.CRITICAL_GAP,
                GapSeverity.AT_RISK,
            ):
                recs.append(
                    {
                        "domain": gap.domain.value,
                        "skill_name": gap.skill_name,
                        "gap_severity": (gap.gap_severity.value),
                        "current_max_level": (gap.current_max_level.value),
                        "target_level": (gap.required_level.value),
                        "action": (f"Train team in {gap.skill_name} ({gap.domain.value})"),
                    }
                )

        logger.info(
            "team_skill_matrix.training_recommended",
            recommendation_count=len(recs),
            team=team,
        )
        return recs

    # -- Report -----------------------------------------------------

    def generate_skill_report(
        self,
    ) -> SkillMatrixReport:
        total = len(self._items)
        if total == 0:
            return SkillMatrixReport(
                training_recommendations=["No skill entries registered"],
            )

        members = {e.member_name for e in self._items}
        by_domain: dict[str, int] = {}
        by_level: dict[str, int] = {}
        score_sum = 0.0

        for e in self._items:
            dk = e.domain.value
            by_domain[dk] = by_domain.get(dk, 0) + 1
            lk = e.level.value
            by_level[lk] = by_level.get(lk, 0) + 1
            score_sum += _LEVEL_SCORES.get(e.level, 0)

        avg_level = round(score_sum / total, 2)

        gaps = self.identify_skill_gaps()
        critical = [
            f"{g.domain.value}:{g.skill_name}"
            for g in gaps
            if g.gap_severity
            in (
                GapSeverity.CRITICAL_GAP,
                GapSeverity.NO_COVERAGE,
            )
        ]

        spofs = self.find_single_points_of_failure()

        recs: list[str] = []
        if critical:
            recs.append(f"{len(critical)} critical skill gap(s) need attention")
        if spofs:
            recs.append(f"{len(spofs)} single point(s) of failure in skill coverage")
        if avg_level < 3.0:
            recs.append("Average skill level below intermediate — invest in training")

        report = SkillMatrixReport(
            total_members=len(members),
            total_skills=total,
            total_gaps=len(gaps),
            avg_skill_level=avg_level,
            by_domain=by_domain,
            by_level=by_level,
            critical_gaps=critical,
            training_recommendations=[r for r in recs],
        )
        logger.info(
            "team_skill_matrix.report_generated",
            total_members=len(members),
            total_skills=total,
        )
        return report

    # -- Housekeeping -----------------------------------------------

    def clear_data(self) -> None:
        self._items.clear()
        self._gaps.clear()
        logger.info("team_skill_matrix.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        members = {e.member_name for e in self._items}
        teams = {e.team for e in self._items}
        domains = {e.domain.value for e in self._items}
        return {
            "total_entries": len(self._items),
            "total_gaps": len(self._gaps),
            "unique_members": len(members),
            "unique_teams": len(teams),
            "domains": sorted(domains),
        }
