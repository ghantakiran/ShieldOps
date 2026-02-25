"""Tests for shieldops.knowledge.knowledge_gap — KnowledgeGapDetector.

Covers:
- GapType, GapPriority, KnowledgeArea enums
- KnowledgeGap, KnowledgeCoverage, KnowledgeReport model defaults
- record_gap (basic, unique IDs, extra fields, eviction at max)
- get_gap (found, not found)
- list_gaps (all, filter service, filter type, limit)
- resolve_gap (success, not found)
- calculate_coverage (all, by service, empty)
- detect_tribal_knowledge_risks (found, none)
- identify_stale_documentation (found, none)
- rank_by_priority (basic, empty)
- generate_knowledge_report (populated, empty)
- clear_data (basic)
- get_stats (empty, populated)
"""

from __future__ import annotations

from shieldops.knowledge.knowledge_gap import (
    GapPriority,
    GapType,
    KnowledgeArea,
    KnowledgeCoverage,
    KnowledgeGap,
    KnowledgeGapDetector,
    KnowledgeReport,
)


def _engine(**kw) -> KnowledgeGapDetector:
    return KnowledgeGapDetector(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # GapType (5 values)

    def test_type_missing_runbook(self):
        assert GapType.MISSING_RUNBOOK == "missing_runbook"

    def test_type_outdated_doc(self):
        assert GapType.OUTDATED_DOC == "outdated_doc"

    def test_type_undocumented_service(self):
        assert GapType.UNDOCUMENTED_SERVICE == "undocumented_service"

    def test_type_tribal_knowledge(self):
        assert GapType.TRIBAL_KNOWLEDGE == "tribal_knowledge"

    def test_type_no_troubleshooting_guide(self):
        assert GapType.NO_TROUBLESHOOTING_GUIDE == "no_troubleshooting_guide"

    # GapPriority (5 values)

    def test_priority_critical(self):
        assert GapPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert GapPriority.HIGH == "high"

    def test_priority_medium(self):
        assert GapPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert GapPriority.LOW == "low"

    def test_priority_informational(self):
        assert GapPriority.INFORMATIONAL == "informational"

    # KnowledgeArea (5 values)

    def test_area_incident_response(self):
        assert KnowledgeArea.INCIDENT_RESPONSE == "incident_response"

    def test_area_deployment(self):
        assert KnowledgeArea.DEPLOYMENT == "deployment"

    def test_area_architecture(self):
        assert KnowledgeArea.ARCHITECTURE == "architecture"

    def test_area_security(self):
        assert KnowledgeArea.SECURITY == "security"

    def test_area_operations(self):
        assert KnowledgeArea.OPERATIONS == "operations"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_knowledge_gap_defaults(self):
        g = KnowledgeGap(service_name="auth-svc")
        assert g.id
        assert g.service_name == "auth-svc"
        assert g.gap_type == GapType.MISSING_RUNBOOK
        assert g.area == (KnowledgeArea.INCIDENT_RESPONSE)
        assert g.priority == GapPriority.MEDIUM
        assert g.description == ""
        assert g.single_expert == ""
        assert g.doc_age_days == 0
        assert g.is_resolved is False
        assert g.created_at > 0

    def test_knowledge_coverage_defaults(self):
        c = KnowledgeCoverage(
            service_name="api-svc",
        )
        assert c.service_name == "api-svc"
        assert c.area == (KnowledgeArea.INCIDENT_RESPONSE)
        assert c.coverage_pct == 0.0
        assert c.gap_count == 0
        assert c.critical_gaps == 0
        assert c.last_reviewed_at > 0
        assert c.created_at > 0

    def test_knowledge_report_defaults(self):
        r = KnowledgeReport()
        assert r.total_gaps == 0
        assert r.resolved_gaps == 0
        assert r.coverage_pct == 0.0
        assert r.by_type == {}
        assert r.by_priority == {}
        assert r.by_area == {}
        assert r.tribal_knowledge_risks == []
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_gap
# -------------------------------------------------------------------


class TestRecordGap:
    def test_basic(self):
        e = _engine()
        g = e.record_gap(
            service_name="auth-svc",
            gap_type=GapType.MISSING_RUNBOOK,
            area=KnowledgeArea.INCIDENT_RESPONSE,
            priority=GapPriority.HIGH,
        )
        assert g.service_name == "auth-svc"
        assert g.gap_type == GapType.MISSING_RUNBOOK
        assert g.area == (KnowledgeArea.INCIDENT_RESPONSE)
        assert g.priority == GapPriority.HIGH

    def test_unique_ids(self):
        e = _engine()
        g1 = e.record_gap(service_name="a")
        g2 = e.record_gap(service_name="b")
        assert g1.id != g2.id

    def test_extra_fields(self):
        e = _engine()
        g = e.record_gap(
            service_name="db-svc",
            gap_type=GapType.TRIBAL_KNOWLEDGE,
            single_expert="alice",
            doc_age_days=365,
            description="Only Alice knows",
        )
        assert g.gap_type == GapType.TRIBAL_KNOWLEDGE
        assert g.single_expert == "alice"
        assert g.doc_age_days == 365
        assert g.description == "Only Alice knows"

    def test_evicts_at_max(self):
        e = _engine(max_gaps=2)
        g1 = e.record_gap(service_name="a")
        e.record_gap(service_name="b")
        e.record_gap(service_name="c")
        gaps = e.list_gaps()
        ids = {g.id for g in gaps}
        assert g1.id not in ids
        assert len(gaps) == 2


# -------------------------------------------------------------------
# get_gap
# -------------------------------------------------------------------


class TestGetGap:
    def test_found(self):
        e = _engine()
        g = e.record_gap(service_name="auth")
        assert e.get_gap(g.id) is not None
        assert e.get_gap(g.id).service_name == "auth"

    def test_not_found(self):
        e = _engine()
        assert e.get_gap("nonexistent") is None


# -------------------------------------------------------------------
# list_gaps
# -------------------------------------------------------------------


class TestListGaps:
    def test_list_all(self):
        e = _engine()
        e.record_gap(service_name="a")
        e.record_gap(service_name="b")
        e.record_gap(service_name="c")
        assert len(e.list_gaps()) == 3

    def test_filter_by_service(self):
        e = _engine()
        e.record_gap(service_name="auth")
        e.record_gap(service_name="billing")
        filtered = e.list_gaps(
            service_name="auth",
        )
        assert len(filtered) == 1
        assert filtered[0].service_name == "auth"

    def test_filter_by_type(self):
        e = _engine()
        e.record_gap(
            gap_type=GapType.MISSING_RUNBOOK,
        )
        e.record_gap(
            gap_type=GapType.OUTDATED_DOC,
        )
        filtered = e.list_gaps(
            gap_type=GapType.MISSING_RUNBOOK,
        )
        assert len(filtered) == 1

    def test_limit(self):
        e = _engine()
        for i in range(10):
            e.record_gap(service_name=f"s-{i}")
        assert len(e.list_gaps(limit=3)) == 3


# -------------------------------------------------------------------
# resolve_gap
# -------------------------------------------------------------------


class TestResolveGap:
    def test_success(self):
        e = _engine()
        g = e.record_gap(service_name="auth")
        result = e.resolve_gap(g.id)
        assert result is not None
        assert result.is_resolved is True

    def test_not_found(self):
        e = _engine()
        assert e.resolve_gap("nonexistent") is None


# -------------------------------------------------------------------
# calculate_coverage
# -------------------------------------------------------------------


class TestCalculateCoverage:
    def test_all(self):
        e = _engine()
        g1 = e.record_gap(service_name="auth")
        e.record_gap(service_name="billing")
        e.resolve_gap(g1.id)
        cov = e.calculate_coverage()
        assert cov.service_name == "all"
        assert cov.gap_count == 2
        assert cov.coverage_pct == 50.0

    def test_by_service(self):
        e = _engine()
        g = e.record_gap(service_name="auth")
        e.record_gap(service_name="billing")
        e.resolve_gap(g.id)
        cov = e.calculate_coverage(
            service_name="auth",
        )
        assert cov.service_name == "auth"
        assert cov.coverage_pct == 100.0

    def test_empty(self):
        e = _engine()
        cov = e.calculate_coverage()
        assert cov.gap_count == 0
        assert cov.coverage_pct == 100.0


# -------------------------------------------------------------------
# detect_tribal_knowledge_risks
# -------------------------------------------------------------------


class TestDetectTribalKnowledgeRisks:
    def test_found(self):
        e = _engine()
        e.record_gap(
            service_name="auth",
            gap_type=GapType.TRIBAL_KNOWLEDGE,
            single_expert="alice",
            priority=GapPriority.CRITICAL,
        )
        e.record_gap(
            service_name="billing",
            gap_type=GapType.MISSING_RUNBOOK,
        )
        risks = e.detect_tribal_knowledge_risks()
        assert len(risks) == 1
        assert risks[0]["service_name"] == "auth"
        assert risks[0]["single_expert"] == "alice"

    def test_none(self):
        e = _engine()
        e.record_gap(
            gap_type=GapType.MISSING_RUNBOOK,
        )
        assert e.detect_tribal_knowledge_risks() == []


# -------------------------------------------------------------------
# identify_stale_documentation
# -------------------------------------------------------------------


class TestIdentifyStaleDocumentation:
    def test_found(self):
        e = _engine()
        e.record_gap(
            service_name="old-svc",
            doc_age_days=365,
        )
        e.record_gap(
            service_name="new-svc",
            doc_age_days=30,
        )
        stale = e.identify_stale_documentation(
            max_age_days=180,
        )
        assert len(stale) == 1
        assert stale[0]["service_name"] == "old-svc"
        assert stale[0]["doc_age_days"] == 365

    def test_none(self):
        e = _engine()
        e.record_gap(doc_age_days=10)
        assert (
            e.identify_stale_documentation(
                max_age_days=180,
            )
            == []
        )


# -------------------------------------------------------------------
# rank_by_priority
# -------------------------------------------------------------------


class TestRankByPriority:
    def test_basic(self):
        e = _engine()
        e.record_gap(
            service_name="low-p",
            priority=GapPriority.LOW,
        )
        e.record_gap(
            service_name="critical-p",
            priority=GapPriority.CRITICAL,
        )
        ranked = e.rank_by_priority()
        assert len(ranked) == 2
        assert ranked[0]["priority"] == "critical"
        assert ranked[1]["priority"] == "low"

    def test_empty(self):
        e = _engine()
        assert e.rank_by_priority() == []


# -------------------------------------------------------------------
# generate_knowledge_report
# -------------------------------------------------------------------


class TestGenerateKnowledgeReport:
    def test_populated(self):
        e = _engine()
        g = e.record_gap(
            service_name="auth",
            gap_type=GapType.TRIBAL_KNOWLEDGE,
            area=KnowledgeArea.SECURITY,
            priority=GapPriority.CRITICAL,
            single_expert="alice",
        )
        e.record_gap(
            service_name="billing",
            gap_type=GapType.MISSING_RUNBOOK,
            area=KnowledgeArea.OPERATIONS,
            priority=GapPriority.LOW,
        )
        e.resolve_gap(g.id)
        report = e.generate_knowledge_report()
        assert report.total_gaps == 2
        assert report.resolved_gaps == 1
        assert report.coverage_pct == 50.0
        assert "tribal_knowledge" in report.by_type
        assert "critical" in report.by_priority
        assert "security" in report.by_area
        assert len(report.recommendations) > 0

    def test_empty(self):
        e = _engine()
        report = e.generate_knowledge_report()
        assert report.total_gaps == 0
        assert report.resolved_gaps == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_basic(self):
        e = _engine()
        e.record_gap(service_name="a")
        e.record_gap(service_name="b")
        count = e.clear_data()
        assert count == 2
        assert e.list_gaps() == []


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        e = _engine()
        stats = e.get_stats()
        assert stats["total_gaps"] == 0
        assert stats["max_gaps"] == 100000
        assert stats["stale_doc_threshold_days"] == 180
        assert stats["type_distribution"] == {}

    def test_populated(self):
        e = _engine()
        e.record_gap(
            gap_type=GapType.TRIBAL_KNOWLEDGE,
        )
        e.record_gap(
            gap_type=GapType.MISSING_RUNBOOK,
        )
        e.record_gap(
            gap_type=GapType.TRIBAL_KNOWLEDGE,
        )
        stats = e.get_stats()
        assert stats["total_gaps"] == 3
        assert stats["type_distribution"]["tribal_knowledge"] == 2
        assert stats["type_distribution"]["missing_runbook"] == 1
