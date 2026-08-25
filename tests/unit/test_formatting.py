"""Tests for executive number formatting."""

from src.ui.formatting import fmt_customer_code, fmt_inr, fmt_pct


def test_fmt_inr_millions():
    assert fmt_inr(126_719_936) == "₹126.7M"
    assert fmt_inr(36_291_748) == "₹36.3M"
    assert fmt_inr(688_152_293) == "₹688.2M"


def test_fmt_inr_thousands():
    assert fmt_inr(450_000) == "₹450K"
    assert fmt_inr(2_450_000) == "₹2.45M"


def test_fmt_inr_none():
    assert fmt_inr(None) == "—"


def test_fmt_pct():
    assert fmt_pct(0.713) == "71%"


def test_fmt_customer_code():
    assert "Co." in fmt_customer_code("COMPANY010")
