"""Tests for AI playbook generation (F9)."""

from unittest.mock import AsyncMock, patch

import pytest

from shieldops.playbooks.ai_generator import (
    AIPlaybookGenerator,
    GeneratedPlaybook,
    GeneratedStep,
)


class TestGeneratedStepModel:
    def test_defaults(self):
        step = GeneratedStep(order=1, description="Test")
        assert step.order == 1
        assert step.description == "Test"
        assert step.command == ""
        assert step.risk_level == "low"
        assert step.rollback_command == ""
        assert step.validation == ""

    def test_full(self):
        step = GeneratedStep(
            order=2,
            description="Restart service",
            command="systemctl restart nginx",
            risk_level="medium",
            rollback_command="systemctl stop nginx",
            validation="systemctl status nginx",
        )
        assert step.command == "systemctl restart nginx"
        assert step.risk_level == "medium"


class TestGeneratedPlaybookModel:
    def test_defaults(self):
        pb = GeneratedPlaybook(name="Test", description="A test playbook")
        assert pb.name == "Test"
        assert pb.severity == "medium"
        assert pb.steps == []
        assert pb.estimated_duration_minutes == 15
        assert pb.requires_approval is False
        assert pb.tags == []
        assert pb.confidence == 0.0

    def test_full(self):
        pb = GeneratedPlaybook(
            name="Fix CVE",
            description="Remediate critical CVE",
            severity="critical",
            target_type="container",
            steps=[GeneratedStep(order=1, description="Patch")],
            estimated_duration_minutes=60,
            requires_approval=True,
            tags=["critical", "container"],
            confidence=0.9,
        )
        assert len(pb.steps) == 1
        assert pb.requires_approval is True
        assert pb.confidence == 0.9


