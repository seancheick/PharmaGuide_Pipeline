"""A brand's clinical record reaches a label only when the label names the brand.

`enrich_supplements_v3._brand_mentioned` confirms an alias-only BRAND_ match in the
product text, using the entry's curated `brand_tokens` when present; aliases stay the
discovery surface and may be generic. BioPerine and Zynamite had no brand_tokens, so
a generic alias ("piperine", "mangiferin") confirmed itself, and HMB and OptiFerrin
were ingredient evidence filed as brands: 81 raw labels in the corpus census of
2026-09-29 took a brand's Evidence floor without naming a brand. Receipts:
scripts/audits/rr_correctness_20260928/research.md.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
DATA = Path(__file__).resolve().parents[1] / "data"


def _entries():
    rows = json.loads((DATA / "backed_clinical_studies.json").read_text())["backed_clinical_studies"]
    return {e["id"]: e for e in rows}


def test_brands_with_generic_aliases_confirm_on_their_brand_token():
    entries = _entries()
    assert entries["BRAND_ZYNAMITE"]["brand_tokens"] == ["zynamite"]
    assert entries["BRAND_SUNTHEANINE"]["brand_tokens"] == ["suntheanine"]


def test_ingredient_evidence_is_filed_as_ingredient_evidence():
    entries = _entries()
    assert "BRAND_HMB" not in entries and "BRAND_OPTIFERRIN" not in entries
    hmb, lactoferrin = entries["INGR_HMB"], entries["INGR_LACTOFERRIN"]
    assert lactoferrin["evidence_level"] == "ingredient-human"
    # Dr. Pham, 2026-10-28: HMB's restrictive conclusion is a completed
    # no-credit decision on the reference-only path, still under its INGR_ id.
    assert hmb["evidence_level"] == hmb["study_type"] == "reference"
    assert {"hmb", "calcium hmb"} <= set(hmb["aliases"])
    assert "lactoferrin" in lactoferrin["aliases"]
    assert (lactoferrin["min_clinical_dose"], lactoferrin["dose_unit"]) == (200, "mg")


def test_bioperine_is_an_absorption_aid_not_an_efficacy_record():
    """BRAND_BIOPERINE (removed 2026-09-29, Sean) filed pharmacokinetic evidence
    (piperine raising curcumin exposure) as Energy / Healthy Aging efficacy. The
    absorption-aid role stays with its owner, absorption_enhancers.json."""
    assert "BRAND_BIOPERINE" not in _entries()
    enhancers = json.loads((DATA / "absorption_enhancers.json").read_text())["absorption_enhancers"]
    pepper = next(e for e in enhancers if e["id"] == "ENHANCER_BLACK_PEPPER")
    assert "bioperine" in pepper["aliases"]


def _matches(pid):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    raw = json.loads((FIXTURES / f"brand_generic_{pid}_raw.json").read_text())
    enriched, _ = SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    evidence = enriched.get("evidence_data") or {}
    accepted = {m.get("id") for m in evidence.get("clinical_matches") or []}
    rejected = {m.get("id"): m.get("reason_code") for m in evidence.get("rejected_clinical_matches") or []}
    return accepted, rejected


# Discovery remains separate from eligibility: completed reference-only and
# held-source records retain their exact rejection reason. Routing is asserted
# without restoring affirmative credit to the held lactoferrin source.
@pytest.mark.parametrize("pid, absent, present, reference_only", [
    ("233404", "BRAND_ZYNAMITE", None, False),          # mangiferin, Zynamite not named
    ("18416", "BRAND_HMB", "INGR_HMB", True),           # plain HMB
    ("267894", "BRAND_OPTIFERRIN", "INGR_LACTOFERRIN", False),  # plain lactoferrin
    ("182824", "BRAND_BIOPERINE", None, False),        # "Curcumin 500 with Bioperine": no efficacy record
    ("214982", None, "BRAND_SUNTHEANINE", True),       # names Suntheanine
])
def test_real_labels_reach_the_right_record(pid, absent, present, reference_only):
    accepted, rejected = _matches(pid)
    if absent:
        assert absent not in accepted and absent not in rejected
    if present and reference_only:
        assert present not in accepted
        assert rejected.get(present) == "reference_only_clinical_record"
    elif present == "INGR_LACTOFERRIN":
        from clinical_applicability import assess_clinical_source_review
        assert present not in accepted
        assert rejected.get(present) == "clinical_sources_ineligible"
        assert assess_clinical_source_review({"id": present})["is_complete"] is False
    elif present:
        assert present in accepted



@pytest.mark.parametrize('record_id,canonical,generic,branded', [
    ('BRAND_UCII', 'collagen_type_ii', 'Undenatured Collagen II', 'UC-II Undenatured Type II Collagen'),
    ('BRAND_MAGTEIN', 'magnesium', 'Magnesium L-Threonate', 'Magtein Magnesium L-Threonate'),
])
def test_generic_identity_or_another_row_cannot_supply_exact_brand_scope(record_id, canonical, generic, branded):
    from copy import deepcopy
    from clinical_applicability import assess_clinical_applicability
    from test_green_tea_evidence_identity import _source_product
    product = _source_product(generic)
    row = product['activeIngredients'][0]
    row.update(name=generic, raw_source_text=generic, standardName=generic, canonical_id=canonical,
               ingredientGroup=canonical, matched_form=branded, forms=[])
    row['raw_taxonomy'].update(category='non-nutrient/non-botanical', ingredientGroup=canonical, forms=[])
    entry = {'id': record_id, 'matched_source_row_refs': ['ingredientRows[0]'],
             'matched_canonical_ids': [canonical]}
    decision = assess_clinical_applicability(product, entry, assess_amount=False)
    assert decision['status'] == 'not_applicable'
    assert decision['reason_code'] == 'clinical_form_mismatch'
    sibling = deepcopy(row)
    sibling.update(name=branded, raw_source_text=branded, raw_source_path='ingredientRows[1]')
    product['activeIngredients'].append(sibling)
    assert assess_clinical_applicability(product, entry, assess_amount=False)['reason_code'] == 'clinical_form_mismatch'
    exact = {**entry, 'matched_source_row_refs': ['ingredientRows[1]']}
    assert assess_clinical_applicability(product, exact, assess_amount=False)['status'] == 'applicable'
