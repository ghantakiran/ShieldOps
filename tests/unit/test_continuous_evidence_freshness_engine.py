"""Tests for ContinuousEvidenceFreshnessEngine."""

from __future__ import annotations

from shieldops.compliance.continuous_evidence_freshness_engine import (
    ContinuousEvidenceFreshnessEngine,
    ControlCategory,
    EvidenceType,
    FreshnessStatus,
)


def _engine(**kw) -> ContinuousEvidenceFreshnessEngine:
    return ContinuousEvidenceFreshnessEngine(**kw)


class TestEnums:
    def test_freshness_status_values(self):
        for v in FreshnessStatus:
            assert isinstance(v.value, str)

    def test_evidence_type_values(self):
        for v in EvidenceType:
            assert isinstance(v.value, str)

    def test_control_category_values(self):
        for v in ControlCategory:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(evidence_id="ev1")
        assert r.evidence_id == "ev1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(evidence_id=f"ev-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(evidence_id="ev1", freshness_score=80.0)
        a = eng.process(r.id)
        assert hasattr(a, "evidence_id")
        assert a.evidence_id == "ev1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(evidence_id="ev1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(evidence_id="ev1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(evidence_id="ev1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeEvidenceFreshnessScores:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(evidence_id="ev1", freshness_score=50.0)
        result = eng.compute_evidence_freshness_scores()
        assert len(result) == 1
        assert result[0]["evidence_id"] == "ev1"

    def test_empty(self):
        assert _engine().compute_evidence_freshness_scores() == []


class TestDetectStaleEvidence:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            evidence_id="ev1",
            freshness_status=FreshnessStatus.STALE,
            age_days=90.0,
        )
        result = eng.detect_stale_evidence()
        assert len(result) == 1
        assert result[0]["evidence_id"] == "ev1"

    def test_empty(self):
        assert _engine().detect_stale_evidence() == []


class TestRankControlsByEvidenceUrgency:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(control_id="c1", age_days=30.0)
        eng.add_record(control_id="c2", age_days=60.0)
        result = eng.rank_controls_by_evidence_urgency()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_controls_by_evidence_urgency() == []
