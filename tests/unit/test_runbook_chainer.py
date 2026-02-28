"""Tests for shieldops.operations.runbook_chainer — RunbookChainExecutor."""

from __future__ import annotations

from shieldops.operations.runbook_chainer import (
    ChainLink,
    ChainMode,
    ChainRecord,
    ChainStatus,
    RunbookChainExecutor,
    RunbookChainReport,
    TransitionType,
)


def _engine(**kw) -> RunbookChainExecutor:
    return RunbookChainExecutor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ChainMode (5)
    def test_mode_sequential(self):
        assert ChainMode.SEQUENTIAL == "sequential"

    def test_mode_parallel(self):
        assert ChainMode.PARALLEL == "parallel"

    def test_mode_conditional(self):
        assert ChainMode.CONDITIONAL == "conditional"

    def test_mode_loop(self):
        assert ChainMode.LOOP == "loop"

    def test_mode_fallback(self):
        assert ChainMode.FALLBACK == "fallback"

    # ChainStatus (5)
    def test_status_pending(self):
        assert ChainStatus.PENDING == "pending"

    def test_status_executing(self):
        assert ChainStatus.EXECUTING == "executing"

    def test_status_completed(self):
        assert ChainStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert ChainStatus.FAILED == "failed"

    def test_status_aborted(self):
        assert ChainStatus.ABORTED == "aborted"

    # TransitionType (5)
    def test_transition_success(self):
        assert TransitionType.SUCCESS == "success"

    def test_transition_failure(self):
        assert TransitionType.FAILURE == "failure"

    def test_transition_timeout(self):
        assert TransitionType.TIMEOUT == "timeout"

    def test_transition_conditional(self):
        assert TransitionType.CONDITIONAL == "conditional"

    def test_transition_always(self):
        assert TransitionType.ALWAYS == "always"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_chain_record_defaults(self):
        r = ChainRecord()
        assert r.id
        assert r.chain_name == ""
        assert r.chain_mode == ChainMode.SEQUENTIAL
        assert r.chain_status == ChainStatus.PENDING
        assert r.transition_type == TransitionType.SUCCESS
        assert r.runbook_count == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_chain_link_defaults(self):
        r = ChainLink()
        assert r.id
        assert r.link_name == ""
        assert r.chain_mode == ChainMode.SEQUENTIAL
        assert r.chain_status == ChainStatus.EXECUTING
        assert r.execution_time_seconds == 0.0
        assert r.created_at > 0

    def test_runbook_chain_report_defaults(self):
        r = RunbookChainReport()
        assert r.total_chains == 0
        assert r.total_links == 0
        assert r.success_rate_pct == 0.0
        assert r.by_mode == {}
        assert r.by_status == {}
        assert r.abort_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_chain
# -------------------------------------------------------------------


