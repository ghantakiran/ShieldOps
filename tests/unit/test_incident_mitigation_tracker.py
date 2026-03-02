"""Tests for shieldops.incidents.incident_mitigation_tracker — IncidentMitigationTracker."""

from __future__ import annotations

from shieldops.incidents.incident_mitigation_tracker import (
    IncidentMitigationReport,
    IncidentMitigationTracker,
    MitigationAnalysis,
    MitigationCategory,
    MitigationRecord,
    MitigationStatus,
    MitigationUrgency,
)


def _engine(**kw) -> IncidentMitigationTracker:
    return IncidentMitigationTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_pending(self):
        assert MitigationStatus.PENDING == "pending"

    def test_status_in_progress(self):
        assert MitigationStatus.IN_PROGRESS == "in_progress"

    def test_status_applied(self):
        assert MitigationStatus.APPLIED == "applied"

    def test_status_verified(self):
        assert MitigationStatus.VERIFIED == "verified"

    def test_status_rolled_back(self):
        assert MitigationStatus.ROLLED_BACK == "rolled_back"

    def test_category_infrastructure(self):
        assert MitigationCategory.INFRASTRUCTURE == "infrastructure"

    def test_category_application(self):
        assert MitigationCategory.APPLICATION == "application"

    def test_category_network(self):
        assert MitigationCategory.NETWORK == "network"

    def test_category_database(self):
        assert MitigationCategory.DATABASE == "database"

    def test_category_configuration(self):
        assert MitigationCategory.CONFIGURATION == "configuration"

    def test_urgency_critical(self):
        assert MitigationUrgency.CRITICAL == "critical"

    def test_urgency_high(self):
        assert MitigationUrgency.HIGH == "high"

    def test_urgency_medium(self):
        assert MitigationUrgency.MEDIUM == "medium"

    def test_urgency_low(self):
        assert MitigationUrgency.LOW == "low"

    def test_urgency_deferred(self):
        assert MitigationUrgency.DEFERRED == "deferred"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_mitigation_record_defaults(self):
        r = MitigationRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.mitigation_status == MitigationStatus.PENDING
        assert r.mitigation_category == MitigationCategory.INFRASTRUCTURE
        assert r.mitigation_urgency == MitigationUrgency.CRITICAL
        assert r.effectiveness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_mitigation_analysis_defaults(self):
        a = MitigationAnalysis()
        assert a.id
        assert a.incident_id == ""
        assert a.mitigation_status == MitigationStatus.PENDING
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_incident_mitigation_report_defaults(self):
        r = IncidentMitigationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_effectiveness_count == 0
        assert r.avg_effectiveness_score == 0.0
        assert r.by_status == {}
        assert r.by_category == {}
        assert r.by_urgency == {}
        assert r.top_low_effectiveness == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_mitigation
# ---------------------------------------------------------------------------


