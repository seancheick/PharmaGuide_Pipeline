"""RC-5: product_label_corrections.json — reviewer-signed corrections
for manufacturer label defects.

Background

Some DSLD product labels print typos that produce clinically
impossible or dangerous ingredients. The first reviewer-signed
correction is GNC pid=69734 ("Women's Ultra Mega Active Vanilla")
where the label prints "Insulin" between "Inositol" and
"Fructooligosaccharides" — but Insulin is a hormone biologic
regulated under FDA's BPCIA pathway and cannot legally appear on a
US supplement label. The sibling fiber-blend context (Inositol,
FOS, Gum Acacia, Cellulose Gum, MCT Oil) is overwhelming evidence
of an "Inulin" typo.

Why this is a mechanism, not a per-incident patch

A global "Insulin → Inulin" alias is unsafe: it would let ANY future
supplement label literally listing "Insulin" be silently
re-interpreted as fiber. The correct fix is a reviewer-signed,
product-scoped override mechanism. This batch builds that
mechanism with Insulin/pid=69734 as the first entry. Future
label-typo cases (Magnesuim, Calcuim, etc.) go through the same
reviewer pipeline.

What this test pins

1. Schema: every correction entry must carry the required reviewer
   provenance fields.
2. Single-record fidelity: the GNC pid=69734 entry corrects
   "Insulin" → "Inulin" with the documented evidence.
3. Scope discipline: the override is keyed by (dsld_id,
   raw_ingredient_text). Tests assert the file structure supports
   scope=dsld_id_only and does NOT permit global aliasing.
4. UNUSED future drug tokens: if a row's raw_ingredient_text is a
   known regulated-drug token (Insulin, Acetaminophen, Ibuprofen)
   and there is NO override for the product, the cleaner must NOT
   silently map the row. This test pins the policy contract; the
   quarantine-emit code lives in enhanced_normalizer.py and is
   covered by integration tests separately.

Future work (out of scope for this test file)

- Integration test: shadow-clean GNC pid=69734 and assert the row
  emerges with name="Inulin" and provenance_tag set.
- Quarantine integration test: synthesize a fake product with raw
  "Insulin" but no override, assert the row routes to quarantine.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_OVERRIDES_PATH = os.path.join(
    _ROOT, "scripts", "data", "curated_overrides",
    "product_label_corrections.json"
)

# Drug tokens that must NEVER appear in a supplement label without a
# reviewer-signed product-scoped correction. Adding to this list is
# itself a reviewer decision.
KNOWN_DRUG_TOKENS = {
    "insulin",
    "acetaminophen", "paracetamol", "tylenol",
    "ibuprofen", "advil", "motrin",
    "naproxen", "aleve",
    "aspirin",
    "metformin",
    "warfarin",
    "heparin",
}


@pytest.fixture(scope="module")
def overrides() -> Dict[str, Any]:
    assert os.path.exists(_OVERRIDES_PATH), (
        f"product_label_corrections.json missing at {_OVERRIDES_PATH}"
    )
    with open(_OVERRIDES_PATH) as f:
        return json.load(f)


def test_schema_has_metadata(overrides):
    meta = overrides.get("_metadata") or {}
    assert meta.get("schema_version"), "schema_version required"
    assert meta.get("description"), "description required"
    assert meta.get("purpose"), "purpose required"
    assert meta.get("review_policy"), "review_policy required"
    assert meta.get("unmatched_drug_tokens_policy"), (
        "unmatched_drug_tokens_policy required — the quarantine path "
        "is a contract obligation, not an implementation detail"
    )
    actual_count = len(overrides.get("corrections", {}))
    assert meta.get("total_entries") == actual_count, (
        f"_metadata.total_entries={meta.get('total_entries')} but "
        f"actual={actual_count}"
    )


def test_corrections_is_keyed_by_dsld_id(overrides):
    corrections = overrides.get("corrections") or {}
    assert corrections, "corrections payload must not be empty"
    for key in corrections.keys():
        # Existing product identities are numeric DSLD IDs or canonical manual-label IDs.
        assert key.isdigit() or (key.startswith("PG_SUB_") and len(key) == 39
                                and all(c in "0123456789ABCDEF" for c in key[7:])), (
            f"correction key {key!r} must be an existing DSLD or canonical PG_SUB product id"
        )


REQUIRED_ENTRY_FIELDS = (
    "brand",
    "product_name",
    "raw_ingredient_text",
    "corrected_ingredient_text",
    "correction_fields",
    "evidence",
    "sources",
    "reviewer",
    "review_date",
    "scope",
    "provenance_tag",
)

ALLOWED_SCORING_DISPOSITIONS = {"source_descriptor", "unresolved_unit"}


def test_every_correction_has_reviewer_provenance(overrides):
    corrections = overrides.get("corrections") or {}
    for dsld_id, entry in corrections.items():
        for field in REQUIRED_ENTRY_FIELDS:
            assert entry.get(field), (
                f"correction[{dsld_id}] missing required field "
                f"{field!r}. Got: {entry}"
            )
        assert entry["scope"] == "dsld_id_only", (
            f"correction[{dsld_id}] scope must be 'dsld_id_only' — "
            f"global aliasing of label-typo tokens is explicitly "
            f"forbidden because future supplement labels printing the "
            f"same token must re-enter the reviewer pipeline. Got: "
            f"{entry.get('scope')!r}"
        )
        assert isinstance(entry["sources"], list) and entry["sources"], (
            f"correction[{dsld_id}] sources must be a non-empty list "
            f"of authoritative URLs"
        )
        assert entry["review_date"].count("-") == 2, (
            f"correction[{dsld_id}] review_date must be ISO 8601 "
            f"YYYY-MM-DD. Got: {entry['review_date']!r}"
        )


def test_scoring_dispositions_use_the_reviewed_allowlist(overrides):
    for dsld_id, entry in (overrides.get("corrections") or {}).items():
        disposition = entry.get("scoring_disposition")
        if disposition is None:
            continue
        assert disposition in ALLOWED_SCORING_DISPOSITIONS, (
            f"correction[{dsld_id}] uses unsupported scoring_disposition "
            f"{disposition!r}"
        )
        assert "scoring_disposition" in entry.get("correction_fields", []), (
            f"correction[{dsld_id}] must declare scoring_disposition in "
            "correction_fields"
        )


def test_gnc_69734_insulin_correction_present(overrides):
    """The first reviewer-signed correction. Pins the canonical
    record so accidental edits get caught."""
    corrections = overrides.get("corrections") or {}
    entry = corrections.get("69734")
    assert entry, "correction for GNC pid=69734 (Insulin → Inulin) missing"
    assert entry["raw_ingredient_text"] == "Insulin", (
        f"raw_ingredient_text must be 'Insulin' (case-sensitive — the "
        f"label-printed form). Got: {entry.get('raw_ingredient_text')!r}"
    )
    assert entry["corrected_ingredient_text"] == "Inulin", (
        f"corrected_ingredient_text must be 'Inulin'. Got: "
        f"{entry.get('corrected_ingredient_text')!r}"
    )
    evidence = (entry.get("evidence") or "").lower()
    # Evidence must cite the sibling-context reasoning + the
    # regulatory-status reason. Both signals are required.
    assert "inositol" in evidence or "fos" in evidence or "fiber" in evidence, (
        f"evidence must cite the sibling fiber-blend context (inositol "
        f"/ FOS / fiber). Got: {entry.get('evidence')!r}"
    )
    assert "bpcia" in evidence or "biologic" in evidence or "hormone" in evidence, (
        f"evidence must cite Insulin's regulatory status as a hormone "
        f"biologic that cannot legally appear on a US supplement label. "
        f"Got: {entry.get('evidence')!r}"
    )


def test_gnc_259789_iodine_unit_correction_present(overrides):
    """The live DSLD JSON says mg, but the official DSLD label PDF says mcg."""
    entry = (overrides.get("corrections") or {}).get("259789")

    assert entry, "correction for GNC pid=259789 iodine unit is missing"
    assert entry["raw_ingredient_text"] == "Iodine"
    assert entry["corrected_ingredient_text"] == "Iodine"
    assert entry["raw_quantity_unit"] == "mg"
    assert entry["corrected_quantity_unit"] == "mcg"
    assert "quantity.unit" in entry["correction_fields"]
    assert (
        "https://api.ods.od.nih.gov/dsld/s3/pdf/259789.pdf"
        in entry["sources"]
    )


def test_natures_way_328117_boron_unit_correction_present(overrides):
    """The live DSLD JSON says mg, but the official DSLD label PDF says mcg."""
    entry = (overrides.get("corrections") or {}).get("328117")

    assert entry, "correction for Nature's Way pid=328117 boron unit is missing"
    assert entry["raw_ingredient_text"] == "Boron"
    assert entry["corrected_ingredient_text"] == "Boron"
    assert entry["raw_quantity_unit"] == "mg"
    assert entry["corrected_quantity_unit"] == "mcg"
    assert "quantity.unit" in entry["correction_fields"]
    assert (
        "https://api.ods.od.nih.gov/dsld/s3/pdf/328117.pdf"
        in entry["sources"]
    )


@pytest.mark.parametrize(
    ("dsld_id", "product_name", "verification_source"),
    [
        (
            "259709",
            "Weight Gainer Strawberries & Cream",
            "https://www.gnc.com/on/demandware.static/-/Sites-GNC2-Library/default/pdf/369937_lbl.pdf",
        ),
        (
            "69608",
            "Weight Gainer Strawberries & Cream",
            "https://www.gnc.com/on/demandware.static/-/Sites-GNC2-Library/default/pdf/369937_lbl.pdf",
        ),
        (
            "69599",
            "Weight Gainer Vanilla Ice Cream",
            "https://api.ods.od.nih.gov/dsld/v9/label/69599",
        ),
    ],
)
def test_gnc_weight_gainer_protein_unit_corrections_are_source_verified(
    overrides, dsld_id, product_name, verification_source
):
    entry = (overrides.get("corrections") or {}).get(dsld_id)

    assert entry, f"correction for GNC weight gainer {dsld_id} is missing"
    assert entry["product_name"] == product_name
    assert entry["raw_ingredient_text"] == "Protein"
    assert entry["corrected_ingredient_text"] == "Protein"
    assert entry["raw_quantity_unit"] == "mg"
    assert entry["corrected_quantity_unit"] == "Gram(s)"
    assert entry["correction_fields"] == ["quantity.unit"]
    assert verification_source in entry["sources"]


def test_doctors_best_selenium_quantity_and_unit_are_source_verified(overrides):
    entry = (overrides.get("corrections") or {}).get("302650")

    assert entry, "correction for Doctor's Best 302650 selenium is missing"
    assert entry["raw_ingredient_text"] == "SelenoExcell "
    assert entry["corrected_ingredient_text"] == "Selenium"
    assert entry["raw_quantity_value"] == 640
    assert entry["raw_quantity_unit"] == "mg"
    assert entry["corrected_quantity_value"] == 200
    assert entry["corrected_quantity_unit"] == "mcg"
    assert "quantity.value" in entry["correction_fields"]
    assert "quantity.unit" in entry["correction_fields"]
    assert (
        "https://www.doctorsbest.com/products/"
        "doctor-s-best-comprehensive-prostate-formula-120-veggie-caps-25"
        in entry["sources"]
    )


def test_cvs_25935_crossed_dha_identity_is_source_verified(overrides):
    """The live NIH record's own product copy identifies the 200 mg row as DHA."""
    entry = (overrides.get("corrections") or {}).get("25935")

    assert entry, "correction for CVS pid=25935 crossed DHA row is missing"
    assert entry["product_name"] == "DHA"
    assert entry["raw_ingredient_text"] == "Dextrose"
    assert entry["corrected_ingredient_text"] == "DHA"
    assert entry["raw_unii_code"] == "IY9XDZ35W2"
    assert entry["corrected_unii_code"] is None
    assert entry["corrected_category"] == "fatty acid"
    assert entry["corrected_ingredient_group"] == "DHA"
    assert entry["corrected_forms"] == []
    assert entry["correction_fields"] == [
        "name",
        "uniiCode",
        "category",
        "ingredientGroup",
        "forms",
    ]
    assert (
        "https://api.ods.od.nih.gov/dsld/v9/label/25935"
        in entry["sources"]
    )


