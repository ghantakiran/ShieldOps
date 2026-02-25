"""Tests for shieldops.incidents.recurrence_predictor."""

from __future__ import annotations

from shieldops.incidents.recurrence_predictor import (
    FixCompleteness,
    IncidentRecurrencePredictor,
    RecurrencePattern,
    RecurrenceRecord,
    RecurrenceReport,
    RecurrenceRisk,
    SimilarityBasis,
)


def _engine(**kw) -> IncidentRecurrencePredictor:
    return IncidentRecurrencePredictor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # RecurrenceRisk (5 values)

    def test_risk_negligible(self):
        assert RecurrenceRisk.NEGLIGIBLE == "negligible"

    def test_risk_low(self):
        assert RecurrenceRisk.LOW == "low"

    def test_risk_moderate(self):
        assert RecurrenceRisk.MODERATE == "moderate"

    def test_risk_high(self):
        assert RecurrenceRisk.HIGH == "high"

    def test_risk_almost_certain(self):
        assert RecurrenceRisk.ALMOST_CERTAIN == "almost_certain"

    # FixCompleteness (5 values)

    def test_fix_full(self):
        assert FixCompleteness.FULL_FIX == "full_fix"

    def test_fix_partial(self):
        assert FixCompleteness.PARTIAL_FIX == "partial_fix"

    def test_fix_workaround(self):
        assert FixCompleteness.WORKAROUND == "workaround"

    def test_fix_monitoring_only(self):
        assert FixCompleteness.MONITORING_ONLY == "monitoring_only"

    def test_fix_unresolved(self):
        assert FixCompleteness.UNRESOLVED == "unresolved"

    # SimilarityBasis (5 values)

    def test_similarity_root_cause(self):
        assert SimilarityBasis.ROOT_CAUSE == "root_cause"

    def test_similarity_symptoms(self):
        assert SimilarityBasis.SYMPTOMS == "symptoms"

    def test_similarity_affected_service(self):
        assert SimilarityBasis.AFFECTED_SERVICE == "affected_service"

    def test_similarity_time_pattern(self):
        assert SimilarityBasis.TIME_PATTERN == "time_pattern"

    def test_similarity_change_related(self):
        assert SimilarityBasis.CHANGE_RELATED == "change_related"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_recurrence_record_defaults(self):
        rec = RecurrenceRecord()
        assert rec.id
        assert rec.incident_id == ""
        assert rec.service_name == ""
        assert rec.root_cause == ""
        assert rec.fix_completeness == FixCompleteness.UNRESOLVED
        assert rec.recurrence_risk == RecurrenceRisk.NEGLIGIBLE
        assert rec.similarity_score == 0.0
        assert rec.predicted_recurrence_days == 0
        assert rec.actual_recurred is False
        assert rec.created_at > 0

    def test_recurrence_pattern_defaults(self):
        pat = RecurrencePattern()
        assert pat.id
        assert pat.pattern_name == ""
        assert pat.occurrence_count == 0
        assert pat.avg_interval_days == 0.0
        assert pat.services == []
        assert pat.last_seen_at > 0
        assert pat.created_at > 0

    def test_recurrence_report_defaults(self):
        rpt = RecurrenceReport()
        assert rpt.total_records == 0
        assert rpt.total_patterns == 0
        assert rpt.prediction_accuracy_pct == 0.0
        assert rpt.by_risk == {}
        assert rpt.by_fix == {}
        assert rpt.high_risk_incidents == []
        assert rpt.recommendations == []
        assert rpt.generated_at > 0


# -------------------------------------------------------------------
# record_incident
# -------------------------------------------------------------------


class TestRecordIncident:
    def test_basic_record(self):
        eng = _engine()
        rec = eng.record_incident("INC-001", "svc-a")
        assert rec.incident_id == "INC-001"
        assert rec.service_name == "svc-a"
        assert len(eng.list_records()) == 1

    def test_record_assigns_unique_ids(self):
        eng = _engine()
        r1 = eng.record_incident("INC-001")
        r2 = eng.record_incident("INC-002")
        assert r1.id != r2.id

    def test_record_with_fix(self):
        eng = _engine()
        rec = eng.record_incident(
            "INC-001",
            fix_completeness=FixCompleteness.FULL_FIX,
            similarity_score=0.1,
        )
        assert rec.fix_completeness == FixCompleteness.FULL_FIX
        assert rec.similarity_score == 0.1

    def test_risk_computed_from_fix(self):
        eng = _engine()
        rec = eng.record_incident(
            "INC-001",
            fix_completeness=FixCompleteness.UNRESOLVED,
            similarity_score=0.9,
        )
        assert rec.recurrence_risk in (
            RecurrenceRisk.HIGH,
            RecurrenceRisk.ALMOST_CERTAIN,
        )

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        ids = []
        for i in range(4):
            rec = eng.record_incident(f"INC-{i}")
            ids.append(rec.id)
        records = eng.list_records(limit=100)
        assert len(records) == 3
        found = {r.id for r in records}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_record
# -------------------------------------------------------------------


class TestGetRecord:
    def test_get_existing(self):
        eng = _engine()
        rec = eng.record_incident("INC-001")
        found = eng.get_record(rec.id)
        assert found is not None
        assert found.id == rec.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# -------------------------------------------------------------------
