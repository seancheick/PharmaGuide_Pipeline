"""Every evidence owner of these 8 labels has a finished literature review.

Each product scored Evidence 0 with the pillar saying `not_yet_reviewed`:
its purpose-owning identity was a proprietary blend (or branded blend) that
nobody had searched. Sean asked on 2026-09-28 for all of them to be reviewed
(scripts/audits/rr_correctness_20260928/CALIBRATION_PACKET.md item 3). A blend
with no published human trial gets a reproducible search record that
concludes so; a branded blend with trials (Tesnor, Sytrinol) gets its reviewed
clinical entry. The answer then depends on the evidence, never on a missing
review.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
PRODUCTS = ["1179", "14168", "315089", "243271", "282638", "299755", "54775", "275464"]

_REVIEW_PRODUCTS = PRODUCTS


@pytest.fixture(scope="module")
def enriched():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    out = {}
    for pid in PRODUCTS:
        raw = json.loads((FIXTURES / f"evidence_review_{pid}_raw.json").read_text())
        out[pid], _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return out


@pytest.mark.parametrize("pid", _REVIEW_PRODUCTS)
def test_the_owner_review_is_finished(enriched, pid):
    from evidence_resolver import resolve_product_evidence

    resolution = resolve_product_evidence(enriched[pid], owner_scoped=True)
    assert resolution.is_assessment_complete, [
        (r.canonical_id, r.disposition) for r in resolution.resolutions
    ]


@pytest.mark.parametrize("pid", _REVIEW_PRODUCTS)
def test_the_evidence_pillar_no_longer_says_not_yet_reviewed(enriched, pid):
    from scoring_v4.scored_artifact import build_scored_artifact

    evidence = build_scored_artifact(enriched[pid])["quality_pillars_v4"]["evidence"]
    assert evidence["display_state"] != "not_yet_reviewed"


def test_tesnor_and_sytrinol_resolve_to_their_reviewed_trials(enriched):
    from evidence_resolver import resolve_product_evidence

    for pid, canonical in (("315089", "tesnor_pomegranate_cocoa_blend"), ("54775", "sytrinol")):
        resolution = resolve_product_evidence(enriched[pid], owner_scoped=True)
        owner = next(r for r in resolution.resolutions if r.canonical_id == canonical)
        assert "backed_clinical_studies" in owner.matched_owners


@pytest.mark.parametrize("pid,canonical", [
    pytest.param("1179", "cinnamon", marks=pytest.mark.xfail(strict=True, reason=(
        "Ravage's undosed 'Cinnamon Extract' blend member is read as the other-ingredients "
        "flavour (is_excipient): active or carrier is a per-item purpose decision, lane 2B"
    ))),
    ("243271", "turmeric"),
])
def test_a_lent_blend_total_is_no_evidence_dose(enriched, pid, canonical):
    """Ravage's cinnamon and Golden Milk's turmeric carry only their blend's
    total (3.2 g), lent to them as a blend-level anchor. The Evidence dose map
    read that total as their own dose, so the trials looked applicable. Their
    own amounts are not on the label (RR-04: no consumer reads a lent mass as
    an individual dose)."""
    from evidence_resolver import resolve_evidence_for_row
    from scoring_input_contract import get_evidence_subject_rows

    row = next(
        r for r in get_evidence_subject_rows(enriched[pid])
        if r.get("canonical_id") == canonical
    )
    resolution = resolve_evidence_for_row(row, enriched[pid])
    assert resolution.applicability_status == "dose_undisclosed"


def test_golden_milk_piperine_uses_the_absorption_aid_owner(enriched):
    """An undosed active-panel aid stays visible, while the established
    turmeric pairing resolves its Evidence role without inventing an efficacy
    trial for piperine."""
    from evidence_resolver import resolve_product_evidence

    product = enriched["243271"]
    assert product["absorption_enhancer_paired"] is True
    resolution = resolve_product_evidence(product, owner_scoped=True)
    piperine = next(r for r in resolution.resolutions if r.canonical_id == "piperine")
    assert piperine.disposition == "not_efficacy_relevant"
    assert piperine.matched_owners == ["absorption_enhancer_role"]


@pytest.fixture(scope="module")
def multivitamins():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    out = {}
    for pid in ("200362", "15923"):
        raw = json.loads((FIXTURES / f"absorption_pairing_{pid}_raw.json").read_text())
        out[pid], _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return out


@pytest.mark.parametrize("pid", ["200362", "15923"])
def test_a_nutrient_listed_as_an_enhancer_keeps_its_own_evidence(multivitamins, pid):
    """absorption_enhancers.json also lists nutrients (vitamin D for calcium,
    vitamin C and A for iron). They are actives in their own right: only an
    aid-role entry (non_scorable_when_sub_threshold: piperine) may resolve a
    label row as a paired absorption aid."""
    from evidence_resolver import resolve_product_evidence

    product = multivitamins[pid]
    assert not [
        row.get("name") for row in product["ingredient_quality_data"]["ingredients"]
        if row.get("recognition_type") == "paired_absorption_enhancer"
    ]
    resolution = resolve_product_evidence(product, owner_scoped=True)
    assert not [
        r.canonical_id for r in resolution.resolutions
        if r.applicability_status == "paired_absorption_aid"
    ]


def test_nutrient_enhancers_pair_only_through_primary_actives(multivitamins):
    """15923 (vitamins A/C/D with calcium and iron on 06b00bb3: no absorption
    bonus) must not gain the bonus from quality-row canonical names."""
    assert multivitamins["15923"]["absorption_data"]["qualifies_for_bonus"] is False


@pytest.mark.parametrize("quantity,paired_aid", [(0.0, True), (20.0, False)])
def test_only_an_undosed_aid_takes_the_paired_aid_role(quantity, paired_aid):
    """absorption_enhancers.json: piperine <= 10 mg is an aid (demoted by the
    threshold rule), above 10 mg a therapeutic active. The pairing may settle
    the role only when the label gives no amount."""
    from enrich_supplements_v3 import SupplementEnricherV3

    turmeric = {"name": "Turmeric", "standard_name": "Turmeric", "canonical_id": "turmeric",
                "source_section": "active", "quantity": 0.0, "unit": "NP",
                "raw_source_path": "ingredientRows[0].nestedRows[0]"}
    piperine = {"name": "Black Pepper", "standard_name": "Piperine", "canonical_id": "piperine",
                "source_section": "active", "quantity": quantity, "unit": "mg",
                "raw_source_path": "ingredientRows[0].nestedRows[1]"}
    product = {"activeIngredients": [], "ingredient_quality_data": {"ingredients": [turmeric, piperine]}}
    data = SupplementEnricherV3()._collect_absorption_data(product)
    assert data["qualifies_for_bonus"] is True
    assert (piperine.get("recognition_type") == "paired_absorption_enhancer") is paired_aid

