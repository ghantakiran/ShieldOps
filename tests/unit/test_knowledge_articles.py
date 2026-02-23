"""Tests for shieldops.knowledge.article_manager — KnowledgeBaseManager."""

from __future__ import annotations

from shieldops.knowledge.article_manager import (
    ArticleCategory,
    ArticleStatus,
    ArticleVote,
    KnowledgeArticle,
    KnowledgeBaseManager,
    VoteType,
)


def _manager(**kw) -> KnowledgeBaseManager:
    return KnowledgeBaseManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # ArticleStatus (4 values)

    def test_article_status_draft(self):
        assert ArticleStatus.DRAFT == "draft"

    def test_article_status_published(self):
        assert ArticleStatus.PUBLISHED == "published"

    def test_article_status_archived(self):
        assert ArticleStatus.ARCHIVED == "archived"

    def test_article_status_under_review(self):
        assert ArticleStatus.UNDER_REVIEW == "under_review"

    # ArticleCategory (5 values)

    def test_article_category_troubleshooting(self):
        assert ArticleCategory.TROUBLESHOOTING == "troubleshooting"

    def test_article_category_runbook(self):
        assert ArticleCategory.RUNBOOK == "runbook"

    def test_article_category_architecture(self):
        assert ArticleCategory.ARCHITECTURE == "architecture"

    def test_article_category_postmortem(self):
        assert ArticleCategory.POSTMORTEM == "postmortem"

    def test_article_category_how_to(self):
        assert ArticleCategory.HOW_TO == "how_to"

    # VoteType (2 values)

    def test_vote_type_helpful(self):
        assert VoteType.HELPFUL == "helpful"

    def test_vote_type_not_helpful(self):
        assert VoteType.NOT_HELPFUL == "not_helpful"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_knowledge_article_defaults(self):
        article = KnowledgeArticle(title="Test Article")
        assert article.id
        assert article.title == "Test Article"
        assert article.content == ""
        assert article.category == ArticleCategory.HOW_TO
        assert article.status == ArticleStatus.DRAFT
        assert article.author == ""
        assert article.tags == []
        assert article.linked_incidents == []
        assert article.helpful_votes == 0
        assert article.not_helpful_votes == 0
        assert article.created_at > 0
        assert article.updated_at > 0

    def test_article_vote_defaults(self):
        vote = ArticleVote(article_id="a-1", vote_type=VoteType.HELPFUL)
        assert vote.id
        assert vote.article_id == "a-1"
        assert vote.vote_type == VoteType.HELPFUL
        assert vote.voter == ""
        assert vote.voted_at > 0


# ---------------------------------------------------------------------------
# create_article
# ---------------------------------------------------------------------------


class TestCreateArticle:
    def test_basic_create(self):
        mgr = _manager()
        article = mgr.create_article("DNS Resolution Guide")
        assert article.title == "DNS Resolution Guide"
        assert article.category == ArticleCategory.HOW_TO
        assert article.status == ArticleStatus.DRAFT
        assert mgr.get_article(article.id) is not None

    def test_create_assigns_unique_ids(self):
        mgr = _manager()
        a1 = mgr.create_article("Article A")
        a2 = mgr.create_article("Article B")
        assert a1.id != a2.id

    def test_create_with_extra_fields(self):
        mgr = _manager()
        article = mgr.create_article(
            "Scaling Playbook",
            content="Steps to scale the cluster",
            category=ArticleCategory.RUNBOOK,
            author="sre-team",
            tags=["scaling", "k8s"],
        )
        assert article.content == "Steps to scale the cluster"
        assert article.category == ArticleCategory.RUNBOOK
        assert article.author == "sre-team"
        assert article.tags == ["scaling", "k8s"]

    def test_evicts_at_max_articles(self):
        mgr = _manager(max_articles=3)
        ids = []
        for i in range(4):
            article = mgr.create_article(f"Article {i}")
            ids.append(article.id)
        assert mgr.get_article(ids[0]) is None
        assert mgr.get_article(ids[3]) is not None
        assert len(mgr.list_articles()) == 3


# ---------------------------------------------------------------------------
# update_article
# ---------------------------------------------------------------------------


