"""A row whose forms carry UNIIs of different substances has no single identity.

DSLD encodes some blend headers' constituents as ``forms`` (Nature's Bounty
17186 "Glucosamine Chondroitin Complex 3,500 mg": Chondroitin Sulfate,
Glucosamine Sulfate, Vitamin C). The first form UNII must not become the
row's identity; only agreeing form UNIIs may identify a row.
"""
import pytest

from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope="module")
def normalizer() -> EnhancedDSLDNormalizer:
    return EnhancedDSLDNormalizer()


def _two_distinct_uniis(normalizer):
    lookup = normalizer._identity_unii_to_payload_lookup
    by_name = {}
    for unii, payload in lookup.items():
        by_name.setdefault(payload.get("standard_name"), unii)
        if len(by_name) >= 2:
            break
    (name_a, unii_a), (name_b, unii_b) = list(by_name.items())[:2]
    assert name_a != name_b
    return (unii_a, name_a), (unii_b, name_b)


def test_disagreeing_form_uniis_do_not_identify_the_row(normalizer):
    (unii_a, _), (unii_b, _) = _two_distinct_uniis(normalizer)
    row = {"name": "Multi Complex", "uniiCode": None,
           "forms": [{"name": "A", "uniiCode": unii_a}, {"name": "B", "uniiCode": unii_b}]}
    assert normalizer._try_unii_match(row) is None


def test_agreeing_form_uniis_still_identify_the_row(normalizer):
    (unii_a, name_a), _ = _two_distinct_uniis(normalizer)
    row = {"name": "Single form", "uniiCode": None,
           "forms": [{"name": "A", "uniiCode": unii_a}, {"name": "A again", "uniiCode": unii_a}]}
    payload, method = normalizer._try_unii_match(row)
    assert method == "unii_form_exact_match"
    assert payload.get("standard_name") == name_a


def test_blend_group_row_never_takes_a_form_unii(normalizer):
    # 17186: only the Vitamin C form carries a UNII; the row is a DSLD blend
    # group, so no single form can be the identity of the 3,500 mg total.
    (unii_a, _), _ = _two_distinct_uniis(normalizer)
    row = {"name": "Glucosamine Chondroitin Complex", "ingredientGroup": "Blend (Combination)", "uniiCode": None,
           "forms": [{"name": "Chondroitin Sulfate", "uniiCode": None}, {"name": "Glucosamine Sulfate", "uniiCode": None}, {"name": "Vitamin C", "uniiCode": unii_a}]}
    assert normalizer._try_unii_match(row) is None
