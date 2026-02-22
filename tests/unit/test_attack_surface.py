"""Tests for Attack Surface Mapping (F12)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.vulnerability.attack_surface import (
    AttackSurfaceEntry,
    AttackSurfaceMap,
    AttackSurfaceMapper,
)


class TestAttackSurfaceModels:
    def test_entry_defaults(self):
        entry = AttackSurfaceEntry(
            resource_id="svc-1",
            resource_type="service",
            category="network",
        )
        assert entry.risk_level == "medium"
        assert entry.exposure == "internal"
        assert entry.details == {}
        assert entry.recommendations == []

    def test_entry_full(self):
        entry = AttackSurfaceEntry(
            resource_id="lb-1",
            resource_type="load_balancer",
            category="network",
            risk_level="high",
            exposure="external",
            details={"provider": "aws"},
            recommendations=["Restrict access"],
        )
        assert entry.exposure == "external"
        assert entry.risk_level == "high"
        assert len(entry.recommendations) == 1

    def test_map_defaults(self):
        m = AttackSurfaceMap()
        assert m.entries == []
        assert m.score_by_category == {}
        assert m.overall_score == 0.0
        assert m.total_external == 0
        assert m.total_internal == 0
        assert m.timestamp != ""

    def test_map_with_entries(self):
        entries = [
            AttackSurfaceEntry(
                resource_id="svc-1",
                resource_type="service",
                category="network",
                exposure="external",
            ),
            AttackSurfaceEntry(
                resource_id="cred-1",
                resource_type="credential",
                category="identity",
                exposure="internal",
            ),
        ]
        m = AttackSurfaceMap(
            entries=entries,
            score_by_category={"network": 80.0, "identity": 95.0},
            overall_score=87.5,
            total_external=1,
            total_internal=1,
        )
        assert len(m.entries) == 2
        assert m.overall_score == 87.5


class TestAttackSurfaceMapper:
    @pytest.fixture
    def mapper(self):
        return AttackSurfaceMapper()

    @pytest.fixture
    def mock_router(self):
        router = MagicMock()
        router.providers = ["aws", "k8s"]
        resource1 = MagicMock()
        resource1.id = "web-svc"
        resource1.resource_type = "service"
        resource1.labels = {"exposure": "external", "type": "LoadBalancer"}
        resource2 = MagicMock()
        resource2.id = "internal-svc"
        resource2.resource_type = "service"
        resource2.labels = {"exposure": "internal"}

        connector = AsyncMock()
        connector.list_resources.return_value = [resource1, resource2]
        router.get.return_value = connector
        return router

    @pytest.fixture
    def mock_repository(self):
        repo = AsyncMock()
        repo.list_vulnerabilities.return_value = [
            {
                "affected_resource": "web-server",
                "severity": "high",
                "title": "Open port vulnerability",
                "cve_id": "CVE-2024-1111",
                "remediation": "Close port 8080",
                "package_name": "openssl",
                "fixed_version": "3.1.5",
            },
        ]
        return repo

    @pytest.fixture
    def mock_credential_store(self):
        store = AsyncMock()
        store.store_name = "vault"
        store.list_credentials.return_value = [
            {
                "credential_id": "cred-1",
                "credential_type": "api_key",
                "expires_at": datetime.now(UTC) - timedelta(days=1),  # expired
                "last_rotated": datetime.now(UTC) - timedelta(days=90),
            },
            {
                "credential_id": "cred-2",
                "credential_type": "database",
                "expires_at": datetime.now(UTC) + timedelta(days=30),
                "last_rotated": None,
            },
        ]
        return store

    @pytest.fixture
    def full_mapper(self, mock_router, mock_repository, mock_credential_store):
        return AttackSurfaceMapper(
            connector_router=mock_router,
            repository=mock_repository,
            credential_stores=[mock_credential_store],
        )

    def test_calculate_category_score_empty(self, mapper):
        score = mapper._calculate_category_score([])
        assert score == 100.0

    def test_calculate_category_score_with_entries(self, mapper):
        entries = [
            AttackSurfaceEntry(
                resource_id="a", resource_type="svc", category="network", risk_level="critical"
            ),
            AttackSurfaceEntry(
                resource_id="b", resource_type="svc", category="network", risk_level="low"
            ),
        ]
        score = mapper._calculate_category_score(entries)
        # penalty = 10.0 + 0.5 = 10.5
        assert score == 89.5

    def test_calculate_category_score_capped(self, mapper):
        entries = [
            AttackSurfaceEntry(
                resource_id=f"r{i}", resource_type="svc", category="network", risk_level="critical"
            )
            for i in range(15)
        ]
        score = mapper._calculate_category_score(entries)
        # penalty = 15 * 10 = 150 → capped at 100 → score 0
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_map_no_data(self, mapper):
        surface = await mapper.map()
        assert len(surface.entries) == 0
        assert surface.overall_score == 100.0
        assert surface.total_external == 0
        assert surface.total_internal == 0

    @pytest.mark.asyncio
    async def test_map_with_router(self, mock_router):
        mapper = AttackSurfaceMapper(connector_router=mock_router)
        surface = await mapper.map()
        # 2 providers × 2 resources = 4 entries from external services
        assert len(surface.entries) >= 2
        assert any(e.exposure == "external" for e in surface.entries)

    @pytest.mark.asyncio
    async def test_map_with_repository(self, mock_repository):
        mapper = AttackSurfaceMapper(repository=mock_repository)
        surface = await mapper.map()
        assert len(surface.entries) >= 1

    @pytest.mark.asyncio
    async def test_map_with_credential_stores(self, mock_credential_store):
        mapper = AttackSurfaceMapper(credential_stores=[mock_credential_store])
        surface = await mapper.map()
        assert len(surface.entries) == 2
        cred_entries = [e for e in surface.entries if e.category == "identity"]
        assert len(cred_entries) == 2

    @pytest.mark.asyncio
    async def test_map_full(self, full_mapper):
        surface = await full_mapper.map()
        assert len(surface.entries) > 0
        categories = {e.category for e in surface.entries}
        assert "network" in categories
        assert "identity" in categories

    @pytest.mark.asyncio
    async def test_map_score_by_category(self, full_mapper):
        surface = await full_mapper.map()
        for cat in ("network", "identity", "application", "data"):
            assert cat in surface.score_by_category
            assert 0 <= surface.score_by_category[cat] <= 100

    @pytest.mark.asyncio
    async def test_external_services(self, full_mapper):
        services = await full_mapper.get_external_services()
        assert isinstance(services, list)
        for svc in services:
            assert "resource_id" in svc

    @pytest.mark.asyncio
    async def test_external_services_empty(self, mapper):
        services = await mapper.get_external_services()
        assert services == []

    @pytest.mark.asyncio
    async def test_get_changes(self, full_mapper):
        changes = await full_mapper.get_changes(since_hours=24)
        assert changes["since_hours"] == 24
        assert "current_entry_count" in changes
        assert "external_count" in changes
        assert "timestamp" in changes

    @pytest.mark.asyncio
    async def test_get_changes_empty(self, mapper):
        changes = await mapper.get_changes()
        assert changes["current_entry_count"] == 0

    @pytest.mark.asyncio
    async def test_get_risk_summary(self, full_mapper):
        summary = await full_mapper.get_risk_summary()
        assert "overall_score" in summary
        assert "score_by_category" in summary
        assert "risk_counts" in summary
        assert "total_entries" in summary
        assert "external_exposure" in summary

    @pytest.mark.asyncio
    async def test_get_risk_summary_empty(self, mapper):
        summary = await mapper.get_risk_summary()
        assert summary["total_entries"] == 0
        assert summary["overall_score"] == 100.0

    @pytest.mark.asyncio
    async def test_map_external_services_router_error(self):
        router = MagicMock()
        router.providers = ["aws"]
        connector = AsyncMock()
        connector.list_resources.side_effect = Exception("timeout")
        router.get.return_value = connector
        mapper = AttackSurfaceMapper(connector_router=router)
        surface = await mapper.map()
        # Error in one provider shouldn't crash the whole map
        assert isinstance(surface.entries, list)

    @pytest.mark.asyncio
    async def test_map_iam_expired_credential(self, mock_credential_store):
        mapper = AttackSurfaceMapper(credential_stores=[mock_credential_store])
        surface = await mapper.map()
        expired_entries = [
            e for e in surface.entries if e.risk_level == "critical" and e.category == "identity"
        ]
        assert len(expired_entries) >= 1
        assert any("Rotate" in r for e in expired_entries for r in e.recommendations)

    @pytest.mark.asyncio
    async def test_map_iam_no_rotation(self, mock_credential_store):
        mapper = AttackSurfaceMapper(credential_stores=[mock_credential_store])
        surface = await mapper.map()
        medium_creds = [
            e for e in surface.entries if e.risk_level == "medium" and e.category == "identity"
        ]
        assert len(medium_creds) >= 1

    @pytest.mark.asyncio
    async def test_map_iam_store_error(self):
        store = AsyncMock()
        store.list_credentials.side_effect = Exception("auth failed")
        mapper = AttackSurfaceMapper(credential_stores=[store])
        surface = await mapper.map()
        assert len(surface.entries) == 0

    @pytest.mark.asyncio
    async def test_map_unpatched_services(self, mock_repository):
        mapper = AttackSurfaceMapper(repository=mock_repository)
        surface = await mapper.map()
        unpatched = [e for e in surface.entries if e.resource_type == "unpatched_service"]
        assert len(unpatched) >= 1
        assert any("Patch" in r for e in unpatched for r in e.recommendations)

    @pytest.mark.asyncio
    async def test_map_certificate_status(self):
        repo = AsyncMock()
        repo.list_vulnerabilities.return_value = [
            {
                "affected_resource": "web.example.com",
                "severity": "high",
                "title": "Expired TLS Certificate",
            },
        ]
        mapper = AttackSurfaceMapper(repository=repo)
        surface = await mapper.map()
        cert_entries = [e for e in surface.entries if e.resource_type == "certificate"]
        assert len(cert_entries) >= 1

    @pytest.mark.asyncio
    async def test_map_certificate_ssl_keyword(self):
        repo = AsyncMock()
        repo.list_vulnerabilities.return_value = [
            {
                "affected_resource": "api.example.com",
                "severity": "medium",
                "title": "Weak SSL cipher detected",
            },
        ]
        mapper = AttackSurfaceMapper(repository=repo)
        surface = await mapper.map()
        cert_entries = [e for e in surface.entries if e.resource_type == "certificate"]
        assert len(cert_entries) >= 1

    @pytest.mark.asyncio
    async def test_map_no_cert_match(self):
        repo = AsyncMock()
        repo.list_vulnerabilities.return_value = [
            {
                "affected_resource": "db-server",
                "severity": "medium",
                "title": "Open port detected",
            },
        ]
        mapper = AttackSurfaceMapper(repository=repo)
        entries = await mapper._map_certificate_status()
        assert len(entries) == 0
