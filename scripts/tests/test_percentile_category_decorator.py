"""Phase 0b — percentile category is a DECORATION of the canonical taxonomy.

WHY THIS EXISTS
    `_infer_percentile_category` was the pipeline's THIRD decision system. It
    scored name tokens, canonical ingredients and form factor against
    `data/percentile_categories.json` and picked a cohort on its own — in
    parallel with, and in ignorance of, `classify_supplement`.

    Measured on the 14,193-product corpus before this change: the two disagreed
    on 7,975 products (56.2%), essentially one-way. The cause was vocabulary,
    not weights: the enricher's config knows 9 categories while the taxonomy's
    map has 20, so `herbal_botanical` (2,139), `amino_acid` (1,251),
    `single_vitamin` (1,189), `single_mineral` (778) and the rest had no
    expressible id and collapsed into the `general_supplement` fallback.

    It never reached the catalog — `build_final_db.py:8144` already resolves the
    export from `supplement_taxonomy.percentile_category`, and
    `score_supplements._resolve_percentile_category` already prefers the
    taxonomy ("SP-2.8: taxonomy is the source of truth for product class").
    So the enricher was maintaining a 56%-wrong opinion that two downstream
    consumers had already learned to ignore. This makes the artifact tell the
    truth instead.

THE CONTRACT
    The taxonomy DECIDES; the enricher only projects. `percentile_category` is
    the taxonomy's value verbatim, and the label/source/confidence/signals are
    derived from it — never from a product name, an ingredient list, or a form
    factor.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from supplement_taxonomy import percentile_label_for  # noqa: E402


@pytest.fixture(scope="module")
def enricher():
    return SupplementEnricherV3(
        config_path=str(SCRIPTS_DIR / "config" / "enrichment_config.json")
    )


def _taxonomy(category, *, confidence=0.85, reasons=None):
    return {
        "primary_type": "single_vitamin",
        "percentile_category": category,
        "classification_confidence": confidence,
        "classification_reasons": reasons if reasons is not None else ["a reason"],
    }


# ---------------------------------------------------------------------------
# The decorator projects; it does not decide
# ---------------------------------------------------------------------------


def test_percentile_category_is_the_taxonomy_value_verbatim(enricher):
    enriched = {"supplement_taxonomy": _taxonomy("herbal_botanical")}
    out = enricher._decorate_percentile_category(enriched)

    assert out["percentile_category"] == "herbal_botanical"
    assert out["percentile_category_source"] == "taxonomy_v2"
    assert out["percentile_category_confidence"] == 0.85
    assert out["percentile_category_signals"] == ["a reason"]


def test_categories_the_old_config_could_not_express_now_survive(enricher):
    """The 56.2% collapse: these ids have no entry in percentile_categories.json
    (which knows only 9), so the old inferer fell back to general_supplement."""
    for category in (
        "herbal_botanical", "amino_acid", "single_vitamin", "single_mineral",
        "sleep_support", "joint_support", "fiber_digestive", "b_complex",
        "immune_support", "beauty_hair_skin_nails", "vitamin_mineral_combo",
        "collagen", "electrolyte",
    ):
        out = enricher._decorate_percentile_category(
            {"supplement_taxonomy": _taxonomy(category)}
        )
        assert out["percentile_category"] == category, (
            f"{category!r} collapsed to {out['percentile_category']!r} — the "
            "enricher is still deciding instead of projecting"
        )


def test_product_name_cannot_override_the_taxonomy(enricher):
    """The one-brain test. The old inferer scored name tokens, so a product
    called 'Greens Powder' became greens_powder regardless of what the
    classifier concluded."""
    enriched = {
        "product_name": "Super Greens Powder Superfood Blend",
        "fullName": "Super Greens Powder Superfood Blend",
        "form_factor": "powder",
        "supplement_type": {"type": "specialty"},
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"canonical_id": "spirulina"}, {"canonical_id": "chlorella"},
                {"canonical_id": "barley_grass"}, {"canonical_id": "wheatgrass"},
            ]
        },
        "supplement_taxonomy": _taxonomy("single_vitamin"),
    }
    out = enricher._decorate_percentile_category(enriched)

    assert out["percentile_category"] == "single_vitamin", (
        "a product NAME overrode the canonical taxonomy — the third brain is "
        "still alive"
    )


def test_label_matches_the_shipped_derivation(enricher):
    """The label must equal what score_supplements/build_final_db already ship
    (`re.sub(r'[_-]+',' ',cat).strip().title()`), not the curated plural labels
    in percentile_categories.json ('General Supplements', 'Fish Oil & Omega-3s')
    which have never reached the catalog."""
    cases = {
        "herbal_botanical": "Herbal Botanical",
        "general_supplement": "General Supplement",
        "fish_oil": "Fish Oil",
        "amino_acid": "Amino Acid",
        "beauty_hair_skin_nails": "Beauty Hair Skin Nails",
    }
    for category, expected in cases.items():
        out = enricher._decorate_percentile_category(
            {"supplement_taxonomy": _taxonomy(category)}
        )
        assert out["percentile_category_label"] == expected
        assert percentile_label_for(category) == expected


def test_missing_taxonomy_is_reason_coded_not_fabricated(enricher):
    """TRAP 3: zero confidence is truthful when there is no evidence. The
    decorator must not invent a cohort."""
    out = enricher._decorate_percentile_category({})

    assert out["percentile_category"] is None
    assert out["percentile_category_confidence"] == 0.0
    assert out["percentile_category_source"] == "taxonomy_unavailable"
    assert out["percentile_category_signals"], "reasons must never be empty"


# ---------------------------------------------------------------------------
# The third brain is actually gone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("gone", [
    "_infer_percentile_category",
    "_collect_percentile_context",
    "_percentile_category_fallback_id",
    "_canonical_token",
    "_word_token_match",
])
def test_independent_inference_machinery_is_deleted(gone):
    """Reduced to a decorator means the decision machinery is gone, not merely
    bypassed — a dormant decider grows back."""
    assert not hasattr(SupplementEnricherV3, gone), (
        f"{gone} still exists; the percentile third brain was bypassed, not retired"
    )


def test_decorator_does_not_read_the_percentile_categories_config():
    """Inspect the decorator's CODE, not its docstring — the docstring
    legitimately explains the config it replaced."""
    import ast
    import textwrap

    source = (SCRIPTS_DIR / "enrich_supplements_v3.py").read_text()
    start = source.index("    def _decorate_percentile_category")
    end = source.index("\n    def ", start + 1)
    tree = ast.parse(textwrap.dedent(source[start:end]))
    func = tree.body[0]
    if ast.get_docstring(func):
        func.body = func.body[1:]          # drop the docstring node
    code = ast.unparse(func)

    for forbidden in ("percentile_categories", "name_tokens", "form_factor",
                      "product_name", "canonical_ingredients", "databases"):
        assert forbidden not in code, (
            f"the decorator's code references {forbidden!r} — that is deciding, "
            "not decorating"
        )
    # It may only consult the taxonomy.
    assert "supplement_taxonomy" in code


# ---------------------------------------------------------------------------
# End to end through the real pipeline
# ---------------------------------------------------------------------------


def _build(name: str, actives: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "dsld_id": 970202,
        "product_name": name,
        "productName": name,
        "fullName": name,
        "brandName": "TestBrand",
        "activeIngredients": actives,
        "inactiveIngredients": [],
    }


@pytest.mark.parametrize("name, actives, expected", [
    # Ported from the retired TestPercentileCategoryInference. The intent is
    # still worth guarding — a green tea CAPSULE is not a greens powder — but it
    # is now the canonical taxonomy's call, reached end to end, rather than a
    # second engine scoring name tokens against a 9-category config.
    (
        "Green Tea Extract 500mg Capsules",
        [{"name": "Green Tea Extract", "quantity": 500.0, "unit": "mg"}],
        "herbal_botanical",
    ),
    (
        "Gold Standard Whey Protein Powder",
        [{"name": "Whey Protein Isolate", "quantity": 24.0, "unit": "g"},
         {"name": "Whey Protein Concentrate", "quantity": 6.0, "unit": "g"}],
        "protein_powder",
    ),
    (
        "Raw Organic Perfect Food Green Superfood Juiced Greens Powder",
        [{"name": "Spirulina", "quantity": 1000.0, "unit": "mg"},
         {"name": "Chlorella", "quantity": 1000.0, "unit": "mg"},
         {"name": "Barley Grass", "quantity": 1000.0, "unit": "mg"},
         {"name": "Wheatgrass", "quantity": 1000.0, "unit": "mg"}],
        "greens_powder",
    ),
])
def test_cohort_intent_survives_under_one_brain(enricher, name, actives, expected):
    enriched, _ = enricher.enrich_product(_build(name, actives))
    assert enriched["percentile_category"] == expected
    assert enriched["percentile_category"] == (
        enriched["supplement_taxonomy"]["percentile_category"]
    )


def test_green_tea_capsule_is_not_a_greens_powder(enricher):
    """The specific near-miss the retired inferer guarded, kept explicit."""
    enriched, _ = enricher.enrich_product(_build(
        "Green Tea Extract 500mg Capsules",
        [{"name": "Green Tea Extract", "quantity": 500.0, "unit": "mg"}],
    ))
    assert enriched["percentile_category"] != "greens_powder"


def test_enriched_artifact_agrees_with_its_own_taxonomy(enricher):
    """The artifact must stop contradicting itself: enriched.percentile_category
    == enriched.supplement_taxonomy.percentile_category, always."""
    product = {
        "dsld_id": 970201,
        "product_name": "Test Ashwagandha Extract",
        "productName": "Test Ashwagandha Extract",
        "fullName": "Test Ashwagandha Extract",
        "brandName": "TestBrand",
        "activeIngredients": [
            {"name": "Ashwagandha Root Extract", "quantity": 600.0, "unit": "mg"},
        ],
        "inactiveIngredients": [],
    }
    enriched, _ = enricher.enrich_product(product)

    tax_category = enriched["supplement_taxonomy"]["percentile_category"]
    assert enriched["percentile_category"] == tax_category
    assert enriched["percentile_category_label"] == percentile_label_for(tax_category)
    assert enriched["percentile_category_source"] == "taxonomy_v2"
