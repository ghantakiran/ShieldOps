"""Tests for shieldops.incidents.incident_containment_tracker — IncidentContainmentTracker."""

from __future__ import annotations

from shieldops.incidents.incident_containment_tracker import (
    ContainmentAnalysis,
    ContainmentRecord,
    ContainmentReport,
    ContainmentStatus,
    ContainmentType,
    IncidentContainmentTracker,
    UrgencyLevel,
)


def _engine(**kw) -> IncidentContainmentTracker:
    return IncidentContainmentTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_network_isolation(self):
        assert ContainmentType.NETWORK_ISOLATION == "network_isolation"

    def test_type_account_lockout(self):
        assert ContainmentType.ACCOUNT_LOCKOUT == "account_lockout"

    def test_type_service_shutdown(self):
        assert ContainmentType.SERVICE_SHUTDOWN == "service_shutdown"

    def test_type_firewall_block(self):
        assert ContainmentType.FIREWALL_BLOCK == "firewall_block"

    def test_type_credential_revocation(self):
        assert ContainmentType.CREDENTIAL_REVOCATION == "credential_revocation"

    def test_status_active(self):
        assert ContainmentStatus.ACTIVE == "active"

    def test_status_completed(self):
        assert ContainmentStatus.COMPLETED == "completed"

    def test_status_failed(self):
        assert ContainmentStatus.FAILED == "failed"

    def test_status_rolled_back(self):
        assert ContainmentStatus.ROLLED_BACK == "rolled_back"

    def test_status_pending(self):
        assert ContainmentStatus.PENDING == "pending"

    def test_urgency_immediate(self):
        assert UrgencyLevel.IMMEDIATE == "immediate"

    def test_urgency_high(self):
        assert UrgencyLevel.HIGH == "high"

    def test_urgency_medium(self):
        assert UrgencyLevel.MEDIUM == "medium"

    def test_urgency_low(self):
        assert UrgencyLevel.LOW == "low"

    def test_urgency_scheduled(self):
        assert UrgencyLevel.SCHEDULED == "scheduled"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_containment_record_defaults(self):
        r = ContainmentRecord()
        assert r.id
        assert r.containment_name == ""
        assert r.containment_type == ContainmentType.NETWORK_ISOLATION
        assert r.containment_status == ContainmentStatus.ACTIVE
        assert r.urgency_level == UrgencyLevel.IMMEDIATE
        assert r.effectiveness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_containment_analysis_defaults(self):
        c = ContainmentAnalysis()
        assert c.id
        assert c.containment_name == ""
        assert c.containment_type == ContainmentType.NETWORK_ISOLATION
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_containment_report_defaults(self):
        r = ContainmentReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_effectiveness_count == 0
        assert r.avg_effectiveness_score == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_urgency == {}
        assert r.top_low_effectiveness == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_containment
# ---------------------------------------------------------------------------


