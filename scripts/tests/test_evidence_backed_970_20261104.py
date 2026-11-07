"""970-label Evidence review: true rejections earn nothing and packet drafts stay unsigned."""
import importlib.util
import json
from pathlib import Path

import pytest

from clinical_applicability import assess_clinical_applicability, reviewed_entries

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audits" / "evidence_backed_970_20261104"
NAT = "INGR_N_ACETYL_L_TYROSINE"


def _nat_row(name, form=None):
    row = {"name": name, "canonical_id": "l_tyrosine", "quantity": 350, "unit": "mg",
           "raw_source_path": "ingredientRows[0]"}
    if form:
        row["forms"] = [{"name": form}]
    return row


@pytest.mark.parametrize("name,form", [
    ("N-Acetyl L-Tyrosine", None),
    ("N-Acetyl-L-Tyrosine", None),
    ("N-Acetyl Tyrosine", None),
    ("NALT", None),
    ("L-Tyrosine", "N-Acetyl-L-Tyrosine"),
    ("Tyrosine", "Acetyl-L-Tyrosine"),
])
def test_n_acetyl_tyrosine_is_rejected_on_every_spelling(name, form):
    row = _nat_row(name, form)
    entry = {**reviewed_entries()[NAT], "ingredient": name, "matched_source_row_refs": ["ingredientRows[0]"]}
    result = assess_clinical_applicability({"activeIngredients": [row]}, entry, assess_amount=False)
    assert result["status"] == "not_applicable"
    assert result["reason_code"] == "clinical_form_excluded"


def test_rejection_record_cannot_reach_or_credit_free_tyrosine():
    record = reviewed_entries()[NAT]
    names = {record["standard_name"].lower(), *(alias.lower() for alias in record["aliases"])}
    assert not names & {"tyrosine", "l-tyrosine", "l tyrosine"}
    assert record["effect_direction"] == "null"
    assert not record.get("study_contexts")


def test_rejection_record_says_who_reviewed_it_and_cites_only_what_was_read():
    record = reviewed_entries()[NAT]
    text = json.dumps(record)
    assert "Agent review (Claude)" in record["applicability"]["reason"]
    assert "clinician_approved" not in text and "Dr. Pham" not in text
    cited = {ref["pmid"] for ref in record["references_structured"]}
    assert cited == set(record["published_studies"])
    assert set(record["applicability"]["source_pmids"]) <= cited


def test_packet_drafts_pass_the_authoring_rules_and_carry_no_approval():
    spec = importlib.util.spec_from_file_location("check_packet", AUDIT / "check_packet.py")
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    packets = sorted((AUDIT / "packet").glob("*.json"))
    assert packets
    for path in packets:
        assert check.packet_problems(json.loads(path.read_text(encoding="utf-8"))) == []
        assert "clinician_approved" not in path.read_text(encoding="utf-8")


def test_packet_drafts_stay_outside_the_data_file():
    packeted = {path.stem for path in (AUDIT / "packet").glob("*.json")}
    # The original packet remains unsigned. Only its independently qualified
    # successor may enter production, with unfinished sibling sources retained.
    qualified = {"INGR_L_GLUTAMINE": "30108163", "INGR_L_TYROSINE": "24433977"}
    assert packeted & set(reviewed_entries()) == set(qualified)
    from clinical_applicability import assess_clinical_source_review
    for record_id, pmid in qualified.items():
        record = reviewed_entries()[record_id]
        approved = [c for c in record["study_contexts"] if c["scoring_eligible"]]
        assert len(approved) == 1
        assert approved[0]["source_pmids"] == [pmid]
        assert approved[0]["review_status"] == "clinician_approved"
        assert "Codex" in approved[0]["clinical_review"]["reviewer"]
        assert not assess_clinical_source_review(record)["is_complete"]


