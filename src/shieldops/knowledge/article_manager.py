"""Knowledge Base Article Manager — curate, search, rank operational knowledge articles."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ArticleStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    UNDER_REVIEW = "under_review"


class ArticleCategory(StrEnum):
    TROUBLESHOOTING = "troubleshooting"
    RUNBOOK = "runbook"
    ARCHITECTURE = "architecture"
    POSTMORTEM = "postmortem"
    HOW_TO = "how_to"


class VoteType(StrEnum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"


# --- Models ---


class KnowledgeArticle(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str = ""
    category: ArticleCategory = ArticleCategory.HOW_TO
    status: ArticleStatus = ArticleStatus.DRAFT
    author: str = ""
    tags: list[str] = Field(default_factory=list)
    linked_incidents: list[str] = Field(default_factory=list)
    helpful_votes: int = 0
    not_helpful_votes: int = 0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ArticleVote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    article_id: str
    vote_type: VoteType
    voter: str = ""
    voted_at: float = Field(default_factory=time.time)


# --- Manager ---


class KnowledgeBaseManager:
    """Curates, searches, and ranks operational knowledge articles."""

    def __init__(
        self,
        max_articles: int = 5000,
        max_votes: int = 50000,
    ) -> None:
        self._max_articles = max_articles
        self._max_votes = max_votes
        self._articles: dict[str, KnowledgeArticle] = {}
        self._votes: list[ArticleVote] = []
        logger.info(
            "knowledge_base.initialized",
            max_articles=max_articles,
            max_votes=max_votes,
        )

    def create_article(
        self,
        title: str,
        content: str = "",
        category: ArticleCategory = ArticleCategory.HOW_TO,
        author: str = "",
        **kw: Any,
    ) -> KnowledgeArticle:
        """Create a new knowledge article."""
        article = KnowledgeArticle(
            title=title,
            content=content,
            category=category,
            author=author,
            **kw,
        )
        self._articles[article.id] = article
        if len(self._articles) > self._max_articles:
            oldest = next(iter(self._articles))
            del self._articles[oldest]
        logger.info(
            "knowledge_base.article_created",
            article_id=article.id,
            title=title,
            category=category,
        )
        return article

    def update_article(
        self,
        article_id: str,
        **updates: Any,
    ) -> KnowledgeArticle | None:
        """Update an existing article."""
        article = self._articles.get(article_id)
        if article is None:
            return None
        for key, value in updates.items():
            if hasattr(article, key):
                setattr(article, key, value)
        article.updated_at = time.time()
        return article

    def publish_article(self, article_id: str) -> KnowledgeArticle | None:
        """Publish a draft article."""
        article = self._articles.get(article_id)
        if article is None:
            return None
        article.status = ArticleStatus.PUBLISHED
        article.updated_at = time.time()
        logger.info("knowledge_base.article_published", article_id=article_id)
        return article

    def archive_article(self, article_id: str) -> KnowledgeArticle | None:
        """Archive an article."""
        article = self._articles.get(article_id)
        if article is None:
            return None
        article.status = ArticleStatus.ARCHIVED
        article.updated_at = time.time()
        return article

    def search_articles(self, query: str) -> list[KnowledgeArticle]:
        """Search articles by title/content substring."""
        q = query.lower()
        return [
            a for a in self._articles.values() if q in a.title.lower() or q in a.content.lower()
        ]

    def vote_article(
        self,
        article_id: str,
        vote_type: VoteType,
        voter: str = "",
    ) -> ArticleVote | None:
        """Vote on an article."""
        article = self._articles.get(article_id)
        if article is None:
            return None
        vote = ArticleVote(article_id=article_id, vote_type=vote_type, voter=voter)
        self._votes.append(vote)
        if vote_type == VoteType.HELPFUL:
            article.helpful_votes += 1
        else:
            article.not_helpful_votes += 1
        if len(self._votes) > self._max_votes:
            self._votes = self._votes[-self._max_votes :]
        return vote

    def get_article(self, article_id: str) -> KnowledgeArticle | None:
        """Retrieve an article by ID."""
        return self._articles.get(article_id)

    def list_articles(
        self,
        category: ArticleCategory | None = None,
        status: ArticleStatus | None = None,
    ) -> list[KnowledgeArticle]:
        """List articles with optional filters."""
        results = list(self._articles.values())
        if category is not None:
            results = [a for a in results if a.category == category]
        if status is not None:
            results = [a for a in results if a.status == status]
        return results

    def get_top_articles(self, limit: int = 10) -> list[KnowledgeArticle]:
        """Get top-rated articles by helpful votes."""
        published = [a for a in self._articles.values() if a.status == ArticleStatus.PUBLISHED]
        published.sort(key=lambda a: a.helpful_votes, reverse=True)
        return published[:limit]

    def link_incident(self, article_id: str, incident_id: str) -> bool:
        """Link an incident to an article."""
        article = self._articles.get(article_id)
        if article is None:
            return False
        if incident_id not in article.linked_incidents:
            article.linked_incidents.append(incident_id)
        return True

    def delete_article(self, article_id: str) -> bool:
        """Delete an article."""
        if article_id in self._articles:
            del self._articles[article_id]
            logger.info("knowledge_base.article_deleted", article_id=article_id)
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        category_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for a in self._articles.values():
            category_counts[a.category] = category_counts.get(a.category, 0) + 1
            status_counts[a.status] = status_counts.get(a.status, 0) + 1
        total_helpful = sum(a.helpful_votes for a in self._articles.values())
        total_not_helpful = sum(a.not_helpful_votes for a in self._articles.values())
        return {
            "total_articles": len(self._articles),
            "total_votes": len(self._votes),
            "total_helpful": total_helpful,
            "total_not_helpful": total_not_helpful,
            "category_distribution": category_counts,
            "status_distribution": status_counts,
        }