def test_ravage_crossed_vitamin_b_row_is_source_verified(overrides):
    """The exact NIH label prints the 5.3 g row as Anabolic Muscle Primer."""
    entry = (overrides.get("corrections") or {}).get("1179")

    assert entry, "correction for Ravage 1179 crossed blend row is missing"
    assert entry["product_name"] == "Ravage Fruit Punch"
    assert entry["raw_ingredient_text"] == "vitamin B"
    assert entry["corrected_ingredient_text"] == "Anabolic Muscle Primer"
    assert entry["corrected_category"] == "blend"
    assert entry["corrected_ingredient_group"] == "Blend (Combination)"
    assert [form["name"] for form in entry["corrected_forms"]] == [
        "Betaine Anhydrous",
        "Micronized L-Leucine",
        "Fenugreek Extract (Trigonella foenum) (seed) (standardized for fenuside)",
        "HMB Powder",
        "Saw Palmetto Extract (Serenoa repens) (fruit)",
        "Yohimbe Powder (Pausinystalia yohimbe) (bark)",
        "Wild Yam Extract (Dioscorea villosa) (root)",
    ]
    assert entry["correction_fields"] == [
        "name",
        "category",
        "ingredientGroup",
        "forms",
    ]
    assert "https://api.ods.od.nih.gov/dsld/s3/pdf/1179.pdf" in entry["sources"]


@pytest.mark.parametrize(
    ("dsld_id", "product_name", "ingredient", "dose_mg"),
    [
        ("2248", "Flax Seed Oil 1300", "Flax seed Oil", 1300),
        ("17794", "Flax Seed Oil 1000", "Flax seed Oil", 1000),
        ("57157", "Evening Primrose Oil 1300", "Evening Primrose Oil", 1300),
        ("75189", "Evening Primrose Oil 1300", "Evening Primrose Oil", 1300),
        ("75256", "Evening Primrose Oil 500", "Evening Primrose Oil", 1000),
        ("75261", "Evening Primrose Oil 1300", "Evening Primrose Oil", 1300),
        ("79163", "Evening Primrose Oil 500", "Evening Primrose Oil", 500),
    ],
)
def test_statement_backed_missing_form_doses_are_product_scoped(
    overrides, dsld_id, product_name, ingredient, dose_mg
):
    entry = (overrides.get("corrections") or {}).get(dsld_id)

    assert entry, f"correction for DSLD {dsld_id} missing form dose is absent"
    assert entry["product_name"] == product_name
    assert entry["raw_ingredient_text"] == ingredient
    assert entry["corrected_ingredient_text"] == ingredient
    assert entry["raw_quantity_missing"] is True
    assert entry["corrected_quantity_value"] == dose_mg
    assert entry["corrected_quantity_unit"] == "mg"
    assert entry["correction_fields"] == ["quantity.missing_to_value"]
    assert (
        f"https://api.ods.od.nih.gov/dsld/v9/label/{dsld_id}"
        in entry["sources"]
    )


