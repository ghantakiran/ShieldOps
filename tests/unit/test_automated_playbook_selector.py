"""Tests for shieldops.security.automated_playbook_selector — AutomatedPlaybookSelector."""

from __future__ import annotations

from shieldops.security.automated_playbook_selector import (
    AutomatedPlaybookSelector,
    PlaybookCategory,
    PlaybookConfidence,
    PlaybookSelectionAnalysis,
    PlaybookSelectionRecord,
    PlaybookSelectionReport,
    SelectionCriteria,
)


def _engine(**kw) -> AutomatedPlaybookSelector:
    return AutomatedPlaybookSelector(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert PlaybookCategory.INCIDENT_RESPONSE == "incident_response"

    def test_e1_v2(self):
        assert PlaybookCategory.THREAT_HUNTING == "threat_hunting"

    def test_e1_v3(self):
        assert PlaybookCategory.REMEDIATION == "remediation"

    def test_e1_v4(self):
        assert PlaybookCategory.INVESTIGATION == "investigation"

    def test_e1_v5(self):
        assert PlaybookCategory.COMPLIANCE == "compliance"

    def test_e2_v1(self):
        assert SelectionCriteria.THREAT_TYPE == "threat_type"

    def test_e2_v2(self):
        assert SelectionCriteria.SEVERITY == "severity"

    def test_e2_v3(self):
        assert SelectionCriteria.ASSET_TYPE == "asset_type"

    def test_e2_v4(self):
        assert SelectionCriteria.TEAM == "team"

    def test_e2_v5(self):
        assert SelectionCriteria.HISTORICAL == "historical"

    def test_e3_v1(self):
        assert PlaybookConfidence.HIGH == "high"

    def test_e3_v2(self):
        assert PlaybookConfidence.MEDIUM == "medium"

    def test_e3_v3(self):
        assert PlaybookConfidence.LOW == "low"

    def test_e3_v4(self):
        assert PlaybookConfidence.MANUAL_OVERRIDE == "manual_override"

    def test_e3_v5(self):
        assert PlaybookConfidence.UNKNOWN == "unknown"


class TestModels:
    def test_rec(self):
        r = PlaybookSelectionRecord()
        assert r.id and r.selection_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = PlaybookSelectionAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = PlaybookSelectionReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_selection(
            selection_id="t",
            playbook_category=PlaybookCategory.THREAT_HUNTING,
            selection_criteria=SelectionCriteria.SEVERITY,
            playbook_confidence=PlaybookConfidence.MEDIUM,
            selection_score=92.0,
            service="s",
            team="t",
        )
        assert r.selection_id == "t" and r.selection_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_selection(selection_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_selection(selection_id="t")
        assert eng.get_selection(r.id) is not None

    def test_not_found(self):
        assert _engine().get_selection("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_selection(selection_id="a")
        eng.record_selection(selection_id="b")
        assert len(eng.list_selections()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_selection(selection_id="a", playbook_category=PlaybookCategory.INCIDENT_RESPONSE)
        eng.record_selection(selection_id="b", playbook_category=PlaybookCategory.THREAT_HUNTING)
        assert len(eng.list_selections(playbook_category=PlaybookCategory.INCIDENT_RESPONSE)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_selection(selection_id="a", selection_criteria=SelectionCriteria.THREAT_TYPE)
        eng.record_selection(selection_id="b", selection_criteria=SelectionCriteria.SEVERITY)
        assert len(eng.list_selections(selection_criteria=SelectionCriteria.THREAT_TYPE)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_selection(selection_id="a", team="x")
        eng.record_selection(selection_id="b", team="y")
        assert len(eng.list_selections(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_selection(selection_id=f"t-{i}")
        assert len(eng.list_selections(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            selection_id="t",
            playbook_category=PlaybookCategory.THREAT_HUNTING,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(selection_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_selection(
            selection_id="a",
            playbook_category=PlaybookCategory.INCIDENT_RESPONSE,
            selection_score=90.0,
        )
        eng.record_selection(
            selection_id="b",
            playbook_category=PlaybookCategory.INCIDENT_RESPONSE,
            selection_score=70.0,
        )
        assert "incident_response" in eng.analyze_category_distribution()

    def test_empty(self):
        assert _engine().analyze_category_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(selection_threshold=80.0)
        eng.record_selection(selection_id="a", selection_score=60.0)
        eng.record_selection(selection_id="b", selection_score=90.0)
        assert len(eng.identify_selection_gaps()) == 1

    def test_sorted(self):
        eng = _engine(selection_threshold=80.0)
        eng.record_selection(selection_id="a", selection_score=50.0)
        eng.record_selection(selection_id="b", selection_score=30.0)
        assert len(eng.identify_selection_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_selection(selection_id="a", service="s1", selection_score=80.0)
        eng.record_selection(selection_id="b", service="s2", selection_score=60.0)
        assert eng.rank_by_selection()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_selection() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(selection_id="t", analysis_score=float(v))
        assert eng.detect_selection_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(selection_id="t", analysis_score=float(v))
        assert eng.detect_selection_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_selection_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_selection(selection_id="t", selection_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_selection(selection_id="t")
        eng.add_analysis(selection_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_selection(selection_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_selection(selection_id="a")
        eng.record_selection(selection_id="b")
        eng.add_analysis(selection_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
