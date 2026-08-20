#!/usr/bin/env python3
"""Contracts for exact, source-preserving catalog brand identity."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brand_identity import BrandRegistry


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "catalog_brand_registry.json"


def test_registry_resolves_alias_without_rewriting_source_brand(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({
        "_metadata": {"schema_version": "1.0.0"},
        "brands": [{
            "id": "garden_of_life",
            "display_name": "Garden of Life",
            "family": "Garden of Life",
            "aliases": [
                {"name": "Garden of Life", "product_line": None},
                {"name": "Garden of Life Dr. Fomulated", "product_line": "Dr. Formulated"},
            ],
        }],
        "wave_1": [],
    }), encoding="utf-8")

    resolved = BrandRegistry.load(path).resolve("  GARDEN OF LIFE DR. FOMULATED ")

    assert resolved.source_brand == "  GARDEN OF LIFE DR. FOMULATED "
    assert resolved.display_brand == "Garden of Life"
    assert resolved.family == "Garden of Life"
    assert resolved.product_line == "Dr. Formulated"
    assert resolved.matched is True


def test_registry_unknown_brand_passes_through_visibly():
    registry = BrandRegistry.from_dict({"_metadata": {"schema_version": "1.0.0"}, "brands": [], "wave_1": []})

    resolved = registry.resolve("  New Future Brand  ")

    assert resolved.source_brand == "  New Future Brand  "
    assert resolved.display_brand == "New Future Brand"
    assert resolved.family == "New Future Brand"
    assert resolved.product_line is None
    assert resolved.matched is False


def test_registry_does_not_use_substring_or_fuzzy_matching():
    registry = BrandRegistry.from_dict({
        "_metadata": {"schema_version": "1.0.0"},
        "brands": [{
            "id": "gnc",
            "display_name": "GNC",
            "family": "GNC",
            "aliases": [{"name": "GNC Mega Men", "product_line": "Mega Men"}],
        }],
        "wave_1": [],
    })

    resolved = registry.resolve("GNC Mega Men Ultra New Formula")

    assert resolved.matched is False
    assert resolved.display_brand == "GNC Mega Men Ultra New Formula"


def test_registry_rejects_normalized_alias_collisions():
    payload = {
        "_metadata": {"schema_version": "1.0.0"},
        "brands": [
            {
                "id": "first",
                "display_name": "First",
                "family": "First",
                "aliases": [{"name": "Same Brand", "product_line": None}],
            },
            {
                "id": "second",
                "display_name": "Second",
                "family": "Second",
                "aliases": [{"name": " same   brand ", "product_line": None}],
            },
        ],
        "wave_1": [],
    }

    try:
        BrandRegistry.from_dict(payload)
    except ValueError as exc:
        assert "alias collision" in str(exc).lower()
    else:
        raise AssertionError("normalized alias collision was accepted")


def test_production_registry_contains_wave_1_and_megafood():
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    registry = BrandRegistry.load(DATA_PATH)

    assert payload["_metadata"]["total_entries"] == len(payload["brands"])
    assert len(registry.wave_1) == 9
    assert sum(item.expected_live_labels for item in registry.wave_1) == 1220
    megafood = next(item for item in registry.wave_1 if item.query_brand == "MegaFood")
    assert megafood.folder == "MegaFood"
    assert megafood.expected_live_labels == 278


def test_production_registry_normalizes_known_current_aliases():
    registry = BrandRegistry.load(DATA_PATH)

    expected = {
        "BulkSupplements.com": ("BulkSupplements", None),
        "GNC Mega Men": ("GNC", "Mega Men"),
        "Garden of Life Dr. Fomulated": ("Garden of Life", "Dr. Formulated"),
        "SR Sports Research": ("Sports Research", None),
        "Thorne Research": ("Thorne", None),
        "CVS pharmacy": ("CVS Health", None),
        "Women's Ensemble by MegaFood": ("MegaFood", "Women's Ensemble"),
    }
    for raw_brand, (display, line) in expected.items():
        resolved = registry.resolve(raw_brand)
        assert resolved.matched is True, raw_brand
        assert (resolved.display_brand, resolved.product_line) == (display, line)
