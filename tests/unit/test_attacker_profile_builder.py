"""Tests for shieldops.security.attacker_profile_builder — AttackerProfileBuilder."""

from __future__ import annotations

from shieldops.security.attacker_profile_builder import (
    AttackerProfileBuilder,
    AttributionSource,
    ProfileAnalysis,
    ProfileConfidence,
    ProfileRecord,
    ProfileReport,
    ProfileType,
)


def _engine(**kw) -> AttackerProfileBuilder:
    return AttackerProfileBuilder(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_nation_state(self):
        assert ProfileType.NATION_STATE == "nation_state"

    def test_type_apt_group(self):
        assert ProfileType.APT_GROUP == "apt_group"

    def test_type_cybercriminal(self):
        assert ProfileType.CYBERCRIMINAL == "cybercriminal"

    def test_type_hacktivist(self):
        assert ProfileType.HACKTIVIST == "hacktivist"

    def test_type_insider(self):
        assert ProfileType.INSIDER == "insider"

    def test_confidence_confirmed(self):
        assert ProfileConfidence.CONFIRMED == "confirmed"

    def test_confidence_high(self):
        assert ProfileConfidence.HIGH == "high"

    def test_confidence_medium(self):
        assert ProfileConfidence.MEDIUM == "medium"

    def test_confidence_low(self):
        assert ProfileConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert ProfileConfidence.SPECULATIVE == "speculative"

    def test_source_threat_intel(self):
        assert AttributionSource.THREAT_INTEL == "threat_intel"

    def test_source_forensic_evidence(self):
        assert AttributionSource.FORENSIC_EVIDENCE == "forensic_evidence"

    def test_source_behavioral_analysis(self):
        assert AttributionSource.BEHAVIORAL_ANALYSIS == "behavioral_analysis"

    def test_source_osint(self):
        assert AttributionSource.OSINT == "osint"

    def test_source_honeypot_data(self):
        assert AttributionSource.HONEYPOT_DATA == "honeypot_data"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_profile_record_defaults(self):
        r = ProfileRecord()
        assert r.id
        assert r.profile_name == ""
        assert r.profile_type == ProfileType.NATION_STATE
        assert r.profile_confidence == ProfileConfidence.CONFIRMED
        assert r.attribution_source == AttributionSource.THREAT_INTEL
        assert r.profile_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_profile_analysis_defaults(self):
        a = ProfileAnalysis()
        assert a.id
        assert a.profile_name == ""
        assert a.profile_type == ProfileType.NATION_STATE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_profile_report_defaults(self):
        r = ProfileReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_confidence_count == 0
        assert r.avg_profile_score == 0.0
        assert r.by_type == {}
        assert r.by_confidence == {}
        assert r.by_source == {}
        assert r.top_low_confidence == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_profile
# ---------------------------------------------------------------------------


class TestRecordProfile:
    def test_basic(self):
        eng = _engine()
        r = eng.record_profile(
            profile_name="APT-29",
            profile_type=ProfileType.APT_GROUP,
            profile_confidence=ProfileConfidence.HIGH,
            attribution_source=AttributionSource.THREAT_INTEL,
            profile_score=82.0,
            service="threat-intel-svc",
            team="security",
        )
        assert r.profile_name == "APT-29"
        assert r.profile_type == ProfileType.APT_GROUP
        assert r.profile_confidence == ProfileConfidence.HIGH
        assert r.attribution_source == AttributionSource.THREAT_INTEL
        assert r.profile_score == 82.0
        assert r.service == "threat-intel-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_profile(profile_name=f"PRF-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------


class TestGetProfile:
    def test_found(self):
        eng = _engine()
        r = eng.record_profile(
            profile_name="APT-29",
            profile_type=ProfileType.APT_GROUP,
        )
        result = eng.get_profile(r.id)
        assert result is not None
        assert result.profile_type == ProfileType.APT_GROUP

    def test_not_found(self):
        eng = _engine()
        assert eng.get_profile("nonexistent") is None


# ---------------------------------------------------------------------------
# list_profiles
# ---------------------------------------------------------------------------


class TestListProfiles:
    def test_list_all(self):
        eng = _engine()
        eng.record_profile(profile_name="PRF-001")
        eng.record_profile(profile_name="PRF-002")
        assert len(eng.list_profiles()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_profile(
            profile_name="PRF-001",
            profile_type=ProfileType.NATION_STATE,
        )
        eng.record_profile(
            profile_name="PRF-002",
            profile_type=ProfileType.CYBERCRIMINAL,
        )
        results = eng.list_profiles(profile_type=ProfileType.NATION_STATE)
        assert len(results) == 1

    def test_filter_by_confidence(self):
        eng = _engine()
        eng.record_profile(
            profile_name="PRF-001",
            profile_confidence=ProfileConfidence.CONFIRMED,
        )
        eng.record_profile(
            profile_name="PRF-002",
            profile_confidence=ProfileConfidence.SPECULATIVE,
        )
        results = eng.list_profiles(
            profile_confidence=ProfileConfidence.CONFIRMED,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_profile(profile_name="PRF-001", team="security")
        eng.record_profile(profile_name="PRF-002", team="platform")
        results = eng.list_profiles(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_profile(profile_name=f"PRF-{i}")
        assert len(eng.list_profiles(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            profile_name="APT-29",
            profile_type=ProfileType.APT_GROUP,
            analysis_score=88.5,
            threshold=65.0,
            breached=True,
            description="attribution confidence analysis",
        )
        assert a.profile_name == "APT-29"
        assert a.profile_type == ProfileType.APT_GROUP
        assert a.analysis_score == 88.5
        assert a.threshold == 65.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(profile_name=f"PRF-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_profile_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeProfileDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_profile(
            profile_name="PRF-001",
            profile_type=ProfileType.NATION_STATE,
            profile_score=90.0,
        )
        eng.record_profile(
            profile_name="PRF-002",
            profile_type=ProfileType.NATION_STATE,
            profile_score=70.0,
        )
        result = eng.analyze_profile_distribution()
        assert "nation_state" in result
        assert result["nation_state"]["count"] == 2
        assert result["nation_state"]["avg_profile_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_profile_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_confidence_profiles
# ---------------------------------------------------------------------------


class TestIdentifyLowConfidenceProfiles:
    def test_detects_below_threshold(self):
        eng = _engine(profile_confidence_threshold=65.0)
        eng.record_profile(profile_name="PRF-001", profile_score=40.0)
        eng.record_profile(profile_name="PRF-002", profile_score=80.0)
        results = eng.identify_low_confidence_profiles()
        assert len(results) == 1
        assert results[0]["profile_name"] == "PRF-001"

    def test_sorted_ascending(self):
        eng = _engine(profile_confidence_threshold=65.0)
        eng.record_profile(profile_name="PRF-001", profile_score=50.0)
        eng.record_profile(profile_name="PRF-002", profile_score=30.0)
        results = eng.identify_low_confidence_profiles()
        assert len(results) == 2
        assert results[0]["profile_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_profiles() == []


# ---------------------------------------------------------------------------
# rank_by_profile
# ---------------------------------------------------------------------------


class TestRankByProfile:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_profile(profile_name="PRF-001", service="threat-intel-svc", profile_score=90.0)
        eng.record_profile(profile_name="PRF-002", service="attribution-svc", profile_score=50.0)
        results = eng.rank_by_profile()
        assert len(results) == 2
        assert results[0]["service"] == "attribution-svc"
        assert results[0]["avg_profile_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_profile() == []


# ---------------------------------------------------------------------------
# detect_profile_trends
# ---------------------------------------------------------------------------


class TestDetectProfileTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(profile_name="PRF-001", analysis_score=50.0)
        result = eng.detect_profile_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(profile_name="PRF-001", analysis_score=20.0)
        eng.add_analysis(profile_name="PRF-002", analysis_score=20.0)
        eng.add_analysis(profile_name="PRF-003", analysis_score=80.0)
        eng.add_analysis(profile_name="PRF-004", analysis_score=80.0)
        result = eng.detect_profile_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_profile_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(profile_confidence_threshold=65.0)
        eng.record_profile(
            profile_name="APT-29",
            profile_type=ProfileType.APT_GROUP,
            profile_confidence=ProfileConfidence.HIGH,
            attribution_source=AttributionSource.THREAT_INTEL,
            profile_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ProfileReport)
        assert report.total_records == 1
        assert report.low_confidence_count == 1
        assert len(report.top_low_confidence) == 1
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
        eng.record_profile(profile_name="PRF-001")
        eng.add_analysis(profile_name="PRF-001")
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
        eng.record_profile(
            profile_name="PRF-001",
            profile_type=ProfileType.NATION_STATE,
            service="threat-intel-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "nation_state" in stats["type_distribution"]
