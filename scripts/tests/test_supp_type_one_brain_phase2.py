"""Phase 2: the canonical taxonomy is the only supplement-type decider.

The legacy ``supplement_type`` surface may survive only as a mechanical
compatibility projection.  It must never rescue, override, or independently
classify a product.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from build_final_db import resolve_export_supplement_type
from enrich_supplements_v3 import SupplementEnricherV3
from score_supplements import SupplementScorer
from scoring_v4.confidence import _supp_type_driver


SCRIPTS = Path(__file__).resolve().parents[1]


def test_legacy_classifier_and_reader_helpers_are_retired() -> None:
    type_utils = (SCRIPTS / "supplement_type_utils.py").read_text()
    generic_helpers = (SCRIPTS / "scoring_v4/modules/generic_helpers.py").read_text()
    enricher = (SCRIPTS / "enrich_supplements_v3.py").read_text()

    assert "def infer_supplement_type(" not in type_utils
    assert "def _iter_classification_rows(" not in type_utils
    assert "def supp_type_of(" not in generic_helpers
    assert "infer_supplement_type" not in enricher
    assert "def _classify_supplement_type(" not in enricher
    scorer = (SCRIPTS / "score_supplements.py").read_text()
    assert "def _classify_supplement_type(" not in scorer


def test_obsolete_shadow_scorer_is_deleted() -> None:
    assert not (SCRIPTS / "shadow_score_comparison.py").exists()


def test_export_type_is_taxonomy_only() -> None:
    enriched = {
        "supplement_taxonomy": {"primary_type": "general_supplement"},
        "supplement_type": {"type": "multivitamin"},
    }
    scored = {"supp_type": "probiotic"}
    assert resolve_export_supplement_type(enriched, scored) == "general_supplement"


def test_enricher_compatibility_mirror_is_mechanical() -> None:
    class ProjectionHarness:
        @staticmethod
        def _collect_product_scoring_evidence(_product):
            return []

        @staticmethod
        def _collect_product_scoring_classification(_product):
            return {"route_module": "generic"}

    enriched = {
        "product_name": "Vitamin C 500 mg",
        "activeIngredients": [
            {
                "name": "Vitamin C",
                "canonical_id": "vitamin_c",
                "category": "vitamin",
                "quantity": 500,
                "unit": "mg",
            }
        ],
        "probiotic_data": {"is_probiotic_product": False},
    }

    SupplementEnricherV3.apply_taxonomy_projection(ProjectionHarness(), enriched)

    taxonomy = enriched["supplement_taxonomy"]
    mirror = enriched["supplement_type"]
    assert mirror["type"] == taxonomy["primary_type"]
    assert mirror["active_count"] == taxonomy["quantified_label_active_count"]
    assert mirror["category_breakdown"] == taxonomy["category_breakdown"]
    assert mirror["classification_reason_codes"] == taxonomy["classification_reason_codes"]
    assert mirror["source"] == "supplement_taxonomy"


def test_export_type_does_not_rescue_missing_taxonomy_from_legacy_fields() -> None:
    enriched = {"supplement_type": {"type": "multivitamin"}}
    scored = {"supp_type": "probiotic"}
    assert resolve_export_supplement_type(enriched, scored) == "unknown"


def test_v3_rollback_scorer_does_not_classify_from_legacy_mirror() -> None:
    scorer = SupplementScorer()
    product = {"supplement_type": {"type": "probiotic"}}
    assert scorer._primary_type_from_product(product) == ""


def test_v3_b5_does_not_route_from_legacy_mirror() -> None:
    scorer = SupplementScorer()
    product = {
        "product_name": "Example Product",
        "supplement_type": {"type": "multivitamin"},
    }
    assert scorer._b5_class_for_product(product) == "generic"


def test_confidence_does_not_penalize_legacy_mirror() -> None:
    product = {"supplement_type": {"type": "specialty", "confidence": 0.0}}
    assert _supp_type_driver(product) == []


def test_phase2_decision_consumers_do_not_read_legacy_mirror() -> None:
    files = (
        "score_supplements.py",
        "scoring_input_contract.py",
        "scoring_v4/router.py",
        "scoring_v4/confidence.py",
        "scoring_v4/modules/sports_formulation.py",
    )
    offenders = []
    for relative in files:
        source = (SCRIPTS / relative).read_text()
        if 'get("supplement_type")' in source or "get('supplement_type')" in source:
            offenders.append(relative)
    assert offenders == []


def test_one_brain_guard_is_not_accidentally_testing_itself() -> None:
    """Keep the source guard honest if the test file is moved or copied."""
    assert "supplement_type" in inspect.getsource(
        test_phase2_decision_consumers_do_not_read_legacy_mirror
    )
