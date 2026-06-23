import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.mark.parametrize(
    "label",
    [
        "Typical Fatty Acid Profile Per Capsule",
        "Isoflavone Content Per Serving",
        "Typical Isoflavone Composition:",
    ],
)
def test_active_section_headers_are_not_unmapped_actives(label):
    normalizer = EnhancedDSLDNormalizer()
    snapshot = normalizer.get_unmapped_snapshot()

    row = normalizer._process_single_ingredient_enhanced(
        {
            "name": label,
            "standardName": label,
            "category": None,
            "ingredientGroup": "Header",
            "quantity": 0,
            "unit": "NP",
        },
        is_active=True,
    )

    assert row is None
    assert normalizer.get_unmapped_delta(snapshot)["unmapped"] == []


@pytest.mark.parametrize(
    ("label", "canonical_id", "source_db"),
    [
        ("Pyridoxal 5'-Phosphate", "vitamin_b6_pyridoxine", "ingredient_quality_map"),
        ("L-Ornithine Hydrochloride, Micronized", "l_ornithine", "ingredient_quality_map"),
        ("PreticX Prebiotic Fiber", "prebiotics", "ingredient_quality_map"),
        ("PreticX Xylooligosacharides", "prebiotics", "ingredient_quality_map"),
        ("FloraGLO Marigold extract", "lutein", "ingredient_quality_map"),
        ("standardized Eleuthero extract", "ginseng", "ingredient_quality_map"),
        ("Goji Berry Fruit Juice, Powder", "goji_berry", "ingredient_quality_map"),
        ("Lycium (Goji) Berry fruit juice powder", "goji_berry", "ingredient_quality_map"),
        ("Ginkgo Flavone Glycoside", "ginkgo", "ingredient_quality_map"),
        ("standardized Chaste extract", "chasteberry", "ingredient_quality_map"),
        ("White Willow 5:1 extract", "white_willow_bark", "ingredient_quality_map"),
        ("White Willow bark 5:1 extract", "white_willow_bark", "ingredient_quality_map"),
        ("Solae Soy Protein isolate", "protein", "ingredient_quality_map"),
        ("Steviosides", "NHA_STEVIA", "other_ingredients"),
        ("Bovine Adrenal", "OI_WHOLE_ADRENAL", "other_ingredients"),
    ],
)
def test_remaining_active_label_variants_resolve_to_existing_identity(label, canonical_id, source_db):
    normalizer = EnhancedDSLDNormalizer()

    standard_name, mapped, _ = normalizer._enhanced_ingredient_mapping(
        label,
        [],
        ingredient_group=None,
    )

    assert mapped is True
    assert normalizer._resolve_canonical_identity(
        standard_name,
        raw_name=label,
    ) == (canonical_id, source_db)
