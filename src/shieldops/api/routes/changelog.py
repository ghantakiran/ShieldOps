"""API changelog endpoint."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

CHANGELOG: list[dict[str, str]] = [
    {
        "version": "1.0.0",
        "date": "2026-02-20",
        "changes": (
            "Initial release: Investigation, Remediation, Security,"
            " Learning agents; Multi-cloud connectors (AWS, GCP,"
            " Azure, K8s, Linux); Vulnerability management; OIDC"
            " SSO; Helm chart deployment"
        ),
    },
]


@router.get("/changelog")
async def get_changelog() -> list[dict[str, str]]:
    """Get API changelog."""
    return CHANGELOG