def _audit_module(name):
    spec = importlib.util.spec_from_file_location(name, AUDIT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REJECTIONS = _audit_module("records").RECORDS
CORRECTIONS = _audit_module("records").LITERATURE_CORRECTIONS


def _literature_record(canonical):
    payload = json.loads((ROOT / "data" / "literature_evidence_records.json").read_text(encoding="utf-8"))
    return {r["canonical_id"]: r for r in payload["literature_evidence_records"]}[canonical]


@pytest.mark.parametrize("record_id,name,canonical", [
    ("INGR_BUTTERBUR_WHOLE_HERB", "Butterbur Whole Herb Extract", "butterbur"),
    ("INGR_L_ORNITHINE_L_ASPARTATE", "L-Ornithine L-Aspartate", "l_ornithine"),
])
def test_preparation_rejection_refuses_the_row_it_was_written_for(record_id, name, canonical):
    row = {"name": name, "canonical_id": canonical, "quantity": 150, "unit": "mg",
           "raw_source_path": "ingredientRows[0]"}
    entry = {**reviewed_entries()[record_id], "ingredient": name, "matched_source_row_refs": ["ingredientRows[0]"]}
    result = assess_clinical_applicability({"activeIngredients": [row]}, entry, assess_amount=False)
    assert result["status"] == "not_applicable"
    assert result["reason_code"] == "clinical_form_excluded"


@pytest.mark.parametrize("record_id,other_preparations", [
    ("INGR_BUTTERBUR_WHOLE_HERB", {"butterbur", "butterbur extract", "butterbur root extract", "petadolex"}),
    ("INGR_L_ORNITHINE_L_ASPARTATE", {"ornithine", "l-ornithine", "l-ornithine hcl", "l-ornithine hydrochloride"}),
])
def test_preparation_rejection_cannot_reach_a_different_preparation(record_id, other_preparations):
    record = reviewed_entries()[record_id]
    names = {record["standard_name"].lower(), *(alias.lower() for alias in record["aliases"])}
    assert not names & other_preparations


@pytest.mark.parametrize("record", REJECTIONS, ids=lambda record: record["id"])
def test_every_rejection_earns_nothing_and_cites_what_it_read(record):
    stored = reviewed_entries()[record["id"]]
    text = json.dumps(stored)
    assert stored["effect_direction"] == "null"
    assert not stored.get("study_contexts")
    assert "Agent review (Claude)" in stored["applicability"]["reason"]
    assert "not that it was tested and failed" in stored["effect_direction_rationale"]
    assert "clinician_approved" not in text and "Dr. Pham" not in text
    cited = {ref["pmid"] for ref in stored["references_structured"]}
    assert cited == set(stored["published_studies"])
    assert set(stored["applicability"]["source_pmids"]) <= cited


NULL_RESULTS = sorted(c for c, fix in CORRECTIONS.items() if fix.get("result") != "no_qualifying_human_evidence")
NO_QUALIFYING = sorted(c for c, fix in CORRECTIONS.items() if fix.get("result") == "no_qualifying_human_evidence")


def _resolve(canonical):
    from evidence_resolver import _load_literature_evidence, resolve_evidence_for_row
    _load_literature_evidence.cache_clear()
    row = {"canonical_id": canonical, "name": canonical, "raw_source_text": canonical,
           "source_label_name": canonical, "raw_source_path": "activeIngredients[0]",
           "source_section": "activeIngredients"}
    return resolve_evidence_for_row(row, {"activeIngredients": [row], "ingredients_scorable": [row]})


@pytest.mark.parametrize("canonical", NULL_RESULTS)
def test_conflicting_review_closes_without_credit(canonical):
    resolution = _resolve(canonical)
    assert resolution.disposition == "reviewed_null_unfavorable"
    assert resolution.points_eligible is False
    assert not resolution.blocking_reasons


@pytest.mark.parametrize("canonical", NO_QUALIFYING)
def test_no_qualifying_review_closes_without_credit_or_studies(canonical):
    resolution = _resolve(canonical)
    assert resolution.disposition == "no_qualifying_human_evidence"
    assert resolution.points_eligible is False
    assert not resolution.blocking_reasons
    record = _literature_record(canonical)
    assert record["qualifying_human_studies"] == []
    assert record["effect_direction"] is None
    assert CORRECTIONS[canonical]["quotes"][0]["quote"] in record["applicability_decision"]


@pytest.mark.parametrize("canonical", sorted(CORRECTIONS))
def test_literature_correction_is_named_as_agent_review_and_quotes_its_source(canonical):
    record = _literature_record(canonical)
    decision = record["applicability_decision"]
    assert decision.startswith(("Conflicting human evidence", "Finished review with no qualifying study"))
    assert "not clinician reviewed" in decision
    assert "no clinician approval" in record["verification_provenance"]["verified_by"]
    assert "clinician_approved" not in json.dumps(record) and "Dr. Pham" not in json.dumps(record)
    # These words reroute a decision to "applicability unestablished", which doesn't finish a label.
    assert not any(word in decision.lower() for word in ("applicability unestablished", "prohibited", "blocked"))


@pytest.mark.parametrize("canonical", NULL_RESULTS)
def test_conflicting_review_keeps_the_studies_it_read(canonical):
    record = _literature_record(canonical)
    for study in CORRECTIONS[canonical]["studies"]:
        row = next(row for row in record["qualifying_human_studies"] if row["pmid"] == study["pmid"])
        assert row["verification_provenance"]["abstract_evidence_quote"] == study["quote"]


def test_lysine_rationale_names_the_positive_trial_and_the_review_it_conflicts_with():
    decision = _literature_record("l_lysine")["applicability_decision"]
    assert "PMID 3115841" in decision and "PMID 26252373" in decision
    assert "We failed to find any evidence of efficacy for lysine" in decision


@pytest.mark.parametrize("canonical,positive,null_quote", [
    ("l_leucine", ["32230954", "37923932"],
     "Leucine-isolated supplementation did not improve muscle mass and strength in elderly."),
    ("lecithin", ["21490917", "29310653"],
     "Evidence from randomized trials does not support the use of lecithin in the treatment of patients with dementia."),
    ("siberian_ginseng", ["21793317", "15207399"], "Overall efficacy was not demonstrated."),
    ("d_ribose", ["35644694", "14607200", "1354276"],
     "does not affect anaerobic exercise capacity or metabolic markers in trained subjects"),
    ("cayenne_pepper", ["36938807", "24246368"], "is not effective at inducing thermogenesis"),
    ("gotu_kola", ["11666126", "18191355"], "there is not strong evidence to support the use of C. asiatica"),
    ("feverfew", ["16232154", "41422534"], "MIG-99 failed to show a significant migraine prophylactic effect in general."),
    ("theobromine", ["23595874", "37615657"], "TB was not effective on HDL-CH"),
    ("hawthorn", ["12798455", "18254076"], "Hawthorn provides no symptomatic or functional benefit"),
    ("cla", ["37671495", "17490954"], "data from high-quality studies failed to show"),
    ("d_beta_hydroxybutyrate_bhb", ["39575959", "42063954"], "did not improve high-intensity cycling"),
    ("uva_ursi_leaf", ["34111592"], "We found no evidence of an effect of either intervention"),
    ("coffeeberry", ["33498314", "39064791"], "does not have a beneficial effect on mood"),
    ("gamma_linolenic_acid", ["21328257", "31701699"], "lack effect on eczema"),
])
def test_conflicting_rationale_names_both_sides(canonical, positive, null_quote):
    decision = _literature_record(canonical)["applicability_decision"]
    assert null_quote in decision
    assert all(pmid in decision for pmid in positive)


@pytest.mark.parametrize("canonical,tested_elsewhere", [
    ("african_mango", ["19254366", "36364907", "31855111"]),
    ("zeaxanthin", ["28079755", "23644932"]),
    ("goldenseal", ["17495878", "32683037"]),
    ("agmatine", ["20447305"]),
    ("lignans", ["17987126", "24606716", "19352068"]),
    ("coffee_fruit", ["23312069", "37299382"]),
])
def test_no_qualifying_decision_names_the_human_research_it_read(canonical, tested_elsewhere):
    decision = _literature_record(canonical)["applicability_decision"]
    assert all(pmid in decision for pmid in tested_elsewhere)


@pytest.mark.parametrize("canonical", NO_QUALIFYING)
def test_no_qualifying_decision_does_not_claim_the_preparation_failed(canonical):
    assert "does not say the preparation was tested and failed" in _literature_record(canonical)["applicability_decision"]


@pytest.mark.parametrize("canonical", NO_QUALIFYING)
def test_no_qualifying_decision_keeps_the_opening_words_the_sentence_keys_on(canonical):
    assert _literature_record(canonical)["applicability_decision"].startswith("Finished review with no qualifying study")
