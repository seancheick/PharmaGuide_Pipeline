"""RC-5 Phase-3 source-resolution corrections (2026-09-20).

Pins the ten reviewer-signed corrections authored by the Phase-3
source-resolution phase, and the three dispositions that phase closed. Each
correction is source-backed: the printed Supplement Facts panel or an
independent in-DSLD sibling transcription establishes the value, never
physiological plausibility.

What this file guards:

1. The three E2 Vitamin A unit defects really are repaired, and the quantity
   is untouched (unit-only corrections).
2. The three E2 rows whose printed denomination could NOT be established to
   audit grade carry NO correction at all. A plausibility-based mg/mcg rewrite
   is exactly what the reviewed-source contract forbids.
3. Every Bulk 1340 Vitamin A form correction supplies the printed provitamin-A
   source and never defaults the row to retinol.
4. The Solgar Male Multiple declared-total row is renamed to its printed
   identity without creating a global alias.
5. The Doctor's Best Serrapeptase activity is restored from the printed panel,
   with the 0 NP source value preserved for audit.
6. Every entry still carries the reviewer provenance the schema requires.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_CORRECTIONS_PATH = os.path.join(
    _ROOT, "scripts", "data", "curated_overrides", "product_label_corrections.json"
)

# E2 unit defects and the unit each printed label establishes.
E2_UNIT_CORRECTIONS = {
    "223563": ("mg RAE", "mcg RAE"),
    "223572": ("mg RAE", "mcg RAE"),
    "328644": ("mg RAE", "mcg RAE"),
}

# E2 rows whose printed denomination is DFE-shaped but cannot be separated from
# RAE at audit grade. These must stay uncorrected.
E2_WITHHELD_NO_CORRECTION = ("231334", "231335", "263865")

# Bulk 1340 products whose printed vitamin/mineral blend names the vitamin A
# source as Natural beta-Carotene.
BULK_1340_VITAMIN_A_FORM = ("228823", "243799", "243808", "243812", "243815")

# Source-resolved and CLOSED, but deliberately NOT authorable through the
# sanctioned per-row-text mechanism: in 201420 the declared-total row (1333 mcg
# DFE) and its own nested form row (800 mcg) both carry the identical raw text
# 'Folic Acid', so a rename keyed on that text applies to both and would
# manufacture a second row under a parent name — making the double count it was
# meant to remove worse. The printed structure is confirmed (sibling 201405
# transcribes the same panel as 'Folate 1333 mcg DFE'), so this is a mechanism
# limit, not an open source question. It is resolved structurally instead, by
# the folate dose-safety contract — see
# scripts/tests/test_folate_dose_basis_reconciliation.py and the receipt's
# `implementation` field.
ENGINE_RECONCILED_NO_ROW_REWRITE = ("201420",)


@pytest.fixture(scope="module")
def corrections():
    with open(_CORRECTIONS_PATH) as handle:
        return json.load(handle)["corrections"]


def test_expected_corrections_are_present(corrections):
    expected = (
        set(E2_UNIT_CORRECTIONS)
        | set(BULK_1340_VITAMIN_A_FORM)
        | {"269360"}
    )
    missing = sorted(expected - set(corrections))
    assert not missing, f"Phase-3 corrections missing from the ledger: {missing}"
    assert len(expected) == 9


@pytest.mark.parametrize("dsld_id", ENGINE_RECONCILED_NO_ROW_REWRITE)
def test_rows_the_mechanism_cannot_scope_are_not_rewritten(corrections, dsld_id):
    """A correction must never be authored when the review cannot scope it to
    the exact row it was reviewed against — and closing the product by engine
    fix must not quietly reintroduce the row rewrite."""
    assert dsld_id not in corrections, (
        f"{dsld_id}: the declared-total row and its nested form row share the "
        f"same raw_ingredient_text, so a rename cannot be scoped to the total "
        f"alone. Authoring it would rename the form row too."
    )


@pytest.mark.parametrize("dsld_id", ENGINE_RECONCILED_NO_ROW_REWRITE)
def test_engine_fix_actually_reconciles_the_flagged_shape(dsld_id):
    """The product is only closed if the contract recognises its real flagged
    shape: two rows named 'Folic Acid', the declared one Daily-Value anchored."""
    sys.path.insert(0, os.path.join(_ROOT, "scripts"))
    from scoring_v4.dose_safety import is_folate_parent_total_duplicate_flag

    assert is_folate_parent_total_duplicate_flag({
        "nutrient": "Vitamin B9 (Folate)",
        "canonical_id": "vitamin_b9_folate",
        "aggregation": "canonical_sum",
        "pct_ul": 161.55,
        "ul_gate_eligible": True,
        "contributing_rows": [
            {
                "ingredient": "Folic Acid",
                "amount": 1333.0,
                "unit": "mcg DFE",
                "ul_exposure_basis": "daily_value_confirmed_nutrient_amount",
                "ul_gate_eligible": True,
            },
            {
                "ingredient": "Folic Acid",
                "amount": 1360.0,
                "unit": "mcg DFE",
                "ul_exposure_basis": "canonical_parent_substance_amount",
                "ul_gate_eligible": True,
            },
        ],
    }) is True, (
        f"{dsld_id}: the mis-named declared total is no longer recognised, so "
        f"the product's folate exposure is being charged twice again"
    )


@pytest.mark.parametrize("dsld_id", sorted(E2_UNIT_CORRECTIONS))
def test_e2_unit_correction_changes_only_the_unit(corrections, dsld_id):
    raw_unit, corrected_unit = E2_UNIT_CORRECTIONS[dsld_id]
    entry = corrections[dsld_id]
    assert entry["raw_quantity_unit"] == raw_unit
    assert entry["corrected_quantity_unit"] == corrected_unit
    assert entry["correction_fields"] == ["quantity.unit"]
    assert "corrected_quantity_value" not in entry, (
        f"{dsld_id}: the printed source establishes the unit, not a different "
        f"quantity — the amount must not be rewritten"
    )
    assert "https://api.ods.od.nih.gov/dsld/v9/label/" + dsld_id in entry["sources"]


@pytest.mark.parametrize("dsld_id", E2_WITHHELD_NO_CORRECTION)
def test_e2_insufficient_rows_never_get_a_plausibility_rewrite(corrections, dsld_id):
    assert dsld_id not in corrections, (
        f"{dsld_id}: the archived scan cannot separate DFE from RAE at audit "
        f"grade, so the correct final state is source_insufficient_keep_withheld. "
        f"No correction may be authored from plausibility."
    )


@pytest.mark.parametrize("dsld_id", BULK_1340_VITAMIN_A_FORM)
def test_bulk_1340_vitamin_a_form_is_provitamin_a_not_retinol(corrections, dsld_id):
    entry = corrections[dsld_id]
    assert entry["raw_ingredient_text"] == "Vitamin A"
    assert entry["correction_fields"] == ["forms"]
    forms = entry["corrected_forms"]
    assert len(forms) == 1
    names = " ".join(str(form.get("name", "")) for form in forms).lower()
    assert "beta-carotene" in names or "beta carotene" in names, (
        f"{dsld_id}: expected the printed provitamin-A source, got {forms!r}"
    )
    assert "retinol" not in names, (
        f"{dsld_id}: an unknown Vitamin A form must never default to retinol — "
        f"the preformed-Vitamin-A UL would then apply incorrectly"
    )
    assert entry["corrected_forms"][0]["uniiCode"] == "01YAE03M7J"
    assert "corrected_quantity_value" not in entry
    assert "https://api.ods.od.nih.gov/dsld/s3/pdf/" + dsld_id + ".pdf" in entry["sources"], (
        f"{dsld_id}: the printed archived label image must be one of the cited sources"
    )


def test_no_new_entry_creates_a_global_alias(corrections):
    """Every Phase-3 correction stays product-scoped and name-rewriting entries
    never widen a shared token such as 'Folic Acid' into a global alias."""
    for dsld_id in (
        set(E2_UNIT_CORRECTIONS) | set(BULK_1340_VITAMIN_A_FORM) | {"269360"}
    ):
        entry = corrections[dsld_id]
        assert entry["scope"] == "dsld_id_only"
        assert entry["corrected_ingredient_text"] == entry["raw_ingredient_text"], (
            f"{dsld_id}: no Phase-3 correction may rewrite a row's identity text"
        )


def test_serrapeptase_activity_is_restored_from_the_printed_panel(corrections):
    entry = corrections["269360"]
    assert entry["raw_ingredient_text"] == "Serrapeptase Enzyme"
    assert entry["raw_quantity_value"] == 0
    assert entry["raw_quantity_unit"] == "NP"
    assert entry["corrected_quantity_value"] == 40000
    assert entry["corrected_quantity_unit"] == "SPU"
    assert sorted(entry["correction_fields"]) == ["quantity.unit", "quantity.value"]
    # The activity must be traceable to the panel and the manufacturer, not to
    # the product name.
    joined = " ".join(entry["sources"])
    assert "/dsld/s3/pdf/269360.pdf" in joined
    assert "doctorsbest.com" in joined
    assert "40,000" in entry["evidence"] or "40000" in entry["evidence"]


@pytest.mark.parametrize(
    "dsld_id", sorted(set(E2_UNIT_CORRECTIONS) | set(BULK_1340_VITAMIN_A_FORM) | {"269360"})
)
def test_every_new_correction_carries_reviewer_provenance(corrections, dsld_id):
    entry = corrections[dsld_id]
    for field in (
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
    ):
        assert entry.get(field), f"{dsld_id} missing {field!r}"
    assert entry["review_date"] == "2026-09-20"
    assert entry["scope"] == "dsld_id_only"
    assert all(
        str(url).startswith("https://") for url in entry["sources"]
    ), f"{dsld_id}: sources must be authoritative URLs"
    assert len(entry["evidence"]) > 200, (
        f"{dsld_id}: the evidence must state the source basis (printed panel, "
        f"sibling transcription, row %DV), not just assert a change"
    )


# ── the corrections must actually reach the cleaner ──────────────────────

sys.path.insert(0, os.path.join(_ROOT, "scripts"))

try:
    from enhanced_normalizer import EnhancedDSLDNormalizer  # type: ignore

    _NORMALIZER_AVAILABLE = True
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - defensive
    EnhancedDSLDNormalizer = None  # type: ignore
    _NORMALIZER_AVAILABLE = False
    _IMPORT_ERROR = exc


@pytest.fixture(scope="module")
def normalizer():
    if not _NORMALIZER_AVAILABLE:
        pytest.skip(f"EnhancedDSLDNormalizer not importable: {_IMPORT_ERROR}")
    return EnhancedDSLDNormalizer()


def _quantity_row(dsld_id: str, name: str, quantity, unit, forms=None):
    return {
        "id": int(dsld_id),
        "fullName": "probe",
        "brandName": "probe",
        "ingredientRows": [
            {
                "name": name,
                "category": "vitamin",
                "ingredientGroup": "Vitamin A",
                "order": 1,
                "ingredientId": 0,
                "uniiCode": "0",
                "quantity": [{"quantity": quantity, "unit": unit}],
                "forms": forms or [],
            }
        ],
    }


def test_cleaner_applies_the_e2_unit_correction(normalizer):
    product = _quantity_row("223563", "Vitamin A", 900, "mg RAE")
    rows = normalizer._apply_label_corrections(
        product["ingredientRows"], "223563"
    )
    row = rows[0]
    assert row["_pre_correction_quantity_unit"] == "mg RAE"
    assert row["quantity"][0]["quantity"] == 900, "the printed quantity is unchanged"
    assert row["quantity"][0]["unit"] == "mcg RAE"


def test_cleaner_restores_the_serrapeptase_activity(normalizer):
    product = _quantity_row("269360", "Serrapeptase Enzyme", 0, "NP")
    rows = normalizer._apply_label_corrections(
        product["ingredientRows"], "269360"
    )
    row = rows[0]
    assert row["_pre_correction_quantity_value"] == 0
    assert row["_pre_correction_quantity_unit"] == "NP"
    assert row["quantity"][0]["quantity"] == 40000
    assert row["quantity"][0]["unit"] == "SPU"


def test_cleaner_supplies_the_provitamin_a_form(normalizer):
    product = _quantity_row("243808", "Vitamin A", 3000, "mcg")
    rows = normalizer._apply_label_corrections(
        product["ingredientRows"], "243808"
    )
    row = rows[0]
    assert row["_pre_correction_forms"] == []
    assert [form["name"] for form in row["forms"]] == ["Natural Beta-Carotene"]
    assert row["forms"][0]["ingredientGroup"] == "Vitamin A"


def test_cleaner_leaves_the_unscopable_row_untouched(normalizer):
    """201420: renaming would hit the nested form row as well, so the lane must
    see the row unchanged rather than renamed twice."""
    product = _quantity_row("201420", "Folic Acid", 1333, "mcg DFE")
    rows = normalizer._apply_label_corrections(
        product["ingredientRows"], "201420"
    )
    row = rows[0]
    assert "_pre_correction_name" not in row
    assert row["name"] == "Folic Acid"
    assert row["quantity"][0]["quantity"] == 1333


def test_cleaner_leaves_the_withheld_e2_rows_untouched(normalizer):
    for dsld_id in E2_WITHHELD_NO_CORRECTION:
        product = _quantity_row(dsld_id, "Vitamin A", 6000, "mcg DFE")
        rows = normalizer._apply_label_corrections(
            product["ingredientRows"], dsld_id
        )
        row = rows[0]
        assert "_pre_correction_quantity_unit" not in row
        assert row["quantity"][0]["unit"] == "mcg DFE"
