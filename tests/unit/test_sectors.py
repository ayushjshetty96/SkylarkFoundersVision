"""Unit tests for sector normalization."""

from src.normalization.sectors import normalize_billing_status, normalize_sector, sector_matches


def test_billed_typo():
    normalized, note = normalize_billing_status("BIlled")
    assert normalized == "Billed"
    assert note == "normalized_from:BIlled"


def test_billed_normal():
    normalized, note = normalize_billing_status("Partially Billed")
    assert normalized == "Partially Billed"
    assert note is None


def test_energy_sector_alias():
    assert normalize_sector("energy") == "Energy"


def test_sector_matches_energy_renewables_group():
    assert sector_matches("Renewables", "Energy")
    assert sector_matches("Energy", "energy")
    assert not sector_matches("Mining", "Energy")