class TestRecordContainment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_containment(
            containment_name="isolate-compromised-host",
            containment_type=ContainmentType.ACCOUNT_LOCKOUT,
            containment_status=ContainmentStatus.COMPLETED,
            urgency_level=UrgencyLevel.HIGH,
            effectiveness_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.containment_name == "isolate-compromised-host"
        assert r.containment_type == ContainmentType.ACCOUNT_LOCKOUT
        assert r.containment_status == ContainmentStatus.COMPLETED
        assert r.urgency_level == UrgencyLevel.HIGH
        assert r.effectiveness_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_containment(containment_name=f"CONT-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_containment
# ---------------------------------------------------------------------------


class TestGetContainment:
    def test_found(self):
        eng = _engine()
        r = eng.record_containment(
            containment_name="isolate-compromised-host",
            urgency_level=UrgencyLevel.IMMEDIATE,
        )
        result = eng.get_containment(r.id)
        assert result is not None
        assert result.urgency_level == UrgencyLevel.IMMEDIATE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_containment("nonexistent") is None


# ---------------------------------------------------------------------------
# list_containments
# ---------------------------------------------------------------------------


class TestListContainments:
    def test_list_all(self):
        eng = _engine()
        eng.record_containment(containment_name="CONT-001")
        eng.record_containment(containment_name="CONT-002")
        assert len(eng.list_containments()) == 2

    def test_filter_by_containment_type(self):
        eng = _engine()
        eng.record_containment(
            containment_name="CONT-001",
            containment_type=ContainmentType.NETWORK_ISOLATION,
        )
        eng.record_containment(
            containment_name="CONT-002",
            containment_type=ContainmentType.FIREWALL_BLOCK,
        )
        results = eng.list_containments(
            containment_type=ContainmentType.NETWORK_ISOLATION,
        )
        assert len(results) == 1

    def test_filter_by_containment_status(self):
        eng = _engine()
        eng.record_containment(
            containment_name="CONT-001",
            containment_status=ContainmentStatus.ACTIVE,
        )
        eng.record_containment(
            containment_name="CONT-002",
            containment_status=ContainmentStatus.FAILED,
        )
        results = eng.list_containments(
            containment_status=ContainmentStatus.ACTIVE,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_containment(containment_name="CONT-001", team="security")
        eng.record_containment(containment_name="CONT-002", team="platform")
        results = eng.list_containments(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_containment(containment_name=f"CONT-{i}")
        assert len(eng.list_containments(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            containment_name="isolate-compromised-host",
            containment_type=ContainmentType.ACCOUNT_LOCKOUT,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="low effectiveness detected",
        )
        assert a.containment_name == "isolate-compromised-host"
        assert a.containment_type == ContainmentType.ACCOUNT_LOCKOUT
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(containment_name=f"CONT-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_containment_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeContainmentDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_containment(
            containment_name="CONT-001",
            containment_type=ContainmentType.NETWORK_ISOLATION,
            effectiveness_score=90.0,
        )
        eng.record_containment(
            containment_name="CONT-002",
            containment_type=ContainmentType.NETWORK_ISOLATION,
            effectiveness_score=70.0,
        )
        result = eng.analyze_containment_distribution()
        assert "network_isolation" in result
        assert result["network_isolation"]["count"] == 2
        assert result["network_isolation"]["avg_effectiveness_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_containment_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_effectiveness_containments
# ---------------------------------------------------------------------------


class TestIdentifyLowEffectivenessContainments:
    def test_detects_below_threshold(self):
        eng = _engine(effectiveness_threshold=80.0)
        eng.record_containment(containment_name="CONT-001", effectiveness_score=60.0)
        eng.record_containment(containment_name="CONT-002", effectiveness_score=90.0)
        results = eng.identify_low_effectiveness_containments()
        assert len(results) == 1
        assert results[0]["containment_name"] == "CONT-001"

    def test_sorted_ascending(self):
        eng = _engine(effectiveness_threshold=80.0)
        eng.record_containment(containment_name="CONT-001", effectiveness_score=50.0)
        eng.record_containment(containment_name="CONT-002", effectiveness_score=30.0)
        results = eng.identify_low_effectiveness_containments()
        assert len(results) == 2
        assert results[0]["effectiveness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_effectiveness_containments() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankByEffectiveness:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_containment(
            containment_name="CONT-001", service="auth-svc", effectiveness_score=90.0
        )
        eng.record_containment(
            containment_name="CONT-002", service="api-gw", effectiveness_score=50.0
        )
        results = eng.rank_by_effectiveness()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_effectiveness_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness() == []


# ---------------------------------------------------------------------------
# detect_containment_trends
# ---------------------------------------------------------------------------


class TestDetectContainmentTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(containment_name="CONT-001", analysis_score=50.0)
        result = eng.detect_containment_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(containment_name="CONT-001", analysis_score=20.0)
        eng.add_analysis(containment_name="CONT-002", analysis_score=20.0)
        eng.add_analysis(containment_name="CONT-003", analysis_score=80.0)
        eng.add_analysis(containment_name="CONT-004", analysis_score=80.0)
        result = eng.detect_containment_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_containment_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(effectiveness_threshold=80.0)
        eng.record_containment(
            containment_name="isolate-compromised-host",
            containment_type=ContainmentType.ACCOUNT_LOCKOUT,
            containment_status=ContainmentStatus.COMPLETED,
            urgency_level=UrgencyLevel.HIGH,
            effectiveness_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ContainmentReport)
        assert report.total_records == 1
        assert report.low_effectiveness_count == 1
        assert len(report.top_low_effectiveness) == 1
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
        eng.record_containment(containment_name="CONT-001")
        eng.add_analysis(containment_name="CONT-001")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_containment(
            containment_name="CONT-001",
            containment_type=ContainmentType.NETWORK_ISOLATION,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "network_isolation" in stats["type_distribution"]
