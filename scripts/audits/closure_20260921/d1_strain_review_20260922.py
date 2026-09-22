#!/usr/bin/env python3
"""Closure D1: terminal literature review of every product-holding probiotic stub.

Scope: the 90 registry identities whose label strains read
``strain_identity_or_review_unresolved`` on the 2026-09-21 corpus, plus the one
remaining unreviewed stub with no product today (Ll-23, applied with ``--only``).
Two of the 90 (Bi-07, BB-12) carry a suspended clinician sign-off and stay under
the clinician gate; this script does not touch them.

For the other 89, every candidate human record from a designation-and-species
PubMed search was read (efetch XML, which keeps the italic genus/species tokens
that the 2026-09-13 plain-text read lost). The per-strain search, screened
PMIDs and classification are in ``D1_STRAIN_REVIEW_20260922.json`` (the basis
every registry record cites). Each strain ends in one of two states:

* ``exact_strain_contexts_recorded``: a placebo- or vehicle-controlled trial of
  the strain alone exists and is recorded below as a study context.
  Uncontrolled or no-placebo single-strain studies are listed, not scored
  (the 2026-09-14 convention).
* ``no_qualifying_human_evidence`` with a reason: combination-only research
  (a combination never credits one strain), uncontrolled research only, no
  human research, or a species conflict in the sources.

Outcome kinds follow the registry's existing conventions (lipids, immune and
microbiota markers are surrogates; symptoms, infections, quality of life and
body-fat change are patient-important). Doses are recorded only when the
abstract states a per-day amount with its exponent. Nothing here flips
``dr_pham_signoff``; the approvals are the delegated research review named in
``REVIEWER``, not a clinician sign-off.

Agent-authored legacy summaries (BS01, LP01, M-63, the four DS-01 members) are
retired into the one owner: study contexts, or for DS-01 the whole-formula
record ``FORMULA_SEED_DS01`` in backed_clinical_studies.json.

    python3 scripts/audits/closure_20260921/d1_strain_review_20260922.py          # dry run
    python3 scripts/audits/closure_20260921/d1_strain_review_20260922.py --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

REG = ROOT / "scripts/data/clinically_relevant_strains.json"
BASIS_REL = "scripts/audits/closure_20260921/D1_STRAIN_REVIEW_20260922.json"
BASIS = ROOT / BASIS_REL
REVIEWED_ON = "2026-09-22"
REVIEWER = ("Claude Opus 5 research review (closure D1, 2026-09-22), delegated by Sean B "
            "(engineering owner) to resolve reviews from established doctrine; not a clinician sign-off")
CLINICIAN_GATED = {"STRAIN_LACTIS_BI07", "STRAIN_LACTIS_BB12"}
RETIRE_LEGACY = {"STRAIN_LACTIS_BS01", "STRAIN_PLANTARUM_LP01", "STRAIN_INFANTIS_M63",
                 "STRAIN_BREVE_SD_BR3_IT", "STRAIN_PLANTARUM_SD_LP1_IT",
                 "STRAIN_SALIVARIUS_SD_LS1_IT", "STRAIN_PLANTARUM_SD_LPLDL_UK"}

PI, SU = "patient_important", "surrogate"


def ctx(context_id, pmids, *, owner, age, population, purpose, condition, outcomes, family,
        limitations, design, n, blinding, tier, values=(), dose_status="extraction_pending",
        dose_pmid=None, duration=None, duration_basis=None, forms=(), co_therapies=(),
        registration=None, comparator="placebo", funding="unreported", measurement_type="viable_count"):
    dose = {
        "basis": "discrete_daily_arms" if values else "unresolved",
        "unit": "spores" if measurement_type == "spores" else "CFU",
        "values": list(values),
        "dosage_forms": list(forms),
        "duration_days": duration,
        "co_therapies": list(co_therapies),
        "dose_status": dose_status,
        "dose_basis": "per_strain_daily",
        "duration_basis": duration_basis or ("fixed_protocol" if duration else "not_recorded"),
    }
    if measurement_type != "viable_count":
        dose["measurement_type"] = measurement_type
    if dose_status == "verified":
        dose["source_provenance"] = {"pmid": dose_pmid or pmids[0],
                                     "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{dose_pmid or pmids[0]}/",
                                     "location": "abstract"}
    outs = []
    for name, hier, kind, direction, *role in outcomes:
        row = {"name": name, "hierarchy": hier, "kind": kind, "direction": direction}
        if role:
            row["outcome_role"] = role[0]
        outs.append(row)
    return owner, {
        "context_id": context_id, "source_pmids": list(pmids), "identity_scope": "exact_strain",
        "components": [owner], "population": {"age_group": age, "description": population},
        "purpose": purpose, "condition": condition, "dose": dose, "outcomes": outs,
        "trial_family": family, "limitations": list(limitations),
        "review_status": "clinician_approved", "study_design": design, "sample_size": n,
        "blinding": blinding, "funding": funding, "source_tier": tier, "trial_registration": registration,
        "comparator": comparator, "authored_on": REVIEWED_ON,
        "authoring_method": "PubMed title/abstract read (efetch XML); closure D1 designation-and-species search",
        "context_schema_version": "1.1.0", "evidence_role": "direct_rct",
        "component_registration_status": "fully_registered", "scoring_eligible": True,
    }


LA14, LR32, LS33, BI26 = ("STRAIN_ACIDOPHILUS_LA14", "STRAIN_RHAMNOSUS_LR32",
                          "STRAIN_SALIVARIUS_LS33", "STRAIN_INFANTIS_BI26")
R0011, N30242, SD5865, UALA01 = ("STRAIN_RHAMNOSUS_R0011", "STRAIN_REUTERI_NCIMB30242",
                                 "STRAIN_REUTERI_SD5865", "STRAIN_ACIDOPHILUS_UALA01")
CRL1505, CU1, I3799, B420 = ("STRAIN_RHAMNOSUS_CRL1505", "STRAIN_SUBTILIS_CU1",
                             "STRAIN_BOULARDII_I3799", "STRAIN_LACTIS_B420")
G91, BS01, M63 = "STRAIN_BIFIDUM_G91", "STRAIN_LACTIS_BS01", "STRAIN_INFANTIS_M63"

CONTEXTS = [
    ctx("la14_oral_cholera_vaccine_response_18422632", ["18422632"], owner=LA14, age="adult",
        population="83 healthy adults aged 18-62 randomized across seven single-strain arms and placebo; oral cholera vaccine on days 7 and 14",
        purpose="challenge", condition="oral_cholera_vaccine_humoral_response", duration=21,
        co_therapies=["oral cholera vaccine (challenge)"], comparator="maltodextrin placebo",
        outcomes=[("specific_serum_igg_response", "unresolved", SU, "positive"),
                  ("specific_salivary_iga", "unresolved", SU, "null"),
                  ("overall_vaccination_response", "unresolved", SU, "null")],
        family="seven_strain_cholera_vaccine_18422632", design="rct", n=83, blinding="double", tier="D",
        limitations=["Pilot trial: 83 participants across seven strain arms and placebo, so each arm is small.",
                     "Serum immunoglobulin responses are immune surrogates; overall vaccination response was not influenced.",
                     "The abstract states 2 x 10^10 CFU without an explicit per-day basis."]),
    ctx("lr32_denture_oral_candida_cheese_28346730", ["28346730"], owner=LR32, age="adult",
        population="60 complete-denture wearers harboring oral Candida randomized to NCFM cheese, Lr-32 cheese or control cheese for 8 weeks",
        purpose="prevention", condition="oral_candida_colonization_denture_wearers", duration=56, forms=["cheese"],
        comparator="control cheese without probiotic",
        outcomes=[("oral_candida_levels", "unresolved", SU, "positive", "within_group_change")],
        family="denture_candida_cheese_28346730", design="rct", n=60, blinding="unreported", tier="D",
        limitations=["Oral Candida counts are a colonization surrogate, not clinical candidiasis.",
                     "The abstract reports within-group reductions (both probiotic cheeses, not control); no between-group estimate.",
                     "Dose not reported in the abstract."]),
    ctx("ls33_obese_adolescents_metabolic_markers_22695039", ["22695039", "23510724"], owner=LS33, age="child",
        population="50 adolescents with obesity randomized to Ls-33 or placebo daily for 12 weeks",
        purpose="treatment", condition="adolescent_obesity_inflammation_and_metabolic_markers", duration=84,
        outcomes=[("inflammatory_biomarkers", "unresolved", SU, "null"),
                  ("metabolic_syndrome_parameters", "unresolved", SU, "null"),
                  ("anthropometric_measures", "unresolved", SU, "null"),
                  ("fecal_bacteroides_to_firmicutes_ratios", "unresolved", SU, "positive")],
        family="ls33_obese_adolescents_nct01020617", design="rct", n=50, blinding="double", tier="D",
        registration="NCT01020617",
        limitations=["No difference from placebo in inflammatory, metabolic or anthropometric markers.",
                     "The retrieved abstract lost the daily dose exponent ('10 CFU').",
                     "23510724 is an exploratory fecal-microbiota report of the same trial."]),
    ctx("bi26_underweight_infants_growth_42137872", ["42137872"], owner=BI26, age="infant",
        population="40 underweight infants (weight-for-age z below -2) aged 30-120 days in Pakistan; Bi-26 or placebo daily for 28 days, follow-up to day 90",
        purpose="treatment", condition="infant_undernutrition_growth", duration=28,
        outcomes=[("weight_for_age_z_change_day_56", "primary", PI, "null"),
                  ("weight_gain", "secondary", PI, "null"),
                  ("fecal_b_infantis_levels", "secondary", SU, "positive"),
                  ("adverse_events", "secondary", PI, "positive")],
        family="bi26_pakistan_underweight_nct05952076", design="rct", n=40, blinding="double", tier="D",
        registration="NCT05952076",
        limitations=["Terminated early: 40 of a planned 396 infants, so the trial is underpowered for growth.",
                     "The primary endpoint did not differ from placebo."]),
    ctx("r0011_chronic_rhinosinusitis_19201289", ["19201289"], owner=R0011, age="adult",
        population="77 adults with chronic inflammatory rhinosinusitis; R0011 or placebo for 4 weeks as adjunctive treatment, assessed at 4 and 8 weeks",
        purpose="treatment", condition="chronic_rhinosinusitis", values=[1e9], dose_status="verified",
        duration=28, forms=["tablet"],
        outcomes=[("sinonasal_quality_of_life_snot20", "primary", PI, "null"),
                  ("symptom_frequency", "secondary", PI, "null"),
                  ("medication_use", "secondary", PI, "null")],
        family="r0011_crs_19201289", design="rct", n=77, blinding="double", tier="D",
        limitations=["SNOT-20 improved within the probiotic group at 4 weeks but not versus placebo at 4 or 8 weeks.",
                     "Dose: 500 million active cells per tablet twice daily."]),
    ctx("ncimb30242_yogurt_hypercholesterolemia_22067612", ["22067612", "22425689"], owner=N30242, age="adult",
        population="Hypercholesterolaemic adults (114 completed; 120 randomized in the safety report); microencapsulated NCIMB 30242 yoghurt or placebo yoghurt twice daily for 6 weeks, multicentre",
        purpose="treatment", condition="hypercholesterolemia", values=[1e11], dose_status="verified",
        dose_pmid="22425689", duration=42, forms=["yogurt"],
        outcomes=[("ldl_cholesterol", "unresolved", SU, "positive"),
                  ("total_and_non_hdl_cholesterol_apob100", "unresolved", SU, "positive"),
                  ("hdl_cholesterol_and_triglycerides", "unresolved", SU, "null"),
                  ("adverse_events", "secondary", PI, "null")],
        family="ncimb30242_yogurt_trial", design="rct", n=114, blinding="double", tier="C",
        limitations=["Lipid endpoints are cardiovascular surrogates.",
                     "Microencapsulated yoghurt formulation; the daily dose comes from the companion safety report (5 x 10^10 CFU twice daily)."]),
    ctx("ncimb30242_capsule_hypercholesterolemia_22990854", ["22990854", "22561556", "23609838", "24074303"],
        owner=N30242, age="adult",
        population="Hypercholesterolemic adults (127 completed; 131 randomized in the safety report); NCIMB 30242 capsules or placebo twice daily for 9 weeks, multicenter",
        purpose="treatment", condition="hypercholesterolemia", values=[5.8e9], dose_status="verified",
        dose_pmid="22561556", duration=63, forms=["capsule"],
        outcomes=[("ldl_cholesterol", "primary", SU, "positive"),
                  ("total_and_non_hdl_cholesterol_apob100", "secondary", SU, "positive"),
                  ("hs_crp_and_fibrinogen", "secondary", SU, "positive"),
                  ("serum_25_hydroxyvitamin_d", "post_hoc", SU, "positive"),
                  ("gastrointestinal_health_status", "post_hoc", PI, "positive"),
                  ("adverse_events", "secondary", PI, "null")],
        family="ncimb30242_capsule_trial", design="rct", n=127, blinding="double", tier="C",
        limitations=["The primary outcome (LDL-cholesterol) is a cardiovascular surrogate.",
                     "Vitamin D (23609838) and GI-symptom (24074303) findings are post hoc analyses of the same trial.",
                     "Dose from the safety report: 2.9 x 10^9 CFU twice daily."]),
    ctx("sd5865_incretin_insulin_secretion_26084343", ["26084343"], owner=SD5865, age="adult",
        population="21 glucose-tolerant adults (11 lean, 10 obese); L. reuteri SD5865 or placebo twice daily for 4 weeks",
        purpose="physiology", condition="incretin_and_insulin_secretion", values=[2e10], dose_status="verified",
        duration=28,
        outcomes=[("glp1_and_glp2_release", "unresolved", SU, "positive"),
                  ("insulin_and_c_peptide_secretion", "unresolved", SU, "positive"),
                  ("insulin_sensitivity", "unresolved", SU, "null"),
                  ("ectopic_fat_and_cytokines", "unresolved", SU, "null")],
        family="sd5865_incretin_26084343", design="rct", n=21, blinding="double", tier="D",
        limitations=["Proof-of-concept physiology trial of 21 participants; every outcome is a metabolic surrogate.",
                     "Insulin sensitivity, body fat distribution and cytokines were unchanged."]),
    ctx("uala01_postmenopausal_bone_39010860", ["39010860"], owner=UALA01, age="adult",
        population="55 postmenopausal women randomized to L. acidophilus UALa-01 (n=30) or placebo (n=25) daily for 12 weeks",
        purpose="prevention", condition="postmenopausal_bone_health", duration=84,
        outcomes=[("bone_mineral_density", "unresolved", SU, "null"),
                  ("bone_turnover_markers", "unresolved", SU, "null"),
                  ("serum_calcium", "unresolved", SU, "negative"),
                  ("fasting_glucose", "unresolved", SU, "negative"),
                  ("body_and_visceral_fat", "unresolved", SU, "positive")],
        family="uala01_postmenopausal_39010860", design="rct", n=55, blinding="unreported", tier="D",
        limitations=["Bone mineral density did not change; every outcome is a biomarker.",
                     "The authors report an unfavourable rise in glucose and fall in serum calcium in the probiotic group.",
                     "Dose not stated in the abstract."]),
    ctx("crl1505_adult_urti_prevention_42354894", ["42354894"], owner=CRL1505, age="adult",
        population="Healthy adults randomized to L. rhamnosus CRL 1505 or placebo for 12 weeks with a 4-week follow-up",
        purpose="prevention", condition="upper_respiratory_tract_infection", values=[1e9], dose_status="verified",
        duration=84,
        outcomes=[("proportion_with_urti_episodes", "primary", PI, "mixed"),
                  ("urti_episodes_duration_and_free_time", "secondary", PI, "positive"),
                  ("symptomatic_medication_use", "secondary", PI, "positive")],
        family="crl1505_adult_urti_42354894", design="rct", n=None, blinding="double", tier="D",
        limitations=["The primary endpoint was significant only for three or more episodes at 16 weeks, not for one or two.",
                     "Sample size not stated in the abstract."]),
    ctx("cu1_elderly_common_infectious_disease_26640504", ["26640504", "27825987"], owner=CU1, age="adult",
        population="100 healthy adults aged 60-74; B. subtilis CU1 or placebo in four 10-day courses separated by 18-day breaks over 16 weeks",
        purpose="prevention", condition="common_infectious_disease_elderly", values=[2e9], dose_status="verified",
        dose_pmid="27825987", duration=112, measurement_type="spores",
        outcomes=[("days_with_common_infectious_disease_symptoms", "primary", PI, "null"),
                  ("fecal_and_salivary_secretory_iga", "secondary", SU, "positive"),
                  ("respiratory_infection_frequency", "post_hoc", PI, "positive"),
                  ("safety_markers", "secondary", SU, "null")],
        family="cu1_elderly_cid_26640504", design="rct", n=100, blinding="double", tier="C",
        limitations=["The primary outcome was not reduced (P = 0.20).",
                     "Immune findings come from a 44-participant subset; the respiratory-infection reduction is post hoc.",
                     "Intermittent intake: 2 x 10^9 spores per day on 40 of 112 days (27825987)."]),
    ctx("i3799_pediatric_acute_diarrhea_32796401", ["32796401"], owner=I3799, age="child",
        population="100 infants and children aged 3-36 months with acute diarrhea managed per WHO guidelines; S. boulardii CNCM I-3799 or placebo for 5 days, multicenter",
        purpose="treatment", condition="acute_diarrhea_pediatric", values=[1e10], dose_status="verified",
        duration=5,
        outcomes=[("diarrhea_duration", "primary", PI, "positive"),
                  ("stool_frequency_and_consistency", "secondary", PI, "positive")],
        family="i3799_pediatric_diarrhea_32796401", design="rct", n=100, blinding="double", tier="C",
        limitations=["One multicenter trial of five-day treatment, adjunctive to WHO-guideline rehydration care.",
                     "Dose: 5 billion CFU twice daily."]),
    ctx("b420_nsaid_gi_inflammation_33908058", ["33908058"], owner=B420, age="adult",
        population="50 healthy adults aged 20-40 (Finland); B420 or placebo, then with diclofenac sustained-release tablets",
        purpose="challenge", condition="nsaid_induced_gastrointestinal_inflammation",
        co_therapies=["diclofenac sustained-release (challenge)"],
        outcomes=[("fecal_calprotectin", "primary", SU, "null"),
                  ("fecal_and_blood_hemoglobin", "secondary", SU, "null")],
        family="b420_nsaid_33908058", design="rct", n=50, blinding="double", tier="D",
        limitations=["The primary surrogate (faecal calprotectin) did not differ from placebo.",
                     "Dose not stated in the abstract."]),
    ctx("b420_overweight_body_fat_27810310", ["27810310", "30525950"], owner=B420, age="adult",
        population="225 healthy overweight or obese adults (BMI 28-34.9) randomized to placebo, polydextrose, B420 or B420 with polydextrose for 6 months",
        purpose="treatment", condition="overweight_body_fat", values=[1e10], dose_status="verified",
        duration=182, registration="NCT01978691", comparator="microcrystalline cellulose placebo",
        outcomes=[("body_fat_change_b420_alone", "primary", PI, "null"),
                  ("body_fat_change_b420_factorial", "post_hoc", PI, "positive"),
                  ("gut_microbiota", "secondary", SU, "positive")],
        family="b420_weight_management_nct01978691", design="rct", n=225, blinding="double", tier="C",
        limitations=["The B420-alone arm did not differ from placebo on the primary outcome (-3.0%, P = 0.28 per protocol; ITT also null).",
                     "The significant effect was B420 with polydextrose, a combination with fiber; a post hoc factorial analysis favoured B420.",
                     "30525950 reports exploratory microbiota outcomes of the same trial."]),
    ctx("g91_chronic_constipation_qol_41843723", ["41843723"], owner=G91, age="adult",
        population="140 adults with chronic constipation (JPAC-QOL overall >= 1) analyzed; BBG9-1 or placebo for 8 weeks, multicenter Japan",
        purpose="treatment", condition="chronic_constipation", duration=56,
        outcomes=[("constipation_quality_of_life_jpac_qol", "primary", PI, "null"),
                  ("physical_discomfort_subscale", "secondary", PI, "positive"),
                  ("defecation_frequency_high_straining_subgroup", "post_hoc", PI, "positive")],
        family="g91_constipation_qol_41843723", design="rct", n=140, blinding="double", tier="C",
        limitations=["The primary endpoint did not differ from placebo (p = 0.282); the authors conclude a limited effect.",
                     "Only one subscale reached nominal significance; dose not stated in the abstract."]),
    ctx("bs01_evacuation_disorders_20697291", ["20697291"], owner=BS01, age="adult",
        population="300 healthy adults with evacuation disorders and hard stools: placebo (n=80), LP01 + BR03 (n=110) or BS01 alone (n=110) for 30 days",
        purpose="treatment", condition="functional_evacuation_disorders", duration=30,
        outcomes=[("weekly_bowel_movements", "unresolved", PI, "positive"),
                  ("stool_consistency_and_ease_of_expulsion", "unresolved", PI, "positive"),
                  ("abdominal_bloating_and_discomfort", "unresolved", PI, "positive")],
        family="probiotical_evacuation_disorders_20697291", design="rct", n=300, blinding="double", tier="C",
        limitations=["Endpoint hierarchy is not stated in the abstract.",
                     "The retrieved abstract lost the daily dose exponent ('5 x 10 colony-forming units/d')."]),
    ctx("m63_term_infants_microbiota_development_36986131", ["36986131", "40681696"], owner=M63, age="infant",
        population="Healthy term infants (56 M-63, 54 placebo; 111 in the companion report); 1 x 10^9 CFU/day from postnatal day 7 or earlier to 3 months",
        purpose="physiology", condition="infant_gut_microbiota_development", values=[1e9], dose_status="verified",
        duration_basis="participant_specific",
        outcomes=[("fecal_bifidobacterium_abundance", "unresolved", SU, "positive"),
                  ("stool_ph_acetate_and_iga", "unresolved", SU, "positive"),
                  ("fecal_inflammatory_cytokines", "unresolved", SU, "positive"),
                  ("adverse_events", "unresolved", PI, "null")],
        family="m63_term_infant_trial", design="rct", n=110, blinding="double", tier="C",
        limitations=["Microbiota and fecal markers are surrogates; no clinical outcome is reported.",
                     "40681696 reports inflammation markers from the same trial."]),
    ctx("m63_weaning_bowel_function_42056537", ["42056537"], owner=M63, age="child",
        population="100 healthy infants and toddlers (5 months to under 3 years); M-63 5 billion CFU or placebo daily for 8 weeks",
        purpose="physiology", condition="weaning_bowel_function", values=[5e9], dose_status="verified",
        duration=56,
        outcomes=[("days_with_normal_stools", "unresolved", PI, "positive"),
                  ("diarrhea_episodes", "unresolved", PI, "null"),
                  ("cold_like_symptoms_subgroups", "post_hoc", PI, "unresolved")],
        family="m63_weaning_42056537", design="rct", n=100, blinding="double", tier="D",
        limitations=["The authors describe the trial as exploratory and hypothesis-generating; no primary endpoint is named.",
                     "Subgroup trends need confirmation."]),
]

# Identity facts the 2026-09-13 plain-text read could not see (italics lost) or
# that the retired legacy summaries carried implicitly.
IDENTITY = {
    R0011: {"status": "designation_verified", "add_pmids": ["19201289"], "deposit_ids": None,
            "note": "2026-09-22 (closure D1): PMID 19201289 names Lactobacillus rhamnosus R0011; the 2026-09-13 'species unconfirmed' was a lost-italics plain-text read, not a source conflict."},
    BS01: {"status": "designation_verified", "add_pmids": ["20697291"], "deposit_ids": ["LMG P-21384"],
           "note": "2026-09-22 (closure D1): PMID 20697291 names Bifidobacterium animalis subsp. lactis BS01 (LMG P-21384)."},
    "STRAIN_PLANTARUM_LP01": {"status": "designation_verified", "add_pmids": ["20697291"], "deposit_ids": ["LMG P-21021"],
                              "note": "2026-09-22 (closure D1): PMID 20697291 names Lactobacillus plantarum LP01 (LMG P-21021)."},
    M63: {"status": "designation_verified", "add_pmids": ["36986131"], "deposit_ids": None,
          "note": "2026-09-22 (closure D1): PMID 36986131 names Bifidobacterium longum subsp. infantis M-63."},
}


def _review_block(review: dict) -> dict:
    block = {"conclusion": review["conclusion"]}
    if review.get("reason"):
        block["reason"] = review["reason"]
    block.update({
        "reviewed_on": REVIEWED_ON, "reviewer": REVIEWER, "search_query": review["search_query"],
        "pmids_screened": review["pmids_screened"], "combination_pmids": review["combination_pmids"],
        "ineligible_single_strain_pmids": sorted(review["ineligible_single_strain_pmids"]),
        "basis": BASIS_REL,
    })
    if review.get("note"):
        block["note"] = review["note"]
    return block


def apply(registry: dict, reviews: dict, reviewed_at: str) -> dict:
    from probiotic_measurements import (
        derived_context_evidence, identity_review_accepted, strain_literature_review_concluded)
    from studied_formulas import valid_native_study_context

    by_id = {e["id"]: e for e in registry["clinically_relevant_strains"]}
    contexts: dict[str, list] = {}
    for owner, row in CONTEXTS:
        row = deepcopy(row)
        row["clinical_review"] = {"reviewer": REVIEWER, "reviewed_at": reviewed_at,
                                  "scope": "identity_dose_outcome_applicability",
                                  "basis": BASIS_REL, "decision": "approve"}
        contexts.setdefault(owner, []).append(row)
    contexts = {sid: rows for sid, rows in contexts.items() if sid in reviews}
    assert set(contexts) == {sid for sid, r in reviews.items()
                             if r["conclusion"] == "exact_strain_contexts_recorded"}, "context owners != review set"
    assert not (set(reviews) & CLINICIAN_GATED)

    changed = []
    for sid, review in sorted(reviews.items()):
        entry = by_id[sid]
        assert "literature_review" not in entry, f"{sid}: already reviewed (refusing to re-apply)"
        assert (entry.get("cfu_thresholds") or {}).get("dr_pham_signoff") is not True, sid
        if sid in RETIRE_LEGACY:
            assert isinstance(entry["cfu_thresholds"].get("evidence"), dict), f"{sid}: no legacy block"
            entry["cfu_thresholds"]["evidence"] = None
        else:
            assert entry["cfu_thresholds"].get("evidence") is None, f"{sid}: unexpected legacy block"
        if sid in IDENTITY:
            spec = IDENTITY[sid]
            iv = dict(entry.get("identity_verification") or {})
            iv["status"] = spec["status"]
            iv["source_pmids"] = sorted(set(iv.get("source_pmids") or []) | set(spec["add_pmids"]))
            if spec["deposit_ids"] is not None:
                iv["deposit_ids"] = spec["deposit_ids"]
            iv.setdefault("deposit_ids", [])
            iv["verified_on"] = REVIEWED_ON
            iv["method"] = "PubMed efetch XML title/abstract read for the designation and species"
            iv["note"] = spec["note"]
            entry["identity_verification"] = iv
        entry["literature_review"] = _review_block(review)
        if review["conclusion"] == "exact_strain_contexts_recorded":
            existing = entry.get("study_contexts") or []
            new = contexts[sid]
            ids = {c["context_id"] for c in existing}
            assert not ids & {c["context_id"] for c in new}, sid
            entry["study_contexts"] = existing + new
            for c in new:
                assert valid_native_study_context(c, sid), f"{sid}: invalid context {c['context_id']}"
            derived = derived_context_evidence(entry)
            assert derived is not None and identity_review_accepted(entry), f"{sid}: contexts do not own evidence"
            entry["evidence_level"] = {"strong": "high", "medium": "moderate", "weak": "low"}[derived["evidence_strength"]]
            entry["notable_studies"] = (f"Closure D1 review {REVIEWED_ON}: {len(new)} single-strain controlled "
                                        f"{'trial' if len(new) == 1 else 'trials'} recorded as study contexts "
                                        f"(derived direction: {derived['effect_direction']}).")
        else:
            entry["evidence_level"] = "none"
            entry["key_benefits"] = []
            entry["notable_studies"] = (f"Closure D1 review {REVIEWED_ON}: no qualifying human evidence "
                                        f"({review['reason'].replace('_', ' ')}).")
            assert strain_literature_review_concluded(entry), f"{sid}: conclusion not recognized"
            assert not identity_review_accepted(entry), sid
        changed.append(sid)

    meta = registry["_metadata"]
    meta["last_updated"] = REVIEWED_ON
    meta["literature_review_note_2026_09_22"] = (
        f"Closure D1: {sum('literature_review' in e for e in by_id.values())} identities reviewed to a terminal state "
        f"({sum((e.get('literature_review') or {}).get('conclusion') == 'exact_strain_contexts_recorded' for e in by_id.values())} with single-strain "
        "controlled trials recorded as study contexts; the rest no qualifying human evidence, with reasons). "
        "Bi-07 and BB-12 stay under their suspended clinician sign-off. Agent-authored summaries for BS01, LP01, "
        "M-63 and the four DS-01 members were retired into study contexts or FORMULA_SEED_DS01. "
        f"Approvals are a delegated research review, not a clinician sign-off. Basis: {BASIS_REL}.")
    return {"changed": changed, "contexts": sum(len(v) for v in contexts.values())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--only", nargs="+", help="apply just these identities (later additions to the basis)")
    args = parser.parse_args()
    raw = REG.read_text(encoding="utf-8")
    registry = json.loads(raw)
    assert json.dumps(registry, indent=2, ensure_ascii=False) + "\n" == raw, "registry not in canonical form"
    reviews = json.loads(BASIS.read_text(encoding="utf-8"))["reviews"]
    if args.only:
        assert set(args.only) <= set(reviews), set(args.only) - set(reviews)
        reviews = {sid: reviews[sid] for sid in args.only}
    reviewed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = deepcopy(registry)
    result = apply(registry, reviews, reviewed_at)
    untouched = [e["id"] for e, b in zip(registry["clinically_relevant_strains"], before["clinically_relevant_strains"])
                 if e == b]
    assert len(untouched) + len(result["changed"]) == len(registry["clinically_relevant_strains"])
    print(f"{len(result['changed'])} identities changed, {result['contexts']} contexts, {len(untouched)} untouched")
    if args.apply:
        REG.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written", REG.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