class TestRecordMitigation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_mitigation(
            incident_id="INC-001",
            mitigation_status=MitigationStatus.APPLIED,
            mitigation_category=MitigationCategory.NETWORK,
            mitigation_urgency=MitigationUrgency.HIGH,
            effectiveness_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.incident_id == "INC-001"
        assert r.mitigation_status == MitigationStatus.APPLIED
        assert r.mitigation_category == MitigationCategory.NETWORK
        assert r.mitigation_urgency == MitigationUrgency.HIGH
        assert r.effectiveness_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mitigation(incident_id=f"INC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_mitigation
# ---------------------------------------------------------------------------


class TestGetMitigation:
    def test_found(self):
        eng = _engine()
        r = eng.record_mitigation(
            incident_id="INC-001",
            mitigation_status=MitigationStatus.VERIFIED,
        )
        result = eng.get_mitigation(r.id)
        assert result is not None
        assert result.mitigation_status == MitigationStatus.VERIFIED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_mitigation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_mitigations
# ---------------------------------------------------------------------------


class TestListMitigations:
    def test_list_all(self):
        eng = _engine()
        eng.record_mitigation(incident_id="INC-001")
        eng.record_mitigation(incident_id="INC-002")
        assert len(eng.list_mitigations()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_mitigation(
            incident_id="INC-001",
            mitigation_status=MitigationStatus.APPLIED,
        )
        eng.record_mitigation(
            incident_id="INC-002",
            mitigation_status=MitigationStatus.ROLLED_BACK,
        )
        results = eng.list_mitigations(
            mitigation_status=MitigationStatus.APPLIED,
        )
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_mitigation(
            incident_id="INC-001",
            mitigation_category=MitigationCategory.NETWORK,
        )
        eng.record_mitigation(
            incident_id="INC-002",
            mitigation_category=MitigationCategory.DATABASE,
        )
        results = eng.list_mitigations(
            mitigation_category=MitigationCategory.NETWORK,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_mitigation(incident_id="INC-001", team="sre")
        eng.record_mitigation(incident_id="INC-002", team="platform")
        results = eng.list_mitigations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mitigation(incident_id=f"INC-{i}")
        assert len(eng.list_mitigations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            incident_id="INC-001",
            mitigation_status=MitigationStatus.APPLIED,
            analysis_score=45.0,
            threshold=70.0,
            breached=True,
            description="Low effectiveness detected",
        )
        assert a.incident_id == "INC-001"
        assert a.mitigation_status == MitigationStatus.APPLIED
        assert a.analysis_score == 45.0
        assert a.threshold == 70.0
        assert a.breached is True
        assert a.description == "Low effectiveness detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(incident_id=f"INC-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_mitigation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeMitigationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_mitigation(
            incident_id="INC-001",
            mitigation_status=MitigationStatus.APPLIED,
            effectiveness_score=80.0,
        )
        eng.record_mitigation(
            incident_id="INC-002",
            mitigation_status=MitigationStatus.APPLIED,
            effectiveness_score=60.0,
        )
        result = eng.analyze_mitigation_distribution()
        assert "applied" in result
        assert result["applied"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_mitigation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_effectiveness
# ---------------------------------------------------------------------------


class TestIdentifyLowEffectiveness:
    def test_detects(self):
        eng = _engine(effectiveness_threshold=70.0)
        eng.record_mitigation(
            incident_id="INC-001",
            effectiveness_score=40.0,
        )
        eng.record_mitigation(
            incident_id="INC-002",
            effectiveness_score=90.0,
        )
        results = eng.identify_low_effectiveness()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_effectiveness() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankByEffectiveness:
    def test_ranked(self):
        eng = _engine()
        eng.record_mitigation(
            incident_id="INC-001",
            service="api-gateway",
            effectiveness_score=90.0,
        )
        eng.record_mitigation(
            incident_id="INC-002",
            service="payments",
            effectiveness_score=30.0,
        )
        results = eng.rank_by_effectiveness()
        assert len(results) == 2
        assert results[0]["service"] == "payments"
        assert results[0]["avg_effectiveness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness() == []


# ---------------------------------------------------------------------------
# detect_mitigation_trends
# ---------------------------------------------------------------------------


class TestDetectMitigationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(
                incident_id="INC-001",
                analysis_score=50.0,
            )
        result = eng.detect_mitigation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(incident_id="INC-001", analysis_score=30.0)
        eng.add_analysis(incident_id="INC-002", analysis_score=30.0)
        eng.add_analysis(incident_id="INC-003", analysis_score=80.0)
        eng.add_analysis(incident_id="INC-004", analysis_score=80.0)
        result = eng.detect_mitigation_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_mitigation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_mitigation(
            incident_id="INC-001",
            mitigation_status=MitigationStatus.APPLIED,
            mitigation_category=MitigationCategory.NETWORK,
            mitigation_urgency=MitigationUrgency.HIGH,
            effectiveness_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, IncidentMitigationReport)
        assert report.total_records == 1
        assert report.low_effectiveness_count == 1
        assert len(report.top_low_effectiveness) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_mitigation(incident_id="INC-001")
        eng.add_analysis(incident_id="INC-001")
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
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_mitigation(
            incident_id="INC-001",
            mitigation_status=MitigationStatus.APPLIED,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "applied" in stats["status_distribution"]