@pytest.mark.parametrize(
    ("dsld_id", "product_name", "ingredient", "raw_unit", "corrected_unit"),
    [
        ("66380", "Multi Vitamin", "Niacin", "ng", "mg"),
        ("46729", "Alive! Once Daily Men's 50+", "Vitamin B6", "ng", "mg"),
        ("69455", "Amplified Wheybolic Extreme 60 Ripped Strawberries & Cream", "Niacin", "Gram(s)", "mg"),
        ("254204", "Women's Multi", "Biotin", "m.c.u.", "mcg"),
        ("311874", "PRE Fruit Punch", "Vitamin B12", "mcg DFE", "mcg"),
        ("308222", "Healthy Mom Prenatal Multi", "Docosahexaenoic Acid", "ng", "mg"),
        ("243029", "Beyond Raw Orange Mango", "Caffeine Anhydrous", "mmg", "mg"),
        ("66883", "Creatine Plus 5950 Unflavored", "Glycine", "Jar(s)", "mg"),
        ("261915", "Airborne Elderberry Effervescent Tablets", "Vitamin A", "mg", "mcg RAE"),
        ("256977", "Centrum Specialist Energy Multivitamin", "Biotin", "mC Unit(s)", "mcg"),
        ("257088", "Centrum Men", "Vitamin B12", "mcg DFE", "mcg"),
        ("205918", "Kidz Vitamin C 250 mg Fruit Punch", "Zinc", "ng", "mg"),
        ("250997", "Baby & Me 2 Prenatal Multi", "Copper", "m.c.u.", "mg"),
        ("265207", "Multi for Men", "Vitamin B6", "mg {alpha}-TE", "mg"),
        ("327573", "Men's 55+ Advanced Multivitamin", "Thiamine", "NP", "mg"),
        ("46802", "Acidophilus", "active Lactobacillus acidophilus", "{Unit(s)}", "CFU"),
        ("19916", "Adults' 50+ Multivitamin/Multimineral", "Boron", "mg", "mcg"),
        ("265197", "Men Over 40 One Daily", "Boron", "mg", "mcg"),
        ("76510", "Triple Strength Glucosamine Chondroitin MSM with Vitamin D", "Vitamin D", "NP", "IU"),
        ("5862", "Amplified Endurance Booster Blue Raspberry", "Copper", "g", "mg"),
        ("5864", "Amplified Endurance Booster Orange", "Copper", "g", "mg"),
        ("18529", "Amplified Endurance Booster Blue Raspberry", "Copper", "g", "mg"),
    ],
)
def test_verified_source_unit_corrections_are_product_scoped(
    overrides, dsld_id, product_name, ingredient, raw_unit, corrected_unit
):
    entry = (overrides.get("corrections") or {}).get(dsld_id)

    assert entry, f"correction for DSLD {dsld_id} is missing"
    assert entry["product_name"] == product_name
    assert entry["raw_ingredient_text"] == ingredient
    assert entry["corrected_ingredient_text"] == ingredient
    assert entry["raw_quantity_unit"] == raw_unit
    assert entry["corrected_quantity_unit"] == corrected_unit
    assert "quantity.unit" in entry["correction_fields"]
    assert f"https://api.ods.od.nih.gov/dsld/s3/pdf/{dsld_id}.pdf" in entry["sources"]


def test_cognimag_299037_crossed_hierarchy_names_are_corrected(overrides):
    """The API crosses the printed nutrient and source-material row names."""
    entry = (overrides.get("corrections") or {}).get("299037")

    assert entry, "correction for CogniMag pid=299037 is missing"
    assert entry["raw_ingredient_text"] == "Magnesium"
    assert entry["corrected_ingredient_text"] == "Magtein Magnesium L-Threonate"
    assert entry["raw_unii_code"] == "I38ZP9992A"
    assert entry["corrected_unii_code"] is None
    additional = entry.get("additional_row_corrections") or []
    assert additional == [{
        "raw_ingredient_text": "Magtein Magnesium L-Threonate",
        "corrected_ingredient_text": "Magnesium",
        "correction_fields": ["name"],
    }]
    assert (
        "https://api.ods.od.nih.gov/dsld/s3/pdf/299037.pdf"
        in entry["sources"]
    )


def test_transglucosidase_59047_activity_dose_is_restored_from_exact_label(overrides):
    entry = (overrides.get("corrections") or {}).get("59047")

    assert entry, "correction for DSLD 59047 is missing"
    assert entry["product_name"] == "GlycemicPro Transglucosidase"
    assert entry["raw_ingredient_text"] == "Transglucosidase"
    assert entry["corrected_ingredient_text"] == "Transglucosidase"
    assert entry["raw_quantity_value"] == 0
    assert entry["raw_quantity_unit"] == "NP"
    assert entry["corrected_quantity_value"] == 450000
    assert entry["corrected_quantity_unit"] == "TG"
    assert set(entry["correction_fields"]) == {
        "uniiCode",
        "quantity.value",
        "quantity.unit",
    }
    assert (
        "https://api.ods.od.nih.gov/dsld/s3/pdf/59047.pdf"
        in entry["sources"]
    )


def test_life_extension_328300_koact_label_text_is_restored(overrides):
    entry = (overrides.get("corrections") or {}).get("328300")

    assert entry, "correction for Life Extension 328300 KoAct is missing"
    assert entry["raw_ingredient_text"] == "KoAct"
    assert entry["corrected_ingredient_text"] == (
        "KoAct Calcium Collagen Chelate"
    )
    assert entry["correction_fields"] == ["name", "scoring_disposition"]
    assert entry["scoring_disposition"] == "source_descriptor"
    assert entry["scope"] == "dsld_id_only"
    assert entry["provenance_tag"] == "official_label_text_correction"
    assert (
        "https://api.ods.od.nih.gov/dsld/s3/pdf/328300.pdf"
        in entry["sources"]
    )


def test_megafood_327590_springtail_is_product_scoped_horsetail_correction(
    overrides,
):
    entry = (overrides.get("corrections") or {}).get("327590")

    assert entry, "correction for MegaFood pid=327590 is missing"
    assert entry["raw_ingredient_text"] == "Springtail"
    assert entry["corrected_ingredient_text"] == "Spring Horsetail"
    assert entry["correction_fields"] == ["name"]
    assert entry["scope"] == "dsld_id_only"
    assert entry["provenance_tag"] == "official_label_text_correction"


def test_no_correction_targets_known_drug_token_globally(overrides):
    """No two corrections may share the same raw_ingredient_text
    targeting a known drug token — that would amount to de-facto
    global aliasing and defeats the scope=dsld_id_only discipline."""
    corrections = overrides.get("corrections") or {}
    by_token = {}
    for dsld_id, entry in corrections.items():
        token = (entry.get("raw_ingredient_text") or "").strip().lower()
        if token in KNOWN_DRUG_TOKENS:
            by_token.setdefault(token, []).append((dsld_id, entry))
    # Each known drug token may have multiple reviewer-signed
    # corrections (one per product), and that's allowed and expected
    # over time. This test just makes sure we don't accidentally have
    # an entry without scope='dsld_id_only'.
    for token, entries in by_token.items():
        for dsld_id, entry in entries:
            assert entry.get("scope") == "dsld_id_only", (
                f"correction for drug-token {token!r} on pid={dsld_id} "
                f"must have scope='dsld_id_only'"
            )


def test_unmatched_drug_tokens_policy_is_documented(overrides):
    """The quarantine policy for unmatched drug tokens is part of
    the data contract, not an implementation choice. Verifying it
    here makes the contract loud."""
    policy = (overrides.get("_metadata") or {}).get(
        "unmatched_drug_tokens_policy", ""
    ).lower()
    assert "quarantine" in policy or "human" in policy or "review" in policy, (
        f"unmatched_drug_tokens_policy must describe the quarantine / "
        f"human-review fallback. Got: {policy!r}"
    )
    assert "silently" in policy or "not" in policy, (
        f"unmatched_drug_tokens_policy must state that silent mapping "
        f"is forbidden. Got: {policy!r}"
    )


