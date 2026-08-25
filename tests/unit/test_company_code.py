"""Unit tests for company code normalization."""

import pytest

from src.normalization.company_code import normalize_company_code


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("WOCOMPANY_002", "COMPANY002"),
        ("COMPANY002", "COMPANY002"),
        ("COMPANY2", "COMPANY002"),
        ("company089", "COMPANY089"),
        (None, None),
        ("", None),
        ("INVALID", None),
    ],
)
def test_normalize_company_code(raw, expected):
    assert normalize_company_code(raw) == expected
