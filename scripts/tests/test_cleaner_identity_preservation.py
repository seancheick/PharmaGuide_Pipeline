"""Regression tests for identity vs bioactivity split — cleaner stage.

After Phases 2-3 of the identity_bioactivity_split, the cleaner must resolve
source-botanical labels to source-botanical canonicals (not marker canonicals).
Bare marker products still resolve to their marker canonicals as before.

These tests catch the original "Acerola Extract → vitamin_c bio_score=12" bug
class and any future regression of the source-vs-marker conflation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from enhanced_normalizer import EnhancedDSLDNormalizer  # noqa: E402


@pytest.fixture(scope="module")
def normalizer():
    return EnhancedDSLDNormalizer()


# Each row: (label, expected_substring_in_standard_name, reason)
# expected_substring is matched case-insensitively against the cleaner output.
SOURCE_BOTANICAL_CASES = [
    # Pure source-botanical labels — must resolve to source botanical, NOT marker.
    ("Acerola Extract",              "acerola",  "previously routed to vitamin_c (bio=12)"),
    ("Acerola Cherry Extract",       "acerola",  "vitamin_c.acerola_cherry_extract form deleted"),
    ("Camu Camu Fruit Extract",      "camu",     "previously routed to vitamin_c"),
    ("Camu Camu",                    "camu",     "bare botanical label"),
    ("Turmeric (root) extract",      "turmeric", "previously routed to curcumin"),
    ("organic turmeric",             "turmeric", "previously routed to curcumin"),
    ("Turmeric Extract standardized to 95% curcuminoids", "turmeric", "standardized source extract remains turmeric identity"),
    ("Turmeric Extract 95% Curcuminoids", "turmeric", "pct marker declaration still preserves source identity"),
    ("Broccoli Sprout Extract",      "broccoli sprout", "broccoli_sprout botanical, not sulforaphane"),
    ("Broccoli sprout powder",       "broccoli sprout", "broccoli_sprout botanical, not sulforaphane"),
    ("Broccoli Sprout Extract standardized to 13% glucoraphanin", "broccoli sprout", "standardized source extract remains broccoli_sprout identity"),
    ("Tomato powder",                "tomato",   "tomato botanical, not lycopene"),
    ("Sophora japonica",             "sophora",  "previously routed to quercetin via stdbot alias"),
    ("Sophora japonica extract",     "sophora",  "stdbot quercetin had 'sophora japonica extract' alias"),
    ("Horse Chestnut seed extract",  "horse",    "horse_chestnut_seed botanical, not aescin"),
    ("horse chestnut extract 20%",   "horse",    "20% source extract is still horse_chestnut_seed identity, not aescin"),
    ("Horse Chestnut Extract standardized to 20% aescin", "horse", "standardized source extract remains horse_chestnut_seed identity"),
    ("Polygonum cuspidatum",         "knotweed", "previously routed to resveratrol"),
    ("polygonum cuspidatum 50% extract", "knotweed", "50% source extract is still japanese_knotweed identity, not resveratrol"),
    ("standardized extract of polygonum cuspidatum", "knotweed", "standardized source extract is still japanese_knotweed identity"),
    ("chinese knotweed extract",     "knotweed", "source botanical alias, not resveratrol marker"),
    ("Asian Knotweed Root Extract",  "knotweed", "source botanical alias, not resveratrol marker"),
    ("Japanese Knotweed Extract 50% resveratrol", "knotweed", "standardized source extract remains japanese_knotweed identity"),
    ("Polygonum cuspidatum root extract", "knotweed", "stdbot resveratrol had 'polygonum cuspidatum extract' alias"),
]


# Marker products that MUST still resolve to their marker canonical.
MARKER_PRESERVATION_CASES = [
    ("Vitamin C",          "vitamin c",    "core marker"),
    ("Liposomal Vitamin C", "vitamin c",   "premium delivery form"),
    ("Ascorbic Acid",      "vitamin c",    "USP-grade marker"),
    ("Curcumin",           "curcumin",     "bare marker"),
    ("Quercetin",          "quercetin",    "bare marker"),
    ("Quercetin Dihydrate", "quercetin",   "marker salt form"),
    ("Resveratrol",        "resveratrol",  "bare marker"),
    ("Trans-Resveratrol",  "resveratrol",  "marker isomer"),
    ("Sulforaphane",       "sulforaphane", "bare marker"),
    ("Lycopene",           "lycopene",     "bare marker"),
    ("Capsaicin",          "capsaicin",    "bare marker"),
]


@pytest.mark.parametrize("label,expected_substr,reason", SOURCE_BOTANICAL_CASES)
def test_source_botanical_does_not_cross_to_marker(normalizer, label, expected_substr, reason):
    """Source-botanical labels must resolve to a source-botanical canonical,
    never to the marker canonical they happen to deliver.

    Reason: identity_bioactivity_split (Phases 2-3). The marker contribution,
    if any, lives in delivers_markers[] (Phase 4 enricher), not as the primary
    canonical_id.
    """
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(label, [])
    assert mapped is True, f"{label!r} should map ({reason})"
    assert expected_substr.lower() in str(standard_name).lower(), (
        f"{label!r} resolved to {standard_name!r}; expected to contain "
        f"{expected_substr!r}. {reason}"
    )


# Forbid: these source-botanical labels MUST NOT resolve to their marker.
MARKER_FORBIDDEN_FOR_SOURCE = [
    ("Acerola Extract",              "vitamin c"),
    ("Camu Camu Fruit Extract",      "vitamin c"),
    ("Turmeric (root) extract",      "curcumin"),
    ("organic turmeric",             "curcumin"),
    ("Turmeric Extract standardized to 95% curcuminoids", "curcumin"),
    ("Turmeric Extract 95% Curcuminoids", "curcumin"),
    ("Broccoli sprout powder",       "sulforaphane"),
    ("Broccoli Sprout Extract standardized to 13% glucoraphanin", "sulforaphane"),
    ("Sophora japonica",             "quercetin"),
    ("Polygonum cuspidatum",         "resveratrol"),
    ("polygonum cuspidatum 50% extract", "resveratrol"),
    ("standardized extract of polygonum cuspidatum", "resveratrol"),
    ("chinese knotweed extract",     "resveratrol"),
    ("Asian Knotweed Root Extract",  "resveratrol"),
    ("Horse Chestnut seed extract",  "aescin"),
    ("horse chestnut extract 20%",   "aescin"),
    ("Horse Chestnut Extract standardized to 20% aescin", "aescin"),
    ("Japanese Knotweed Extract 50% resveratrol", "resveratrol"),
    ("Tomato powder",                "lycopene"),
]


@pytest.mark.parametrize("label,forbidden_marker", MARKER_FORBIDDEN_FOR_SOURCE)
def test_source_botanical_does_not_map_to_marker_canonical(normalizer, label, forbidden_marker):
    """Affirmative check: the resolved standard_name MUST NOT be the marker
    canonical's name. Pairs with the substring test — catches the inverse bug."""
    standard_name, _, _ = normalizer._enhanced_ingredient_mapping(label, [])
    assert forbidden_marker.lower() not in str(standard_name).lower(), (
        f"REGRESSION: {label!r} resolved to {standard_name!r} which contains "
        f"forbidden marker {forbidden_marker!r}. Identity_bioactivity_split "
        f"Phase 2-3 migration should prevent this."
    )


