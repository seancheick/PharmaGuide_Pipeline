"""
Regression suite for branded-botanical display_label fidelity.

Golden-path canary: DSLD 1181 "Be-Energized Calorie Burning Formula" has
an ingredient with:

  raw_source_text: "Capsimax(TM) Capsicum Fruit Extract"
  name:            "Capsimax"
  forms[0].name:   "extract"  (source: name_extraction — cleaner reverse-engineered)
  standardName:    "Cayenne Pepper"
  standard_name:   "Cayenne Pepper"

Before the fix, display_label was "Capsimax (extract)" — losing:
  - the species ("Capsicum")
  - the plant part ("Fruit")
  - the descriptive form wording ("Fruit Extract")

The user must see what the bottle says: the brand carries the clinical
evidence package; the species+plant-part govern the bioactive profile.
A user reading "Capsimax (extract)" can't tell whether it's a capsicum,
turmeric, or anything else — and can't cross-reference the trial data
keyed to "Capsicum Fruit Extract".

Test invariants this suite locks in:

  1. Brand token present in display_label when it's in raw_source_text
  2. Species (the standardName/common name) present when relevant
  3. Plant part token from raw_source_text preserved in display_label
  4. Trademark symbols ((TM), (R), ®) stripped — they don't render well
  5. Generic-form-only fallbacks (name="Capsimax", form="extract") are
     replaced by richer raw_source_text content when the cleaner's form
     extraction was reverse-engineered (source: name_extraction)
  6. Standardization notes (when present) survive into the contract
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def _compute_display_label(ingredient: dict) -> str:
    """Import-on-demand so the test file pure-functions itself."""
    from scripts.build_final_db import _compute_display_label as fn
    return fn(ingredient)


# ---------------------------------------------------------------------------
# Capsimax canary (the case that surfaced the bug)
# ---------------------------------------------------------------------------

CAPSIMAX_FIXTURE = {
    "name": "Capsimax",
    "raw_source_text": "Capsimax(TM) Capsicum Fruit Extract",
    "forms": [{"name": "extract", "source": "name_extraction"}],
    "standardName": "Cayenne Pepper",
    "standard_name": "Cayenne Pepper",
}


def test_capsimax_brand_token_preserved() -> None:
    """display_label must carry 'Capsimax'."""
    label = _compute_display_label(CAPSIMAX_FIXTURE)
    assert "capsimax" in label.lower(), (
        f"brand token 'Capsimax' missing from display_label={label!r}"
    )


def test_capsimax_plant_part_preserved() -> None:
    """display_label must carry 'fruit' (the plant part from the raw label)."""
    label = _compute_display_label(CAPSIMAX_FIXTURE)
    assert "fruit" in label.lower(), (
        f"plant part 'Fruit' from raw_source_text missing from display_label={label!r}"
    )


def test_capsimax_species_preserved() -> None:
    """display_label must surface 'capsicum' (the species/common name from raw)."""
    label = _compute_display_label(CAPSIMAX_FIXTURE)
    assert "capsicum" in label.lower(), (
        f"species 'Capsicum' from raw_source_text missing from display_label={label!r}"
    )


def test_capsimax_trademark_marker_stripped() -> None:
    """``(TM)``, ``(R)``, ``®``, ``™`` markers must not appear in display_label."""
    label = _compute_display_label(CAPSIMAX_FIXTURE)
    forbidden_patterns = [
        r"\(\s*TM\s*\)",
        r"\(\s*R\s*\)",
        r"™",
        r"®",
    ]
    for pat in forbidden_patterns:
        assert not re.search(pat, label, re.IGNORECASE), (
            f"trademark marker {pat!r} survived into display_label={label!r}"
        )


def test_capsimax_does_not_collapse_to_name_only() -> None:
    """display_label must not be just 'Capsimax' — that would hide the
    species and plant part. The minimum acceptable shape is something
    like 'Capsimax Capsicum Fruit Extract'."""
    label = _compute_display_label(CAPSIMAX_FIXTURE)
    assert label.lower() != "capsimax", (
        f"display_label collapsed to bare brand: {label!r}"
    )
    assert label.lower() != "capsimax (extract)", (
        f"display_label is the pre-fix string {label!r} — species + plant part dropped"
    )


# ---------------------------------------------------------------------------
# Other branded botanicals — class-level coverage
# ---------------------------------------------------------------------------

BRANDED_BOTANICALS = [
    # (label, fixture, expected_substrings_lower)
    (
        "KSM-66 with full DSLD form",
        {
            "name": "Ashwagandha",
            "raw_source_text": "KSM-66 Ashwagandha Root Extract",
            "forms": [{"name": "KSM-66 Ashwagandha Root Extract", "source": "label"}],
            "standardName": "Ashwagandha",
        },
        ("ksm-66", "ashwagandha", "root"),
    ),
    (
        "BioPerine generic form",
        {
            "name": "BioPerine",
            "raw_source_text": "BioPerine(R) Black Pepper Extract",
            "forms": [{"name": "extract", "source": "name_extraction"}],
            "standardName": "Black Pepper",
        },
        ("bioperine", "black pepper"),
    ),
    (
        "Meriva phytosome",
        {
            "name": "Meriva",
            "raw_source_text": "Meriva Curcumin Phytosome",
            "forms": [{"name": "phytosome", "source": "name_extraction"}],
            "standardName": "Curcumin",
        },
        ("meriva", "curcumin"),
    ),
]


@pytest.mark.parametrize("label_name, fixture, expected_substrings", BRANDED_BOTANICALS)
def test_branded_botanical_preserves_components(
    label_name: str, fixture: dict, expected_substrings: tuple[str, ...]
) -> None:
    out = _compute_display_label(fixture).lower()
    for sub in expected_substrings:
        assert sub in out, (
            f"{label_name}: expected substring {sub!r} missing from display_label={out!r}"
        )


# ---------------------------------------------------------------------------
# Negative tests — preserve existing good behaviour
# ---------------------------------------------------------------------------

def test_unbranded_simple_nutrient_unchanged() -> None:
    """Plain nutrients shouldn't get raw_source_text fallback."""
    fixture = {
        "name": "Magnesium",
        "raw_source_text": "Magnesium (as Magnesium Citrate)",
        "forms": [{"name": "Citrate"}],
        "standardName": "Magnesium",
    }
    label = _compute_display_label(fixture)
    # Must contain Magnesium and Citrate; brand-style trademark cleanup should be no-op
    assert "magnesium" in label.lower()
    assert "citrate" in label.lower()
    # Must NOT smash everything into one mess
    assert "(as" not in label.lower()  # we don't want the "(as X)" parenthetical


