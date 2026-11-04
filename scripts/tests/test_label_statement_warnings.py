"""A label's own firm pregnancy statement reaches only the people it names, in its own words."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_build_final_db import make_enriched, make_scored
from build_final_db import build_detail_blob

_EVAL_PATH = Path(__file__).resolve().parents[1] / "profile_gate_evaluator.py"
_spec = importlib.util.spec_from_file_location("profile_gate_evaluator", _EVAL_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["profile_gate_evaluator"] = _mod
_spec.loader.exec_module(_mod)

PREGNANT = dict(conditions=["pregnancy"], flags=["pregnant"])
NURSING = dict(conditions=["lactation"], flags=["breastfeeding"])
TTC = dict(conditions=["ttc"], flags=["trying_to_conceive"])
MAN_TTC = dict(conditions=["ttc"], flags=["trying_to_conceive", "sex_male"])
UNSTATED_TTC = dict(conditions=["ttc"], flags=["trying_to_conceive", "sex_unstated"])
WOMAN_TTC = dict(conditions=["ttc"], flags=["trying_to_conceive"])
NO_PROFILE = dict(conditions=[], flags=[])


def _blob(*notes):
    enriched = make_enriched()
    enriched["statements"] = [{"type": "Precautions", "notes": note} for note in notes]
    return build_detail_blob(enriched, make_scored())


def _label_rows(*notes):
    return [w for w in _blob(*notes)["warnings"] if w.get("type") == "label_statement"]


def _fires(warning, viewer):
    return _mod.evaluate_profile_gate(
        warning["profile_gate"],
        {"conditions": viewer["conditions"], "drug_classes": [], "profile_flags": viewer["flags"]},
        {"product_form": None, "nutrient_form": None, "dose_per_day": None, "dose_unit": None},
        base_severity=warning["severity"],
    )


@pytest.mark.parametrize("sentence,severity,conditions", [
    ("Warning: Do not use if you are pregnant.", "avoid", ["pregnancy"]),
    ("Do not use if pregnant or nursing.", "avoid", ["pregnancy", "lactation"]),
    ("Not to be taken by pregnant or lactating women.", "avoid", ["pregnancy", "lactation"]),
    ("Not intended for use by pregnant or nursing women.", "avoid", ["pregnancy", "lactation"]),
    ("Dietary supplementation with phytosterols is not suitable for pregnant or lactating women.", "avoid", ["pregnancy", "lactation"]),
    ("Do not use if pregnant, breast-feeding, or under 18.", "avoid", ["pregnancy", "lactation"]),
    ("Warning: If pregnant, nursing, or trying to conceive, do not use this product.", "avoid", ["pregnancy", "lactation", "ttc"]),
    ("Do not use if you are pregnant, may become pregnant, or are nursing.", "avoid", ["pregnancy", "lactation", "ttc"]),
    ("Do not use if you are pregnant, nursing or are a woman of childbearing age.", "avoid", ["pregnancy", "lactation", "ttc"]),
    ("This product is not recommended for women who may become pregnant.", "avoid", ["ttc"]),
    ("This product is not intended for children or women who may be pregnant or nursing.", "avoid", ["pregnancy", "lactation"]),
    ("Do not take if pregnant, breastfeeding, on medication, or with a known medical condition unless you have consulted a physician.", "caution", ["pregnancy", "lactation"]),
    ("Do not use this product unless advised by a physician if you are pregnant, attempting to become pregnant, or nursing;", "caution", ["pregnancy", "lactation", "ttc"]),
    ("Not for use during pregnancy and lactation unless directed by a healthcare practitioner.", "caution", ["pregnancy", "lactation"]),
    ("Do not take this product if you are pregnant or nursing, consult your physician if you are on other medications.", "avoid", ["pregnancy", "lactation"]),
    ("Do not use if pregnant, consult your doctor if nursing.", "avoid", ["pregnancy"]),
])
def test_firm_statement_carries_its_severity_and_audience(sentence, severity, conditions):
    rows = _label_rows(sentence)
    assert [row["detail"] for row in rows] == [sentence]
    assert rows[0]["severity"] == severity
    assert rows[0]["condition_ids"] == sorted(conditions)


@pytest.mark.parametrize("note", [
    "If you are pregnant, nursing, or taking any medications, consult a healthcare professional before use.",
    "Women who are pregnant or likely to become pregnant should not exceed the recommended dose.",
    "Do not take more than 2 capsules if pregnant.",
    "Women of childbearing potential should consider an effective method of contraception during the use of this product.",
    "For use before, during and after pregnancy.",
    "Do not use if seal is broken. If pregnant, consult your doctor.",
    "Do not use if seal is broken, consult your doctor if pregnant.",
    "If pregnant, ask your doctor, and never share this bottle.",
    "Do not use if pregnant {chart}",
    "Do not use if seal is broken.",
    "Keep out of reach of children.",
])
def test_anything_else_stays_out(note):
    assert _label_rows(note) == []


@pytest.mark.parametrize("note,sentence", [
    ("Store cool. Warning: Do not use if pregnant. Keep away from children.", "Warning: Do not use if pregnant."),
    ("Warning for AM Tablet: DO NOT take if you are Pregnant or Nursing.", "Warning for AM Tablet: DO NOT take if you are Pregnant or Nursing."),
    ("Pack This product is not to be taken by pregnant\nor lactating women.", "Pack This product is not to be taken by pregnant\nor lactating women."),
])
def test_the_sentence_stays_as_printed(note, sentence):
    assert [row["detail"] for row in _label_rows(note)] == [sentence]


def test_the_card_says_only_label_warning_and_the_sentence():
    sentence = "Do not use Moringa if you are pregnant, nursing or under 18 years of age."
    row = _label_rows(sentence)[0]
    assert row["title"] == "Label warning"
    assert row["alert_body"] == sentence
    assert row["detail"] == sentence
    assert row["evidence_level"] == "ungraded"
    assert row["source"] == "label_statements"
    assert row["display_mode_default"] == "suppress"
    assert row["drug_class_ids"] == []
    for field in ("alert_headline", "informational_note", "action", "safety_warning", "safety_warning_one_liner"):
        assert field not in row


def test_it_stays_out_of_the_list_shown_without_a_profile():
    blob = _blob("Do not use if pregnant or nursing.")
    assert not [w for w in blob["warnings_profile_gated"] if w.get("type") == "label_statement"]


def test_it_never_reaches_the_top_warnings_or_changes_any_other_blob_field():
    plain = build_detail_blob(make_enriched(), make_scored())
    labelled = _blob("Do not use if pregnant or nursing.")
    assert [w for w in labelled["warnings"] if w.get("type") != "label_statement"] == plain["warnings"]
    differing = {k for k in plain.keys() | labelled.keys() if plain.get(k) != labelled.get(k)}
    assert differing == {"warnings"}


def test_two_different_statements_stay_two_cards():
    first, second = "Do not use if pregnant or nursing.", "Not intended for use by pregnant women."
    assert [row["detail"] for row in _label_rows(first, second)] == [first, second]
    soft_one = "Do not take if pregnant unless you have consulted a physician."
    soft_two = "Not for use during pregnancy unless directed by a healthcare practitioner."
    assert [row["detail"] for row in _label_rows(soft_one, soft_two)] == [soft_one, soft_two]


def test_a_repeated_statement_is_one_card():
    rows = _label_rows("Do not use if pregnant.", "Do not use if pregnant.", "DO NOT  USE IF PREGNANT.")
    assert [row["detail"] for row in rows] == ["Do not use if pregnant."]


@pytest.mark.parametrize("statements", [
    None, "Do not use if pregnant.", 7, [], [None, 7, "Do not use if pregnant."],
    [{"type": "Precautions"}, {"notes": None}, {"notes": 7}, {"notes": ""}],
])
def test_missing_or_malformed_statements_emit_nothing(statements):
    enriched = make_enriched()
    enriched["statements"] = statements
    assert not [w for w in build_detail_blob(enriched, make_scored())["warnings"] if w.get("type") == "label_statement"]


@pytest.mark.parametrize("sentence,viewer,fires", [
    ("Do not use if pregnant or nursing.", PREGNANT, True),
    ("Do not use if pregnant or nursing.", NURSING, True),
    ("Do not use if pregnant or nursing.", TTC, False),
    ("Do not use if pregnant or nursing.", NO_PROFILE, False),
    ("Warning: Do not use if you are pregnant.", NURSING, False),
    ("Do not use if pregnant, nursing, or trying to conceive.", TTC, True),
    ("This product is not recommended for women who may become pregnant.", TTC, True),
    ("Do not take if pregnant unless you have consulted a physician.", PREGNANT, True),
    ("Do not take if pregnant unless you have consulted a physician.", NO_PROFILE, False),
])
def test_the_gate_reaches_only_the_people_named(sentence, viewer, fires):
    assert _fires(_label_rows(sentence)[0], viewer).fires is fires


@pytest.mark.parametrize("viewer,fires", [
    (MAN_TTC, True), (UNSTATED_TTC, True), (WOMAN_TTC, False), (PREGNANT, False),
    (dict(conditions=[], flags=["sex_male"]), False), (NO_PROFILE, False),
])
def test_a_statement_to_men_reaches_men_and_unstated_sex_trying_to_conceive(viewer, fires):
    rows = _label_rows("Warning: Not for use in men if attempting to conceive.")
    assert rows[0]["severity"] == "avoid"
    assert rows[0]["title"] == "Label warning"
    assert rows[0]["evidence_level"] == "ungraded"
    assert rows[0]["condition_ids"] == ["ttc"]
    assert _fires(rows[0], viewer).fires is fires


def test_a_label_with_both_statements_gives_each_its_own_audience():
    men = "Not for use in men if attempting to conceive."
    women = "Do not use if pregnant or nursing."
    rows = {row["detail"]: row for row in _label_rows(men, women)}
    assert rows[men]["condition_ids"] == ["ttc"]
    assert rows[women]["condition_ids"] == ["lactation", "pregnancy"]
    assert _fires(rows[women], MAN_TTC).fires is False


@pytest.mark.parametrize("sentence", [
    "Do not use if pregnant or nursing.",
    "Do not take if pregnant unless you have consulted a physician.",
    "Not for use in men if attempting to conceive.",
])
def test_every_gate_is_a_valid_gate(sentence):
    taxonomy = json.loads((Path(__file__).resolve().parents[1] / "data" / "clinical_risk_taxonomy.json").read_text())
    assert _mod.validate_profile_gate(_label_rows(sentence)[0]["profile_gate"], taxonomy=taxonomy) == []
