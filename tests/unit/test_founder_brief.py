"""Tests for deterministic founder brief."""

from __future__ import annotations

from tests.unit.test_intelligence_engine import _metrics_and_data
from src.dashboard.founder_brief import generate_founder_brief
from src.dashboard.intelligence_engine import build_intelligence


def test_founder_brief_structure():
    metrics, data = _metrics_and_data()
    intel = build_intelligence(data, metrics)
    brief = generate_founder_brief(metrics, intel)
    assert brief["title"] == "FOUNDER BRIEF"
    assert "financial" in brief
    assert "founder_actions" in brief
    assert len(brief.get("risks", [])) <= 3
    assert "historical trend unavailable" in brief.get("snapshot_note", "").lower()
