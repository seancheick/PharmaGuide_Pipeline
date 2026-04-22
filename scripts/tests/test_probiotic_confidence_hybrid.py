"""
Sprint E1.3.2.b — probiotic confidence hybrid regression tests.

Step 3 of the mini-sprint (per external-dev plan): descriptive-only
layer on top of the adequacy signal from E1.3.2.a. Adds three fields
per strain-matched ingredient:

  * ``cfu_confidence``  — ``high | moderate | low``
  * ``dose_basis``      — ``clinical | industry_standard | inferred``
  * ``ui_copy_hint``    — controlled enum (not freeform prose):
      * ``studied_range``
      * ``limited_evidence``
      * ``label_disclosed_no_threshold``
      * ``blend_not_individually_disclosed``

Dev guardrails this test suite enforces:
  1. No confidence field without a deterministic derivation path.
  2. ``dose_basis = "clinical"`` ONLY if the threshold is from the
     validated strain block (not the default banding). Dr Pham's
     current ``tiers_cfu_per_day`` bands are industry-standard
     1B/10B/50B — so ``industry_standard`` is the correct dose_basis
     for all current strains.
  3. Multi-strain blends get ``blend_not_individually_disclosed``
     and low confidence — no inference across strain members.
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

from enrich_supplements_v3 import _compute_probiotic_confidence_hybrid  # noqa: E402


# ---------------------------------------------------------------------------
# High-support + tier-matched (L. plantarum 299v canary shape)
# ---------------------------------------------------------------------------

def test_high_support_tier_matched_yields_studied_range_high() -> None:
    out = _compute_probiotic_confidence_hybrid(
        cfu_per_day=10_000_000_000,
        adequacy_tier="good",
        clinical_support_level="high",
    )
    assert out == {
        "cfu_confidence": "high",
        "dose_basis": "industry_standard",
        "ui_copy_hint": "studied_range",
    }


def test_moderate_support_tier_matched_yields_studied_range_moderate() -> None:
    out = _compute_probiotic_confidence_hybrid(
        cfu_per_day=5_000_000_000,
        adequacy_tier="adequate",
        clinical_support_level="moderate",
    )
    assert out["cfu_confidence"] == "moderate"
    assert out["dose_basis"] == "industry_standard"
    assert out["ui_copy_hint"] == "studied_range"


def test_weak_support_tier_matched_yields_limited_evidence_low() -> None:
    out = _compute_probiotic_confidence_hybrid(
        cfu_per_day=1_000_000_000,
        adequacy_tier="adequate",
        clinical_support_level="weak",
    )
    assert out["cfu_confidence"] == "low"
    assert out["ui_copy_hint"] == "limited_evidence"
    # dose_basis still industry_standard — the tier itself is from
    # industry bands, weakness is in the evidence
    assert out["dose_basis"] == "industry_standard"


# ---------------------------------------------------------------------------
# No tier match → label disclosed but no threshold band applies
# ---------------------------------------------------------------------------

def test_tier_none_with_dose_yields_label_disclosed_no_threshold() -> None:
    """Single-strain blend with a disclosed dose but no matching tier
    (e.g. strain not in DB, or thresholds missing)."""
    out = _compute_probiotic_confidence_hybrid(
        cfu_per_day=5_000_000_000,
        adequacy_tier=None,
        clinical_support_level="high",
    )
    assert out["cfu_confidence"] == "low"
    assert out["dose_basis"] == "inferred"
    assert out["ui_copy_hint"] == "label_disclosed_no_threshold"


# ---------------------------------------------------------------------------
# Multi-strain blend → not individually disclosed
# ---------------------------------------------------------------------------

def test_multi_strain_blend_yields_not_individually_disclosed() -> None:
    out = _compute_probiotic_confidence_hybrid(
        cfu_per_day=None,            # None signals multi-strain blend
        adequacy_tier=None,
        clinical_support_level="high",
    )
    assert out["cfu_confidence"] == "low"
    assert out["dose_basis"] == "industry_standard"
    assert out["ui_copy_hint"] == "blend_not_individually_disclosed"


def test_multi_strain_blend_precedence_over_tier() -> None:
    """If cfu_per_day is None (multi-strain), even a strong support +
    matching tier must render as 'blend_not_individually_disclosed'."""
    out = _compute_probiotic_confidence_hybrid(
        cfu_per_day=None,
        adequacy_tier="good",  # shouldn't matter
        clinical_support_level="high",
    )
    assert out["ui_copy_hint"] == "blend_not_individually_disclosed"


# ---------------------------------------------------------------------------
# Output shape & enum tightness
# ---------------------------------------------------------------------------

VALID_CFU_CONFIDENCE = {"high", "moderate", "low"}
VALID_DOSE_BASIS = {"clinical", "industry_standard", "inferred"}
VALID_UI_COPY_HINT = {
    "studied_range",
    "limited_evidence",
    "label_disclosed_no_threshold",
    "blend_not_individually_disclosed",
}


@pytest.mark.parametrize("cfu,tier,support", [
    (10_000_000_000, "good", "high"),
    (10_000_000_000, "good", "moderate"),
    (10_000_000_000, "good", "weak"),
    (5_000_000_000, "adequate", "moderate"),
    (5_000_000_000, None, "high"),
    (None, None, "high"),
    (None, "good", "high"),
    (0, None, "weak"),
])
def test_output_always_in_controlled_enums(cfu, tier, support) -> None:
    out = _compute_probiotic_confidence_hybrid(
        cfu_per_day=cfu, adequacy_tier=tier, clinical_support_level=support,
    )
    assert set(out.keys()) == {"cfu_confidence", "dose_basis", "ui_copy_hint"}
    assert out["cfu_confidence"] in VALID_CFU_CONFIDENCE
    assert out["dose_basis"] in VALID_DOSE_BASIS
    assert out["ui_copy_hint"] in VALID_UI_COPY_HINT


def test_dose_basis_never_clinical_with_current_industry_bands() -> None:
    """Conservative guard per dev: current thresholds are 1B/10B/50B
    industry standards, NOT from per-strain trial arms. Nothing should
    emit ``dose_basis="clinical"`` until strain-level trial dosing is
    explicitly tagged in the data. This test ensures we don't promote
    industry_standard → clinical by accident."""
    for cfu in (None, 0, 1_000_000_000, 50_000_000_000):
        for tier in (None, "low", "adequate", "good", "excellent"):
            for support in ("high", "moderate", "weak"):
                out = _compute_probiotic_confidence_hybrid(
                    cfu_per_day=cfu, adequacy_tier=tier, clinical_support_level=support,
                )
                assert out["dose_basis"] != "clinical", (
                    f"leaked clinical basis on (cfu={cfu}, tier={tier}, support={support})"
                )


# ---------------------------------------------------------------------------
# Canary — 19067 L. plantarum 299v 10B must get coherent fields
# ---------------------------------------------------------------------------

def test_canary_19067_probiotic_confidence_fields() -> None:
    import json
    blob_path = ROOT / "reports" / "canary_rebuild" / "19067.json"
    if not blob_path.exists():
        pytest.skip("19067 canary not rebuilt yet")
    blob = json.loads(blob_path.read_text())
    plantarum = None
    for ing in blob.get("ingredients") or []:
        if "plantarum" in (ing.get("name") or "").lower() and "299v" in (ing.get("name") or ""):
            plantarum = ing
            break
    assert plantarum is not None
    assert plantarum.get("cfu_confidence") == "high"
    assert plantarum.get("dose_basis") == "industry_standard"
    assert plantarum.get("ui_copy_hint") == "studied_range"


def test_non_probiotic_canary_does_not_get_confidence_fields() -> None:
    """Per dev: keep hybrid fields off generic ingredient surfaces.
    Non-probiotic ingredients must NOT carry these keys (either absent
    entirely, or explicitly None — both acceptable)."""
    import json
    blob_path = ROOT / "reports" / "canary_rebuild" / "306237.json"  # KSM-66 ashwagandha
    if not blob_path.exists():
        pytest.skip("306237 canary not rebuilt yet")
    blob = json.loads(blob_path.read_text())
    for ing in blob.get("ingredients") or []:
        # Not a probiotic strain — confidence fields must be absent or None
        cfu_conf = ing.get("cfu_confidence")
        assert cfu_conf in (None, ""), (
            f"non-probiotic ingredient {ing.get('name')!r} has cfu_confidence={cfu_conf!r}"
        )
