"""Tests for shieldops.security.lateral_movement_graph_analyzer — LateralMovementGraphAnalyzer."""

from __future__ import annotations

from shieldops.security.lateral_movement_graph_analyzer import (
    GraphMetric,
    LateralMovementGraphAnalyzer,
    LateralMovementReport,
    MovementAnalysis,
    MovementRecord,
    MovementType,
    PathRisk,
)


def _engine(**kw) -> LateralMovementGraphAnalyzer:
    return LateralMovementGraphAnalyzer(**kw)


class TestEnums:
    def test_movement_rdp(self):
        assert MovementType.RDP == "rdp"

    def test_movement_ssh(self):
        assert MovementType.SSH == "ssh"

    def test_movement_smb(self):
        assert MovementType.SMB == "smb"

    def test_movement_wmi(self):
        assert MovementType.WMI == "wmi"

    def test_movement_psexec(self):
        assert MovementType.PSEXEC == "psexec"

    def test_risk_low(self):
        assert PathRisk.LOW == "low"

    def test_risk_medium(self):
        assert PathRisk.MEDIUM == "medium"

    def test_risk_high(self):
        assert PathRisk.HIGH == "high"

    def test_risk_critical(self):
        assert PathRisk.CRITICAL == "critical"

    def test_risk_benign(self):
        assert PathRisk.BENIGN == "benign"

    def test_metric_centrality(self):
        assert GraphMetric.CENTRALITY == "centrality"

    def test_metric_betweenness(self):
        assert GraphMetric.BETWEENNESS == "betweenness"

    def test_metric_path_length(self):
        assert GraphMetric.PATH_LENGTH == "path_length"

    def test_metric_clustering(self):
        assert GraphMetric.CLUSTERING == "clustering"

    def test_metric_connectivity(self):
        assert GraphMetric.CONNECTIVITY == "connectivity"


class TestModels:
    def test_record_defaults(self):
        r = MovementRecord()
        assert r.id
        assert r.source_host == ""
        assert r.movement_type == MovementType.RDP
        assert r.path_risk == PathRisk.BENIGN
        assert r.graph_metric == GraphMetric.CENTRALITY
        assert r.movement_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = MovementAnalysis()
        assert a.id
        assert a.source_host == ""
        assert a.movement_type == MovementType.RDP
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = LateralMovementReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_movement_score == 0.0
        assert r.by_movement_type == {}
        assert r.by_path_risk == {}
        assert r.by_graph_metric == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_movement(
            source_host="lateral-001",
            movement_type=MovementType.SSH,
            path_risk=PathRisk.HIGH,
            graph_metric=GraphMetric.BETWEENNESS,
            movement_score=85.0,
            service="network-svc",
            team="security",
        )
        assert r.source_host == "lateral-001"
        assert r.movement_type == MovementType.SSH
        assert r.movement_score == 85.0
        assert r.service == "network-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_movement(source_host=f"mov-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_movement(source_host="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_movement(source_host="a")
        eng.record_movement(source_host="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_movement_type(self):
        eng = _engine()
        eng.record_movement(source_host="a", movement_type=MovementType.RDP)
        eng.record_movement(source_host="b", movement_type=MovementType.SSH)
        assert len(eng.list_records(movement_type=MovementType.RDP)) == 1

    def test_filter_by_path_risk(self):
        eng = _engine()
        eng.record_movement(source_host="a", path_risk=PathRisk.LOW)
        eng.record_movement(source_host="b", path_risk=PathRisk.HIGH)
        assert len(eng.list_records(path_risk=PathRisk.LOW)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_movement(source_host="a", team="sec")
        eng.record_movement(source_host="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_movement(source_host=f"m-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            source_host="test",
            analysis_score=88.5,
            breached=True,
            description="lateral movement detected",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(source_host=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_movement(
            source_host="a",
            movement_type=MovementType.RDP,
            movement_score=90.0,
        )
        eng.record_movement(
            source_host="b",
            movement_type=MovementType.RDP,
            movement_score=70.0,
        )
        result = eng.analyze_distribution()
        assert "rdp" in result
        assert result["rdp"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_movement(source_host="a", movement_score=60.0)
        eng.record_movement(source_host="b", movement_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_movement(source_host="a", movement_score=50.0)
        eng.record_movement(source_host="b", movement_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["movement_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_movement(source_host="a", service="auth", movement_score=90.0)
        eng.record_movement(source_host="b", service="api", movement_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(source_host="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(source_host="a", analysis_score=20.0)
        eng.add_analysis(source_host="b", analysis_score=20.0)
        eng.add_analysis(source_host="c", analysis_score=80.0)
        eng.add_analysis(source_host="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_movement(source_host="test", movement_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_movement(source_host="test")
        eng.add_analysis(source_host="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_movement(source_host="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
