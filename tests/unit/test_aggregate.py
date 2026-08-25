"""Unit tests for aggregation."""

from src.tools.aggregate import aggregate


def test_sum_excludes_null():
    records = [
        {"deal_value": 100.0},
        {"deal_value": None},
        {"deal_value": 200.0},
    ]
    result = aggregate(
        records,
        metrics=[{"name": "total", "field": "deal_value", "op": "sum"}],
    )
    assert result.metrics["total"] == 300.0
    assert result.excluded_from_metrics.get("deal_value", 0) == 1
    assert any("excluded" in w for w in result.warnings)


def test_group_by():
    records = [
        {"sector": "Mining", "deal_value": 100.0},
        {"sector": "Mining", "deal_value": 200.0},
        {"sector": "Railways", "deal_value": 50.0},
    ]
    result = aggregate(
        records,
        group_by=["sector"],
        metrics=[{"name": "total", "field": "deal_value", "op": "sum"}],
    )
    assert len(result.groups) == 2
    mining = next(g for g in result.groups if g["sector"] == "Mining")
    assert mining["total"] == 300.0


def test_count():
    result = aggregate(
        [{"a": 1}, {"a": 2}],
        metrics=[{"name": "n", "field": "*", "op": "count"}],
    )
    assert result.metrics["n"] == 2


def test_filter():
    records = [
        {"deal_status": "Open", "deal_value": 100.0},
        {"deal_status": "Won", "deal_value": 200.0},
    ]
    result = aggregate(
        records,
        filters={"deal_status": "Open"},
        metrics=[{"name": "total", "field": "deal_value", "op": "sum"}],
    )
    assert result.metrics["total"] == 100.0
    assert result.valid_row_count == 1