class TestUpdateArticle:
    def test_basic_update(self):
        mgr = _manager()
        article = mgr.create_article("Original Title")
        result = mgr.update_article(article.id, title="Updated Title", content="new body")
        assert result is not None
        assert result.title == "Updated Title"
        assert result.content == "new body"

    def test_update_not_found(self):
        mgr = _manager()
        result = mgr.update_article("nonexistent", title="nope")
        assert result is None


# ---------------------------------------------------------------------------
# publish_article
# ---------------------------------------------------------------------------


class TestPublishArticle:
    def test_basic_publish(self):
        mgr = _manager()
        article = mgr.create_article("Draft Article")
        assert article.status == ArticleStatus.DRAFT
        result = mgr.publish_article(article.id)
        assert result is not None
        assert result.status == ArticleStatus.PUBLISHED

    def test_publish_not_found(self):
        mgr = _manager()
        assert mgr.publish_article("nonexistent") is None


# ---------------------------------------------------------------------------
# archive_article
# ---------------------------------------------------------------------------


class TestArchiveArticle:
    def test_basic_archive(self):
        mgr = _manager()
        article = mgr.create_article("Active Article")
        result = mgr.archive_article(article.id)
        assert result is not None
        assert result.status == ArticleStatus.ARCHIVED

    def test_archive_not_found(self):
        mgr = _manager()
        assert mgr.archive_article("nonexistent") is None


# ---------------------------------------------------------------------------
# search_articles
# ---------------------------------------------------------------------------


class TestSearchArticles:
    def test_search_by_title(self):
        mgr = _manager()
        mgr.create_article("DNS Resolution Guide")
        mgr.create_article("Memory Leak Debugging")
        results = mgr.search_articles("DNS")
        assert len(results) == 1
        assert results[0].title == "DNS Resolution Guide"

    def test_search_by_content(self):
        mgr = _manager()
        mgr.create_article("Incident Guide", content="Steps for database failover")
        mgr.create_article("Other Guide", content="Steps for cache flush")
        results = mgr.search_articles("database")
        assert len(results) == 1
        assert "database" in results[0].content

    def test_search_case_insensitive(self):
        mgr = _manager()
        mgr.create_article("Kubernetes Scaling")
        results = mgr.search_articles("kubernetes")
        assert len(results) == 1
        results_upper = mgr.search_articles("KUBERNETES")
        assert len(results_upper) == 1

    def test_search_no_results(self):
        mgr = _manager()
        mgr.create_article("DNS Guide")
        results = mgr.search_articles("nonexistent topic")
        assert results == []


# ---------------------------------------------------------------------------
# vote_article
# ---------------------------------------------------------------------------


class TestVoteArticle:
    def test_helpful_vote(self):
        mgr = _manager()
        article = mgr.create_article("Good Article")
        vote = mgr.vote_article(article.id, VoteType.HELPFUL, voter="user-1")
        assert vote is not None
        assert vote.vote_type == VoteType.HELPFUL
        assert vote.voter == "user-1"
        updated = mgr.get_article(article.id)
        assert updated.helpful_votes == 1

    def test_not_helpful_vote(self):
        mgr = _manager()
        article = mgr.create_article("Bad Article")
        vote = mgr.vote_article(article.id, VoteType.NOT_HELPFUL)
        assert vote is not None
        assert vote.vote_type == VoteType.NOT_HELPFUL
        updated = mgr.get_article(article.id)
        assert updated.not_helpful_votes == 1

    def test_vote_not_found(self):
        mgr = _manager()
        result = mgr.vote_article("nonexistent", VoteType.HELPFUL)
        assert result is None

    def test_vote_trims_at_max(self):
        mgr = _manager(max_votes=3)
        article = mgr.create_article("Popular Article")
        for _ in range(4):
            mgr.vote_article(article.id, VoteType.HELPFUL)
        # Internal votes list trimmed to max_votes
        assert len(mgr._votes) == 3


# ---------------------------------------------------------------------------
# get_article
# ---------------------------------------------------------------------------


class TestGetArticle:
    def test_found(self):
        mgr = _manager()
        article = mgr.create_article("Test Article")
        result = mgr.get_article(article.id)
        assert result is not None
        assert result.id == article.id

    def test_not_found(self):
        mgr = _manager()
        assert mgr.get_article("nonexistent") is None


# ---------------------------------------------------------------------------
# list_articles
# ---------------------------------------------------------------------------


