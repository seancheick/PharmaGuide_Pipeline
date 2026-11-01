"""Blend-owner reviews do not complete unresolved individual active reviews.

Each product scored Evidence 0 with the pillar saying `not_yet_reviewed`:
its purpose-owning identity was a proprietary blend (or branded blend) that
nobody had searched. Sean asked on 2026-09-28 for all of them to be reviewed
(scripts/audits/rr_correctness_20260928/CALIBRATION_PACKET.md item 3). A blend
with no published human trial gets a reproducible search record that
concludes so; a branded blend with trials (Tesnor, Sytrinol) gets its reviewed
clinical entry. Empty automated verification stamps are not finished source searches. Such
individual owners remain pending independently of the blend review.
"""
import json
import logging
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
PRODUCTS = ["1179", "14168", "315089", "243271", "282638", "299755", "54775", "275464"]

# 1179 (Ravage) also carries L-phenylalanine as a primary active. Its literature record's only
# citation, PMID 37629744, is a review of depression treatment in Parkinson's disease, not a
# phenylalanine trial (literature records review 2026-10-20), so that review is genuinely open
# again. Methionine also has only an empty automated verification stamp; neither
# unfinished individual review is completed by the blend owners.
# Whole turmeric cannot inherit Curcumin trials from an INGR_ key suffix.
_REVIEW_PRODUCTS = [pid for pid in PRODUCTS if pid not in {"1179", "243271", "282638", "299755"}]


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


def test_ravage_retains_each_unfinished_individual_review(enriched):
    from evidence_resolver import resolve_product_evidence
    from scoring_v4.scored_artifact import build_scored_artifact

    resolution = resolve_product_evidence(enriched["1179"], owner_scoped=True)
    open_owners = [
        (r.canonical_id, r.blocking_reasons) for r in resolution.resolutions
        if r.disposition == "literature_resolution_required"
    ]
    assert open_owners == [("methionine", ["literature_verification_pending"]),
                           ("l_phenylalanine", ["literature_verification_pending"])]
    _assert_empty_automated_source_is_unfinished("methionine")
    evidence = build_scored_artifact(enriched["1179"])["quality_pillars_v4"]["evidence"]
    assert evidence["display_state"] == "not_yet_reviewed"

    # The source-verified Anabolic Muscle Primer lists yohimbe bark. Its
    # absence must never hide the existing high-risk finding or lend a dose.
    artifact = build_scored_artifact(enriched["1179"])
    assert set(artifact["_v4_safety_gate"]["safety_signals"]) >= {
        "B0_HIGH_RISK_SUBSTANCE", "STIMULANT_UNDISCLOSED_BLEND",
    }
    from scoring_input_contract import get_evidence_subject_rows
    yohimbe = next(row for row in get_evidence_subject_rows(enriched["1179"])
                   if row.get("canonical_id") == "yohimbe")
    assert not yohimbe.get("quantity")


def test_tesnor_and_sytrinol_resolve_to_their_reviewed_trials(enriched):
    from evidence_resolver import resolve_product_evidence

    for pid, canonical in (("315089", "tesnor_pomegranate_cocoa_blend"), ("54775", "sytrinol")):
        resolution = resolve_product_evidence(enriched[pid], owner_scoped=True)
        owner = next(r for r in resolution.resolutions if r.canonical_id == canonical)
        assert "backed_clinical_studies" in owner.matched_owners


@pytest.mark.parametrize("pid,canonical", [
    ("1179", "cinnamon"),
    ("243271", "turmeric"),
])
def test_a_lent_blend_total_is_not_a_member_dose(enriched, pid, canonical):
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
    assert resolution.applicability_status == (
        "unverified_literature_record" if canonical == "turmeric"
        else "applicability_unestablished"
    )

    # Cinnamon also retains its reviewed source-integrity hold; a lent mass
    # cannot clear it. Dose
    # still refuses to borrow the blend total as this member's exposure.
    from dose_assessment import positive_clinical_benchmark
    assert positive_clinical_benchmark(enriched[pid], row) is None


def test_golden_milk_whole_pepper_uses_the_absorption_aid_owner(enriched):
    """An undosed active-panel aid stays visible, while the established
    turmeric pairing resolves its Evidence role without inventing an efficacy
    trial for piperine."""
    from evidence_resolver import resolve_product_evidence

    product = enriched["243271"]
    assert product["absorption_enhancer_paired"] is True
    resolution = resolve_product_evidence(product, owner_scoped=True)
    # The retained raw row declares undosed organic Black Pepper, no extract
    # or isolated marker. Its existing absorption-aid role stays distinct.
    pepper = next(r for r in resolution.resolutions if r.canonical_id == "black_pepper")
    assert not any(r.canonical_id == "piperine" for r in resolution.resolutions)
    assert pepper.disposition == "not_efficacy_relevant"
    assert pepper.matched_owners == ["absorption_enhancer_role"]


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



@pytest.mark.parametrize("name,is_additive", [
    ("Cinnamon Extract", False),
    ("Natural Cinnamon Flavoring", True),
    ("Cinnamon (Natural Flavoring)", True),
    ("Natural Orange Flavor", True),
])
def test_printed_blend_member_function_is_not_a_generated_identity_alias(name, is_additive):
    """Identity variations may find a parent, but cannot invent flavor use."""
    from enhanced_normalizer import EnhancedDSLDNormalizer

    raw = json.loads((FIXTURES / "evidence_review_1179_raw.json").read_text())
    raw["ingredientRows"][10]["forms"][0]["name"] = name
    cleaned = EnhancedDSLDNormalizer().normalize_product(raw)

    def descendants(rows):
        for row in rows:
            yield row
            yield from descendants(row.get("nestedIngredients") or [])

    row = next(r for r in descendants(cleaned["activeIngredients"])
               if r.get("raw_source_path") == "ingredientRows[10].forms[0]")
    assert row.get("isAdditive", False) is is_additive
    assert row["source_section"] == "active"
    assert row["quantity"] == 0
    assert row["parentBlendMass"] == 3.2
    if not is_additive:
        assert row["canonical_id"] == "cinnamon"
        assert row["score_eligible_by_cleaner"] is True