@pytest.mark.parametrize("dsld_id", ["31063", "801", "312980", "28976", "28980"])
def test_maximum_nutrition_molybdenum_conflict_is_not_a_verified_unit_correction(overrides, dsld_id):
    entry = overrides["corrections"].get(dsld_id)
    assert entry, "Preserve the source conflict: printed75mg versus100%DV"
    assert entry["raw_ingredient_text"] == "Molybdenum"
    assert entry["corrected_ingredient_text"] == "Molybdenum"
    assert entry["raw_quantity_unit"] == "mg"
    if dsld_id in {"31063", "801"}:
        assert entry["corrected_quantity_unit"] is None
        assert entry["scoring_disposition"] == "unresolved_unit"
        assert entry["raw_quantity_value"] == 75
        assert entry["correction_fields"] == ["scoring_disposition"]
    else:
        # Other exact-label corrections retain their independently reviewed units.
        assert entry["corrected_quantity_unit"] == "mcg"
        assert "quantity.unit" in entry["correction_fields"]
    assert f"https://api.ods.od.nih.gov/dsld/s3/pdf/{dsld_id}.pdf" in entry["sources"]


@pytest.mark.parametrize("pid,name,forms,amount", [
    ("326244", "Vitamin C", ["Calcium Ascorbate"], 180),
    ("321393", "Chlorella", [], 250),
    ("321394", "Chlorella", [], 250),
])
def test_exact_source_forms_do_not_borrow_wrong_api_chemistry(pid, name, forms, amount):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((Path(__file__).parent / "fixtures" / f"completion_source_{pid}_raw.json").read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    source_ref = 'ingredientRows[2]' if name == 'Vitamin C' else 'ingredientRows[1]'
    [row] = [r for r in cleaned["activeIngredients"] if r['raw_source_path'] == source_ref]
    assert [form["name"] for form in row["forms"]] == forms
    assert row["quantity"] == amount and row["unit"] == "mg"
    assert row["canonical_id"] == ("vitamin_c" if name == "Vitamin C" else "chlorella")
    assert row["source_correction"]["provenance_tag"] == "official_label_form_correction"


@pytest.mark.parametrize("change", ["amount", "unit", "path", "form"])
def test_exact_source_form_correction_does_not_transfer_to_a_changed_edition(change):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((Path(__file__).parent / "fixtures" / "completion_source_326244_raw.json").read_text())
    rows = raw["ingredientRows"]
    if change == "amount":
        rows[2]["quantity"][0]["quantity"] = 181
    elif change == "unit":
        rows[2]["quantity"][0]["unit"] = "mcg"
    elif change == "path":
        rows[2], rows[3] = rows[3], rows[2]
    else:
        rows[2]["forms"][0]["name"] = "Other declared form"
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    [row] = [r for r in cleaned["activeIngredients"] if r["name"] == "Vitamin C"]
    assert [form["name"] for form in row["forms"]] == (["Other declared form"] if change == "form" else ["Calcium Carbonate"])


def test_reviewed_form_correction_preserves_malformed_source_for_normal_validation():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'completion_source_321393_raw.json').read_text())
    rows = raw['ingredientRows']
    rows[1]['forms'] = ['unparsed source form']
    normalizer = EnhancedDSLDNormalizer()
    normalizer._stamp_raw_source_paths(rows, 'ingredientRows')
    normalizer._apply_label_corrections(rows, '321393')
    assert rows[1]['forms'] == ['unparsed source form']
    assert not rows[1].get('_label_correction_applied')


def test_printed_forskolin_marker_dose_keeps_compound_identity_not_source_plant():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'completion_source_241681_raw.json').read_text())
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)
    enriched, _ = SupplementEnricherV3().enrich_product(cleaned)
    rows = enriched['ingredient_quality_data']['ingredients']
    [row] = [r for r in rows if r.get('raw_source_path') == 'ingredientRows[0].nestedRows[0]']
    assert row['canonical_id'] == 'forskolin'
    assert row['quantity'] == 25 and row['unit'] == 'mg'
    [parent] = [r for r in cleaned['activeIngredients'] if r.get('raw_source_path') == 'ingredientRows[0]']
    assert parent['quantity'] == 250 and parent['unit'] == 'mg'
    assert row['source_label_name'] == 'Forskolin'


@pytest.mark.parametrize('forms', [None, {}, ['unparsed form']])
def test_category_only_correction_requires_its_reviewed_source_form(forms):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'completion_source_241681_raw.json').read_text())
    rows = raw['ingredientRows']; marker = rows[0]['nestedRows'][0]; marker['forms'] = forms
    normalizer = EnhancedDSLDNormalizer(); normalizer._stamp_raw_source_paths(rows, 'ingredientRows')
    normalizer._apply_label_corrections(rows, '241681')
    assert marker['category'] == 'botanical'
    assert not marker.get('_label_correction_applied')


def test_working_corrected_forms_cannot_mutate_cached_correction_source():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    normalizer = EnhancedDSLDNormalizer()
    def apply():
        rows = json.loads((Path(__file__).parent / 'fixtures' / 'completion_source_326244_raw.json').read_text())['ingredientRows']
        normalizer._stamp_raw_source_paths(rows, 'ingredientRows'); normalizer._apply_label_corrections(rows, '326244')
        return rows[2]
    first = apply(); first['forms'][0]['name'] = 'Mutated working object'
    second = apply()
    assert second['forms'][0]['name'] == 'Calcium Ascorbate'


@pytest.mark.parametrize('pid,source_ref,wrong', [
    ('326244', 'ingredientRows[2]', 'Calcium Carbonate'),
    ('321393', 'ingredientRows[1]', 'Omega-9 Fatty Acids'),
    ('321394', 'ingredientRows[1]', 'Omega-9 Fatty Acids'),
])
def test_reviewed_form_facts_survive_the_export_display_ledger(pid, source_ref, wrong):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    from build_final_db import build_detail_blob
    raw = json.loads((Path(__file__).parent / 'fixtures' / f'completion_source_{pid}_raw.json').read_text())
    clean = EnhancedDSLDNormalizer().normalize_product(raw)
    enriched, _ = SupplementEnricherV3().enrich_product(clean)
    blob = build_detail_blob(enriched, build_scored_artifact(enriched))
    [row] = [r for r in blob['display_ingredients'] if r.get('raw_source_path') == source_ref]
    assert '_label_forms_corrected' not in json.dumps(clean)
    assert '_forms_corrected' not in json.dumps(blob)
    assert wrong not in str(row.get('label_display_form') or '')
    if pid == '326244':
        assert row['label_display_form'] == 'Calcium Ascorbate'
    else:
        [ingredient] = [r for r in enriched['ingredient_quality_data']['ingredients'] if r.get('raw_source_path') == source_ref]
        assert 'cracked-wall' in ingredient['source_label_name'].casefold()
        assert ingredient['form_match_status'] != 'FORM_UNMAPPED'
        assert 'does not identify' not in str(ingredient.get('consumer_note') or '')


def test_signed_source_vitamin_e_uses_printed_natural_form_and_resolves_conversion():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact

    raw = json.loads((Path(__file__).parent / 'fixtures' / 'completion_source_8958_raw.json').read_text())
    clean = EnhancedDSLDNormalizer().normalize_product(raw)
    [vitamin] = [row for row in clean['activeIngredients'] if row.get('raw_source_path') == 'ingredientRows[0]']
    assert any(form.get('name') == 'd-alpha-tocopherol' for form in vitamin.get('forms') or [])
    assert vitamin['quantity'] == 800 and vitamin['unit'] == 'IU'
    enriched, _ = SupplementEnricherV3().enrich_product(clean)
    scored = build_scored_artifact(enriched)
    assert scored['assessment_readiness']['dose']['readiness'] == 'complete'
    [owner] = [row for row in enriched['ingredient_quality_data']['ingredients'] if row.get('canonical_id') == 'vitamin_e']
    assert owner['matched_form'] == 'd-alpha-tocopherol'
    [assessment] = enriched['rda_ul_data']['adequacy_results']
    assert assessment['per_day_min'] == pytest.approx(536)
    assert assessment['per_day_max'] == pytest.approx(1072)
    assert assessment['over_ul'] is True
    assert assessment['ul'] == 1000
    assert scored['dose_safety_evaluation']['dose_ceiling']['minimum_exceeds'] is False
    assert scored['dose_safety_evaluation']['dose_ceiling']['pct_ul'] == pytest.approx(107.2)
    assert scored['product_safety_status'] == 'caution'
    from build_final_db import build_detail_blob
    blob = build_detail_blob(enriched, scored)
    assert blob['product_safety_status'] == 'caution'
    [printed] = [row for row in blob['display_ingredients'] if row.get('raw_source_path') == 'ingredientRows[0]']
    assert printed['exact_dose_text'] == '800 IU'
    assert printed['label_display_form'] == 'd-alpha-tocopherol'


