"""A form-scoped interaction rule reads a skipped blend row's printed form.

The scorer skips a row inside a blend with no amount, so it never gets a form and
RULE_IQM_GLUCOMANNAN_DIABETES, scoped to konjac glucomannan, stayed silent on 200826.
Printing any amount turned the rule on, so the warning depended on disclosure.
Ginger on the same blend kept its alerts only because its rules have no form scope.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
GLUCOMANNAN_RULE = "RULE_IQM_GLUCOMANNAN_DIABETES"


@pytest.fixture(scope="module")
def pipeline():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    return EnhancedDSLDNormalizer(), SupplementEnricherV3()


def _alerts(pipeline, label):
    normalizer, enricher = pipeline
    raw = json.loads((FIXTURES / f"skipped_row_form_{label}_raw.json").read_text())
    return enricher.enrich_product(normalizer.normalize_product(raw))[0]["interaction_profile"]["ingredient_alerts"]


@pytest.mark.parametrize("label, printed", [
    ("200826", "Glucomannan"),
    ("28518", "Konjac Glucomannan"),
    ("213312", "Glucomannan powder"),
])
def test_a_hidden_amount_doesnt_silence_a_rule_about_the_printed_form(pipeline, label, printed):
    alert = next(a for a in _alerts(pipeline, label) if a["rule_id"] == GLUCOMANNAN_RULE)
    assert alert["ingredient_name"] == printed
    assert {hit["condition_id"] for hit in alert["condition_hits"]} >= {"diabetes"}
    assert {hit["drug_class_id"] for hit in alert["drug_class_hits"]} >= {"hypoglycemics_high_risk"}


def test_generic_fiber_in_a_blend_stays_outside_the_rule(pipeline):
    enricher = pipeline[1]
    rule = {"form_scope": ["konjac glucomannan"]}
    row = {"name": "Soluble Fiber", "raw_source_text": "Soluble Fiber", "standard_name": "Fiber",
           "canonical_id": "fiber", "form_id": None, "form_match_status": "n/a"}
    assert not enricher._interaction_rule_applies(rule, enricher._skipped_row_scope_row(row))


@pytest.mark.parametrize("name", ["Vitamin A", "Gamma-Carotene"])
def test_a_name_with_no_form_doesnt_reach_a_rule_scoped_to_the_unspecified_form(pipeline, name):
    # RULE_IQM_VITAMIN_A_PREGNANCY_DOSE scopes "vitamin a (unspecified)". Gamma-carotene is
    # not preformed vitamin A, so a generic match must not read as a printed form here.
    enricher = pipeline[1]
    row = {"name": name, "raw_source_text": name, "standard_name": "Vitamin A",
           "canonical_id": "vitamin_a", "form_id": None, "form_match_status": "n/a"}
    assert enricher._skipped_row_scope_row(row) is row


def test_a_read_form_doesnt_silence_a_fail_open_rule(pipeline):
    # Fail-open rules are silent only for a form the label confirms in a scored match.
    enricher = pipeline[1]
    rule = {"form_scope": ["some other form"], "form_scope_match": "fail_open"}
    row = {"name": "Glucomannan", "raw_source_text": "Glucomannan", "standard_name": "Fiber",
           "canonical_id": "fiber", "form_id": None, "form_match_status": "n/a"}
    assert enricher._interaction_rule_applies(rule, enricher._skipped_row_scope_row(row))


def test_a_form_outside_the_row_identity_is_not_read(pipeline):
    enricher = pipeline[1]
    row = {"name": "Glucomannan", "raw_source_text": "Glucomannan", "standard_name": "Fiber",
           "canonical_id": "vitamin_a", "form_id": None, "form_match_status": "n/a"}
    assert enricher._skipped_row_scope_row(row) is row
