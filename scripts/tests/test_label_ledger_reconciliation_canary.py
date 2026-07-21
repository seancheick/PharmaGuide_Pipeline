"""Real-product canaries for label-ledger reconciliation.

Exposed by the full-corpus run (2026-07-20): the enrichment contract gate
rejected ~20 brands because the label ledger was not fully reconciled — printed
label rows inventoried into label_source_rows but never classified as
displayed / folded / documented-omission (the "bottle shows X, app shows fewer
ingredients" trust bug).

These canaries run the REAL cleaner + enricher on REAL DSLD fixtures and assert
the authoritative EnrichmentContractValidator plus the specific display
semantics (order, hierarchy, no duplicate form rows). Synthetic fixtures are
exactly what let this hide, so every case here is a copied real source file.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3
from enrichment_contract_validator import EnrichmentContractValidator

_FIXTURES = Path(__file__).parent / "fixtures" / "label_ledger_canaries"


def _raw(pid):
    return json.loads((_FIXTURES / f"{pid}.json").read_text())


def _cleaned(pid):
    return EnhancedDSLDNormalizer().normalize_product(_raw(pid))


def _enriched(pid):
    enriched, _ = SupplementEnricherV3().enrich_product(_cleaned(pid))
    return enriched


def _contract_errors(product):
    violations = EnrichmentContractValidator(strict_mode=False).validate(product)
    return [v for v in violations if v.severity == "error"]


def _display_texts(product):
    return [
        str(r.get("raw_source_text") or "")
        for r in (product.get("display_ingredients") or [])
    ]


# ---------------------------------------------------------------------------
# Defect 1 — enrichment inference must never enter the label ledger (330088)
# ---------------------------------------------------------------------------

def test_330088_inferred_curcumin_never_enters_label_view():
    """BulkSupplements 'Turmeric Curcumin 500 mg' — enrichment infers a
    'Curcumin' ingredient from the product NAME. That inference must not
    appear in display_ingredients (the user's Label view)."""
    display = _enriched("330088").get("display_ingredients") or []
    inferred = [
        r for r in display
        if isinstance(r, dict) and (
            r.get("display_type") == "inferred_from_name"
            or r.get("source_section") == "product_name"
            or r.get("resolution_type") == "product_name_fallback"
        )
    ]
    assert inferred == [], (
        f"product-name inference leaked into the label ledger: "
        f"{[r.get('display_name') for r in inferred]}"
    )


def test_330088_passes_contract_after_enrichment():
    assert _contract_errors(_enriched("330088")) == []


# ---------------------------------------------------------------------------
# Defect 2 — nested Other-Ingredient forms reconciled, IN SOURCE ORDER (79324)
# ---------------------------------------------------------------------------

def test_79324_nested_other_ingredient_forms_are_reconciled():
    """Solgar 'Advanced Multi-Billion Dophilus' (rev 79324) prints its Other
    Ingredients as forms[] nested under one blend header. Every source row must
    land in display_ingredients or a documented omission — none dropped."""
    assert _contract_errors(_cleaned("79324")) == []


def test_79324_components_displayed_via_finalizer_in_source_order():
    """The real inactive components must be SHOWN (the trust bug), recovered by
    the finalizer (display_type=label_only), and in canonical source order:
    'Vegetable Cellulose' is printed AFTER the six complex components, so it must
    render after them — not appended out of order."""
    cleaned = _cleaned("79324")
    rows = cleaned.get("display_ingredients") or []
    by_text = {
        str(r.get("raw_source_text") or "").lower(): r for r in rows
    }
    for component in ("maltodextrin", "silica", "sodium alginate"):
        match = next((t for t in by_text if component in t), None)
        assert match is not None, f"component {component!r} missing from ledger"
        assert by_text[match].get("display_type") == "label_only", (
            f"{component!r} should be finalizer-recovered (label_only)"
        )
    order = [t for t in (str(r.get("raw_source_text") or "").lower() for r in rows)]
    malto = next(i for i, t in enumerate(order) if "maltodextrin" in t)
    veg_cell = next(i for i, t in enumerate(order) if "vegetable cellulose" in t)
    assert veg_cell > malto, (
        "'Vegetable Cellulose' must follow the complex components in source order"
    )


def test_264116_working_revision_still_reconciles():
    """Same SKU, a revision whose Other Ingredients are already flat. Must
    remain contract-clean after the fix (no regression)."""
    assert _contract_errors(_cleaned("264116")) == []


# ---------------------------------------------------------------------------
# Parent/form identity — a molecular form must fold, not stand alone
# ---------------------------------------------------------------------------

def test_179343_cholecalciferol_form_does_not_duplicate_vitamin_d3():
    """Nature Made 179343 re-discloses 'Vitamin D3 (Cholecalciferol)' in Other
    Ingredients. Cholecalciferol IS Vitamin D3 (canonical vitamin_d, already
    displayed) — it must NOT surface as a standalone Other Ingredient row."""
    cleaned = _cleaned("179343")
    assert _contract_errors(cleaned) == []
    assert not any(
        "cholecalciferol" in t.lower() for t in _display_texts(cleaned)
    ), "molecular form 'Cholecalciferol' leaked as a standalone display row"


def test_179343_cholecalciferol_form_is_preserved_on_vitamin_d3():
    """Removing the detached duplicate must not erase the label parenthetical."""
    cleaned = _cleaned("179343")
    vitamin_d = next(
        row
        for row in cleaned.get("display_ingredients") or []
        if row.get("canonical_id") == "vitamin_d"
    )
    assert vitamin_d.get("label_display_form") == "Cholecalciferol"
    assert any(
        component.get("raw_source_text") == "Cholecalciferol"
        for component in vitamin_d.get("folded_label_components") or []
    ), "the duplicate form occurrence must fold into the displayed Vitamin D3 row"


def test_214224_omega_form_dedup_and_source_order():
    """Nordic Naturals 214224 (omega-3 softgel) — Cholecalciferol must fold into
    the shown Vitamin D3, and recovered rows keep source order (Olive Oil is
    printed before Rosemary extract, so it must not be appended after it)."""
    cleaned = _cleaned("214224")
    assert _contract_errors(cleaned) == []
    texts = [t.lower() for t in _display_texts(cleaned)]
    assert not any("cholecalciferol" in t for t in texts), (
        "molecular form 'Cholecalciferol' leaked as a standalone display row"
    )
    olive = next(i for i, t in enumerate(texts) if "olive oil" in t)
    rosemary = next(i for i, t in enumerate(texts) if "rosemary" in t)
    assert olive < rosemary, "recovered 'Olive Oil' must keep source order"


# ---------------------------------------------------------------------------
# Multivitamin — finalizer surfaces real dropped botanicals, contract-clean
# ---------------------------------------------------------------------------

def test_49495_multivitamin_recovers_real_dropped_botanicals():
    """Nature's Bounty 49495 'Your Life Multi Men's 50+' — real botanicals
    (Saw Palmetto, Ginkgo) printed under a blend were dropped from the ledger.
    The finalizer must surface them (display-only) and stay contract-clean."""
    cleaned = _cleaned("49495")
    assert _contract_errors(cleaned) == []
    texts = [t.lower() for t in _display_texts(cleaned)]
    assert any("saw palmetto" in t for t in texts), (
        "real botanical 'Saw Palmetto' missing from the label view"
    )


def test_conditional_other_ingredient_container_preserves_qualifier_and_child():
    """A 'May contain' source group is label meaning, not a decorative header.

    Its possible ingredients must remain children of the conditional container;
    they must never render as unconditional standalone Other Ingredients.
    """
    normalizer = EnhancedDSLDNormalizer()
    normalizer._label_ledger_omissions = []
    parent_path = "otheringredients.ingredients[0]"
    source_rows = [
        {
            "raw_source_path": parent_path,
            "raw_source_text": "May contain",
            "source_section": "inactiveIngredients",
            "label_order": 0,
            "nested_depth": 0,
        },
        {
            "raw_source_path": f"{parent_path}.forms[0]",
            "raw_source_text": "Sodium Chloride",
            "source_section": "inactiveIngredients",
            "label_order": 1,
            "nested_depth": 1,
            "parent_label": "May contain",
            "parent_source_path": parent_path,
        },
    ]

    rows = normalizer._reconcile_orphan_source_rows([], source_rows)
    by_text = {row["raw_source_text"]: row for row in rows}

    assert by_text["May contain"]["display_type"] == "structural_container"
    assert by_text["May contain"]["children"] == ["Sodium Chloride"]
    assert by_text["Sodium Chloride"]["nested_depth"] == 1
    assert by_text["Sodium Chloride"]["parent_label"] == "May contain"
    assert not normalizer._label_ledger_omissions


def test_conditional_header_expansion_queues_a_display_parent_not_an_omission():
    normalizer = EnhancedDSLDNormalizer()
    normalizer._label_ledger_omissions = []
    normalizer._display_ingredients_buffer = []
    parent_path = "otheringredients.ingredients[0]"
    ingredient = {
        "name": "May contain",
        "raw_source_path": parent_path,
        "order": 1,
        "category": "other",
        "ingredientGroup": "Header",
        "forms": [
            {
                "name": "Sodium Chloride",
                "order": 1,
                "category": "non-nutrient/non-botanical",
                "ingredientGroup": "Sodium chloride",
            }
        ],
    }

    normalizer._expand_header_forms_for_processing(ingredient, parent_path)

    assert normalizer._label_ledger_omissions == []
    assert normalizer._display_ingredients_buffer[0]["raw_source_text"] == "May contain"
    assert normalizer._display_ingredients_buffer[0]["display_type"] == "structural_container"
    assert normalizer._display_ingredients_buffer[0]["children"] == ["Sodium Chloride"]


def test_orphan_identity_resolution_does_not_hide_mapper_failures(monkeypatch):
    """A mapper regression must block the pipeline, not become an unmapped row."""
    normalizer = EnhancedDSLDNormalizer()

    def broken_mapper(_text):
        raise RuntimeError("identity mapper unavailable")

    monkeypatch.setattr(normalizer, "_map_inactive_name_prefer_other", broken_mapper)
    with pytest.raises(RuntimeError, match="identity mapper unavailable"):
        normalizer._orphan_canonical_identity("Cholecalciferol")


def test_duplicate_parent_routes_form_to_matching_canonical_occurrence():
    """Shared canonical IDs must not attach a form to the wrong label row."""
    normalizer = EnhancedDSLDNormalizer()
    normalizer._label_ledger_omissions = []
    vitamin_a = {
        "raw_source_path": "ingredientRows[0]",
        "raw_source_text": "Vitamin A",
        "label_display_name": "Vitamin A",
        "canonical_id": "vitamin_a",
        "score_included": True,
        "children": [],
    }
    beta_carotene = {
        "raw_source_path": "ingredientRows[1]",
        "raw_source_text": "Beta-Carotene",
        "label_display_name": "Beta-Carotene",
        "canonical_id": "vitamin_a",
        "score_included": True,
        "children": [],
    }
    parent_path = "otheringredients.ingredients[0]"
    source_rows = [
        {
            "raw_source_path": "ingredientRows[0]",
            "raw_source_text": "Vitamin A",
            "source_section": "activeIngredients",
            "label_order": 0,
        },
        {
            "raw_source_path": "ingredientRows[1]",
            "raw_source_text": "Beta-Carotene",
            "source_section": "activeIngredients",
            "label_order": 1,
        },
        {
            "raw_source_path": parent_path,
            "raw_source_text": "Vitamin A",
            "source_section": "inactiveIngredients",
            "label_order": 2,
        },
        {
            "raw_source_path": f"{parent_path}.forms[0]",
            "raw_source_text": "Retinyl Palmitate",
            "source_section": "inactiveIngredients",
            "label_order": 3,
            "nested_depth": 1,
            "parent_label": "Vitamin A",
            "parent_source_path": parent_path,
        },
    ]

    normalizer._reconcile_orphan_source_rows(
        [vitamin_a, beta_carotene], source_rows
    )

    assert vitamin_a.get("label_display_form") == "Retinyl Palmitate"
    assert beta_carotene.get("label_display_form") is None
