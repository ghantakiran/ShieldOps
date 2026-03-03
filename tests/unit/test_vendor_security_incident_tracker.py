"""Tests for shieldops.security.vendor_security_incident_tracker — VendorSecurityIncidentTracker."""

from __future__ import annotations

from shieldops.security.vendor_security_incident_tracker import (
    IncidentImpact,
    ResponseStatus,
    VendorIncidentAnalysis,
    VendorIncidentRecord,
    VendorSecurityIncidentReport,
    VendorSecurityIncidentTracker,
    VendorTier,
)


def _engine(**kw) -> VendorSecurityIncidentTracker:
    return VendorSecurityIncidentTracker(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert VendorTier.CRITICAL == "critical"

    def test_e1_v2(self):
        assert VendorTier.HIGH == "high"

    def test_e1_v3(self):
        assert VendorTier.MEDIUM == "medium"

    def test_e1_v4(self):
        assert VendorTier.LOW == "low"

    def test_e1_v5(self):
        assert VendorTier.UNCLASSIFIED == "unclassified"

    def test_e2_v1(self):
        assert IncidentImpact.DATA_BREACH == "data_breach"

    def test_e2_v2(self):
        assert IncidentImpact.SERVICE_DISRUPTION == "service_disruption"

    def test_e2_v3(self):
        assert IncidentImpact.COMPLIANCE_VIOLATION == "compliance_violation"

    def test_e2_v4(self):
        assert IncidentImpact.REPUTATION == "reputation"

    def test_e2_v5(self):
        assert IncidentImpact.FINANCIAL == "financial"

    def test_e3_v1(self):
        assert ResponseStatus.ACKNOWLEDGED == "acknowledged"

    def test_e3_v2(self):
        assert ResponseStatus.INVESTIGATING == "investigating"

    def test_e3_v3(self):
        assert ResponseStatus.MITIGATED == "mitigated"

    def test_e3_v4(self):
        assert ResponseStatus.RESOLVED == "resolved"

    def test_e3_v5(self):
        assert ResponseStatus.ESCALATED == "escalated"


class TestModels:
    def test_rec(self):
        r = VendorIncidentRecord()
        assert r.id and r.incident_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = VendorIncidentAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = VendorSecurityIncidentReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_incident(
            incident_id="t",
            vendor_tier=VendorTier.HIGH,
            incident_impact=IncidentImpact.SERVICE_DISRUPTION,
            response_status=ResponseStatus.INVESTIGATING,
            incident_score=92.0,
            service="s",
            team="t",
        )
        assert r.incident_id == "t" and r.incident_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_incident(incident_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_incident(incident_id="t")
        assert eng.get_incident(r.id) is not None

    def test_not_found(self):
        assert _engine().get_incident("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_incident(incident_id="a")
        eng.record_incident(incident_id="b")
        assert len(eng.list_incidents()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_incident(incident_id="a", vendor_tier=VendorTier.CRITICAL)
        eng.record_incident(incident_id="b", vendor_tier=VendorTier.HIGH)
        assert len(eng.list_incidents(vendor_tier=VendorTier.CRITICAL)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_incident(incident_id="a", incident_impact=IncidentImpact.DATA_BREACH)
        eng.record_incident(incident_id="b", incident_impact=IncidentImpact.SERVICE_DISRUPTION)
        assert len(eng.list_incidents(incident_impact=IncidentImpact.DATA_BREACH)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_incident(incident_id="a", team="x")
        eng.record_incident(incident_id="b", team="y")
        assert len(eng.list_incidents(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_incident(incident_id=f"t-{i}")
        assert len(eng.list_incidents(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            incident_id="t", vendor_tier=VendorTier.HIGH, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(incident_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_incident(incident_id="a", vendor_tier=VendorTier.CRITICAL, incident_score=90.0)
        eng.record_incident(incident_id="b", vendor_tier=VendorTier.CRITICAL, incident_score=70.0)
        assert "critical" in eng.analyze_incident_distribution()

    def test_empty(self):
        assert _engine().analyze_incident_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(incident_gap_threshold=80.0)
        eng.record_incident(incident_id="a", incident_score=60.0)
        eng.record_incident(incident_id="b", incident_score=90.0)
        assert len(eng.identify_incident_gaps()) == 1

    def test_sorted(self):
        eng = _engine(incident_gap_threshold=80.0)
        eng.record_incident(incident_id="a", incident_score=50.0)
        eng.record_incident(incident_id="b", incident_score=30.0)
        assert len(eng.identify_incident_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_incident(incident_id="a", service="s1", incident_score=80.0)
        eng.record_incident(incident_id="b", service="s2", incident_score=60.0)
        assert eng.rank_by_incident()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_incident() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(incident_id="t", analysis_score=float(v))
        assert eng.detect_incident_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(incident_id="t", analysis_score=float(v))
        assert eng.detect_incident_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_incident_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_incident(incident_id="t", incident_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_incident(incident_id="t")
        eng.add_analysis(incident_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_incident(incident_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_incident(incident_id="a")
        eng.record_incident(incident_id="b")
        eng.add_analysis(incident_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
