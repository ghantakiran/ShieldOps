"""Tests for shieldops.observability.noise_classifier — AlertNoiseClassifier."""

from __future__ import annotations

from shieldops.observability.noise_classifier import (
    AlertNoiseClassifier,
    ClassificationMethod,
    NoiseCategory,
    NoiseClassifierReport,
    NoiseRecord,
    NoiseRule,
    SignalStrength,
)


def _engine(**kw) -> AlertNoiseClassifier:
    return AlertNoiseClassifier(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # NoiseCategory (5)
    def test_category_false_positive(self):
        assert NoiseCategory.FALSE_POSITIVE == "false_positive"

    def test_category_transient(self):
        assert NoiseCategory.TRANSIENT == "transient"

    def test_category_duplicate(self):
        assert NoiseCategory.DUPLICATE == "duplicate"

    def test_category_low_priority(self):
        assert NoiseCategory.LOW_PRIORITY == "low_priority"

    def test_category_informational(self):
        assert NoiseCategory.INFORMATIONAL == "informational"

    # SignalStrength (5)
    def test_strength_strong(self):
        assert SignalStrength.STRONG == "strong"

    def test_strength_moderate(self):
        assert SignalStrength.MODERATE == "moderate"

    def test_strength_weak(self):
        assert SignalStrength.WEAK == "weak"

    def test_strength_noise(self):
        assert SignalStrength.NOISE == "noise"

    def test_strength_unknown(self):
        assert SignalStrength.UNKNOWN == "unknown"

    # ClassificationMethod (5)
    def test_method_rule_based(self):
        assert ClassificationMethod.RULE_BASED == "rule_based"

    def test_method_ml_model(self):
        assert ClassificationMethod.ML_MODEL == "ml_model"

    def test_method_heuristic(self):
        assert ClassificationMethod.HEURISTIC == "heuristic"

    def test_method_manual(self):
        assert ClassificationMethod.MANUAL == "manual"

    def test_method_hybrid(self):
        assert ClassificationMethod.HYBRID == "hybrid"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_noise_record_defaults(self):
        r = NoiseRecord()
        assert r.id
        assert r.alert_name == ""
        assert r.source == ""
        assert r.category == NoiseCategory.INFORMATIONAL
        assert r.signal_strength == SignalStrength.UNKNOWN
        assert r.method == ClassificationMethod.RULE_BASED
        assert r.noise_score == 0.0
        assert r.suppressed is False
        assert r.created_at > 0

    def test_noise_rule_defaults(self):
        r = NoiseRule()
        assert r.id
        assert r.rule_name == ""
        assert r.category == NoiseCategory.INFORMATIONAL
        assert r.method == ClassificationMethod.RULE_BASED
        assert r.pattern == ""
        assert r.threshold == 0.5
        assert r.enabled is True
        assert r.created_at > 0

    def test_report_defaults(self):
        r = NoiseClassifierReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.noise_count == 0
        assert r.signal_count == 0
        assert r.noise_ratio_pct == 0.0
        assert r.by_category == {}
        assert r.by_signal_strength == {}
        assert r.by_method == {}
        assert r.top_noisy_sources == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_noise
# -------------------------------------------------------------------


class TestRecordNoise:
    def test_basic(self):
        eng = _engine()
        r = eng.record_noise("cpu-spike")
        assert r.alert_name == "cpu-spike"
        assert r.category == NoiseCategory.INFORMATIONAL

    def test_with_params(self):
        eng = _engine()
        r = eng.record_noise(
            "disk-full",
            source="prometheus",
            category=NoiseCategory.FALSE_POSITIVE,
            signal_strength=SignalStrength.NOISE,
            method=ClassificationMethod.ML_MODEL,
            noise_score=0.92,
            suppressed=True,
        )
        assert r.category == NoiseCategory.FALSE_POSITIVE
        assert r.signal_strength == SignalStrength.NOISE
        assert r.noise_score == 0.92
        assert r.suppressed is True

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_noise("alert-a")
        r2 = eng.record_noise("alert-b")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_noise(f"alert-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_noise
# -------------------------------------------------------------------


class TestGetNoise:
    def test_found(self):
        eng = _engine()
        r = eng.record_noise("test-alert")
        assert eng.get_noise(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_noise("nonexistent") is None


# -------------------------------------------------------------------
# list_noises
# -------------------------------------------------------------------


class TestListNoises:
    def test_list_all(self):
        eng = _engine()
        eng.record_noise("alert-a")
        eng.record_noise("alert-b")
        assert len(eng.list_noises()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_noise("alert-a", category=NoiseCategory.FALSE_POSITIVE)
        eng.record_noise("alert-b", category=NoiseCategory.TRANSIENT)
        results = eng.list_noises(category=NoiseCategory.FALSE_POSITIVE)
        assert len(results) == 1
        assert results[0].category == NoiseCategory.FALSE_POSITIVE

    def test_filter_by_signal_strength(self):
        eng = _engine()
        eng.record_noise("alert-a", signal_strength=SignalStrength.NOISE)
        eng.record_noise("alert-b", signal_strength=SignalStrength.STRONG)
        results = eng.list_noises(signal_strength=SignalStrength.NOISE)
        assert len(results) == 1

    def test_filter_by_method(self):
        eng = _engine()
        eng.record_noise("alert-a", method=ClassificationMethod.ML_MODEL)
        eng.record_noise("alert-b", method=ClassificationMethod.MANUAL)
        results = eng.list_noises(method=ClassificationMethod.ML_MODEL)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_noise(f"alert-{i}")
        assert len(eng.list_noises(limit=5)) == 5


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        rule = eng.add_rule("suppress-flapping")
        assert rule.rule_name == "suppress-flapping"
        assert rule.category == NoiseCategory.INFORMATIONAL
        assert rule.enabled is True

    def test_with_params(self):
        eng = _engine()
        rule = eng.add_rule(
            "ml-classifier",
            category=NoiseCategory.FALSE_POSITIVE,
            method=ClassificationMethod.ML_MODEL,
            pattern="cpu.*high",
            threshold=0.8,
        )
        assert rule.category == NoiseCategory.FALSE_POSITIVE
        assert rule.method == ClassificationMethod.ML_MODEL
        assert rule.threshold == 0.8

    def test_unique_rule_ids(self):
        eng = _engine()
        r1 = eng.add_rule("rule-a")
        r2 = eng.add_rule("rule-b")
        assert r1.id != r2.id


# -------------------------------------------------------------------
# analyze_noise_by_source
# -------------------------------------------------------------------


class TestAnalyzeNoiseBySource:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_noise_by_source()
        assert result["total_sources"] == 0
        assert result["breakdown"] == []

    def test_with_data(self):
        eng = _engine()
        for _ in range(5):
            eng.record_noise("cpu", source="datadog", signal_strength=SignalStrength.NOISE)
        eng.record_noise("mem", source="prometheus", signal_strength=SignalStrength.STRONG)
        result = eng.analyze_noise_by_source()
        assert result["total_sources"] == 2
        sources = [b["source"] for b in result["breakdown"]]
        assert "datadog" in sources

    def test_sorted_descending(self):
        eng = _engine()
        for _ in range(3):
            eng.record_noise("alert", source="low-noise", signal_strength=SignalStrength.STRONG)
        for _ in range(7):
            eng.record_noise("alert", source="high-noise", signal_strength=SignalStrength.NOISE)
        result = eng.analyze_noise_by_source()
        ratios = [b["noise_ratio_pct"] for b in result["breakdown"]]
        assert ratios == sorted(ratios, reverse=True)


# -------------------------------------------------------------------
# identify_noisy_alerts
# -------------------------------------------------------------------


class TestIdentifyNoisyAlerts:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_noisy_alerts() == []

    def test_with_data(self):
        eng = _engine()
        for _ in range(3):
            eng.record_noise("noisy-alert", noise_score=0.9)
        eng.record_noise("quiet-alert", noise_score=0.1)
        results = eng.identify_noisy_alerts()
        assert len(results) == 2
        assert results[0]["alert_name"] == "noisy-alert"
        assert results[0]["avg_noise_score"] > results[1]["avg_noise_score"]

    def test_sorted_descending(self):
        eng = _engine()
        eng.record_noise("alpha", noise_score=0.3)
        eng.record_noise("beta", noise_score=0.8)
        results = eng.identify_noisy_alerts()
        assert results[0]["avg_noise_score"] >= results[-1]["avg_noise_score"]


# -------------------------------------------------------------------
# rank_by_noise_ratio
# -------------------------------------------------------------------


class TestRankByNoiseRatio:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_noise_ratio() == []

    def test_sorted_by_ratio(self):
        eng = _engine()
        for _ in range(9):
            eng.record_noise("high-noise", signal_strength=SignalStrength.NOISE)
        eng.record_noise("high-noise", signal_strength=SignalStrength.STRONG)
        for _ in range(5):
            eng.record_noise("low-noise", signal_strength=SignalStrength.STRONG)
        results = eng.rank_by_noise_ratio()
        assert results[0]["noise_ratio_pct"] >= results[-1]["noise_ratio_pct"]
        assert results[0]["alert_name"] == "high-noise"


# -------------------------------------------------------------------
# detect_noise_trends
# -------------------------------------------------------------------


class TestDetectNoiseTrends:
    def test_insufficient_data(self):
        eng = _engine()
        eng.record_noise("alert-a")
        result = eng.detect_noise_trends()
        assert result["trend"] == "insufficient_data"

    def test_stable_trend(self):
        eng = _engine()
        for _ in range(4):
            eng.record_noise("alert", signal_strength=SignalStrength.NOISE)
        for _ in range(4):
            eng.record_noise("alert", signal_strength=SignalStrength.NOISE)
        result = eng.detect_noise_trends()
        assert result["trend"] in ("stable", "improving", "worsening")

    def test_worsening_trend(self):
        eng = _engine()
        for _ in range(8):
            eng.record_noise("alert", signal_strength=SignalStrength.STRONG)
        for _ in range(8):
            eng.record_noise("alert", signal_strength=SignalStrength.NOISE)
        result = eng.detect_noise_trends()
        assert result["trend"] == "worsening"
        assert result["total_records"] == 16


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert isinstance(report, NoiseClassifierReport)
        assert report.total_records == 0
        assert report.recommendations

    def test_with_data(self):
        eng = _engine()
        eng.add_rule("rule-a", category=NoiseCategory.FALSE_POSITIVE)
        eng.record_noise("alert-a", source="prom", signal_strength=SignalStrength.NOISE)
        eng.record_noise("alert-b", source="prom", signal_strength=SignalStrength.STRONG)
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_rules == 1
        assert report.noise_count == 1
        assert report.by_signal_strength


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_records_and_rules(self):
        eng = _engine()
        eng.record_noise("alert-a")
        eng.add_rule("rule-a")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["suppressed_count"] == 0

    def test_populated(self):
        eng = _engine(max_noise_ratio_pct=25.0)
        eng.record_noise(
            "alert-a",
            source="datadog",
            signal_strength=SignalStrength.NOISE,
            noise_score=0.95,
            suppressed=True,
        )
        eng.record_noise("alert-b", source="prometheus", signal_strength=SignalStrength.STRONG)
        eng.add_rule("rule-a")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_rules"] == 1
        assert stats["suppressed_count"] == 1
        assert stats["max_noise_ratio_pct"] == 25.0
        assert stats["unique_sources"] == 2
        assert stats["avg_noise_score"] > 0.0
