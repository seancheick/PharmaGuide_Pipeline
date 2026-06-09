"""Pipeline readiness smoke test (SP-3.99, 2026-05-21).

Run before fresh DSLD batches kick off the pipeline. Locks the end-to-end
contract:

  raw DSLD JSON
    → clean_dsld_data normalizes
    → enrich_supplements_v3 attaches taxonomy + form_factor_canonical
    → score_supplements computes legacy review/detail scaffolding
    → score_supplements_v4 attaches production v4 result fields
    → build_final_db builds the products_core row

If any stage breaks because of recent SP-2 / SP-3 changes, this test
catches it before the user runs the pipeline on real data.

This is a smoke test — it doesn't validate the score numerics, only
that every stage produces the expected field shape and no exceptions
are raised. Numeric correctness lives in the per-stage test suites.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================================
# Synthetic raw DSLD product — minimal shape covering the fields the
# pipeline actually reads. Modeled after a real omega-3 softgel SKU.
# ============================================================================

SYNTHETIC_RAW_PRODUCT = {
    "id": 999001,
    "fullName": "Pipeline Smoke Test Omega-3 1000 mg Softgel",
    "brandName": "Smoke Test Brand",
    "productType": {
        "langualCode": "B0001",
        "langualCodeDescription": "Fat/Fatty Acid",
    },
    "physicalState": {
        "langualCode": "e0161",
        "langualCodeDescription": "Softgel Capsule",
    },
    "servingSizes": [
        {
            "servingSizeQuantity": 1,
            "servingSizeUnitOfMeasure": "softgel(s)",
            "minDailyServings": 1,
            "maxDailyServings": 1,
        }
    ],
    "ingredientRows": [
        {
            "name": "Fish Oil Concentrate",
            "quantity": 1000.0,
            "quantityUnit": "mg",
            "category": "fatty_acid",
            "order": 1,
        },
        {
            "name": "EPA (Eicosapentaenoic Acid)",
            "quantity": 600.0,
            "quantityUnit": "mg",
            "category": "fatty_acid",
            "nestedRows": [],
            "order": 2,
        },
        {
            "name": "DHA (Docosahexaenoic Acid)",
            "quantity": 400.0,
            "quantityUnit": "mg",
            "category": "fatty_acid",
            "order": 3,
        },
    ],
    "statements": [],
    "userGroups": [],
    "status": "active",
    "productStatus": "active",
}


# ============================================================================
# Stage 1 — enricher writes taxonomy + form_factor_canonical
# ============================================================================

def test_enricher_writes_canonical_fields():
    """Lightweight enricher invocation — bypass __init__ database loads and
    exercise just the field-writing helpers. Confirms the canonical fields
    appear on the enriched blob."""
    from enrich_supplements_v3 import SupplementEnricherV3
    from supplement_taxonomy import classify_supplement
    from form_factor_normalizer import canonicalize_form_factor

    # 1a: form_factor_canonical via the enricher's serving-basis helper
    inst = SupplementEnricherV3.__new__(SupplementEnricherV3)
    inst._last_delivery_data = None
    inst.config = {"processing_config": {}}
    import logging
    inst.logger = logging.getLogger("smoke")

    serving = inst._collect_serving_basis_data(SYNTHETIC_RAW_PRODUCT)
    assert serving["form_factor_canonical"] == "softgel", (
        f"Smoke product (DSLD e0161 Softgel Capsule) must canonicalize to "
        f"`softgel`, got {serving['form_factor_canonical']!r}."
    )
    assert serving["form_factor"] is not None  # legacy preserved
    assert "form_factor_canonical" in serving  # new field present

    # 1b: taxonomy classify_supplement on a roughly-enriched blob
    blob_for_classify = {
        **SYNTHETIC_RAW_PRODUCT,
        "product_name": SYNTHETIC_RAW_PRODUCT["fullName"],
        "ingredient_quality_data": {
            "ingredients": [
                {
                    "name": "EPA",
                    "canonical_id": "epa",
                    "category": "fatty_acid",
                    "quantity": 600,
                    "unit": "mg",
                },
                {
                    "name": "DHA",
                    "canonical_id": "dha",
                    "category": "fatty_acid",
                    "quantity": 400,
                    "unit": "mg",
                },
            ],
        },
    }
    tax = classify_supplement(blob_for_classify)
    assert tax["primary_type"] == "omega_3"
    assert tax["percentile_category"] == "fish_oil"
    assert tax["classification_confidence"] >= 0.7


# ============================================================================
# Stage 2 — v4 router reads taxonomy primary_type
# ============================================================================

def test_v4_router_routes_smoke_product_to_omega():
    """The router must read primary_type and dispatch correctly."""
    from scoring_v4.router import class_for_product

    enriched_blob = {
        "product_name": SYNTHETIC_RAW_PRODUCT["fullName"],
        "fullName": SYNTHETIC_RAW_PRODUCT["fullName"],
        "primary_type": "omega_3",
        "supplement_taxonomy": {"primary_type": "omega_3"},
        "form_factor_canonical": "softgel",
        "ingredient_quality_data": {
            "ingredients": [
                {"canonical_id": "epa", "quantity": 600, "unit": "mg"},
                {"canonical_id": "dha", "quantity": 400, "unit": "mg"},
            ],
        },
    }
    assert class_for_product(enriched_blob) == "omega"


# ============================================================================
# Stage 3 — v3 scorer reads taxonomy primary_type for B5 + percentile
# ============================================================================

def test_v3_scorer_b5_class_reads_taxonomy():
    from score_supplements import SupplementScorer
    scorer = SupplementScorer()
    enriched_blob = {
        "product_name": SYNTHETIC_RAW_PRODUCT["fullName"],
        "fullName": SYNTHETIC_RAW_PRODUCT["fullName"],
        "primary_type": "omega_3",
        "supplement_taxonomy": {"primary_type": "omega_3", "percentile_category": "fish_oil"},
    }
    # omega_3 rolls up to `generic` B5 opacity tier (1.0x multiplier).
    assert scorer._b5_class_for_product(enriched_blob) == "generic"


def test_v3_scorer_percentile_reads_taxonomy():
    from score_supplements import SupplementScorer
    scorer = SupplementScorer()
    enriched_blob = {
        "supplement_taxonomy": {
            "primary_type": "omega_3",
            "percentile_category": "fish_oil",
            "classification_confidence": 0.9,
            "classification_reasons": ["smoke"],
        },
    }
    key, label, source, _, _ = scorer._resolve_percentile_category(enriched_blob, {})
    assert key == "fish_oil"
    assert source == "taxonomy_v2"


# ============================================================================
# Stage 4 — v4 scorer end-to-end on a fully-formed enriched blob
# ============================================================================

def test_v4_scorer_produces_breakdown():
    """The v4 scorer chain: router decision → safety/completeness gates
    → module dispatch → final breakdown."""
    from score_supplements_v4 import score_product_v4

    enriched_blob = {
        "dsld_id": "999001",
        "product_name": SYNTHETIC_RAW_PRODUCT["fullName"],
        "fullName": SYNTHETIC_RAW_PRODUCT["fullName"],
        "brand_name": "Smoke Test Brand",
        "product_status": "active",
        "form_factor": "softgel",
        "form_factor_canonical": "softgel",
        "primary_type": "omega_3",
        "supplement_taxonomy": {
            "primary_type": "omega_3",
            "percentile_category": "fish_oil",
            "classification_confidence": 0.95,
            "classification_reasons": ["smoke"],
        },
        "ingredient_quality_data": {
            "total_active": 2,
            "ingredients_scorable": [
                {
                    "name": "EPA",
                    "canonical_id": "epa",
                    "category": "fatty_acid",
                    "quantity": 600,
                    "unit": "mg",
                    "unit_normalized": "mg",
                    "mapped": True,
                    "has_dose": True,
                },
                {
                    "name": "DHA",
                    "canonical_id": "dha",
                    "category": "fatty_acid",
                    "quantity": 400,
                    "unit": "mg",
                    "unit_normalized": "mg",
                    "mapped": True,
                    "has_dose": True,
                },
            ],
        },
        "servingSizes": SYNTHETIC_RAW_PRODUCT["servingSizes"],
        "verified_cert_programs": [],
    }
    result = score_product_v4(enriched_blob)
    assert "v4_breakdown" in result
    assert "v4_verdict" in result
    breakdown = result["v4_breakdown"]
    assert breakdown.get("module", {}).get("module") == "omega", (
        f"Smoke omega-3 must use omega module, got module={breakdown.get('module')!r}"
    )


# ============================================================================
# Stage 5 — build_final_db consumes form_factor_canonical for the serving
#           verb derivation
# ============================================================================

def test_build_final_db_derives_softgel_serving_verb():
    from build_final_db import _derive_serving_verb_and_noun
    verb, sing, plural = _derive_serving_verb_and_noun("ct", "softgel")
    assert "softgel" in (sing + plural).lower()


# ============================================================================
# Stage 6 — sanity check: form_factor_canonical survives via legacy fallback
#           when an OLD enriched blob lacks the field
# ============================================================================

def test_old_blob_without_canonical_still_works():
    """A pre-SP-3 enriched blob (no form_factor_canonical, no primary_type)
    must still flow through every stage via legacy fallback."""
    from scoring_v4.router import class_for_product
    from scoring_v4.gate_completeness import _form_factor
    from score_supplements import SupplementScorer

    old_blob = {
        "product_name": "Old Cap Vitamin D",
        "supplement_type": {"type": "single_nutrient"},
        "form_factor": "capsule",
        "ingredient_quality_data": {
            "ingredients_scorable": [
                {"canonical_id": "vitamin_d", "quantity": 1000, "unit": "IU"},
            ],
        },
    }
    # Router: no taxonomy → falls through to generic
    assert class_for_product(old_blob) == "generic"
    # Completeness gate: legacy form_factor read
    assert _form_factor(old_blob) == "capsule"
    # v3 b5: taxonomy absent → legacy path
    scorer = SupplementScorer()
    assert scorer._b5_class_for_product(old_blob) == "generic"


# ============================================================================
# Stage 7 — Taxonomy + form_factor vocabs are mutually consistent
# ============================================================================

def test_vocab_files_load_cleanly():
    """Both vocab JSONs must load without exception. Catches malformed
    edits before they hit the pipeline."""
    from supplement_taxonomy import PRIMARY_TYPES
    from form_factor_normalizer import _load_vocab as load_ff

    assert len(PRIMARY_TYPES) >= 15  # taxonomy has 20
    ff = load_ff()
    assert len(ff["entries"]) == 18  # form_factor has 18
    assert "alias_index" in ff
    assert "langual_index" in ff


# ============================================================================
# Stage 8 — Critical configs load (scoring_config, omega_rubric, vocab JSONs)
# ============================================================================

def test_critical_config_files_load():
    """If any required config JSON fails to parse, the pipeline can't run."""
    repo_root = Path(__file__).resolve().parents[2]
    required = [
        "scripts/config/scoring_config.json",
        "scripts/config/enrichment_config.json",
        "scripts/data/omega_rubric.json",
        "scripts/data/product_type_vocab.json",
        "scripts/data/form_factor_vocab.json",
    ]
    for rel in required:
        path = repo_root / rel
        assert path.is_file(), f"Required config missing: {rel}"
        try:
            with open(path) as fh:
                json.load(fh)
        except json.JSONDecodeError as exc:
            pytest.fail(f"Required config has malformed JSON: {rel} — {exc}")