@pytest.mark.parametrize("label,expected_substr,reason", MARKER_PRESERVATION_CASES)
def test_marker_products_still_resolve_to_marker(normalizer, label, expected_substr, reason):
    """Pure marker labels (no source-botanical mention) must still resolve to
    the marker canonical. The fix must not break legitimate marker products."""
    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(label, [])
    assert mapped is True, f"{label!r} should map ({reason})"
    assert expected_substr.lower() in str(standard_name).lower(), (
        f"{label!r} resolved to {standard_name!r}; expected to contain "
        f"{expected_substr!r}. Marker preservation: {reason}"
    )


def test_iqm_no_source_botanical_aliases_remain(normalizer):
    """Structural assertion: ingredient_quality_map.json must not contain
    source-botanical names as aliases under any of the 8 marker canonicals.
    """
    import json
    iqm_path = SCRIPTS_ROOT / "data" / "ingredient_quality_map.json"
    with iqm_path.open() as f:
        iqm = json.load(f)

    MARKERS = ["vitamin_c", "curcumin", "sulforaphane", "capsaicin",
               "lycopene", "quercetin", "aescin", "resveratrol"]
    FORBIDDEN_PATTERNS = [
        ("acerola", "acerola"),       # bare acerola anywhere
        ("camu camu", "camu_camu"),
        # turmeric: allow in QUALIFY aliases that also contain curcuminoid keyword
        # (these are the 10 QUALIFY entries; cleaner predicate enforces standardization)
        ("broccoli sprout", "broccoli_sprout"),
        ("cayenne", "cayenne_pepper"),
        ("sophora japonica", "sophora_japonica"),
        ("horse chestnut", "horse_chestnut_seed"),
        ("polygonum cuspidatum", "japanese_knotweed"),
    ]

    import re
    # QUALIFY predicates: aliases with these keywords are kept under marker
    # because the alias text itself encodes standardization (cleaner only
    # matches the alias when the label declares the predicate).
    QUALIFY_PATTERN = re.compile(
        r"\b\d+\s*%|\bstandardi[sz]ed\b|\bstd\.?\b|\bcurcuminoid|\bcontaining\b|\bextract\s+\d+\s*[:x]\b",
        re.I,
    )

    violations = []
    for marker in MARKERS:
        entry = iqm.get(marker, {})
        forms = entry.get("forms", {})
        for fname, fdata in forms.items():
            # Check form_name itself
            for needle, target in FORBIDDEN_PATTERNS:
                if needle in fname.lower():
                    violations.append(f"form_name {marker}.{fname!r} contains source botanical {needle!r}")
            # Check aliases
            for alias in fdata.get("aliases", []) or []:
                for needle, target in FORBIDDEN_PATTERNS:
                    if needle in alias.lower():
                        # QUALIFY exception: alias text encodes standardization predicate
                        if QUALIFY_PATTERN.search(alias):
                            continue
                        violations.append(
                            f"alias {alias!r} (under {marker}.forms[{fname!r}]) "
                            f"contains source botanical {needle!r} — should be moved to {target}"
                        )
    assert not violations, (
        f"identity_bioactivity_split structural regression — "
        f"{len(violations)} source-botanical alias(es) found under marker IQM canonicals:\n  "
        + "\n  ".join(violations[:10])
    )


def test_standardized_botanicals_no_source_aliases_under_markers():
    """Same structural check for standardized_botanicals.json."""
    import json
    sb_path = SCRIPTS_ROOT / "data" / "standardized_botanicals.json"
    with sb_path.open() as f:
        sb = json.load(f)

    MARKERS = {"vitamin_c", "curcumin", "sulforaphane", "capsaicin",
               "lycopene", "quercetin", "aescin", "resveratrol"}
    FORBIDDEN_NEEDLES = [
        "acerola", "camu camu", "broccoli sprout", "cayenne",
        "sophora japonica", "horse chestnut", "polygonum cuspidatum",
        "grape skin", "red wine",
    ]
    violations = []
    for entry in sb["standardized_botanicals"]:
        if entry["id"] not in MARKERS:
            continue
        for alias in entry.get("aliases", []):
            for needle in FORBIDDEN_NEEDLES:
                if needle in alias.lower():
                    violations.append(
                        f"standardized_botanicals.{entry['id']} alias {alias!r} "
                        f"contains source botanical {needle!r}"
                    )
    assert not violations, (
        "identity_bioactivity_split: source-botanical aliases under marker "
        "entries in standardized_botanicals.json:\n  " + "\n  ".join(violations)
    )
