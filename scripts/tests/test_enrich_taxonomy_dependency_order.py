"""Phase 0c — the enrichment dependency order around the canonical taxonomy.

WHY THIS EXISTS
    SUPP_TYPE_CONSOLIDATION_PLAN.md §5 fixes one order:

        ingredient-quality -> probiotic -> taxonomy
          -> primary/secondary (+ compatibility mirror)
          -> percentile compatibility fields FROM the taxonomy
          -> downstream scoring-evidence classification

    Two of those edges are load-bearing and were only enforced by a comment:

    1. `classify_supplement` READS `probiotic_data` (is_probiotic_product /
       total_cfu / total_strain_count) for its NP-exemption gate on probiotic
       strains. Run the taxonomy first and the gate is starved: a Paradise-style
       product (Zinc + 5 NP strains, total_cfu=0) stops resolving to
       `single_mineral`. This is TRAP 1 in the plan — never move the taxonomy
       ahead of probiotic_data.

    2. `_infer_percentile_category` ran BEFORE the taxonomy, so it could not
       possibly consume it — which is exactly why it grew into an independent
       third decision system that disagrees with the taxonomy on 56.2% of the
       corpus. A decorator cannot run before the thing it decorates, so 0b is
       blocked until this order is right.

    These are behavioural guards, not source-order greps: they assert what the
    code actually saw at call time.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3(
        config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json")
    )


def _build(name: str, actives: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "dsld_id": 970101,
        "product_name": name,
        "productName": name,
        "fullName": name,
        "brandName": "TestBrand",
        "activeIngredients": actives,
        "inactiveIngredients": [],
    }


@pytest.fixture
def product():
    return _build("Test Magnesium Glycinate", [
        {"name": "Magnesium Glycinate", "quantity": 200.0, "unit": "mg"},
    ])


def _spy_on(monkeypatch, enricher, method_name, capture):
    """Record what `enriched` already contained when `method_name` was called."""
    real = getattr(enricher, method_name)

    def spy(*args, **kwargs):
        # enrich_product passes `enriched` as the last positional arg for the
        # methods spied on here.
        enriched = args[-1] if args else kwargs.get("enriched")
        capture["called"] = True
        capture["has_taxonomy"] = isinstance(enriched, dict) and (
            "supplement_taxonomy" in enriched
        )
        capture["has_probiotic"] = isinstance(enriched, dict) and (
            "probiotic_data" in enriched
        )
        capture["primary_type"] = (
            enriched.get("primary_type") if isinstance(enriched, dict) else None
        )
        return real(*args, **kwargs)

    monkeypatch.setattr(enricher, method_name, spy)
    return capture


def test_percentile_projection_runs_after_the_taxonomy(monkeypatch, enricher, product):
    """§5 step 5: percentile fields are emitted FROM the taxonomy.

    RED before Phase 0c: the call sat ~25 lines above the taxonomy write, so it
    could never see one. Phase 0b then renamed the method to
    `_decorate_percentile_category` — it projects, it no longer infers.
    """
    seen: Dict[str, Any] = {}
    _spy_on(monkeypatch, enricher, "_decorate_percentile_category", seen)

    enricher.enrich_product(product)

    assert seen.get("called"), "_infer_percentile_category did not run"
    assert seen["has_taxonomy"], (
        "percentile inference ran BEFORE the canonical taxonomy — it cannot "
        "decorate a result that does not exist yet (plan §5 step 5)"
    )
    assert seen["primary_type"], (
        "percentile inference ran without a resolved primary_type"
    )


def test_taxonomy_still_runs_after_probiotic_data(monkeypatch, enricher, product):
    """TRAP 1. Reordering the percentile call must not disturb this edge."""
    seen: Dict[str, Any] = {}
    _spy_on(monkeypatch, enricher, "apply_taxonomy_projection", seen)

    enricher.enrich_product(product)

    assert seen.get("called"), "apply_taxonomy_projection did not run"
    assert seen["has_probiotic"], (
        "the taxonomy ran BEFORE probiotic_data — this starves the NP-exemption "
        "gate for probiotic strains (plan TRAP 1)"
    )


def test_taxonomy_runs_after_ingredient_quality_data(monkeypatch, enricher, product):
    """§5 step 1: the classifier's row population comes from IQD."""
    seen: Dict[str, Any] = {}
    real = enricher.apply_taxonomy_projection

    def spy(enriched):
        seen["has_iqd"] = "ingredient_quality_data" in enriched
        return real(enriched)

    monkeypatch.setattr(enricher, "apply_taxonomy_projection", spy)
    enricher.enrich_product(product)

    assert seen.get("has_iqd"), "the taxonomy ran before ingredient_quality_data"


def test_probiotic_np_exemption_gate_still_fires(enricher):
    """The behaviour TRAP 1 protects, pinned end to end.

    Paradise-style: a mineral product carrying decorative NP probiotic strains
    with total_cfu=0 must stay `single_mineral`, not become `probiotic`. If the
    taxonomy ever runs before probiotic_data this silently flips.
    """
    product = _build("Test Zinc Whole Food Blend", [
        {"name": "Zinc", "quantity": 15.0, "unit": "mg"},
        {"name": "Lactobacillus acidophilus", "quantity": 0.0, "unit": "NP"},
        {"name": "Bifidobacterium bifidum", "quantity": 0.0, "unit": "NP"},
    ])
    enriched, _ = enricher.enrich_product(product)

    assert enriched["primary_type"] == "single_mineral", (
        f"decorative NP strains hijacked the classification -> "
        f"{enriched['primary_type']!r}"
    )


def test_percentile_fields_are_still_emitted(enricher, product):
    """The move must not drop the compatibility surface."""
    enriched, _ = enricher.enrich_product(product)

    for key in (
        "percentile_category",
        "percentile_category_label",
        "percentile_category_source",
        "percentile_category_confidence",
        "percentile_category_signals",
    ):
        assert key in enriched, f"{key} disappeared from the enriched artifact"
