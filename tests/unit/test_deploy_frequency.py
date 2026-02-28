"""Tests for shieldops.changes.deploy_frequency — DeploymentFrequencyAnalyzer."""

from __future__ import annotations

from shieldops.changes.deploy_frequency import (
    DeployFrequencyReport,
    DeploymentFrequencyAnalyzer,
    DeploymentType,
    FrequencyBand,
    FrequencyMetric,
    FrequencyRecord,
    FrequencyTrend,
)


def _engine(**kw) -> DeploymentFrequencyAnalyzer:
    return DeploymentFrequencyAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # FrequencyBand (5)
    def test_band_elite(self):
        assert FrequencyBand.ELITE == "elite"

    def test_band_high(self):
        assert FrequencyBand.HIGH == "high"

    def test_band_medium(self):
        assert FrequencyBand.MEDIUM == "medium"

    def test_band_low(self):
        assert FrequencyBand.LOW == "low"

    def test_band_rare(self):
        assert FrequencyBand.RARE == "rare"

    # DeploymentType (5)
    def test_type_feature(self):
        assert DeploymentType.FEATURE == "feature"

    def test_type_hotfix(self):
        assert DeploymentType.HOTFIX == "hotfix"

    def test_type_rollback(self):
        assert DeploymentType.ROLLBACK == "rollback"

    def test_type_config_change(self):
        assert DeploymentType.CONFIG_CHANGE == "config_change"

    def test_type_infrastructure(self):
        assert DeploymentType.INFRASTRUCTURE == "infrastructure"

    # FrequencyTrend (5)
    def test_trend_accelerating(self):
        assert FrequencyTrend.ACCELERATING == "accelerating"

    def test_trend_stable(self):
        assert FrequencyTrend.STABLE == "stable"

    def test_trend_decelerating(self):
        assert FrequencyTrend.DECELERATING == "decelerating"

    def test_trend_volatile(self):
        assert FrequencyTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert FrequencyTrend.INSUFFICIENT_DATA == "insufficient_data"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_frequency_record_defaults(self):
        r = FrequencyRecord()
        assert r.id
        assert r.service == ""
        assert r.team == ""
        assert r.deployment_type == DeploymentType.FEATURE
        assert r.frequency_band == FrequencyBand.MEDIUM
        assert r.deploys_per_week == 0.0
        assert r.deploy_success_rate == 100.0
        assert r.lead_time_hours == 0.0
        assert r.created_at > 0

    def test_frequency_metric_defaults(self):
        r = FrequencyMetric()
        assert r.id
        assert r.metric_name == ""
        assert r.service == ""
        assert r.team == ""
        assert r.value == 0.0
        assert r.unit == ""
        assert r.trend == FrequencyTrend.STABLE
        assert r.created_at > 0

    def test_report_defaults(self):
        r = DeployFrequencyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.avg_deploys_per_week == 0.0
        assert r.by_frequency_band == {}
        assert r.by_deployment_type == {}
        assert r.by_trend == {}
        assert r.low_frequency_services == []
        assert r.elite_teams == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_frequency
# -------------------------------------------------------------------


