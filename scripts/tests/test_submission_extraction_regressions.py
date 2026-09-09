"""Permanent counterexamples from the independent Batch 1 review (R4–R8)."""
import copy

import pytest

from submission_review.extraction import benchmark
from submission_review.extraction.envelope import LabelDraftError, validate_label_draft_v1
from test_submission_extraction_benchmark import _valid_draft, _gold, _entry, _write_set, _write, holdout


@pytest.mark.parametrize("unit", ["µg", "μg", "mcg", "IU", "CFU", "AFU"])
def test_unlike_printed_units_are_never_equal(unit):
    gold = _gold("x")
    gold["rows"][0]["amount"] = {"value": 1, "unit_text": "g"}
    draft = _valid_draft()
    draft["ingredient_rows"][0]["amount"]["value"] = {"value": 1, "unit_text": unit}
    assert benchmark.score_product(gold, "draft", draft)["tuple_exact"] == 0


def test_duplicate_dose_row_is_an_excess_active():
    draft = _valid_draft()
    extra = copy.deepcopy(draft["ingredient_rows"][0])
    extra["amount"]["value"]["value"] *= 1000
    draft["ingredient_rows"].append(extra)
    result = benchmark.score_product(_gold("x"), "draft", draft)
    assert len(result["invented"]) == 1


def test_repeated_printed_names_are_matched_one_to_one():
    draft, gold = _valid_draft(), _gold("x")
    draft["ingredient_rows"].append(copy.deepcopy(draft["ingredient_rows"][0]))
    gold["rows"].append(copy.deepcopy(gold["rows"][0]))
    result = benchmark.score_product(gold, "draft", draft)
    assert result["recalled_rows"] == result["tuple_exact"] == 2


def test_wrong_serving_basis_is_not_an_exact_tuple():
    gold = _gold("x")
    gold["serving"] = {"size": "2 capsules", "basis_text": "per serving"}
    draft = _valid_draft()
    draft["serving"]["size"]["value"] = "200 capsules"
    draft["serving"]["basis_text"]["value"] = "per capsule"
    assert benchmark.score_product(gold, "draft", draft)["tuple_exact"] == 0


def test_readable_failed_products_stay_in_quality_denominators(tmp_path):
    entries = [_entry(f"h-{i}", f"brand-{i}", "holdout") for i in range(40)]
    _write_set(tmp_path, entries, {e["product_key"]: _gold(e["product_key"]) for e in entries})
    run = tmp_path / "run"
    run.mkdir()
    for i in range(40):
        _write(run, f"h-{i}", _valid_draft() if i == 0 else {
            "schema_version": "extraction_failure_v1", "code": "model_failure"})
    report = benchmark.evaluate(tmp_path, run, "holdout")
    assert report["metrics"]["row_recall"]["rate"] == 0.025
    assert report["metrics"]["tuple_exact_rate"]["N"] == 40
    assert report["verdict"] != "qualifies"


def test_missing_latency_and_human_evidence_do_not_pass(holdout):
    root, run = holdout
    _write(run, "h-1", _valid_draft())
    report = benchmark.evaluate(root, run, "holdout")
    assert report["gates"]["latency_p95_seconds"]["passed"] is not True
    assert report["verdict"] != "qualifies"


@pytest.mark.parametrize("bad", [[], {}])
def test_enum_type_errors_are_typed_failures(bad):
    draft = _valid_draft()
    draft["identity"]["brand"]["status"] = bad
    with pytest.raises(LabelDraftError):
        validate_label_draft_v1(draft)


def test_model_cannot_reference_unsent_inputs():
    draft = _valid_draft()
    draft["sent_inputs"] = []
    with pytest.raises(LabelDraftError):
        validate_label_draft_v1(draft)


@pytest.mark.parametrize("unit", ["μg", "µg", "mcg"])
def test_reviewed_microgram_spellings_are_equivalent(unit):
    draft, gold = _valid_draft(), _gold("x")
    draft["ingredient_rows"][0]["amount"]["value"]["unit_text"] = unit
    gold["rows"][0]["amount"]["unit_text"] = "mcg"
    assert benchmark.score_product(gold, "draft", draft)["tuple_exact"] == 1


@pytest.mark.parametrize("left,right", [("CFU", "AFU"), ("AFU", "IU"), ("IU", "CFU")])
def test_biological_units_remain_distinct(left, right):
    draft, gold = _valid_draft(), _gold("x")
    draft["ingredient_rows"][0]["amount"]["value"]["unit_text"] = left
    gold["rows"][0]["amount"]["unit_text"] = right
    assert benchmark.score_product(gold, "draft", draft)["tuple_exact"] == 0