class TestListArticles:
    def test_list_all(self):
        mgr = _manager()
        mgr.create_article("A")
        mgr.create_article("B")
        mgr.create_article("C")
        assert len(mgr.list_articles()) == 3

    def test_filter_by_category(self):
        mgr = _manager()
        mgr.create_article("A", category=ArticleCategory.RUNBOOK)
        mgr.create_article("B", category=ArticleCategory.POSTMORTEM)
        mgr.create_article("C", category=ArticleCategory.RUNBOOK)
        results = mgr.list_articles(category=ArticleCategory.RUNBOOK)
        assert len(results) == 2
        assert all(a.category == ArticleCategory.RUNBOOK for a in results)

    def test_filter_by_status(self):
        mgr = _manager()
        a1 = mgr.create_article("Draft One")
        mgr.create_article("Draft Two")
        mgr.publish_article(a1.id)
        results = mgr.list_articles(status=ArticleStatus.PUBLISHED)
        assert len(results) == 1
        assert results[0].status == ArticleStatus.PUBLISHED


# ---------------------------------------------------------------------------
# get_top_articles
# ---------------------------------------------------------------------------


class TestGetTopArticles:
    def test_basic_top_articles(self):
        mgr = _manager()
        a1 = mgr.create_article("Popular")
        a2 = mgr.create_article("Less Popular")
        mgr.publish_article(a1.id)
        mgr.publish_article(a2.id)
        for _ in range(5):
            mgr.vote_article(a1.id, VoteType.HELPFUL)
        for _ in range(2):
            mgr.vote_article(a2.id, VoteType.HELPFUL)
        top = mgr.get_top_articles(limit=10)
        assert len(top) == 2
        assert top[0].id == a1.id
        assert top[0].helpful_votes == 5

    def test_empty_top_articles(self):
        mgr = _manager()
        top = mgr.get_top_articles()
        assert top == []


# ---------------------------------------------------------------------------
# link_incident
# ---------------------------------------------------------------------------


class TestLinkIncident:
    def test_basic_link(self):
        mgr = _manager()
        article = mgr.create_article("Incident Guide")
        result = mgr.link_incident(article.id, "INC-001")
        assert result is True
        updated = mgr.get_article(article.id)
        assert "INC-001" in updated.linked_incidents

    def test_link_not_found(self):
        mgr = _manager()
        result = mgr.link_incident("nonexistent", "INC-001")
        assert result is False

    def test_link_duplicate_ignored(self):
        mgr = _manager()
        article = mgr.create_article("Incident Guide")
        mgr.link_incident(article.id, "INC-001")
        mgr.link_incident(article.id, "INC-001")
        updated = mgr.get_article(article.id)
        assert updated.linked_incidents.count("INC-001") == 1


# ---------------------------------------------------------------------------
# delete_article
# ---------------------------------------------------------------------------


class TestDeleteArticle:
    def test_delete_success(self):
        mgr = _manager()
        article = mgr.create_article("Deletable Article")
        assert mgr.delete_article(article.id) is True
        assert mgr.get_article(article.id) is None

    def test_delete_not_found(self):
        mgr = _manager()
        assert mgr.delete_article("nonexistent") is False


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        mgr = _manager()
        stats = mgr.get_stats()
        assert stats["total_articles"] == 0
        assert stats["total_votes"] == 0
        assert stats["total_helpful"] == 0
        assert stats["total_not_helpful"] == 0
        assert stats["category_distribution"] == {}
        assert stats["status_distribution"] == {}

    def test_stats_populated(self):
        mgr = _manager()
        a1 = mgr.create_article("A", category=ArticleCategory.RUNBOOK)
        mgr.create_article("B", category=ArticleCategory.POSTMORTEM)
        mgr.vote_article(a1.id, VoteType.HELPFUL)
        mgr.vote_article(a1.id, VoteType.NOT_HELPFUL)

        stats = mgr.get_stats()
        assert stats["total_articles"] == 2
        assert stats["total_votes"] == 2
        assert stats["total_helpful"] == 1
        assert stats["total_not_helpful"] == 1
        assert stats["category_distribution"][ArticleCategory.RUNBOOK] == 1
        assert stats["category_distribution"][ArticleCategory.POSTMORTEM] == 1
        assert stats["status_distribution"][ArticleStatus.DRAFT] == 2
