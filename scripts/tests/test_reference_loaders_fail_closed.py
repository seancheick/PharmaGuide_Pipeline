"""Shared reference loaders used by Clean and Enrich fail closed.

2026-10-19 (independent audit of PR #176): `UnitConverter._load_database`
logged a missing or corrupt unit_conversions.json and left empty rule tables,
so every later conversion silently returned "no rule"; the cleaner loaded the
converter lazily, so only folate products would have errored. The UNII
exoneration allowlist loader also returned {} for a missing or corrupt file.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import enhanced_normalizer
import unit_converter
from dosage_normalizer import DosageNormalizer
from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from unit_converter import UnitConverter


@pytest.fixture
def missing_path(tmp_path):
    return tmp_path / "missing.json"


@pytest.fixture
def corrupt_path(tmp_path):
    path = tmp_path / "corrupt.json"
    path.write_text('{"vitamin_conversions": {', encoding="utf-8")
    return path


@pytest.fixture
def empty_rules_path(tmp_path):
    path = tmp_path / "empty_rules.json"
    path.write_text(json.dumps({"_metadata": {"version": "x"}}), encoding="utf-8")
    return path


@pytest.mark.parametrize("fixture", ["missing_path", "corrupt_path", "empty_rules_path"])
def test_unit_converter_raises_on_unusable_database(fixture, request):
    with pytest.raises(RuntimeError, match="unit conversions"):
        UnitConverter(db_path=request.getfixturevalue(fixture))


@pytest.fixture
def default_unit_db(monkeypatch):
    """Point the converter's default path at a test file and drop the singleton."""
    def point_at(path):
        monkeypatch.setattr(unit_converter, "UNIT_CONVERSIONS_DB", path)
        monkeypatch.setattr(unit_converter, "_converter_instance", None)
    return point_at


@pytest.mark.parametrize("fixture", ["missing_path", "corrupt_path"])
def test_cleaner_init_stops_on_unusable_unit_database(fixture, request, default_unit_db):
    default_unit_db(request.getfixturevalue(fixture))
    with pytest.raises(RuntimeError, match="unit conversions"):
        EnhancedDSLDNormalizer()


@pytest.mark.parametrize("fixture", ["missing_path", "corrupt_path"])
def test_enricher_init_stops_on_unusable_unit_database(fixture, request, default_unit_db):
    default_unit_db(request.getfixturevalue(fixture))
    with pytest.raises(RuntimeError, match="unit conversions"):
        DosageNormalizer()
    with pytest.raises(RuntimeError, match="unit conversions"):
        SupplementEnricherV3()


@pytest.fixture
def unii_allowlist_path(tmp_path):
    enhanced_normalizer._load_unii_exoneration_label_tokens.cache_clear()
    yield tmp_path / "unii_exoneration_allowlist.json"
    enhanced_normalizer._load_unii_exoneration_label_tokens.cache_clear()


def test_unii_exoneration_allowlist_missing_raises(unii_allowlist_path):
    with pytest.raises(RuntimeError, match="unii_exoneration_allowlist"):
        enhanced_normalizer._load_unii_exoneration_label_tokens(unii_allowlist_path)


def test_unii_exoneration_allowlist_corrupt_raises(unii_allowlist_path):
    unii_allowlist_path.write_text('{"exonerations": [', encoding="utf-8")
    with pytest.raises(RuntimeError, match="unii_exoneration_allowlist"):
        enhanced_normalizer._load_unii_exoneration_label_tokens(unii_allowlist_path)


def test_unii_exoneration_allowlist_without_exonerations_raises(unii_allowlist_path):
    unii_allowlist_path.write_text(json.dumps({"_metadata": {}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="unii_exoneration_allowlist"):
        enhanced_normalizer._load_unii_exoneration_label_tokens(unii_allowlist_path)


def test_shipped_unii_exoneration_allowlist_loads(unii_allowlist_path):
    assert enhanced_normalizer._load_unii_exoneration_label_tokens()