def test_signed_source_arginine_variant_uses_own_pdf_and_preserves_other_column():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    raw = json.loads((Path(__file__).parent / 'fixtures' / 'completion_source_27808_raw.json').read_text())
    rows = raw['ingredientRows']
    normalizer = EnhancedDSLDNormalizer()
    normalizer._stamp_raw_source_paths(rows, 'ingredientRows')
    normalizer._apply_label_corrections(rows, '27808')
    arginine = rows[10]['nestedRows'][0]
    assert {q['servingSizeQuantity']: q['quantity'] for q in arginine['quantity']} == {5.55: 500, 11.1: 1000}
    assert {q['unit'] for q in arginine['quantity']} == {'mg'}
    assert arginine['_pre_correction_quantity_value'] == 100
    assert [form['name'] for form in arginine['forms']] == ['L-Arginine', 'L-Arginine, OT2']


@pytest.mark.parametrize('changed', ['quantity', 'form'])
def test_signed_source_vitamin_e_correction_does_not_override_a_changed_edition(changed):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    raw = json.loads((Path(__file__).parent / 'fixtures' / 'completion_source_8958_raw.json').read_text())
    row = raw['ingredientRows'][0]
    if changed == 'quantity':
        row['quantity'][0]['quantity'] = 400
    else:
        row['forms'] = [{'name': 'dl-alpha-tocopherol'}]
    normalizer = EnhancedDSLDNormalizer()
    normalizer._stamp_raw_source_paths(raw['ingredientRows'], 'ingredientRows')
    expected_forms = json.loads(json.dumps(row['forms']))
    normalizer._apply_label_corrections(raw['ingredientRows'], '8958')
    assert row['forms'] == expected_forms
    assert not row.get('_label_correction_applied')


@pytest.mark.parametrize('pid', ['8958', '27808'])
def test_signed_source_correction_never_applies_to_another_label_id(pid):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    raw = json.loads((Path(__file__).parent / 'fixtures' / f'completion_source_{pid}_raw.json').read_text())
    normalizer = EnhancedDSLDNormalizer()
    normalizer._stamp_raw_source_paths(raw['ingredientRows'], 'ingredientRows')
    normalizer._apply_label_corrections(raw['ingredientRows'], '999999999')
    if pid == '8958':
        assert raw['ingredientRows'][0]['forms'] == []
    else:
        assert {q['servingSizeQuantity']: q['quantity'] for q in raw['ingredientRows'][10]['nestedRows'][0]['quantity']} == {5.55: 100, 11.1: 1000}


def test_signed_source_lemon_tea_caffeine_matches_own_printed_columns():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'completion_source_27808_raw.json').read_text())
    normalizer = EnhancedDSLDNormalizer()
    normalizer._stamp_raw_source_paths(raw['ingredientRows'], 'ingredientRows')
    normalizer._apply_label_corrections(raw['ingredientRows'], '27808')
    rows = raw['ingredientRows'][9]['nestedRows'][1]['nestedRows']
    assert [(r['name'], r['quantity'][0]['quantity']) for r in rows] == [('50 mg Caffeine', 50), ('100 mg Caffeine', 100)]


def test_signed_source_fruit_blast_conflict_preserves_printed_numbers_without_exact_total():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.dose_safety import _declared_daily_caffeine
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'completion_source_28993_raw.json').read_text())
    clean = EnhancedDSLDNormalizer().normalize_product(raw)
    enriched, _ = SupplementEnricherV3().enrich_product(clean)
    caffeine = _declared_daily_caffeine(enriched)
    assert caffeine['total_mg_day_min'] is None
    assert caffeine['total_mg_day_max'] is None
    assert caffeine['unknown_rows'] == 4
    assert build_scored_artifact(enriched)['assessment_readiness']['dose']['readiness'] != 'complete'
    [guarana] = [r for r in enriched['ingredient_quality_data']['ingredients']
                  if r.get('raw_source_path') == 'ingredientRows[9].nestedRows[1].nestedRows[0]']
    assert guarana['quantity'] == 300
    assert {v['quantity'] for v in guarana['raw_taxonomy']['quantityVariants']} == {150, 300}


def test_source_quantity_qualifier_is_exact_snapshot_bound_and_does_not_mutate_registry():
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    normalizer = EnhancedDSLDNormalizer()
    raw_quantity = [{'quantity': 150, 'unit': 'mg', 'operator': '=', 'servingSizeQuantity': 5.1}]
    entry = {'raw_ingredient_text': 'Caffeine', 'raw_source_path': 'ingredientRows[0]',
             'raw_quantities': deepcopy(raw_quantity), 'corrected_quantity_operator': 'ambiguous'}
    normalizer._label_corrections_by_dsld_id['test'] = entry
    def apply(quantities):
        rows = [{'name': 'Caffeine', 'raw_source_path': 'ingredientRows[0]', 'quantity': quantities}]
        return normalizer._apply_label_corrections(rows, 'test')[0]
    result = apply(deepcopy(raw_quantity))
    assert result['quantity'][0]['operator'] == 'ambiguous'
    assert result['quantity'][0]['quantity'] == 150
    assert entry['raw_quantities'] == raw_quantity
    changed = deepcopy(raw_quantity); changed[0]['quantity'] = 160
    assert apply(changed)['quantity'][0]['operator'] == '='
    changed = deepcopy(raw_quantity); changed[0]['servingSizeQuantity'] = 10.2
    assert apply(changed)['quantity'][0]['operator'] == '='


def test_lemon_tea_caffeine_daily_range_does_not_add_alternative_columns():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.dose_safety import _declared_daily_caffeine
    raw = json.loads((Path(__file__).parent / 'fixtures' / 'completion_source_27808_raw.json').read_text())
    clean = EnhancedDSLDNormalizer().normalize_product(raw)
    enriched, _ = SupplementEnricherV3().enrich_product(clean)
    caffeine = _declared_daily_caffeine(enriched)
    assert caffeine['rows'] == 4
    assert caffeine['unknown_rows'] == 0
    assert caffeine['total_mg_day_min'] == 200
    assert caffeine['total_mg_day_max'] == 400


@pytest.fixture(scope="module")
def preparation_source_records():
    return json.loads((Path(__file__).parent / "fixtures" / "completion_source_preparation_columns_raw.json").read_text())


@pytest.mark.parametrize("pid,expected_a,expected_calcium", [
    ("66984", 5000, 800), ("69584", 5000, 800),
    ("69613", 5000, 730), ("243776", 5000, 800),
    ("243812", 3000, 730), ("243815", 3000, 800),
    ("308692", 1500, 800), ("315322", 1500, 800),
])
def test_reviewed_powder_columns_keep_product_amounts_and_alternatives(preparation_source_records, pid, expected_a, expected_calcium):
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = deepcopy(preparation_source_records[pid])
    clean = EnhancedDSLDNormalizer().normalize_product(raw)
    for name, expected in [("Vitamin A", expected_a), ("Calcium", expected_calcium)]:
        [row] = [r for r in clean["activeIngredients"] if r["name"] == name]
        assert row["quantity"] == expected
        variants = row["raw_taxonomy"]["quantityVariants"]
        assert {v["serving_size_order"] for v in variants} == {1, 2}
        assert len(variants) == 2
    assert "water" in clean["servingSizes"][0]["notes"].lower()
    assert "milk" in clean["servingSizes"][1]["notes"].lower()


