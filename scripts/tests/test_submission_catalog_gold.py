"""Guards on matching a bottle to a transcription nobody derived from it."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from submission_review.extraction import catalog_gold as cg  # noqa: E402
from submission_review.extraction.benchmark import REQUIRED_CASES  # noqa: E402


class _Index:
    """Stands in for the console's identity index, same lookup contract."""

    def __init__(self, matches: dict[str, list]) -> None:
        self._matches = matches

    def lookup(self, gtin14: str):
        return list(self._matches.get(gtin14, ()))


class _Hit:
    def __init__(self, dsld_id: str, brand: str = "B", name: str = "N", upc: str = "") -> None:
        self.dsld_id, self.brand_name, self.product_name, self.upc_sku = dsld_id, brand, name, upc


def _blob(tmp: Path, dsld_id: str, **overrides) -> Path:
    payload = {
        "dsld_id": dsld_id,
        "brand_name": "Northwind",
        "product_name": "Magnesium Glycinate",
        "serving_info": {"basis_count": 2.0, "basis_unit": "capsule"},
        "label_record": {"source_name": "NIH DSLD", "source_date": "2019-01-01",
                         "catalog_version": "CODE 1 X", "formula_fingerprint": "f" * 64},
        "proprietary_blend_detail": {"has_proprietary_blends": False},
        "ingredients": [{"raw_source_text": "Magnesium", "quantity": 200.0, "unit": "mg",
                         "forms": ["glycinate"]}],
    }
    payload.update(overrides)
    path = tmp / f"{dsld_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_every_required_case_is_classified():
    """An unclassified case would be silently uncovered by the report."""
    assert set(cg.CASE_SOURCES) == set(REQUIRED_CASES)
    assert set(cg.CASE_SOURCES.values()) == {"catalog", "capture", "sourcing"}


def test_mass_spelling_comes_from_the_pipeline_not_from_a_second_table():
    """A local table missed Milligram(s) on 820 rows of the real corpus."""
    for spelling in ("mg", "Milligram(s)", "mg NE", "mg DFE", "mg AT", "mgc"):
        assert cg.unit_case(spelling) == "unit_mg" or spelling == "mgc", spelling
    assert cg.unit_case("mgc") == "unit_mcg"          # the pipeline's own alias
    for spelling in ("mcg", "Microgram(s)", "\u00b5g", "mcg DFE", "mcg RAE"):
        assert cg.unit_case(spelling) == "unit_mcg", spelling
    for spelling in ("g", "Gram(s)", "grams", "Grams Powder"):
        assert cg.unit_case(spelling) == "unit_g", spelling


def test_activity_units_survive_a_magnitude_and_a_dosage_form():
    """Probiotics print "Billion AFU", never a bare token.

    Found in the real corpus after a bare-spelling table reported AFU as
    absent from the catalogue entirely, which would have sent a person
    hunting for a product they already had.
    """
    assert cg.unit_case("AFU") == "unit_AFU"
    assert cg.unit_case("Billion AFU") == "unit_AFU"
    assert cg.unit_case("billion CFU") == "unit_CFU"
    assert cg.unit_case("12.5 Billion Probiotic CFU Capsule(s)") == "unit_CFU"
    assert cg.unit_case("75000000000 CFU Capsule(s)") == "unit_CFU"


def test_a_unit_nobody_recognises_belongs_to_no_family():
    """Whole words only: a prefix rule reads the enzyme unit GaIU as IU."""
    for unknown in ("GALU", "GaIU", "mmg", "mcg/g", "NP", "HUT", "Kilogram(s)", None, ""):
        assert cg.unit_case(unknown) is None, unknown


def test_nested_blend_reads_the_detail_object_not_the_bare_flag(tmp_path):
    """`proprietary_blend` answers a different question and is not this one."""
    flagged = json.loads(_blob(tmp_path, "1", proprietary_blend=True).read_text())
    assert "nested_blend" not in cg.label_cases(flagged)
    real = json.loads(_blob(tmp_path, "2",
                            proprietary_blend_detail={"has_proprietary_blends": True},
                            proprietary_blend=False).read_text())
    assert "nested_blend" in cg.label_cases(real)


def test_label_cases_never_claims_a_case_the_record_cannot_show(tmp_path):
    blob = json.loads(_blob(tmp_path, "3").read_text())
    assert cg.label_cases(blob) <= cg.CATALOG_CASES
    assert "dv_only" not in cg.label_cases(blob)


