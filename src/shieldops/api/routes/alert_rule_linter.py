"""Alert rule linter API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/alert-rule-linter",
    tags=["Alert Rule Linter"],
)

_instance: Any = None


def set_linter(linter: Any) -> None:
    global _instance
    _instance = linter


def _get_linter() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Alert rule linter service unavailable",
        )
    return _instance


class RegisterRuleRequest(BaseModel):
    name: str
    rule_type: str = "metric_threshold"
    expression: str = ""
    threshold: float = 0.0
    labels: dict[str, str] = Field(
        default_factory=dict,
    )
    runbook_url: str = ""
    service_name: str = ""
    is_enabled: bool = True


class AutoFixRequest(BaseModel):
    rule_id: str


@router.post("/rules")
async def register_rule(
    body: RegisterRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    linter = _get_linter()
    rule = linter.register_rule(**body.model_dump())
    return rule.model_dump()


@router.get("/rules")
async def list_rules(
    service_name: str | None = None,
    rule_type: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    linter = _get_linter()
    return [
        r.model_dump()
        for r in linter.list_rules(
            service_name=service_name,
            rule_type=rule_type,
            limit=limit,
        )
    ]


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    linter = _get_linter()
    rule = linter.get_rule(rule_id)
    if rule is None:
        raise HTTPException(
            404,
            f"Rule '{rule_id}' not found",
        )
    return rule.model_dump()


@router.post("/rules/{rule_id}/lint")
async def lint_rule(
    rule_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    linter = _get_linter()
    findings = linter.lint_rule(rule_id)
    return [f.model_dump() for f in findings]


@router.post("/lint-all")
async def lint_all_rules(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    linter = _get_linter()
    findings = linter.lint_all_rules()
    return [f.model_dump() for f in findings]


@router.post("/rules/{rule_id}/auto-fix")
async def auto_fix_rule(
    rule_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    linter = _get_linter()
    rule = linter.auto_fix_rule(rule_id)
    if rule is None:
        raise HTTPException(
            404,
            f"Rule '{rule_id}' not found",
        )
    return rule.model_dump()


@router.get("/duplicates")
async def detect_duplicates(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    linter = _get_linter()
    return linter.detect_duplicate_rules()


@router.get("/quality-score")
async def quality_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    linter = _get_linter()
    score = linter.calculate_rule_quality_score()
    return {"quality_score": score}


@router.get("/report")
async def lint_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    linter = _get_linter()
    return linter.generate_lint_report().model_dump()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    linter = _get_linter()
    count = linter.clear_data()
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    linter = _get_linter()
    return linter.get_stats()
