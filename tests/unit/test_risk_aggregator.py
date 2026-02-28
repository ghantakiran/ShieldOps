"""Tests for shieldops.security.risk_aggregator — RiskSignalAggregator."""

from __future__ import annotations

from shieldops.security.risk_aggregator import (
    AggregatedRiskScore,
    AggregationMethod,
    RiskSignalAggregator,
    RiskSignalRecord,
    RiskSignalReport,
    SignalDomain,
    SignalSeverity,
)


def _engine(**kw) -> RiskSignalAggregator:
    return RiskSignalAggregator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # SignalDomain (5)
    def test_domain_security(self):
        assert SignalDomain.SECURITY == "security"

    def test_domain_reliability(self):
        assert SignalDomain.RELIABILITY == "reliability"

    def test_domain_cost(self):
        assert SignalDomain.COST == "cost"

    def test_domain_compliance(self):
        assert SignalDomain.COMPLIANCE == "compliance"

    def test_domain_operational(self):
        assert SignalDomain.OPERATIONAL == "operational"

    # SignalSeverity (5)
    def test_severity_critical(self):
        assert SignalSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert SignalSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert SignalSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert SignalSeverity.LOW == "low"

    def test_severity_info(self):
        assert SignalSeverity.INFO == "info"

    # AggregationMethod (5)
    def test_method_weighted_average(self):
        assert AggregationMethod.WEIGHTED_AVERAGE == "weighted_average"

    def test_method_max_severity(self):
        assert AggregationMethod.MAX_SEVERITY == "max_severity"

    def test_method_bayesian(self):
        assert AggregationMethod.BAYESIAN == "bayesian"

    def test_method_exponential_decay(self):
        assert AggregationMethod.EXPONENTIAL_DECAY == "exponential_decay"

    def test_method_custom(self):
        assert AggregationMethod.CUSTOM == "custom"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_risk_signal_record_defaults(self):
        r = RiskSignalRecord()
        assert r.id
        assert r.service_name == ""
        assert r.signal_domain == SignalDomain.SECURITY
        assert r.signal_severity == SignalSeverity.MEDIUM
        assert r.aggregation_method == AggregationMethod.WEIGHTED_AVERAGE
        assert r.risk_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_aggregated_risk_score_defaults(self):
        r = AggregatedRiskScore()
        assert r.id
        assert r.score_label == ""
        assert r.signal_domain == SignalDomain.SECURITY
        assert r.signal_severity == SignalSeverity.MEDIUM
        assert r.weighted_score == 0.0
        assert r.created_at > 0

    def test_risk_signal_report_defaults(self):
        r = RiskSignalReport()
        assert r.total_signals == 0
        assert r.total_scores == 0
        assert r.critical_rate_pct == 0.0
        assert r.by_domain == {}
        assert r.by_severity == {}
        assert r.high_risk_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_signal
# -------------------------------------------------------------------


