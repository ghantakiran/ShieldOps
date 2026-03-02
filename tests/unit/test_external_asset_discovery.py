"""Tests for shieldops.security.external_asset_discovery — ExternalAssetDiscovery."""

from __future__ import annotations

from shieldops.security.external_asset_discovery import (
    AssetDiscoveryAnalysis,
    AssetDiscoveryRecord,
    AssetDiscoveryReport,
    AssetType,
    DiscoveryMethod,
    DiscoveryStatus,
    ExternalAssetDiscovery,
)


def _engine(**kw) -> ExternalAssetDiscovery:
    return ExternalAssetDiscovery(**kw)


class TestEnums:
    def test_assettype_val1(self):
        assert AssetType.DOMAIN == "domain"

    def test_assettype_val2(self):
        assert AssetType.SUBDOMAIN == "subdomain"

    def test_assettype_val3(self):
        assert AssetType.IP_ADDRESS == "ip_address"

    def test_assettype_val4(self):
        assert AssetType.API_ENDPOINT == "api_endpoint"

    def test_assettype_val5(self):
        assert AssetType.CLOUD_RESOURCE == "cloud_resource"

    def test_discoverymethod_val1(self):
        assert DiscoveryMethod.DNS_ENUMERATION == "dns_enumeration"

    def test_discoverymethod_val2(self):
        assert DiscoveryMethod.CERT_TRANSPARENCY == "cert_transparency"

    def test_discoverymethod_val3(self):
        assert DiscoveryMethod.PORT_SCAN == "port_scan"

    def test_discoverymethod_val4(self):
        assert DiscoveryMethod.CLOUD_API == "cloud_api"

    def test_discoverymethod_val5(self):
        assert DiscoveryMethod.PASSIVE_RECON == "passive_recon"

    def test_discoverystatus_val1(self):
        assert DiscoveryStatus.DISCOVERED == "discovered"

    def test_discoverystatus_val2(self):
        assert DiscoveryStatus.VERIFIED == "verified"

    def test_discoverystatus_val3(self):
        assert DiscoveryStatus.CLASSIFIED == "classified"

    def test_discoverystatus_val4(self):
        assert DiscoveryStatus.MONITORED == "monitored"

    def test_discoverystatus_val5(self):
        assert DiscoveryStatus.RETIRED == "retired"


class TestModels:
    def test_record_defaults(self):
        r = AssetDiscoveryRecord()
        assert r.id
        assert r.asset_name == ""

    def test_analysis_defaults(self):
        a = AssetDiscoveryAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = AssetDiscoveryReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_asset(
            asset_name="test",
            asset_type=AssetType.SUBDOMAIN,
            risk_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.asset_name == "test"
        assert r.risk_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_asset(asset_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_asset(asset_name="test")
        assert eng.get_asset(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_asset("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_asset(asset_name="a")
        eng.record_asset(asset_name="b")
        assert len(eng.list_assets()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_asset(asset_name="a", asset_type=AssetType.DOMAIN)
        eng.record_asset(asset_name="b", asset_type=AssetType.SUBDOMAIN)
        assert len(eng.list_assets(asset_type=AssetType.DOMAIN)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_asset(asset_name="a", discovery_method=DiscoveryMethod.DNS_ENUMERATION)
        eng.record_asset(asset_name="b", discovery_method=DiscoveryMethod.CERT_TRANSPARENCY)
        assert len(eng.list_assets(discovery_method=DiscoveryMethod.DNS_ENUMERATION)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_asset(asset_name="a", team="sec")
        eng.record_asset(asset_name="b", team="ops")
        assert len(eng.list_assets(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_asset(asset_name=f"t-{i}")
        assert len(eng.list_assets(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            asset_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(asset_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_asset(asset_name="a", asset_type=AssetType.DOMAIN, risk_score=90.0)
        eng.record_asset(asset_name="b", asset_type=AssetType.DOMAIN, risk_score=70.0)
        result = eng.analyze_distribution()
        assert AssetType.DOMAIN.value in result
        assert result[AssetType.DOMAIN.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_asset(asset_name="a", risk_score=60.0)
        eng.record_asset(asset_name="b", risk_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_asset(asset_name="a", risk_score=50.0)
        eng.record_asset(asset_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_asset(asset_name="a", service="auth", risk_score=90.0)
        eng.record_asset(asset_name="b", service="api", risk_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(asset_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(asset_name="a", analysis_score=20.0)
        eng.add_analysis(asset_name="b", analysis_score=20.0)
        eng.add_analysis(asset_name="c", analysis_score=80.0)
        eng.add_analysis(asset_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_asset(asset_name="test", risk_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_asset(asset_name="test")
        eng.add_analysis(asset_name="test")
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
        eng.record_asset(asset_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
