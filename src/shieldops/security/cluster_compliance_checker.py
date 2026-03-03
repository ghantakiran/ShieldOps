"""Cluster Compliance Checker — check Kubernetes cluster compliance against benchmarks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplianceBenchmark(StrEnum):
    CIS_K8S = "cis_k8s"
    NSA_CISA = "nsa_cisa"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    CUSTOM = "custom"


class CheckResult(StrEnum):
    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"
    NOT_APPLICABLE = "not_applicable"


class RemediationPriority(StrEnum):
    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DEFERRED = "deferred"


# --- Models ---


class ComplianceCheckRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    check_id: str = ""
    compliance_benchmark: ComplianceBenchmark = ComplianceBenchmark.CIS_K8S
    check_result: CheckResult = CheckResult.PASS
    remediation_priority: RemediationPriority = RemediationPriority.IMMEDIATE
    compliance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceCheckAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    check_id: str = ""
    compliance_benchmark: ComplianceBenchmark = ComplianceBenchmark.CIS_K8S
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ClusterComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_compliance_score: float = 0.0
    by_benchmark: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ClusterComplianceChecker:
    """Check Kubernetes cluster compliance against CIS, NSA/CISA, SOC2, and PCI DSS benchmarks."""

    def __init__(
        self,
        max_records: int = 200000,
        compliance_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._compliance_gap_threshold = compliance_gap_threshold
        self._records: list[ComplianceCheckRecord] = []
        self._analyses: list[ComplianceCheckAnalysis] = []
        logger.info(
            "cluster_compliance_checker.initialized",
            max_records=max_records,
            compliance_gap_threshold=compliance_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_check(
        self,
        check_id: str,
        compliance_benchmark: ComplianceBenchmark = ComplianceBenchmark.CIS_K8S,
        check_result: CheckResult = CheckResult.PASS,
        remediation_priority: RemediationPriority = RemediationPriority.IMMEDIATE,
        compliance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ComplianceCheckRecord:
        record = ComplianceCheckRecord(
            check_id=check_id,
            compliance_benchmark=compliance_benchmark,
            check_result=check_result,
            remediation_priority=remediation_priority,
            compliance_score=compliance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cluster_compliance_checker.check_recorded",
            record_id=record.id,
            check_id=check_id,
            compliance_benchmark=compliance_benchmark.value,
            check_result=check_result.value,
        )
        return record

    def get_check(self, record_id: str) -> ComplianceCheckRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_checks(
        self,
        compliance_benchmark: ComplianceBenchmark | None = None,
        check_result: CheckResult | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ComplianceCheckRecord]:
        results = list(self._records)
        if compliance_benchmark is not None:
            results = [r for r in results if r.compliance_benchmark == compliance_benchmark]
        if check_result is not None:
            results = [r for r in results if r.check_result == check_result]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        check_id: str,
        compliance_benchmark: ComplianceBenchmark = ComplianceBenchmark.CIS_K8S,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ComplianceCheckAnalysis:
        analysis = ComplianceCheckAnalysis(
            check_id=check_id,
            compliance_benchmark=compliance_benchmark,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "cluster_compliance_checker.analysis_added",
            check_id=check_id,
            compliance_benchmark=compliance_benchmark.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_benchmark_distribution(self) -> dict[str, Any]:
        """Group by compliance_benchmark; return count and avg compliance_score."""
        benchmark_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.compliance_benchmark.value
            benchmark_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for benchmark, scores in benchmark_data.items():
            result[benchmark] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_compliance_gaps(self) -> list[dict[str, Any]]:
        """Return records where compliance_score < compliance_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_score < self._compliance_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "check_id": r.check_id,
                        "compliance_benchmark": r.compliance_benchmark.value,
                        "compliance_score": r.compliance_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["compliance_score"])

    def rank_by_compliance(self) -> list[dict[str, Any]]:
        """Group by service, avg compliance_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.compliance_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_compliance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_score"])
        return results

    def detect_compliance_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ClusterComplianceReport:
        by_benchmark: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for r in self._records:
            by_benchmark[r.compliance_benchmark.value] = (
                by_benchmark.get(r.compliance_benchmark.value, 0) + 1
            )
            by_result[r.check_result.value] = by_result.get(r.check_result.value, 0) + 1
            by_priority[r.remediation_priority.value] = (
                by_priority.get(r.remediation_priority.value, 0) + 1
            )
        gap_count = sum(
            1 for r in self._records if r.compliance_score < self._compliance_gap_threshold
        )
        scores = [r.compliance_score for r in self._records]
        avg_compliance_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_compliance_gaps()
        top_gaps = [o["check_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} check(s) below compliance threshold "
                f"({self._compliance_gap_threshold})"
            )
        if self._records and avg_compliance_score < self._compliance_gap_threshold:
            recs.append(
                f"Avg compliance score {avg_compliance_score} below threshold "
                f"({self._compliance_gap_threshold})"
            )
        if not recs:
            recs.append("Cluster compliance checking is healthy")
        return ClusterComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_compliance_score=avg_compliance_score,
            by_benchmark=by_benchmark,
            by_result=by_result,
            by_priority=by_priority,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cluster_compliance_checker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        benchmark_dist: dict[str, int] = {}
        for r in self._records:
            key = r.compliance_benchmark.value
            benchmark_dist[key] = benchmark_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "compliance_gap_threshold": self._compliance_gap_threshold,
            "benchmark_distribution": benchmark_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
