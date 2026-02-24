"""Team Performance Analyzer — SRE team effectiveness, knowledge silos, burnout risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PerformanceMetric(StrEnum):
    MTTR = "mttr"
    INCIDENT_PARTICIPATION = "incident_participation"
    KNOWLEDGE_BREADTH = "knowledge_breadth"
    ONCALL_LOAD = "oncall_load"
    RESOLUTION_QUALITY = "resolution_quality"


class RiskCategory(StrEnum):
    BURNOUT = "burnout"
    KNOWLEDGE_SILO = "knowledge_silo"
    UNDERSTAFFING = "understaffing"
    SKILL_GAP = "skill_gap"
    ATTRITION = "attrition"


class TeamHealth(StrEnum):
    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# --- Models ---


class TeamMember(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    team: str = ""
    role: str = ""
    skills: list[str] = Field(default_factory=list)
    oncall_hours: float = 0.0
    incidents_handled: int = 0
    avg_resolution_minutes: float = 0.0
    joined_at: float = Field(default_factory=time.time)


class PerformanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team: str = ""
    period_start: float = 0.0
    period_end: float = 0.0
    avg_mttr_minutes: float = 0.0
    total_incidents: int = 0
    participation_score: float = 0.0
    knowledge_breadth_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class RiskAssessment(BaseModel):
    team: str = ""
    member_id: str = ""
    risk_category: RiskCategory = RiskCategory.BURNOUT
    risk_score: float = 0.0
    description: str = ""
    recommendation: str = ""


# --- Engine ---


class TeamPerformanceAnalyzer:
    """SRE team effectiveness metrics, knowledge concentration detection, burnout risk scoring."""

    def __init__(
        self,
        max_members: int = 10000,
        burnout_threshold: float = 0.8,
    ) -> None:
        self._max_members = max_members
        self._burnout_threshold = burnout_threshold
        self._members: list[TeamMember] = []
        self._activities: list[dict[str, Any]] = []
        self._reports: list[PerformanceReport] = []
        logger.info(
            "team_performance.initialized",
            max_members=max_members,
            burnout_threshold=burnout_threshold,
        )

    def register_member(
        self,
        name: str,
        team: str = "",
        role: str = "",
        skills: list[str] | None = None,
    ) -> TeamMember:
        member = TeamMember(
            name=name,
            team=team,
            role=role,
            skills=skills or [],
        )
        self._members.append(member)
        if len(self._members) > self._max_members:
            self._members = self._members[-self._max_members :]
        logger.info("team_performance.member_registered", member_id=member.id, name=name)
        return member

    def get_member(self, member_id: str) -> TeamMember | None:
        for m in self._members:
            if m.id == member_id:
                return m
        return None

    def list_members(
        self,
        team: str | None = None,
        limit: int = 100,
    ) -> list[TeamMember]:
        results = list(self._members)
        if team is not None:
            results = [m for m in results if m.team == team]
        return results[-limit:]

    def record_activity(
        self,
        member_id: str,
        activity_type: str = "incident",
        duration_minutes: float = 0.0,
        oncall_hours: float = 0.0,
        incident_resolved: bool = False,
    ) -> dict[str, Any]:
        member = self.get_member(member_id)
        if member is None:
            return {"error": "member_not_found"}
        if oncall_hours > 0:
            member.oncall_hours += oncall_hours
        if incident_resolved:
            member.incidents_handled += 1
            # Running average
            prev = member.avg_resolution_minutes * (member.incidents_handled - 1)
            total = prev + duration_minutes
            member.avg_resolution_minutes = round(total / member.incidents_handled, 1)
        activity = {
            "member_id": member_id,
            "activity_type": activity_type,
            "duration_minutes": duration_minutes,
            "oncall_hours": oncall_hours,
            "recorded_at": time.time(),
        }
        self._activities.append(activity)
        return activity

    def compute_performance(self, team: str) -> PerformanceReport:
        members = [m for m in self._members if m.team == team]
        total_incidents = sum(m.incidents_handled for m in members)
        avg_mttr = 0.0
        if members:
            mttrs = [m.avg_resolution_minutes for m in members if m.incidents_handled > 0]
            avg_mttr = round(sum(mttrs) / len(mttrs), 1) if mttrs else 0.0
        # Participation score: what % of team handles incidents
        participating = sum(1 for m in members if m.incidents_handled > 0)
        participation = round(participating / len(members), 2) if members else 0.0
        # Knowledge breadth: unique skills across team
        all_skills: set[str] = set()
        for m in members:
            all_skills.update(m.skills)
        breadth = round(len(all_skills) / max(len(members), 1), 2)
        report = PerformanceReport(
            team=team,
            period_start=time.time() - 86400 * 30,
            period_end=time.time(),
            avg_mttr_minutes=avg_mttr,
            total_incidents=total_incidents,
            participation_score=participation,
            knowledge_breadth_score=breadth,
        )
        self._reports.append(report)
        return report

    def detect_knowledge_silos(self, team: str | None = None) -> list[RiskAssessment]:
        members = self._members
        if team:
            members = [m for m in members if m.team == team]
        silos: list[RiskAssessment] = []
        # Find skills held by only one person
        skill_holders: dict[str, list[str]] = {}
        for m in members:
            for skill in m.skills:
                skill_holders.setdefault(skill, []).append(m.id)
        for skill, holders in skill_holders.items():
            if len(holders) == 1:
                member = self.get_member(holders[0])
                silos.append(
                    RiskAssessment(
                        team=member.team if member else "",
                        member_id=holders[0],
                        risk_category=RiskCategory.KNOWLEDGE_SILO,
                        risk_score=0.8,
                        description=f"Sole holder of skill: {skill}",
                        recommendation=f"Cross-train another member on {skill}",
                    )
                )
        return silos

    def assess_burnout_risk(self, team: str | None = None) -> list[RiskAssessment]:
        members = self._members
        if team:
            members = [m for m in members if m.team == team]
        risks: list[RiskAssessment] = []
        if not members:
            return risks
        avg_oncall = sum(m.oncall_hours for m in members) / len(members) if members else 0.0
        for m in members:
            # Burnout score based on oncall load relative to team average
            load_ratio = m.oncall_hours / avg_oncall if avg_oncall > 0 else 0.0
            score = min(1.0, load_ratio / 2)
            if score >= self._burnout_threshold:
                risks.append(
                    RiskAssessment(
                        team=m.team,
                        member_id=m.id,
                        risk_category=RiskCategory.BURNOUT,
                        risk_score=round(score, 2),
                        description=f"High on-call load: {m.oncall_hours}h "
                        f"(team avg: {avg_oncall:.0f}h)",
                        recommendation="Redistribute on-call responsibilities",
                    )
                )
        risks.sort(key=lambda r: r.risk_score, reverse=True)
        return risks

    def get_team_health(self, team: str) -> dict[str, Any]:
        members = [m for m in self._members if m.team == team]
        if not members:
            return {"team": team, "health": TeamHealth.UNKNOWN, "members": 0}
        burnout_risks = self.assess_burnout_risk(team)
        silos = self.detect_knowledge_silos(team)
        if len(burnout_risks) > len(members) * 0.5 or len(silos) > len(members):
            health = TeamHealth.CRITICAL
        elif burnout_risks or silos:
            health = TeamHealth.AT_RISK
        else:
            health = TeamHealth.HEALTHY
        return {
            "team": team,
            "health": health.value,
            "members": len(members),
            "burnout_risks": len(burnout_risks),
            "knowledge_silos": len(silos),
        }

    def get_recommendations(self, team: str) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []
        burnout = self.assess_burnout_risk(team)
        for r in burnout:
            recommendations.append(
                {
                    "category": r.risk_category.value,
                    "member_id": r.member_id,
                    "recommendation": r.recommendation,
                    "priority": "high" if r.risk_score > 0.9 else "medium",
                }
            )
        silos = self.detect_knowledge_silos(team)
        for s in silos:
            recommendations.append(
                {
                    "category": s.risk_category.value,
                    "member_id": s.member_id,
                    "recommendation": s.recommendation,
                    "priority": "high",
                }
            )
        return recommendations

    def get_stats(self) -> dict[str, Any]:
        team_counts: dict[str, int] = {}
        for m in self._members:
            team_counts[m.team] = team_counts.get(m.team, 0) + 1
        return {
            "total_members": len(self._members),
            "total_activities": len(self._activities),
            "total_reports": len(self._reports),
            "unique_teams": len(team_counts),
            "team_distribution": team_counts,
        }
