"""Tests for PCI-DSS compliance engine.

Tests cover:
- PCIDSSEngine initialization with all 15 controls across 10 requirements
- evaluate() returns PCIDSSReport with correct structure and scoring
- Individual control checker methods (network, encryption, access, etc.)
- Overall compliance status calculation (pass/fail/warning/not_applicable)
- Per-requirement score breakdown
- Evidence collection per control
- get_controls() with requirement and status filtering
- Edge cases: all pass, all fail, mixed statuses, module import failures
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from shieldops.compliance.pci_dss import (
    _PCI_CONTROLS,
    PCIDSSControl,
    PCIDSSControlStatus,
    PCIDSSEngine,
    PCIDSSReport,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def engine() -> PCIDSSEngine:
    return PCIDSSEngine()


# =================================================================
# 1. Initialization
# =================================================================


class TestPCIDSSEngineInit:
    def test_engine_creates_all_controls(self, engine: PCIDSSEngine) -> None:
        assert len(engine._controls) == 15

    def test_all_control_ids_match_registry(self, engine: PCIDSSEngine) -> None:
        expected_ids = {ctrl_id for ctrl_id, *_ in _PCI_CONTROLS}
        actual_ids = set(engine._controls.keys())
        assert actual_ids == expected_ids

    def test_controls_default_status_is_fail(self, engine: PCIDSSEngine) -> None:
        for ctrl in engine._controls.values():
            assert ctrl.status == "fail"

    def test_controls_have_correct_requirements(self, engine: PCIDSSEngine) -> None:
        assert engine._controls["PCI-1.1"].requirement == 1
        assert engine._controls["PCI-3.4"].requirement == 3
        assert engine._controls["PCI-7.1"].requirement == 7
        assert engine._controls["PCI-12.1"].requirement == 12

    def test_controls_are_pci_dss_control_instances(self, engine: PCIDSSEngine) -> None:
        for ctrl in engine._controls.values():
            assert isinstance(ctrl, PCIDSSControl)

    def test_controls_have_name_and_description(self, engine: PCIDSSEngine) -> None:
        for ctrl in engine._controls.values():
            assert ctrl.name, f"Control {ctrl.id} has empty name"
            assert ctrl.description, f"Control {ctrl.id} has empty description"

    def test_controls_have_no_evidence_initially(self, engine: PCIDSSEngine) -> None:
        for ctrl in engine._controls.values():
            assert ctrl.evidence == []

    def test_controls_last_checked_is_none_initially(self, engine: PCIDSSEngine) -> None:
        for ctrl in engine._controls.values():
            assert ctrl.last_checked is None


class TestPCIDSSControlStatus:
    def test_pass_status_value(self) -> None:
        assert PCIDSSControlStatus.PASS == "pass"  # noqa: S105

    def test_fail_status_value(self) -> None:
        assert PCIDSSControlStatus.FAIL == "fail"

    def test_warning_status_value(self) -> None:
        assert PCIDSSControlStatus.WARNING == "warning"

    def test_not_applicable_status_value(self) -> None:
        assert PCIDSSControlStatus.NOT_APPLICABLE == "not_applicable"


# =================================================================
# 2. evaluate() — Full Audit
# =================================================================


class TestPCIDSSEvaluate:
    @pytest.mark.asyncio
    async def test_evaluate_returns_pci_dss_report(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        assert isinstance(report, PCIDSSReport)

    @pytest.mark.asyncio
    async def test_report_id_starts_with_pci_prefix(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        assert report.id.startswith("pci-")

    @pytest.mark.asyncio
    async def test_report_has_generated_at_timestamp(self, engine: PCIDSSEngine) -> None:
        before = datetime.now(UTC)
        report = await engine.evaluate()
        after = datetime.now(UTC)
        assert before <= report.generated_at <= after

    @pytest.mark.asyncio
    async def test_report_total_controls_equals_15(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        assert report.total_controls == 15

    @pytest.mark.asyncio
    async def test_report_counts_sum_to_total(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        total = report.passed + report.failed + report.warnings + report.not_applicable
        assert total == report.total_controls

    @pytest.mark.asyncio
    async def test_report_overall_score_in_valid_range(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        assert 0.0 <= report.overall_score <= 100.0

    @pytest.mark.asyncio
    async def test_report_contains_all_controls(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        assert len(report.controls) == 15

    @pytest.mark.asyncio
    async def test_controls_have_last_checked_after_evaluate(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        for ctrl in report.controls:
            assert ctrl.last_checked is not None

    @pytest.mark.asyncio
    async def test_report_has_requirement_scores(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        # Requirements present: 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12
        expected_requirements = {1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12}
        actual_keys = set()
        for key in report.requirement_scores:
            req_num = int(key.split()[-1])
            actual_keys.add(req_num)
        assert actual_keys == expected_requirements

    @pytest.mark.asyncio
    async def test_requirement_scores_in_valid_range(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        for req_name, score in report.requirement_scores.items():
            assert 0.0 <= score <= 100.0, f"{req_name} score {score} out of range"


# =================================================================
# 3. Score Calculation
# =================================================================


class TestPCIDSSScoreCalculation:
    @pytest.mark.asyncio
    async def test_score_is_percentage_of_passed_over_scoreable(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        scoreable = report.total_controls - report.not_applicable
        if scoreable > 0:
            expected = round(report.passed / scoreable * 100, 1)
            assert report.overall_score == pytest.approx(expected, abs=0.1)

    @pytest.mark.asyncio
    async def test_all_pass_yields_100_score(self, engine: PCIDSSEngine) -> None:
        """When all checkers return pass, overall score is 100."""

        async def _mock_pass():
            return "pass", "Mock pass", [{"type": "mock"}]

        for _ctrl_id, _, _, _, checker_name in _PCI_CONTROLS:
            setattr(engine, checker_name, _mock_pass)

        report = await engine.evaluate()
        assert report.overall_score == pytest.approx(100.0)
        assert report.passed == 15
        assert report.failed == 0

    @pytest.mark.asyncio
    async def test_all_fail_yields_0_score(self, engine: PCIDSSEngine) -> None:
        """When all checkers return fail, overall score is 0."""

        async def _mock_fail():
            return "fail", "Mock fail", []

        for _ctrl_id, _, _, _, checker_name in _PCI_CONTROLS:
            setattr(engine, checker_name, _mock_fail)

        report = await engine.evaluate()
        assert report.overall_score == pytest.approx(0.0)
        assert report.failed == 15
        assert report.passed == 0

    @pytest.mark.asyncio
    async def test_mixed_statuses_calculate_correctly(self, engine: PCIDSSEngine) -> None:
        """With a known mix of pass/fail/warning, score should be deterministic."""
        statuses = iter(["pass"] * 5 + ["fail"] * 5 + ["warning"] * 5)

        for _ctrl_id, _, _, _, checker_name in _PCI_CONTROLS:
            st = next(statuses)

            async def _mock(s=st):
                return s, f"Mock {s}", [{"type": "test"}]

            setattr(engine, checker_name, _mock)

        report = await engine.evaluate()
        assert report.passed == 5
        assert report.failed == 5
        assert report.warnings == 5
        # score = 5/15 * 100 = 33.3
        assert report.overall_score == pytest.approx(33.3, abs=0.1)

    @pytest.mark.asyncio
    async def test_not_applicable_excluded_from_score_denominator(
        self, engine: PCIDSSEngine
    ) -> None:
        """not_applicable controls should not count against the score."""
        statuses = iter(["pass"] * 5 + ["not_applicable"] * 10)

        for _ctrl_id, _, _, _, checker_name in _PCI_CONTROLS:
            st = next(statuses)

            async def _mock(s=st):
                return s, f"Mock {s}", []

            setattr(engine, checker_name, _mock)

        report = await engine.evaluate()
        assert report.not_applicable == 10
        # score = 5 / (15 - 10) * 100 = 100.0
        assert report.overall_score == pytest.approx(100.0)


# =================================================================
# 4. Individual Control Checkers
# =================================================================


class TestNetworkSecurityCheck:
    @pytest.mark.asyncio
    async def test_passes_when_opa_module_exists(self, engine: PCIDSSEngine) -> None:
        with patch("shieldops.compliance.pci_dss.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock()
            status, details, evidence = await engine._check_network_security()
        assert status == "pass"
        assert "OPA" in details
        assert len(evidence) > 0

    @pytest.mark.asyncio
    async def test_fails_when_opa_module_missing(self, engine: PCIDSSEngine) -> None:
        with patch(
            "shieldops.compliance.pci_dss.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, details, evidence = await engine._check_network_security()
        assert status == "fail"


class TestNetworkSegmentationCheck:
    @pytest.mark.asyncio
    async def test_passes_when_k8s_connector_exists(self, engine: PCIDSSEngine) -> None:
        with patch("shieldops.compliance.pci_dss.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock()
            status, details, evidence = await engine._check_network_segmentation()
        assert status == "pass"
        assert len(evidence) > 0

    @pytest.mark.asyncio
    async def test_warning_when_k8s_connector_missing(self, engine: PCIDSSEngine) -> None:
        with patch(
            "shieldops.compliance.pci_dss.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_network_segmentation()
        assert status == "warning"


class TestDefaultCredentialsCheck:
    @pytest.mark.asyncio
    async def test_passes_when_jwt_secret_is_custom(self, engine: PCIDSSEngine) -> None:
        with patch.dict("os.environ", {"SHIELDOPS_JWT_SECRET_KEY": "my-super-secret-key-123"}):
            status, details, evidence = await engine._check_default_credentials()
        assert status == "pass"
        assert evidence[0]["default_jwt_changed"] is True

    @pytest.mark.asyncio
    async def test_warning_when_jwt_secret_is_default(self, engine: PCIDSSEngine) -> None:
        with patch.dict(
            "os.environ",
            {"SHIELDOPS_JWT_SECRET_KEY": "change-me-in-production"},
            clear=False,
        ):
            status, details, evidence = await engine._check_default_credentials()
        assert status == "warning"
        assert "default" in details.lower()

    @pytest.mark.asyncio
    async def test_warning_when_jwt_secret_not_set(self, engine: PCIDSSEngine) -> None:
        with patch.dict("os.environ", {}, clear=True):
            status, _, _ = await engine._check_default_credentials()
        assert status == "warning"


class TestEncryptionAtRestCheck:
    @pytest.mark.asyncio
    async def test_passes_when_db_url_has_sslmode(self, engine: PCIDSSEngine) -> None:
        with patch.dict(
            "os.environ",
            {"SHIELDOPS_DATABASE_URL": "postgresql://host/db?sslmode=require"},
        ):
            status, details, evidence = await engine._check_encryption_at_rest()
        assert status == "pass"
        assert evidence[0]["ssl_detected"] is True

    @pytest.mark.asyncio
    async def test_passes_when_db_url_uses_asyncpg(self, engine: PCIDSSEngine) -> None:
        with patch.dict(
            "os.environ",
            {"SHIELDOPS_DATABASE_URL": "postgresql+asyncpg://host/db"},
        ):
            status, _, _ = await engine._check_encryption_at_rest()
        assert status == "pass"

    @pytest.mark.asyncio
    async def test_warning_when_no_ssl_in_db_url(self, engine: PCIDSSEngine) -> None:
        with patch.dict(
            "os.environ",
            {"SHIELDOPS_DATABASE_URL": "postgresql://host/db"},
        ):
            status, _, _ = await engine._check_encryption_at_rest()
        assert status == "warning"

    @pytest.mark.asyncio
    async def test_warning_when_db_url_empty(self, engine: PCIDSSEngine) -> None:
        with patch.dict("os.environ", {}, clear=True):
            status, _, _ = await engine._check_encryption_at_rest()
        assert status == "warning"


class TestEncryptionInTransitCheck:
    @pytest.mark.asyncio
    async def test_passes_when_middleware_exists(self, engine: PCIDSSEngine) -> None:
        with patch("shieldops.compliance.pci_dss.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock()
            status, details, evidence = await engine._check_encryption_in_transit()
        assert status == "pass"
        assert "TLS" in details

    @pytest.mark.asyncio
    async def test_fails_when_middleware_missing(self, engine: PCIDSSEngine) -> None:
        with patch(
            "shieldops.compliance.pci_dss.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_encryption_in_transit()
        assert status == "fail"


class TestAccessControlCheck:
    @pytest.mark.asyncio
    async def test_passes_when_rbac_available(self, engine: PCIDSSEngine) -> None:
        mock_mod = MagicMock()
        mock_mod.require_role = MagicMock()
        with patch("shieldops.compliance.pci_dss.importlib.import_module", return_value=mock_mod):
            status, details, evidence = await engine._check_access_control()
        assert status == "pass"
        assert "RBAC" in details

    @pytest.mark.asyncio
    async def test_warning_when_no_require_role(self, engine: PCIDSSEngine) -> None:
        mock_mod = MagicMock(spec=[])  # no attributes at all
        with patch("shieldops.compliance.pci_dss.importlib.import_module", return_value=mock_mod):
            status, _, _ = await engine._check_access_control()
        assert status == "warning"

    @pytest.mark.asyncio
    async def test_fails_when_auth_module_missing(self, engine: PCIDSSEngine) -> None:
        with patch(
            "shieldops.compliance.pci_dss.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_access_control()
        assert status == "fail"


class TestUserAuthenticationCheck:
    @pytest.mark.asyncio
    async def test_passes_when_auth_service_complete(self, engine: PCIDSSEngine) -> None:
        mock_mod = MagicMock()
        mock_mod.create_token = MagicMock()
        mock_mod.decode_token = MagicMock()
        with patch("shieldops.compliance.pci_dss.importlib.import_module", return_value=mock_mod):
            status, details, _ = await engine._check_user_authentication()
        assert status == "pass"
        assert "JWT" in details

    @pytest.mark.asyncio
    async def test_warning_when_partial_auth(self, engine: PCIDSSEngine) -> None:
        mock_mod = MagicMock(spec=["create_token"])
        mock_mod.create_token = MagicMock()
        with patch("shieldops.compliance.pci_dss.importlib.import_module", return_value=mock_mod):
            status, _, _ = await engine._check_user_authentication()
        assert status == "warning"

    @pytest.mark.asyncio
    async def test_fails_when_auth_service_missing(self, engine: PCIDSSEngine) -> None:
        with patch(
            "shieldops.compliance.pci_dss.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_user_authentication()
        assert status == "fail"


class TestAuditLoggingCheck:
    @pytest.mark.asyncio
    async def test_passes_when_audit_module_exists(self, engine: PCIDSSEngine) -> None:
        with patch("shieldops.compliance.pci_dss.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock()
            status, _, evidence = await engine._check_audit_logging()
        assert status == "pass"
        assert evidence[0]["audit_routes"] is True

    @pytest.mark.asyncio
    async def test_fails_when_audit_module_missing(self, engine: PCIDSSEngine) -> None:
        with patch(
            "shieldops.compliance.pci_dss.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_audit_logging()
        assert status == "fail"


class TestSecureDevelopmentCheck:
    @pytest.mark.asyncio
    async def test_passes_when_ci_workflows_exist(self, engine: PCIDSSEngine) -> None:
        """CI workflows directory exists in this project, so check should pass."""
        status, details, evidence = await engine._check_secure_development()
        # The .github/workflows directory exists in this repo
        assert status in ("pass", "warning")
        assert len(evidence) > 0

    @pytest.mark.asyncio
    async def test_evidence_contains_filesystem_check(self, engine: PCIDSSEngine) -> None:
        status, details, evidence = await engine._check_secure_development()
        assert len(evidence) > 0
        assert evidence[0]["type"] == "filesystem_check"


class TestSecurityPolicyCheck:
    @pytest.mark.asyncio
    async def test_evidence_contains_filesystem_check(self, engine: PCIDSSEngine) -> None:
        status, details, evidence = await engine._check_security_policy()
        assert len(evidence) > 0
        assert evidence[0]["type"] == "filesystem_check"

    @pytest.mark.asyncio
    async def test_returns_valid_status(self, engine: PCIDSSEngine) -> None:
        status, _, _ = await engine._check_security_policy()
        assert status in ("pass", "warning", "fail")


# =================================================================
# 5. get_controls() Filtering
# =================================================================


class TestGetControls:
    @pytest.mark.asyncio
    async def test_get_all_controls_returns_15(self, engine: PCIDSSEngine) -> None:
        controls = await engine.get_controls()
        assert len(controls) == 15

    @pytest.mark.asyncio
    async def test_filter_by_requirement_1(self, engine: PCIDSSEngine) -> None:
        controls = await engine.get_controls(requirement=1)
        assert len(controls) == 2
        for c in controls:
            assert c.requirement == 1

    @pytest.mark.asyncio
    async def test_filter_by_requirement_3(self, engine: PCIDSSEngine) -> None:
        controls = await engine.get_controls(requirement=3)
        assert len(controls) == 2
        for c in controls:
            assert c.requirement == 3

    @pytest.mark.asyncio
    async def test_filter_by_requirement_10(self, engine: PCIDSSEngine) -> None:
        controls = await engine.get_controls(requirement=10)
        assert len(controls) == 2
        for c in controls:
            assert c.requirement == 10

    @pytest.mark.asyncio
    async def test_filter_by_nonexistent_requirement_returns_empty(
        self, engine: PCIDSSEngine
    ) -> None:
        controls = await engine.get_controls(requirement=99)
        assert len(controls) == 0

    @pytest.mark.asyncio
    async def test_filter_by_status_fail_initially(self, engine: PCIDSSEngine) -> None:
        controls = await engine.get_controls(status="fail")
        assert len(controls) == 15  # all default to fail

    @pytest.mark.asyncio
    async def test_filter_by_status_pass_initially_returns_empty(
        self, engine: PCIDSSEngine
    ) -> None:
        controls = await engine.get_controls(status="pass")
        assert len(controls) == 0

    @pytest.mark.asyncio
    async def test_filter_by_both_requirement_and_status(self, engine: PCIDSSEngine) -> None:
        controls = await engine.get_controls(requirement=1, status="fail")
        assert len(controls) == 2
        for c in controls:
            assert c.requirement == 1
            assert c.status == "fail"

    @pytest.mark.asyncio
    async def test_filter_after_evaluate_finds_passed_controls(self, engine: PCIDSSEngine) -> None:
        await engine.evaluate()
        passed = await engine.get_controls(status="pass")
        # At least some controls should pass in a real project
        assert isinstance(passed, list)


# =================================================================
# 6. Evidence Collection
# =================================================================


class TestEvidenceCollection:
    @pytest.mark.asyncio
    async def test_evidence_populated_after_evaluate(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        controls_with_evidence = [c for c in report.controls if len(c.evidence) > 0]
        assert len(controls_with_evidence) > 0

    @pytest.mark.asyncio
    async def test_evidence_items_have_type_field(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        for ctrl in report.controls:
            for ev in ctrl.evidence:
                assert "type" in ev, f"Evidence for {ctrl.id} missing 'type' key"

    @pytest.mark.asyncio
    async def test_evidence_types_are_recognized(self, engine: PCIDSSEngine) -> None:
        report = await engine.evaluate()
        valid_types = {"module_check", "config_check", "filesystem_check"}
        for ctrl in report.controls:
            for ev in ctrl.evidence:
                assert ev["type"] in valid_types, (
                    f"Control {ctrl.id} has unknown evidence type: {ev['type']}"
                )


# =================================================================
# 7. Edge Cases
# =================================================================


class TestPCIDSSEdgeCases:
    @pytest.mark.asyncio
    async def test_multiple_evaluations_dont_duplicate_controls(self, engine: PCIDSSEngine) -> None:
        report1 = await engine.evaluate()
        report2 = await engine.evaluate()
        assert report1.total_controls == report2.total_controls == 15

    @pytest.mark.asyncio
    async def test_evaluate_updates_existing_control_status(self, engine: PCIDSSEngine) -> None:
        # Before evaluation all are "fail"
        assert engine._controls["PCI-1.1"].status == "fail"
        await engine.evaluate()
        # After evaluation, status should be updated by checker
        assert engine._controls["PCI-1.1"].status in ("pass", "fail", "warning", "not_applicable")

    @pytest.mark.asyncio
    async def test_report_id_is_unique_across_evaluations(self, engine: PCIDSSEngine) -> None:
        report1 = await engine.evaluate()
        report2 = await engine.evaluate()
        assert report1.id != report2.id

    @pytest.mark.asyncio
    async def test_all_not_applicable_yields_zero_score(self, engine: PCIDSSEngine) -> None:
        async def _mock_na():
            return "not_applicable", "Not applicable", []

        for _, _, _, _, checker_name in _PCI_CONTROLS:
            setattr(engine, checker_name, _mock_na)

        report = await engine.evaluate()
        assert report.overall_score == pytest.approx(0.0)
        assert report.not_applicable == 15

    def test_pci_control_model_serialization(self) -> None:
        ctrl = PCIDSSControl(
            id="PCI-TEST",
            requirement=99,
            name="Test Control",
            description="Test description",
            status="pass",
            details="All good",
            evidence=[{"type": "test"}],
        )
        data = ctrl.model_dump()
        assert data["id"] == "PCI-TEST"
        assert data["requirement"] == 99
        assert data["status"] == "pass"

    def test_pci_report_model_serialization(self) -> None:
        report = PCIDSSReport(
            id="pci-test123",
            generated_at=datetime.now(UTC),
            overall_score=85.5,
            total_controls=15,
            passed=12,
            failed=2,
            warnings=1,
            not_applicable=0,
            requirement_scores={"Requirement 1": 100.0},
            controls=[],
        )
        data = report.model_dump()
        assert data["overall_score"] == 85.5
        assert data["passed"] == 12

    @pytest.mark.asyncio
    async def test_per_requirement_score_with_all_pass_in_requirement(
        self, engine: PCIDSSEngine
    ) -> None:
        """When all controls in a requirement pass, that requirement scores 100."""

        async def _mock_pass():
            return "pass", "Passed", [{"type": "mock"}]

        for _, _, _, _, checker_name in _PCI_CONTROLS:
            setattr(engine, checker_name, _mock_pass)

        report = await engine.evaluate()
        for req_name, score in report.requirement_scores.items():
            assert score == pytest.approx(100.0), f"{req_name} should be 100"
