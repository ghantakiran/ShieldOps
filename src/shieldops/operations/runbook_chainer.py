"""Runbook Chain Executor — connect multiple runbooks into conditional workflows."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ChainMode(StrEnum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    FALLBACK = "fallback"


class ChainStatus(StrEnum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class TransitionType(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CONDITIONAL = "conditional"
    ALWAYS = "always"


# --- Models ---


class ChainRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_name: str = ""
    chain_mode: ChainMode = ChainMode.SEQUENTIAL
    chain_status: ChainStatus = ChainStatus.PENDING
    transition_type: TransitionType = TransitionType.SUCCESS
    runbook_count: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ChainLink(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    link_name: str = ""
    chain_mode: ChainMode = ChainMode.SEQUENTIAL
    chain_status: ChainStatus = ChainStatus.EXECUTING
    execution_time_seconds: float = 0.0
    created_at: float = Field(default_factory=time.time)


class RunbookChainReport(BaseModel):
    total_chains: int = 0
    total_links: int = 0
    success_rate_pct: float = 0.0
    by_mode: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    abort_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RunbookChainExecutor:
    """Connect multiple runbooks into conditional workflows."""

    def __init__(
        self,
        max_records: int = 200000,
        max_chain_length: int = 20,
    ) -> None:
        self._max_records = max_records
        self._max_chain_length = max_chain_length
        self._records: list[ChainRecord] = []
        self._links: list[ChainLink] = []
        logger.info(
            "runbook_chain_executor.initialized",
            max_records=max_records,
            max_chain_length=max_chain_length,
        )

    # -- record / get / list ---------------------------------------------

    def record_chain(
        self,
        chain_name: str,
        chain_mode: ChainMode = ChainMode.SEQUENTIAL,
        chain_status: ChainStatus = ChainStatus.PENDING,
        transition_type: TransitionType = TransitionType.SUCCESS,
        runbook_count: int = 0,
        details: str = "",
    ) -> ChainRecord:
        record = ChainRecord(
            chain_name=chain_name,
            chain_mode=chain_mode,
            chain_status=chain_status,
            transition_type=transition_type,
            runbook_count=runbook_count,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "runbook_chain_executor.chain_recorded",
            record_id=record.id,
            chain_name=chain_name,
            chain_status=chain_status.value,
        )
        return record

    def get_chain(self, record_id: str) -> ChainRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_chains(
        self,
        chain_name: str | None = None,
        chain_status: ChainStatus | None = None,
        limit: int = 50,
    ) -> list[ChainRecord]:
        results = list(self._records)
        if chain_name is not None:
            results = [r for r in results if r.chain_name == chain_name]
        if chain_status is not None:
            results = [r for r in results if r.chain_status == chain_status]
        return results[-limit:]

    def add_link(
        self,
        link_name: str,
        chain_mode: ChainMode = ChainMode.SEQUENTIAL,
        chain_status: ChainStatus = ChainStatus.EXECUTING,
        execution_time_seconds: float = 0.0,
    ) -> ChainLink:
        link = ChainLink(
            link_name=link_name,
            chain_mode=chain_mode,
            chain_status=chain_status,
            execution_time_seconds=execution_time_seconds,
        )
        self._links.append(link)
        if len(self._links) > self._max_records:
            self._links = self._links[-self._max_records :]
        logger.info(
            "runbook_chain_executor.link_added",
            link_name=link_name,
            chain_status=chain_status.value,
        )
        return link

    # -- domain operations -----------------------------------------------

    def analyze_chain_efficiency(self, chain_name: str) -> dict[str, Any]:
        """Analyze success rate for a chain and check threshold."""
        chain_records = [r for r in self._records if r.chain_name == chain_name]
        if not chain_records:
            return {"chain_name": chain_name, "status": "no_data"}
        completed = sum(1 for r in chain_records if r.chain_status == ChainStatus.COMPLETED)
        success_rate = round((completed / len(chain_records)) * 100, 2)
        avg_runbooks = round(sum(r.runbook_count for r in chain_records) / len(chain_records), 2)
        return {
            "chain_name": chain_name,
            "success_rate": success_rate,
            "record_count": len(chain_records),
            "avg_runbook_count": avg_runbooks,
            "max_chain_length": self._max_chain_length,
        }

    def identify_broken_chains(self) -> list[dict[str, Any]]:
        """Find chains with more than one FAILED or ABORTED execution."""
        chain_counts: dict[str, int] = {}
        for r in self._records:
            if r.chain_status in (ChainStatus.FAILED, ChainStatus.ABORTED):
                chain_counts[r.chain_name] = chain_counts.get(r.chain_name, 0) + 1
        results: list[dict[str, Any]] = []
        for chain, count in chain_counts.items():
            if count > 1:
                results.append({"chain_name": chain, "broken_count": count})
        results.sort(key=lambda x: x["broken_count"], reverse=True)
        return results

    def rank_by_execution_speed(self) -> list[dict[str, Any]]:
        """Rank chains by average runbook count descending."""
        chain_counts: dict[str, list[int]] = {}
        for r in self._records:
            chain_counts.setdefault(r.chain_name, []).append(r.runbook_count)
        results: list[dict[str, Any]] = []
        for chain, counts in chain_counts.items():
            avg = round(sum(counts) / len(counts), 2)
            results.append(
                {
                    "chain_name": chain,
                    "avg_runbook_count": avg,
                    "record_count": len(counts),
                }
            )
        results.sort(key=lambda x: x["avg_runbook_count"], reverse=True)
        return results

    def detect_chain_loops(self) -> list[dict[str, Any]]:
        """Detect chains with more than 3 records."""
        chain_counts: dict[str, int] = {}
        for r in self._records:
            chain_counts[r.chain_name] = chain_counts.get(r.chain_name, 0) + 1
        results: list[dict[str, Any]] = []
        for chain, count in chain_counts.items():
            if count > 3:
                results.append({"chain_name": chain, "record_count": count})
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> RunbookChainReport:
        by_mode: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_mode[r.chain_mode.value] = by_mode.get(r.chain_mode.value, 0) + 1
            by_status[r.chain_status.value] = by_status.get(r.chain_status.value, 0) + 1
        completed = sum(1 for r in self._records if r.chain_status == ChainStatus.COMPLETED)
        success_rate = round((completed / len(self._records)) * 100, 2) if self._records else 0.0
        abort_count = sum(1 for r in self._records if r.chain_status == ChainStatus.ABORTED)
        recs: list[str] = []
        if abort_count > 0:
            recs.append(f"{abort_count} chain(s) aborted")
        failed_count = sum(1 for r in self._records if r.chain_status == ChainStatus.FAILED)
        if failed_count > 0:
            recs.append(f"{failed_count} chain(s) failed")
        if not recs:
            recs.append("Runbook chain execution is healthy")
        return RunbookChainReport(
            total_chains=len(self._records),
            total_links=len(self._links),
            success_rate_pct=success_rate,
            by_mode=by_mode,
            by_status=by_status,
            abort_count=abort_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._links.clear()
        logger.info("runbook_chain_executor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        mode_dist: dict[str, int] = {}
        for r in self._records:
            key = r.chain_mode.value
            mode_dist[key] = mode_dist.get(key, 0) + 1
        return {
            "total_chains": len(self._records),
            "total_links": len(self._links),
            "max_chain_length": self._max_chain_length,
            "mode_distribution": mode_dist,
            "unique_chains": len({r.chain_name for r in self._records}),
        }
