"""Tests for shieldops.security.access_anomaly — AccessAnomalyDetector."""

from __future__ import annotations

from shieldops.security.access_anomaly import (
    AccessAnomalyDetector,
    AccessAnomalyRecord,
    AccessAnomalyReport,
    AccessBaseline,
    AccessContext,
    AnomalyType,
    ThreatLevel,
)


def _engine(**kw) -> AccessAnomalyDetector:
    return AccessAnomalyDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # AnomalyType (5)
    def test_type_unusual_time(self):
        assert AnomalyType.UNUSUAL_TIME == "unusual_time"

    def test_type_impossible_travel(self):
        assert AnomalyType.IMPOSSIBLE_TRAVEL == "impossible_travel"

    def test_type_privilege_escalation(self):
        assert AnomalyType.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_type_bulk_access(self):
        assert AnomalyType.BULK_ACCESS == "bulk_access"

    def test_type_dormant_reactivation(self):
        assert AnomalyType.DORMANT_REACTIVATION == "dormant_reactivation"

    # ThreatLevel (5)
    def test_level_benign(self):
        assert ThreatLevel.BENIGN == "benign"

    def test_level_suspicious(self):
        assert ThreatLevel.SUSPICIOUS == "suspicious"

    def test_level_elevated(self):
        assert ThreatLevel.ELEVATED == "elevated"

    def test_level_high_risk(self):
        assert ThreatLevel.HIGH_RISK == "high_risk"

    def test_level_confirmed_threat(self):
        assert ThreatLevel.CONFIRMED_THREAT == "confirmed_threat"

    # AccessContext (5)
    def test_context_corporate_network(self):
        assert AccessContext.CORPORATE_NETWORK == "corporate_network"

    def test_context_vpn(self):
        assert AccessContext.VPN == "vpn"

    def test_context_public_internet(self):
        assert AccessContext.PUBLIC_INTERNET == "public_internet"

    def test_context_cloud_console(self):
        assert AccessContext.CLOUD_CONSOLE == "cloud_console"

    def test_context_api_key(self):
        assert AccessContext.API_KEY == "api_key"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_access_anomaly_record_defaults(self):
        r = AccessAnomalyRecord()
        assert r.id
        assert r.user_id == ""
        assert r.anomaly_type == AnomalyType.UNUSUAL_TIME
        assert r.threat_level == ThreatLevel.SUSPICIOUS
        assert r.context == AccessContext.CORPORATE_NETWORK
        assert r.source_ip == ""
        assert r.location == ""
        assert r.resource_accessed == ""
        assert r.threat_score == 0.0
        assert r.investigated is False
        assert r.false_positive is False
        assert r.created_at > 0

    def test_access_baseline_defaults(self):
        b = AccessBaseline()
        assert b.id
        assert b.user_id == ""
        assert b.usual_hours == list(range(8, 18))
        assert b.usual_locations == []
        assert b.usual_contexts == []
        assert b.avg_daily_accesses == 0.0
        assert b.last_active_at == 0.0
        assert b.created_at > 0

    def test_access_anomaly_report_defaults(self):
        r = AccessAnomalyReport()
        assert r.total_anomalies == 0
        assert r.high_risk_count == 0
        assert r.investigated_count == 0
        assert r.false_positive_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_threat_level == {}
        assert r.high_risk_users == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_anomaly
# ---------------------------------------------------------------------------


class TestRecordAnomaly:
    def test_basic(self):
        eng = _engine()
        r = eng.record_anomaly(
            user_id="user-1",
            anomaly_type=AnomalyType.UNUSUAL_TIME,
        )
        assert r.user_id == "user-1"
        assert r.anomaly_type == AnomalyType.UNUSUAL_TIME
        assert r.threat_score == 0.5
        assert r.threat_level == ThreatLevel.ELEVATED

    def test_high_threat_score(self):
        eng = _engine()
        r = eng.record_anomaly(
            user_id="user-2",
            anomaly_type=AnomalyType.PRIVILEGE_ESCALATION,
            threat_score=0.95,
        )
        assert r.threat_level == ThreatLevel.CONFIRMED_THREAT
        assert r.threat_score == 0.95

    def test_low_threat_score(self):
        eng = _engine()
        r = eng.record_anomaly(
            user_id="user-3",
            anomaly_type=AnomalyType.BULK_ACCESS,
            threat_score=0.1,
        )
        assert r.threat_level == ThreatLevel.BENIGN

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_anomaly(
                user_id=f"user-{i}",
                anomaly_type=AnomalyType.UNUSUAL_TIME,
            )
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_anomaly
# ---------------------------------------------------------------------------