# list_records
# -------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_incident("INC-001")
        eng.record_incident("INC-002")
        eng.record_incident("INC-003")
        assert len(eng.list_records()) == 3

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_incident("INC-001", "svc-a")
        eng.record_incident("INC-002", "svc-b")
        eng.record_incident("INC-003", "svc-a")
        results = eng.list_records(service_name="svc-a")
        assert len(results) == 2

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_incident(f"INC-{i}")
        results = eng.list_records(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# predict_recurrence
# -------------------------------------------------------------------


class TestPredictRecurrence:
    def test_predict_existing(self):
        eng = _engine()
        rec = eng.record_incident(
            "INC-001",
            fix_completeness=FixCompleteness.WORKAROUND,
            similarity_score=0.7,
        )
        result = eng.predict_recurrence(rec.id)
        assert result is not None
        assert result["record_id"] == rec.id
        assert "recurrence_risk" in result
        assert "predicted_days" in result

    def test_predict_not_found(self):
        eng = _engine()
        assert eng.predict_recurrence("nope") is None

    def test_predict_updates_record(self):
        eng = _engine()
        rec = eng.record_incident(
            "INC-001",
            fix_completeness=FixCompleteness.UNRESOLVED,
            similarity_score=0.8,
        )
        eng.predict_recurrence(rec.id)
        updated = eng.get_record(rec.id)
        assert updated is not None
        assert updated.predicted_recurrence_days > 0


# -------------------------------------------------------------------
# detect_patterns
# -------------------------------------------------------------------


class TestDetectPatterns:
    def test_patterns_detected(self):
        eng = _engine()
        eng.record_incident(
            "INC-001",
            "svc-a",
            root_cause="oom",
        )
        eng.record_incident(
            "INC-002",
            "svc-b",
            root_cause="oom",
        )
        patterns = eng.detect_patterns()
        assert len(patterns) == 1
        assert patterns[0].pattern_name == "oom"
        assert patterns[0].occurrence_count == 2

    def test_no_patterns(self):
        eng = _engine()
        eng.record_incident(
            "INC-001",
            root_cause="unique_cause",
        )
        patterns = eng.detect_patterns()
        assert patterns == []


# -------------------------------------------------------------------
# mark_recurred
# -------------------------------------------------------------------


class TestMarkRecurred:
    def test_mark_success(self):
        eng = _engine()
        rec = eng.record_incident("INC-001")
        result = eng.mark_recurred(rec.id)
        assert result is not None
        assert result.actual_recurred is True

    def test_mark_not_found(self):
        eng = _engine()
        assert eng.mark_recurred("nope") is None


# -------------------------------------------------------------------
# calculate_prediction_accuracy
# -------------------------------------------------------------------


class TestCalculatePredictionAccuracy:
    def test_no_high_risk(self):
        eng = _engine()
        eng.record_incident(
            "INC-001",
            fix_completeness=FixCompleteness.FULL_FIX,
            similarity_score=0.0,
        )
        assert eng.calculate_prediction_accuracy() == 100.0

    def test_accuracy_with_recurrence(self):
        eng = _engine()
        rec = eng.record_incident(
            "INC-001",
            fix_completeness=FixCompleteness.UNRESOLVED,
            similarity_score=0.9,
        )
        eng.mark_recurred(rec.id)
        accuracy = eng.calculate_prediction_accuracy()
        assert accuracy == 100.0


# -------------------------------------------------------------------
# identify_chronic_incidents
# -------------------------------------------------------------------


class TestIdentifyChronicIncidents:
    def test_chronic_detected(self):
        eng = _engine()
        r1 = eng.record_incident("INC-001", "svc-a")
        r2 = eng.record_incident("INC-002", "svc-a")
        eng.mark_recurred(r1.id)
        eng.mark_recurred(r2.id)
        chronic = eng.identify_chronic_incidents()
        assert len(chronic) == 1
        assert chronic[0]["service_name"] == "svc-a"
        assert chronic[0]["recurred_count"] == 2

    def test_no_chronic(self):
        eng = _engine()
        eng.record_incident("INC-001", "svc-a")
        chronic = eng.identify_chronic_incidents()
        assert chronic == []


# -------------------------------------------------------------------
# generate_recurrence_report
# -------------------------------------------------------------------


class TestGenerateRecurrenceReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_incident(
            "INC-001",
            fix_completeness=FixCompleteness.FULL_FIX,
        )
        eng.record_incident(
            "INC-002",
            fix_completeness=FixCompleteness.UNRESOLVED,
            similarity_score=0.9,
        )
        report = eng.generate_recurrence_report()
        assert report.total_records == 2
        assert isinstance(report.by_risk, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_recurrence_report()
        assert report.total_records == 0
        assert report.total_patterns == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_incident("INC-001")
        eng.record_incident("INC-002")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_records()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_patterns"] == 0
        assert stats["risk_threshold"] == 0.6
        assert stats["risk_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_incident(
            "INC-001",
            fix_completeness=FixCompleteness.FULL_FIX,
        )
        eng.record_incident(
            "INC-002",
            fix_completeness=FixCompleteness.UNRESOLVED,
            similarity_score=0.9,
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert len(stats["risk_distribution"]) > 0
