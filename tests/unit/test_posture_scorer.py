"""Tests for shieldops.vulnerability.posture_scorer — SecurityPostureScorer."""

from __future__ import annotations

from shieldops.vulnerability.posture_scorer import (
    PostureCategory,
    PostureCheck,
    PostureGrade,
    PostureScore,
    SecurityPostureScorer,
)


def _scorer(**kw) -> SecurityPostureScorer:
    return SecurityPostureScorer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # PostureCategory (6 values)

    def test_category_vulnerability_management(self):
        assert PostureCategory.VULNERABILITY_MANAGEMENT == "vulnerability_management"

    def test_category_access_control(self):
        assert PostureCategory.ACCESS_CONTROL == "access_control"

    def test_category_encryption(self):
        assert PostureCategory.ENCRYPTION == "encryption"

    def test_category_network_security(self):
        assert PostureCategory.NETWORK_SECURITY == "network_security"

    def test_category_compliance(self):
        assert PostureCategory.COMPLIANCE == "compliance"

    def test_category_incident_response(self):
        assert PostureCategory.INCIDENT_RESPONSE == "incident_response"

    # PostureGrade (5 values)

    def test_grade_a(self):
        assert PostureGrade.A == "A"

    def test_grade_b(self):
        assert PostureGrade.B == "B"

    def test_grade_c(self):
        assert PostureGrade.C == "C"

    def test_grade_d(self):
        assert PostureGrade.D == "D"

    def test_grade_f(self):
        assert PostureGrade.F == "F"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_posture_check_defaults(self):
        check = PostureCheck(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="tls_enabled",
        )
        assert check.id
        assert check.passed is True
        assert check.weight == 1.0
        assert check.details == ""
        assert check.checked_at > 0

    def test_posture_score_defaults(self):
        score = PostureScore(service="api")
        assert score.id
        assert score.overall_score == 0.0
        assert score.grade == PostureGrade.F
        assert score.category_scores == {}
        assert score.checks_passed == 0
        assert score.checks_total == 0
        assert score.scored_at > 0


# ---------------------------------------------------------------------------
# record_check
# ---------------------------------------------------------------------------


class TestRecordCheck:
    def test_basic_record(self):
        s = _scorer()
        check = s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="tls_enabled",
            passed=True,
        )
        assert check.service == "api"
        assert check.category == PostureCategory.ENCRYPTION
        assert check.check_name == "tls_enabled"
        assert check.passed is True

    def test_all_fields(self):
        s = _scorer()
        check = s.record_check(
            service="db",
            category=PostureCategory.ACCESS_CONTROL,
            check_name="mfa_enabled",
            passed=False,
            weight=2.0,
            details="MFA not configured",
        )
        assert check.weight == 2.0
        assert check.details == "MFA not configured"
        assert check.passed is False

    def test_trims_to_max(self):
        s = _scorer(max_checks=3)
        for i in range(5):
            s.record_check(
                service="api",
                category=PostureCategory.ENCRYPTION,
                check_name=f"check_{i}",
                passed=True,
            )
        assert len(s._checks) == 3

    def test_unique_ids(self):
        s = _scorer()
        c1 = s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="a",
            passed=True,
        )
        c2 = s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="b",
            passed=True,
        )
        assert c1.id != c2.id


# ---------------------------------------------------------------------------
# calculate_score
# ---------------------------------------------------------------------------


class TestCalculateScore:
    def test_all_passing_checks_grade_a(self):
        s = _scorer()
        for cat in PostureCategory:
            s.record_check(service="api", category=cat, check_name="ok", passed=True)
        score = s.calculate_score("api")
        assert score.overall_score == 100.0
        assert score.grade == PostureGrade.A

    def test_mixed_results_lower_grade(self):
        s = _scorer()
        # 3 passing, 7 failing in one category => 30% => grade F
        for i in range(3):
            s.record_check(
                service="web",
                category=PostureCategory.ENCRYPTION,
                check_name=f"pass_{i}",
                passed=True,
            )
        for i in range(7):
            s.record_check(
                service="web",
                category=PostureCategory.ENCRYPTION,
                check_name=f"fail_{i}",
                passed=False,
            )
        score = s.calculate_score("web")
        assert score.overall_score == 30.0
        assert score.grade == PostureGrade.F

    def test_no_checks_returns_zero_score(self):
        s = _scorer()
        score = s.calculate_score("empty")
        assert score.overall_score == 0.0
        assert score.grade == PostureGrade.F
        assert score.checks_total == 0

    def test_score_by_service_isolation(self):
        s = _scorer()
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="x",
            passed=True,
        )
        s.record_check(
            service="db",
            category=PostureCategory.ENCRYPTION,
            check_name="x",
            passed=False,
        )
        api_score = s.calculate_score("api")
        db_score = s.calculate_score("db")
        assert api_score.overall_score == 100.0
        assert db_score.overall_score == 0.0


# ---------------------------------------------------------------------------
# get_score
# ---------------------------------------------------------------------------


class TestGetScore:
    def test_found(self):
        s = _scorer()
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="x",
            passed=True,
        )
        s.calculate_score("api")
        result = s.get_score("api")
        assert result is not None
        assert result.service == "api"

    def test_not_found(self):
        s = _scorer()
        assert s.get_score("nonexistent") is None


# ---------------------------------------------------------------------------
# list_scores
# ---------------------------------------------------------------------------


