"""Cost attribution and chargeback engine for team-level cost allocation.

Applies allocation rules to cloud cost entries to attribute spend to teams,
supporting tag-based, proportional, fixed, and custom allocation methods.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class AllocationMethod(enum.StrEnum):
    TAG_BASED = "tag_based"
    PROPORTIONAL = "proportional"
    FIXED = "fixed"
    CUSTOM = "custom"


class ReportPeriod(enum.StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


# -- Models --------------------------------------------------------------------


class CostAllocationRule(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    team: str
    method: AllocationMethod = AllocationMethod.TAG_BASED
    match_tags: dict[str, str] = Field(default_factory=dict)
    match_services: list[str] = Field(default_factory=list)
    proportion: float = 1.0
    created_at: float = Field(default_factory=time.time)


class CostEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    service: str
    resource_id: str = ""
    amount: float
    currency: str = "USD"
    tags: dict[str, str] = Field(default_factory=dict)
    period: str = ""
    recorded_at: float = Field(default_factory=time.time)


class TeamCostReport(BaseModel):
    team: str
    total_cost: float = 0.0
    currency: str = "USD"
    services: dict[str, float] = Field(default_factory=dict)
    period: str = ""
    generated_at: float = Field(default_factory=time.time)


# -- Engine --------------------------------------------------------------------


class CostAttributionEngine:
    """Attribute cloud costs to teams via configurable allocation rules.

    Parameters
    ----------
    max_rules:
        Maximum number of allocation rules to store.
    max_entries:
        Maximum number of cost entries to retain.
    """

    def __init__(
        self,
        max_rules: int = 200,
        max_entries: int = 100000,
    ) -> None:
        self._rules: dict[str, CostAllocationRule] = {}
        self._entries: list[CostEntry] = []
        self._max_rules = max_rules
        self._max_entries = max_entries

    def create_rule(
        self,
        name: str,
        team: str,
        method: AllocationMethod = AllocationMethod.TAG_BASED,
        match_tags: dict[str, str] | None = None,
        match_services: list[str] | None = None,
        proportion: float = 1.0,
    ) -> CostAllocationRule:
        if len(self._rules) >= self._max_rules:
            raise ValueError(f"Maximum rules limit reached: {self._max_rules}")
        rule = CostAllocationRule(
            name=name,
            team=team,
            method=method,
            match_tags=match_tags or {},
            match_services=match_services or [],
            proportion=proportion,
        )
        self._rules[rule.id] = rule
        logger.info("cost_rule_created", rule_id=rule.id, name=name, team=team)
        return rule

    def record_cost(
        self,
        service: str,
        amount: float,
        resource_id: str = "",
        currency: str = "USD",
        tags: dict[str, str] | None = None,
        period: str = "",
    ) -> CostEntry:
        entry = CostEntry(
            service=service,
            amount=amount,
            resource_id=resource_id,
            currency=currency,
            tags=tags or {},
            period=period,
        )
        self._entries.append(entry)
        # Trim to max_entries
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]
        logger.info("cost_entry_recorded", entry_id=entry.id, service=service, amount=amount)
        return entry

    def _matches_rule(self, entry: CostEntry, rule: CostAllocationRule) -> bool:
        """Check whether a cost entry matches an allocation rule."""
        if rule.method == AllocationMethod.TAG_BASED:
            if not rule.match_tags:
                return False
            return all(entry.tags.get(k) == v for k, v in rule.match_tags.items())
        if rule.method == AllocationMethod.FIXED:
            if rule.match_services:
                return entry.service in rule.match_services
            return True
        if rule.method == AllocationMethod.PROPORTIONAL:
            if rule.match_services:
                return entry.service in rule.match_services
            return True
        if rule.method == AllocationMethod.CUSTOM:
            # Custom rules match on both tags and services when specified
            tag_match = (
                all(entry.tags.get(k) == v for k, v in rule.match_tags.items())
                if rule.match_tags
                else True
            )
            svc_match = entry.service in rule.match_services if rule.match_services else True
            return tag_match and svc_match
        return False

    def allocate_costs(self) -> list[TeamCostReport]:
        team_costs: dict[str, dict[str, float]] = {}

        for entry in self._entries:
            for rule in self._rules.values():
                if self._matches_rule(entry, rule):
                    team = rule.team
                    if team not in team_costs:
                        team_costs[team] = {}
                    allocated = entry.amount * rule.proportion
                    team_costs[team][entry.service] = (
                        team_costs[team].get(entry.service, 0.0) + allocated
                    )

        reports: list[TeamCostReport] = []
        for team, services in team_costs.items():
            total = sum(services.values())
            reports.append(
                TeamCostReport(
                    team=team,
                    total_cost=round(total, 2),
                    services={k: round(v, 2) for k, v in services.items()},
                )
            )
        logger.info("costs_allocated", teams=len(reports))
        return reports

    def get_team_report(self, team: str, period: str = "") -> TeamCostReport:
        entries = self._entries
        if period:
            entries = [e for e in entries if e.period == period]

        services: dict[str, float] = {}
        for entry in entries:
            for rule in self._rules.values():
                if rule.team == team and self._matches_rule(entry, rule):
                    allocated = entry.amount * rule.proportion
                    services[entry.service] = services.get(entry.service, 0.0) + allocated

        total = sum(services.values())
        return TeamCostReport(
            team=team,
            total_cost=round(total, 2),
            services={k: round(v, 2) for k, v in services.items()},
            period=period,
        )

    def list_rules(self, team: str | None = None) -> list[CostAllocationRule]:
        rules = list(self._rules.values())
        if team:
            rules = [r for r in rules if r.team == team]
        return rules

    def delete_rule(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    def list_entries(
        self,
        service: str | None = None,
        limit: int = 100,
    ) -> list[CostEntry]:
        entries = self._entries
        if service:
            entries = [e for e in entries if e.service == service]
        return entries[-limit:]

    def get_unattributed_costs(self) -> list[CostEntry]:
        unattributed: list[CostEntry] = []
        for entry in self._entries:
            matched = any(self._matches_rule(entry, rule) for rule in self._rules.values())
            if not matched:
                unattributed.append(entry)
        return unattributed

    def get_stats(self) -> dict[str, Any]:
        total_cost = sum(e.amount for e in self._entries)
        unattributed = len(self.get_unattributed_costs())
        teams = {r.team for r in self._rules.values()}
        return {
            "total_rules": len(self._rules),
            "total_entries": len(self._entries),
            "total_cost": round(total_cost, 2),
            "unattributed_entries": unattributed,
            "teams": len(teams),
        }