@pytest.mark.parametrize("pid,expected", [("275412", (3, 9, False)), ("243815", (1, 2, False))])
def test_reviewed_directed_daily_ranges_are_not_truncated(preparation_source_records, pid, expected):
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from serving_frequency import resolve_daily_serving_range
    clean = EnhancedDSLDNormalizer().normalize_product(deepcopy(preparation_source_records[pid]))
    assert resolve_daily_serving_range(clean) == expected


def test_reviewed_two_capsule_panel_fixes_shared_basis_not_amounts(preparation_source_records):
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    raw = deepcopy(preparation_source_records["328753"])
    clean = EnhancedDSLDNormalizer().normalize_product(raw)
    assert clean["servingSizes"][0]["minQuantity"] == 2
    enriched, _ = SupplementEnricherV3().enrich_product(clean)
    for nutrient, expected in [("vitamin_a", 1500), ("vitamin_d", 50), ("vitamin_e", 67), ("magnesium", 100), ("zinc", 25)]:
        [row] = [a for a in enriched["rda_ul_data"]["adequacy_results"] if a.get("canonical_id") == nutrient and a.get("ul_status") != "skipped_compound_duplicate_row"]
        assert row["per_day_min"] == pytest.approx(expected)
        assert row["per_day_max"] == pytest.approx(expected)
    [vitamin_a] = [a for a in enriched["rda_ul_data"]["adequacy_results"] if a.get("canonical_id") == "vitamin_a"]
    assert vitamin_a["ul_status"] == "assessed_within_limit_worst_case_preformed_vitamin_a"
    assert vitamin_a.get("preformed_vitamin_a_fraction") is None


@pytest.mark.parametrize("changed", ["quantity", "directions", "serving", "forms"])
def test_reviewed_preparation_binding_fails_closed_on_changed_source(preparation_source_records, changed):
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = deepcopy(preparation_source_records["328753"])
    if changed == "quantity":
        raw["ingredientRows"][0]["quantity"][0]["quantity"] = 1499
    elif changed == "directions":
        raw["statements"].append({"type": "Suggested/Recommended/Usage/Directions", "notes": "Take one capsule daily."})
    elif changed == "serving":
        raw["servingSizes"][0]["minQuantity"] = 2
    else:
        raw["ingredientRows"][0]["forms"] = []
    with pytest.raises(ValueError, match="Reviewed serving source changed"):
        EnhancedDSLDNormalizer().normalize_product(raw)


def test_reviewed_preparation_does_not_mutate_input_or_cross_product_ids(preparation_source_records):
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = deepcopy(preparation_source_records["328753"])
    original = deepcopy(raw)
    normalizer = EnhancedDSLDNormalizer()
    first = normalizer.normalize_product(raw)
    second = normalizer.normalize_product(raw)
    assert raw == original
    assert first["servingSizes"] == second["servingSizes"]
    raw["id"] = 999999999
    clean = normalizer.normalize_product(raw)
    assert clean["servingSizes"][0]["minQuantity"] == 1


def test_reviewed_source_names_do_not_invent_legacy_rae_or_preformed_share(preparation_source_records):
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    for pid in ["66984", "69584", "69613", "243776", "67030"]:
        clean = normalizer.normalize_product(deepcopy(preparation_source_records[pid]))
        [vitamin] = [r for r in clean["activeIngredients"] if r["name"] == "Vitamin A"]
        assert any("carotene" in f.get("name", "").lower() for f in vitamin["forms"])
        assert vitamin["unit"] == "IU"
        enriched, _ = enricher.enrich_product(clean)
        [assessment] = [r for r in enriched["rda_ul_data"]["adequacy_results"] if r.get("canonical_id") == "vitamin_a"]
        assert assessment["scoring_eligible"] is False
        assert assessment["conversion_applied"] is False
        assert assessment["ul_status"].startswith(("indeterminate_", "assessed_within_limit_worst_case_"))
        assert assessment.get("preformed_vitamin_a_fraction") is None
        assert not assessment["over_ul"]


def test_reviewed_modern_powder_activity_survives_unknown_preformed_allocation(preparation_source_records):
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    for pid, low, high in [("243812", 3000, 6000), ("243815", 3000, 6000), ("308692", 1500, 3000), ("315322", 1500, 3000)]:
        clean = normalizer.normalize_product(deepcopy(preparation_source_records[pid]))
        enriched, _ = enricher.enrich_product(clean)
        [a] = [r for r in enriched["rda_ul_data"]["adequacy_results"] if r.get("canonical_id") == "vitamin_a"]
        assert a["scoring_eligible"] is True
        assert a["per_day_min"] == low and a["per_day_max"] == high
        assert "fraction_unknown" in a["ul_status"]


def test_poolzyme_description_does_not_claim_unbranded_or_clear_review():
    data = json.loads((Path(__file__).parent.parent / "data" / "backed_clinical_studies.json").read_text())
    from data_batch import entries
    [record] = [r for r in entries(data).values() if isinstance(r, dict) and r.get("id") == "INGR_DIGESTIVE_ENZYMES"]
    assert "Poolzyme Multi" in record["notes"]
    assert "unbranded" not in record["notes"] + record["notable_studies"]
    assert not record.get("source_contexts")


def test_canonical_quantity_column_does_not_fall_through_to_prepared_milk():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    normalizer = EnhancedDSLDNormalizer()
    normalizer._canonical_serving_row = {"order": 1, "minQuantity": 360, "unit": "Gram(s)"}
    q = [{"quantity": 900, "unit": "mcg", "servingSizeQuantity": 360, "servingSizeOrder": 2},
         {"quantity": 0, "unit": "NP", "servingSizeQuantity": 360, "servingSizeOrder": 1}]
    value, unit, _, _ = normalizer._process_quantity(q)
    assert value == 0 and unit == "NP"


@pytest.mark.parametrize("pid,name,expected,unit", [
    ("69584", "Iodine", 150, "mcg"), ("69613", "Iodine", 150, "mcg"),
    ("69584", "Sodium", 400, "mg"), ("69613", "Sodium", 330, "mg"),
    ("243776", "Magnesium", 140, "mg"), ("243776", "Zinc", 15, "mg"),
    ("315322", "Thiamine", 4.8, "mg"),
    ("308692", "Energizing ATP Complex", 1.505, "Gram(s)"),
    ("315322", "Energizing ATP Complex", 1.505, "Gram(s)"),
])
def test_reviewed_column_transcriptions_match_printed_source(preparation_source_records, pid, name, expected, unit):
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    clean = EnhancedDSLDNormalizer().normalize_product(deepcopy(preparation_source_records[pid]))
    if name == "Sodium":
        row = clean["nutritionalInfo"]["sodium"]
        assert row["amount"] == pytest.approx(expected)
    else:
        [row] = [r for r in clean["activeIngredients"] if r["name"] == name]
        assert row["quantity"] == pytest.approx(expected)
    assert row["unit"] == unit


