"""Tests for shieldops.security.threat_enrichment_orchestrator — ThreatEnrichmentOrchestrator."""

from __future__ import annotations

from shieldops.security.threat_enrichment_orchestrator import (
    EnrichmentAnalysis,
    EnrichmentQuality,
    EnrichmentRecord,
    EnrichmentReport,
    EnrichmentSource,
    EnrichmentType,
    ThreatEnrichmentOrchestrator,
)


def _engine(**kw) -> ThreatEnrichmentOrchestrator:
    return ThreatEnrichmentOrchestrator(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert EnrichmentSource.THREAT_INTEL == "threat_intel"

    def test_e1_v2(self):
        assert EnrichmentSource.OSINT == "osint"

    def test_e1_v3(self):
        assert EnrichmentSource.INTERNAL == "internal"

    def test_e1_v4(self):
        assert EnrichmentSource.VENDOR == "vendor"

    def test_e1_v5(self):
        assert EnrichmentSource.COMMUNITY == "community"

    def test_e2_v1(self):
        assert EnrichmentType.IP_REPUTATION == "ip_reputation"

    def test_e2_v2(self):
        assert EnrichmentType.DOMAIN_ANALYSIS == "domain_analysis"

    def test_e2_v3(self):
        assert EnrichmentType.FILE_HASH == "file_hash"

    def test_e2_v4(self):
        assert EnrichmentType.URL_SCAN == "url_scan"

    def test_e2_v5(self):
        assert EnrichmentType.BEHAVIOR_PROFILE == "behavior_profile"

    def test_e3_v1(self):
        assert EnrichmentQuality.VERIFIED == "verified"

    def test_e3_v2(self):
        assert EnrichmentQuality.HIGH == "high"

    def test_e3_v3(self):
        assert EnrichmentQuality.MEDIUM == "medium"

    def test_e3_v4(self):
        assert EnrichmentQuality.LOW == "low"

    def test_e3_v5(self):
        assert EnrichmentQuality.UNVERIFIED == "unverified"


class TestModels:
    def test_rec(self):
        r = EnrichmentRecord()
        assert r.id and r.enrichment_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = EnrichmentAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = EnrichmentReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_enrichment(
            enrichment_id="t",
            enrichment_source=EnrichmentSource.OSINT,
            enrichment_type=EnrichmentType.DOMAIN_ANALYSIS,
            enrichment_quality=EnrichmentQuality.HIGH,
            enrichment_score=92.0,
            service="s",
            team="t",
        )
        assert r.enrichment_id == "t" and r.enrichment_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_enrichment(enrichment_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_enrichment(enrichment_id="t")
        assert eng.get_enrichment(r.id) is not None

    def test_not_found(self):
        assert _engine().get_enrichment("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_enrichment(enrichment_id="a")
        eng.record_enrichment(enrichment_id="b")
        assert len(eng.list_enrichments()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_enrichment(enrichment_id="a", enrichment_source=EnrichmentSource.THREAT_INTEL)
        eng.record_enrichment(enrichment_id="b", enrichment_source=EnrichmentSource.OSINT)
        assert len(eng.list_enrichments(enrichment_source=EnrichmentSource.THREAT_INTEL)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_enrichment(enrichment_id="a", enrichment_type=EnrichmentType.IP_REPUTATION)
        eng.record_enrichment(enrichment_id="b", enrichment_type=EnrichmentType.DOMAIN_ANALYSIS)
        assert len(eng.list_enrichments(enrichment_type=EnrichmentType.IP_REPUTATION)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_enrichment(enrichment_id="a", team="x")
        eng.record_enrichment(enrichment_id="b", team="y")
        assert len(eng.list_enrichments(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_enrichment(enrichment_id=f"t-{i}")
        assert len(eng.list_enrichments(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            enrichment_id="t",
            enrichment_source=EnrichmentSource.OSINT,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(enrichment_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_enrichment(
            enrichment_id="a",
            enrichment_source=EnrichmentSource.THREAT_INTEL,
            enrichment_score=90.0,
        )
        eng.record_enrichment(
            enrichment_id="b",
            enrichment_source=EnrichmentSource.THREAT_INTEL,
            enrichment_score=70.0,
        )
        assert "threat_intel" in eng.analyze_source_distribution()

    def test_empty(self):
        assert _engine().analyze_source_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(enrichment_threshold=80.0)
        eng.record_enrichment(enrichment_id="a", enrichment_score=60.0)
        eng.record_enrichment(enrichment_id="b", enrichment_score=90.0)
        assert len(eng.identify_enrichment_gaps()) == 1

    def test_sorted(self):
        eng = _engine(enrichment_threshold=80.0)
        eng.record_enrichment(enrichment_id="a", enrichment_score=50.0)
        eng.record_enrichment(enrichment_id="b", enrichment_score=30.0)
        assert len(eng.identify_enrichment_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_enrichment(enrichment_id="a", service="s1", enrichment_score=80.0)
        eng.record_enrichment(enrichment_id="b", service="s2", enrichment_score=60.0)
        assert eng.rank_by_enrichment()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_enrichment() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(enrichment_id="t", analysis_score=float(v))
        assert eng.detect_enrichment_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(enrichment_id="t", analysis_score=float(v))
        assert eng.detect_enrichment_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_enrichment_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_enrichment(enrichment_id="t", enrichment_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_enrichment(enrichment_id="t")
        eng.add_analysis(enrichment_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_enrichment(enrichment_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_enrichment(enrichment_id="a")
        eng.record_enrichment(enrichment_id="b")
        eng.add_analysis(enrichment_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
