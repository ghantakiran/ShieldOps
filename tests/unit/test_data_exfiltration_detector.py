"""Tests for shieldops.analytics.data_exfiltration_detector — DataExfiltrationDetector."""

from __future__ import annotations

from shieldops.analytics.data_exfiltration_detector import (
    DataExfiltrationDetector,
    DataExfiltrationReport,
    DetectionConfidence,
    ExfilAnalysis,
    ExfilChannel,
    ExfilIndicator,
    ExfilRecord,
)


def _engine(**kw) -> DataExfiltrationDetector:
    return DataExfiltrationDetector(**kw)


class TestEnums:
    def test_channel_email(self):
        assert ExfilChannel.EMAIL == "email"

    def test_channel_cloud_storage(self):
        assert ExfilChannel.CLOUD_STORAGE == "cloud_storage"

    def test_channel_usb(self):
        assert ExfilChannel.USB == "usb"

    def test_channel_dns_tunnel(self):
        assert ExfilChannel.DNS_TUNNEL == "dns_tunnel"

    def test_channel_encrypted_channel(self):
        assert ExfilChannel.ENCRYPTED_CHANNEL == "encrypted_channel"

    def test_indicator_volume_spike(self):
        assert ExfilIndicator.VOLUME_SPIKE == "volume_spike"

    def test_indicator_unusual_destination(self):
        assert ExfilIndicator.UNUSUAL_DESTINATION == "unusual_destination"

    def test_indicator_off_hours_transfer(self):
        assert ExfilIndicator.OFF_HOURS_TRANSFER == "off_hours_transfer"

    def test_indicator_sensitive_data(self):
        assert ExfilIndicator.SENSITIVE_DATA == "sensitive_data"

    def test_indicator_repeated_pattern(self):
        assert ExfilIndicator.REPEATED_PATTERN == "repeated_pattern"

    def test_confidence_low(self):
        assert DetectionConfidence.LOW == "low"

    def test_confidence_medium(self):
        assert DetectionConfidence.MEDIUM == "medium"

    def test_confidence_high(self):
        assert DetectionConfidence.HIGH == "high"

    def test_confidence_confirmed(self):
        assert DetectionConfidence.CONFIRMED == "confirmed"

    def test_confidence_suspected(self):
        assert DetectionConfidence.SUSPECTED == "suspected"


class TestModels:
    def test_record_defaults(self):
        r = ExfilRecord()
        assert r.id
        assert r.entity_name == ""
        assert r.exfil_channel == ExfilChannel.EMAIL
        assert r.exfil_indicator == ExfilIndicator.VOLUME_SPIKE
        assert r.detection_confidence == DetectionConfidence.SUSPECTED
        assert r.exfil_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ExfilAnalysis()
        assert a.id
        assert a.entity_name == ""
        assert a.exfil_channel == ExfilChannel.EMAIL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = DataExfiltrationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_exfil_score == 0.0
        assert r.by_exfil_channel == {}
        assert r.by_exfil_indicator == {}
        assert r.by_detection_confidence == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_exfil(
            entity_name="exfil-001",
            exfil_channel=ExfilChannel.CLOUD_STORAGE,
            exfil_indicator=ExfilIndicator.VOLUME_SPIKE,
            detection_confidence=DetectionConfidence.HIGH,
            exfil_score=85.0,
            service="dlp-svc",
            team="security",
        )
        assert r.entity_name == "exfil-001"
        assert r.exfil_channel == ExfilChannel.CLOUD_STORAGE
        assert r.exfil_score == 85.0
        assert r.service == "dlp-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_exfil(entity_name=f"exfil-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_exfil(entity_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_exfil(entity_name="a")
        eng.record_exfil(entity_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_exfil_channel(self):
        eng = _engine()
        eng.record_exfil(entity_name="a", exfil_channel=ExfilChannel.EMAIL)
        eng.record_exfil(entity_name="b", exfil_channel=ExfilChannel.USB)
        assert len(eng.list_records(exfil_channel=ExfilChannel.EMAIL)) == 1

    def test_filter_by_exfil_indicator(self):
        eng = _engine()
        eng.record_exfil(entity_name="a", exfil_indicator=ExfilIndicator.VOLUME_SPIKE)
        eng.record_exfil(entity_name="b", exfil_indicator=ExfilIndicator.UNUSUAL_DESTINATION)
        assert len(eng.list_records(exfil_indicator=ExfilIndicator.VOLUME_SPIKE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_exfil(entity_name="a", team="sec")
        eng.record_exfil(entity_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_exfil(entity_name=f"e-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            entity_name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed exfil",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(entity_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_exfil(entity_name="a", exfil_channel=ExfilChannel.EMAIL, exfil_score=90.0)
        eng.record_exfil(entity_name="b", exfil_channel=ExfilChannel.EMAIL, exfil_score=70.0)
        result = eng.analyze_distribution()
        assert "email" in result
        assert result["email"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_exfil(entity_name="a", exfil_score=60.0)
        eng.record_exfil(entity_name="b", exfil_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_exfil(entity_name="a", exfil_score=50.0)
        eng.record_exfil(entity_name="b", exfil_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["exfil_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_exfil(entity_name="a", service="auth", exfil_score=90.0)
        eng.record_exfil(entity_name="b", service="api", exfil_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(entity_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(entity_name="a", analysis_score=20.0)
        eng.add_analysis(entity_name="b", analysis_score=20.0)
        eng.add_analysis(entity_name="c", analysis_score=80.0)
        eng.add_analysis(entity_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_exfil(entity_name="test", exfil_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_exfil(entity_name="test")
        eng.add_analysis(entity_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_exfil(entity_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
