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
        ("Essential Daily Multivitamin", "Essential Daily Multivitamin Herbal"),
        ("Essential Daily Multivitamin", "Essential Daily Multivitamin Himalayan"),
        ("Essential Daily Multivitamin", "Essential Daily Multivitamin 50 and Uplift"),
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

    result = resolve("Nature Made Kids First", "Multi with Omega-3", ["USP Verified"], registry,
                     label_context={"form_factor_canonical": "gummy"})[0]

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
                                         dsld_id="291803", label_context={"form_factor_canonical": "capsule"})

    assert any(match.program == "NSF Certified" and match.scope == "sku"
               and match.matched_product == "Thorne® Zinc Picolinate 30 mg"
               for match in matches)


@pytest.mark.parametrize("source,dsld_id,record_id", [
    ("output_Garden_of_life_enriched/enriched/enriched_cleaned_batch_2.json", "326765", "NSF_CERTIFIE_90843FED563A"),
    ("output_Nature_Made_enriched/enriched/enriched_cleaned_batch_1.json", "179567", "USP_VERIFIED_E23C156DFA48"),
    ("output_Nature_Made_enriched/enriched/enriched_cleaned_batch_1.json", "179682", "USP_VERIFIED_E23C156DFA48"),
    ("output_GNC_enriched/enriched/enriched_cleaned_batch_4.json", "69623", "CONSUMERLAB_1EF2345DA0FC"),
    ("output_GNC_enriched/enriched/enriched_cleaned_batch_2.json", "243038", "CONSUMERLAB_B22055A0546B"),
    ("output_GNC_enriched/enriched/enriched_cleaned_batch_5.json", "77146", "CONSUMERLAB_24CA69C78AC5"),
    ("output_GNC_enriched/enriched/enriched_cleaned_batch_5.json", "77163", "CONSUMERLAB_24CA69C78AC5"),
    ("output_Garden_of_life_enriched/enriched/enriched_cleaned_batch_2.json", "327402", "NSF_CERTIFIE_D4BCF7D29051"),
    ("output_Kirkland_Signature_enriched/enriched/enriched_cleaned_batch_1.json", "239499", "USP_VERIFIED_39DC5AE7CE69"),
    ("output_Olly/cleaned/cleaned_batch_1.json", "230157", "NSF_CERTIFIE_EAC1D5275C44"),
    ("output_Olly/cleaned/cleaned_batch_1.json", "273631", "NSF_CERTIFIE_F995BFDC01CE"),
    ("output_Olly/cleaned/cleaned_batch_1.json", "290548", "NSF_CERTIFIE_3D37AC2815DE"),
])
def test_real_label_form_detail_preserves_complete_registry_identity(source, dsld_id, record_id):
    path = Path(__file__).resolve().parents[1] / "products" / source
    if not path.is_file():
        pytest.skip("local enriched corpus not available")
    product = next(row for row in json.loads(path.read_text()) if str(row.get("id")) == dsld_id)

    matches = discover_verified_programs(
        product["brandName"], product["fullName"], CertRegistry.load(),
        dsld_id=dsld_id, label_context=product,
    )

    assert any(row.record_id == record_id and row.scores_points() for row in matches)


@pytest.mark.parametrize("brand_directory,dsld_id,record_id,retained_record", [
    ("GNC", "210510", "CONSUMERLAB_1EC707BB1D61", "INFORMED_CHO_2A37E46C977C"),
    ("GNC", "220082", "CONSUMERLAB_1EC707BB1D61", "INFORMED_CHO_E04203686D9C"),
    ("GNC", "18518", "INFORMED_CHO_FC7B49F1D312", None),
    ("Nature_Made", "179748", "USP_VERIFIED_14A671BAE9D9", None),
    ("Nature_Made", "180107", "USP_VERIFIED_14A671BAE9D9", None),
    ("Nature_Made", "271506", "USP_VERIFIED_14A671BAE9D9", None),
    ("Nature_Made", "211392", "INFORMED_CHO_C158CCD681EE", None),
])
def test_real_named_variant_never_inherits_generic_sku(brand_directory, dsld_id, record_id, retained_record):
    path = Path(__file__).resolve().parents[1] / f"products/output_{brand_directory}_enriched/enriched/enriched_cleaned_batch_1.json"
    if not path.is_file():
        pytest.skip("local enriched corpus not available")
    product = next(row for row in json.loads(path.read_text()) if str(row.get("id")) == dsld_id)

    matches = discover_verified_programs(
        product["brandName"], product["fullName"], CertRegistry.load(),
        dsld_id=dsld_id, label_context=product,
    )

    assert not any(row.record_id == record_id for row in matches)
    if retained_record:
        assert any(row.record_id == retained_record and row.scores_points() for row in matches)


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


