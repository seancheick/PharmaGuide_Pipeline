"""Sean-approved magnesium form calibration, October 13, 2026 (Option C).

bio_score grades magnesium delivery only. Tied top forms share 15 so the
parent-relative Formulation value equals the authored whole number; purpose,
tolerability and personal fit are assessed elsewhere. Glycerophosphate 2 -> 6
is held as a separate decision, so the unspecified floor stays 1.
"""

import json
from pathlib import Path

import pytest

from iqm_form_evidence import load_backlog_file, validate_iqm_form
from scoring_reference_resolver import (
    effective_form_bio,
    parent_relative_form_quality,
    unknown_form_quality,
)

DATA = Path(__file__).resolve().parents[1] / "data"
IQM = json.loads((DATA / "ingredient_quality_map.json").read_text())
FORMS = IQM["magnesium"]["forms"]

APPROVED = {
    "magnesium citrate": 15,
    "magnesium chloride": 15,
    "magnesium lactate": 15,
    "magnesium aspartate": 15,
    "magnesium glycinate": 12,
    "magnesium amino acid chelate": 11,
    "magnesium malate": 11,
    "magnesium citrate-malate": 11,
    "magnesium threonate": 11,
    "magnesium gluconate": 10,
    "magnesium taurate": 10,
    "magnesium ascorbate (as magnesium source)": 10,
    "magnesium acetyl-taurate": 9,
    "magnesium orotate": 9,
    "magnesium pyruvate": 9,
    "magnesium succinate": 9,
    "magnesium brown rice chelate": 6,
    "magnesium carbonate": 6,
    "magnesium phosphate": 6,
    "magnesium glycerophosphate": 2,  # held: no citable basis for 6 yet
    "magnesium sulfate": 4,
    "magnesium hydroxide": 3,
    "magnesium oxide": 3,
    "magnesium (unspecified)": 1,
}


def _pmids(form):
    refs = (form.get("form_evidence") or {}).get("references_structured") or []
    return {str(r.get("pmid")) for r in refs}


def test_every_magnesium_form_has_its_approved_whole_number_score():
    assert {name: form["bio_score"] for name, form in FORMS.items()} == APPROVED
    assert all(type(form["bio_score"]) is int for form in FORMS.values())


@pytest.mark.parametrize("name", sorted(APPROVED))
def test_parent_relative_value_equals_authored_score(name):
    effective = effective_form_bio(IQM["magnesium"], FORMS[name])
    assert parent_relative_form_quality("magnesium", effective) == APPROVED[name]


def test_unspecified_magnesium_is_the_mechanical_floor_without_a_named_form():
    unknown = unknown_form_quality(IQM["magnesium"])
    assert unknown["bio_score"] == 1
    assert unknown["form_id"] == "magnesium (unspecified)"
    assert unknown["basis"] == "authored_unspecified_mechanical_floor"


def test_excellent_magnesium_forms_carry_verified_evidence_not_backlog_grandfathering():
    backlog = load_backlog_file(DATA / "iqm_excellent_evidence_backlog.json")
    for name, score in APPROVED.items():
        if score < 12:
            continue
        assert validate_iqm_form(FORMS[name], label=name) == []
        assert f"magnesium::{name}" not in backlog


def test_glycinate_evidence_records_population_and_mixed_comparisons():
    evidence = FORMS["magnesium glycinate"]["form_evidence"]
    assert evidence["evidence_level"] == "moderate"
    assert {"7815675", "39770988", "29630135"} <= _pmids(FORMS["magnesium glycinate"])
    rationale = evidence["rationale"]
    assert "ileal resection" in rationale
    assert "23.5%" in rationale and "22.8%" in rationale
    assert "superiority" in rationale
    # Population and preparation limits stay attached to the grade.
    assert "orosoluble powders" in rationale
    assert "buffered" in rationale and "lysinate" in rationale


def test_changed_or_retained_forms_cite_their_human_or_regulatory_source():
    assert "38481468" in _pmids(FORMS["magnesium threonate"])
    chloride = FORMS["magnesium chloride"]
    assert {"11794633", "1468087"} <= _pmids(chloride)
    assert chloride["form_evidence"]["references_structured"][0]["pmid"] == "11794633"
    gluconate = FORMS["magnesium gluconate"]
    assert "1468087" in _pmids(gluconate)
    own_claims = gluconate["absorption"] + gluconate["form_evidence"]["rationale"]
    assert "no human" not in own_claims.lower()
    assert "healthy adults" in gluconate["form_evidence"]["rationale"]


def test_held_glycerophosphate_is_untouched_by_this_batch():
    form = FORMS["magnesium glycerophosphate"]
    assert form["bio_score"] == 2
    assert "form_evidence" not in form
    assert "provisional" not in form["notes"]


def test_magnesium_prose_no_longer_cites_superseded_scores():
    assert "bio_score 14" not in FORMS["magnesium citrate"]["notes"]
    assert "pending clinical calibration" not in FORMS["magnesium glycinate"]["notes"]
    assert "pending clinical calibration" not in FORMS["magnesium citrate"]["notes"]
