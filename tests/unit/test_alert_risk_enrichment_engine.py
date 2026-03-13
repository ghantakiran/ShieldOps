"""Tests for AlertRiskEnrichmentEngine."""

from __future__ import annotations

from shieldops.security.alert_risk_enrichment_engine import (
    AlertFidelity,
    AlertRiskEnrichmentEngine,
    EnrichmentQuality,
    EnrichmentSource,
)


def _engine(**kw) -> AlertRiskEnrichmentEngine:
    return AlertRiskEnrichmentEngine(**kw)


class TestEnums:
    def test_enrichment_source_values(self):
        for v in EnrichmentSource:
            assert isinstance(v.value, str)

    def test_enrichment_quality_values(self):
        for v in EnrichmentQuality:
            assert isinstance(v.value, str)

    def test_alert_fidelity_values(self):
        for v in AlertFidelity:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(alert_id="a1")
        assert r.alert_id == "a1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(alert_id=f"a-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(alert_id="a1")
        a = eng.process(r.id)
        assert hasattr(a, "alert_id")
        assert a.alert_id == "a1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_id="a1")
        assert eng.generate_report().total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(alert_id="a1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(alert_id="a1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestEnrichAlertWithRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_id="a1",
            enrichment_score=75.0,
        )
        result = eng.enrich_alert_with_risk()
        assert len(result) == 1
        assert result[0]["alert_id"] == "a1"

    def test_empty(self):
        assert _engine().enrich_alert_with_risk() == []


class TestComputeEnrichmentCompleteness:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_id="a1",
            source=EnrichmentSource.ASSET_CONTEXT,
        )
        result = eng.compute_enrichment_completeness()
        assert result["overall_completeness"] > 0

    def test_empty(self):
        result = _engine().compute_enrichment_completeness()
        assert result["overall_completeness"] == 0.0


class TestDetectStaleEnrichment:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            alert_id="a1",
            quality=EnrichmentQuality.STALE,
            staleness_hours=48.0,
        )
        result = eng.detect_stale_enrichment()
        assert len(result) == 1
        assert result[0]["staleness_hours"] == 48.0

    def test_empty(self):
        assert _engine().detect_stale_enrichment() == []