class TestRecordFrequency:
    def test_basic(self):
        eng = _engine()
        r = eng.record_frequency("api-service")
        assert r.service == "api-service"
        assert r.frequency_band == FrequencyBand.MEDIUM

    def test_with_params(self):
        eng = _engine()
        r = eng.record_frequency(
            "payment-svc",
            team="payments-team",
            deployment_type=DeploymentType.HOTFIX,
            frequency_band=FrequencyBand.ELITE,
            deploys_per_week=14.0,
            deploy_success_rate=98.5,
            lead_time_hours=2.0,
        )
        assert r.team == "payments-team"
        assert r.frequency_band == FrequencyBand.ELITE
        assert r.deploys_per_week == 14.0

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_frequency("svc-a")
        r2 = eng.record_frequency("svc-b")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_frequency(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_frequency
# -------------------------------------------------------------------


class TestGetFrequency:
    def test_found(self):
        eng = _engine()
        r = eng.record_frequency("api-svc")
        assert eng.get_frequency(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_frequency("nonexistent") is None


# -------------------------------------------------------------------
# list_frequencies
# -------------------------------------------------------------------


class TestListFrequencies:
    def test_list_all(self):
        eng = _engine()
        eng.record_frequency("svc-a")
        eng.record_frequency("svc-b")
        assert len(eng.list_frequencies()) == 2

    def test_filter_by_band(self):
        eng = _engine()
        eng.record_frequency("svc-a", frequency_band=FrequencyBand.ELITE)
        eng.record_frequency("svc-b", frequency_band=FrequencyBand.RARE)
        results = eng.list_frequencies(frequency_band=FrequencyBand.ELITE)
        assert len(results) == 1
        assert results[0].frequency_band == FrequencyBand.ELITE

    def test_filter_by_deployment_type(self):
        eng = _engine()
        eng.record_frequency("svc-a", deployment_type=DeploymentType.HOTFIX)
        eng.record_frequency("svc-b", deployment_type=DeploymentType.FEATURE)
        results = eng.list_frequencies(deployment_type=DeploymentType.HOTFIX)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_frequency("svc-a", team="team-alpha")
        eng.record_frequency("svc-b", team="team-beta")
        results = eng.list_frequencies(team="team-alpha")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_frequency(f"svc-{i}")
        assert len(eng.list_frequencies(limit=3)) == 3


# -------------------------------------------------------------------
# add_metric
# -------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric("deploy-rate")
        assert m.metric_name == "deploy-rate"
        assert m.trend == FrequencyTrend.STABLE

    def test_with_params(self):
        eng = _engine()
        m = eng.add_metric(
            "lead-time",
            service="auth-svc",
            team="auth-team",
            value=4.5,
            unit="hours",
            trend=FrequencyTrend.ACCELERATING,
        )
        assert m.value == 4.5
        assert m.trend == FrequencyTrend.ACCELERATING

    def test_unique_ids(self):
        eng = _engine()
        m1 = eng.add_metric("metric-a")
        m2 = eng.add_metric("metric-b")
        assert m1.id != m2.id


# -------------------------------------------------------------------
# analyze_frequency_by_team
# -------------------------------------------------------------------


class TestAnalyzeFrequencyByTeam:
    def test_empty(self):
        eng = _engine()
        assert eng.analyze_frequency_by_team() == []

    def test_with_data(self):
        eng = _engine()
        eng.record_frequency("svc-a", team="alpha", deploys_per_week=10.0)
        eng.record_frequency("svc-b", team="alpha", deploys_per_week=6.0)
        eng.record_frequency("svc-c", team="beta", deploys_per_week=2.0)
        results = eng.analyze_frequency_by_team()
        assert len(results) == 2
        assert results[0]["team"] == "alpha"
        assert results[0]["avg_deploys_per_week"] == 8.0

    def test_sorted_descending(self):
        eng = _engine()
        eng.record_frequency("svc-x", team="fast-team", deploys_per_week=20.0)
        eng.record_frequency("svc-y", team="slow-team", deploys_per_week=1.0)
        results = eng.analyze_frequency_by_team()
        assert results[0]["avg_deploys_per_week"] >= results[-1]["avg_deploys_per_week"]


# -------------------------------------------------------------------
# identify_low_frequency_services
# -------------------------------------------------------------------


class TestIdentifyLowFrequencyServices:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_frequency_services() == []

    def test_with_low_frequency(self):
        eng = _engine(min_deploy_per_week=2.0)
        eng.record_frequency("slow-svc", deploys_per_week=0.5)
        eng.record_frequency("fast-svc", deploys_per_week=10.0)
        results = eng.identify_low_frequency_services()
        assert len(results) == 1
        assert results[0]["service"] == "slow-svc"

    def test_sorted_ascending(self):
        eng = _engine(min_deploy_per_week=5.0)
        eng.record_frequency("svc-a", deploys_per_week=0.1)
        eng.record_frequency("svc-b", deploys_per_week=1.5)
        results = eng.identify_low_frequency_services()
        assert results[0]["deploys_per_week"] <= results[-1]["deploys_per_week"]


# -------------------------------------------------------------------
# rank_by_deploy_rate
# -------------------------------------------------------------------


class TestRankByDeployRate:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_deploy_rate() == []

    def test_sorted_descending(self):
        eng = _engine()
        eng.record_frequency("svc-a", deploys_per_week=2.0)
        eng.record_frequency("svc-b", deploys_per_week=15.0)
        eng.record_frequency("svc-c", deploys_per_week=7.0)
        results = eng.rank_by_deploy_rate()
        rates = [r["avg_deploys_per_week"] for r in results]
        assert rates == sorted(rates, reverse=True)
        assert results[0]["service"] == "svc-b"


# -------------------------------------------------------------------
# detect_frequency_trends
# -------------------------------------------------------------------


class TestDetectFrequencyTrends:
    def test_insufficient_data(self):
        eng = _engine()
        eng.record_frequency("svc-a", deploys_per_week=5.0)
        result = eng.detect_frequency_trends()
        assert result["trend"] == "insufficient_data"

    def test_stable(self):
        eng = _engine()
        for _ in range(8):
            eng.record_frequency("svc", deploys_per_week=5.0)
        result = eng.detect_frequency_trends()
        assert result["trend"] == "stable"

    def test_accelerating(self):
        eng = _engine()
        for _ in range(4):
            eng.record_frequency("svc", deploys_per_week=2.0)
        for _ in range(4):
            eng.record_frequency("svc", deploys_per_week=10.0)
        result = eng.detect_frequency_trends()
        assert result["trend"] == "accelerating"
        assert result["delta_dpw"] > 0

    def test_decelerating(self):
        eng = _engine()
        for _ in range(4):
            eng.record_frequency("svc", deploys_per_week=10.0)
        for _ in range(4):
            eng.record_frequency("svc", deploys_per_week=1.0)
        result = eng.detect_frequency_trends()
        assert result["trend"] == "decelerating"


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert isinstance(report, DeployFrequencyReport)
        assert report.total_records == 0
        assert report.recommendations

    def test_with_data(self):
        eng = _engine(min_deploy_per_week=2.0)
        eng.record_frequency(
            "slow-svc", team="team-a", deploys_per_week=0.5, frequency_band=FrequencyBand.RARE
        )
        eng.record_frequency(
            "fast-svc", team="team-b", deploys_per_week=14.0, frequency_band=FrequencyBand.ELITE
        )
        eng.add_metric("deploy-rate", trend=FrequencyTrend.ACCELERATING)
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_metrics == 1
        assert "slow-svc" in report.low_frequency_services


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_records_and_metrics(self):
        eng = _engine()
        eng.record_frequency("svc-a")
        eng.add_metric("m-a")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["avg_deploys_per_week"] == 0.0
        assert stats["unique_services"] == 0

    def test_populated(self):
        eng = _engine(min_deploy_per_week=2.0)
        eng.record_frequency(
            "svc-a", team="team-a", deploys_per_week=5.0, frequency_band=FrequencyBand.HIGH
        )
        eng.record_frequency(
            "svc-b", team="team-b", deploys_per_week=3.0, frequency_band=FrequencyBand.MEDIUM
        )
        eng.add_metric("metric-a")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_metrics"] == 1
        assert stats["avg_deploys_per_week"] == 4.0
        assert stats["min_deploy_per_week"] == 2.0
        assert stats["unique_services"] == 2
        assert stats["unique_teams"] == 2
