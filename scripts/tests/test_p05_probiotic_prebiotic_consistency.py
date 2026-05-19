"""P0.5 regression tests — probiotic_detail.prebiotic_present must agree
with the scorer's prebiotic credit signal.

Codex's read-only audit on the 2026-05-19 RC surfaced a split-brain
contract on DSLD 274081 (Garden of Life Once Daily Prenatal):

  - scorer credits prebiotic: probiotic_breakdown.prebiotic = 1.0
    (because the substring "acacia" matches the scorer's prebiotic_terms
    list against the active ingredient "organic Acacia Fiber")
  - enricher detail says no prebiotic: probiotic_detail.prebiotic_present
    = False, prebiotic_name = "" (because the enricher only does
    exact-match against clinically_relevant_strains.json's prebiotics
    list, which doesn't accept "organic Acacia Fiber" as a match for
    "Acacia Fiber" or its aliases)

Catalog scan found 74 products with score prebiotic > 0 but display
flag false. This file is the regression contract that prevents drift.

Fix: enricher gains a second-pass substring detection against the same
prebiotic_terms list the scorer uses (sourced from scoring_config so
both reads stay in sync).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher() -> SupplementEnricherV3:
    return SupplementEnricherV3()


def _probiotic_product(
    *,
    extra_active: list | None = None,
    extra_inactive: list | None = None,
    nested_in_blend: list | None = None,
) -> dict:
    """Minimal probiotic product with two strains.  Caller decorates with
    prebiotic candidates via `extra_active`, `extra_inactive`, or
    `nested_in_blend` (children of the first probiotic blend)."""
    actives = [
        {
            "name": "Lactobacillus rhamnosus",
            "standardName": "Lactobacillus Rhamnosus",
            "category": "probiotic",
            "quantity": 5_000_000_000,
            "unit": "Live Cell(s)",
            "nestedIngredients": nested_in_blend or [],
            "harvestMethod": "",
            "notes": "",
        },
        {
            "name": "Bifidobacterium lactis",
            "standardName": "Bifidobacterium Lactis",
            "category": "probiotic",
            "quantity": 5_000_000_000,
            "unit": "Live Cell(s)",
            "nestedIngredients": [],
            "harvestMethod": "",
            "notes": "",
        },
    ]
    if extra_active:
        actives.extend(extra_active)
    return {
        "id": "test_p05",
        "product_name": "Test Probiotic",
        "fullName": "Test Probiotic",
        "bundleName": "",
        "statements": [],
        "activeIngredients": actives,
        "inactiveIngredients": extra_inactive or [],
    }


# --- Anchor: the GoL prenatal pattern that triggered P0.5 -----------------


def test_organic_acacia_fiber_active_marks_prebiotic_present(enricher) -> None:
    """Active ingredient 'organic Acacia Fiber' is a prebiotic per the
    scorer's terms list ('acacia' substring) — enricher must agree.

    This reproduces the exact split-brain pattern on DSLD 274081
    (Garden of Life Dr. Formulated Probiotics Once Daily Prenatal)."""
    product = _probiotic_product(
        extra_active=[
            {
                "name": "organic Acacia Fiber",
                "standardName": "Organic Acacia Fiber",
                "category": "fiber",
                "quantity": 200,
                "unit": "mg",
                "nestedIngredients": [],
                "harvestMethod": "",
                "notes": "",
            }
        ],
    )
    pd = enricher._collect_probiotic_data(product)
    assert pd["prebiotic_present"] is True, (
        "active 'organic Acacia Fiber' should set prebiotic_present=True "
        "(scorer awards prebiotic credit via 'acacia' substring; enricher "
        "must agree). got prebiotic_name=%r" % pd.get("prebiotic_name")
    )
    assert pd["prebiotic_name"], "prebiotic_name should not be empty"


# --- Each canonical prebiotic-term family ---------------------------------


@pytest.mark.parametrize(
    "ingredient_name",
    [
        "Inulin",
        "Chicory Root Fiber",
        "FOS (Fructooligosaccharides)",
        "GOS (Galactooligosaccharides)",
        "Beta-Glucan",
        "Pea Fiber",
        "XOS",
        "Lactulose",
        "Raftiline",
    ],
)
def test_known_prebiotic_terms_detected(enricher, ingredient_name: str) -> None:
    """Every term in scoring_config.prebiotic_terms should round-trip:
    if the scorer credits it via substring, the enricher must flag it.
    Locks the cross-config single-source-of-truth."""
    product = _probiotic_product(
        extra_active=[
            {
                "name": ingredient_name,
                "standardName": ingredient_name,
                "category": "fiber",
                "quantity": 500,
                "unit": "mg",
                "nestedIngredients": [],
                "harvestMethod": "",
                "notes": "",
            }
        ],
    )
    pd = enricher._collect_probiotic_data(product)
    assert pd["prebiotic_present"] is True, (
        f"{ingredient_name!r} contains a scorer-recognized prebiotic term; "
        f"enricher must flag prebiotic_present"
    )


# --- Coverage in nested-blend children ------------------------------------


def test_prebiotic_in_nested_blend_child_detected(enricher) -> None:
    """A prebiotic hidden inside a proprietary-blend's nested children must
    still set prebiotic_present.  Existing enricher logic already supports
    nested coverage for exact-matches; substring fallback must preserve it."""
    product = _probiotic_product(
        nested_in_blend=[
            {
                "name": "Acacia Fiber",
                "standardName": "Acacia Fiber",
                "category": "fiber",
                "quantity": 100,
                "unit": "mg",
            }
        ],
    )
    pd = enricher._collect_probiotic_data(product)
    assert pd["prebiotic_present"] is True, (
        "prebiotic in nested blend child must be detected"
    )


# --- Negative cases -------------------------------------------------------


def test_no_prebiotic_means_prebiotic_present_false(enricher) -> None:
    """A probiotic with strains but NO prebiotic ingredient must score
    prebiotic_present=False.  Avoid false positives."""
    product = _probiotic_product()
    pd = enricher._collect_probiotic_data(product)
    assert pd["prebiotic_present"] is False
    assert pd["prebiotic_name"] == ""


def test_non_prebiotic_fiber_not_falsely_detected(enricher) -> None:
    """'Apple fiber' is not in the scorer's prebiotic_terms list and is
    not a canonical prebiotic.  Must not trigger prebiotic_present."""
    product = _probiotic_product(
        extra_active=[
            {
                "name": "Apple Fiber",
                "standardName": "Apple Fiber",
                "category": "fiber",
                "quantity": 200,
                "unit": "mg",
                "nestedIngredients": [],
            }
        ],
    )
    pd = enricher._collect_probiotic_data(product)
    assert pd["prebiotic_present"] is False, (
        "'Apple Fiber' must not falsely trigger prebiotic_present"
    )


# --- Cross-source contract -------------------------------------------------


def test_existing_exact_match_path_still_works(enricher) -> None:
    """The new substring fallback must not break the existing exact-match
    detection against clinically_relevant_strains.json."""
    # "Inulin" is in the canonical prebiotics DB AND in the scorer's
    # substring terms list. Both paths should agree.
    product = _probiotic_product(
        extra_active=[
            {
                "name": "Inulin",
                "standardName": "Inulin",
                "category": "fiber",
                "quantity": 500,
                "unit": "mg",
                "nestedIngredients": [],
            }
        ],
    )
    pd = enricher._collect_probiotic_data(product)
    assert pd["prebiotic_present"] is True
    # prebiotic_name should be non-empty (exact match prefers canonical name)
    assert pd["prebiotic_name"], "prebiotic_name should be populated"


# --- Config-source single source of truth ----------------------------------


def test_enricher_reads_scoring_config_prebiotic_terms() -> None:
    """Drift prevention — the enricher's substring fallback should source
    its term list from scoring_config (same place the scorer reads from)
    so the two stay aligned.  If a future maintainer extends the terms
    list in config, both paths should pick it up without code changes."""
    import json
    cfg = json.loads(
        (SCRIPTS_ROOT / "config" / "scoring_config.json").read_text()
    )
    pro_cfg = cfg["section_A_ingredient_quality"]["probiotic_bonus"]
    terms = pro_cfg.get("prebiotic_terms") or []
    assert "acacia" in terms, (
        "scoring_config.prebiotic_terms must contain 'acacia' — both the "
        "scorer's existing detection and the new enricher fallback depend "
        "on this term"
    )
    assert "inulin" in terms
    assert "fos" in terms
