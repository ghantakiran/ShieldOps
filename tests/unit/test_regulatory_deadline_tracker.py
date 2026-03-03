"""Tests for shieldops.compliance.regulatory_deadline_tracker — RegulatoryDeadlineTracker."""

from __future__ import annotations

from shieldops.compliance.regulatory_deadline_tracker import (
    DeadlineAnalysis,
    DeadlineRecord,
    DeadlineReport,
    DeadlineStatus,
    DeadlineType,
    Regulation,
    RegulatoryDeadlineTracker,
)


def _engine(**kw) -> RegulatoryDeadlineTracker:
    return RegulatoryDeadlineTracker(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert Regulation.GDPR == "gdpr"

    def test_e1_v2(self):
        assert Regulation.SOX == "sox"

    def test_e1_v3(self):
        assert Regulation.PCI_DSS == "pci_dss"

    def test_e1_v4(self):
        assert Regulation.HIPAA == "hipaa"

    def test_e1_v5(self):
        assert Regulation.SOC2 == "soc2"

    def test_e2_v1(self):
        assert DeadlineType.FILING == "filing"

    def test_e2_v2(self):
        assert DeadlineType.AUDIT == "audit"

    def test_e2_v3(self):
        assert DeadlineType.REMEDIATION == "remediation"

    def test_e2_v4(self):
        assert DeadlineType.CERTIFICATION == "certification"

    def test_e2_v5(self):
        assert DeadlineType.RENEWAL == "renewal"

    def test_e3_v1(self):
        assert DeadlineStatus.ON_TRACK == "on_track"

    def test_e3_v2(self):
        assert DeadlineStatus.AT_RISK == "at_risk"

    def test_e3_v3(self):
        assert DeadlineStatus.OVERDUE == "overdue"

    def test_e3_v4(self):
        assert DeadlineStatus.COMPLETED == "completed"

    def test_e3_v5(self):
        assert DeadlineStatus.WAIVED == "waived"


class TestModels:
    def test_rec(self):
        r = DeadlineRecord()
        assert r.id and r.compliance_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = DeadlineAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = DeadlineReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_deadline(
            deadline_id="t",
            regulation=Regulation.SOX,
            deadline_type=DeadlineType.AUDIT,
            deadline_status=DeadlineStatus.AT_RISK,
            compliance_score=92.0,
            service="s",
            team="t",
        )
        assert r.deadline_id == "t" and r.compliance_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_deadline(deadline_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_deadline(deadline_id="t")
        assert eng.get_deadline(r.id) is not None

    def test_not_found(self):
        assert _engine().get_deadline("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_deadline(deadline_id="a")
        eng.record_deadline(deadline_id="b")
        assert len(eng.list_deadlines()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_deadline(deadline_id="a", regulation=Regulation.GDPR)
        eng.record_deadline(deadline_id="b", regulation=Regulation.SOX)
        assert len(eng.list_deadlines(regulation=Regulation.GDPR)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_deadline(deadline_id="a", deadline_type=DeadlineType.FILING)
        eng.record_deadline(deadline_id="b", deadline_type=DeadlineType.AUDIT)
        assert len(eng.list_deadlines(deadline_type=DeadlineType.FILING)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_deadline(deadline_id="a", team="x")
        eng.record_deadline(deadline_id="b", team="y")
        assert len(eng.list_deadlines(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_deadline(deadline_id=f"t-{i}")
        assert len(eng.list_deadlines(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            deadline_id="t", regulation=Regulation.SOX, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(deadline_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_deadline(deadline_id="a", regulation=Regulation.GDPR, compliance_score=90.0)
        eng.record_deadline(deadline_id="b", regulation=Regulation.GDPR, compliance_score=70.0)
        assert "gdpr" in eng.analyze_regulation_distribution()

    def test_empty(self):
        assert _engine().analyze_regulation_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(compliance_threshold=80.0)
        eng.record_deadline(deadline_id="a", compliance_score=60.0)
        eng.record_deadline(deadline_id="b", compliance_score=90.0)
        assert len(eng.identify_deadline_gaps()) == 1

    def test_sorted(self):
        eng = _engine(compliance_threshold=80.0)
        eng.record_deadline(deadline_id="a", compliance_score=50.0)
        eng.record_deadline(deadline_id="b", compliance_score=30.0)
        assert len(eng.identify_deadline_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_deadline(deadline_id="a", service="s1", compliance_score=80.0)
        eng.record_deadline(deadline_id="b", service="s2", compliance_score=60.0)
        assert eng.rank_by_compliance()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_compliance() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(deadline_id="t", analysis_score=float(v))
        assert eng.detect_deadline_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(deadline_id="t", analysis_score=float(v))
        assert eng.detect_deadline_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_deadline_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_deadline(deadline_id="t", compliance_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_deadline(deadline_id="t")
        eng.add_analysis(deadline_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_deadline(deadline_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_deadline(deadline_id="a")
        eng.record_deadline(deadline_id="b")
        eng.add_analysis(deadline_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
