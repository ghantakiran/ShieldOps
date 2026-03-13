"""Tests for CloudResourceTaggingCompliance."""

from __future__ import annotations

from shieldops.compliance.cloud_resource_tagging_compliance import (
    CloudResourceTaggingCompliance,
    ComplianceLevel,
    TagCategory,
    TagStatus,
)


def _engine(**kw) -> CloudResourceTaggingCompliance:
    return CloudResourceTaggingCompliance(**kw)


class TestEnums:
    def test_tag_status_values(self):
        for v in TagStatus:
            assert isinstance(v.value, str)

    def test_tag_category_values(self):
        for v in TagCategory:
            assert isinstance(v.value, str)

    def test_compliance_level_values(self):
        for v in ComplianceLevel:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(resource_id="r1")
        assert r.resource_id == "r1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(resource_id=f"r-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            resource_id="r1",
            total_tags=10,
            missing_tags=2,
        )
        a = eng.process(r.id)
        assert hasattr(a, "resource_id")
        assert a.compliance_score == 80.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(resource_id="r1", total_tags=5)
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(resource_id="r1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(resource_id="r1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestAuditTagCompliance:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            resource_id="r1",
            missing_tags=3,
        )
        result = eng.audit_tag_compliance()
        assert len(result) == 1

    def test_empty(self):
        r = _engine().audit_tag_compliance()
        assert r == []


class TestDetectUntaggedResources:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            resource_id="r1",
            missing_tags=5,
        )
        result = eng.detect_untagged_resources()
        assert len(result) == 1
        assert result[0]["missing_tags"] == 5

    def test_empty(self):
        r = _engine().detect_untagged_resources()
        assert r == []


class TestRankTeamsByTaggingDiscipline:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            resource_id="r1",
            team_id="t1",
            tag_status=TagStatus.COMPLIANT,
        )
        eng.add_record(
            resource_id="r2",
            team_id="t2",
            tag_status=TagStatus.MISSING_REQUIRED,
        )
        result = eng.rank_teams_by_tagging_discipline()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_teams_by_tagging_discipline()
        assert r == []
