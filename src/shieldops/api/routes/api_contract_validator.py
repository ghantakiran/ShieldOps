"""API contract validator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
acv_route = APIRouter(
    prefix="/api-contract-validator",
    tags=["API Contract Validator"],
)

_instance: Any = None


def set_validator(validator: Any) -> None:
    global _instance
    _instance = validator


def _get_validator() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "API contract validator unavailable",
        )
    return _instance


# -- Request models --


class RegisterContractRequest(BaseModel):
    provider_service: str
    consumer_service: str = ""
    endpoint: str = ""
    schema_format: str = "openapi"
    version: str = ""
    fields: list[str] = []


class DetectBreakingRequest(BaseModel):
    contract_id: str
    new_fields: list[str]


# -- Routes --


@acv_route.post("/contracts")
async def register_contract(
    body: RegisterContractRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    contract = validator.register_contract(**body.model_dump())
    return contract.model_dump()  # type: ignore[no-any-return]


@acv_route.get("/contracts")
async def list_contracts(
    provider: str | None = None,
    consumer: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    validator = _get_validator()
    return [  # type: ignore[no-any-return]
        c.model_dump()
        for c in validator.list_contracts(
            provider=provider,
            consumer=consumer,
            limit=limit,
        )
    ]


@acv_route.get("/contracts/{contract_id}")
async def get_contract(
    contract_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    contract = validator.get_contract(contract_id)
    if contract is None:
        raise HTTPException(
            404,
            f"Contract '{contract_id}' not found",
        )
    return contract.model_dump()  # type: ignore[no-any-return]


@acv_route.post("/validate/{contract_id}")
async def validate_contract(
    contract_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    result = validator.validate_contract(contract_id)
    if result is None:
        raise HTTPException(
            404,
            f"Contract '{contract_id}' not found",
        )
    return result  # type: ignore[no-any-return]


@acv_route.post("/breaking-changes")
async def detect_breaking_changes(
    body: DetectBreakingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    validator = _get_validator()
    violations = validator.detect_breaking_changes(
        body.contract_id,
        body.new_fields,
    )
    return [v.model_dump() for v in violations]  # type: ignore[no-any-return]


@acv_route.get("/version-compatibility")
async def check_version_compatibility(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    validator = _get_validator()
    return validator.check_version_compatibility()  # type: ignore[no-any-return]


@acv_route.get("/undocumented")
async def get_undocumented_apis(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    validator = _get_validator()
    return validator.identify_undocumented_apis()  # type: ignore[no-any-return]


@acv_route.get("/compliance-rate")
async def get_compliance_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    return {  # type: ignore[no-any-return]
        "compliance_pct": (validator.calculate_compliance_rate()),
    }


@acv_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    report = validator.generate_contract_report()
    return report.model_dump()  # type: ignore[no-any-return]


@acv_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    validator = _get_validator()
    return validator.get_stats()  # type: ignore[no-any-return]
