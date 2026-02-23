"""Tests for Infrastructure Topology Mapper (Phase 17 — F12)."""

from __future__ import annotations

import time

import pytest

from shieldops.topology.infrastructure_map import (
    InfrastructureTopologyMapper,
    NodeType,
    RelationshipType,
    TopologyNode,
    TopologyRelationship,
    TopologyView,
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _mapper(**kw) -> InfrastructureTopologyMapper:
    return InfrastructureTopologyMapper(**kw)


def _node(
    m: InfrastructureTopologyMapper,
    name: str = "api-svc",
    node_type: NodeType = NodeType.SERVICE,
    **kw,
) -> TopologyNode:
    return m.add_node(name=name, node_type=node_type, **kw)


def _rel(
    m: InfrastructureTopologyMapper,
    src: str,
    tgt: str,
    rtype: RelationshipType = RelationshipType.DEPENDS_ON,
    **kw,
) -> TopologyRelationship:
    return m.add_relationship(src, tgt, rtype, **kw)


# -------------------------------------------------------------------
# Enum values
# -------------------------------------------------------------------


class TestEnums:
    def test_node_type_service(self):
        assert NodeType.SERVICE == "service"

    def test_node_type_database(self):
        assert NodeType.DATABASE == "database"

    def test_node_type_cache(self):
        assert NodeType.CACHE == "cache"

    def test_node_type_queue(self):
        assert NodeType.QUEUE == "queue"

    def test_node_type_load_balancer(self):
        assert NodeType.LOAD_BALANCER == "load_balancer"

    def test_node_type_cdn(self):
        assert NodeType.CDN == "cdn"

    def test_node_type_storage(self):
        assert NodeType.STORAGE == "storage"

    def test_node_type_external_api(self):
        assert NodeType.EXTERNAL_API == "external_api"

    def test_rel_depends_on(self):
        assert RelationshipType.DEPENDS_ON == "depends_on"

    def test_rel_provides_data(self):
        assert RelationshipType.PROVIDES_DATA == "provides_data"

    def test_rel_communicates_with(self):
        assert RelationshipType.COMMUNICATES_WITH == "communicates_with"

    def test_rel_load_balances(self):
        assert RelationshipType.LOAD_BALANCES == "load_balances"

    def test_rel_caches_for(self):
        assert RelationshipType.CACHES_FOR == "caches_for"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_topology_node_defaults(self):
        n = TopologyNode(name="web", node_type=NodeType.SERVICE)
        assert n.id
        assert n.name == "web"
        assert n.node_type == NodeType.SERVICE
        assert n.environment == "production"
        assert n.provider == ""
        assert n.metadata == {}
        assert n.health_status == "unknown"
        assert n.created_at > 0
        assert n.updated_at > 0

    def test_topology_node_full(self):
        n = TopologyNode(
            name="pg-primary",
            node_type=NodeType.DATABASE,
            environment="staging",
            provider="aws",
            metadata={"instance": "db.r5.large"},
            health_status="healthy",
        )
        assert n.environment == "staging"
        assert n.provider == "aws"
        assert n.health_status == "healthy"

    def test_topology_relationship_defaults(self):
        r = TopologyRelationship(
            source_id="s1",
            target_id="t1",
            relationship_type=RelationshipType.DEPENDS_ON,
        )
        assert r.id
        assert r.latency_ms == 0.0
        assert r.metadata == {}
        assert r.created_at > 0

    def test_topology_view_defaults(self):
        v = TopologyView()
        assert v.total_nodes == 0
        assert v.total_relationships == 0
        assert v.by_type == {}
        assert v.by_environment == {}
        assert v.critical_paths == []


# -------------------------------------------------------------------
# add_node
# -------------------------------------------------------------------


class TestAddNode:
    def test_basic_add(self):
        m = _mapper()
        n = _node(m)
        assert n.name == "api-svc"
        assert n.node_type == NodeType.SERVICE

    def test_add_all_fields(self):
        m = _mapper()
        n = m.add_node(
            name="redis-cache",
            node_type=NodeType.CACHE,
            environment="staging",
            provider="gcp",
            metadata={"version": "7.2"},
        )
        assert n.environment == "staging"
        assert n.provider == "gcp"
        assert n.metadata["version"] == "7.2"

    def test_unique_ids(self):
        m = _mapper()
        n1 = _node(m, name="svc-1")
        n2 = _node(m, name="svc-2")
        assert n1.id != n2.id

    def test_max_nodes_limit(self):
        m = _mapper(max_nodes=2)
        _node(m, name="n1")
        _node(m, name="n2")
        with pytest.raises(ValueError, match="Maximum nodes limit"):
            _node(m, name="n3")


# -------------------------------------------------------------------
# add_relationship
# -------------------------------------------------------------------


class TestAddRelationship:
    def test_basic_relationship(self):
        m = _mapper()
        s = _node(m, name="web")
        t = _node(m, name="db", node_type=NodeType.DATABASE)
        rel = _rel(m, s.id, t.id)
        assert rel.source_id == s.id
        assert rel.target_id == t.id
        assert rel.relationship_type == RelationshipType.DEPENDS_ON

    def test_relationship_with_latency(self):
        m = _mapper()
        s = _node(m, name="web")
        t = _node(m, name="cache", node_type=NodeType.CACHE)
        rel = _rel(
            m,
            s.id,
            t.id,
            rtype=RelationshipType.CACHES_FOR,
            latency_ms=1.5,
        )
        assert rel.latency_ms == 1.5

    def test_relationship_with_metadata(self):
        m = _mapper()
        s = _node(m, name="web")
        t = _node(m, name="api")
        rel = _rel(
            m,
            s.id,
            t.id,
            metadata={"protocol": "grpc"},
        )
        assert rel.metadata["protocol"] == "grpc"

    def test_source_not_found_raises(self):
        m = _mapper()
        t = _node(m, name="db")
        with pytest.raises(ValueError, match="Source node not found"):
            _rel(m, "ghost", t.id)

    def test_target_not_found_raises(self):
        m = _mapper()
        s = _node(m, name="web")
        with pytest.raises(ValueError, match="Target node not found"):
            _rel(m, s.id, "ghost")

    def test_max_relationships_limit(self):
        m = _mapper(max_relationships=1)
        s = _node(m, name="web")
        t1 = _node(m, name="db", node_type=NodeType.DATABASE)
        t2 = _node(m, name="cache", node_type=NodeType.CACHE)
        _rel(m, s.id, t1.id)
        with pytest.raises(ValueError, match="Maximum relationships limit"):
            _rel(m, s.id, t2.id)


# -------------------------------------------------------------------
# update_node_health
# -------------------------------------------------------------------


class TestUpdateNodeHealth:
    def test_update_existing(self):
        m = _mapper()
        n = _node(m)
        updated = m.update_node_health(n.id, "healthy")
        assert updated is not None
        assert updated.health_status == "healthy"

    def test_update_changes_updated_at(self):
        m = _mapper()
        n = _node(m)
        original = n.updated_at
        time.sleep(0.01)
        m.update_node_health(n.id, "unhealthy")
        assert n.updated_at > original

    def test_update_nonexistent_returns_none(self):
        m = _mapper()
        assert m.update_node_health("ghost", "healthy") is None


# -------------------------------------------------------------------
# remove_node / remove_relationship
# -------------------------------------------------------------------


class TestRemoveNodeAndRelationship:
    def test_remove_existing_node(self):
        m = _mapper()
        n = _node(m)
        assert m.remove_node(n.id) is True
        assert m.get_node(n.id) is None

    def test_remove_nonexistent_node(self):
        m = _mapper()
        assert m.remove_node("ghost") is False

    def test_remove_node_cascades_relationships(self):
        m = _mapper()
        s = _node(m, name="web")
        t = _node(m, name="db", node_type=NodeType.DATABASE)
        _rel(m, s.id, t.id)
        m.remove_node(s.id)
        stats = m.get_stats()
        assert stats["total_relationships"] == 0

    def test_remove_node_leaves_other_rels(self):
        m = _mapper()
        a = _node(m, name="a")
        b = _node(m, name="b")
        c = _node(m, name="c")
        _rel(m, a.id, b.id)
        _rel(m, b.id, c.id)
        m.remove_node(a.id)
        # Only the a->b rel should be removed
        stats = m.get_stats()
        assert stats["total_relationships"] == 1

    def test_remove_existing_relationship(self):
        m = _mapper()
        s = _node(m, name="web")
        t = _node(m, name="db", node_type=NodeType.DATABASE)
        rel = _rel(m, s.id, t.id)
        assert m.remove_relationship(rel.id) is True

    def test_remove_nonexistent_relationship(self):
        m = _mapper()
        assert m.remove_relationship("ghost") is False


# -------------------------------------------------------------------
# get_node / list_nodes
# -------------------------------------------------------------------


class TestNodeAccess:
    def test_get_existing(self):
        m = _mapper()
        n = _node(m)
        found = m.get_node(n.id)
        assert found is not None
        assert found.name == "api-svc"

    def test_get_nonexistent(self):
        m = _mapper()
        assert m.get_node("ghost") is None

    def test_list_all(self):
        m = _mapper()
        _node(m, name="a")
        _node(m, name="b")
        assert len(m.list_nodes()) == 2

    def test_list_filter_by_type(self):
        m = _mapper()
        _node(m, name="svc", node_type=NodeType.SERVICE)
        _node(m, name="db", node_type=NodeType.DATABASE)
        svcs = m.list_nodes(node_type=NodeType.SERVICE)
        assert len(svcs) == 1
        assert svcs[0].name == "svc"

    def test_list_filter_by_environment(self):
        m = _mapper()
        _node(m, name="prod-svc", environment="production")
        _node(m, name="stg-svc", environment="staging")
        prod = m.list_nodes(environment="production")
        assert len(prod) == 1

    def test_list_empty(self):
        m = _mapper()
        assert m.list_nodes() == []


# -------------------------------------------------------------------
# get_node_dependencies / get_node_dependents
# -------------------------------------------------------------------


class TestDependencies:
    def test_get_dependencies(self):
        m = _mapper()
        web = _node(m, name="web")
        db = _node(m, name="db", node_type=NodeType.DATABASE)
        _rel(m, web.id, db.id, RelationshipType.DEPENDS_ON)
        deps = m.get_node_dependencies(web.id)
        assert len(deps) == 1
        assert deps[0].id == db.id

    def test_get_dependencies_empty(self):
        m = _mapper()
        web = _node(m, name="web")
        assert m.get_node_dependencies(web.id) == []

    def test_only_depends_on_counted(self):
        m = _mapper()
        web = _node(m, name="web")
        cache = _node(m, name="cache", node_type=NodeType.CACHE)
        _rel(
            m,
            web.id,
            cache.id,
            RelationshipType.COMMUNICATES_WITH,
        )
        assert m.get_node_dependencies(web.id) == []

    def test_get_dependents(self):
        m = _mapper()
        db = _node(m, name="db", node_type=NodeType.DATABASE)
        web = _node(m, name="web")
        _rel(m, web.id, db.id, RelationshipType.DEPENDS_ON)
        dependents = m.get_node_dependents(db.id)
        assert len(dependents) == 1
        assert dependents[0].id == web.id

    def test_get_dependents_empty(self):
        m = _mapper()
        db = _node(m, name="db", node_type=NodeType.DATABASE)
        assert m.get_node_dependents(db.id) == []


# -------------------------------------------------------------------
# get_topology_view
# -------------------------------------------------------------------


class TestTopologyView:
    def test_empty_view(self):
        m = _mapper()
        v = m.get_topology_view()
        assert v.total_nodes == 0
        assert v.total_relationships == 0

    def test_view_counts(self):
        m = _mapper()
        s = _node(m, name="web")
        t = _node(m, name="db", node_type=NodeType.DATABASE)
        _rel(m, s.id, t.id)
        v = m.get_topology_view()
        assert v.total_nodes == 2
        assert v.total_relationships == 1

    def test_view_by_type(self):
        m = _mapper()
        _node(m, name="web")
        _node(m, name="api")
        _node(m, name="db", node_type=NodeType.DATABASE)
        v = m.get_topology_view()
        assert v.by_type["service"] == 2
        assert v.by_type["database"] == 1

    def test_view_by_environment(self):
        m = _mapper()
        _node(m, name="prod", environment="production")
        _node(m, name="stg", environment="staging")
        v = m.get_topology_view()
        assert v.by_environment["production"] == 1
        assert v.by_environment["staging"] == 1

    def test_view_filter_by_environment(self):
        m = _mapper()
        _node(m, name="prod", environment="production")
        _node(m, name="stg", environment="staging")
        v = m.get_topology_view(environment="production")
        assert v.total_nodes == 1

    def test_critical_paths_simple_chain(self):
        m = _mapper()
        a = _node(m, name="a")
        b = _node(m, name="b")
        c = _node(m, name="c")
        _rel(m, a.id, b.id, RelationshipType.DEPENDS_ON)
        _rel(m, b.id, c.id, RelationshipType.DEPENDS_ON)
        v = m.get_topology_view()
        assert len(v.critical_paths) >= 1
        found = any(len(p) == 3 and p[0] == a.id for p in v.critical_paths)
        assert found, "Expected a->b->c critical path"

    def test_no_critical_paths_without_depends_on(self):
        m = _mapper()
        a = _node(m, name="a")
        b = _node(m, name="b")
        _rel(
            m,
            a.id,
            b.id,
            RelationshipType.COMMUNICATES_WITH,
        )
        v = m.get_topology_view()
        assert v.critical_paths == []

    def test_env_filter_excludes_cross_env_rels(self):
        m = _mapper()
        p = _node(m, name="prod-svc", environment="production")
        s = _node(m, name="stg-svc", environment="staging")
        _rel(m, p.id, s.id)
        v = m.get_topology_view(environment="production")
        assert v.total_relationships == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        m = _mapper()
        s = m.get_stats()
        assert s["total_nodes"] == 0
        assert s["total_relationships"] == 0
        assert s["healthy_nodes"] == 0
        assert s["unhealthy_nodes"] == 0
        assert s["environments"] == []
        assert s["node_types"] == []

    def test_populated_stats(self):
        m = _mapper()
        web = _node(m, name="web")
        db = _node(m, name="db", node_type=NodeType.DATABASE)
        _rel(m, web.id, db.id)
        m.update_node_health(web.id, "healthy")
        m.update_node_health(db.id, "unhealthy")
        s = m.get_stats()
        assert s["total_nodes"] == 2
        assert s["total_relationships"] == 1
        assert s["healthy_nodes"] == 1
        assert s["unhealthy_nodes"] == 1
        assert "production" in s["environments"]
        assert "service" in s["node_types"]
        assert "database" in s["node_types"]

    def test_multiple_environments(self):
        m = _mapper()
        _node(m, name="prod", environment="production")
        _node(m, name="stg", environment="staging")
        s = m.get_stats()
        assert len(s["environments"]) == 2
