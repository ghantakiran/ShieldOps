"""Event Contract Testing Engine —
validate contract compliance, detect contract drift,
rank contracts by violation risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ContractStatus(StrEnum):
    COMPLIANT = "compliant"
    DRIFTED = "drifted"
    BROKEN = "broken"
    UNTESTED = "untested"


class TestResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class DriftSeverity(StrEnum):
    BREAKING = "breaking"
    SIGNIFICANT = "significant"
    MINOR = "minor"
    COSMETIC = "cosmetic"


# --- Models ---


class ContractTestRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str = ""
    contract_status: ContractStatus = ContractStatus.COMPLIANT
    test_result: TestResult = TestResult.PASSED
    drift_severity: DriftSeverity = DriftSeverity.MINOR
    violation_count: int = 0
    coverage_pct: float = 0.0
    service: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContractTestAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str = ""
    contract_status: ContractStatus = ContractStatus.COMPLIANT
    compliance_score: float = 0.0
    drift_detected: bool = False
    violation_risk: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContractTestReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_coverage: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    broken_contracts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EventContractTestingEngine:
    """Validate contract compliance, detect drift,
    rank contracts by violation risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ContractTestRecord] = []
        self._analyses: dict[str, ContractTestAnalysis] = {}
        logger.info(
            "event_contract_testing_engine.init",
            max_records=max_records,
        )

    def record_item(
        self,
        contract_id: str = "",
        contract_status: ContractStatus = (ContractStatus.COMPLIANT),
        test_result: TestResult = TestResult.PASSED,
        drift_severity: DriftSeverity = (DriftSeverity.MINOR),
        violation_count: int = 0,
        coverage_pct: float = 0.0,
        service: str = "",
        description: str = "",
    ) -> ContractTestRecord:
        record = ContractTestRecord(
            contract_id=contract_id,
            contract_status=contract_status,
            test_result=test_result,
            drift_severity=drift_severity,
            violation_count=violation_count,
            coverage_pct=coverage_pct,
            service=service,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "contract_testing.item_recorded",
            record_id=record.id,
            contract_id=contract_id,
        )
        return record

    def process(self, key: str) -> ContractTestAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        compliance = round(rec.coverage_pct, 2)
        drifted = rec.contract_status in (
            ContractStatus.DRIFTED,
            ContractStatus.BROKEN,
        )
        risk = round(rec.violation_count * 10.0, 2)
        analysis = ContractTestAnalysis(
            contract_id=rec.contract_id,
            contract_status=rec.contract_status,
            compliance_score=compliance,
            drift_detected=drifted,
            violation_risk=risk,
            description=(f"Contract {rec.contract_id} compliance {compliance}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ContractTestReport:
        by_st: dict[str, int] = {}
        by_rs: dict[str, int] = {}
        by_sv: dict[str, int] = {}
        coverages: list[float] = []
        for r in self._records:
            k = r.contract_status.value
            by_st[k] = by_st.get(k, 0) + 1
            k2 = r.test_result.value
            by_rs[k2] = by_rs.get(k2, 0) + 1
            k3 = r.drift_severity.value
            by_sv[k3] = by_sv.get(k3, 0) + 1
            coverages.append(r.coverage_pct)
        avg = round(sum(coverages) / len(coverages), 2) if coverages else 0.0
        broken = list(
            {
                r.contract_id
                for r in self._records
                if r.contract_status
                in (
                    ContractStatus.BROKEN,
                    ContractStatus.DRIFTED,
                )
            }
        )[:10]
        recs: list[str] = []
        if broken:
            recs.append(f"{len(broken)} broken contracts")
        if not recs:
            recs.append("All contracts compliant")
        return ContractTestReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_coverage=avg,
            by_status=by_st,
            by_result=by_rs,
            by_severity=by_sv,
            broken_contracts=broken,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        st_dist: dict[str, int] = {}
        for r in self._records:
            k = r.contract_status.value
            st_dist[k] = st_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "status_distribution": st_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("event_contract_testing_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def validate_contract_compliance(
        self,
    ) -> list[dict[str, Any]]:
        """Validate compliance per contract."""
        contract_data: dict[str, list[str]] = {}
        contract_cov: dict[str, list[float]] = {}
        for r in self._records:
            contract_data.setdefault(r.contract_id, []).append(r.test_result.value)
            contract_cov.setdefault(r.contract_id, []).append(r.coverage_pct)
        results: list[dict[str, Any]] = []
        for cid, results_list in contract_data.items():
            passed = results_list.count("passed")
            rate = round(passed / len(results_list) * 100, 2)
            avg_cov = round(
                sum(contract_cov[cid]) / len(contract_cov[cid]),
                2,
            )
            results.append(
                {
                    "contract_id": cid,
                    "pass_rate": rate,
                    "avg_coverage": avg_cov,
                    "total_tests": len(results_list),
                }
            )
        results.sort(
            key=lambda x: x["pass_rate"],
            reverse=True,
        )
        return results

    def detect_contract_drift(
        self,
    ) -> list[dict[str, Any]]:
        """Detect contracts with drift."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.contract_status
                in (
                    ContractStatus.DRIFTED,
                    ContractStatus.BROKEN,
                )
                and r.contract_id not in seen
            ):
                seen.add(r.contract_id)
                results.append(
                    {
                        "contract_id": (r.contract_id),
                        "status": (r.contract_status.value),
                        "severity": (r.drift_severity.value),
                        "violations": (r.violation_count),
                        "service": r.service,
                    }
                )
        results.sort(
            key=lambda x: x["violations"],
            reverse=True,
        )
        return results

    def rank_contracts_by_violation_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank contracts by violation risk."""
        sev_weights = {
            "breaking": 4,
            "significant": 3,
            "minor": 2,
            "cosmetic": 1,
        }
        contract_scores: dict[str, float] = {}
        for r in self._records:
            w = sev_weights.get(r.drift_severity.value, 1)
            score = w * r.violation_count
            contract_scores[r.contract_id] = contract_scores.get(r.contract_id, 0.0) + score
        results: list[dict[str, Any]] = []
        for cid, total_score in contract_scores.items():
            results.append(
                {
                    "contract_id": cid,
                    "risk_score": round(total_score, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["risk_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
