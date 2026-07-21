"""Real-product canaries for label-ledger reconciliation.

Exposed by the full-corpus run (2026-07-20): the enrichment contract gate
rejected ~20 brands because the label ledger was not fully reconciled. Two
producer defects, both cases of "a source occurrence the cleaner inventoried
but never classified as displayed / folded / documented-omission":

  1. Enrichment appended product-name-inferred rows (e.g. Curcumin) into
     `display_ingredients` after the ledger + audit were finalized. Inference
     is not a printed Supplement Facts row and must stay out of the Label view.
  2. The cleaner inventories nested `otheringredients.ingredients[N].forms[*]`
     source rows but neither displays them nor records an allowed omission,
     because form-container expansion only fired for a closed name-set.

These canaries run the REAL cleaner + enricher on REAL fixtures and assert the
authoritative contract (EnrichmentContractValidator, 0 errors) — synthetic
fixtures are exactly what let this hide.
"""

import json
import sys
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Defect 1 — enrichment inference must never enter the label ledger (330088)
# ---------------------------------------------------------------------------

def test_330088_inferred_curcumin_never_enters_label_view():
    """BulkSupplements 'Turmeric Curcumin 500 mg' — enrichment infers a
    'Curcumin' ingredient from the product NAME. That inference must not
    appear in display_ingredients (the user's Label view)."""
    enriched = _enriched("330088")
    display = enriched.get("display_ingredients") or []
    inferred = [
        r for r in display
        if isinstance(r, dict) and (
            r.get("display_type") == "inferred_from_name"
            or r.get("source_section") == "product_name"
            or r.get("resolution_type") == "product_name_fallback"
        )
    ]
    assert inferred == [], (
        "product-name inference leaked into the label ledger: "
        f"{[r.get('display_name') for r in inferred]}"
    )


def test_330088_passes_contract_after_enrichment():
    assert _contract_errors(_enriched("330088")) == []


# ---------------------------------------------------------------------------
# Defect 2 — nested Other-Ingredient forms must be reconciled (79324)
# ---------------------------------------------------------------------------

def test_79324_nested_other_ingredient_forms_are_reconciled():
    """Solgar 'Advanced Multi-Billion Dophilus' (rev 79324) prints its Other
    Ingredients as forms[] nested under one blend header. Every source row
    must land in display_ingredients or a documented omission — none dropped."""
    cleaned = _cleaned("79324")
    assert _contract_errors(cleaned) == []


def test_79324_other_ingredient_components_are_displayed():
    """The real inactive components (Maltodextrin, Silica, ...) must be shown
    to the user, not silently dropped — the actual trust bug."""
    cleaned = _cleaned("79324")
    display_names = {
        str(r.get("display_name") or r.get("raw_source_text") or "").lower()
        for r in (cleaned.get("display_ingredients") or [])
    }
    for component in ("maltodextrin", "silica", "sodium alginate"):
        assert any(component in n for n in display_names), (
            f"label-printed Other Ingredient {component!r} is missing from "
            f"the display ledger; shown={sorted(display_names)}"
        )


# ---------------------------------------------------------------------------
# Regression — the working-comparison revision must stay green (264116)
# ---------------------------------------------------------------------------

def test_264116_working_revision_still_reconciles():
    """Same SKU, a revision whose Other Ingredients are already flat. Must
    remain contract-clean after the fix (no regression)."""
    assert _contract_errors(_cleaned("264116")) == []
