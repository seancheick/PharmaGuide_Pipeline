"""The branded clinically-studied form credit follows the enricher's brand check.

`botanical_profile` gave full standardization (4), +3 "branded clinically studied"
and studied-dose status to any row whose names met a BRAND_ entry's aliases. Aliases
are the discovery surface and some are generic ("black pepper extract"), so a plain
BulkSupplements black pepper extract (311167) scored Formulation 20/20 as if it were
BioPerine. Whether a label names the brand is decided once, by
`enrich_supplements_v3._brand_mentioned`, and recorded on the row's clinical match.
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


def test_plain_black_pepper_extract_is_not_bioperine():
    components = _botanical_formulation("branded_form_plain_pepper_311167_raw.json")
    assert "branded_clinically_studied_extract" not in components
    assert components.get("marker_standardization_declared", 0) < 4.0


def test_a_label_naming_ksm66_keeps_the_branded_credit():
    components = _botanical_formulation("branded_form_ksm66_305203_raw.json")
    assert components.get("branded_clinically_studied_extract") == 3.0


def test_a_brand_named_blend_total_keeps_the_branded_credit():
    """54775 prints one "Sytrinol" total over its two extracts. The row scored is a
    label-level projection the enricher's evidence matcher never assesses, so its
    own label name is what names the brand."""
    components = _botanical_formulation("branded_form_sytrinol_54775_raw.json")
    assert components.get("branded_clinically_studied_extract") == 3.0


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