@pytest.mark.parametrize("pid,dose", [("243812", "3000 mcg"), ("328753", "1,500 mcg RAE")])
def test_reviewed_serving_correction_reaches_exported_label_display(preparation_source_records, pid, dose):
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    from build_final_db import build_detail_blob
    clean = EnhancedDSLDNormalizer().normalize_product(deepcopy(preparation_source_records[pid]))
    enriched, _ = SupplementEnricherV3().enrich_product(clean)
    scored = build_scored_artifact(enriched)
    blob = build_detail_blob(enriched, scored)
    ref = "ingredientRows[5]" if pid == "243812" else "ingredientRows[0]"
    [row] = [r for r in blob["display_ingredients"] if r.get("raw_source_path") == ref]
    assert row["exact_dose_text"] == dose
    if pid == "243812":
        variants = row["serving_variants"]
        assert {v["exact_dose_text"] for v in variants} == {"3,000 mcg", "3,417 mcg"}
        assert [v["exact_dose_text"] for v in variants if v["is_canonical"]] == ["3,000 mcg"]
        assert "water" in variants[0]["serving_note"].lower()
        assert "milk" in variants[1]["serving_note"].lower()
    else:
        assert blob["product_safety_status"] == "caution"


def test_named_poolzyme_source_still_requires_source_context_review():
    from clinical_applicability import assess_clinical_source_review
    from data_batch import entries
    data = json.loads((Path(__file__).parent.parent / "data" / "backed_clinical_studies.json").read_text())
    record = next(r for r in entries(data).values() if isinstance(r, dict) and r.get("id") == "INGR_DIGESTIVE_ENZYMES")
    review = assess_clinical_source_review(record)
    assert not review["is_complete"]
    # Dr. Pham, 2026-10-28: the named brand is unverified for the trial
    # material, so the draft context stays in the audit receipt and the record
    # hold is the only state; no production context can complete the review.
    assert record.get("study_contexts") == []
    assert record["scoring_eligible"] is False
    assert "clinical_source_contexts_missing" in review["errors"]


@pytest.fixture(scope="module")
def bamboo_label_normalizer():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    return EnhancedDSLDNormalizer()


@pytest.mark.parametrize(
    "product_id,source_name,raw_notes,ratio",
    [
        ("252349", "Bamboo extract", "", ""),
        ("253304", "Bamboo extract", "", ""),
        ("253309", "Bamboo extract", "", ""),
        ("253312", "Bamboo extract", "", ""),
        ("310922", "Bamboo extract", "", ""),
        ("310927", "Bamboo extract", "", ""),
        ("310921", "Bamboo Leaf, Stem Extract", "", ""),
        ("310924", "Bamboo Leaf, Stem Extract", "", ""),
        ("330290", "Bamboo Leaf, Stem Extract", "30:1", "30:1"),
        ("330291", "Bamboo Leaf, Stem Extract", "30:1", "30:1"),
        ("330292", "Bamboo Leaf, Stem Extract", "30:1", "30:1"),
        ("330293", "Bamboo Leaf, Stem Extract", "30:1", "30:1"),
    ],
)
def test_bamboo_exact_label_restores_only_printed_species_and_parts(
    bamboo_label_normalizer, product_id, source_name, raw_notes, ratio
):
    """Official label omits neither species nor tissue; API working notes do."""
    from copy import deepcopy

    raw = [{"name": source_name, "notes": raw_notes, "forms": [],
            "quantity": [{"quantity": 500, "unit": "mg"}]}]
    before = deepcopy(raw)
    bamboo_label_normalizer._stamp_raw_source_paths(raw, "ingredientRows")
    result = bamboo_label_normalizer._apply_label_corrections(raw, product_id)
    row = result[0]
    assert "Bambusa vulgaris" in row["notes"]
    assert "PlantPart: stem and leaves" in row["notes"]
    assert ("30:1" in row["notes"]) is bool(ratio)
    assert row["_pre_correction_notes"] == raw_notes
    assert row["name"] == source_name
    assert row["forms"] == before[0]["forms"]
    assert row["quantity"] == before[0]["quantity"]
    assert row["raw_source_path"] == "ingredientRows[0]"
    assert "silica" not in row["notes"].lower()
    assert "%" not in row["notes"]
    corrected = deepcopy(result)
    assert bamboo_label_normalizer._apply_label_corrections(result, product_id) == corrected


@pytest.mark.parametrize("changed_field", ["name", "notes", "quantity", "raw_source_path"])
def test_bamboo_exact_label_correction_rejects_changed_source_binding(
    bamboo_label_normalizer, changed_field
):
    from copy import deepcopy

    row = {"name": "Bamboo extract", "notes": "", "raw_source_path": "ingredientRows[0]",
           "quantity": [{"quantity": 500, "unit": "mg"}]}
    replacement = {"name": "Bamboo root extract", "notes": "new source edition",
                   "quantity": [{"quantity": 600, "unit": "mg"}],
                   "raw_source_path": "ingredientRows[1]"}
    row[changed_field] = replacement[changed_field]
    before = deepcopy(row)
    with pytest.raises(ValueError, match="Reviewed note attribution changed"):
        bamboo_label_normalizer._apply_label_corrections([row], "252349")
    assert row == before


@pytest.mark.parametrize("product_id", ["unreviewed-label", "294422", "331010"])
def test_bamboo_exact_label_facts_are_not_copied_to_unverified_siblings(
    bamboo_label_normalizer, product_id
):
    from copy import deepcopy

    raw = [{"name": "Bamboo extract", "notes": "", "quantity": [{"quantity": 500, "unit": "mg"}]}]
    before = deepcopy(raw)
    if product_id in {"294422", "331010"}:
        # These exact IDs now have independently verified Horsetail source
        # corrections. A substituted Bamboo row must fail their original-row
        # attribution guard, rather than acquire either product's facts.
        with pytest.raises(ValueError, match="Reviewed note attribution changed"):
            bamboo_label_normalizer._apply_label_corrections(raw, product_id)
        assert raw == before
    else:
        assert bamboo_label_normalizer._apply_label_corrections(raw, product_id) == before


@pytest.mark.parametrize("pid,name,ratio,unit", [
    ("252441", "Cascara Sagrada extract", "", "mg"),
    ("253399", "Cascara Sagrada extract", "", "mg"),
    ("253403", "Cascara Sagrada extract", "", "mg"),
    ("253404", "Cascara Sagrada extract", "", "mg"),
    ("311301", "Cascara Sagrada extract", "", "mg"),
    ("311302", "Cascara Sagrada extract", "", "mg"),
    ("311303", "Cascara Sagrada extract", "", "mg"),
    ("311304", "Cascara Sagrada extract", "", "mg"),
    ("330523", "Cascara Sagrada Bark Extract", "10:1", "mg"),
    ("330524", "Cascara Sagrada extract", "10:1", "mg"),
    ("330525", "Cascara Sagrada Bark Extract", "10:1", "mg"),
])
def test_exact_cascara_label_keeps_printed_davurica_without_species_equivalence(
    bamboo_label_normalizer, pid, name, ratio, unit,
):
    from copy import deepcopy
    rows = [{"name": name, "notes": ratio, "raw_source_path": "ingredientRows[0]",
             "quantity": [{"quantity": 500, "unit": unit}], "forms": []}]
    before = deepcopy(rows)
    result = bamboo_label_normalizer._apply_label_corrections(rows, pid)
    assert "Rhamnus davurica" in result[0]["notes"]
    assert "PlantPart: bark" in result[0]["notes"]
    assert ("10:1" in result[0]["notes"]) is bool(ratio)
    assert "purshiana" not in result[0]["notes"].lower()
    assert result[0]["quantity"] == before[0]["quantity"]
    assert result[0]["forms"] == []
    assert result[0]["name"] == name


