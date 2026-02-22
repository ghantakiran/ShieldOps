"""Tests for SBOM generation (F7)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from shieldops.integrations.scanners.sbom_generator import (
    SBOMComponent,
    SBOMFormat,
    SBOMGenerator,
    SBOMResult,
)


class TestSBOMModels:
    def test_sbom_format_values(self):
        assert SBOMFormat.CYCLONEDX_JSON == "cyclonedx-json"
        assert SBOMFormat.CYCLONEDX_XML == "cyclonedx-xml"
        assert SBOMFormat.SPDX_JSON == "spdx-json"
        assert SBOMFormat.SPDX_TAG_VALUE == "spdx-tag-value"

    def test_sbom_component_defaults(self):
        comp = SBOMComponent(name="requests")
        assert comp.name == "requests"
        assert comp.version == ""
        assert comp.type == "library"
        assert comp.purl == ""
        assert comp.ecosystem == ""
        assert comp.licenses == []

    def test_sbom_component_full(self):
        comp = SBOMComponent(
            name="django",
            version="4.2.8",
            type="library",
            purl="pkg:pypi/django@4.2.8",
            ecosystem="pip",
            licenses=["BSD-3-Clause"],
        )
        assert comp.name == "django"
        assert comp.version == "4.2.8"
        assert comp.licenses == ["BSD-3-Clause"]

    def test_sbom_result_defaults(self):
        result = SBOMResult(target="myapp", format="cyclonedx-json", tool="syft")
        assert result.target == "myapp"
        assert result.component_count == 0
        assert result.components == []
        assert result.raw_sbom == {}
        assert result.errors == []

    def test_sbom_result_with_errors(self):
        result = SBOMResult(
            target="img",
            format="cyclonedx-json",
            tool="syft",
            errors=["binary not found"],
        )
        assert len(result.errors) == 1

    def test_sbom_result_with_components(self):
        comp = SBOMComponent(name="pkg", version="1.0")
        result = SBOMResult(
            target="img",
            format="cyclonedx-json",
            tool="syft",
            component_count=1,
            components=[comp],
        )
        assert result.component_count == 1
        assert result.components[0].name == "pkg"


class TestSBOMGenerator:
    @pytest.fixture
    def generator(self):
        return SBOMGenerator(syft_path="syft", trivy_path="trivy")

    def test_supported_formats(self):
        fmts = SBOMGenerator.supported_formats()
        assert "cyclonedx-json" in fmts
        assert "spdx-json" in fmts
        assert len(fmts) == 4

    def test_syft_format_flag(self):
        assert SBOMGenerator._syft_format_flag(SBOMFormat.CYCLONEDX_JSON) == "cyclonedx-json"
        assert SBOMGenerator._syft_format_flag(SBOMFormat.SPDX_JSON) == "spdx-json"
        assert SBOMGenerator._syft_format_flag(SBOMFormat.CYCLONEDX_XML) == "cyclonedx-xml"
        assert SBOMGenerator._syft_format_flag(SBOMFormat.SPDX_TAG_VALUE) == "spdx-tag-value"

    def test_parse_cyclonedx_empty(self, generator):
        result = generator._parse_cyclonedx({})
        assert result == []

    def test_parse_cyclonedx_with_components(self, generator):
        raw = {
            "components": [
                {
                    "name": "django",
                    "version": "4.2.8",
                    "type": "library",
                    "purl": "pkg:pypi/django@4.2.8",
                    "licenses": [{"license": {"id": "BSD-3-Clause"}}],
                },
                {
                    "name": "requests",
                    "version": "2.31.0",
                },
            ]
        }
        components = generator._parse_cyclonedx(raw)
        assert len(components) == 2
        assert components[0].name == "django"
        assert components[0].version == "4.2.8"
        assert components[0].licenses == ["BSD-3-Clause"]
        assert components[1].name == "requests"

    def test_parse_cyclonedx_license_name_fallback(self, generator):
        raw = {
            "components": [
                {
                    "name": "pkg",
                    "licenses": [{"license": {"name": "MIT License"}}],
                }
            ]
        }
        components = generator._parse_cyclonedx(raw)
        assert components[0].licenses == ["MIT License"]

    def test_parse_cyclonedx_license_string(self, generator):
        raw = {
            "components": [
                {
                    "name": "pkg",
                    "licenses": [{"license": "MIT"}],
                }
            ]
        }
        components = generator._parse_cyclonedx(raw)
        assert components[0].licenses == ["MIT"]

    def test_parse_cyclonedx_license_not_dict(self, generator):
        raw = {
            "components": [
                {
                    "name": "pkg",
                    "licenses": ["MIT"],
                }
            ]
        }
        # Strings (not dicts) in licenses list are skipped
        components = generator._parse_cyclonedx(raw)
        assert components[0].licenses == []

    @pytest.mark.asyncio
    async def test_generate_syft_success(self, generator):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"", b"")

        raw_sbom = {"components": [{"name": "flask", "version": "3.0"}]}

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("pathlib.Path.read_text", return_value=json.dumps(raw_sbom)),
            patch("tempfile.NamedTemporaryFile"),
        ):
            result = await generator.generate("myimage:latest", SBOMFormat.CYCLONEDX_JSON)

        assert result.tool == "syft"
        assert result.errors == []
        assert result.component_count == 1
        assert result.components[0].name == "flask"

    @pytest.mark.asyncio
    async def test_generate_syft_failure_falls_back_to_trivy(self, generator):
        # syft fails
        syft_proc = AsyncMock()
        syft_proc.returncode = 1
        syft_proc.communicate.return_value = (b"", b"syft error")

        # trivy succeeds
        trivy_proc = AsyncMock()
        trivy_proc.returncode = 0
        trivy_proc.communicate.return_value = (b"", b"")

        raw_sbom = {"components": [{"name": "numpy", "version": "1.0"}]}
        call_count = [0]

        async def mock_subprocess(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return syft_proc
            return trivy_proc

        with (
            patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess),
            patch("pathlib.Path.read_text", return_value=json.dumps(raw_sbom)),
            patch("tempfile.NamedTemporaryFile"),
        ):
            result = await generator.generate("myimage:latest")

        assert result.tool == "trivy"
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_generate_syft_not_found(self, generator):
        with (
            patch(
                "asyncio.create_subprocess_exec",
                side_effect=FileNotFoundError("syft not found"),
            ),
            patch("tempfile.NamedTemporaryFile"),
        ):
            # syft not found → tries trivy
            trivy_proc = AsyncMock()
            trivy_proc.returncode = 0
            trivy_proc.communicate.return_value = (b"", b"")

            raw = {"components": []}

            # Second call succeeds
            calls = [0]

            async def mock_exec(*a, **kw):
                calls[0] += 1
                if calls[0] <= 1:
                    raise FileNotFoundError
                return trivy_proc

            with (
                patch("asyncio.create_subprocess_exec", side_effect=mock_exec),
                patch("pathlib.Path.read_text", return_value=json.dumps(raw)),
                patch("tempfile.NamedTemporaryFile"),
            ):
                result = await generator.generate("target")
            assert result.tool == "trivy"

    @pytest.mark.asyncio
    async def test_generate_both_fail(self, generator):
        async def always_fail(*a, **kw):
            raise FileNotFoundError("not found")

        with (
            patch("asyncio.create_subprocess_exec", side_effect=always_fail),
            patch("tempfile.NamedTemporaryFile"),
        ):
            result = await generator.generate("target")

        assert result.tool == "trivy"
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_generate_trivy_fs_mode_for_directory(self, generator):
        """Targets without ':' should use trivy 'fs' subcommand."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"", b"")

        raw = {"components": []}
        exec_calls = []

        async def capture_exec(*args, **kwargs):
            exec_calls.append(args)
            return mock_proc

        # syft fails so trivy is tried
        syft_proc = AsyncMock()
        syft_proc.returncode = 1
        syft_proc.communicate.return_value = (b"", b"fail")
        call_idx = [0]

        async def mock_exec(*args, **kwargs):
            call_idx[0] += 1
            exec_calls.append(args)
            if call_idx[0] == 1:
                return syft_proc
            return mock_proc

        with (
            patch("asyncio.create_subprocess_exec", side_effect=mock_exec),
            patch("pathlib.Path.read_text", return_value=json.dumps(raw)),
            patch("tempfile.NamedTemporaryFile"),
        ):
            await generator.generate("/app/src")

        # trivy call should use "fs" not "image"
        trivy_call = exec_calls[-1]
        assert "fs" in trivy_call

    @pytest.mark.asyncio
    async def test_generate_trivy_image_mode_for_image(self, generator):
        """Targets with ':' should use trivy 'image' subcommand."""
        syft_proc = AsyncMock()
        syft_proc.returncode = 1
        syft_proc.communicate.return_value = (b"", b"fail")

        trivy_proc = AsyncMock()
        trivy_proc.returncode = 0
        trivy_proc.communicate.return_value = (b"", b"")

        raw = {"components": []}
        exec_calls = []
        call_idx = [0]

        async def mock_exec(*args, **kwargs):
            call_idx[0] += 1
            exec_calls.append(args)
            if call_idx[0] == 1:
                return syft_proc
            return trivy_proc

        with (
            patch("asyncio.create_subprocess_exec", side_effect=mock_exec),
            patch("pathlib.Path.read_text", return_value=json.dumps(raw)),
            patch("tempfile.NamedTemporaryFile"),
        ):
            await generator.generate("nginx:latest")

        trivy_call = exec_calls[-1]
        assert "image" in trivy_call

    @pytest.mark.asyncio
    async def test_generate_spdx_no_component_parse(self, generator):
        """SPDX format should not attempt CycloneDX parsing."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"", b"")

        raw = {"spdxVersion": "SPDX-2.3", "packages": []}

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("pathlib.Path.read_text", return_value=json.dumps(raw)),
            patch("tempfile.NamedTemporaryFile"),
        ):
            result = await generator.generate("target", SBOMFormat.SPDX_JSON)

        assert result.errors == []
        assert result.components == []

    @pytest.mark.asyncio
    async def test_generate_and_scan_success(self, generator):
        comp = SBOMComponent(name="openssl", version="1.1.1")
        sbom_result = SBOMResult(
            target="img",
            format="cyclonedx-json",
            tool="syft",
            component_count=1,
            components=[comp],
        )

        mock_source = AsyncMock()
        mock_source.scan.return_value = [{"cve_id": "CVE-2024-1111", "severity": "high"}]

        with patch.object(generator, "generate", return_value=sbom_result):
            result = await generator.generate_and_scan(
                "img", cve_sources=[mock_source], severity_threshold="medium"
            )

        assert result["total_vulnerabilities"] == 1
        assert result["vulnerabilities"][0]["sbom_component"] == "openssl"
        assert result["vulnerabilities"][0]["sbom_version"] == "1.1.1"

    @pytest.mark.asyncio
    async def test_generate_and_scan_no_sources(self, generator):
        sbom_result = SBOMResult(
            target="img",
            format="cyclonedx-json",
            tool="syft",
            component_count=1,
            components=[SBOMComponent(name="pkg")],
        )

        with patch.object(generator, "generate", return_value=sbom_result):
            result = await generator.generate_and_scan("img")

        assert result["total_vulnerabilities"] == 0
        assert result["vulnerabilities"] == []

    @pytest.mark.asyncio
    async def test_generate_and_scan_sbom_errors(self, generator):
        sbom_result = SBOMResult(
            target="img",
            format="cyclonedx-json",
            tool="syft",
            errors=["binary not found"],
        )

        with patch.object(generator, "generate", return_value=sbom_result):
            result = await generator.generate_and_scan("img")

        assert "errors" in result
        assert result["vulnerabilities"] == []

    @pytest.mark.asyncio
    async def test_generate_and_scan_source_error_handled(self, generator):
        comp = SBOMComponent(name="pkg", version="1.0")
        sbom_result = SBOMResult(
            target="img",
            format="cyclonedx-json",
            tool="syft",
            component_count=1,
            components=[comp],
        )

        mock_source = AsyncMock()
        mock_source.scan.side_effect = Exception("Source API down")

        with patch.object(generator, "generate", return_value=sbom_result):
            result = await generator.generate_and_scan("img", cve_sources=[mock_source])

        assert result["total_vulnerabilities"] == 0

    @pytest.mark.asyncio
    async def test_generate_and_scan_multiple_components(self, generator):
        comps = [
            SBOMComponent(name="pkg1", version="1.0"),
            SBOMComponent(name="pkg2", version="2.0"),
        ]
        sbom_result = SBOMResult(
            target="img",
            format="cyclonedx-json",
            tool="syft",
            component_count=2,
            components=comps,
        )

        mock_source = AsyncMock()
        mock_source.scan.side_effect = [
            [{"cve_id": "CVE-1", "severity": "high"}],
            [{"cve_id": "CVE-2", "severity": "medium"}],
        ]

        with patch.object(generator, "generate", return_value=sbom_result):
            result = await generator.generate_and_scan("img", cve_sources=[mock_source])

        assert result["total_vulnerabilities"] == 2