def test_repeated_blend_names_retain_distinct_parent_ownership():
    draft, gold = _valid_draft(), _gold("x")
    row = copy.deepcopy(draft["ingredient_rows"][0])
    grow = copy.deepcopy(gold["rows"][0])
    draft["ingredient_rows"], gold["rows"] = [], []
    for amount in (300, 600):
        header, member = copy.deepcopy(row), copy.deepcopy(row)
        header["display_name"]["value"] = "Blend"
        header["is_blend_header"] = True
        header["amount"]["value"]["value"] = amount
        member["parent_index"] = len(draft["ingredient_rows"])
        gheader, gmember = copy.deepcopy(grow), copy.deepcopy(grow)
        gheader.update(display_name="Blend", is_blend_header=True, amount={"value": amount, "unit_text": "mg"})
        gmember["parent_index"] = len(gold["rows"])
        draft["ingredient_rows"].extend([header, member])
        gold["rows"].extend([gheader, gmember])
    assert benchmark.score_product(gold, "draft", draft)["tuple_exact"] == 4
    draft["ingredient_rows"][3]["parent_index"] = 0
    assert benchmark.score_product(gold, "draft", draft)["tuple_exact"] == 3


@pytest.mark.parametrize("field,value", [("form_text", "magnesium oxide"), ("percent_dv", 480)])
def test_forms_and_percent_dv_have_explicit_fidelity_checks(field, value):
    draft = _valid_draft()
    draft["ingredient_rows"][0][field]["value"] = value
    result = benchmark.score_product(_gold("x"), "draft", draft)
    assert result["field_exact"] < result["field_checks"]
    assert result["tuple_exact"] == 0


def test_partial_amount_with_missing_number_is_measured_without_crashing():
    draft = _valid_draft()
    draft["ingredient_rows"][0]["amount"].update(status="partial", value={"value": None, "unit_text": "mg"})
    validate_label_draft_v1(draft)
    assert benchmark.score_product(_gold("x"), "draft", draft)["tuple_exact"] == 0


def test_raw_barcode_retains_leading_zeroes_and_other_ingredients_are_measured():
    draft = _valid_draft()
    draft["identity"]["barcode_digits_seen"]["value"] = "12345678905"
    draft["other_ingredients"]["text"]["value"] = "Vegetable cellulose"
    result = benchmark.score_product(_gold("x"), "draft", draft)
    assert result["wrong_product"]
    assert result["field_exact"] == result["field_checks"] - 2


def test_unit_error_cannot_hide_inside_one_percent_tuple_allowance(tmp_path):
    draft, gold = _valid_draft(), _gold("h-1")
    gold["rows"] = [copy.deepcopy(gold["rows"][0]) for _ in range(100)]
    draft["ingredient_rows"] = [copy.deepcopy(draft["ingredient_rows"][0]) for _ in range(100)]
    for row in gold["rows"]:
        row["amount"]["unit_text"] = "g"
    for row in draft["ingredient_rows"]:
        row["amount"]["value"]["unit_text"] = "g"
    draft["ingredient_rows"][-1]["amount"]["value"]["unit_text"] = "µg"
    _write_set(tmp_path, [_entry("h-1", "brand", "holdout")], {"h-1": gold})
    run = tmp_path / "run"
    run.mkdir()
    _write(run, "h-1", draft)
    report = benchmark.evaluate(tmp_path, run, "holdout")
    assert report["gates"]["tuple_exact_rate"]["passed"] is True
    assert report["gates"]["unit_mismatches"]["passed"] is False


@pytest.mark.parametrize("gold_amount,draft_amount", [(200, 0), (0, 200)])
def test_zero_and_positive_amount_substitution_is_critical(gold_amount, draft_amount):
    draft, gold = _valid_draft(), _gold("x")
    gold["rows"][0]["amount"]["value"] = gold_amount
    draft["ingredient_rows"][0]["amount"]["value"]["value"] = draft_amount
    assert benchmark.score_product(gold, "draft", draft)["magnitude_errors"]


def test_explicit_wrong_brand_is_critical_even_when_marked_partial():
    draft = _valid_draft()
    draft["identity"]["brand"].update(value="Clearly Other Product Brand", status="partial")
    assert benchmark.score_product(_gold("x"), "draft", draft)["wrong_product"]


@pytest.mark.parametrize("name_status", ["partial", "read"])
@pytest.mark.parametrize("gold_readable", [True, False])
@pytest.mark.parametrize("amount,critical", [({"value": 200000, "unit_text": "mg"}, "magnitude_errors"),
                                           ({"value": 200, "unit_text": "g"}, "unit_mismatches")])
def test_known_amount_contradictions_are_checked_before_recall_exclusion(name_status, gold_readable, amount, critical):
    draft, gold = _valid_draft(), _gold("x")
    draft["ingredient_rows"][0]["display_name"]["status"] = name_status
    draft["ingredient_rows"][0]["amount"]["value"] = amount
    gold["rows"][0]["readable"] = gold_readable
    assert benchmark.score_product(gold, "draft", draft)[critical]
