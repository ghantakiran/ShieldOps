"""Tests for shieldops.security.threat_response_tracker — ThreatResponseTracker."""

from __future__ import annotations

from shieldops.security.threat_response_tracker import (
    ResponseAssessment,
    ResponseEffectiveness,
    ResponseStatus,
    ThreatCategory,
    ThreatResponseRecord,
    ThreatResponseReport,
    ThreatResponseTracker,
)


def _engine(**kw) -> ThreatResponseTracker:
    return ThreatResponseTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_malware(self):
        assert ThreatCategory.MALWARE == "malware"

    def test_category_phishing(self):
        assert ThreatCategory.PHISHING == "phishing"

    def test_category_intrusion(self):
        assert ThreatCategory.INTRUSION == "intrusion"

    def test_category_data_exfiltration(self):
        assert ThreatCategory.DATA_EXFILTRATION == "data_exfiltration"

    def test_category_insider_threat(self):
        assert ThreatCategory.INSIDER_THREAT == "insider_threat"

    def test_status_contained(self):
        assert ResponseStatus.CONTAINED == "contained"

    def test_status_investigating(self):
        assert ResponseStatus.INVESTIGATING == "investigating"

    def test_status_eradicating(self):
        assert ResponseStatus.ERADICATING == "eradicating"

    def test_status_recovering(self):
        assert ResponseStatus.RECOVERING == "recovering"

    def test_status_closed(self):
        assert ResponseStatus.CLOSED == "closed"

    def test_effectiveness_excellent(self):
        assert ResponseEffectiveness.EXCELLENT == "excellent"

    def test_effectiveness_good(self):
        assert ResponseEffectiveness.GOOD == "good"

    def test_effectiveness_adequate(self):
        assert ResponseEffectiveness.ADEQUATE == "adequate"

    def test_effectiveness_poor(self):
        assert ResponseEffectiveness.POOR == "poor"

    def test_effectiveness_failed(self):
        assert ResponseEffectiveness.FAILED == "failed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_threat_response_record_defaults(self):
        r = ThreatResponseRecord()
        assert r.id
        assert r.threat_id == ""
        assert r.threat_category == ThreatCategory.MALWARE
        assert r.response_status == ResponseStatus.INVESTIGATING
        assert r.response_effectiveness == ResponseEffectiveness.ADEQUATE
        assert r.response_time_hours == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_response_assessment_defaults(self):
        a = ResponseAssessment()
        assert a.id
        assert a.threat_id == ""
        assert a.threat_category == ThreatCategory.MALWARE
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_threat_response_report_defaults(self):
        r = ThreatResponseReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.active_threats == 0
        assert r.avg_response_time_hours == 0.0
        assert r.by_category == {}
        assert r.by_status == {}
        assert r.by_effectiveness == {}
        assert r.top_slow_responses == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_response
# ---------------------------------------------------------------------------


