"""Security Posture Simulator — simulate attack scenarios against posture."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AttackScenario(StrEnum):
    LATERAL_MOVEMENT = "lateral_movement"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    SUPPLY_CHAIN = "supply_chain"
    INSIDER_THREAT = "insider_threat"


class SimulationResult(StrEnum):
    BLOCKED = "blocked"
    DETECTED = "detected"
    PARTIALLY_DETECTED = "partially_detected"
    UNDETECTED = "undetected"
    BYPASSED = "bypassed"  # noqa: S105


class PostureLevel(StrEnum):
    HARDENED = "hardened"
    STRONG = "strong"
    ADEQUATE = "adequate"
    WEAK = "weak"
    VULNERABLE = "vulnerable"


# --- Models ---


class SimulationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_name: str = ""
    attack: AttackScenario = AttackScenario.LATERAL_MOVEMENT
    result: SimulationResult = SimulationResult.BLOCKED
    posture: PostureLevel = PostureLevel.ADEQUATE
    risk_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class SimulationScenario(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_name: str = ""
    attack: AttackScenario = AttackScenario.LATERAL_MOVEMENT
    posture: PostureLevel = PostureLevel.ADEQUATE
    complexity_score: float = 5.0
    auto_remediate: bool = False
    created_at: float = Field(default_factory=time.time)


class PostureSimulatorReport(BaseModel):
    total_simulations: int = 0
    total_scenarios: int = 0
    blocked_rate_pct: float = 0.0
    by_attack: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    bypassed_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityPostureSimulator:
    """Simulate attack scenarios against posture."""

    def __init__(
        self,
        max_records: int = 200000,
        min_blocked_rate_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_blocked_rate_pct = min_blocked_rate_pct
        self._records: list[SimulationRecord] = []
        self._scenarios: list[SimulationScenario] = []
        logger.info(
            "posture_simulator.initialized",
            max_records=max_records,
            min_blocked_rate_pct=min_blocked_rate_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_simulation(
        self,
        scenario_name: str,
        attack: AttackScenario = (AttackScenario.LATERAL_MOVEMENT),
        result: SimulationResult = (SimulationResult.BLOCKED),
        posture: PostureLevel = PostureLevel.ADEQUATE,
        risk_score: float = 0.0,
        details: str = "",
    ) -> SimulationRecord:
        record = SimulationRecord(
            scenario_name=scenario_name,
            attack=attack,
            result=result,
            posture=posture,
            risk_score=risk_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "posture_simulator.recorded",
            record_id=record.id,
            scenario_name=scenario_name,
            attack=attack.value,
            result=result.value,
        )
        return record

    def get_simulation(self, record_id: str) -> SimulationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_simulations(
        self,
        scenario_name: str | None = None,
        attack: AttackScenario | None = None,
        limit: int = 50,
    ) -> list[SimulationRecord]:
        results = list(self._records)
        if scenario_name is not None:
            results = [r for r in results if r.scenario_name == scenario_name]
        if attack is not None:
            results = [r for r in results if r.attack == attack]
        return results[-limit:]

    def add_scenario(
        self,
        scenario_name: str,
        attack: AttackScenario = (AttackScenario.LATERAL_MOVEMENT),
        posture: PostureLevel = PostureLevel.ADEQUATE,
        complexity_score: float = 5.0,
        auto_remediate: bool = False,
    ) -> SimulationScenario:
        scenario = SimulationScenario(
            scenario_name=scenario_name,
            attack=attack,
            posture=posture,
            complexity_score=complexity_score,
            auto_remediate=auto_remediate,
        )
        self._scenarios.append(scenario)
        if len(self._scenarios) > self._max_records:
            self._scenarios = self._scenarios[-self._max_records :]
        logger.info(
            "posture_simulator.scenario_added",
            scenario_name=scenario_name,
            attack=attack.value,
            posture=posture.value,
        )
        return scenario

    # -- domain operations -------------------------------------------

    def analyze_posture_strength(self, scenario_name: str) -> dict[str, Any]:
        """Analyze posture strength for a scenario."""
        records = [r for r in self._records if r.scenario_name == scenario_name]
        if not records:
            return {
                "scenario_name": scenario_name,
                "status": "no_data",
            }
        blocked = sum(1 for r in records if r.result == SimulationResult.BLOCKED)
        blocked_rate = round(blocked / len(records) * 100, 2)
        avg_risk = round(
            sum(r.risk_score for r in records) / len(records),
            2,
        )
        return {
            "scenario_name": scenario_name,
            "simulation_count": len(records),
            "blocked_count": blocked,
            "blocked_rate": blocked_rate,
            "avg_risk_score": avg_risk,
            "meets_threshold": (blocked_rate >= self._min_blocked_rate_pct),
        }

    def identify_bypassed_defenses(
        self,
    ) -> list[dict[str, Any]]:
        """Find scenarios with bypassed defenses."""
        bypass_counts: dict[str, int] = {}
        for r in self._records:
            if r.result in (
                SimulationResult.BYPASSED,
                SimulationResult.UNDETECTED,
            ):
                bypass_counts[r.scenario_name] = bypass_counts.get(r.scenario_name, 0) + 1
        results: list[dict[str, Any]] = []
        for scn, count in bypass_counts.items():
            if count > 1:
                results.append(
                    {
                        "scenario_name": scn,
                        "bypassed_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["bypassed_count"],
            reverse=True,
        )
        return results

    def rank_by_risk_score(
        self,
    ) -> list[dict[str, Any]]:
        """Rank scenarios by avg risk score desc."""
        totals: dict[str, list[float]] = {}
        for r in self._records:
            totals.setdefault(r.scenario_name, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for scn, scores in totals.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "scenario_name": scn,
                    "avg_risk_score": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_risk_score"],
            reverse=True,
        )
        return results

    def detect_posture_weaknesses(
        self,
    ) -> list[dict[str, Any]]:
        """Detect scenarios with posture weaknesses (>3)."""
        non_blocked: dict[str, int] = {}
        for r in self._records:
            if r.result != SimulationResult.BLOCKED:
                non_blocked[r.scenario_name] = non_blocked.get(r.scenario_name, 0) + 1
        results: list[dict[str, Any]] = []
        for scn, count in non_blocked.items():
            if count > 3:
                results.append(
                    {
                        "scenario_name": scn,
                        "non_blocked_count": count,
                        "weakness_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_blocked_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(
        self,
    ) -> PostureSimulatorReport:
        by_attack: dict[str, int] = {}
        by_result: dict[str, int] = {}
        for r in self._records:
            by_attack[r.attack.value] = by_attack.get(r.attack.value, 0) + 1
            by_result[r.result.value] = by_result.get(r.result.value, 0) + 1
        blocked = sum(1 for r in self._records if r.result == SimulationResult.BLOCKED)
        blocked_rate = (
            round(
                blocked / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        bypassed = sum(1 for d in self.identify_bypassed_defenses())
        recs: list[str] = []
        if blocked_rate < self._min_blocked_rate_pct:
            recs.append(
                f"Blocked rate {blocked_rate}% is below {self._min_blocked_rate_pct}% threshold"
            )
        if bypassed > 0:
            recs.append(f"{bypassed} scenario(s) with bypassed defenses")
        weak = len(self.detect_posture_weaknesses())
        if weak > 0:
            recs.append(f"{weak} scenario(s) with posture weaknesses")
        if not recs:
            recs.append("Security posture simulation is healthy")
        return PostureSimulatorReport(
            total_simulations=len(self._records),
            total_scenarios=len(self._scenarios),
            blocked_rate_pct=blocked_rate,
            by_attack=by_attack,
            by_result=by_result,
            bypassed_count=bypassed,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._scenarios.clear()
        logger.info("posture_simulator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        attack_dist: dict[str, int] = {}
        for r in self._records:
            key = r.attack.value
            attack_dist[key] = attack_dist.get(key, 0) + 1
        return {
            "total_simulations": len(self._records),
            "total_scenarios": len(self._scenarios),
            "min_blocked_rate_pct": (self._min_blocked_rate_pct),
            "attack_distribution": attack_dist,
            "unique_scenarios": len({r.scenario_name for r in self._records}),
        }
