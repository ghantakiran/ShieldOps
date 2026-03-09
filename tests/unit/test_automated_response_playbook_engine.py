"""Tests for AutomatedResponsePlaybookEngine."""

from __future__ import annotations

from shieldops.security.automated_response_playbook_engine import (
    AutomatedResponsePlaybookEngine,
    PlaybookExecution,
    PlaybookPriority,
    PlaybookRecord,
    PlaybookReport,
    PlaybookStatus,
    ThreatClassification,
)


def _engine(**kw) -> AutomatedResponsePlaybookEngine:
    return AutomatedResponsePlaybookEngine(**kw)


# --- Enum tests ---


class TestEnums:
    def test_threat_malware(self):
        assert ThreatClassification.MALWARE == "malware"

    def test_threat_phishing(self):
        assert ThreatClassification.PHISHING == "phishing"

    def test_threat_ransomware(self):
        assert ThreatClassification.RANSOMWARE == "ransomware"

    def test_threat_exfil(self):
        assert ThreatClassification.DATA_EXFILTRATION == "data_exfiltration"

    def test_threat_insider(self):
        assert ThreatClassification.INSIDER_THREAT == "insider_threat"

    def test_threat_brute(self):
        assert ThreatClassification.BRUTE_FORCE == "brute_force"

    def test_threat_dos(self):
        assert ThreatClassification.DENIAL_OF_SERVICE == "denial_of_service"

    def test_status_pending(self):
        assert PlaybookStatus.PENDING == "pending"

    def test_status_running(self):
        assert PlaybookStatus.RUNNING == "running"

    def test_status_completed(self):
        assert PlaybookStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert PlaybookStatus.FAILED == "failed"

    def test_status_rolled_back(self):
        assert PlaybookStatus.ROLLED_BACK == "rolled_back"

    def test_priority_low(self):
        assert PlaybookPriority.LOW == "low"

    def test_priority_critical(self):
        assert PlaybookPriority.CRITICAL == "critical"


# --- Model tests ---


class TestModels:
    def test_record_defaults(self):
        r = PlaybookRecord()
        assert r.id
        assert r.name == ""
        assert r.threat_classification == ThreatClassification.MALWARE
        assert r.status == PlaybookStatus.PENDING
        assert r.score == 0.0
        assert r.created_at > 0

    def test_execution_defaults(self):
        e = PlaybookExecution()
        assert e.id
        assert e.playbook_id == ""
        assert e.success is False
        assert e.rollback_available is True

    def test_report_defaults(self):
        r = PlaybookReport()
        assert r.id
        assert r.total_playbooks == 0
        assert r.by_threat == {}
        assert r.recommendations == []


# --- select_playbook ---


class TestSelectPlaybook:
    def test_basic(self):
        eng = _engine()
        p = eng.select_playbook(
            name="test",
            threat_classification=ThreatClassification.RANSOMWARE,
            priority=PlaybookPriority.HIGH,
            score=85.0,
            service="auth",
            team="sec",
        )
        assert p.name == "test"
        assert p.threat_classification == ThreatClassification.RANSOMWARE
        assert p.priority == PlaybookPriority.HIGH
        assert p.score == 85.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.select_playbook(name=f"p-{i}")
        assert len(eng._playbooks) == 3


# --- execute_playbook ---


class TestExecutePlaybook:
    def test_success(self):
        eng = _engine()
        p = eng.select_playbook(name="test", steps_total=5)
        e = eng.execute_playbook(p.id, success=True, execution_time_ms=120.0)
        assert e.success is True
        assert e.execution_time_ms == 120.0
        assert p.status == PlaybookStatus.COMPLETED

    def test_failure(self):
        eng = _engine()
        p = eng.select_playbook(name="test")
        e = eng.execute_playbook(p.id, success=False)
        assert e.success is False
        assert p.status == PlaybookStatus.FAILED

    def test_unknown_playbook(self):
        eng = _engine()
        e = eng.execute_playbook("unknown", success=True)
        assert e.playbook_id == "unknown"


# --- validate_execution ---


class TestValidateExecution:
    def test_valid(self):
        eng = _engine()
        p = eng.select_playbook(name="test")
        eng.execute_playbook(p.id, success=True)
        result = eng.validate_execution(p.id)
        assert result["valid"] is True

    def test_invalid(self):
        eng = _engine()
        p = eng.select_playbook(name="test")
        eng.execute_playbook(p.id, success=False)
        result = eng.validate_execution(p.id)
        assert result["valid"] is False

    def test_no_executions(self):
        eng = _engine()
        result = eng.validate_execution("unknown")
        assert result["valid"] is False
        assert result["reason"] == "no_executions_found"


# --- rollback_playbook ---


class TestRollbackPlaybook:
    def test_success(self):
        eng = _engine()
        p = eng.select_playbook(name="test")
        result = eng.rollback_playbook(p.id)
        assert result["status"] == "rolled_back"
        assert p.status == PlaybookStatus.ROLLED_BACK

    def test_not_found(self):
        eng = _engine()
        result = eng.rollback_playbook("unknown")
        assert result["status"] == "not_found"


# --- get_playbook_effectiveness ---


class TestEffectiveness:
    def test_with_data(self):
        eng = _engine()
        p = eng.select_playbook(name="a", score=80.0)
        eng.execute_playbook(p.id, success=True)
        result = eng.get_playbook_effectiveness()
        assert result["total"] == 1
        assert result["avg_score"] == 80.0
        assert result["success_rate"] == 100.0

    def test_empty(self):
        eng = _engine()
        result = eng.get_playbook_effectiveness()
        assert result["total"] == 0


# --- list_playbooks ---


class TestListPlaybooks:
    def test_all(self):
        eng = _engine()
        eng.select_playbook(name="a")
        eng.select_playbook(name="b")
        assert len(eng.list_playbooks()) == 2

    def test_filter_threat(self):
        eng = _engine()
        eng.select_playbook(name="a", threat_classification=ThreatClassification.MALWARE)
        eng.select_playbook(name="b", threat_classification=ThreatClassification.PHISHING)
        r = eng.list_playbooks(threat_classification=ThreatClassification.MALWARE)
        assert len(r) == 1

    def test_filter_team(self):
        eng = _engine()
        eng.select_playbook(name="a", team="sec")
        eng.select_playbook(name="b", team="ops")
        assert len(eng.list_playbooks(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.select_playbook(name=f"p-{i}")
        assert len(eng.list_playbooks(limit=5)) == 5


# --- generate_report ---


class TestReport:
    def test_populated(self):
        eng = _engine(score_threshold=80.0)
        eng.select_playbook(name="test", score=40.0)
        report = eng.generate_report()
        assert isinstance(report, PlaybookReport)
        assert report.total_playbooks == 1
        assert len(report.top_issues) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_playbooks == 0
        assert len(report.recommendations) > 0


# --- get_stats / clear_data ---


class TestStatsAndClear:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_playbooks"] == 0

    def test_stats_populated(self):
        eng = _engine()
        eng.select_playbook(name="a", service="s", team="t")
        stats = eng.get_stats()
        assert stats["total_playbooks"] == 1
        assert stats["unique_teams"] == 1

    def test_clear(self):
        eng = _engine()
        eng.select_playbook(name="test")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._playbooks) == 0
