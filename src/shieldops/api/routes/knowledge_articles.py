"""Knowledge base article API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/knowledge-articles",
    tags=["Knowledge Articles"],
)

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Knowledge base service unavailable")
    return _manager


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateArticleRequest(BaseModel):
    title: str
    content: str = ""
    category: str = "how_to"
    author: str = ""
    tags: list[str] = Field(default_factory=list)


class UpdateArticleRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    tags: list[str] | None = None


class VoteRequest(BaseModel):
    article_id: str
    vote_type: str
    voter: str = ""


class LinkIncidentRequest(BaseModel):
    article_id: str
    incident_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/articles")
async def create_article(
    body: CreateArticleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    article = mgr.create_article(
        title=body.title,
        content=body.content,
        category=body.category,
        author=body.author,
        tags=body.tags,
    )
    return article.model_dump()


@router.get("/articles")
async def list_articles(
    category: str | None = None,
    status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    articles = mgr.list_articles(category=category, status=status)
    return [a.model_dump() for a in articles[-limit:]]


@router.get("/articles/{article_id}")
async def get_article(
    article_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    article = mgr.get_article(article_id)
    if article is None:
        raise HTTPException(404, f"Article '{article_id}' not found")
    return article.model_dump()


@router.put("/articles/{article_id}")
async def update_article(
    article_id: str,
    body: UpdateArticleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    article = mgr.update_article(article_id, **updates)
    if article is None:
        raise HTTPException(404, f"Article '{article_id}' not found")
    return article.model_dump()


@router.put("/articles/{article_id}/publish")
async def publish_article(
    article_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    article = mgr.publish_article(article_id)
    if article is None:
        raise HTTPException(404, f"Article '{article_id}' not found")
    return article.model_dump()


@router.put("/articles/{article_id}/archive")
async def archive_article(
    article_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    article = mgr.archive_article(article_id)
    if article is None:
        raise HTTPException(404, f"Article '{article_id}' not found")
    return article.model_dump()


@router.get("/search")
async def search_articles(
    query: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    articles = mgr.search_articles(query)
    return [a.model_dump() for a in articles]


@router.post("/vote")
async def vote_article(
    body: VoteRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    vote = mgr.vote_article(body.article_id, body.vote_type, body.voter)
    if vote is None:
        raise HTTPException(404, f"Article '{body.article_id}' not found")
    return vote.model_dump()


@router.post("/link-incident")
async def link_incident(
    body: LinkIncidentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    linked = mgr.link_incident(body.article_id, body.incident_id)
    if not linked:
        raise HTTPException(404, f"Article '{body.article_id}' not found")
    return {"linked": True, "article_id": body.article_id, "incident_id": body.incident_id}


@router.get("/top")
async def get_top_articles(
    limit: int = 10,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    articles = mgr.get_top_articles(limit=limit)
    return [a.model_dump() for a in articles]


@router.delete("/articles/{article_id}")
async def delete_article(
    article_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    deleted = mgr.delete_article(article_id)
    if not deleted:
        raise HTTPException(404, f"Article '{article_id}' not found")
    return {"deleted": True, "article_id": article_id}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()