class TestGetAnomaly:
    def test_found(self):
        eng = _engine()
        r = eng.record_anomaly(
            user_id="user-1",
            anomaly_type=AnomalyType.UNUSUAL_TIME,
        )
        result = eng.get_anomaly(r.id)
        assert result is not None
        assert result.user_id == "user-1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_anomaly("nonexistent") is None


# ---------------------------------------------------------------------------
# list_anomalies
# ---------------------------------------------------------------------------


class TestListAnomalies:
    def test_list_all(self):
        eng = _engine()
        eng.record_anomaly(user_id="user-1", anomaly_type=AnomalyType.UNUSUAL_TIME)
        eng.record_anomaly(user_id="user-2", anomaly_type=AnomalyType.BULK_ACCESS)
        assert len(eng.list_anomalies()) == 2

    def test_filter_by_user_id(self):
        eng = _engine()
        eng.record_anomaly(user_id="user-1", anomaly_type=AnomalyType.UNUSUAL_TIME)
        eng.record_anomaly(user_id="user-2", anomaly_type=AnomalyType.BULK_ACCESS)
        results = eng.list_anomalies(user_id="user-1")
        assert len(results) == 1
        assert results[0].user_id == "user-1"

    def test_filter_by_anomaly_type(self):
        eng = _engine()
        eng.record_anomaly(user_id="user-1", anomaly_type=AnomalyType.UNUSUAL_TIME)
        eng.record_anomaly(user_id="user-2", anomaly_type=AnomalyType.BULK_ACCESS)
        results = eng.list_anomalies(anomaly_type=AnomalyType.BULK_ACCESS)
        assert len(results) == 1
        assert results[0].anomaly_type == AnomalyType.BULK_ACCESS


# ---------------------------------------------------------------------------
# assess_threat_level
# ---------------------------------------------------------------------------


class TestAssessThreatLevel:
    def test_valid(self):
        eng = _engine()
        r = eng.record_anomaly(
            user_id="user-1",
            anomaly_type=AnomalyType.UNUSUAL_TIME,
            threat_score=0.5,
        )
        result = eng.assess_threat_level(r.id)
        assert result["found"] is True
        assert result["record_id"] == r.id
        assert result["user_id"] == "user-1"
        assert result["threat_score"] == 0.5

    def test_not_found(self):
        eng = _engine()
        result = eng.assess_threat_level("nonexistent")
        assert result["found"] is False


# ---------------------------------------------------------------------------
# create_baseline
# ---------------------------------------------------------------------------


class TestCreateBaseline:
    def test_basic(self):
        eng = _engine()
        b = eng.create_baseline(user_id="user-1")
        assert b.user_id == "user-1"
        assert b.usual_hours == list(range(8, 18))
        assert b.usual_locations == []
        assert b.usual_contexts == []
        assert b.avg_daily_accesses == 0.0
        assert b.last_active_at > 0

    def test_with_all_params(self):
        eng = _engine()
        b = eng.create_baseline(
            user_id="user-2",
            usual_hours=[9, 10, 11, 12, 13, 14, 15, 16, 17],
            usual_locations=["New York", "Boston"],
            usual_contexts=["corporate_network", "vpn"],
            avg_daily_accesses=25.0,
        )
        assert b.usual_hours == [9, 10, 11, 12, 13, 14, 15, 16, 17]
        assert b.usual_locations == ["New York", "Boston"]
        assert b.usual_contexts == ["corporate_network", "vpn"]
        assert b.avg_daily_accesses == 25.0


# ---------------------------------------------------------------------------
# detect_impossible_travel
# ---------------------------------------------------------------------------


