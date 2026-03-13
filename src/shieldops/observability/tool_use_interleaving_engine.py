"""Tool Use Interleaving Engine —
optimize reasoning/tool-call interleaving in investigations,
recommend next actions, compute tool call ROI."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TurnType(StrEnum):
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    SYNTHESIS = "synthesis"
    VERIFICATION = "verification"


class InterleavingPattern(StrEnum):
    REASON_FIRST = "reason_first"
    TOOL_FIRST = "tool_first"
    ALTERNATING = "alternating"
    ADAPTIVE = "adaptive"


class ToolCallOutcome(StrEnum):
    INFORMATIVE = "informative"
    REDUNDANT = "redundant"
    FAILED = "failed"
    DECISIVE = "decisive"


# --- Models ---


class ToolUseInterleavingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    turn_type: TurnType = TurnType.REASONING
    interleaving_pattern: InterleavingPattern = InterleavingPattern.ALTERNATING
    tool_call_outcome: ToolCallOutcome = ToolCallOutcome.INFORMATIVE
    information_gain: float = 0.0
    turn_duration_ms: float = 0.0
    tool_name: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ToolUseInterleavingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    turn_type: TurnType = TurnType.REASONING
    interleaving_pattern: InterleavingPattern = InterleavingPattern.ALTERNATING
    tool_call_outcome: ToolCallOutcome = ToolCallOutcome.INFORMATIVE
    roi_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ToolUseInterleavingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_information_gain: float = 0.0
    by_turn_type: dict[str, int] = Field(default_factory=dict)
    by_interleaving_pattern: dict[str, int] = Field(default_factory=dict)
    by_tool_call_outcome: dict[str, int] = Field(default_factory=dict)
    top_tools_by_roi: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ToolUseInterleavingEngine:
    """Optimize reasoning/tool-call interleaving in investigations,
    recommend next actions, compute tool call ROI."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ToolUseInterleavingRecord] = []
        self._analyses: dict[str, ToolUseInterleavingAnalysis] = {}
        logger.info("tool_use_interleaving_engine.init", max_records=max_records)

    def add_record(
        self,
        session_id: str = "",
        turn_type: TurnType = TurnType.REASONING,
        interleaving_pattern: InterleavingPattern = InterleavingPattern.ALTERNATING,
        tool_call_outcome: ToolCallOutcome = ToolCallOutcome.INFORMATIVE,
        information_gain: float = 0.0,
        turn_duration_ms: float = 0.0,
        tool_name: str = "",
        description: str = "",
    ) -> ToolUseInterleavingRecord:
        record = ToolUseInterleavingRecord(
            session_id=session_id,
            turn_type=turn_type,
            interleaving_pattern=interleaving_pattern,
            tool_call_outcome=tool_call_outcome,
            information_gain=information_gain,
            turn_duration_ms=turn_duration_ms,
            tool_name=tool_name,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "tool_use_interleaving.record_added",
            record_id=record.id,
            session_id=session_id,
        )
        return record

    def process(self, key: str) -> ToolUseInterleavingAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        outcome_weights = {
            "decisive": 4,
            "informative": 3,
            "redundant": 1,
            "failed": 0,
        }
        w = outcome_weights.get(rec.tool_call_outcome.value, 1)
        roi = round(
            (rec.information_gain * w) / max(rec.turn_duration_ms, 1.0) * 1000,
            4,
        )
        analysis = ToolUseInterleavingAnalysis(
            session_id=rec.session_id,
            turn_type=rec.turn_type,
            interleaving_pattern=rec.interleaving_pattern,
            tool_call_outcome=rec.tool_call_outcome,
            roi_score=roi,
            description=(
                f"Session {rec.session_id} turn={rec.turn_type.value} "
                f"outcome={rec.tool_call_outcome.value}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ToolUseInterleavingReport:
        by_tt: dict[str, int] = {}
        by_ip: dict[str, int] = {}
        by_tco: dict[str, int] = {}
        gains: list[float] = []
        for r in self._records:
            k = r.turn_type.value
            by_tt[k] = by_tt.get(k, 0) + 1
            k2 = r.interleaving_pattern.value
            by_ip[k2] = by_ip.get(k2, 0) + 1
            k3 = r.tool_call_outcome.value
            by_tco[k3] = by_tco.get(k3, 0) + 1
            gains.append(r.information_gain)
        avg_gain = round(sum(gains) / len(gains), 4) if gains else 0.0
        tool_gains: dict[str, float] = {}
        for r in self._records:
            if r.tool_name:
                tool_gains[r.tool_name] = tool_gains.get(r.tool_name, 0.0) + r.information_gain
        top_tools = sorted(tool_gains, key=lambda x: tool_gains[x], reverse=True)[:10]
        recs: list[str] = []
        redundant = by_tco.get("redundant", 0)
        if redundant:
            recs.append(f"{redundant} redundant tool calls detected — optimize interleaving")
        failed = by_tco.get("failed", 0)
        if failed:
            recs.append(f"{failed} failed tool calls need investigation")
        if not recs:
            recs.append("Tool use interleaving is well-optimized")
        return ToolUseInterleavingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_information_gain=avg_gain,
            by_turn_type=by_tt,
            by_interleaving_pattern=by_ip,
            by_tool_call_outcome=by_tco,
            top_tools_by_roi=top_tools,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.turn_type.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "turn_type_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("tool_use_interleaving_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def analyze_interleaving_pattern(self) -> list[dict[str, Any]]:
        """Analyze interleaving patterns by session."""
        session_map: dict[str, list[ToolUseInterleavingRecord]] = {}
        for r in self._records:
            session_map.setdefault(r.session_id, []).append(r)
        results: list[dict[str, Any]] = []
        for sid, sess_recs in session_map.items():
            pattern_counts: dict[str, int] = {}
            for r in sess_recs:
                pv = r.interleaving_pattern.value
                pattern_counts[pv] = pattern_counts.get(pv, 0) + 1
            dominant = max(pattern_counts, key=lambda x: pattern_counts[x])
            avg_gain = sum(r.information_gain for r in sess_recs) / len(sess_recs)
            results.append(
                {
                    "session_id": sid,
                    "dominant_pattern": dominant,
                    "avg_information_gain": round(avg_gain, 4),
                    "turn_count": len(sess_recs),
                    "pattern_counts": pattern_counts,
                }
            )
        results.sort(key=lambda x: x["avg_information_gain"], reverse=True)
        return results

    def recommend_next_action(self) -> list[dict[str, Any]]:
        """Recommend next action type per session based on history."""
        session_map: dict[str, list[ToolUseInterleavingRecord]] = {}
        for r in self._records:
            session_map.setdefault(r.session_id, []).append(r)
        results: list[dict[str, Any]] = []
        for sid, sess_recs in session_map.items():
            last = sess_recs[-1]
            if last.turn_type == TurnType.REASONING:
                recommended = TurnType.TOOL_CALL.value
                rationale = "Follow reasoning with tool call for data"
            elif last.turn_type == TurnType.TOOL_CALL:
                if last.tool_call_outcome == ToolCallOutcome.DECISIVE:
                    recommended = TurnType.SYNTHESIS.value
                    rationale = "Decisive tool result — synthesize findings"
                else:
                    recommended = TurnType.REASONING.value
                    rationale = "Non-decisive result — reason about next step"
            elif last.turn_type == TurnType.SYNTHESIS:
                recommended = TurnType.VERIFICATION.value
                rationale = "Verify synthesized conclusions"
            else:
                recommended = TurnType.REASONING.value
                rationale = "Post-verification — reason about completeness"
            results.append(
                {
                    "session_id": sid,
                    "last_turn_type": last.turn_type.value,
                    "recommended_next": recommended,
                    "rationale": rationale,
                }
            )
        return results

    def compute_tool_call_roi(self) -> list[dict[str, Any]]:
        """Compute ROI per tool name across all sessions."""
        outcome_weights = {
            "decisive": 4,
            "informative": 3,
            "redundant": 1,
            "failed": 0,
        }
        tool_data: dict[str, dict[str, float]] = {}
        for r in self._records:
            if r.turn_type != TurnType.TOOL_CALL:
                continue
            tn = r.tool_name or "unknown"
            tool_data.setdefault(tn, {"gain": 0.0, "duration": 0.0, "count": 0.0})
            w = outcome_weights.get(r.tool_call_outcome.value, 1)
            tool_data[tn]["gain"] += r.information_gain * w
            tool_data[tn]["duration"] += max(r.turn_duration_ms, 1.0)
            tool_data[tn]["count"] += 1.0
        results: list[dict[str, Any]] = []
        for tn, td in tool_data.items():
            roi = round((td["gain"] / td["duration"]) * 1000, 4)
            results.append(
                {
                    "tool_name": tn,
                    "roi_score": roi,
                    "total_calls": int(td["count"]),
                    "avg_gain": round(td["gain"] / td["count"], 4),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["roi_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
