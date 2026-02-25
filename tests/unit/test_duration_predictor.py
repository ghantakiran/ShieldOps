"""Tests for shieldops.incidents.duration_predictor — IncidentDurationPredictor."""

from __future__ import annotations

from shieldops.incidents.duration_predictor import (
    DurationBenchmark,
    DurationBucket,
    DurationRecord,
    DurationReport,
    IncidentComplexity,
    IncidentDurationPredictor,
    ResolutionPath,
)


def _engine(**kw) -> IncidentDurationPredictor:
    return IncidentDurationPredictor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DurationBucket (5)
    def test_bucket_0_15(self):
        assert DurationBucket.MINUTES_0_15 == "minutes_0_15"

    def test_bucket_15_60(self):
        assert DurationBucket.MINUTES_15_60 == "minutes_15_60"

    def test_bucket_1_4(self):
        assert DurationBucket.HOURS_1_4 == "hours_1_4"

    def test_bucket_4_12(self):
        assert DurationBucket.HOURS_4_12 == "hours_4_12"

    def test_bucket_12_plus(self):
        assert DurationBucket.HOURS_12_PLUS == "hours_12_plus"

    # IncidentComplexity (5)
    def test_complexity_trivial(self):
        assert IncidentComplexity.TRIVIAL == "trivial"

    def test_complexity_simple(self):
        assert IncidentComplexity.SIMPLE == "simple"

    def test_complexity_moderate(self):
        assert IncidentComplexity.MODERATE == "moderate"

    def test_complexity_complex(self):
        assert IncidentComplexity.COMPLEX == "complex"

    def test_complexity_catastrophic(self):
        assert IncidentComplexity.CATASTROPHIC == "catastrophic"

    # ResolutionPath (5)
    def test_path_automated(self):
        assert ResolutionPath.AUTOMATED_FIX == "automated_fix"

    def test_path_known_runbook(self):
        assert ResolutionPath.KNOWN_RUNBOOK == "known_runbook"

    def test_path_investigation(self):
        assert ResolutionPath.INVESTIGATION_NEEDED == "investigation_needed"

    def test_path_escalation(self):
        assert ResolutionPath.ESCALATION_REQUIRED == "escalation_required"

    def test_path_vendor(self):
        assert ResolutionPath.VENDOR_DEPENDENCY == "vendor_dependency"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = DurationRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.service_name == ""
        assert r.complexity == IncidentComplexity.MODERATE
        assert r.resolution_path == ResolutionPath.INVESTIGATION_NEEDED
        assert r.predicted_bucket == DurationBucket.HOURS_1_4
        assert r.predicted_minutes == 0.0
        assert r.actual_minutes == 0.0
        assert r.responder_count == 1
        assert r.is_business_hours is True
        assert r.created_at > 0

    def test_benchmark_defaults(self):
        r = DurationBenchmark()
        assert r.id
        assert r.service_name == ""
        assert r.avg_duration_minutes == 0.0
        assert r.p50_minutes == 0.0
        assert r.p90_minutes == 0.0
        assert r.sample_count == 0
        assert r.by_complexity == {}
        assert r.created_at > 0

    def test_report_defaults(self):
        r = DurationReport()
        assert r.total_predictions == 0
        assert r.accuracy_pct == 0.0
        assert r.avg_predicted_minutes == 0.0
        assert r.avg_actual_minutes == 0.0
        assert r.by_bucket == {}
        assert r.by_complexity == {}
        assert r.slow_resolving_services == []
        assert r.recommendations == []


# -------------------------------------------------------------------
# record_prediction
# -------------------------------------------------------------------


class TestRecordPrediction:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_prediction(
            "INC-001",
            "api-svc",
            "sev2",
            IncidentComplexity.SIMPLE,
            ResolutionPath.KNOWN_RUNBOOK,
        )
        assert r.incident_id == "INC-001"
        assert r.service_name == "api-svc"
        assert r.severity == "sev2"
        assert r.complexity == IncidentComplexity.SIMPLE

    def test_with_all_params(self):
        eng = _engine()
        r = eng.record_prediction(
            "INC-002",
            "db-svc",
            "sev1",
            IncidentComplexity.CATASTROPHIC,
            ResolutionPath.VENDOR_DEPENDENCY,
            responder_count=3,
            is_business_hours=False,
        )
        assert r.responder_count == 3
        assert r.is_business_hours is False
        assert r.predicted_minutes > 0

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_prediction(
            "INC-001",
            "svc-a",
            "sev3",
            IncidentComplexity.MODERATE,
            ResolutionPath.INVESTIGATION_NEEDED,
        )
        r2 = eng.record_prediction(
            "INC-002",
            "svc-b",
            "sev3",
            IncidentComplexity.MODERATE,
            ResolutionPath.INVESTIGATION_NEEDED,
        )
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_prediction(
                f"INC-{i}",
                "svc",
                "sev3",
                IncidentComplexity.SIMPLE,
                ResolutionPath.KNOWN_RUNBOOK,
            )
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_prediction
# -------------------------------------------------------------------