class TestDetectImpossibleTravel:
    def test_travel_detected(self):
        eng = _engine()
        result = eng.detect_impossible_travel(
            user_id="user-1",
            location_a="New York",
            location_b="London",
            time_diff_minutes=30.0,
        )
        assert result["is_impossible"] is True
        assert result["threat_score"] > 0
        assert result["user_id"] == "user-1"
        assert len(eng._records) == 1
        assert eng._records[0].anomaly_type == AnomalyType.IMPOSSIBLE_TRAVEL

    def test_no_travel_same_location(self):
        eng = _engine()
        result = eng.detect_impossible_travel(
            user_id="user-1",
            location_a="New York",
            location_b="New York",
            time_diff_minutes=10.0,
        )
        assert result["is_impossible"] is False
        assert result["threat_score"] == 0.0
        assert len(eng._records) == 0


# ---------------------------------------------------------------------------
# identify_high_risk_users
# ---------------------------------------------------------------------------


class TestIdentifyHighRiskUsers:
    def test_has_high_risk(self):
        eng = _engine(threat_threshold=0.7)
        eng.record_anomaly(
            user_id="user-1",
            anomaly_type=AnomalyType.PRIVILEGE_ESCALATION,
            threat_score=0.85,
        )
        eng.record_anomaly(
            user_id="user-2",
            anomaly_type=AnomalyType.UNUSUAL_TIME,
            threat_score=0.2,
        )
        results = eng.identify_high_risk_users()
        assert len(results) == 1
        assert results[0]["user_id"] == "user-1"
        assert results[0]["max_threat_score"] == 0.85

    def test_none_high_risk(self):
        eng = _engine(threat_threshold=0.7)
        eng.record_anomaly(
            user_id="user-1",
            anomaly_type=AnomalyType.UNUSUAL_TIME,
            threat_score=0.2,
        )
        results = eng.identify_high_risk_users()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# mark_investigated
# ---------------------------------------------------------------------------


class TestMarkInvestigated:
    def test_mark_investigated(self):
        eng = _engine()
        r = eng.record_anomaly(
            user_id="user-1",
            anomaly_type=AnomalyType.UNUSUAL_TIME,
        )
        result = eng.mark_investigated(r.id)
        assert result["found"] is True
        assert result["investigated"] is True
        assert result["false_positive"] is False
        assert r.investigated is True
        assert r.false_positive is False

    def test_mark_false_positive(self):
        eng = _engine()
        r = eng.record_anomaly(
            user_id="user-1",
            anomaly_type=AnomalyType.UNUSUAL_TIME,
        )
        result = eng.mark_investigated(r.id, false_positive=True)
        assert result["found"] is True
        assert result["false_positive"] is True
        assert r.false_positive is True


# ---------------------------------------------------------------------------
# generate_anomaly_report
# ---------------------------------------------------------------------------


class TestGenerateAnomalyReport:
    def test_populated(self):
        eng = _engine()
        eng.record_anomaly(
            user_id="user-1",
            anomaly_type=AnomalyType.UNUSUAL_TIME,
            threat_score=0.5,
        )
        eng.record_anomaly(
            user_id="user-2",
            anomaly_type=AnomalyType.PRIVILEGE_ESCALATION,
            threat_score=0.85,
        )
        report = eng.generate_anomaly_report()
        assert isinstance(report, AccessAnomalyReport)
        assert report.total_anomalies == 2
        assert report.high_risk_count == 1
        assert len(report.by_type) == 2
        assert len(report.by_threat_level) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_anomaly_report()
        assert report.total_anomalies == 0
        assert report.high_risk_count == 0
        assert "No significant access anomalies detected" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_anomaly(
            user_id="user-1",
            anomaly_type=AnomalyType.UNUSUAL_TIME,
        )
        eng.create_baseline(user_id="user-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._baselines) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_anomalies"] == 0
        assert stats["total_baselines"] == 0
        assert stats["type_distribution"] == {}
        assert stats["unique_users"] == 0
        assert stats["investigated"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_anomaly(
            user_id="user-1",
            anomaly_type=AnomalyType.UNUSUAL_TIME,
        )
        eng.create_baseline(user_id="user-1")
        stats = eng.get_stats()
        assert stats["total_anomalies"] == 1
        assert stats["total_baselines"] == 1
        assert stats["threat_threshold"] == 0.7
        assert "unusual_time" in stats["type_distribution"]
        assert stats["unique_users"] == 1