class TestAIPlaybookGenerator:
    @pytest.fixture
    def generator(self):
        return AIPlaybookGenerator()

    @pytest.fixture
    def generator_with_repo(self):
        repo = AsyncMock()
        repo.list_remediations.return_value = [
            {"action_type": "restart", "description": "Restarted nginx"},
        ]
        return AIPlaybookGenerator(repository=repo)

    @pytest.fixture
    def vulnerability(self):
        return {
            "cve_id": "CVE-2024-1234",
            "severity": "high",
            "title": "OpenSSL buffer overflow",
            "description": "A buffer overflow in OpenSSL allows remote code execution.",
            "package_name": "openssl",
            "affected_resource": "web-server-1",
            "fixed_version": "3.1.5",
            "scanner_type": "trivy",
        }

    @pytest.mark.asyncio
    async def test_generate_success(self, generator, vulnerability):
        mock_playbook = GeneratedPlaybook(
            name="Fix CVE-2024-1234",
            description="Update OpenSSL",
            severity="high",
            steps=[
                GeneratedStep(order=1, description="Update openssl", command="apt upgrade openssl"),
            ],
            confidence=0.85,
        )

        with patch(
            "shieldops.utils.llm.llm_structured",
            return_value=mock_playbook,
        ):
            result = await generator.generate(vulnerability)

        assert result.name == "Fix CVE-2024-1234"
        assert len(result.steps) == 1
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_generate_dict_result(self, generator, vulnerability):
        mock_dict = {
            "name": "Fix It",
            "description": "Fix the vuln",
            "severity": "high",
            "steps": [{"order": 1, "description": "Do the thing"}],
            "confidence": 0.7,
        }

        with patch(
            "shieldops.utils.llm.llm_structured",
            return_value=mock_dict,
        ):
            result = await generator.generate(vulnerability)

        assert result.name == "Fix It"
        assert result.confidence == 0.7

    @pytest.mark.asyncio
    async def test_generate_fallback_on_error(self, generator, vulnerability):
        with patch(
            "shieldops.utils.llm.llm_structured",
            side_effect=Exception("LLM timeout"),
        ):
            result = await generator.generate(vulnerability)

        assert "CVE-2024-1234" in result.name
        assert result.confidence == 0.3
        assert len(result.steps) == 4
        assert "fallback" in result.tags

    @pytest.mark.asyncio
    async def test_generate_fallback_requires_approval_critical(self, generator):
        vuln = {"cve_id": "CVE-2024-0001", "severity": "critical"}

        with patch(
            "shieldops.utils.llm.llm_structured",
            side_effect=Exception("fail"),
        ):
            result = await generator.generate(vuln)

        assert result.requires_approval is True
        assert result.severity == "critical"

    @pytest.mark.asyncio
    async def test_generate_fallback_no_approval_low(self, generator):
        vuln = {"cve_id": "CVE-2024-0001", "severity": "low"}

        with patch(
            "shieldops.utils.llm.llm_structured",
            side_effect=Exception("fail"),
        ):
            result = await generator.generate(vuln)

        assert result.requires_approval is False

    @pytest.mark.asyncio
    async def test_generate_with_context(self, generator, vulnerability):
        mock_playbook = GeneratedPlaybook(
            name="Fix CVE",
            description="Fix it",
            steps=[GeneratedStep(order=1, description="Step 1")],
            confidence=0.8,
        )

        with patch(
            "shieldops.utils.llm.llm_structured",
            return_value=mock_playbook,
        ):
            result = await generator.generate(
                vulnerability,
                context={"environment": "production", "team": "platform"},
            )

        assert result.name == "Fix CVE"

    @pytest.mark.asyncio
    async def test_generate_with_historical_context(self, generator_with_repo, vulnerability):
        mock_playbook = GeneratedPlaybook(
            name="Fix",
            description="Fix with history",
            steps=[GeneratedStep(order=1, description="Step")],
            confidence=0.9,
        )

        with patch(
            "shieldops.utils.llm.llm_structured",
            return_value=mock_playbook,
        ):
            result = await generator_with_repo.generate(vulnerability)

        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_generate_batch(self, generator):
        vulns = [
            {"cve_id": "CVE-1", "severity": "high"},
            {"cve_id": "CVE-2", "severity": "medium"},
        ]

        mock_playbook = GeneratedPlaybook(
            name="Fix",
            description="Fix it",
            steps=[GeneratedStep(order=1, description="Step")],
            confidence=0.8,
        )

        with patch(
            "shieldops.utils.llm.llm_structured",
            return_value=mock_playbook,
        ):
            results = await generator.generate_batch(vulns)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_refine_success(self, generator):
        playbook = GeneratedPlaybook(
            name="Original",
            description="Original playbook",
            steps=[GeneratedStep(order=1, description="Old step")],
        )

        refined = GeneratedPlaybook(
            name="Refined",
            description="Refined playbook",
            steps=[
                GeneratedStep(order=1, description="Updated step"),
                GeneratedStep(order=2, description="New step"),
            ],
            confidence=0.9,
        )

        with patch(
            "shieldops.utils.llm.llm_structured",
            return_value=refined,
        ):
            result = await generator.refine(playbook, "Add a validation step")

        assert result.name == "Refined"
        assert len(result.steps) == 2

    @pytest.mark.asyncio
    async def test_refine_dict_result(self, generator):
        playbook = GeneratedPlaybook(name="Orig", description="Orig")

        with patch(
            "shieldops.utils.llm.llm_structured",
            return_value={
                "name": "Refined",
                "description": "Better",
                "steps": [],
                "confidence": 0.8,
            },
        ):
            result = await generator.refine(playbook, "improve it")

        assert result.name == "Refined"

    @pytest.mark.asyncio
    async def test_refine_error_returns_original(self, generator):
        playbook = GeneratedPlaybook(name="Original", description="Keep me")

        with patch(
            "shieldops.utils.llm.llm_structured",
            side_effect=Exception("LLM error"),
        ):
            result = await generator.refine(playbook, "feedback")

        assert result.name == "Original"

    @pytest.mark.asyncio
    async def test_historical_context_no_repo(self, generator):
        result = await generator._get_historical_context({"cve_id": "CVE-1"})
        assert result == []

    @pytest.mark.asyncio
    async def test_historical_context_error(self, generator_with_repo):
        generator_with_repo._repository.list_remediations.side_effect = Exception("DB error")
        result = await generator_with_repo._get_historical_context({"cve_id": "CVE-1"})
        assert result == []

    def test_build_system_prompt_no_history(self, generator):
        prompt = generator._build_system_prompt([])
        assert "SRE" in prompt
        assert "Historical" not in prompt

    def test_build_system_prompt_with_history(self, generator):
        history = [
            {"action_type": "restart", "description": "Restarted nginx after CVE fix"},
        ]
        prompt = generator._build_system_prompt(history)
        assert "Historical" in prompt
        assert "restart" in prompt

    def test_build_user_prompt(self, generator):
        vuln = {
            "cve_id": "CVE-2024-1234",
            "severity": "high",
            "title": "Test Vuln",
            "description": "A test vulnerability",
            "package_name": "openssl",
        }
        prompt = generator._build_user_prompt(vuln, None)
        assert "CVE-2024-1234" in prompt
        assert "high" in prompt
        assert "openssl" in prompt

    def test_build_user_prompt_with_context(self, generator):
        vuln = {"cve_id": "CVE-1"}
        context = {"environment": "production"}
        prompt = generator._build_user_prompt(vuln, context)
        assert "production" in prompt

    def test_fallback_playbook(self, generator):
        vuln = {"cve_id": "CVE-2024-1234", "severity": "high"}
        result = generator._fallback_playbook(vuln)
        assert result.name == "Remediation for CVE-2024-1234"
        assert result.severity == "high"
        assert len(result.steps) == 4
        assert result.confidence == 0.3
        assert result.requires_approval is True

    def test_fallback_playbook_finding_id(self, generator):
        vuln = {"finding_id": "F-1234", "severity": "low"}
        result = generator._fallback_playbook(vuln)
        assert "F-1234" in result.name
        assert result.requires_approval is False

    def test_fallback_playbook_unknown(self, generator):
        result = generator._fallback_playbook({})
        assert "unknown" in result.name
