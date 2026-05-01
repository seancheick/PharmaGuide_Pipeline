#!/usr/bin/env python3
"""
Phase 6 — V1.1 attributes scaffolding contract.

Pins:
  - 458 botanicals carry attributes.source_origin
  - 1 harmful_additive carries attributes.is_animal_derived=true (Carmine)
  - 1 harmful_additive carries attributes.caramel_class (Caramel Color, null)
  - ≥3 other_ingredients carry attributes.is_branded_complex=true
  - When attributes object is present, it has only known attribute keys
"""

import json
from pathlib import Path
import pytest

DATA = Path(__file__).parent.parent / "data"
HA = json.load(open(DATA / "harmful_additives.json"))["harmful_additives"]
OI = json.load(open(DATA / "other_ingredients.json"))["other_ingredients"]
BOT = json.load(open(DATA / "botanical_ingredients.json"))["botanical_ingredients"]


KNOWN_ATTRIBUTE_KEYS = {
    "source_origin",
    "is_branded_complex",
    "is_synthetic_form",
    "is_animal_derived",
    "flavor_source",
    "colorant_source",
    "caramel_class",
    "e171_eu_concern",
}


def test_botanical_source_origin_coverage():
    """All botanicals must carry source_origin (rhododendron_caucasicum was
    fixed in the 2026-04-30 cross-file audit — was 'unspecified', now 'herb'
    with source_origin=plant). Count tracks total botanicals."""
    populated = [e for e in BOT if (e.get("attributes") or {}).get("source_origin")]
    assert len(populated) == len(BOT), (
        f"every botanical must carry source_origin; got {len(populated)}/{len(BOT)}"
    )


def test_botanical_source_origin_values():
    """source_origin must be one of: plant, fungal, algal, animal."""
    allowed = {"plant", "fungal", "algal", "animal"}
    bad = []
    for e in BOT:
        origin = (e.get("attributes") or {}).get("source_origin")
        if origin and origin not in allowed:
            bad.append((e.get("id"), origin))
    assert not bad, f"unexpected source_origin values: {bad}"


def test_carmine_is_animal_derived():
    """Cochineal extract — clinician's archetypal animal-derived colorant."""
    by_id = {e["id"]: e for e in HA}
    carmine = by_id["ADD_CARMINE_RED"]
    assert carmine.get("attributes", {}).get("is_animal_derived") is True


def test_caramel_color_class_attribute_pending():
    """Per clinician 4F: caramel_class attribute exists but value is null
    pending V1.1 per-class data (B1 logic fires on Class III/IV)."""
    by_id = {e["id"]: e for e in HA}
    cc = by_id["ADD_CARAMEL_COLOR"]
    attrs = cc.get("attributes", {})
    assert "caramel_class" in attrs, "caramel_class must be present (may be null)"
    assert attrs["caramel_class"] is None, (
        f"caramel_class should be null pending per-class data; got "
        f"{attrs['caramel_class']!r}"
    )


def test_branded_complex_at_least_3_entries():
    """At least 3 known branded complexes flagged (heuristic detection)."""
    branded = [e for e in OI
               if (e.get("attributes") or {}).get("is_branded_complex")]
    assert len(branded) >= 3, (
        f"expected ≥3 is_branded_complex entries; got {len(branded)}. "
        f"V1.1 batches will expand this heuristic."
    )


def test_no_unknown_attribute_keys():
    """Lean schema: the attributes object can only contain known keys.
    Catches typos and unauthorized schema drift."""
    bad = []
    for arr_label, arr in [("HA", HA), ("OI", OI), ("BOT", BOT)]:
        for e in arr:
            attrs = e.get("attributes")
            if not attrs:
                continue
            extra = set(attrs.keys()) - KNOWN_ATTRIBUTE_KEYS
            if extra:
                bad.append((arr_label, e.get("id"), extra))
    assert not bad, f"unknown attribute keys: {bad[:5]}"


def test_attributes_object_is_dict_when_present():
    """attributes must be a dict (or absent), never any other type."""
    for arr_label, arr in [("HA", HA), ("OI", OI), ("BOT", BOT)]:
        for e in arr:
            if "attributes" in e:
                assert isinstance(e["attributes"], dict), (
                    f"{arr_label}/{e.get('id')}: attributes must be a dict"
                )