def test_multiple_forms_needs_more_than_one_form(tmp_path):
    one = json.loads(_blob(tmp_path, "4").read_text())
    assert "multiple_forms" not in cg.label_cases(one)
    two = json.loads(_blob(tmp_path, "5", ingredients=[
        {"raw_source_text": "Magnesium", "quantity": 200.0, "unit": "mg",
         "forms": ["glycinate", "oxide"]}]).read_text())
    assert "multiple_forms" in cg.label_cases(two)


def test_a_record_file_holding_another_record_is_refused(tmp_path):
    _blob(tmp_path, "7")
    (tmp_path / "8.json").write_text((tmp_path / "7.json").read_text(), encoding="utf-8")
    with pytest.raises(ValueError, match="does not hold record 8"):
        cg.read_candidate("8", tmp_path)


def test_a_record_id_cannot_escape_the_catalog_directory(tmp_path):
    """A CLI identifier must never turn into an arbitrary file path."""
    outside = tmp_path.parent / "secret.json"
    outside.write_text(json.dumps({"dsld_id": "../secret"}), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid catalog record id"):
        cg.read_candidate("../secret", tmp_path)


def test_an_unreadable_barcode_is_not_looked_up(tmp_path):
    [result] = cg.scan(["99999"], _Index({}), tmp_path)
    assert result.canonical == () and not result.matched
    assert result.note == "not a readable barcode"


def test_a_valid_barcode_with_no_record_matches_nothing(tmp_path):
    [result] = cg.scan(["012345678905"], _Index({}), tmp_path)
    assert result.canonical and not result.matched and result.note is None


def test_two_records_on_one_barcode_are_reported_never_resolved(tmp_path):
    _blob(tmp_path, "10")
    _blob(tmp_path, "11", product_name="Magnesium Glycinate II")
    index = _Index({"00012345678905": [_Hit("10"), _Hit("11")]})
    [result] = cg.scan(["012345678905"], index, tmp_path)
    assert len(result.candidates) == 2
    assert "confirm which edition" in result.note


def test_a_match_carries_what_a_person_compares_against_the_bottle(tmp_path):
    _blob(tmp_path, "12")
    index = _Index({"00012345678905": [_Hit("12")]})
    [result] = cg.scan(["012345678905"], index, tmp_path)
    candidate = result.candidates[0]
    assert candidate.corroboration() == {
        "brand": "Northwind", "product_name": "Magnesium Glycinate",
        "serving": "2 capsule", "active_rows": 1,
    }
    # Provenance is carried, and is deliberately not part of corroboration:
    # neither identifies the package in a person's hand.
    assert candidate.formula_fingerprint == "f" * 64
    assert candidate.catalog_version == "CODE 1 X"


def _draft(rows: list[dict]) -> dict:
    return {"ingredient_rows": rows}


def _row(name: str, value=None, unit=None, parent=None):
    amount = None if value is None else {
        "status": "read", "value": {"value": value, "unit_text": unit}}
    return {"display_name": {"status": "read", "value": name}, "amount": amount,
            "parent_index": parent, "is_blend_header": False, "status": "read"}


def test_disagreements_report_both_directions(tmp_path):
    blob = json.loads(_blob(tmp_path, "20", ingredients=[
        {"raw_source_text": "Magnesium", "quantity": 200.0, "unit": "mg", "forms": []},
        {"raw_source_text": "Zinc", "quantity": 15.0, "unit": "mg", "forms": []},
    ]).read_text())
    found = cg.disagreements(blob, _draft([
        _row("Magnesium", 200.0, "mg"),
        _row("Ashwagandha", 300.0, "mg"),
    ]))
    kinds = {(d.kind, d.row) for d in found}
    assert ("absent_from_record", "Ashwagandha") in kinds
    assert ("missing_from_draft", "Zinc") in kinds
    assert not any(d.row == "Magnesium" for d in found)


def test_a_wrong_dose_and_a_wrong_unit_are_reported_differently(tmp_path):
    blob = json.loads(_blob(tmp_path, "21").read_text())
    [dose] = cg.disagreements(blob, _draft([_row("Magnesium", 2000.0, "mg")]))
    assert dose.kind == "amount" and dose.record == "200 mg" and dose.draft == "2000 mg"
    [unit] = cg.disagreements(blob, _draft([_row("Magnesium", 200.0, "mcg")]))
    assert unit.kind == "unit" and unit.draft == "200 mcg"


def test_coverage_counts_and_thin_cases():
    counts = cg.case_counts([{"unit_mg", "nested_blend"}, {"unit_mg"}])
    assert counts["unit_mg"] == 2 and counts["nested_blend"] == 1
    thin = cg.thin_cases(counts)
    assert "unit_mg" not in thin and "nested_blend" in thin
    assert set(thin) <= set(REQUIRED_CASES)


def test_a_form_parenthetical_does_not_become_a_phantom_row(tmp_path):
    """DSLD keeps the form in its own field; a label prints it inline.

    Measured on a real 21-row prenatal record, exact-name matching alone
    reported 12 of 21 rows as disagreements on wording, which would send a
    person to adjudicate more than half a label they never needed to see.
    """
    blob = json.loads(_blob(tmp_path, "30", ingredients=[
        {"raw_source_text": "Niacin", "quantity": 20.0, "unit": "mg", "forms": []},
    ]).read_text())
    [only] = cg.disagreements(blob, _draft([_row("Niacin (as niacinamide)", 20.0, "mg")]))
    assert only.kind == "name_text"
    # Both printed names are shown, so a person can see whether it is one row.
    assert "Niacin ·" in only.record and "niacinamide" in only.draft


def test_a_wrong_dose_survives_the_name_pairing(tmp_path):
    """Pairing must never soften a contradiction into a wording note."""
    blob = json.loads(_blob(tmp_path, "31", ingredients=[
        {"raw_source_text": "Niacin", "quantity": 20.0, "unit": "mg", "forms": []},
    ]).read_text())
    [only] = cg.disagreements(blob, _draft([_row("Niacin (as niacinamide)", 200.0, "mg")]))
    assert only.kind == "amount" and only.record == "20 mg" and only.draft == "200 mg"


def test_an_ambiguous_leftover_stays_a_disagreement(tmp_path):
    """Two record rows share a dose, so pairing by dose would be a guess."""
    blob = json.loads(_blob(tmp_path, "32", ingredients=[
        {"raw_source_text": "Rhodiola", "quantity": 300.0, "unit": "mg", "forms": []},
        {"raw_source_text": "Schisandra", "quantity": 300.0, "unit": "mg", "forms": []},
    ]).read_text())
    found = cg.disagreements(blob, _draft([_row("Ashwagandha root", 300.0, "mg")]))
    kinds = sorted(d.kind for d in found)
    assert kinds == ["absent_from_record", "missing_from_draft", "missing_from_draft"]


def test_one_record_row_is_paired_at_most_once(tmp_path):
    blob = json.loads(_blob(tmp_path, "33", ingredients=[
        {"raw_source_text": "Magnesium", "quantity": 200.0, "unit": "mg", "forms": []},
    ]).read_text())
    found = cg.disagreements(blob, _draft([
        _row("Magnesium", 200.0, "mg"), _row("Magnesium", 200.0, "mg"),
    ]))
    assert [d.kind for d in found] == ["absent_from_record"]


def test_a_reformulated_record_surfaces_as_hard_disagreements(tmp_path):
    """A stale edition is not detectable by date; it shows up as contradiction.

    The record cannot tell you it is out of date, and `source_date` only says
    when the record was written. What a reformulation looks like from here is
    a changed dose plus a row on one side and not the other — which is exactly
    the signal that sends the product to the two-person route instead.
    """
    blob = json.loads(_blob(tmp_path, "40", ingredients=[
        {"raw_source_text": "Magnesium", "quantity": 200.0, "unit": "mg", "forms": []},
        {"raw_source_text": "Vitamin B6", "quantity": 2.0, "unit": "mg", "forms": []},
    ]).read_text())
    found = cg.disagreements(blob, _draft([
        _row("Magnesium (as magnesium glycinate)", 400.0, "mg"),   # reformulated dose
        _row("Zinc", 15.0, "mg"),                                  # added since
    ]))
    kinds = sorted((d.kind, d.row) for d in found)
    assert ("amount", "Magnesium (as magnesium glycinate)") in kinds
    assert ("absent_from_record", "Zinc") in kinds
    assert ("missing_from_draft", "Vitamin B6") in kinds
    assert not any(d.kind == "name_text" for d in found)


def test_a_record_carries_its_age_so_a_person_can_weigh_it(tmp_path):
    _blob(tmp_path, "41")
    candidate = cg.read_candidate("41", tmp_path)
    assert candidate.source_date == "2019-01-01"
    assert candidate.source_name == "NIH DSLD"
    # Age is never a verdict here: nothing in this module drops or downgrades a
    # record for being old. A person compares the package.
    assert "source_date" not in candidate.corroboration()