class TestRecordSignal:
    def test_basic(self):
        eng = _engine()
        r = eng.record_signal(
            "svc-a",
            signal_domain=SignalDomain.SECURITY,
            signal_severity=SignalSeverity.CRITICAL,
        )
        assert r.service_name == "svc-a"
        assert r.signal_domain == SignalDomain.SECURITY

    def test_max_records_trim(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_signal(f"svc-{i}")
        assert len(eng._records) == 3

    def test_get_by_id(self):
        eng = _engine()
        r = eng.record_signal("svc-a")
        assert eng.get_signal(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_signal("nonexistent") is None

    def test_list_filter(self):
        eng = _engine()
        eng.record_signal("svc-a")
        eng.record_signal("svc-b")
        results = eng.list_signals(service_name="svc-a")
        assert len(results) == 1

    def test_list_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_signal(f"svc-{i}")
        results = eng.list_signals(limit=3)
        assert len(results) == 3


# -------------------------------------------------------------------
# add_score
# -------------------------------------------------------------------


class TestAddScore:
    def test_basic(self):
        eng = _engine()
        s = eng.add_score(
            "score-1",
            signal_domain=SignalDomain.SECURITY,
            signal_severity=SignalSeverity.HIGH,
            weighted_score=85.0,
        )
        assert s.score_label == "score-1"
        assert s.weighted_score == 85.0

    def test_trim(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_score(f"score-{i}")
        assert len(eng._scores) == 2


# -------------------------------------------------------------------
# analyze_service_risk
# -------------------------------------------------------------------


class TestAnalyze:
    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_service_risk("ghost")
        assert result["status"] == "no_data"

    def test_with_data(self):
        eng = _engine()
        eng.record_signal("svc-a", signal_severity=SignalSeverity.CRITICAL, risk_score=90.0)
        eng.record_signal("svc-a", signal_severity=SignalSeverity.LOW, risk_score=10.0)
        result = eng.analyze_service_risk("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_signals"] == 2
        assert result["critical_rate_pct"] == 50.0

    def test_meets_threshold(self):
        eng = _engine(critical_threshold=50.0)
        eng.record_signal("svc-a", risk_score=80.0)
        result = eng.analyze_service_risk("svc-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_high_risk_services
# -------------------------------------------------------------------


class TestIdentify:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_services() == []

    def test_with_matches(self):
        eng = _engine()
        eng.record_signal("svc-a", signal_severity=SignalSeverity.CRITICAL)
        eng.record_signal("svc-a", signal_severity=SignalSeverity.HIGH)
        eng.record_signal("svc-b", signal_severity=SignalSeverity.INFO)
        results = eng.identify_high_risk_services()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"


# -------------------------------------------------------------------
# rank_by_risk_score
# -------------------------------------------------------------------


class TestRank:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []

    def test_ordering(self):
        eng = _engine()
        eng.record_signal("svc-a")
        eng.record_signal("svc-a")
        eng.record_signal("svc-b")
        results = eng.rank_by_risk_score()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["signal_count"] == 2


# -------------------------------------------------------------------
# detect_risk_escalations
# -------------------------------------------------------------------


class TestDetect:
    def test_empty(self):
        eng = _engine()
        assert eng.detect_risk_escalations() == []

    def test_detection(self):
        eng = _engine()
        for _ in range(5):
            eng.record_signal("svc-a", signal_severity=SignalSeverity.CRITICAL)
        eng.record_signal("svc-b", signal_severity=SignalSeverity.INFO)
        results = eng.detect_risk_escalations()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["escalation_detected"] is True


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_signals == 0
        assert "meets targets" in report.recommendations[0]

    def test_with_data(self):
        eng = _engine()
        eng.record_signal("svc-a", signal_severity=SignalSeverity.CRITICAL)
        eng.record_signal("svc-b", signal_severity=SignalSeverity.LOW)
        eng.record_signal("svc-b", signal_severity=SignalSeverity.HIGH)
        eng.add_score("score-1")
        report = eng.generate_report()
        assert report.total_signals == 3
        assert report.total_scores == 1
        assert report.by_domain != {}
        assert report.recommendations != []

    def test_recommendations(self):
        eng = _engine()
        eng.record_signal("svc-a", signal_severity=SignalSeverity.CRITICAL)
        report = eng.generate_report()
        assert len(report.recommendations) >= 1


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clear(self):
        eng = _engine()
        eng.record_signal("svc-a")
        eng.add_score("score-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._scores) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_signals"] == 0
        assert stats["total_scores"] == 0
        assert stats["domain_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_signal("svc-a", signal_domain=SignalDomain.SECURITY)
        eng.record_signal("svc-b", signal_domain=SignalDomain.RELIABILITY)
        eng.add_score("score-1")
        stats = eng.get_stats()
        assert stats["total_signals"] == 2
        assert stats["total_scores"] == 1
        assert stats["unique_services"] == 2
