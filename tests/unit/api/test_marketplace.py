"""Tests for marketplace API endpoints.

Tests cover:
- GET /marketplace/templates — list all templates
- GET /marketplace/templates?category=... — filter by category
- GET /marketplace/templates?cloud=... — filter by cloud provider
- GET /marketplace/templates?q=... — search by keyword
- GET /marketplace/templates?tags=... — filter by tags
- GET /marketplace/templates/{template_id} — get template by ID
- GET /marketplace/templates/{template_id} — 404 for invalid ID
- POST /marketplace/deploy — deploy template
- POST /marketplace/deploy — 400 for missing required params
- POST /marketplace/deploy — 400 for unknown template
- GET /marketplace/categories — list categories with counts
- GET /marketplace/featured — list featured templates
- GET endpoints with no loader initialized
- Template YAML schema validation
- Combined filter query
- Deploy template with custom params
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shieldops.api.routes import marketplace
from shieldops.playbooks.template_loader import TemplateLoader

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "playbooks" / "templates"


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_module_loader():
    original = marketplace._template_loader
    marketplace._template_loader = None
    yield
    marketplace._template_loader = original


@pytest.fixture
def template_loader() -> TemplateLoader:
    loader = TemplateLoader(templates_dir=TEMPLATES_DIR)
    loader.load_all()
    return loader


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(marketplace.router, prefix="/api/v1")
    return app


def _build_client_with_auth(
    app: FastAPI,
    loader: TemplateLoader | None = None,
) -> TestClient:
    """Wire dependency overrides for an authenticated user."""
    if loader is not None:
        marketplace.set_template_loader(loader)

    from shieldops.api.auth.dependencies import get_current_user
    from shieldops.api.auth.models import UserResponse, UserRole

    user = UserResponse(
        id="user-1",
        email="test@test.com",
        name="Test User",
        role=UserRole.OPERATOR,
        is_active=True,
    )

    async def _mock_user() -> UserResponse:
        return user

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


# =================================================================
# 1. List all templates
# =================================================================


class TestListTemplates:
    def test_list_all_templates(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8
        assert len(data["templates"]) == 8

    def test_list_templates_returns_expected_fields(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates")
        data = resp.json()
        first = data["templates"][0]
        expected_keys = {
            "id",
            "name",
            "description",
            "category",
            "cloud_providers",
            "agent_type",
            "risk_level",
            "tags",
            "estimated_setup_minutes",
            "featured",
            "parameters",
            "steps",
        }
        assert expected_keys.issubset(first.keys())


# =================================================================
# 2. Filter by category
# =================================================================


class TestFilterByCategory:
    def test_filter_remediation(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates?category=remediation")
        data = resp.json()
        assert data["total"] > 0
        for t in data["templates"]:
            assert t["category"] == "remediation"

    def test_filter_security(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates?category=security")
        data = resp.json()
        assert data["total"] > 0
        for t in data["templates"]:
            assert t["category"] == "security"

    def test_filter_nonexistent_category_returns_empty(
        self, template_loader: TemplateLoader
    ) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates?category=nonexistent")
        data = resp.json()
        assert data["total"] == 0
        assert data["templates"] == []


# =================================================================
# 3. Filter by cloud provider
# =================================================================


class TestFilterByCloud:
    def test_filter_aws(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates?cloud=aws")
        data = resp.json()
        assert data["total"] > 0
        for t in data["templates"]:
            assert "aws" in t["cloud_providers"]

    def test_filter_kubernetes(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates?cloud=kubernetes")
        data = resp.json()
        assert data["total"] > 0
        for t in data["templates"]:
            assert "kubernetes" in t["cloud_providers"]


# =================================================================
# 4. Search by keyword
# =================================================================


class TestSearchByKeyword:
    def test_search_by_name(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates?q=certificate")
        data = resp.json()
        assert data["total"] >= 1
        names = [t["name"] for t in data["templates"]]
        assert any("Certificate" in n or "certificate" in n.lower() for n in names)

    def test_search_by_tag(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates?q=kubernetes")
        data = resp.json()
        assert data["total"] >= 1

    def test_search_no_results(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates?q=zzzznotfound")
        data = resp.json()
        assert data["total"] == 0


# =================================================================
# 5. Filter by tags
# =================================================================


class TestFilterByTags:
    def test_filter_by_single_tag(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates?tags=auto-scaling")
        data = resp.json()
        assert data["total"] >= 1
        for t in data["templates"]:
            assert "auto-scaling" in t["tags"]

    def test_filter_by_multiple_tags(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates?tags=security,cve")
        data = resp.json()
        assert data["total"] >= 1


# =================================================================
# 6. Get template by ID
# =================================================================


class TestGetTemplateById:
    def test_get_valid_template(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates/tmpl-aws-ec2-autoscale")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "tmpl-aws-ec2-autoscale"
        assert data["name"] == "AWS EC2 Auto-Scale"
        assert data["category"] == "remediation"
        assert len(data["parameters"]) > 0
        assert len(data["steps"]) > 0

    def test_get_template_not_found(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates/tmpl-does-not-exist")
        assert resp.status_code == 404


# =================================================================
# 7. Deploy template
# =================================================================


class TestDeployTemplate:
    def test_deploy_template_success(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.post(
            "/api/v1/marketplace/deploy",
            json={
                "template_id": "tmpl-k8s-pod-restart",
                "org_id": "org-test",
                "environment": "staging",
                "parameters": {
                    "namespace": "production",
                    "pod_selector": "app=web",
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["template_id"] == "tmpl-k8s-pod-restart"
        assert data["template_name"] == "Kubernetes Pod Restart"
        assert data["org_id"] == "org-test"
        assert data["environment"] == "staging"
        assert data["status"] == "deployed"
        assert "deployment_id" in data
        assert len(data["steps"]) > 0

    def test_deploy_unknown_template_returns_400(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.post(
            "/api/v1/marketplace/deploy",
            json={
                "template_id": "tmpl-nonexistent",
                "org_id": "org-test",
                "environment": "production",
                "parameters": {},
            },
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"]

    def test_deploy_with_custom_params(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.post(
            "/api/v1/marketplace/deploy",
            json={
                "template_id": "tmpl-disk-space-cleanup",
                "org_id": "org-test",
                "environment": "production",
                "parameters": {
                    "target_host": "web-01.prod.internal",
                    "disk_threshold_percent": 90,
                    "log_retention_days": 3,
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["parameters"]["target_host"] == "web-01.prod.internal"
        assert data["parameters"]["disk_threshold_percent"] == 90
        assert data["parameters"]["log_retention_days"] == 3


# =================================================================
# 8. List categories
# =================================================================


class TestListCategories:
    def test_list_categories(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        category_names = [c["category"] for c in data["categories"]]
        assert "remediation" in category_names
        assert "security" in category_names

    def test_categories_have_counts(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/categories")
        data = resp.json()
        for cat in data["categories"]:
            assert cat["count"] > 0


# =================================================================
# 9. Featured templates
# =================================================================


class TestFeaturedTemplates:
    def test_list_featured(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/featured")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for t in data["templates"]:
            assert t["featured"] is True


# =================================================================
# 10. No loader initialized (graceful degradation)
# =================================================================


class TestNoLoaderInitialized:
    def test_list_templates_no_loader(self) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, loader=None)

        resp = client.get("/api/v1/marketplace/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["templates"] == []

    def test_get_template_no_loader(self) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, loader=None)

        resp = client.get("/api/v1/marketplace/templates/tmpl-aws-ec2-autoscale")
        assert resp.status_code == 503

    def test_deploy_no_loader(self) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, loader=None)

        resp = client.post(
            "/api/v1/marketplace/deploy",
            json={
                "template_id": "tmpl-test",
                "org_id": "org-1",
                "environment": "production",
                "parameters": {},
            },
        )
        assert resp.status_code == 503

    def test_categories_no_loader(self) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, loader=None)

        resp = client.get("/api/v1/marketplace/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_featured_no_loader(self) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, loader=None)

        resp = client.get("/api/v1/marketplace/featured")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


# =================================================================
# 11. Template YAML validation
# =================================================================


class TestTemplateYamlValidation:
    def test_all_templates_have_required_fields(self, template_loader: TemplateLoader) -> None:
        """Verify every loaded template has the required schema fields."""
        templates = template_loader.all_templates()
        assert len(templates) == 8

        for t in templates:
            assert t.id, f"Template missing id: {t.name}"
            assert t.name, "Template missing name"
            assert t.description, f"Template {t.name} missing description"
            assert t.category in (
                "remediation",
                "security",
                "cost",
                "investigation",
            ), f"Template {t.name} has invalid category: {t.category}"
            assert len(t.cloud_providers) > 0, f"Template {t.name} has no cloud providers"
            assert t.risk_level in ("low", "medium", "high"), (
                f"Template {t.name} has invalid risk_level: {t.risk_level}"
            )
            assert len(t.tags) > 0, f"Template {t.name} has no tags"
            assert len(t.parameters) > 0, f"Template {t.name} has no parameters"
            assert len(t.steps) > 0, f"Template {t.name} has no steps"

    def test_all_parameters_have_descriptions(self, template_loader: TemplateLoader) -> None:
        """Verify every parameter has a name, type, and description."""
        for t in template_loader.all_templates():
            for p in t.parameters:
                assert p.name, f"Unnamed parameter in {t.name}"
                assert p.type in (
                    "string",
                    "integer",
                    "boolean",
                ), f"Invalid type '{p.type}' in {t.name}.{p.name}"
                assert p.description, f"Parameter {p.name} in {t.name} missing description"


# =================================================================
# 12. Combined filter query
# =================================================================


class TestCombinedFilters:
    def test_category_and_cloud_combined(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates?category=remediation&cloud=aws")
        data = resp.json()
        for t in data["templates"]:
            assert t["category"] == "remediation"
            assert "aws" in t["cloud_providers"]

    def test_category_cloud_and_search(self, template_loader: TemplateLoader) -> None:
        app = _create_test_app()
        client = _build_client_with_auth(app, template_loader)

        resp = client.get("/api/v1/marketplace/templates?category=security&q=certificate")
        data = resp.json()
        assert data["total"] >= 1
        for t in data["templates"]:
            assert t["category"] == "security"
