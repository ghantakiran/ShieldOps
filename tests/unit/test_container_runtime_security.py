"""Tests for shieldops.security.container_runtime_security — ContainerRuntimeSecurity."""

from __future__ import annotations

from shieldops.security.container_runtime_security import (
    ContainerRuntimeSecurity,
    ContainerStatus,
    RuntimeAnalysis,
    RuntimeEvent,
    RuntimeRecord,
    RuntimeReport,
    SecurityLevel,
)


def _engine(**kw) -> ContainerRuntimeSecurity:
    return ContainerRuntimeSecurity(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_event_process_exec(self):
        assert RuntimeEvent.PROCESS_EXEC == "process_exec"

    def test_event_file_write(self):
        assert RuntimeEvent.FILE_WRITE == "file_write"

    def test_event_network_connect(self):
        assert RuntimeEvent.NETWORK_CONNECT == "network_connect"

    def test_event_privilege_escalation(self):
        assert RuntimeEvent.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_event_container_escape(self):
        assert RuntimeEvent.CONTAINER_ESCAPE == "container_escape"

    def test_status_running(self):
        assert ContainerStatus.RUNNING == "running"

    def test_status_stopped(self):
        assert ContainerStatus.STOPPED == "stopped"

    def test_status_crashed(self):
        assert ContainerStatus.CRASHED == "crashed"

    def test_status_quarantined(self):
        assert ContainerStatus.QUARANTINED == "quarantined"

    def test_status_terminated(self):
        assert ContainerStatus.TERMINATED == "terminated"

    def test_level_hardened(self):
        assert SecurityLevel.HARDENED == "hardened"

    def test_level_standard(self):
        assert SecurityLevel.STANDARD == "standard"

    def test_level_permissive(self):
        assert SecurityLevel.PERMISSIVE == "permissive"

    def test_level_vulnerable(self):
        assert SecurityLevel.VULNERABLE == "vulnerable"

    def test_level_compromised(self):
        assert SecurityLevel.COMPROMISED == "compromised"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_runtime_record_defaults(self):
        r = RuntimeRecord()
        assert r.id
        assert r.container_name == ""
        assert r.runtime_event == RuntimeEvent.PROCESS_EXEC
        assert r.container_status == ContainerStatus.RUNNING
        assert r.security_level == SecurityLevel.HARDENED
        assert r.security_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_runtime_analysis_defaults(self):
        c = RuntimeAnalysis()
        assert c.id
        assert c.container_name == ""
        assert c.runtime_event == RuntimeEvent.PROCESS_EXEC
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_runtime_report_defaults(self):
        r = RuntimeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_security_count == 0
        assert r.avg_security_score == 0.0
        assert r.by_event == {}
        assert r.by_status == {}
        assert r.by_level == {}
        assert r.top_low_security == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_event
# ---------------------------------------------------------------------------


class TestRecordEvent:
    def test_basic(self):
        eng = _engine()
        r = eng.record_event(
            container_name="web-app-1",
            runtime_event=RuntimeEvent.FILE_WRITE,
            container_status=ContainerStatus.RUNNING,
            security_level=SecurityLevel.STANDARD,
            security_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.container_name == "web-app-1"
        assert r.runtime_event == RuntimeEvent.FILE_WRITE
        assert r.container_status == ContainerStatus.RUNNING
        assert r.security_level == SecurityLevel.STANDARD
        assert r.security_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_event(container_name=f"C-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_event
# ---------------------------------------------------------------------------


class TestGetEvent:
    def test_found(self):
        eng = _engine()
        r = eng.record_event(
            container_name="web-app-1",
            security_level=SecurityLevel.HARDENED,
        )
        result = eng.get_event(r.id)
        assert result is not None
        assert result.security_level == SecurityLevel.HARDENED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_event("nonexistent") is None


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------


class TestListEvents:
    def test_list_all(self):
        eng = _engine()
        eng.record_event(container_name="C-001")
        eng.record_event(container_name="C-002")
        assert len(eng.list_events()) == 2

    def test_filter_by_runtime_event(self):
        eng = _engine()
        eng.record_event(
            container_name="C-001",
            runtime_event=RuntimeEvent.PROCESS_EXEC,
        )
        eng.record_event(
            container_name="C-002",
            runtime_event=RuntimeEvent.FILE_WRITE,
        )
        results = eng.list_events(runtime_event=RuntimeEvent.PROCESS_EXEC)
        assert len(results) == 1

    def test_filter_by_container_status(self):
        eng = _engine()
        eng.record_event(
            container_name="C-001",
            container_status=ContainerStatus.RUNNING,
        )
        eng.record_event(
            container_name="C-002",
            container_status=ContainerStatus.CRASHED,
        )
        results = eng.list_events(
            container_status=ContainerStatus.RUNNING,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_event(container_name="C-001", team="security")
        eng.record_event(container_name="C-002", team="platform")
        results = eng.list_events(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_event(container_name=f"C-{i}")
        assert len(eng.list_events(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            container_name="web-app-1",
            runtime_event=RuntimeEvent.FILE_WRITE,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="security gap detected",
        )
        assert a.container_name == "web-app-1"
        assert a.runtime_event == RuntimeEvent.FILE_WRITE
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(container_name=f"C-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_event_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_event(
            container_name="C-001",
            runtime_event=RuntimeEvent.PROCESS_EXEC,
            security_score=90.0,
        )
        eng.record_event(
            container_name="C-002",
            runtime_event=RuntimeEvent.PROCESS_EXEC,
            security_score=70.0,
        )
        result = eng.analyze_event_distribution()
        assert "process_exec" in result
        assert result["process_exec"]["count"] == 2
        assert result["process_exec"]["avg_security_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_event_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_security_containers
# ---------------------------------------------------------------------------


class TestIdentifyLowSecurityContainers:
    def test_detects_below_threshold(self):
        eng = _engine(runtime_security_threshold=80.0)
        eng.record_event(container_name="C-001", security_score=60.0)
        eng.record_event(container_name="C-002", security_score=90.0)
        results = eng.identify_low_security_containers()
        assert len(results) == 1
        assert results[0]["container_name"] == "C-001"

    def test_sorted_ascending(self):
        eng = _engine(runtime_security_threshold=80.0)
        eng.record_event(container_name="C-001", security_score=50.0)
        eng.record_event(container_name="C-002", security_score=30.0)
        results = eng.identify_low_security_containers()
        assert len(results) == 2
        assert results[0]["security_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_security_containers() == []


# ---------------------------------------------------------------------------
# rank_by_security_score
# ---------------------------------------------------------------------------


class TestRankBySecurityScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_event(container_name="C-001", service="auth-svc", security_score=90.0)
        eng.record_event(container_name="C-002", service="api-gw", security_score=50.0)
        results = eng.rank_by_security_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_security_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_security_score() == []


# ---------------------------------------------------------------------------
# detect_security_trends
# ---------------------------------------------------------------------------


class TestDetectSecurityTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(container_name="C-001", analysis_score=50.0)
        result = eng.detect_security_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(container_name="C-001", analysis_score=20.0)
        eng.add_analysis(container_name="C-002", analysis_score=20.0)
        eng.add_analysis(container_name="C-003", analysis_score=80.0)
        eng.add_analysis(container_name="C-004", analysis_score=80.0)
        result = eng.detect_security_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_security_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(runtime_security_threshold=80.0)
        eng.record_event(
            container_name="web-app-1",
            runtime_event=RuntimeEvent.FILE_WRITE,
            container_status=ContainerStatus.RUNNING,
            security_level=SecurityLevel.STANDARD,
            security_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RuntimeReport)
        assert report.total_records == 1
        assert report.low_security_count == 1
        assert len(report.top_low_security) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_event(container_name="C-001")
        eng.add_analysis(container_name="C-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["event_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_event(
            container_name="C-001",
            runtime_event=RuntimeEvent.PROCESS_EXEC,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "process_exec" in stats["event_distribution"]
