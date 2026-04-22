"""
Sprint E1.3.2 — probiotic CFU adequacy regression tests.

Step 1 of the mini-sprint (scoring core, per external-dev plan):
compute per-strain adequacy tier from Dr Pham's ``cfu_thresholds``
blocks, derive ``clinical_support_level`` from the strain entry with
a fallback chain to ``evidence_strength``, and expose both on each
found clinical strain in ``probiotic_data`` for consumption by the
build-time ingredient adapter.

Hybrid fields (``cfu_confidence``, ``dose_basis``, ``ui_copy_hint``)
and Section-A point uplift are deferred to follow-up sub-tasks per
dev's "step 1: wire scoring only" guidance.

Canary target (sprint §E1.3.2 DoD):
  DSLD 19067 Nature Made Digestive Health Probiotic — single-strain
  L. plantarum 299v at 10 billion CFU → adequacy_tier = "good",
  clinical_support_level = "high" (from evidence_strength="strong"
  fallback), badge wakes to "well_dosed".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from enrich_supplements_v3 import (  # noqa: E402
    _compute_strain_cfu_tier,
    _derive_clinical_support_level,
)


L_PLANTARUM_299V_THRESHOLDS = {
    "low": {"upper_exclusive": 1_000_000_000},
    "adequate": {
        "lower_inclusive": 1_000_000_000,
        "upper_exclusive": 10_000_000_000,
    },
    "good": {
        "lower_inclusive": 10_000_000_000,
        "upper_exclusive": 50_000_000_000,
    },
    "excellent": {"lower_inclusive": 50_000_000_000},
}


# ---------------------------------------------------------------------------
# _compute_strain_cfu_tier — pure mapping function
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cfu,expected_tier", [
    (500_000_000, "low"),          # 500M — below 1B adequate floor
    (999_999_999, "low"),           # just under 1B
    (1_000_000_000, "adequate"),    # exactly at adequate floor
    (5_000_000_000, "adequate"),    # mid-adequate
    (9_999_999_999, "adequate"),    # just under good floor
    (10_000_000_000, "good"),       # exactly at good floor (L. plantarum 299v canary)
    (25_000_000_000, "good"),       # mid-good
    (49_999_999_999, "good"),       # just under excellent floor
    (50_000_000_000, "excellent"),  # excellent floor
    (100_000_000_000, "excellent"), # far above
])
def test_cfu_tier_maps_correctly_for_l_plantarum_299v_thresholds(cfu: int, expected_tier: str) -> None:
    assert _compute_strain_cfu_tier(cfu, L_PLANTARUM_299V_THRESHOLDS) == expected_tier


def test_cfu_tier_returns_none_for_zero_or_missing_cfu() -> None:
    assert _compute_strain_cfu_tier(0, L_PLANTARUM_299V_THRESHOLDS) is None
    assert _compute_strain_cfu_tier(None, L_PLANTARUM_299V_THRESHOLDS) is None


def test_cfu_tier_returns_none_for_empty_or_missing_thresholds() -> None:
    assert _compute_strain_cfu_tier(10_000_000_000, None) is None
    assert _compute_strain_cfu_tier(10_000_000_000, {}) is None


def test_cfu_tier_handles_out_of_order_band_definitions() -> None:
    """Dr Pham's bands are sorted by threshold; order of dict keys in
    JSON doesn't guarantee numeric ordering. Helper must tolerate."""
    shuffled = {
        "excellent": {"lower_inclusive": 50_000_000_000},
        "low": {"upper_exclusive": 1_000_000_000},
        "adequate": {
            "lower_inclusive": 1_000_000_000,
            "upper_exclusive": 10_000_000_000,
        },
        "good": {
            "lower_inclusive": 10_000_000_000,
            "upper_exclusive": 50_000_000_000,
        },
    }
    assert _compute_strain_cfu_tier(10_000_000_000, shuffled) == "good"


# ---------------------------------------------------------------------------
# _derive_clinical_support_level — explicit field + fallback chain
# ---------------------------------------------------------------------------

def test_explicit_clinical_support_level_wins() -> None:
    entry = {
        "cfu_thresholds": {
            "evidence": {
                "clinical_support_level": "moderate",
                "evidence_strength": "strong",
            }
        }
    }
    assert _derive_clinical_support_level(entry) == "moderate"


@pytest.mark.parametrize("evidence_strength,expected", [
    ("strong", "high"),
    ("medium", "moderate"),
    ("weak", "weak"),
])
def test_falls_back_to_evidence_strength_mapping(evidence_strength: str, expected: str) -> None:
    entry = {
        "cfu_thresholds": {
            "evidence": {"evidence_strength": evidence_strength}
        }
    }
    assert _derive_clinical_support_level(entry) == expected


def test_l_plantarum_299v_derives_high_from_strong_fallback() -> None:
    """Canary: Dr Pham's L. plantarum 299v entry has evidence_strength
    ``"strong"`` but no explicit clinical_support_level. Fallback maps
    strong → high → full tier points."""
    entry = {
        "cfu_thresholds": {
            "evidence": {"evidence_strength": "strong"},
        }
    }
    assert _derive_clinical_support_level(entry) == "high"


def test_unknown_or_missing_evidence_returns_weak() -> None:
    """Conservative default — anything we can't positively classify is
    treated as weak so the downstream cap protects against overclaim."""
    assert _derive_clinical_support_level({}) == "weak"
    assert _derive_clinical_support_level({"cfu_thresholds": {}}) == "weak"
    assert _derive_clinical_support_level({"cfu_thresholds": {"evidence": {}}}) == "weak"
    assert _derive_clinical_support_level(
        {"cfu_thresholds": {"evidence": {"evidence_strength": "wibble"}}}
    ) == "weak"


# ---------------------------------------------------------------------------
# End-to-end: 19067 canary adequacy attached to ingredient via build blob
# ---------------------------------------------------------------------------

def test_canary_19067_probiotic_ingredient_carries_adequacy_tier() -> None:
    import json
    blob_path = ROOT / "reports" / "canary_rebuild" / "19067.json"
    if not blob_path.exists():
        pytest.skip("19067 canary not rebuilt yet")
    blob = json.loads(blob_path.read_text())

    # Find the L. plantarum 299v ingredient
    plantarum = None
    for ing in blob.get("ingredients") or []:
        if "plantarum" in (ing.get("name") or "").lower() and "299v" in (ing.get("name") or ""):
            plantarum = ing
            break
    assert plantarum is not None, "L. plantarum 299v not found in 19067 blob"
    assert plantarum.get("adequacy_tier") == "good", (
        f"19067 L. plantarum 299v at 10B CFU should map to 'good' tier; got "
        f"{plantarum.get('adequacy_tier')!r}"
    )
    assert plantarum.get("clinical_support_level") == "high", (
        f"19067 strain should derive high support from evidence_strength='strong'; got "
        f"{plantarum.get('clinical_support_level')!r}"
    )
    # Badge auto-activates
    assert plantarum.get("display_badge") == "well_dosed", (
        f"adequacy 'good' should map to well_dosed badge; got "
        f"{plantarum.get('display_badge')!r}"
    )
