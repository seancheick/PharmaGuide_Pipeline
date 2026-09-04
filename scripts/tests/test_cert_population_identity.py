"""Certification credit must stay with the population, strength, and form tested."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from cert_resolver import CertRegistry, discover_verified_programs, resolve
from test_cert_resolver import _make_registry


@pytest.mark.parametrize(
    ("product", "certified_product"),
    [
        ("Essential for Men Multivitamin 18+", "Ritual Essential for Women Multivitamin 18+"),
        ("Essential for Women Multivitamin 18+", "Essential for Men Multivitamin 18+"),
        ("Essential for Women Multivitamin 50+", "Essential for Women Multivitamin 18+"),
        ("Essential Multivitamin", "Essential Multivitamin for Women"),
        ("Essential for Women Multivitamin", "Essential for Women Multivitamin 18+"),
        ("Essential Multivitamin Adults", "Essential Multivitamin Kids"),
        ("Essential Multivitamin Prenatal", "Essential Multivitamin Postnatal"),
        ("Essential Multivitamin Ages 4-12", "Essential Multivitamin Ages 13-17"),
        ("Essential Multivitamin for Him", "Essential Multivitamin for Her"),
        ("Essential Multivitamin for Her", "Essential Multivitamin for Him"),
        ("Essential Multivitamin", "Essential Multivitamin for Her"),
        ("Essential Multivitamin", "Essential Multivitamin for Him"),
        ("Essential Kids Multivitamin", "Essential Kids Multivitamin Ages 2 and Up"),
        ("Essential Kids Multivitamin Ages 4 and Up", "Essential Kids Multivitamin Ages 2 and Up"),
        ("Essential Women Multivitamin", "Essential Women Multivitamin Ages 50 and Up"),
        ("CoQ10 200 mg Softgels", "CoQ10 100 mg Softgels"),
        ("Vitamin D3 + K2 Softgels", "Vitamin D3 + K2 Gummies"),
    ],
)
def test_incompatible_variant_never_receives_registry_credit(product, certified_product):
    registry = _make_registry(records=[{
        "program": "USP Verified", "brand": "Ritual", "product": certified_product,
    }])
    result = resolve("Ritual", product, ["USP Verified"], registry)[0]

    assert result.scope == "needs_review"
    assert not result.scores_points()
    assert discover_verified_programs("Ritual", product, registry) == []


@pytest.mark.parametrize(
    ("product", "certified_product"),
    [
        ("CoQ10 100 mg Softgel", "CoQ10 100 mg Softgels"),
        ("Vitamin D3 + K2 Gummy", "Vitamin D3 + K2 Gummies"),
        ("Essential for Women's Multivitamin 18+", "Essential for Women Multivitamin 18+"),
        ("Essential for Women Multivitamin 18+", "Essential for Women Multivitamin 18+"),
        ("Essential Multivitamin Prenatal", "Essential Multivitamin Prenatal and Postnatal"),
        ("Creatine HMB Strawberry Lemonade", "Creatine HMB"),
        ("Essential Daily Multivitamin for Women 50+", "Essential Daily Multivitamin for Her 50+"),
        ("Essential Daily Multivitamin for Men 50+", "Essential Daily Multivitamin for Him 50+"),
        ("Essential Kids Multivitamin 2+", "Essential Kids Multivitamin Ages 2 and Up"),
        ("Essential Women Multivitamin 50+", "Essential Women Multivitamin Ages 50 and Up"),
        ("Essential Daily Multivitamin for Her 50+", "Essential Daily Multivitamin for Women 50+"),
        ("Essential Daily Multivitamin for Him 50+", "Essential Daily Multivitamin for Men 50+"),
        ("Essential Kids Multivitamin Ages 2 and Up", "Essential Kids Multivitamin 2+"),
        ("Essential Women Multivitamin Ages 50 and Up", "Essential Women Multivitamin 50+"),
        ("Essential Daily Multivitamin", "Essential Daily Multivitamin Herbal"),
        ("Essential Daily Multivitamin", "Essential Daily Multivitamin Himalayan"),
        ("Essential Daily Multivitamin", "Essential Daily Multivitamin 50 and Uplift"),
    ],
)
def test_supported_identity_and_base_line_matches_keep_credit(product, certified_product):
    registry = _make_registry(records=[{
        "program": "Informed Choice", "brand": "Example", "product": certified_product,
    }])

    result = resolve("Example", product, ["Informed Choice"], registry)[0]

    assert result.scope == "sku"
    assert result.scores_points()


@pytest.mark.parametrize("product", ["CoQ10 200 mg Softgels", "Vitamin D3 + K2 Softgels"])
def test_real_registry_chooses_compatible_strength_or_form_regardless_of_order(product):
    loaded = CertRegistry.load()
    records = [deepcopy(r) for r in loaded.records_by_program["USP Verified"]
               if r.get("brand") == "Nature Made" and (
                   "CoQ10" in r.get("product", "") or "Vitamin D3 + K2" in r.get("product", ""))]
    for candidates in (records, list(reversed(records))):
        registry = _make_registry(records=candidates)
        result = resolve("Nature Made", product, ["USP Verified"], registry)[0]

        assert result.scope == "sku"
        assert result.matched_product.lower() == f"nature made {product}".lower()


@pytest.mark.parametrize("scope", ["sku", "product_line"])
@pytest.mark.parametrize(
    ("product", "reviewed_product"),
    [("CoQ10 200 mg Softgels", "CoQ10 100 mg Softgels"),
     ("Vitamin D3 + K2 Softgels", "Vitamin D3 + K2 Gummies")],
)
def test_lossy_override_key_cannot_transfer_review_to_another_variant(scope, product, reviewed_product):
    registry = _make_registry(overrides=[{
        "brand": "Nature Made", "product": reviewed_product,
        "program": "USP Verified", "status": "verified", "scope": scope,
        "dsld_id": "reviewed-product",
    }])

    result = resolve("Nature Made", product, ["USP Verified"], registry,
                     dsld_id="reviewed-product")[0]

    assert not result.scores_points()


def test_matching_override_is_not_hidden_by_first_lossy_key_collision():
    registry = _make_registry(overrides=[{
        "brand": "Nature Made", "product": f"CoQ10 {strength} mg Softgels",
        "program": "USP Verified", "status": "verified", "scope": "sku",
        "record_id": f"test-{strength}",
    } for strength in (100, 200)])

    result = resolve("Nature Made", "CoQ10 200 mg Softgels", ["USP Verified"], registry)[0]

    assert result.scores_points()
    assert result.record_id == "test-200"


@pytest.mark.parametrize("scope", ["sku", "product_line"])
def test_override_cannot_certify_a_conflicting_registry_population(scope):
    registry = _make_registry(overrides=[{
        "brand": "Ritual", "product": "Essential for Men Multivitamin 18+",
        "program": "USP Verified", "status": "verified", "scope": scope,
        "matched_brand": "Ritual", "matched_product": "Essential for Women Multivitamin 18+",
    }])

    result = resolve("Ritual", "Essential for Men Multivitamin 18+", ["USP Verified"], registry)[0]

    assert not result.scores_points()


def test_member_reviewed_line_override_retains_its_explicit_scope():
    registry = CertRegistry.load()

    result = resolve("Nature Made", "Vitamin D3 2000 IU", ["USP Verified"], registry,
                     dsld_id="12154")[0]

    assert result.scope == "product_line"
    assert result.scores_points()
    assert result.notes == "curated override"


def test_real_ritual_womens_record_does_not_verify_mens_product():
    registry = CertRegistry.load()

    result = resolve("Ritual", "Essential for Men Multivitamin 18+", ["USP Verified"], registry)[0]

    assert result.scope == "needs_review"
    assert not result.scores_points()


def test_real_population_specific_brand_supplies_label_identity():
    registry = CertRegistry.load()

    result = resolve("Nature Made Kids First", "Multi with Omega-3", ["USP Verified"], registry)[0]

    assert result.scope == "sku"
    assert result.matched_product == "Nature Made Kids First Multi with Omega-3 Gummies"


def test_real_baby_brand_cannot_inherit_kids_multivitamin_credit():
    registry = CertRegistry.load()

    result = resolve("Garden of Life Baby", "Multivitamin Liquid", ["NSF Certified"], registry)[0]

    assert not result.scores_points()


@pytest.mark.parametrize("product", ["Advanced Multivitamin 50+ Gummies", "Multi 50+ Tablets"])
def test_real_for_her_or_him_registry_record_does_not_verify_unspecified_population(product):
    registry = CertRegistry.load()

    result = resolve("Nature Made", product, ["USP Verified"], registry)[0]

    assert result.scope == "needs_review"
    assert not result.scores_points()


@pytest.mark.parametrize(
    ("product", "certified_product"),
    [
        ("Apple Powder", "Creatine Monohydrate Powder Sour Green Apple Flavored"),
        ("Apple Flavored Powder", "Creatine Monohydrate Powder Sour Green Apple Flavored"),
        ("Sour Green Apple Powder", "Creatine Monohydrate Powder Sour Green Apple Flavored"),
        ("Pear Powder", "Protein Powder Pear Flavored"),
        ("Watermelon Powder", "Creatine Watermelon Flavored"),
        ("Example Apple Powder", "Example Creatine Monohydrate Powder Sour Green Apple Flavored"),
    ],
)
def test_flavor_overlap_alone_cannot_establish_certified_product_identity(product, certified_product):
    registry = _make_registry(records=[{
        "brand": "Example", "product": certified_product, "program": "NSF Certified",
    }])

    assert discover_verified_programs("Example", product, registry) == []
    assert not resolve("Example", product, ["NSF Certified"], registry)[0].scores_points()


@pytest.mark.parametrize(
    ("product", "certified_product"),
    [("Apple Powder", "Apple Powder"),
     ("Creatine Monohydrate Powder Sour Green Apple Flavored",
      "Creatine Monohydrate Powder Sour Green Apple Flavored"),
     ("Creatine Watermelon Flavored", "Creatine Watermelon Flavored")],
)
def test_actual_product_identity_keeps_credit_even_with_flavor_words(product, certified_product):
    registry = _make_registry(records=[{
        "brand": "Example", "product": certified_product, "program": "NSF Certified",
    }])

    assert resolve("Example", product, ["NSF Certified"], registry)[0].scores_points()


def test_real_apple_powder_is_not_discovered_as_certified_flavored_creatine():
    registry = CertRegistry.load()

    assert discover_verified_programs("BulkSupplements.com", "Apple Powder", registry) == []


@pytest.mark.parametrize(
    ("brand_directory", "product_id"),
    [("BulkSupplements", "252636"), ("Garden_of_life", "222758")],
)
def test_real_cleaned_product_full_enrichment_does_not_inherit_another_formulation(brand_directory, product_id):
    from enrich_supplements_v3 import SupplementEnricherV3

    scripts = Path(__file__).resolve().parents[1]
    cleaned_path = scripts / f"products/output_{brand_directory}/cleaned/cleaned_batch_1.json"
    if not cleaned_path.is_file():
        pytest.skip("local cleaned corpus not available")
    cleaned = json.loads(cleaned_path.read_text())
    product = next(product for product in cleaned if str(product["id"]) == product_id)
    enricher = SupplementEnricherV3(str(scripts / "config/enrichment_config.json"))

    enriched, issues = enricher.enrich_product(deepcopy(product))

    assert issues == []
    assert not any(entry["scope"] in {"sku", "product_line"}
                   for entry in enriched["verified_cert_programs"])


def test_real_zinc_picolinate_matching_strength_remains_discoverable():
    registry = CertRegistry.load()

    matches = discover_verified_programs("Thorne", "Zinc Picolinate 30 mg", registry,
                                         dsld_id="291803")

    assert any(match.program == "NSF Certified" and match.scope == "sku"
               and match.matched_product == "Thorne® Zinc Picolinate 30 mg"
               for match in matches)


@pytest.mark.parametrize(
    ("product", "certified_product"),
    [("CBD 10 mg Softgels", "CBD+ Focus"),
     ("Vitamin B12 Tablets", "Vitamin B12 + Folate Tablets"),
     ("Vitamin B12 + Folate Tablets", "Vitamin B12 + Folate + Iron Tablets")],
)
def test_named_addition_cannot_be_dropped_from_certification_identity(product, certified_product):
    registry = _make_registry(records=[{
        "brand": "Example", "product": certified_product, "program": "NSF Certified",
    }])

    assert discover_verified_programs("Example", product, registry) == []


@pytest.mark.parametrize(
    ("product", "certified_product"),
    [("CBD+ Focus", "CBD+ Focus"),
     ("Vitamin B12 with Folate Tablets", "Vitamin B12 + Folate Tablets"),
     ("Complete Formula", "Complete Formula+™"),
     ("Complete Daily Multivitamin for Women 50+", "Complete Daily Multivitamin for Women 50+ Formula")],
)
def test_named_addition_matching_uses_meaningful_tokens_not_literal_plus(product, certified_product):
    registry = _make_registry(records=[{
        "brand": "Example", "product": certified_product, "program": "NSF Certified",
    }])

    assert resolve("Example", product, ["NSF Certified"], registry)[0].scores_points()
