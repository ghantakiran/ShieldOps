"""Tests for MITRE ATT&CK + EPSS threat intelligence (F8)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.integrations.threat_intel.epss import EPSSScorer
from shieldops.integrations.threat_intel.mitre_attack import (
    CAPEC_TO_ATTACK,
    CWE_TO_CAPEC,
    MITREAttackMapper,
)


class TestMITREAttackMapper:
    @pytest.fixture
    def mapper(self):
        return MITREAttackMapper()

    def test_map_cve_with_cwe(self, mapper):
        result = mapper.map_cve({"cve_id": "CVE-2024-1234", "cwes": ["CWE-89"]})
        assert result["cve_id"] == "CVE-2024-1234"
        assert len(result["cwes"]) == 1
        assert len(result["capec_ids"]) > 0
        assert len(result["attack_techniques"]) > 0
        assert result["technique_count"] > 0
        assert "Initial Access" in result["tactics"]

    def test_map_cve_with_cwe_id(self, mapper):
        result = mapper.map_cve({"cve_id": "CVE-2024-5678", "cwe_id": "CWE-79"})
        assert "CWE-79" in result["cwes"]
        assert len(result["attack_techniques"]) > 0

    def test_map_cve_with_description_inference(self, mapper):
        result = mapper.map_cve(
            {
                "cve_id": "CVE-2024-9999",
                "description": "SQL injection vulnerability in login form",
            }
        )
        assert "CWE-89" in result["cwes"]
        assert len(result["attack_techniques"]) > 0

    def test_map_cve_no_match(self, mapper):
        result = mapper.map_cve({"cve_id": "CVE-2024-0000", "description": "generic issue"})
        assert result["cwes"] == []
        assert result["attack_techniques"] == []
        assert "Manual threat assessment" in result["risk_context"]

    def test_map_cve_deduplicates_techniques(self, mapper):
        # CWE-89 maps to CAPEC-66 and CAPEC-108, both map to T1190
        result = mapper.map_cve({"cwes": ["CWE-89"]})
        tech_ids = [t["technique_id"] for t in result["attack_techniques"]]
        assert len(tech_ids) == len(set(tech_ids))

    def test_map_cve_dict_cwe(self, mapper):
        result = mapper.map_cve({"cwes": [{"id": "CWE-78"}]})
        assert "CWE-78" in result["cwes"]

    def test_map_cve_dict_cwe_id_key(self, mapper):
        result = mapper.map_cve({"cwes": [{"cwe_id": "CWE-22"}]})
        assert "CWE-22" in result["cwes"]

    def test_map_cve_numeric_cwe_normalized(self, mapper):
        result = mapper.map_cve({"cwes": ["89"]})
        assert "CWE-89" in result["cwes"]

    def test_map_cve_cwe_id_numeric_normalized(self, mapper):
        result = mapper.map_cve({"cwe_id": "79"})
        assert "CWE-79" in result["cwes"]

    def test_map_cve_both_cwes_and_cwe_id(self, mapper):
        result = mapper.map_cve({"cwes": ["CWE-89"], "cwe_id": "CWE-79"})
        assert "CWE-89" in result["cwes"]
        assert "CWE-79" in result["cwes"]

    def test_map_cve_cwe_id_no_duplicate(self, mapper):
        result = mapper.map_cve({"cwes": ["CWE-89"], "cwe_id": "CWE-89"})
        assert result["cwes"].count("CWE-89") == 1

    def test_get_technique_found(self, mapper):
        tech = mapper.get_technique("T1190")
        assert tech is not None
        assert tech["technique_id"] == "T1190"
        assert tech["name"] == "Exploit Public-Facing Application"

    def test_get_technique_not_found(self, mapper):
        assert mapper.get_technique("T9999") is None

    def test_get_tactic_summary(self, mapper):
        summary = mapper.get_tactic_summary(["Initial Access", "Execution"])
        assert "Initial Access" in summary
        assert "Execution" in summary
        assert "entry" in summary["Initial Access"].lower()

    def test_get_tactic_summary_unknown(self, mapper):
        summary = mapper.get_tactic_summary(["FakeTactic"])
        assert summary["FakeTactic"] == "Unknown tactic"

    def test_infer_cwes_xss(self, mapper):
        cwes = mapper._infer_cwes_from_description("cross-site scripting vulnerability")
        assert "CWE-79" in cwes

    def test_infer_cwes_xss_short(self, mapper):
        cwes = mapper._infer_cwes_from_description("An XSS flaw in the input handler")
        assert "CWE-79" in cwes

    def test_infer_cwes_command_injection(self, mapper):
        cwes = mapper._infer_cwes_from_description("command injection via user input")
        assert "CWE-78" in cwes

    def test_infer_cwes_path_traversal(self, mapper):
        cwes = mapper._infer_cwes_from_description("path traversal in file upload")
        assert "CWE-22" in cwes

    def test_infer_cwes_directory_traversal(self, mapper):
        cwes = mapper._infer_cwes_from_description("directory traversal in file API")
        assert "CWE-22" in cwes

    def test_infer_cwes_buffer_overflow(self, mapper):
        cwes = mapper._infer_cwes_from_description("buffer overflow in parser")
        assert "CWE-119" in cwes

    def test_infer_cwes_deserialization(self, mapper):
        cwes = mapper._infer_cwes_from_description("insecure deserialization in API")
        assert "CWE-502" in cwes

    def test_infer_cwes_ssrf(self, mapper):
        cwes = mapper._infer_cwes_from_description("SSRF in webhook handler")
        assert "CWE-918" in cwes

    def test_infer_cwes_xxe(self, mapper):
        cwes = mapper._infer_cwes_from_description("XXE in XML parser")
        assert "CWE-611" in cwes

    def test_infer_cwes_csrf(self, mapper):
        cwes = mapper._infer_cwes_from_description("CSRF in form submission")
        assert "CWE-352" in cwes

    def test_infer_cwes_auth_bypass(self, mapper):
        cwes = mapper._infer_cwes_from_description("authentication bypass in admin")
        assert "CWE-287" in cwes

    def test_infer_cwes_privesc(self, mapper):
        cwes = mapper._infer_cwes_from_description("privilege escalation via sudo")
        assert "CWE-269" in cwes

    def test_infer_cwes_hardcoded(self, mapper):
        cwes = mapper._infer_cwes_from_description("hard-coded credentials found")
        assert "CWE-798" in cwes

    def test_infer_cwes_hardcoded_no_hyphen(self, mapper):
        cwes = mapper._infer_cwes_from_description("hardcoded password in config")
        assert "CWE-798" in cwes

    def test_infer_cwes_info_disclosure(self, mapper):
        cwes = mapper._infer_cwes_from_description("information disclosure via error pages")
        assert "CWE-200" in cwes

    def test_infer_cwes_upload(self, mapper):
        cwes = mapper._infer_cwes_from_description("unrestricted upload of dangerous file")
        assert "CWE-434" in cwes

    def test_infer_cwes_no_match(self, mapper):
        cwes = mapper._infer_cwes_from_description("a generic vulnerability")
        assert cwes == []

    def test_infer_cwes_use_after_free(self, mapper):
        cwes = mapper._infer_cwes_from_description("use after free in memory handler")
        assert "CWE-416" in cwes

    def test_risk_context_initial_access(self, mapper):
        result = mapper.map_cve({"cwes": ["CWE-89"]})
        assert "initial network entry" in result["risk_context"]

    def test_risk_context_execution(self, mapper):
        result = mapper.map_cve({"cwes": ["CWE-78"]})
        assert "code execution" in result["risk_context"]

    def test_risk_context_privesc(self, mapper):
        result = mapper.map_cve({"cwes": ["CWE-269"]})
        assert "privilege escalation" in result["risk_context"]

    def test_risk_context_credential_access(self, mapper):
        result = mapper.map_cve({"cwes": ["CWE-287"]})
        assert "credential theft" in result["risk_context"]

    def test_risk_context_collection(self, mapper):
        result = mapper.map_cve({"cwes": ["CWE-200"]})
        assert "exfiltration" in result["risk_context"]

    def test_cwe_to_capec_mapping_exists(self):
        assert "CWE-79" in CWE_TO_CAPEC
        assert "CWE-89" in CWE_TO_CAPEC
        assert len(CWE_TO_CAPEC) >= 15

    def test_capec_to_attack_mapping_exists(self):
        assert "CAPEC-66" in CAPEC_TO_ATTACK
        assert "CAPEC-86" in CAPEC_TO_ATTACK
        assert len(CAPEC_TO_ATTACK) >= 15


class TestEPSSScorer:
    @pytest.fixture
    def scorer(self):
        return EPSSScorer(cache_ttl_seconds=3600)

    def test_classify_risk_critical(self):
        assert EPSSScorer._classify_risk(0.7) == "critical"
        assert EPSSScorer._classify_risk(0.9) == "critical"

    def test_classify_risk_high(self):
        assert EPSSScorer._classify_risk(0.4) == "high"
        assert EPSSScorer._classify_risk(0.69) == "high"

    def test_classify_risk_medium(self):
        assert EPSSScorer._classify_risk(0.1) == "medium"
        assert EPSSScorer._classify_risk(0.39) == "medium"

    def test_classify_risk_low(self):
        assert EPSSScorer._classify_risk(0.01) == "low"
        assert EPSSScorer._classify_risk(0.09) == "low"

    def test_classify_risk_unknown(self):
        assert EPSSScorer._classify_risk(0.0) == "unknown"

    def test_cache_invalid_initially(self, scorer):
        assert scorer._is_cache_valid() is False

    def test_cache_valid_after_set(self, scorer):
        scorer._cache_time = datetime.now(UTC)
        assert scorer._is_cache_valid() is True

    def test_cache_expired(self, scorer):
        scorer._cache_time = datetime.now(UTC) - timedelta(seconds=7200)
        assert scorer._is_cache_valid() is False

    @pytest.mark.asyncio
    async def test_score_success(self, scorer):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [{"cve": "CVE-2024-1234", "epss": "0.85", "percentile": "0.97"}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        scorer._client = mock_client

        result = await scorer.score("CVE-2024-1234")
        assert result["cve_id"] == "CVE-2024-1234"
        assert result["epss_score"] == 0.85
        assert result["percentile"] == 0.97
        assert result["risk_level"] == "critical"

    @pytest.mark.asyncio
    async def test_score_from_cache(self, scorer):
        scorer._cache_time = datetime.now(UTC)
        scorer._cache["CVE-2024-1234"] = {
            "cve_id": "CVE-2024-1234",
            "epss_score": 0.5,
            "percentile": 0.8,
            "risk_level": "high",
        }

        result = await scorer.score("CVE-2024-1234")
        assert result["epss_score"] == 0.5

    @pytest.mark.asyncio
    async def test_score_error_fallback(self, scorer):
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("API down")
        scorer._client = mock_client

        result = await scorer.score("CVE-2024-9999")
        assert result["epss_score"] == 0.0
        assert result["risk_level"] == "unknown"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_score_bulk_success(self, scorer):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"cve": "CVE-2024-1111", "epss": "0.1", "percentile": "0.5"},
                {"cve": "CVE-2024-2222", "epss": "0.8", "percentile": "0.95"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        scorer._client = mock_client

        results = await scorer.score_bulk(["CVE-2024-1111", "CVE-2024-2222"])
        assert len(results) == 2
        assert results["CVE-2024-1111"]["epss_score"] == 0.1
        assert results["CVE-2024-2222"]["epss_score"] == 0.8

    @pytest.mark.asyncio
    async def test_score_bulk_partial_cache(self, scorer):
        scorer._cache_time = datetime.now(UTC)
        scorer._cache["CVE-2024-1111"] = {
            "cve_id": "CVE-2024-1111",
            "epss_score": 0.3,
            "percentile": 0.6,
            "risk_level": "medium",
        }

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"cve": "CVE-2024-2222", "epss": "0.5", "percentile": "0.8"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        scorer._client = mock_client

        results = await scorer.score_bulk(["CVE-2024-1111", "CVE-2024-2222"])
        assert results["CVE-2024-1111"]["epss_score"] == 0.3  # from cache
        assert results["CVE-2024-2222"]["epss_score"] == 0.5  # fetched

    @pytest.mark.asyncio
    async def test_score_bulk_error_fallback(self, scorer):
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("timeout")
        scorer._client = mock_client

        results = await scorer.score_bulk(["CVE-2024-1111"])
        assert results["CVE-2024-1111"]["epss_score"] == 0.0

    @pytest.mark.asyncio
    async def test_close(self, scorer):
        mock_client = AsyncMock()
        scorer._client = mock_client
        await scorer.close()
        assert scorer._client is None
        mock_client.aclose.assert_called_once()

    def test_ensure_client(self, scorer):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            client = scorer._ensure_client()
            assert client is not None
            assert scorer._client is not None

    @pytest.mark.asyncio
    async def test_fetch_scores_updates_cache(self, scorer):
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"cve": "CVE-2024-1234", "epss": "0.5", "percentile": "0.7"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        scorer._client = mock_client

        await scorer._fetch_scores(["CVE-2024-1234"])
        assert "CVE-2024-1234" in scorer._cache
        assert scorer._cache_time is not None

    @pytest.mark.asyncio
    async def test_score_not_in_response(self, scorer):
        """When API returns empty data for a CVE, fallback is returned."""
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        scorer._client = mock_client

        result = await scorer.score("CVE-2024-9999")
        assert result["epss_score"] == 0.0
        assert result["risk_level"] == "unknown"
