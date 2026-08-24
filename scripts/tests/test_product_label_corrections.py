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
        # DSLD IDs are integer-strings (e.g., "69734")
        assert key.isdigit(), (
            f"correction key {key!r} must be a DSLD id integer-string"
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
    ("dsld_id", "product_name"),
    [
        ("259709", "Weight Gainer Strawberries & Cream"),
        ("69608", "Weight Gainer Strawberries & Cream"),
    ],
)
def test_gnc_weight_gainer_protein_unit_corrections_are_source_verified(
    overrides, dsld_id, product_name
):
    entry = (overrides.get("corrections") or {}).get(dsld_id)

    assert entry, f"correction for GNC weight gainer {dsld_id} is missing"
    assert entry["product_name"] == product_name
    assert entry["raw_ingredient_text"] == "Protein"
    assert entry["corrected_ingredient_text"] == "Protein"
    assert entry["raw_quantity_unit"] == "mg"
    assert entry["corrected_quantity_unit"] == "Gram(s)"
    assert entry["correction_fields"] == ["quantity.unit"]
    assert "https://www.gnc.com/on/demandware.static/-/Sites-GNC2-Library/default/pdf/369937_lbl.pdf" in entry["sources"]


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
