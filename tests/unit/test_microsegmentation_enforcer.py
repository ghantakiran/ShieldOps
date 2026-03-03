"""Tests for shieldops.security.microsegmentation_enforcer — MicrosegmentationEnforcer."""

from __future__ import annotations

from shieldops.security.microsegmentation_enforcer import (
    EnforcementAction,
    MicrosegmentationEnforcer,
    SegmentAnalysis,
    SegmentEnforcementReport,
    SegmentRule,
    SegmentStatus,
    SegmentType,
)


def _engine(**kw) -> MicrosegmentationEnforcer:
    return MicrosegmentationEnforcer(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert SegmentType.NETWORK == "network"

    def test_e1_v2(self):
        assert SegmentType.APPLICATION == "application"

    def test_e1_v3(self):
        assert SegmentType.DATA == "data"

    def test_e1_v4(self):
        assert SegmentType.IDENTITY == "identity"

    def test_e1_v5(self):
        assert SegmentType.WORKLOAD == "workload"

    def test_e2_v1(self):
        assert EnforcementAction.ALLOW == "allow"

    def test_e2_v2(self):
        assert EnforcementAction.DENY == "deny"

    def test_e2_v3(self):
        assert EnforcementAction.RESTRICT == "restrict"

    def test_e2_v4(self):
        assert EnforcementAction.MONITOR == "monitor"

    def test_e2_v5(self):
        assert EnforcementAction.QUARANTINE == "quarantine"

    def test_e3_v1(self):
        assert SegmentStatus.ACTIVE == "active"

    def test_e3_v2(self):
        assert SegmentStatus.PENDING == "pending"

    def test_e3_v3(self):
        assert SegmentStatus.VIOLATED == "violated"

    def test_e3_v4(self):
        assert SegmentStatus.EXEMPT == "exempt"

    def test_e3_v5(self):
        assert SegmentStatus.DISABLED == "disabled"


class TestModels:
    def test_rec(self):
        r = SegmentRule()
        assert r.id and r.enforcement_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = SegmentAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = SegmentEnforcementReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_rule(
            segment_id="t",
            segment_type=SegmentType.APPLICATION,
            enforcement_action=EnforcementAction.DENY,
            segment_status=SegmentStatus.PENDING,
            enforcement_score=92.0,
            service="s",
            team="t",
        )
        assert r.segment_id == "t" and r.enforcement_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_rule(segment_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_rule(segment_id="t")
        assert eng.get_rule(r.id) is not None

    def test_not_found(self):
        assert _engine().get_rule("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_rule(segment_id="a")
        eng.record_rule(segment_id="b")
        assert len(eng.list_rules()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_rule(segment_id="a", segment_type=SegmentType.NETWORK)
        eng.record_rule(segment_id="b", segment_type=SegmentType.APPLICATION)
        assert len(eng.list_rules(segment_type=SegmentType.NETWORK)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_rule(segment_id="a", enforcement_action=EnforcementAction.ALLOW)
        eng.record_rule(segment_id="b", enforcement_action=EnforcementAction.DENY)
        assert len(eng.list_rules(enforcement_action=EnforcementAction.ALLOW)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_rule(segment_id="a", team="x")
        eng.record_rule(segment_id="b", team="y")
        assert len(eng.list_rules(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_rule(segment_id=f"t-{i}")
        assert len(eng.list_rules(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            segment_id="t", segment_type=SegmentType.APPLICATION, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(segment_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_rule(segment_id="a", segment_type=SegmentType.NETWORK, enforcement_score=90.0)
        eng.record_rule(segment_id="b", segment_type=SegmentType.NETWORK, enforcement_score=70.0)
        assert "network" in eng.analyze_segment_distribution()

    def test_empty(self):
        assert _engine().analyze_segment_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(enforcement_gap_threshold=80.0)
        eng.record_rule(segment_id="a", enforcement_score=60.0)
        eng.record_rule(segment_id="b", enforcement_score=90.0)
        assert len(eng.identify_enforcement_gaps()) == 1

    def test_sorted(self):
        eng = _engine(enforcement_gap_threshold=80.0)
        eng.record_rule(segment_id="a", enforcement_score=50.0)
        eng.record_rule(segment_id="b", enforcement_score=30.0)
        assert len(eng.identify_enforcement_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_rule(segment_id="a", service="s1", enforcement_score=80.0)
        eng.record_rule(segment_id="b", service="s2", enforcement_score=60.0)
        assert eng.rank_by_enforcement()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_enforcement() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(segment_id="t", analysis_score=float(v))
        assert eng.detect_enforcement_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(segment_id="t", analysis_score=float(v))
        assert eng.detect_enforcement_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_enforcement_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_rule(segment_id="t", enforcement_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_rule(segment_id="t")
        eng.add_analysis(segment_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_rule(segment_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_rule(segment_id="a")
        eng.record_rule(segment_id="b")
        eng.add_analysis(segment_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
