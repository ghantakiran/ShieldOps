"""Tests for Security Posture Dashboard (F10)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from shieldops.vulnerability.posture_aggregator import (
    SEVERITY_WEIGHTS,
    PostureAggregator,
)


class TestPostureAggregator:
    @pytest.fixture
    def aggregator(self):
        return PostureAggregator()

    @pytest.fixture
    def aggregator_with_repo(self):
        repo = AsyncMock()
        repo.get_vulnerability_stats.return_value = {
            "total": 25,
            "by_severity": {"critical": 2, "high": 5, "medium": 10, "low": 8},
            "by_status": {"open": 15, "resolved": 10},
            "sla_breaches": 3,
            "last_scan": "2024-06-01T12:00:00Z",
        }
        repo.list_remediations.return_value = [
            {
                "created_at": (datetime.now(UTC) - timedelta(hours=48)).isoformat(),
                "completed_at": (datetime.now(UTC) - timedelta(hours=24)).isoformat(),
            },
            {
                "created_at": (datetime.now(UTC) - timedelta(hours=24)).isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
            },
        ]
        repo.list_vulnerabilities.return_value = [
            {"severity": "critical", "fixed_version": "1.2.3", "cvss_score": 9.5},
            {"severity": "high", "fixed_version": "", "cvss_score": 7.0},
            {"severity": "medium", "fixed_version": "2.0", "cvss_score": 5.0},
        ]
        return PostureAggregator(repository=repo)

    def test_severity_weights(self):
        assert SEVERITY_WEIGHTS["critical"] == 10.0
        assert SEVERITY_WEIGHTS["high"] == 5.0
        assert SEVERITY_WEIGHTS["medium"] == 2.0
        assert SEVERITY_WEIGHTS["low"] == 0.5

    def test_calculate_score_no_vulns(self, aggregator):
        score = aggregator._calculate_score({"total": 0, "by_severity": {}})
        assert score == 100.0

    def test_calculate_score_with_vulns(self, aggregator):
        stats = {
            "total": 10,
            "by_severity": {"critical": 1, "high": 2, "medium": 3, "low": 4},
        }
        # penalty = 1*10 + 2*5 + 3*2 + 4*0.5 = 10+10+6+2 = 28
        score = aggregator._calculate_score(stats)
        assert score == 72.0

    def test_calculate_score_capped_at_zero(self, aggregator):
        stats = {
            "total": 100,
            "by_severity": {"critical": 20},
        }
        # penalty = 20*10 = 200 → capped at 100 → score = 0
        score = aggregator._calculate_score(stats)
        assert score == 0.0

    def test_score_to_grade_a(self):
        assert PostureAggregator._score_to_grade(95) == "A"
        assert PostureAggregator._score_to_grade(90) == "A"

    def test_score_to_grade_b(self):
        assert PostureAggregator._score_to_grade(85) == "B"
        assert PostureAggregator._score_to_grade(80) == "B"

    def test_score_to_grade_c(self):
        assert PostureAggregator._score_to_grade(75) == "C"
        assert PostureAggregator._score_to_grade(70) == "C"

    def test_score_to_grade_d(self):
        assert PostureAggregator._score_to_grade(65) == "D"
        assert PostureAggregator._score_to_grade(60) == "D"

    def test_score_to_grade_f(self):
        assert PostureAggregator._score_to_grade(50) == "F"
        assert PostureAggregator._score_to_grade(0) == "F"

    @pytest.mark.asyncio
    async def test_get_overview_no_repo(self, aggregator):
        overview = await aggregator.get_overview()
        assert overview["overall_score"] == 100.0
        assert overview["grade"] == "A"
        assert overview["total_vulnerabilities"] == 0

    @pytest.mark.asyncio
    async def test_get_overview_with_repo(self, aggregator_with_repo):
        overview = await aggregator_with_repo.get_overview()
        assert overview["total_vulnerabilities"] == 25
        assert overview["by_severity"]["critical"] == 2
        assert overview["sla_breaches"] == 3
        assert overview["last_scan"] == "2024-06-01T12:00:00Z"
        assert overview["overall_score"] <= 100
        assert overview["overall_score"] >= 0
        assert "grade" in overview
        assert "timestamp" in overview

    @pytest.mark.asyncio
    async def test_get_overview_repo_error(self):
        repo = AsyncMock()
        repo.get_vulnerability_stats.side_effect = Exception("DB down")
        repo.list_remediations.return_value = []
        repo.list_vulnerabilities.return_value = []
        agg = PostureAggregator(repository=repo)
        overview = await agg.get_overview()
        assert overview["total_vulnerabilities"] == 0

    @pytest.mark.asyncio
    async def test_get_trends_no_repo(self, aggregator):
        trends = await aggregator.get_trends(days=7)
        assert trends["period_days"] == 7
        assert len(trends["data_points"]) == 7
        assert "timestamp" in trends

    @pytest.mark.asyncio
    async def test_get_trends_with_repo(self, aggregator_with_repo):
        trends = await aggregator_with_repo.get_trends(days=5)
        assert len(trends["data_points"]) == 5
        for point in trends["data_points"]:
            assert "date" in point
            assert "total" in point
            assert "critical" in point

    @pytest.mark.asyncio
    async def test_get_trends_repo_error(self):
        repo = AsyncMock()
        repo.get_vulnerability_stats.side_effect = Exception("timeout")
        agg = PostureAggregator(repository=repo)
        trends = await agg.get_trends(days=3)
        assert len(trends["data_points"]) == 3

    @pytest.mark.asyncio
    async def test_get_risk_matrix_no_repo(self, aggregator):
        matrix = await aggregator.get_risk_matrix()
        assert "matrix" in matrix
        assert "timestamp" in matrix
        for severity in ("critical", "high", "medium", "low"):
            assert severity in matrix["matrix"]
            for likelihood in ("exploitable", "likely", "possible", "unlikely"):
                assert matrix["matrix"][severity][likelihood] == 0

    @pytest.mark.asyncio
    async def test_get_risk_matrix_with_repo(self, aggregator_with_repo):
        matrix = await aggregator_with_repo.get_risk_matrix()
        # One vuln has cvss 9.5 → exploitable
        assert matrix["matrix"]["critical"]["exploitable"] >= 1
        # One has cvss 7.0 → likely
        assert matrix["matrix"]["high"]["likely"] >= 1

    @pytest.mark.asyncio
    async def test_get_risk_matrix_repo_error(self):
        repo = AsyncMock()
        repo.list_vulnerabilities.side_effect = Exception("fail")
        agg = PostureAggregator(repository=repo)
        matrix = await agg.get_risk_matrix()
        # All zeros on error
        assert matrix["matrix"]["critical"]["exploitable"] == 0

    @pytest.mark.asyncio
    async def test_get_risk_matrix_unknown_severity(self):
        repo = AsyncMock()
        repo.list_vulnerabilities.return_value = [
            {"severity": "unknown_sev", "cvss_score": 5.0},
        ]
        agg = PostureAggregator(repository=repo)
        matrix = await agg.get_risk_matrix()
        # Unknown severity falls back to "medium"; cvss < 7.0 and no fixed_version → "unlikely"
        assert matrix["matrix"]["medium"]["unlikely"] >= 1

    @pytest.mark.asyncio
    async def test_get_team_posture_no_repo(self, aggregator):
        result = await aggregator.get_team_posture("team-alpha")
        assert result["team_id"] == "team-alpha"
        assert result["total_vulnerabilities"] == 0
        assert result["score"] == 100.0
        assert result["grade"] == "A"

    @pytest.mark.asyncio
    async def test_get_team_posture_with_repo(self, aggregator_with_repo):
        result = await aggregator_with_repo.get_team_posture("team-alpha")
        assert result["team_id"] == "team-alpha"
        assert result["total_vulnerabilities"] == 3
        assert "score" in result
        assert "grade" in result

    @pytest.mark.asyncio
    async def test_get_team_posture_repo_error(self):
        repo = AsyncMock()
        repo.list_vulnerabilities.side_effect = Exception("fail")
        agg = PostureAggregator(repository=repo)
        result = await agg.get_team_posture("team-x")
        assert result["total_vulnerabilities"] == 0

    @pytest.mark.asyncio
    async def test_get_remediation_velocity_no_repo(self, aggregator):
        result = await aggregator.get_remediation_velocity()
        assert result["mttr_hours"] == 0.0
        assert result["mttr_days"] == 0

    @pytest.mark.asyncio
    async def test_get_remediation_velocity_with_repo(self, aggregator_with_repo):
        result = await aggregator_with_repo.get_remediation_velocity()
        assert result["mttr_hours"] > 0
        assert result["mttr_days"] > 0

    @pytest.mark.asyncio
    async def test_calculate_mttr_no_repo(self, aggregator):
        mttr = await aggregator._calculate_mttr()
        assert mttr == 0.0

    @pytest.mark.asyncio
    async def test_calculate_mttr_empty_remediations(self):
        repo = AsyncMock()
        repo.list_remediations.return_value = []
        agg = PostureAggregator(repository=repo)
        mttr = await agg._calculate_mttr()
        assert mttr == 0.0

    @pytest.mark.asyncio
    async def test_calculate_mttr_error(self):
        repo = AsyncMock()
        repo.list_remediations.side_effect = Exception("DB error")
        agg = PostureAggregator(repository=repo)
        mttr = await agg._calculate_mttr()
        assert mttr == 0.0

    @pytest.mark.asyncio
    async def test_calculate_mttr_string_timestamps(self):
        created = (datetime.now(UTC) - timedelta(hours=10)).isoformat()
        completed = datetime.now(UTC).isoformat()
        repo = AsyncMock()
        repo.list_remediations.return_value = [
            {"created_at": created, "completed_at": completed},
        ]
        agg = PostureAggregator(repository=repo)
        mttr = await agg._calculate_mttr()
        assert 9 <= mttr <= 11

    @pytest.mark.asyncio
    async def test_calculate_patch_coverage_no_repo(self, aggregator):
        coverage = await aggregator._calculate_patch_coverage()
        assert coverage == 0.0

    @pytest.mark.asyncio
    async def test_calculate_patch_coverage_empty_vulns(self):
        repo = AsyncMock()
        repo.list_vulnerabilities.return_value = []
        agg = PostureAggregator(repository=repo)
        coverage = await agg._calculate_patch_coverage()
        assert coverage == 100.0

    @pytest.mark.asyncio
    async def test_calculate_patch_coverage_with_vulns(self, aggregator_with_repo):
        coverage = await aggregator_with_repo._calculate_patch_coverage()
        # 2 out of 3 have fixed_version
        assert abs(coverage - 66.7) < 1.0

    @pytest.mark.asyncio
    async def test_calculate_patch_coverage_error(self):
        repo = AsyncMock()
        repo.list_vulnerabilities.side_effect = Exception("fail")
        agg = PostureAggregator(repository=repo)
        coverage = await agg._calculate_patch_coverage()
        assert coverage == 0.0
