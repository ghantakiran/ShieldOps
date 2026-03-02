"""Tests for shieldops.security.dlp_scorer — DLPScorer."""

from __future__ import annotations

from shieldops.security.dlp_scorer import (
    DataChannel,
    DataSensitivity,
    DLPAnalysis,
    DLPRecord,
    DLPReport,
    DLPScorer,
    PolicyAction,
)


def _engine(**kw) -> DLPScorer:
    return DLPScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_channel_email(self):
        assert DataChannel.EMAIL == "email"

    def test_channel_cloud_storage(self):
        assert DataChannel.CLOUD_STORAGE == "cloud_storage"

    def test_channel_usb(self):
        assert DataChannel.USB == "usb"

    def test_channel_web_upload(self):
        assert DataChannel.WEB_UPLOAD == "web_upload"

    def test_channel_api_transfer(self):
        assert DataChannel.API_TRANSFER == "api_transfer"

    def test_sensitivity_top_secret(self):
        assert DataSensitivity.TOP_SECRET == "top_secret"  # noqa: S105

    def test_sensitivity_confidential(self):
        assert DataSensitivity.CONFIDENTIAL == "confidential"

    def test_sensitivity_internal(self):
        assert DataSensitivity.INTERNAL == "internal"

    def test_sensitivity_public(self):
        assert DataSensitivity.PUBLIC == "public"

    def test_sensitivity_unclassified(self):
        assert DataSensitivity.UNCLASSIFIED == "unclassified"

    def test_action_block(self):
        assert PolicyAction.BLOCK == "block"

    def test_action_encrypt(self):
        assert PolicyAction.ENCRYPT == "encrypt"

    def test_action_alert(self):
        assert PolicyAction.ALERT == "alert"

    def test_action_log(self):
        assert PolicyAction.LOG == "log"

    def test_action_allow(self):
        assert PolicyAction.ALLOW == "allow"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dlp_record_defaults(self):
        r = DLPRecord()
        assert r.id
        assert r.policy_name == ""
        assert r.data_channel == DataChannel.EMAIL
        assert r.data_sensitivity == DataSensitivity.TOP_SECRET
        assert r.policy_action == PolicyAction.BLOCK
        assert r.protection_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_dlp_analysis_defaults(self):
        c = DLPAnalysis()
        assert c.id
        assert c.policy_name == ""
        assert c.data_channel == DataChannel.EMAIL
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_dlp_report_defaults(self):
        r = DLPReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_protection_count == 0
        assert r.avg_protection_score == 0.0
        assert r.by_channel == {}
        assert r.by_sensitivity == {}
        assert r.by_action == {}
        assert r.top_low_protection == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_policy
# ---------------------------------------------------------------------------