class TestListScores:
    def test_all(self):
        s = _scorer()
        for svc in ("api", "db"):
            s.record_check(
                service=svc,
                category=PostureCategory.ENCRYPTION,
                check_name="x",
                passed=True,
            )
            s.calculate_score(svc)
        assert len(s.list_scores()) == 2

    def test_by_grade(self):
        s = _scorer()
        s.record_check(
            service="good",
            category=PostureCategory.ENCRYPTION,
            check_name="x",
            passed=True,
        )
        s.calculate_score("good")
        s.record_check(
            service="bad",
            category=PostureCategory.ENCRYPTION,
            check_name="x",
            passed=False,
        )
        s.calculate_score("bad")
        a_scores = s.list_scores(grade=PostureGrade.A)
        assert len(a_scores) == 1
        assert a_scores[0].service == "good"

    def test_latest_per_service(self):
        s = _scorer()
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="x",
            passed=False,
        )
        s.calculate_score("api")
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="y",
            passed=True,
        )
        s.calculate_score("api")
        scores = s.list_scores()
        assert len(scores) == 1  # only latest per service


# ---------------------------------------------------------------------------
# get_checks
# ---------------------------------------------------------------------------


class TestGetChecks:
    def test_all(self):
        s = _scorer()
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="a",
            passed=True,
        )
        s.record_check(
            service="db",
            category=PostureCategory.ACCESS_CONTROL,
            check_name="b",
            passed=False,
        )
        assert len(s.get_checks()) == 2

    def test_by_service(self):
        s = _scorer()
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="a",
            passed=True,
        )
        s.record_check(
            service="db",
            category=PostureCategory.ENCRYPTION,
            check_name="b",
            passed=True,
        )
        result = s.get_checks(service="api")
        assert len(result) == 1
        assert result[0].service == "api"

    def test_by_category(self):
        s = _scorer()
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="a",
            passed=True,
        )
        s.record_check(
            service="api",
            category=PostureCategory.ACCESS_CONTROL,
            check_name="b",
            passed=True,
        )
        result = s.get_checks(category=PostureCategory.ENCRYPTION)
        assert len(result) == 1
        assert result[0].category == PostureCategory.ENCRYPTION

    def test_by_passed(self):
        s = _scorer()
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="a",
            passed=True,
        )
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="b",
            passed=False,
        )
        result = s.get_checks(passed=False)
        assert len(result) == 1
        assert result[0].passed is False


# ---------------------------------------------------------------------------
# get_trend
# ---------------------------------------------------------------------------


class TestGetTrend:
    def test_shows_score_progression(self):
        s = _scorer()
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="a",
            passed=False,
        )
        s.calculate_score("api")
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="b",
            passed=True,
        )
        s.calculate_score("api")
        trend = s.get_trend("api")
        assert len(trend) == 2
        # Newest first
        assert trend[0].scored_at >= trend[1].scored_at

    def test_respects_limit(self):
        s = _scorer()
        for i in range(5):
            s.record_check(
                service="api",
                category=PostureCategory.ENCRYPTION,
                check_name=f"c_{i}",
                passed=True,
            )
            s.calculate_score("api")
        trend = s.get_trend("api", limit=3)
        assert len(trend) == 3


# ---------------------------------------------------------------------------
# compare_services
# ---------------------------------------------------------------------------


class TestCompareServices:
    def test_two_services_compared(self):
        s = _scorer()
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="a",
            passed=True,
        )
        s.calculate_score("api")
        s.record_check(
            service="db",
            category=PostureCategory.ENCRYPTION,
            check_name="a",
            passed=False,
        )
        s.calculate_score("db")
        result = s.compare_services(["api", "db"])
        assert result["api"]["score"] == 100.0
        assert result["api"]["grade"] == PostureGrade.A
        assert result["db"]["score"] == 0.0

    def test_unknown_service_defaults(self):
        s = _scorer()
        result = s.compare_services(["unknown"])
        assert result["unknown"]["score"] == 0.0
        assert result["unknown"]["grade"] == PostureGrade.F


# ---------------------------------------------------------------------------
# get_worst_categories
# ---------------------------------------------------------------------------


class TestWorstCategories:
    def test_returns_sorted_by_score_ascending(self):
        s = _scorer()
        # Encryption: 100% pass
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="a",
            passed=True,
        )
        # Access control: 0% pass
        s.record_check(
            service="api",
            category=PostureCategory.ACCESS_CONTROL,
            check_name="b",
            passed=False,
        )
        worst = s.get_worst_categories("api")
        assert len(worst) == 2
        assert worst[0]["category"] == PostureCategory.ACCESS_CONTROL
        assert worst[0]["score"] == 0.0
        assert worst[1]["category"] == PostureCategory.ENCRYPTION
        assert worst[1]["score"] == 100.0

    def test_empty_service_returns_empty(self):
        s = _scorer()
        assert s.get_worst_categories("unknown") == []


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        s = _scorer()
        stats = s.get_stats()
        assert stats["total_checks"] == 0
        assert stats["total_scores"] == 0
        assert stats["services_scored"] == 0
        assert stats["avg_score"] == 0.0
        assert stats["grade_distribution"] == {}
        assert stats["category_avg_scores"] == {}

    def test_populated(self):
        s = _scorer()
        s.record_check(
            service="api",
            category=PostureCategory.ENCRYPTION,
            check_name="a",
            passed=True,
        )
        s.record_check(
            service="api",
            category=PostureCategory.ACCESS_CONTROL,
            check_name="b",
            passed=True,
        )
        s.calculate_score("api")
        stats = s.get_stats()
        assert stats["total_checks"] == 2
        assert stats["total_scores"] == 1
        assert stats["services_scored"] == 1
        assert stats["avg_score"] == 100.0
        assert PostureGrade.A in stats["grade_distribution"]
