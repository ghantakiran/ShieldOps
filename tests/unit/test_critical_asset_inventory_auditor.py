"""Tests for shieldops.security.critical_asset_inventory_auditor — CriticalAssetInventoryAuditor."""

from __future__ import annotations

from shieldops.security.critical_asset_inventory_auditor import (
    AssetAuditAnalysis,
    AssetAuditRecord,
    AssetAuditReport,
    AssetCategory,
    AssetCriticality,
    AuditStatus,
    CriticalAssetInventoryAuditor,
)


def _engine(**kw) -> CriticalAssetInventoryAuditor:
    return CriticalAssetInventoryAuditor(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert AssetCriticality.TIER1_CRITICAL == "tier1_critical"

    def test_e1_v2(self):
        assert AssetCriticality.TIER2_HIGH == "tier2_high"

    def test_e1_v3(self):
        assert AssetCriticality.TIER3_MEDIUM == "tier3_medium"

    def test_e1_v4(self):
        assert AssetCriticality.TIER4_LOW == "tier4_low"

    def test_e1_v5(self):
        assert AssetCriticality.UNCLASSIFIED == "unclassified"

    def test_e2_v1(self):
        assert AssetCategory.DATA_STORE == "data_store"

    def test_e2_v2(self):
        assert AssetCategory.APPLICATION == "application"

    def test_e2_v3(self):
        assert AssetCategory.INFRASTRUCTURE == "infrastructure"

    def test_e2_v4(self):
        assert AssetCategory.NETWORK == "network"

    def test_e2_v5(self):
        assert AssetCategory.IDENTITY == "identity"

    def test_e3_v1(self):
        assert AuditStatus.CURRENT == "current"

    def test_e3_v2(self):
        assert AuditStatus.STALE == "stale"

    def test_e3_v3(self):
        assert AuditStatus.MISSING == "missing"

    def test_e3_v4(self):
        assert AuditStatus.DISPUTED == "disputed"

    def test_e3_v5(self):
        assert AuditStatus.PENDING == "pending"


class TestModels:
    def test_rec(self):
        r = AssetAuditRecord()
        assert r.id and r.audit_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = AssetAuditAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = AssetAuditReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_audit(
            audit_id="t",
            asset_criticality=AssetCriticality.TIER2_HIGH,
            asset_category=AssetCategory.APPLICATION,
            audit_status=AuditStatus.STALE,
            audit_score=92.0,
            service="s",
            team="t",
        )
        assert r.audit_id == "t" and r.audit_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_audit(audit_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_audit(audit_id="t")
        assert eng.get_audit(r.id) is not None

    def test_not_found(self):
        assert _engine().get_audit("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_audit(audit_id="a")
        eng.record_audit(audit_id="b")
        assert len(eng.list_audits()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_audit(audit_id="a", asset_criticality=AssetCriticality.TIER1_CRITICAL)
        eng.record_audit(audit_id="b", asset_criticality=AssetCriticality.TIER2_HIGH)
        assert len(eng.list_audits(asset_criticality=AssetCriticality.TIER1_CRITICAL)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_audit(audit_id="a", asset_category=AssetCategory.DATA_STORE)
        eng.record_audit(audit_id="b", asset_category=AssetCategory.APPLICATION)
        assert len(eng.list_audits(asset_category=AssetCategory.DATA_STORE)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_audit(audit_id="a", team="x")
        eng.record_audit(audit_id="b", team="y")
        assert len(eng.list_audits(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_audit(audit_id=f"t-{i}")
        assert len(eng.list_audits(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            audit_id="t",
            asset_criticality=AssetCriticality.TIER2_HIGH,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(audit_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_audit(
            audit_id="a", asset_criticality=AssetCriticality.TIER1_CRITICAL, audit_score=90.0
        )
        eng.record_audit(
            audit_id="b", asset_criticality=AssetCriticality.TIER1_CRITICAL, audit_score=70.0
        )
        assert "tier1_critical" in eng.analyze_criticality_distribution()

    def test_empty(self):
        assert _engine().analyze_criticality_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(audit_threshold=80.0)
        eng.record_audit(audit_id="a", audit_score=60.0)
        eng.record_audit(audit_id="b", audit_score=90.0)
        assert len(eng.identify_audit_gaps()) == 1

    def test_sorted(self):
        eng = _engine(audit_threshold=80.0)
        eng.record_audit(audit_id="a", audit_score=50.0)
        eng.record_audit(audit_id="b", audit_score=30.0)
        assert len(eng.identify_audit_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_audit(audit_id="a", service="s1", audit_score=80.0)
        eng.record_audit(audit_id="b", service="s2", audit_score=60.0)
        assert eng.rank_by_audit()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_audit() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(audit_id="t", analysis_score=float(v))
        assert eng.detect_audit_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(audit_id="t", analysis_score=float(v))
        assert eng.detect_audit_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_audit_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_audit(audit_id="t", audit_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_audit(audit_id="t")
        eng.add_analysis(audit_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_audit(audit_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_audit(audit_id="a")
        eng.record_audit(audit_id="b")
        eng.add_analysis(audit_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