class TestRecordPolicy:
    def test_basic(self):
        eng = _engine()
        r = eng.record_policy(
            policy_name="block-pii",
            data_channel=DataChannel.CLOUD_STORAGE,
            data_sensitivity=DataSensitivity.CONFIDENTIAL,
            policy_action=PolicyAction.ENCRYPT,
            protection_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.policy_name == "block-pii"
        assert r.data_channel == DataChannel.CLOUD_STORAGE
        assert r.data_sensitivity == DataSensitivity.CONFIDENTIAL
        assert r.policy_action == PolicyAction.ENCRYPT
        assert r.protection_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_policy(policy_name=f"P-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_policy
# ---------------------------------------------------------------------------


class TestGetPolicy:
    def test_found(self):
        eng = _engine()
        r = eng.record_policy(
            policy_name="block-pii",
            policy_action=PolicyAction.BLOCK,
        )
        result = eng.get_policy(r.id)
        assert result is not None
        assert result.policy_action == PolicyAction.BLOCK

    def test_not_found(self):
        eng = _engine()
        assert eng.get_policy("nonexistent") is None


# ---------------------------------------------------------------------------
# list_policies
# ---------------------------------------------------------------------------


class TestListPolicies:
    def test_list_all(self):
        eng = _engine()
        eng.record_policy(policy_name="P-001")
        eng.record_policy(policy_name="P-002")
        assert len(eng.list_policies()) == 2

    def test_filter_by_data_channel(self):
        eng = _engine()
        eng.record_policy(
            policy_name="P-001",
            data_channel=DataChannel.EMAIL,
        )
        eng.record_policy(
            policy_name="P-002",
            data_channel=DataChannel.USB,
        )
        results = eng.list_policies(data_channel=DataChannel.EMAIL)
        assert len(results) == 1

    def test_filter_by_data_sensitivity(self):
        eng = _engine()
        eng.record_policy(
            policy_name="P-001",
            data_sensitivity=DataSensitivity.TOP_SECRET,
        )
        eng.record_policy(
            policy_name="P-002",
            data_sensitivity=DataSensitivity.PUBLIC,
        )
        results = eng.list_policies(
            data_sensitivity=DataSensitivity.TOP_SECRET,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_policy(policy_name="P-001", team="security")
        eng.record_policy(policy_name="P-002", team="platform")
        results = eng.list_policies(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_policy(policy_name=f"P-{i}")
        assert len(eng.list_policies(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            policy_name="block-pii",
            data_channel=DataChannel.CLOUD_STORAGE,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="protection gap detected",
        )
        assert a.policy_name == "block-pii"
        assert a.data_channel == DataChannel.CLOUD_STORAGE
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(policy_name=f"P-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_channel_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_policy(
            policy_name="P-001",
            data_channel=DataChannel.EMAIL,
            protection_score=90.0,
        )
        eng.record_policy(
            policy_name="P-002",
            data_channel=DataChannel.EMAIL,
            protection_score=70.0,
        )
        result = eng.analyze_channel_distribution()
        assert "email" in result
        assert result["email"]["count"] == 2
        assert result["email"]["avg_protection_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_channel_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_protection_policies
# ---------------------------------------------------------------------------


class TestIdentifyLowProtectionPolicies:
    def test_detects_below_threshold(self):
        eng = _engine(protection_threshold=80.0)
        eng.record_policy(policy_name="P-001", protection_score=60.0)
        eng.record_policy(policy_name="P-002", protection_score=90.0)
        results = eng.identify_low_protection_policies()
        assert len(results) == 1
        assert results[0]["policy_name"] == "P-001"

    def test_sorted_ascending(self):
        eng = _engine(protection_threshold=80.0)
        eng.record_policy(policy_name="P-001", protection_score=50.0)
        eng.record_policy(policy_name="P-002", protection_score=30.0)
        results = eng.identify_low_protection_policies()
        assert len(results) == 2
        assert results[0]["protection_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_protection_policies() == []


# ---------------------------------------------------------------------------
# rank_by_protection_score
# ---------------------------------------------------------------------------


class TestRankByProtectionScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_policy(policy_name="P-001", service="auth-svc", protection_score=90.0)
        eng.record_policy(policy_name="P-002", service="api-gw", protection_score=50.0)
        results = eng.rank_by_protection_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_protection_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_protection_score() == []


# ---------------------------------------------------------------------------
# detect_protection_trends
# ---------------------------------------------------------------------------


class TestDetectProtectionTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(policy_name="P-001", analysis_score=50.0)
        result = eng.detect_protection_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(policy_name="P-001", analysis_score=20.0)
        eng.add_analysis(policy_name="P-002", analysis_score=20.0)
        eng.add_analysis(policy_name="P-003", analysis_score=80.0)
        eng.add_analysis(policy_name="P-004", analysis_score=80.0)
        result = eng.detect_protection_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_protection_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(protection_threshold=80.0)
        eng.record_policy(
            policy_name="block-pii",
            data_channel=DataChannel.CLOUD_STORAGE,
            data_sensitivity=DataSensitivity.CONFIDENTIAL,
            policy_action=PolicyAction.ENCRYPT,
            protection_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DLPReport)
        assert report.total_records == 1
        assert report.low_protection_count == 1
        assert len(report.top_low_protection) == 1
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
        eng.record_policy(policy_name="P-001")
        eng.add_analysis(policy_name="P-001")
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
        assert stats["channel_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_policy(
            policy_name="P-001",
            data_channel=DataChannel.EMAIL,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "email" in stats["channel_distribution"]
