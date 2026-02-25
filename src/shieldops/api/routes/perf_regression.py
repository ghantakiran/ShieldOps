"""Performance regression detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
pr_route = APIRouter(
    prefix="/perf-regression",
    tags=["Performance Regression"],
)

_instance: Any = None


def set_detector(detector: Any) -> None:
    global _instance
    _instance = detector


def _get_detector() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Performance regression service unavailable",
        )
    return _instance


# -- Request models --


class RunTestRequest(BaseModel):
    service_name: str
    deployment_id: str = ""
    metric_category: str = "latency"
    before_value: float = 0.0
    after_value: float = 0.0
    method: str = "mean_shift"


class CreateBaselineRequest(BaseModel):
    service_name: str
    metric_category: str = "latency"
    values: list[float] = []


class CompareDeploymentsRequest(BaseModel):
    deployment_a: str
    deployment_b: str


# -- Routes --


@pr_route.post("/tests")
async def run_test(
    body: RunTestRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    test = detector.run_test(**body.model_dump())
    return test.model_dump()  # type: ignore[no-any-return]


@pr_route.get("/tests")
async def list_tests(
    service_name: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return [  # type: ignore[no-any-return]
        t.model_dump()
        for t in detector.list_tests(
            service_name=service_name,
            severity=severity,
            limit=limit,
        )
    ]


@pr_route.get("/tests/{test_id}")
async def get_test(
    test_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    test = detector.get_test(test_id)
    if test is None:
        raise HTTPException(
            404,
            f"Test '{test_id}' not found",
        )
    return test.model_dump()  # type: ignore[no-any-return]


@pr_route.post("/baselines")
async def create_baseline(
    body: CreateBaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    baseline = detector.create_baseline(
        body.service_name,
        body.metric_category,
        body.values,
    )
    return baseline.model_dump()  # type: ignore[no-any-return]


@pr_route.get("/detect/{test_id}")
async def detect_regression(
    test_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    result = detector.detect_regression(test_id)
    if result is None:
        raise HTTPException(
            404,
            f"Test '{test_id}' not found",
        )
    return result  # type: ignore[no-any-return]


@pr_route.post("/compare")
async def compare_deployments(
    body: CompareDeploymentsRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return detector.compare_deployments(  # type: ignore[no-any-return]
        body.deployment_a,
        body.deployment_b,
    )


@pr_route.get("/degrading")
async def get_degrading_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return detector.identify_degrading_services()  # type: ignore[no-any-return]


@pr_route.get("/false-positive-rate")
async def get_false_positive_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return {  # type: ignore[no-any-return]
        "false_positive_rate": (detector.calculate_false_positive_rate()),
    }


@pr_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    report = detector.generate_regression_report()
    return report.model_dump()  # type: ignore[no-any-return]


@pr_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.get_stats()  # type: ignore[no-any-return]