def test_blob_canary_1181_meets_invariants() -> None:
    """Walk the targeted-rebuild canary blob (if present) and confirm the
    Capsimax ingredient passes all 4 fidelity checks at the BLOB level."""
    candidates = [
        Path("/tmp/pharmaguide_release_build_canonical_id/detail_blobs/1181.json"),
        Path("/tmp/pharmaguide_release_build_v3/detail_blobs/1181.json"),
        Path("/tmp/pharmaguide_release_build/detail_blobs/1181.json"),
    ]
    blob_path = next((p for p in candidates if p.exists()), None)
    if blob_path is None:
        pytest.skip("DSLD 1181 blob not present in any build dir — run targeted rebuild first")
    blob = json.loads(blob_path.read_text())

    cap = None
    for ing in blob.get("ingredients") or []:
        if "capsimax" in (ing.get("name") or "").lower():
            cap = ing
            break
        if "capsicum" in (ing.get("raw_source_text") or "").lower():
            cap = ing
            break
    if cap is None:
        pytest.skip("Capsimax ingredient not found in 1181 blob")

    display = cap.get("display_label") or ""
    assert "capsimax" in display.lower(), f"brand missing: {display!r}"
    assert "capsicum" in display.lower(), f"species missing: {display!r}"
    assert "fruit" in display.lower(), f"plant part missing: {display!r}"
    # Trademark markers must not survive
    assert not re.search(r"\(\s*TM\s*\)|\(\s*R\s*\)|™|®", display, re.IGNORECASE), (
        f"trademark marker survived: {display!r}"
    )