class TestRecordChain:
    def test_basic(self):
        eng = _engine()
        r = eng.record_chain("deploy-rollback", chain_mode=ChainMode.SEQUENTIAL)
        assert r.chain_name == "deploy-rollback"
        assert r.chain_mode == ChainMode.SEQUENTIAL

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_chain(
            "scale-and-verify",
            chain_mode=ChainMode.CONDITIONAL,
            chain_status=ChainStatus.FAILED,
            transition_type=TransitionType.TIMEOUT,
            runbook_count=4,
            details="Timeout on step 3",
        )
        assert r.chain_status == ChainStatus.FAILED
        assert r.transition_type == TransitionType.TIMEOUT
        assert r.runbook_count == 4
        assert r.details == "Timeout on step 3"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_chain(f"chain-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_chain
# -------------------------------------------------------------------


class TestGetChain:
    def test_found(self):
        eng = _engine()
        r = eng.record_chain("deploy-rollback")
        assert eng.get_chain(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_chain("nonexistent") is None


# -------------------------------------------------------------------
# list_chains
# -------------------------------------------------------------------


class TestListChains:
    def test_list_all(self):
        eng = _engine()
        eng.record_chain("chain-a")
        eng.record_chain("chain-b")
        assert len(eng.list_chains()) == 2

    def test_filter_by_chain_name(self):
        eng = _engine()
        eng.record_chain("chain-a")
        eng.record_chain("chain-b")
        results = eng.list_chains(chain_name="chain-a")
        assert len(results) == 1
        assert results[0].chain_name == "chain-a"

    def test_filter_by_chain_status(self):
        eng = _engine()
        eng.record_chain("chain-a", chain_status=ChainStatus.PENDING)
        eng.record_chain("chain-b", chain_status=ChainStatus.COMPLETED)
        results = eng.list_chains(chain_status=ChainStatus.COMPLETED)
        assert len(results) == 1
        assert results[0].chain_name == "chain-b"


# -------------------------------------------------------------------
# add_link
# -------------------------------------------------------------------


class TestAddLink:
    def test_basic(self):
        eng = _engine()
        lk = eng.add_link(
            "restart-service",
            chain_mode=ChainMode.SEQUENTIAL,
            chain_status=ChainStatus.COMPLETED,
            execution_time_seconds=12.5,
        )
        assert lk.link_name == "restart-service"
        assert lk.chain_status == ChainStatus.COMPLETED
        assert lk.execution_time_seconds == 12.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_link(f"link-{i}")
        assert len(eng._links) == 2


# -------------------------------------------------------------------
# analyze_chain_efficiency
# -------------------------------------------------------------------


class TestAnalyzeChainEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_chain("chain-a", chain_status=ChainStatus.COMPLETED)
        eng.record_chain("chain-a", chain_status=ChainStatus.COMPLETED)
        eng.record_chain("chain-a", chain_status=ChainStatus.FAILED)
        result = eng.analyze_chain_efficiency("chain-a")
        assert result["success_rate"] == 66.67
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_chain_efficiency("unknown-chain")
        assert result["status"] == "no_data"

    def test_full_success(self):
        eng = _engine()
        eng.record_chain("chain-a", chain_status=ChainStatus.COMPLETED)
        eng.record_chain("chain-a", chain_status=ChainStatus.COMPLETED)
        result = eng.analyze_chain_efficiency("chain-a")
        assert result["success_rate"] == 100.0


# -------------------------------------------------------------------
# identify_broken_chains
# -------------------------------------------------------------------


class TestIdentifyBrokenChains:
    def test_with_broken(self):
        eng = _engine()
        eng.record_chain("chain-a", chain_status=ChainStatus.FAILED)
        eng.record_chain("chain-a", chain_status=ChainStatus.ABORTED)
        eng.record_chain("chain-b", chain_status=ChainStatus.COMPLETED)
        results = eng.identify_broken_chains()
        assert len(results) == 1
        assert results[0]["chain_name"] == "chain-a"
        assert results[0]["broken_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_broken_chains() == []

    def test_single_failed_not_returned(self):
        eng = _engine()
        eng.record_chain("chain-a", chain_status=ChainStatus.FAILED)
        assert eng.identify_broken_chains() == []


# -------------------------------------------------------------------
# rank_by_execution_speed
# -------------------------------------------------------------------


class TestRankByExecutionSpeed:
    def test_with_data(self):
        eng = _engine()
        eng.record_chain("chain-a", runbook_count=2)
        eng.record_chain("chain-b", runbook_count=8)
        results = eng.rank_by_execution_speed()
        assert results[0]["chain_name"] == "chain-b"
        assert results[0]["avg_runbook_count"] == 8.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_execution_speed() == []


# -------------------------------------------------------------------
# detect_chain_loops
# -------------------------------------------------------------------


class TestDetectChainLoops:
    def test_with_loops(self):
        eng = _engine()
        for _ in range(5):
            eng.record_chain("chain-a")
        eng.record_chain("chain-b")
        results = eng.detect_chain_loops()
        assert len(results) == 1
        assert results[0]["chain_name"] == "chain-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_chain_loops() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_chain("chain-a")
        assert eng.detect_chain_loops() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_chain("chain-a", chain_status=ChainStatus.FAILED)
        eng.record_chain("chain-b", chain_status=ChainStatus.COMPLETED)
        eng.add_link("link-1")
        report = eng.generate_report()
        assert report.total_chains == 2
        assert report.total_links == 1
        assert report.by_mode != {}
        assert report.by_status != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_chains == 0
        assert report.success_rate_pct == 0.0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_chain("chain-a")
        eng.add_link("link-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._links) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_chains"] == 0
        assert stats["total_links"] == 0
        assert stats["mode_distribution"] == {}

    def test_populated(self):
        eng = _engine(max_chain_length=20)
        eng.record_chain("chain-a", chain_mode=ChainMode.SEQUENTIAL)
        eng.record_chain("chain-b", chain_mode=ChainMode.PARALLEL)
        eng.add_link("link-1")
        stats = eng.get_stats()
        assert stats["total_chains"] == 2
        assert stats["total_links"] == 1
        assert stats["unique_chains"] == 2
        assert stats["max_chain_length"] == 20