@pytest.mark.parametrize('pid', ['252787','254734','254735','254738','270831','29242','74661'])
def test_exact_yohimbe_source_facts_preserve_whole_mass(bamboo_label_normalizer, pid):
    from copy import deepcopy
    fixture = json.loads((Path(__file__).parent / 'fixtures/yohimbe7_original_api_rows.json').read_text())[pid]
    row = deepcopy(fixture['row'])
    row['raw_source_path'] = fixture['path']
    before = deepcopy(row)
    corrected = bamboo_label_normalizer._apply_label_corrections([row], pid)[0]
    species = 'johimbe' if pid in {'29242','270831'} else 'yohimbe'
    assert f'Pausinystalia {species}' in corrected['notes']
    assert 'PlantPart: bark' in corrected['notes']
    assert 'DER and extraction solvent not declared on label' in corrected['notes']
    assert corrected['quantity'] == before['quantity']
    assert corrected['name'] == before['name']
    assert corrected['raw_source_path'] == before['raw_source_path']
    if pid in {'74661','270831'}:
        assert '2% Yohimbine Alkaloids = 9 mg' in corrected['notes']
    elif pid == '29242':
        assert 'standardized to contain 2% Yohimbine' in corrected['notes']
    else:
        assert 'standardized to contain >=2% Yohimbine' in corrected['notes']
    if pid == '74661':
        assert corrected['forms'][0]['name'] == 'Yohimbine Alkaloids'
    else:
        assert corrected['forms'] == before['forms']


@pytest.mark.parametrize('pid,part', [(p,'bark') for p in ['252787','254734','254735','254738','270831','29242','74661']]+[(p,'stem and leaves') for p in ['252349','253304','253309','253312','310921','310922','310924','310927']])
def test_verified_source_notes_keep_plant_part_separate_from_assay_and_der(bamboo_label_normalizer, overrides, pid, part):
    details = bamboo_label_normalizer._parse_botanical_details(overrides['corrections'][pid]['corrected_notes'])
    assert details['plantPart'] == part


def test_existing_source_notes_keep_their_physical_part(bamboo_label_normalizer):
    assert bamboo_label_normalizer._parse_botanical_details('Peppermint leaf essential oil PlantPart: leaf Genus: Mentha Species: piperita')['plantPart'] == 'leaf'


_SOURCE_NOTE_ROWS = json.loads((Path(__file__).parent / 'fixtures/remaining_source_note_rows.json').read_text())

@pytest.mark.parametrize('pid', sorted(_SOURCE_NOTE_ROWS))
def test_individually_verified_remaining_source_facts_keep_original_amount_and_role(bamboo_label_normalizer, pid):
    from copy import deepcopy
    fixture = _SOURCE_NOTE_ROWS[pid]
    row = deepcopy(fixture['row'])
    row['raw_source_path'] = fixture['path']
    before = deepcopy(row)
    result = bamboo_label_normalizer._apply_label_corrections([row], pid)[0]
    assert result['notes'] == fixture['expected_notes']
    for field in ['quantity','name','nestedRows','raw_source_path']:
        assert result.get(field) == before.get(field)
    if pid in {'252562','255054','255055','255057'}:
        assert before['forms'] == []
        assert result['category'] == 'botanical'
        assert result['forms'] == [{'name': 'Laminaria japonica Whole Grass Extract',
                                   'category': 'botanical', 'ingredientGroup': 'Laminaria japonica'}]
    else:
        assert result.get('forms') == before.get('forms')
    if pid == '326238':
        assert result['quantity'][0]['quantity'] == 0
        assert result['quantity'][0]['unit'] == 'NP'
        assert 'individual amount not declared' in result['notes']
    part = bamboo_label_normalizer._parse_botanical_details(result['notes']).get('plantPart')
    assert part in {'root','leaf','leaves','whole herb','whole grass','bark','fruit','mycelia'}


@pytest.mark.parametrize('pid', ['329925','329926','329927','329928','330068','330069'])
def test_exact_colored_maca_source_fact_does_not_infer_processing_or_mass(bamboo_label_normalizer, pid):
    from copy import deepcopy
    fixture = json.loads((Path(__file__).parent / 'fixtures/maca6_original_api_rows.json').read_text())[pid]
    row = deepcopy(fixture['row'])
    row['raw_source_path'] = fixture['raw_source_path']
    before = deepcopy(row)
    result = bamboo_label_normalizer._apply_label_corrections([row], pid)[0]
    assert result['notes'] == fixture['expected_note']
    assert bamboo_label_normalizer._parse_botanical_details(result['notes']) == {
        'plantPart': 'root', 'genus': 'Lepidium', 'species': 'meyenii', 'form': 'powder'}
    for key in ['name','forms','quantity','raw_source_path','nestedRows']:
        assert result.get(key) == before.get(key)
    assert not any(term in result['notes'].lower() for term in ['gelatinized','raw powder','extract','standardized'])
    wrong = deepcopy(before)
    wrong['quantity'][0]['quantity'] += 1
    with pytest.raises(ValueError, match='Reviewed note attribution changed'):
        bamboo_label_normalizer._apply_label_corrections([wrong], pid)
    assert wrong['notes'] == before['notes']


@pytest.mark.parametrize('pid', ['231929','232062'])
def test_exact_applewise_linkage_is_product_level_and_original_row_bound(bamboo_label_normalizer, pid):
    from copy import deepcopy
    fixture = json.loads((Path(__file__).parent / 'fixtures/applewise2_original_api_rows.json').read_text())[pid]
    row = deepcopy(fixture['row'])
    row['raw_source_path'] = 'ingredientRows[0]'
    before = deepcopy(row)
    result = bamboo_label_normalizer._apply_label_corrections([row], pid)[0]
    assert result['notes'] == fixture['expected_notes']
    assert 'product-level manufacturer linkage' in result['notes']
    assert 'not an ingredient trademark printed in the NIH ingredient row' in result['notes']
    for key in ['name','forms','quantity','raw_source_path']:
        assert result.get(key) == before.get(key)
    wrong = deepcopy(before)
    wrong['forms'][1]['percent'] = 6
    wrong_before = deepcopy(wrong)
    assert bamboo_label_normalizer._apply_label_corrections([wrong], pid) == [wrong_before]
    assert 'manufacturer-linked AppleWise' not in wrong['notes']
    other_label = deepcopy(before)
    assert bamboo_label_normalizer._apply_label_corrections([other_label], 'unreviewed-apple-marker-match') == [before]


@pytest.mark.parametrize('pid', ['231929','232062'])
def test_real_applewise_linkage_changes_no_non_dose_assessment(pid):
    from copy import deepcopy
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    raw = json.loads((Path(__file__).parent / f'fixtures/raw_applewise_{pid}.json').read_text())
    before_owner, after_owner = EnhancedDSLDNormalizer(), EnhancedDSLDNormalizer()
    before_owner._label_corrections_by_dsld_id.pop(pid)
    before = before_owner.normalize_product(deepcopy(raw))
    after = after_owner.normalize_product(deepcopy(raw))
    fields = ['canonical_id','canonical_source_db','quantity','unit','forms','raw_source_text','raw_source_path','cleaner_row_role']
    assert {k: before['activeIngredients'][0].get(k) for k in fields} == {
        k: after['activeIngredients'][0].get(k) for k in fields}
    enricher = SupplementEnricherV3()
    left, errors = enricher.enrich_product(before)
    assert not errors
    right, errors = enricher.enrich_product(after)
    assert not errors
    a, b = build_scored_artifact(left), build_scored_artifact(right)
    for pillar in ['formulation','evidence','transparency','verification','safety_hygiene']:
        assert a['quality_pillars_v4'][pillar]['score'] == b['quality_pillars_v4'][pillar]['score'], pillar
        assert a['quality_pillars_v4'][pillar].get('components') == b['quality_pillars_v4'][pillar].get('components'), pillar
    assert a['product_safety_status'] == b['product_safety_status']
    assert a['_v4_safety_gate'] == b['_v4_safety_gate']
    identity_fields = ['canonical_id','canonical_source_db','canonical_id_before','canonical_id_after','identity_disposition','scoreable_identity']
    assert [{k:r.get(k) for k in identity_fields} for r in left['ingredient_quality_data']['ingredients']] == [
        {k:r.get(k) for k in identity_fields} for r in right['ingredient_quality_data']['ingredients']]