class TestGetPrediction:
    def test_found(self):
        eng = _engine()
        r = eng.record_prediction(
            "INC-001",
            "svc",
            "sev3",
            IncidentComplexity.SIMPLE,
            ResolutionPath.KNOWN_RUNBOOK,
        )
        assert eng.get_prediction(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_prediction("nonexistent") is None


# -------------------------------------------------------------------
# list_predictions
# -------------------------------------------------------------------


class TestListPredictions:
    def test_list_all(self):
        eng = _engine()
        eng.record_prediction(
            "INC-001",
            "svc-a",
            "sev3",
            IncidentComplexity.SIMPLE,
            ResolutionPath.KNOWN_RUNBOOK,
        )
        eng.record_prediction(
            "INC-002",
            "svc-b",
            "sev3",
            IncidentComplexity.MODERATE,
            ResolutionPath.INVESTIGATION_NEEDED,
        )
        assert len(eng.list_predictions()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_prediction(
            "INC-001",
            "svc-a",
            "sev3",
            IncidentComplexity.SIMPLE,
            ResolutionPath.KNOWN_RUNBOOK,
        )
        eng.record_prediction(
            "INC-002",
            "svc-b",
            "sev3",
            IncidentComplexity.SIMPLE,
            ResolutionPath.KNOWN_RUNBOOK,
        )
        results = eng.list_predictions(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_complexity(self):
        eng = _engine()
        eng.record_prediction(
            "INC-001",
            "svc",
            "sev3",
            IncidentComplexity.TRIVIAL,
            ResolutionPath.AUTOMATED_FIX,
        )
        eng.record_prediction(
            "INC-002",
            "svc",
            "sev3",
            IncidentComplexity.CATASTROPHIC,
            ResolutionPath.VENDOR_DEPENDENCY,
        )
        results = eng.list_predictions(complexity=IncidentComplexity.TRIVIAL)
        assert len(results) == 1


# -------------------------------------------------------------------
# predict_duration
# -------------------------------------------------------------------


class TestPredictDuration:
    def test_trivial_automated_short(self):
        eng = _engine()
        result = eng.predict_duration(
            IncidentComplexity.TRIVIAL,
            ResolutionPath.AUTOMATED_FIX,
        )
        # base=10 * 0.3 = 3.0 minutes → MINUTES_0_15
        assert result["predicted_bucket"] == "minutes_0_15"
        assert result["predicted_minutes"] < 15.0

    def test_catastrophic_vendor_long(self):
        eng = _engine()
        result = eng.predict_duration(
            IncidentComplexity.CATASTROPHIC,
            ResolutionPath.VENDOR_DEPENDENCY,
        )
        # base=720 * 2.5 = 1800 minutes → HOURS_12_PLUS
        assert result["predicted_bucket"] == "hours_12_plus"
        assert result["predicted_minutes"] >= 720.0

    def test_non_business_hours_adds_time(self):
        eng = _engine()
        bh = eng.predict_duration(
            IncidentComplexity.MODERATE,
            ResolutionPath.INVESTIGATION_NEEDED,
            is_business_hours=True,
        )
        nbh = eng.predict_duration(
            IncidentComplexity.MODERATE,
            ResolutionPath.INVESTIGATION_NEEDED,
            is_business_hours=False,
        )
        assert nbh["predicted_minutes"] > bh["predicted_minutes"]


# -------------------------------------------------------------------
# record_actual_duration
# -------------------------------------------------------------------


class TestRecordActualDuration:
    def test_valid_record(self):
        eng = _engine()
        r = eng.record_prediction(
            "INC-001",
            "svc",
            "sev3",
            IncidentComplexity.TRIVIAL,
            ResolutionPath.AUTOMATED_FIX,
        )
        result = eng.record_actual_duration(r.id, 10.0)
        assert result["actual_minutes"] == 10.0
        assert result["accurate"] is True  # 10 is in [0, 15)

    def test_not_found(self):
        eng = _engine()
        result = eng.record_actual_duration("bad-id", 10.0)
        assert result["error"] == "record_not_found"

    def test_actual_stored_on_record(self):
        eng = _engine()
        r = eng.record_prediction(
            "INC-001",
            "svc",
            "sev3",
            IncidentComplexity.SIMPLE,
            ResolutionPath.KNOWN_RUNBOOK,
        )
        eng.record_actual_duration(r.id, 45.0)
        updated = eng.get_prediction(r.id)
        assert updated.actual_minutes == 45.0


# -------------------------------------------------------------------
# calculate_accuracy
# -------------------------------------------------------------------


class TestCalculateAccuracy:
    def test_empty(self):
        eng = _engine()
        result = eng.calculate_accuracy()
        assert result["accuracy_pct"] == 0.0

    def test_all_accurate(self):
        eng = _engine()
        # TRIVIAL + AUTOMATED_FIX → 3.0 min → MINUTES_0_15
        for i in range(3):
            r = eng.record_prediction(
                f"INC-{i}",
                "svc",
                "sev3",
                IncidentComplexity.TRIVIAL,
                ResolutionPath.AUTOMATED_FIX,
            )
            eng.record_actual_duration(r.id, 10.0)  # within [0, 15)
        result = eng.calculate_accuracy()
        assert result["accuracy_pct"] == 100.0

    def test_mixed(self):
        eng = _engine()
        # Accurate: TRIVIAL + AUTOMATED → bucket MINUTES_0_15, actual=10
        r1 = eng.record_prediction(
            "INC-1",
            "svc",
            "sev3",
            IncidentComplexity.TRIVIAL,
            ResolutionPath.AUTOMATED_FIX,
        )
        eng.record_actual_duration(r1.id, 10.0)
        # Inaccurate: CATASTROPHIC + VENDOR → bucket HOURS_12_PLUS, actual=50
        r2 = eng.record_prediction(
            "INC-2",
            "svc",
            "sev1",
            IncidentComplexity.CATASTROPHIC,
            ResolutionPath.VENDOR_DEPENDENCY,
        )
        eng.record_actual_duration(r2.id, 50.0)  # 50 not in [720, inf)
        result = eng.calculate_accuracy()
        assert result["accuracy_pct"] == 50.0


# -------------------------------------------------------------------
# compute_benchmarks
# -------------------------------------------------------------------


class TestComputeBenchmarks:
    def test_empty(self):
        eng = _engine()
        bm = eng.compute_benchmarks()
        assert bm.sample_count == 0
        assert bm.avg_duration_minutes == 0.0

    def test_with_data(self):
        eng = _engine()
        r1 = eng.record_prediction(
            "INC-1",
            "svc-a",
            "sev3",
            IncidentComplexity.SIMPLE,
            ResolutionPath.KNOWN_RUNBOOK,
        )
        eng.record_actual_duration(r1.id, 30.0)
        r2 = eng.record_prediction(
            "INC-2",
            "svc-a",
            "sev3",
            IncidentComplexity.SIMPLE,
            ResolutionPath.KNOWN_RUNBOOK,
        )
        eng.record_actual_duration(r2.id, 60.0)
        bm = eng.compute_benchmarks(service_name="svc-a")
        assert bm.sample_count == 2
        assert bm.avg_duration_minutes == 45.0


# -------------------------------------------------------------------
# identify_slow_resolving_services
# -------------------------------------------------------------------


class TestIdentifySlowResolvingServices:
    def test_with_slow(self):
        eng = _engine()
        r = eng.record_prediction(
            "INC-1",
            "slow-svc",
            "sev2",
            IncidentComplexity.COMPLEX,
            ResolutionPath.ESCALATION_REQUIRED,
        )
        eng.record_actual_duration(r.id, 120.0)
        slow = eng.identify_slow_resolving_services(threshold_minutes=60.0)
        assert len(slow) == 1
        assert slow[0]["service_name"] == "slow-svc"

    def test_none_slow(self):
        eng = _engine()
        r = eng.record_prediction(
            "INC-1",
            "fast-svc",
            "sev4",
            IncidentComplexity.TRIVIAL,
            ResolutionPath.AUTOMATED_FIX,
        )
        eng.record_actual_duration(r.id, 5.0)
        slow = eng.identify_slow_resolving_services(threshold_minutes=60.0)
        assert len(slow) == 0


# -------------------------------------------------------------------
# generate_duration_report
# -------------------------------------------------------------------


class TestGenerateDurationReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_duration_report()
        assert report.total_predictions == 0
        assert report.accuracy_pct == 0.0

    def test_with_data(self):
        eng = _engine()
        r1 = eng.record_prediction(
            "INC-1",
            "svc-a",
            "sev3",
            IncidentComplexity.SIMPLE,
            ResolutionPath.KNOWN_RUNBOOK,
        )
        eng.record_actual_duration(r1.id, 25.0)
        r2 = eng.record_prediction(
            "INC-2",
            "svc-b",
            "sev2",
            IncidentComplexity.COMPLEX,
            ResolutionPath.ESCALATION_REQUIRED,
        )
        eng.record_actual_duration(r2.id, 300.0)
        report = eng.generate_duration_report()
        assert report.total_predictions == 2
        assert report.by_complexity != {}


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_prediction(
            "INC-001",
            "svc",
            "sev3",
            IncidentComplexity.SIMPLE,
            ResolutionPath.KNOWN_RUNBOOK,
        )
        eng.clear_data()
        assert len(eng._records) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["accuracy_pct"] == 0.0

    def test_populated(self):
        eng = _engine()
        r = eng.record_prediction(
            "INC-001",
            "svc-a",
            "sev2",
            IncidentComplexity.MODERATE,
            ResolutionPath.INVESTIGATION_NEEDED,
        )
        eng.record_actual_duration(r.id, 90.0)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_incidents"] == 1