@pytest.mark.parametrize("quantity", [None, 1, 500])
def test_active_cinnamon_function_does_not_depend_on_amount(quantity):
    from enhanced_normalizer import EnhancedDSLDNormalizer

    raw = json.loads((FIXTURES / "evidence_review_1179_raw.json").read_text())
    leaf = dict(raw["ingredientRows"][10]["forms"][0])
    leaf.update({"forms": [], "nestedRows": [], "quantity": [] if quantity is None else [{
        "quantity": quantity, "unit": "mg", "servingSizeOrder": 1,
        "servingSizeQuantity": 26, "servingSizeUnit": "Gram(s)",
    }]})
    raw["ingredientRows"] = [leaf]
    row = EnhancedDSLDNormalizer().normalize_product(raw)["activeIngredients"][0]
    assert row["canonical_id"] == "cinnamon"
    assert row["source_section"] == "active"
    assert row.get("isAdditive", False) is False


def test_tesnor_notes_distinguish_primary_symptoms_from_secondary_biomarkers():
    data = json.loads((Path(__file__).parents[1] / "data" / "backed_clinical_studies.json").read_text())
    from data_batch import entries
    record = next(r for r in entries(data).values() if isinstance(r, dict) and r.get("id") == "BRAND_TESNOR")
    notes = record["notes"]
    assert "not clinical outcomes" not in notes
    assert "symptom score was primary" in notes
    assert "hormone levels and strength were secondary" in notes
    assert "outside this blend cannot borrow" in notes


def test_golden_milk_whole_turmeric_does_not_inherit_curcumin_identity(enriched):
    from evidence_resolver import resolve_product_evidence
    from scoring_v4.scored_artifact import build_scored_artifact

    product = enriched["243271"]
    resolution = resolve_product_evidence(product, owner_scoped=True)
    unresolved = [r.canonical_id for r in resolution.resolutions
                  if r.disposition == "literature_resolution_required"]
    assert unresolved == ["turmeric", "cardamom"]
    _assert_empty_automated_source_is_unfinished("cardamom")
    turmeric = next(r for r in resolution.resolutions if r.canonical_id == "turmeric")
    assert "backed_clinical_studies" not in turmeric.matched_owners
    assert not resolution.is_assessment_complete
    evidence = build_scored_artifact(product)["quality_pillars_v4"]["evidence"]
    assert evidence["display_state"] == "not_yet_reviewed"


def _assert_empty_automated_source_is_unfinished(canonical):
    data = json.loads((Path(__file__).parents[1] / "data" / "literature_evidence_records.json").read_text())
    entry = next(row for row in data["literature_evidence_records"] if row["canonical_id"] == canonical)
    assert entry["qualifying_human_studies"] == []
    assert entry["verification_result"] == "authoritative_pubmed_verified"
    assert entry["verification_provenance"]["verified_by"] == "scripts/api_audit/verify_literature_records.py"


def test_finished_blend_does_not_finish_empty_alfalfa_source_review(enriched):
    from evidence_resolver import resolve_product_evidence
    from scoring_v4.scored_artifact import build_scored_artifact

    # The title names no blend member ("Green" of "Green Superfood" is not the
    # Green Juice Blend), so every member is a subject: red cabbage's empty
    # automated review is unfinished too.
    for canonical in ("alfalfa", "cabbage_extract"):
        _assert_empty_automated_source_is_unfinished(canonical)
    product = enriched["282638"]
    resolution = resolve_product_evidence(product, owner_scoped=True)
    assert not resolution.is_assessment_complete
    pending = [(row.canonical_id, row.blocking_reasons) for row in resolution.resolutions
               if row.disposition == "literature_resolution_required"]
    assert pending == [("alfalfa", ["literature_verification_pending"]),
                       ("cabbage_extract", ["literature_verification_pending"])]
    evidence = build_scored_artifact(product)["quality_pillars_v4"]["evidence"]
    assert evidence["display_state"] == "not_yet_reviewed"


def test_flaxseed_blend_uses_independent_verified_sources_without_clearing_history(enriched):
    from evidence_resolver import resolve_product_evidence
    from scoring_v4.scored_artifact import build_scored_artifact
    resolution = resolve_product_evidence(enriched["299755"], owner_scoped=True)
    flax = next(row for row in resolution.resolutions if row.canonical_id == "flaxseed")
    # Independently verified literature cannot invent an accepted clinical
    # context for the exact blend preparation, population and outcome.
    assert flax.disposition == "research_present_applicability_unestablished"
    # Completing source review does not establish affirmative credit for this blend row.
    assert flax.points_eligible is False
    data = json.loads((Path(__file__).parents[1] / "data/literature_evidence_records.json").read_text())
    record = next(row for row in data["literature_evidence_records"] if row["canonical_id"] == "flaxseed")
    active_pmids = {str(source["pmid"]) for source in record["qualifying_human_studies"]}
    assert active_pmids == {"24126178", "26071633"}
    assert "unread erratum26525908" in record["notes"]
    assert "retired from qualifying_human_studies" in record["notes"]
    # Verified research remains distinct from applicable positive credit.
    evidence = build_scored_artifact(enriched["299755"])["quality_pillars_v4"]["evidence"]
    assert evidence["display_state"] == "applicability_unestablished"
