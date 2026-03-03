"""Tests for ComplianceEvidenceAutomatorV3."""

from __future__ import annotations

from shieldops.compliance.compliance_evidence_automator_v3 import (
    CollectionMethod,
    ComplianceEvidenceAutomatorV3,
    EvidenceAnalysis,
    EvidenceRecord,
    EvidenceReport,
    EvidenceStatus,
    EvidenceType,
)


def _engine(**kw) -> ComplianceEvidenceAutomatorV3:
    return ComplianceEvidenceAutomatorV3(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert EvidenceType.SCREENSHOT == "screenshot"

    def test_e1_v2(self):
        assert EvidenceType.LOG_EXPORT == "log_export"

    def test_e1_v3(self):
        assert EvidenceType.CONFIG_SNAPSHOT == "config_snapshot"

    def test_e1_v4(self):
        assert EvidenceType.SCAN_RESULT == "scan_result"

    def test_e1_v5(self):
        assert EvidenceType.ATTESTATION == "attestation"

    def test_e2_v1(self):
        assert CollectionMethod.AUTOMATED == "automated"

    def test_e2_v2(self):
        assert CollectionMethod.SEMI_AUTOMATED == "semi_automated"

    def test_e2_v3(self):
        assert CollectionMethod.MANUAL == "manual"

    def test_e2_v4(self):
        assert CollectionMethod.API_PULL == "api_pull"

    def test_e2_v5(self):
        assert CollectionMethod.SCHEDULED == "scheduled"

    def test_e3_v1(self):
        assert EvidenceStatus.COLLECTED == "collected"

    def test_e3_v2(self):
        assert EvidenceStatus.VALIDATED == "validated"

    def test_e3_v3(self):
        assert EvidenceStatus.EXPIRED == "expired"

    def test_e3_v4(self):
        assert EvidenceStatus.REJECTED == "rejected"

    def test_e3_v5(self):
        assert EvidenceStatus.PENDING == "pending"


class TestModels:
    def test_rec(self):
        r = EvidenceRecord()
        assert r.id and r.evidence_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = EvidenceAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = EvidenceReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_evidence(
            evidence_id="t",
            evidence_type=EvidenceType.LOG_EXPORT,
            collection_method=CollectionMethod.SEMI_AUTOMATED,
            evidence_status=EvidenceStatus.VALIDATED,
            evidence_score=92.0,
            service="s",
            team="t",
        )
        assert r.evidence_id == "t" and r.evidence_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_evidence(evidence_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_evidence(evidence_id="t")
        assert eng.get_evidence(r.id) is not None

    def test_not_found(self):
        assert _engine().get_evidence("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_evidence(evidence_id="a")
        eng.record_evidence(evidence_id="b")
        assert len(eng.list_evidences()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_evidence(evidence_id="a", evidence_type=EvidenceType.SCREENSHOT)
        eng.record_evidence(evidence_id="b", evidence_type=EvidenceType.LOG_EXPORT)
        assert len(eng.list_evidences(evidence_type=EvidenceType.SCREENSHOT)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_evidence(evidence_id="a", collection_method=CollectionMethod.AUTOMATED)
        eng.record_evidence(evidence_id="b", collection_method=CollectionMethod.SEMI_AUTOMATED)
        assert len(eng.list_evidences(collection_method=CollectionMethod.AUTOMATED)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_evidence(evidence_id="a", team="x")
        eng.record_evidence(evidence_id="b", team="y")
        assert len(eng.list_evidences(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_evidence(evidence_id=f"t-{i}")
        assert len(eng.list_evidences(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            evidence_id="t",
            evidence_type=EvidenceType.LOG_EXPORT,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(evidence_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_evidence(
            evidence_id="a", evidence_type=EvidenceType.SCREENSHOT, evidence_score=90.0
        )
        eng.record_evidence(
            evidence_id="b", evidence_type=EvidenceType.SCREENSHOT, evidence_score=70.0
        )
        assert "screenshot" in eng.analyze_type_distribution()

    def test_empty(self):
        assert _engine().analyze_type_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(evidence_threshold=80.0)
        eng.record_evidence(evidence_id="a", evidence_score=60.0)
        eng.record_evidence(evidence_id="b", evidence_score=90.0)
        assert len(eng.identify_evidence_gaps()) == 1

    def test_sorted(self):
        eng = _engine(evidence_threshold=80.0)
        eng.record_evidence(evidence_id="a", evidence_score=50.0)
        eng.record_evidence(evidence_id="b", evidence_score=30.0)
        assert len(eng.identify_evidence_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_evidence(evidence_id="a", service="s1", evidence_score=80.0)
        eng.record_evidence(evidence_id="b", service="s2", evidence_score=60.0)
        assert eng.rank_by_evidence()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_evidence() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(evidence_id="t", analysis_score=float(v))
        assert eng.detect_evidence_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(evidence_id="t", analysis_score=float(v))
        assert eng.detect_evidence_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_evidence_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_evidence(evidence_id="t", evidence_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_evidence(evidence_id="t")
        eng.add_analysis(evidence_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_evidence(evidence_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_evidence(evidence_id="a")
        eng.record_evidence(evidence_id="b")
        eng.add_analysis(evidence_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
