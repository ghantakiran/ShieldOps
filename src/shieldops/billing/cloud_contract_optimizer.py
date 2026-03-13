"""Cloud Contract Optimizer
analyze contract terms, identify negotiation
leverage, model contract scenarios."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ContractType(StrEnum):
    ON_DEMAND = "on_demand"
    ENTERPRISE = "enterprise"
    RESERVED = "reserved"
    CUSTOM = "custom"


class LeverageType(StrEnum):
    VOLUME = "volume"
    COMMITMENT = "commitment"
    MULTI_YEAR = "multi_year"
    BUNDLING = "bundling"


class ScenarioOutcome(StrEnum):
    FAVORABLE = "favorable"
    NEUTRAL = "neutral"
    UNFAVORABLE = "unfavorable"
    RISKY = "risky"


# --- Models ---


class ContractRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str = ""
    contract_type: ContractType = ContractType.ON_DEMAND
    leverage_type: LeverageType = LeverageType.VOLUME
    scenario_outcome: ScenarioOutcome = ScenarioOutcome.NEUTRAL
    annual_value: float = 0.0
    discount_pct: float = 0.0
    term_months: int = 12
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContractAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str = ""
    contract_type: ContractType = ContractType.ON_DEMAND
    effective_rate: float = 0.0
    savings_potential: float = 0.0
    scenario_outcome: ScenarioOutcome = ScenarioOutcome.NEUTRAL
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContractReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_annual_value: float = 0.0
    by_contract_type: dict[str, int] = Field(default_factory=dict)
    by_leverage_type: dict[str, int] = Field(default_factory=dict)
    by_scenario_outcome: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CloudContractOptimizer:
    """Analyze contract terms, identify leverage,
    model contract scenarios."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ContractRecord] = []
        self._analyses: dict[str, ContractAnalysis] = {}
        logger.info(
            "cloud_contract_optimizer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        contract_id: str = "",
        contract_type: ContractType = (ContractType.ON_DEMAND),
        leverage_type: LeverageType = (LeverageType.VOLUME),
        scenario_outcome: ScenarioOutcome = (ScenarioOutcome.NEUTRAL),
        annual_value: float = 0.0,
        discount_pct: float = 0.0,
        term_months: int = 12,
        description: str = "",
    ) -> ContractRecord:
        record = ContractRecord(
            contract_id=contract_id,
            contract_type=contract_type,
            leverage_type=leverage_type,
            scenario_outcome=scenario_outcome,
            annual_value=annual_value,
            discount_pct=discount_pct,
            term_months=term_months,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cloud_contract.record_added",
            record_id=record.id,
            contract_id=contract_id,
        )
        return record

    def process(self, key: str) -> ContractAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        effective = round(
            rec.annual_value * (1 - rec.discount_pct / 100),
            2,
        )
        savings = round(rec.annual_value - effective, 2)
        analysis = ContractAnalysis(
            contract_id=rec.contract_id,
            contract_type=rec.contract_type,
            effective_rate=effective,
            savings_potential=savings,
            scenario_outcome=rec.scenario_outcome,
            description=(f"Contract {rec.contract_id} saves ${savings}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ContractReport:
        by_ct: dict[str, int] = {}
        by_lt: dict[str, int] = {}
        by_so: dict[str, int] = {}
        total_val = 0.0
        for r in self._records:
            k = r.contract_type.value
            by_ct[k] = by_ct.get(k, 0) + 1
            k2 = r.leverage_type.value
            by_lt[k2] = by_lt.get(k2, 0) + 1
            k3 = r.scenario_outcome.value
            by_so[k3] = by_so.get(k3, 0) + 1
            total_val += r.annual_value
        recs: list[str] = []
        risky = [r for r in self._records if r.scenario_outcome == ScenarioOutcome.RISKY]
        if risky:
            recs.append(f"{len(risky)} risky contracts need renegotiation")
        if not recs:
            recs.append("Contract portfolio healthy")
        return ContractReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_annual_value=round(total_val, 2),
            by_contract_type=by_ct,
            by_leverage_type=by_lt,
            by_scenario_outcome=by_so,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ct_dist: dict[str, int] = {}
        for r in self._records:
            k = r.contract_type.value
            ct_dist[k] = ct_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "contract_type_distribution": ct_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("cloud_contract_optimizer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def analyze_contract_terms(
        self,
    ) -> list[dict[str, Any]]:
        """Analyze terms across contracts."""
        ctr_map: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.contract_id not in ctr_map:
                ctr_map[r.contract_id] = {
                    "type": r.contract_type.value,
                    "value": 0.0,
                    "discount": r.discount_pct,
                    "term": r.term_months,
                }
            ctr_map[r.contract_id]["value"] += r.annual_value
        results: list[dict[str, Any]] = []
        for cid, info in ctr_map.items():
            results.append(
                {
                    "contract_id": cid,
                    "type": info["type"],
                    "total_value": round(info["value"], 2),
                    "discount_pct": info["discount"],
                    "term_months": info["term"],
                }
            )
        results.sort(
            key=lambda x: x["total_value"],
            reverse=True,
        )
        return results

    def identify_negotiation_leverage(
        self,
    ) -> list[dict[str, Any]]:
        """Identify negotiation leverage."""
        lev_map: dict[str, list[float]] = {}
        for r in self._records:
            k = r.leverage_type.value
            lev_map.setdefault(k, []).append(r.annual_value)
        results: list[dict[str, Any]] = []
        for ltype, vals in lev_map.items():
            total = round(sum(vals), 2)
            results.append(
                {
                    "leverage_type": ltype,
                    "contract_count": len(vals),
                    "total_value": total,
                    "negotiation_power": round(total / 1000, 2),
                }
            )
        results.sort(
            key=lambda x: x["total_value"],
            reverse=True,
        )
        return results

    def model_contract_scenarios(
        self,
    ) -> list[dict[str, Any]]:
        """Model contract scenarios."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.contract_id not in seen:
                seen.add(r.contract_id)
                base = r.annual_value
                optimistic = round(
                    base * (1 - r.discount_pct / 50),
                    2,
                )
                pessimistic = round(base * 1.1, 2)
                results.append(
                    {
                        "contract_id": (r.contract_id),
                        "base_cost": round(base, 2),
                        "optimistic": optimistic,
                        "pessimistic": pessimistic,
                        "outcome": (r.scenario_outcome.value),
                    }
                )
        return results
