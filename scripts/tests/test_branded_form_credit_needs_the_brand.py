"""Exact material identity and verified standardization are separate facts.

Generic aliases cannot establish a proprietary material. Naming a reviewed
brand likewise cannot invent its marker specification or depend on clinical
benefit eligibility; the existing standardization projection owns that trait.
"""
import json
import logging
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _botanical_formulation(name):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / name).read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    artifact = build_scored_artifact(enriched)
    formulation = artifact["_v4_module_breakdown"]["dimensions"]["formulation"]
    return (formulation.get("metadata") or {}).get("botanical_formulation") or {}


# Sean/team,2026-10-28: physical brand identity alone earns no marker credit.
# KSM-66 has an independently verified material specification; Sytrinol's
# clinical identity cannot substitute for an absent standardization projection.


def test_plain_black_pepper_extract_is_not_bioperine():
    components = _botanical_formulation("branded_form_plain_pepper_311167_raw.json")
    assert "branded_clinically_studied_extract" not in components
    assert components.get("marker_standardization_declared", 0) < 3.2


def test_a_label_naming_ksm66_keeps_the_full_standardization_tier():
    components = _botanical_formulation("branded_form_ksm66_305203_raw.json")
    assert "branded_clinically_studied_extract" not in components
    assert components.get("marker_standardization_declared") == 3.2


def test_a_brand_named_blend_total_cannot_invent_a_standardization_tier():
    """54775 names Sytrinol, but that identity is not marker-specification proof."""
    components = _botanical_formulation("branded_form_sytrinol_54775_raw.json")
    assert "branded_clinically_studied_extract" not in components
    assert components.get("marker_standardization_declared", 0) == 0
    from evidence_resolver import is_reviewed_branded_material
    assert is_reviewed_branded_material("sytrinol", "Sytrinol", strict_material_spelling=True)


def test_reviewed_preparation_recognition_does_not_follow_a_shared_container_path():
    from scoring_v4.modules.botanical_profile import _recognized_botanical_identity

    parent = {"canonical_id": "sytrinol", "name": "Sytrinol",
              "raw_source_path": "ingredientRows[0]"}
    child = {"canonical_id": "unknown_citrus_material", "name": "Citrus material",
             "raw_source_path": "ingredientRows[0]"}
    assert _recognized_botanical_identity(parent)
    assert not _recognized_botanical_identity(child)
    assert not _recognized_botanical_identity({**parent, "canonical_id": "unreviewed_blend",
                                              "name": "Unreviewed Blend"})