class TestRecordResponse:
    def test_basic(self):
        eng = _engine()
        r = eng.record_response(
            threat_id="THR-001",
            threat_category=ThreatCategory.PHISHING,
            response_status=ResponseStatus.INVESTIGATING,
            response_effectiveness=ResponseEffectiveness.GOOD,
            response_time_hours=2.5,
            service="email-gateway",
            team="security",
        )
        assert r.threat_id == "THR-001"
        assert r.threat_category == ThreatCategory.PHISHING
        assert r.response_status == ResponseStatus.INVESTIGATING
        assert r.response_effectiveness == ResponseEffectiveness.GOOD
        assert r.response_time_hours == 2.5
        assert r.service == "email-gateway"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_response(threat_id=f"THR-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_response
# ---------------------------------------------------------------------------


class TestGetResponse:
    def test_found(self):
        eng = _engine()
        r = eng.record_response(
            threat_id="THR-001",
            response_status=ResponseStatus.CONTAINED,
        )
        result = eng.get_response(r.id)
        assert result is not None
        assert result.response_status == ResponseStatus.CONTAINED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_response("nonexistent") is None


# ---------------------------------------------------------------------------
# list_responses
# ---------------------------------------------------------------------------


class TestListResponses:
    def test_list_all(self):
        eng = _engine()
        eng.record_response(threat_id="THR-001")
        eng.record_response(threat_id="THR-002")
        assert len(eng.list_responses()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_response(
            threat_id="THR-001",
            threat_category=ThreatCategory.MALWARE,
        )
        eng.record_response(
            threat_id="THR-002",
            threat_category=ThreatCategory.PHISHING,
        )
        results = eng.list_responses(
            threat_category=ThreatCategory.MALWARE,
        )
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_response(
            threat_id="THR-001",
            response_status=ResponseStatus.CONTAINED,
        )
        eng.record_response(
            threat_id="THR-002",
            response_status=ResponseStatus.INVESTIGATING,
        )
        results = eng.list_responses(
            response_status=ResponseStatus.CONTAINED,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_response(threat_id="THR-001", team="security")
        eng.record_response(threat_id="THR-002", team="platform")
        results = eng.list_responses(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_response(threat_id=f"THR-{i}")
        assert len(eng.list_responses(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            threat_id="THR-001",
            threat_category=ThreatCategory.INTRUSION,
            assessment_score=75.0,
            threshold=60.0,
            breached=True,
            description="Intrusion assessment",
        )
        assert a.threat_id == "THR-001"
        assert a.threat_category == ThreatCategory.INTRUSION
        assert a.assessment_score == 75.0
        assert a.threshold == 60.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(threat_id=f"THR-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_response_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeResponseDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_response(
            threat_id="THR-001",
            threat_category=ThreatCategory.MALWARE,
            response_time_hours=2.0,
        )
        eng.record_response(
            threat_id="THR-002",
            threat_category=ThreatCategory.MALWARE,
            response_time_hours=4.0,
        )
        result = eng.analyze_response_distribution()
        assert "malware" in result
        assert result["malware"]["count"] == 2
        assert result["malware"]["avg_response_time"] == 3.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_response_distribution() == {}


# ---------------------------------------------------------------------------
# identify_slow_responses
# ---------------------------------------------------------------------------


class TestIdentifySlowResponses:
    def test_detects_slow(self):
        eng = _engine(max_response_time_hours=4.0)
        eng.record_response(
            threat_id="THR-001",
            response_time_hours=6.0,
        )
        eng.record_response(
            threat_id="THR-002",
            response_time_hours=2.0,
        )
        results = eng.identify_slow_responses()
        assert len(results) == 1
        assert results[0]["threat_id"] == "THR-001"

    def test_at_threshold_not_slow(self):
        eng = _engine(max_response_time_hours=4.0)
        eng.record_response(
            threat_id="THR-001",
            response_time_hours=4.0,
        )
        results = eng.identify_slow_responses()
        assert len(results) == 0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_responses() == []


# ---------------------------------------------------------------------------
# rank_by_response_time
# ---------------------------------------------------------------------------


class TestRankByResponseTime:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_response(
            threat_id="THR-001",
            service="email-gateway",
            response_time_hours=6.0,
        )
        eng.record_response(
            threat_id="THR-002",
            service="web-app",
            response_time_hours=2.0,
        )
        results = eng.rank_by_response_time()
        assert len(results) == 2
        assert results[0]["service"] == "email-gateway"
        assert results[0]["avg_response_time"] == 6.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_response_time() == []


# ---------------------------------------------------------------------------
# detect_response_trends
# ---------------------------------------------------------------------------


class TestDetectResponseTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(threat_id="THR-001", assessment_score=50.0)
        result = eng.detect_response_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(threat_id="THR-001", assessment_score=30.0)
        eng.add_assessment(threat_id="THR-002", assessment_score=30.0)
        eng.add_assessment(threat_id="THR-003", assessment_score=80.0)
        eng.add_assessment(threat_id="THR-004", assessment_score=80.0)
        result = eng.detect_response_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_response_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_response_time_hours=4.0)
        eng.record_response(
            threat_id="THR-001",
            threat_category=ThreatCategory.INTRUSION,
            response_status=ResponseStatus.INVESTIGATING,
            response_effectiveness=ResponseEffectiveness.POOR,
            response_time_hours=6.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ThreatResponseReport)
        assert report.total_records == 1
        assert report.active_threats == 1
        assert len(report.top_slow_responses) == 1
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
        eng.record_response(threat_id="THR-001")
        eng.add_assessment(threat_id="THR-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_response(
            threat_id="THR-001",
            threat_category=ThreatCategory.MALWARE,
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_threats"] == 1
        assert "malware" in stats["category_distribution"]