def _producer_cert_resolution(product, registry):
    from enrich_supplements_v3 import SupplementEnricherV3

    enricher = SupplementEnricherV3.__new__(SupplementEnricherV3)
    enricher._cert_registry_cache = registry
    return enricher._resolve_verified_cert_programs(
        product, {"programs": [{"name": "USP Verified"}]}, [],
    )


@pytest.mark.parametrize("form_field", ["form_factor_canonical", "form_factor"])
def test_cert_producer_supplies_actual_product_form(form_field):
    registry = _make_registry(records=[{
        "brand": "Example", "product": "Vitamin D3 5000 IU Capsules", "program": "USP Verified",
    }])
    product = {"brandName": "Example", "fullName": "D3 5000 IU", form_field: "capsule"}

    assert _producer_cert_resolution(product, registry)[0]["scope"] == "sku"


@pytest.mark.parametrize("unit", ["Once Daily Vegetarian Capsule(s)", "Vegetarian Capsules", "30 Vegetarian Capsules"])
def test_printed_net_contents_form_descriptor_preserves_culturelle_identity(unit):
    registry = _make_registry(records=[{
        "brand": "Culturelle", "product": "Culturelle Digestive Daily Probiotic Vegetarian Capsules",
        "program": "USP Verified",
    }])
    product = {"id": "250851", "brandName": "Culturelle", "fullName": "Digestive Daily Probiotic",
               "form_factor_canonical": "capsule", "netContents": [{"quantity": 10, "unit": unit}]}

    assert _producer_cert_resolution(product, registry)[0]["scope"] == "sku"


@pytest.mark.parametrize("unit", ["Capsules", "Vegan Capsules", "No Vegetarian Capsules",
                                    "Take one Vegetarian Capsule daily", "50B Vegetarian Capsules"])
def test_net_contents_adapter_cannot_guess_missing_material_qualifier(unit):
    registry = _make_registry(records=[{
        "brand": "Culturelle", "product": "Digestive Daily Probiotic Vegetarian Capsules",
        "program": "USP Verified",
    }])
    product = {"brandName": "Culturelle", "fullName": "Digestive Daily Probiotic",
               "form_factor_canonical": "capsule", "netContents": [{"unit": unit}],
               "statements": [{"notes": "Vegetarian"}]}

    assert _producer_cert_resolution(product, registry)[0]["scope"] == "needs_review"


def test_net_contents_once_daily_does_not_supply_missing_named_daily_variant():
    registry = _make_registry(records=[{
        "brand": "Culturelle", "product": "Digestive Daily Probiotic Vegetarian Capsules",
        "program": "USP Verified",
    }])
    product = {"brandName": "Culturelle", "fullName": "Digestive Probiotic",
               "form_factor_canonical": "capsule",
               "netContents": [{"unit": "Once Daily Vegetarian Capsule(s)"}]}

    assert _producer_cert_resolution(product, registry)[0]["scope"] == "needs_review"


def test_real_culturelle_form_descriptor_supplies_registry_identity_at_producer_boundary():
    path = Path(__file__).resolve().parents[1] / "products/output_Culturelle_enriched/enriched/enriched_cleaned_batch_1.json"
    if not path.is_file():
        pytest.skip("local enriched corpus not available")
    product = next(row for row in json.loads(path.read_text()) if str(row["id"]) == "250851")

    matches = _producer_cert_resolution(product, CertRegistry.load())

    assert any(row["scope"] == "sku" and row["record_id"] == "USP_VERIFIED_A72E3970D2E5" for row in matches)
