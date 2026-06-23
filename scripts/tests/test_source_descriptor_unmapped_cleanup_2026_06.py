"""Remaining source descriptors from post-run unmapped report should not be IQM gaps.

These labels surfaced from rows that live in DSLD other-ingredient/source fields.
They should be recognized for label fidelity and triage hygiene, but should not be
promoted into IQM scoring/evidence credit unless a true scoreable form is named.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer
from enrich_supplements_v3 import SupplementEnricherV3


def test_plural_soybeans_routes_to_allergen_recognition_not_iqm_identity():
    normalizer = EnhancedDSLDNormalizer()

    mapped_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "Soybeans", ingredient_group="active"
    )
    assert mapped is True
    assert mapped_name == "Soy & Soy Lecithin"

    detail = normalizer._build_unmapped_detail("Soybeans", [], is_active=True)
    assert detail.get("recognized_non_identity") is True
    assert detail.get("recognition_standard_name") == "Soy & Soy Lecithin"
    assert detail.get("recognition_type") == "allergen"


def test_barley_rice_protein_is_recognized_as_non_scorable_source_descriptor():
    normalizer = EnhancedDSLDNormalizer()
    enricher = SupplementEnricherV3()

    mapped_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "Barley Rice Protein", ingredient_group="active"
    )
    assert mapped is True
    assert mapped_name == "Barley Rice Protein"

    recognized = enricher._is_recognized_non_scorable(
        "Barley Rice Protein", "Barley Rice Protein"
    )
    assert recognized is not None
    assert recognized["recognition_source"] == "other_ingredients"
    assert recognized["matched_entry_id"] == "PII_BARLEY_RICE_PROTEIN"


def test_bovine_bone_broth_protein_uses_existing_bone_broth_descriptor():
    normalizer = EnhancedDSLDNormalizer()
    enricher = SupplementEnricherV3()

    mapped_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "Bovine Bone Broth Protein", ingredient_group="active"
    )
    assert mapped is True
    assert mapped_name == "Bone Broth Powder"

    recognized = enricher._is_recognized_non_scorable(
        "Bovine Bone Broth Protein", "Bovine Bone Broth Protein"
    )
    assert recognized is not None
    assert recognized["recognition_source"] == "other_ingredients"
    assert recognized["matched_entry_id"] == "PII_BONE_BROTH"


def test_corn_bran_powder_uses_other_ingredient_source_descriptor_not_iqm():
    normalizer = EnhancedDSLDNormalizer()
    enricher = SupplementEnricherV3()

    mapped_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "Corn Bran Powder", ingredient_group="Corn Bran"
    )
    assert mapped is True
    assert mapped_name == "Corn Bran Powder"
    assert normalizer._resolve_canonical_identity(
        mapped_name,
        raw_name="Corn Bran Powder",
    ) == ("PII_CORN_BRAN_POWDER", "other_ingredients")

    recognized = enricher._is_recognized_non_scorable(
        "Corn Bran Powder", "Corn Bran Powder"
    )
    assert recognized is not None
    assert recognized["recognition_source"] == "other_ingredients"
    assert recognized["matched_entry_id"] == "PII_CORN_BRAN_POWDER"


def test_fava_bean_protein_isolate_uses_other_ingredient_source_descriptor_not_vicine():
    normalizer = EnhancedDSLDNormalizer()
    enricher = SupplementEnricherV3()

    mapped_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        "Fava Bean Protein Isolate", ingredient_group="TBD"
    )
    assert mapped is True
    assert mapped_name == "Fava Bean Protein Isolate"
    assert normalizer._resolve_canonical_identity(
        mapped_name,
        raw_name="Fava Bean Protein Isolate",
    ) == ("PII_FAVA_BEAN_PROTEIN_ISOLATE", "other_ingredients")

    recognized = enricher._is_recognized_non_scorable(
        "Fava Bean Protein Isolate", "Fava Bean Protein Isolate"
    )
    assert recognized is not None
    assert recognized["recognition_source"] == "other_ingredients"
    assert recognized["matched_entry_id"] == "PII_FAVA_BEAN_PROTEIN_ISOLATE"
