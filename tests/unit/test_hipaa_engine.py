"""Tests for HIPAA compliance engine.

Tests cover:
- HIPAAEngine initialization with 14 controls across 3 safeguard categories
- evaluate() returns HIPAAReport with correct structure and scoring
- Administrative safeguard checkers (security mgmt, workforce, incidents, etc.)
- Physical safeguard checkers (facility access, workstation security)
- Technical safeguard checkers (access control, audit, encryption, etc.)
- Overall compliance status calculation
- Per-safeguard score breakdown
- Evidence collection per control
- get_controls() with safeguard and status filtering
- Edge cases: all pass, all fail, mixed, not_applicable scoring
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from shieldops.compliance.hipaa import (
    _HIPAA_CONTROLS,
    HIPAAControl,
    HIPAAEngine,
    HIPAAReport,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def engine() -> HIPAAEngine:
    return HIPAAEngine()


# =================================================================
# 1. Initialization
# =================================================================


class TestHIPAAEngineInit:
    def test_engine_creates_all_controls(self, engine: HIPAAEngine) -> None:
        assert len(engine._controls) == 14

    def test_all_control_ids_match_registry(self, engine: HIPAAEngine) -> None:
        expected_ids = {ctrl_id for ctrl_id, *_ in _HIPAA_CONTROLS}
        actual_ids = set(engine._controls.keys())
        assert actual_ids == expected_ids

    def test_controls_default_status_is_fail(self, engine: HIPAAEngine) -> None:
        for ctrl in engine._controls.values():
            assert ctrl.status == "fail"

    def test_administrative_controls_count(self, engine: HIPAAEngine) -> None:
        admin_controls = [c for c in engine._controls.values() if c.safeguard == "administrative"]
        assert len(admin_controls) == 7

    def test_physical_controls_count(self, engine: HIPAAEngine) -> None:
        physical_controls = [c for c in engine._controls.values() if c.safeguard == "physical"]
        assert len(physical_controls) == 2

    def test_technical_controls_count(self, engine: HIPAAEngine) -> None:
        technical_controls = [c for c in engine._controls.values() if c.safeguard == "technical"]
        assert len(technical_controls) == 5

    def test_controls_are_hipaa_control_instances(self, engine: HIPAAEngine) -> None:
        for ctrl in engine._controls.values():
            assert isinstance(ctrl, HIPAAControl)

    def test_controls_have_name_and_description(self, engine: HIPAAEngine) -> None:
        for ctrl in engine._controls.values():
            assert ctrl.name, f"Control {ctrl.id} has empty name"
            assert ctrl.description, f"Control {ctrl.id} has empty description"

    def test_controls_have_valid_safeguard_category(self, engine: HIPAAEngine) -> None:
        valid_safeguards = {"administrative", "physical", "technical"}
        for ctrl in engine._controls.values():
            assert ctrl.safeguard in valid_safeguards, (
                f"Control {ctrl.id} has invalid safeguard: {ctrl.safeguard}"
            )

    def test_controls_have_no_evidence_initially(self, engine: HIPAAEngine) -> None:
        for ctrl in engine._controls.values():
            assert ctrl.evidence == []

    def test_controls_last_checked_is_none_initially(self, engine: HIPAAEngine) -> None:
        for ctrl in engine._controls.values():
            assert ctrl.last_checked is None


# =================================================================
# 2. evaluate() — Full Audit
# =================================================================


class TestHIPAAEvaluate:
    @pytest.mark.asyncio
    async def test_evaluate_returns_hipaa_report(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        assert isinstance(report, HIPAAReport)

    @pytest.mark.asyncio
    async def test_report_id_starts_with_hipaa_prefix(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        assert report.id.startswith("hipaa-")

    @pytest.mark.asyncio
    async def test_report_has_generated_at_timestamp(self, engine: HIPAAEngine) -> None:
        before = datetime.now(UTC)
        report = await engine.evaluate()
        after = datetime.now(UTC)
        assert before <= report.generated_at <= after

    @pytest.mark.asyncio
    async def test_report_total_controls_equals_14(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        assert report.total_controls == 14

    @pytest.mark.asyncio
    async def test_report_counts_sum_to_total(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        total = report.passed + report.failed + report.warnings + report.not_applicable
        assert total == report.total_controls

    @pytest.mark.asyncio
    async def test_report_overall_score_in_valid_range(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        assert 0.0 <= report.overall_score <= 100.0

    @pytest.mark.asyncio
    async def test_report_contains_all_controls(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        assert len(report.controls) == 14

    @pytest.mark.asyncio
    async def test_controls_have_last_checked_after_evaluate(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        for ctrl in report.controls:
            assert ctrl.last_checked is not None

    @pytest.mark.asyncio
    async def test_report_has_all_three_safeguard_scores(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        assert "administrative" in report.safeguard_scores
        assert "physical" in report.safeguard_scores
        assert "technical" in report.safeguard_scores

    @pytest.mark.asyncio
    async def test_safeguard_scores_in_valid_range(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        for safeguard, score in report.safeguard_scores.items():
            assert 0.0 <= score <= 100.0, f"{safeguard} score {score} out of range"


# =================================================================
# 3. Score Calculation
# =================================================================


class TestHIPAAScoreCalculation:
    @pytest.mark.asyncio
    async def test_score_is_percentage_of_passed_over_scoreable(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        scoreable = report.total_controls - report.not_applicable
        if scoreable > 0:
            expected = round(report.passed / scoreable * 100, 1)
            assert report.overall_score == pytest.approx(expected, abs=0.1)

    @pytest.mark.asyncio
    async def test_all_pass_yields_100_score(self, engine: HIPAAEngine) -> None:
        async def _mock_pass():
            return "pass", "Mock pass", [{"type": "mock"}]

        for _, _, _, _, checker_name in _HIPAA_CONTROLS:
            setattr(engine, checker_name, _mock_pass)

        report = await engine.evaluate()
        assert report.overall_score == pytest.approx(100.0)
        assert report.passed == 14
        assert report.failed == 0

    @pytest.mark.asyncio
    async def test_all_fail_yields_0_score(self, engine: HIPAAEngine) -> None:
        async def _mock_fail():
            return "fail", "Mock fail", []

        for _, _, _, _, checker_name in _HIPAA_CONTROLS:
            setattr(engine, checker_name, _mock_fail)

        report = await engine.evaluate()
        assert report.overall_score == pytest.approx(0.0)
        assert report.failed == 14
        assert report.passed == 0

    @pytest.mark.asyncio
    async def test_mixed_statuses_calculate_correctly(self, engine: HIPAAEngine) -> None:
        statuses = iter(["pass"] * 4 + ["fail"] * 4 + ["warning"] * 4 + ["not_applicable"] * 2)

        for _, _, _, _, checker_name in _HIPAA_CONTROLS:
            st = next(statuses)

            async def _mock(s=st):
                return s, f"Mock {s}", [{"type": "test"}]

            setattr(engine, checker_name, _mock)

        report = await engine.evaluate()
        assert report.passed == 4
        assert report.failed == 4
        assert report.warnings == 4
        assert report.not_applicable == 2
        # score = 4 / (14 - 2) * 100 = 33.3
        assert report.overall_score == pytest.approx(33.3, abs=0.1)

    @pytest.mark.asyncio
    async def test_not_applicable_excluded_from_score_denominator(
        self, engine: HIPAAEngine
    ) -> None:
        statuses = iter(["pass"] * 3 + ["not_applicable"] * 11)

        for _, _, _, _, checker_name in _HIPAA_CONTROLS:
            st = next(statuses)

            async def _mock(s=st):
                return s, f"Mock {s}", []

            setattr(engine, checker_name, _mock)

        report = await engine.evaluate()
        assert report.not_applicable == 11
        # score = 3 / (14 - 11) * 100 = 100.0
        assert report.overall_score == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_all_not_applicable_yields_zero_score(self, engine: HIPAAEngine) -> None:
        async def _mock_na():
            return "not_applicable", "Not applicable", []

        for _, _, _, _, checker_name in _HIPAA_CONTROLS:
            setattr(engine, checker_name, _mock_na)

        report = await engine.evaluate()
        assert report.overall_score == pytest.approx(0.0)
        assert report.not_applicable == 14


# =================================================================
# 4. Administrative Safeguard Checkers
# =================================================================


class TestSecurityManagementCheck:
    @pytest.mark.asyncio
    async def test_passes_when_both_modules_exist(self, engine: HIPAAEngine) -> None:
        with patch("shieldops.compliance.hipaa.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock()
            status, details, evidence = await engine._check_security_mgmt()
        assert status == "pass"
        assert "OPA" in details
        assert evidence[0]["opa"] is True
        assert evidence[0]["security_agent"] is True

    @pytest.mark.asyncio
    async def test_fails_when_modules_missing(self, engine: HIPAAEngine) -> None:
        with patch(
            "shieldops.compliance.hipaa.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_security_mgmt()
        assert status == "fail"


class TestSecurityOfficerCheck:
    @pytest.mark.asyncio
    async def test_passes_when_user_role_defined(self, engine: HIPAAEngine) -> None:
        mock_mod = MagicMock()
        mock_mod.UserRole = MagicMock()
        with patch("shieldops.compliance.hipaa.importlib.import_module", return_value=mock_mod):
            status, details, evidence = await engine._check_security_officer()
        assert status == "pass"
        assert evidence[0]["roles_defined"] is True

    @pytest.mark.asyncio
    async def test_warning_when_no_user_role(self, engine: HIPAAEngine) -> None:
        mock_mod = MagicMock(spec=[])
        with patch("shieldops.compliance.hipaa.importlib.import_module", return_value=mock_mod):
            status, _, _ = await engine._check_security_officer()
        assert status == "warning"

    @pytest.mark.asyncio
    async def test_warning_when_module_missing(self, engine: HIPAAEngine) -> None:
        with patch(
            "shieldops.compliance.hipaa.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_security_officer()
        assert status == "warning"


class TestWorkforceSecurityCheck:
    @pytest.mark.asyncio
    async def test_passes_when_rbac_available(self, engine: HIPAAEngine) -> None:
        mock_mod = MagicMock()
        mock_mod.require_role = MagicMock()
        with patch("shieldops.compliance.hipaa.importlib.import_module", return_value=mock_mod):
            status, details, _ = await engine._check_workforce_security()
        assert status == "pass"
        assert "RBAC" in details

    @pytest.mark.asyncio
    async def test_warning_when_no_require_role(self, engine: HIPAAEngine) -> None:
        mock_mod = MagicMock(spec=[])
        with patch("shieldops.compliance.hipaa.importlib.import_module", return_value=mock_mod):
            status, _, _ = await engine._check_workforce_security()
        assert status == "warning"

    @pytest.mark.asyncio
    async def test_fails_when_auth_module_missing(self, engine: HIPAAEngine) -> None:
        with patch(
            "shieldops.compliance.hipaa.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_workforce_security()
        assert status == "fail"


class TestAccessManagementCheck:
    @pytest.mark.asyncio
    async def test_passes_when_permissions_module_exists(self, engine: HIPAAEngine) -> None:
        with patch("shieldops.compliance.hipaa.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock()
            status, details, evidence = await engine._check_access_management()
        assert status == "pass"
        assert "permissions" in details.lower()

    @pytest.mark.asyncio
    async def test_warning_when_permissions_missing(self, engine: HIPAAEngine) -> None:
        with patch(
            "shieldops.compliance.hipaa.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_access_management()
        assert status == "warning"


class TestSecurityTrainingCheck:
    @pytest.mark.asyncio
    async def test_always_returns_warning(self, engine: HIPAAEngine) -> None:
        """Security training is an organizational requirement, always returns warning."""
        status, details, evidence = await engine._check_security_training()
        assert status == "warning"
        assert "organizational" in details.lower()
        assert evidence[0]["type"] == "policy_check"
        assert evidence[0]["training_program"] == "organizational"


class TestIncidentProceduresCheck:
    @pytest.mark.asyncio
    async def test_passes_when_both_agents_exist(self, engine: HIPAAEngine) -> None:
        with patch("shieldops.compliance.hipaa.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock()
            status, details, evidence = await engine._check_incident_procedures()
        assert status == "pass"
        assert "incident" in details.lower()
        assert evidence[0]["incident_agents"] is True

    @pytest.mark.asyncio
    async def test_fails_when_agents_missing(self, engine: HIPAAEngine) -> None:
        with patch(
            "shieldops.compliance.hipaa.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_incident_procedures()
        assert status == "fail"


class TestContingencyPlanCheck:
    @pytest.mark.asyncio
    async def test_passes_when_rollback_and_approval_exist(self, engine: HIPAAEngine) -> None:
        with patch("shieldops.compliance.hipaa.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock()
            status, details, evidence = await engine._check_contingency_plan()
        assert status == "pass"
        assert evidence[0]["rollback"] is True
        assert evidence[0]["approval"] is True

    @pytest.mark.asyncio
    async def test_warning_when_modules_missing(self, engine: HIPAAEngine) -> None:
        with patch(
            "shieldops.compliance.hipaa.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_contingency_plan()
        assert status == "warning"


# =================================================================
# 5. Physical Safeguard Checkers
# =================================================================


class TestFacilityAccessCheck:
    @pytest.mark.asyncio
    async def test_always_passes_cloud_hosted(self, engine: HIPAAEngine) -> None:
        status, details, evidence = await engine._check_facility_access()
        assert status == "pass"
        assert "cloud" in details.lower()
        assert evidence[0]["type"] == "deployment_check"
        assert evidence[0]["cloud_hosted"] is True


class TestWorkstationSecurityCheck:
    @pytest.mark.asyncio
    async def test_always_passes_api_based(self, engine: HIPAAEngine) -> None:
        status, details, evidence = await engine._check_workstation_security()
        assert status == "pass"
        assert "api" in details.lower()
        assert evidence[0]["type"] == "deployment_check"
        assert evidence[0]["api_based"] is True


# =================================================================
# 6. Technical Safeguard Checkers
# =================================================================


class TestTechAccessControlCheck:
    @pytest.mark.asyncio
    async def test_passes_when_auth_service_has_create_token(self, engine: HIPAAEngine) -> None:
        mock_mod = MagicMock()
        mock_mod.create_token = MagicMock()
        with patch("shieldops.compliance.hipaa.importlib.import_module", return_value=mock_mod):
            status, details, evidence = await engine._check_tech_access_control()
        assert status == "pass"
        assert "JWT" in details
        assert evidence[0]["jwt_auth"] is True

    @pytest.mark.asyncio
    async def test_warning_when_no_create_token(self, engine: HIPAAEngine) -> None:
        mock_mod = MagicMock(spec=[])
        with patch("shieldops.compliance.hipaa.importlib.import_module", return_value=mock_mod):
            status, _, _ = await engine._check_tech_access_control()
        assert status == "warning"

    @pytest.mark.asyncio
    async def test_fails_when_auth_module_missing(self, engine: HIPAAEngine) -> None:
        with patch(
            "shieldops.compliance.hipaa.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_tech_access_control()
        assert status == "fail"


class TestAuditControlsCheck:
    @pytest.mark.asyncio
    async def test_passes_when_audit_module_exists(self, engine: HIPAAEngine) -> None:
        with patch("shieldops.compliance.hipaa.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock()
            status, details, evidence = await engine._check_audit_controls()
        assert status == "pass"
        assert "audit" in details.lower()
        assert evidence[0]["audit_routes"] is True

    @pytest.mark.asyncio
    async def test_fails_when_audit_module_missing(self, engine: HIPAAEngine) -> None:
        with patch(
            "shieldops.compliance.hipaa.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_audit_controls()
        assert status == "fail"


class TestIntegrityControlsCheck:
    @pytest.mark.asyncio
    async def test_passes_when_policy_engine_exists(self, engine: HIPAAEngine) -> None:
        with patch("shieldops.compliance.hipaa.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock()
            status, details, evidence = await engine._check_integrity_controls()
        assert status == "pass"
        assert "OPA" in details
        assert evidence[0]["policy_engine"] is True

    @pytest.mark.asyncio
    async def test_fails_when_policy_engine_missing(self, engine: HIPAAEngine) -> None:
        with patch(
            "shieldops.compliance.hipaa.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_integrity_controls()
        assert status == "fail"


class TestTransmissionSecurityCheck:
    @pytest.mark.asyncio
    async def test_passes_when_middleware_exists(self, engine: HIPAAEngine) -> None:
        with patch("shieldops.compliance.hipaa.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock()
            status, details, evidence = await engine._check_transmission_security()
        assert status == "pass"
        assert "HSTS" in details or "TLS" in details
        assert evidence[0]["security_headers"] is True

    @pytest.mark.asyncio
    async def test_warning_when_middleware_missing(self, engine: HIPAAEngine) -> None:
        with patch(
            "shieldops.compliance.hipaa.importlib.import_module",
            side_effect=ImportError("not found"),
        ):
            status, _, _ = await engine._check_transmission_security()
        assert status == "warning"


class TestEncryptionCheck:
    @pytest.mark.asyncio
    async def test_passes_when_db_url_has_sslmode(self, engine: HIPAAEngine) -> None:
        with patch.dict(
            "os.environ",
            {"SHIELDOPS_DATABASE_URL": "postgresql://host/db?sslmode=require"},
        ):
            status, details, evidence = await engine._check_encryption()
        assert status == "pass"
        assert evidence[0]["db_encryption"] is True

    @pytest.mark.asyncio
    async def test_passes_when_db_url_has_asyncpg(self, engine: HIPAAEngine) -> None:
        with patch.dict(
            "os.environ",
            {"SHIELDOPS_DATABASE_URL": "postgresql+asyncpg://host/db"},
        ):
            status, _, evidence = await engine._check_encryption()
        assert status == "pass"
        assert evidence[0]["db_encryption"] is True

    @pytest.mark.asyncio
    async def test_warning_when_no_ssl_in_db_url(self, engine: HIPAAEngine) -> None:
        with patch.dict(
            "os.environ",
            {"SHIELDOPS_DATABASE_URL": "postgresql://host/db"},
        ):
            status, _, _ = await engine._check_encryption()
        assert status == "warning"

    @pytest.mark.asyncio
    async def test_warning_when_db_url_empty(self, engine: HIPAAEngine) -> None:
        with patch.dict("os.environ", {}, clear=True):
            status, _, _ = await engine._check_encryption()
        assert status == "warning"


# =================================================================
# 7. get_controls() Filtering
# =================================================================


class TestGetControls:
    @pytest.mark.asyncio
    async def test_get_all_controls_returns_14(self, engine: HIPAAEngine) -> None:
        controls = await engine.get_controls()
        assert len(controls) == 14

    @pytest.mark.asyncio
    async def test_filter_by_administrative_safeguard(self, engine: HIPAAEngine) -> None:
        controls = await engine.get_controls(safeguard="administrative")
        assert len(controls) == 7
        for c in controls:
            assert c.safeguard == "administrative"

    @pytest.mark.asyncio
    async def test_filter_by_physical_safeguard(self, engine: HIPAAEngine) -> None:
        controls = await engine.get_controls(safeguard="physical")
        assert len(controls) == 2
        for c in controls:
            assert c.safeguard == "physical"

    @pytest.mark.asyncio
    async def test_filter_by_technical_safeguard(self, engine: HIPAAEngine) -> None:
        controls = await engine.get_controls(safeguard="technical")
        assert len(controls) == 5
        for c in controls:
            assert c.safeguard == "technical"

    @pytest.mark.asyncio
    async def test_filter_by_nonexistent_safeguard_returns_empty(self, engine: HIPAAEngine) -> None:
        controls = await engine.get_controls(safeguard="nonexistent")
        assert len(controls) == 0

    @pytest.mark.asyncio
    async def test_filter_by_status_fail_initially(self, engine: HIPAAEngine) -> None:
        controls = await engine.get_controls(status="fail")
        assert len(controls) == 14  # all default to fail

    @pytest.mark.asyncio
    async def test_filter_by_status_pass_initially_returns_empty(self, engine: HIPAAEngine) -> None:
        controls = await engine.get_controls(status="pass")
        assert len(controls) == 0

    @pytest.mark.asyncio
    async def test_filter_by_both_safeguard_and_status(self, engine: HIPAAEngine) -> None:
        controls = await engine.get_controls(safeguard="administrative", status="fail")
        assert len(controls) == 7
        for c in controls:
            assert c.safeguard == "administrative"
            assert c.status == "fail"

    @pytest.mark.asyncio
    async def test_filter_after_evaluate_finds_passed_controls(self, engine: HIPAAEngine) -> None:
        await engine.evaluate()
        passed = await engine.get_controls(status="pass")
        assert isinstance(passed, list)


# =================================================================
# 8. Evidence Collection
# =================================================================


class TestEvidenceCollection:
    @pytest.mark.asyncio
    async def test_evidence_populated_after_evaluate(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        controls_with_evidence = [c for c in report.controls if len(c.evidence) > 0]
        assert len(controls_with_evidence) > 0

    @pytest.mark.asyncio
    async def test_evidence_items_have_type_field(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        for ctrl in report.controls:
            for ev in ctrl.evidence:
                assert "type" in ev, f"Evidence for {ctrl.id} missing 'type' key"

    @pytest.mark.asyncio
    async def test_evidence_types_are_recognized(self, engine: HIPAAEngine) -> None:
        report = await engine.evaluate()
        valid_types = {"module_check", "config_check", "policy_check", "deployment_check"}
        for ctrl in report.controls:
            for ev in ctrl.evidence:
                assert ev["type"] in valid_types, (
                    f"Control {ctrl.id} has unknown evidence type: {ev['type']}"
                )

    @pytest.mark.asyncio
    async def test_physical_controls_have_deployment_check_evidence(
        self, engine: HIPAAEngine
    ) -> None:
        report = await engine.evaluate()
        physical_controls = [c for c in report.controls if c.safeguard == "physical"]
        for ctrl in physical_controls:
            assert len(ctrl.evidence) > 0
            assert ctrl.evidence[0]["type"] == "deployment_check"


# =================================================================
# 9. Safeguard Score Breakdown
# =================================================================


class TestSafeguardScores:
    @pytest.mark.asyncio
    async def test_physical_safeguards_always_pass(self, engine: HIPAAEngine) -> None:
        """Physical safeguards are cloud-hosted checks and should always pass."""
        report = await engine.evaluate()
        assert report.safeguard_scores["physical"] == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_all_pass_yields_100_for_each_safeguard(self, engine: HIPAAEngine) -> None:
        async def _mock_pass():
            return "pass", "Mock pass", [{"type": "mock"}]

        for _, _, _, _, checker_name in _HIPAA_CONTROLS:
            setattr(engine, checker_name, _mock_pass)

        report = await engine.evaluate()
        for safeguard, score in report.safeguard_scores.items():
            assert score == pytest.approx(100.0), f"{safeguard} should be 100"

    @pytest.mark.asyncio
    async def test_all_fail_yields_0_for_each_safeguard(self, engine: HIPAAEngine) -> None:
        async def _mock_fail():
            return "fail", "Mock fail", []

        for _, _, _, _, checker_name in _HIPAA_CONTROLS:
            setattr(engine, checker_name, _mock_fail)

        report = await engine.evaluate()
        for safeguard, score in report.safeguard_scores.items():
            assert score == pytest.approx(0.0), f"{safeguard} should be 0"


# =================================================================
# 10. Edge Cases
# =================================================================


class TestHIPAAEdgeCases:
    @pytest.mark.asyncio
    async def test_multiple_evaluations_dont_duplicate_controls(self, engine: HIPAAEngine) -> None:
        report1 = await engine.evaluate()
        report2 = await engine.evaluate()
        assert report1.total_controls == report2.total_controls == 14

    @pytest.mark.asyncio
    async def test_evaluate_updates_existing_control_status(self, engine: HIPAAEngine) -> None:
        assert engine._controls["HIPAA-A-1"].status == "fail"
        await engine.evaluate()
        assert engine._controls["HIPAA-A-1"].status in ("pass", "fail", "warning", "not_applicable")

    @pytest.mark.asyncio
    async def test_report_id_is_unique_across_evaluations(self, engine: HIPAAEngine) -> None:
        report1 = await engine.evaluate()
        report2 = await engine.evaluate()
        assert report1.id != report2.id

    def test_hipaa_control_model_serialization(self) -> None:
        ctrl = HIPAAControl(
            id="HIPAA-TEST",
            safeguard="technical",
            name="Test Control",
            description="Test description",
            status="pass",
            details="All good",
            evidence=[{"type": "test"}],
        )
        data = ctrl.model_dump()
        assert data["id"] == "HIPAA-TEST"
        assert data["safeguard"] == "technical"
        assert data["status"] == "pass"

    def test_hipaa_report_model_serialization(self) -> None:
        report = HIPAAReport(
            id="hipaa-test123",
            generated_at=datetime.now(UTC),
            overall_score=92.0,
            total_controls=14,
            passed=12,
            failed=1,
            warnings=1,
            not_applicable=0,
            safeguard_scores={
                "administrative": 85.7,
                "physical": 100.0,
                "technical": 80.0,
            },
            controls=[],
        )
        data = report.model_dump()
        assert data["overall_score"] == 92.0
        assert data["passed"] == 12
        assert len(data["safeguard_scores"]) == 3

    @pytest.mark.asyncio
    async def test_security_training_always_produces_evidence(self, engine: HIPAAEngine) -> None:
        """Security training check produces evidence even without module checks."""
        report = await engine.evaluate()
        training_ctrl = next(c for c in report.controls if c.id == "HIPAA-A-5")
        assert len(training_ctrl.evidence) > 0
        assert training_ctrl.evidence[0]["training_program"] == "organizational"

    @pytest.mark.asyncio
    async def test_evaluate_with_partial_import_failures(self, engine: HIPAAEngine) -> None:
        """Engine should handle some checkers passing and some failing gracefully."""
        call_count = 0

        original_import = __import__("importlib").import_module

        def _selective_import(name, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if "opa" in name:
                raise ImportError("Simulated OPA failure")
            return original_import(name, *args, **kwargs)

        with patch(
            "shieldops.compliance.hipaa.importlib.import_module",
            side_effect=_selective_import,
        ):
            report = await engine.evaluate()

        # Engine should not crash; report should still be valid
        assert isinstance(report, HIPAAReport)
        assert report.total_controls == 14
        total = report.passed + report.failed + report.warnings + report.not_applicable
        assert total == 14
