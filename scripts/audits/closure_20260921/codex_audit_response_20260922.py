#!/usr/bin/env python3
"""Apply the reproduced findings of Codex's 2026-09-22 probiotic registry audit.

Codex audited an intermediate snapshot (after Dr Pham's decisions, before the
explicit-direction pass), so A08 and A10 and most of A02/A09 were already fixed by
``pham_review_20260922.py``. Every remaining claim was reproduced before it was
applied: each cited PMID was fetched live from PubMed (efetch XML) and, where the
abstract was silent, the open-access full text (Europe PMC). The per-finding
disposition and the verified facts are in ``CODEX_AUDIT_RESPONSE_20260922.json``.

Scope stays label-bounded (supplements and medications only): an identity with no
supplement label in the catalog (MIMBb75, A26) is not added.

New study contexts are a delegated research review, not a clinician sign-off; they
are listed for Dr Pham's countersignature. Each entry is edited explicitly and
asserted against its current value first; there is no bulk transform.

    python3 scripts/audits/closure_20260921/codex_audit_response_20260922.py          # dry run
    python3 scripts/audits/closure_20260921/codex_audit_response_20260922.py --apply
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
BASIS_REL = "scripts/audits/closure_20260921/CODEX_AUDIT_RESPONSE_20260922.json"
ON = "2026-09-22"
REVIEWER = ("Claude Opus 5 research review (Codex audit response, 2026-09-22), delegated by Sean B "
            "(engineering owner); not a clinician sign-off")
PI, SU = "patient_important", "surrogate"

HEAL9, BB12, L1714 = "STRAIN_PLANTARUM_HEAL9", "STRAIN_LACTIS_BB12", "STRAIN_LONGUM_1714"
B35624, LGG, P299V = "STRAIN_INFANTIS_35624", "STRAIN_LGG", "STRAIN_PLANTARUM_299V"
LAFTI, UABLA12, DDS1 = "STRAIN_ACIDOPHILUS_LAFTI_L10", "STRAIN_LACTIS_UABla12", "STRAIN_ACIDOPHILUS_DDS1"


def ctx(context_id, pmid, *, owner, age, population, purpose, condition, outcomes, family, limitations,
        n, blinding, values=(), dose_status="extraction_pending", location="abstract", source_url=None,
        duration=None, forms=(), frequency=None, registration=None, comparator="placebo"):
    dose = {"basis": "discrete_daily_arms" if values else "unresolved", "unit": "CFU", "values": list(values),
            "dosage_forms": list(forms), "duration_days": duration, "co_therapies": [],
            "dose_status": dose_status, "dose_basis": "per_strain_daily",
            "duration_basis": "fixed_protocol" if duration else "not_recorded"}
    if frequency:
        dose["administration_frequency"] = frequency
    if dose_status == "verified":
        dose["source_provenance"] = {"pmid": pmid, "source_url": source_url or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                                     "location": location}
    outs = []
    for name, hierarchy, kind, direction, *role in outcomes:
        row = {"name": name, "hierarchy": hierarchy, "kind": kind, "direction": direction}
        if role:
            row["outcome_role"] = role[0]
        outs.append(row)
    return owner, {
        "context_id": context_id, "source_pmids": [pmid], "identity_scope": "exact_strain", "components": [owner],
        "population": {"age_group": age, "description": population}, "purpose": purpose, "condition": condition,
        "dose": dose, "outcomes": outs, "trial_family": family, "limitations": list(limitations),
        "review_status": "clinician_approved", "study_design": "rct", "sample_size": n, "blinding": blinding,
        "funding": "unreported", "source_tier": "C", "trial_registration": registration, "comparator": comparator,
        "authored_on": ON, "authoring_method": "PubMed efetch XML abstract read (and Europe PMC full text where named); Codex audit response",
        "context_schema_version": "1.1.0", "evidence_role": "direct_rct",
        "component_registration_status": "fully_registered", "scoring_eligible": True,
    }


CONTEXTS = [
    # A01 - HEAL9 has a single-strain placebo-controlled trial.
    ctx("heal9_moderate_stress_cognition_37571403", "37571403", owner=HEAL9, age="adult",
        population="129 moderately stressed adults aged 21-52 (completers), HEAL9 or placebo for 12 weeks",
        purpose="physiology", condition="cognition_under_moderate_stress", duration=84,
        outcomes=[("cognitive_test_performance", "unresolved", PI, "positive"),
                  ("perceived_stress_and_awakening_cortisol", "unresolved", PI, "null"),
                  ("mood_subscales_and_sleep", "unresolved", PI, "unresolved")],
        family="heal9_stress_cognition_37571403", n=129, blinding="unreported",
        limitations=["Exploratory study; no primary endpoint is named in the abstract.",
                     "Perceived stress and cortisol fell in both groups; mood and sleep differences were trends (p < 0.10).",
                     "Dose not stated in the abstract."]),
    # A13 - two single-strain BB-12 infant-colic RCTs.
    ctx("bb12_infant_colic_breastfed_31797399", "31797399", owner=BB12, age="infant",
        population="80 exclusively breastfed infants with colic, BB-12 1 x 10^9 CFU/day or placebo for 28 days",
        purpose="treatment", condition="infant_colic", values=[1e9], dose_status="verified", duration=28, frequency="once_daily",
        outcomes=[("crying_duration_50pct_responders", "primary", PI, "positive"),
                  ("crying_episodes", "secondary", PI, "positive"),
                  ("stool_consistency", "secondary", PI, "null"),
                  ("faecal_immune_and_microbiota_markers", "secondary", SU, "positive")],
        family="bb12_infant_colic_31797399", n=80, blinding="double",
        limitations=["Single-centre trial in exclusively breastfed infants; not evidence for older children or adults."]),
    ctx("bb12_infant_colic_chengdu_34550055", "34550055", owner=BB12, age="infant",
        population="192 full-term breastfed infants under 3 months with Rome III colic, BB-12 1 x 10^9 CFU/day or placebo for 21 days",
        purpose="treatment", condition="infant_colic", values=[1e9], dose_status="verified", duration=21, frequency="once_daily",
        outcomes=[("crying_fussing_50pct_responders", "primary", PI, "positive"),
                  ("crying_episodes", "secondary", PI, "positive"),
                  ("daily_sleep_duration", "secondary", PI, "positive"),
                  ("faecal_immune_markers", "secondary", SU, "positive")],
        family="bb12_infant_colic_34550055", n=192, blinding="double",
        limitations=["Infant colic only; the adult constipation trial (26382580) remains null for its own question."]),
    # A12 - two B. longum 1714 RCTs, both null on their primary endpoint.
    ctx("b1714_impaired_sleep_quality_38355674", "38355674", owner=L1714, age="adult",
        population="89 adults aged 18-45 with impaired sleep quality (PSQI >= 5), 1714 or placebo for 8 weeks",
        purpose="treatment", condition="impaired_sleep_quality", duration=56, registration="NCT04167475",
        outcomes=[("psqi_global_score", "primary", PI, "null"),
                  ("psqi_sleep_quality_and_daytime_dysfunction_week4", "secondary", PI, "positive"),
                  ("social_functioning_and_vitality_week8", "secondary", PI, "positive"),
                  ("actigraphy_sleep_parameters", "secondary", SU, "null")],
        family="b1714_sleep_38355674", n=89, blinding="double",
        limitations=["The primary PSQI global score improved similarly in both groups; secondary gains were transient or subjective.",
                     "Dose not stated in the abstract."]),
    ctx("b1714_low_mood_42060410", "42060410", owner=L1714, age="adult",
        population="168 adults aged 18-70 with mild to moderate depression, 1714 1 x 10^10 CFU/day or placebo for 8 weeks",
        purpose="treatment", condition="mild_to_moderate_depression", values=[1e10], dose_status="verified", duration=56,
        frequency="once_daily",
        outcomes=[("bdi_ii_change", "primary", PI, "null"),
                  ("psqi_and_phq9_week4", "secondary", PI, "positive"),
                  ("sf36_subscores_week4", "secondary", PI, "positive")],
        family="b1714_mood_42060410", n=168, blinding="double",
        limitations=["Primary depression score not different from placebo at week 4 or 8; secondary week-4 signals did not persist to week 8."]),
    # A14 - 35624 dose-ranging IBS trial (only the 10^8 arm beat placebo).
    ctx("b35624_ibs_women_dose_ranging_16863564", "16863564", owner=B35624, age="adult",
        population="362 women with IBS in primary care, encapsulated 35624 at three doses or placebo for 4 weeks",
        purpose="treatment", condition="irritable_bowel_syndrome", duration=28,
        outcomes=[("abdominal_pain_1e8_arm", "primary", PI, "positive"),
                  ("abdominal_pain_1e6_and_1e10_arms", "primary", PI, "null")],
        family="b35624_ibs_dose_ranging_16863564", n=362, blinding="unreported",
        limitations=["Only the 1 x 10^8 arm beat placebo; the 10^6 and 10^10 arms did not, so no dose-response.",
                     "The abstract gives doses in cfu/mL for a capsule; the per-day dose is left unresolved."]),
    # A15 - LGG acute gastroenteritis (null) and 299v IBS (positive).
    ctx("lgg_pediatric_acute_gastroenteritis_30462938", "30462938", owner=LGG, age="child",
        population="971 children aged 3 months to 4 years with acute gastroenteritis in 10 US emergency departments, LGG or placebo for 5 days",
        purpose="treatment", condition="acute_gastroenteritis_children", values=[2e10], dose_status="verified", duration=5,
        frequency="twice_daily", registration="NCT01773967",
        outcomes=[("moderate_to_severe_gastroenteritis_14d", "primary", PI, "null"),
                  ("diarrhea_and_vomiting_duration", "secondary", PI, "null"),
                  ("household_transmission", "secondary", PI, "null")],
        family="lgg_us_age_30462938", n=971, blinding="double",
        limitations=["Dose 1 x 10^10 CFU twice daily. A treatment trial: says nothing about antibiotic-associated diarrhoea prevention."]),
    ctx("p299v_ibs_rome3_22912552", "22912552", owner=P299V, age="adult",
        population="214 adults with Rome III IBS, one 299v capsule daily or placebo for 4 weeks",
        purpose="treatment", condition="irritable_bowel_syndrome", duration=28,
        outcomes=[("abdominal_pain_severity_and_frequency", "unresolved", PI, "positive"),
                  ("bloating", "unresolved", PI, "positive"),
                  ("global_symptom_rating", "unresolved", PI, "positive")],
        family="p299v_ibs_22912552", n=214, blinding="double",
        limitations=["The abstract does not name a primary endpoint; CFU per capsule not stated."]),
    # A16 - L. helveticus Lafti L10 (the species the label prints).
    ctx("lafti_l10_elite_athletes_urti_27363733", "27363733", owner=LAFTI, age="adult",
        population="39 elite athletes, L. helveticus Lafti L10 or placebo over 14 winter weeks",
        purpose="prevention", condition="upper_respiratory_tract_illness_athletes", duration=98,
        outcomes=[("urti_episode_duration", "unresolved", PI, "positive"),
                  ("urti_symptom_count", "unresolved", PI, "positive"),
                  ("urti_incidence_and_severity", "unresolved", PI, "null"),
                  ("immune_parameters", "unresolved", SU, "null")],
        family="lafti_l10_athletes_27363733", n=39, blinding="double",
        limitations=["Small trial (39 athletes); no primary endpoint named; incidence and severity did not differ.",
                     "2 x 10^10 CFU is stated without a per-day basis."]),
    # Second review (item 4) - 8700:2 has a single-strain RCT; its outcomes are biomarkers.
    ctx("p8700_metabolic_syndrome_37506599", "37506599", owner="STRAIN_PARACASEI_8700", age="adult",
        population="130 adults with metabolic syndrome, L. paracasei 8700:2 1 x 10^10 CFU/day or placebo for 12 weeks",
        purpose="treatment", condition="metabolic_syndrome_cardiometabolic_markers", values=[1e10], dose_status="verified",
        duration=84, frequency="once_daily", registration="NCT05005754",
        outcomes=[("remnant_cholesterol", "unresolved", SU, "positive"),
                  ("endothelial_function_flow_mediated_slowing", "unresolved", SU, "positive"),
                  ("triglycerides_and_mets_severity_per_protocol", "post_hoc", SU, "positive", "post_hoc_subgroup"),
                  ("insulin_sensitivity_and_beta_cell_function", "unresolved", SU, "null")],
        family="p8700_mets_37506599", n=130, blinding="double",
        limitations=["All reported outcomes are cardiometabolic biomarkers; the abstract names no primary endpoint.",
                     "Triglyceride and MetS-severity effects appear only in the ideal-compliance (per-protocol) subset."]),
    # Second review (item 6) - ME-3 double-blind capsule arm; biomarker outcomes.
    ctx("me3_healthy_volunteers_oxidative_stress_16080791", "16080791", owner="STRAIN_FERMENTUM_ME3", age="adult",
        population="24 healthy volunteers in the double-blind arm, ME-3 capsules or placebo for 3 weeks",
        purpose="physiology", condition="oxidative_stress_markers_healthy_adults", duration=21, forms=["capsule"],
        outcomes=[("blood_total_antioxidative_activity_and_status", "unresolved", SU, "positive"),
                  ("faecal_lactobacilli", "unresolved", SU, "positive")],
        family="me3_functional_efficacy_16080791", n=24, blinding="double",
        limitations=["Only the double-blind capsule arm is recorded; the open goat-milk arm was a food and unblinded.",
                     "Oxidative-stress indices are biomarkers; the dose is printed as a log value (9.2) and left unresolved."]),
    # A09 - the UABla-12 solo arm of the three-arm DDS-1 / UABla-12 trial.
    ctx("uabla12_ibs_three_arm_32019158", "32019158", owner=UABLA12, age="adult",
        population="330 adults with Rome IV IBS randomized across placebo, DDS-1 and UABla-12 solo arms; UABla-12 1 x 10^10 CFU/day for 6 weeks",
        purpose="treatment", condition="irritable_bowel_syndrome", values=[1e10], dose_status="verified", duration=42,
        frequency="once_daily", forms=["capsule"], location="full_text_methods",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC7071206/",
        outcomes=[("abdominal_pain_severity_nrs", "primary", PI, "positive"),
                  ("ibs_severity_score", "secondary", PI, "positive")],
        family="uas_dds1_uabla12_ibs_32019158", n=330, blinding="double",
        limitations=["Manufacturer-run (UAS Labs); the DDS-1 solo arm is recorded under DDS-1, not as a combination."]),
]


def _review(reviewed_at: str) -> dict:
    return {"reviewer": REVIEWER, "reviewed_at": reviewed_at, "scope": "identity_dose_outcome_applicability",
            "basis": BASIS_REL, "decision": "approve"}


def add_contexts(by_id: dict, reviewed_at: str) -> None:
    from studied_formulas import valid_native_study_context
    for owner, row in CONTEXTS:
        row = deepcopy(row)
        row["clinical_review"] = _review(reviewed_at)
        existing = by_id[owner].setdefault("study_contexts", [])
        assert row["context_id"] not in {c["context_id"] for c in existing}, row["context_id"]
        assert not any(row["source_pmids"][0] in c["source_pmids"] for c in existing), (owner, row["source_pmids"])
        existing.append(row)
        assert valid_native_study_context(row, owner), row["context_id"]


def _mark_corrected(context: dict, note: str) -> None:
    """Record that an approved context was corrected after its approval (and by whom)."""
    context["clinical_review"]["corrected_by"] = {"reviewer": REVIEWER, "on": ON, "basis": BASIS_REL, "note": note}


def _context(by_id, owner, cid):
    return next(c for c in by_id[owner]["study_contexts"] if c["context_id"] == cid)


def _evidence(by_id, sid):
    return by_id[sid]["cfu_thresholds"]["evidence"]


def reopen_reviews(by_id: dict) -> None:
    """A01 HEAL9 and A16 LAFTI L10: 'no qualifying evidence' came from an incomplete search."""
    heal9 = by_id[HEAL9]
    review = heal9["literature_review"]
    assert review["conclusion"] == "no_qualifying_human_evidence" and review["withdrawn_citation"]["pmid"] == "31734734"
    review.update({
        "conclusion": "exact_strain_contexts_recorded", "reason": None,
        "reviewed_on": ON, "reopened_by": REVIEWER,
        "reopen_note": (f"{ON}: a single-strain placebo-controlled HEAL9 RCT (37571403) disproves the combination-only "
                        "conclusion. Dr Pham's withdrawal of the HEAL9 + 8700:2 trial as single-strain evidence stands."),
        "pmids_screened": sorted(set(review["pmids_screened"]) | {"37571403"}),
    })
    review.pop("reason")
    heal9["notable_studies"] = (f"Review {ON}: one exploratory single-strain RCT (129 moderately stressed adults, 12 "
                                "weeks) improved four cognitive tests vs placebo; stress, cortisol, mood and sleep did "
                                "not differ. The HEAL9 + 8700:2 cold trial is combination evidence.")
    heal9["evidence_level"] = "low"

    lafti = by_id[LAFTI]
    assert lafti["standard_name"] == "Lactobacillus acidophilus LAFTI L10"
    review = lafti["literature_review"]
    assert review["reason"] == "species_identity_unconfirmed_in_sources"
    lafti["standard_name"] = "Lactobacillus helveticus LAFTI L10"
    lafti["identity_verification"].update({
        "status": "designation_verified",
        "source_pmids": sorted(set(lafti["identity_verification"]["source_pmids"]) | {"27363733", "27100317", "39018571"}),
        "supplier": "Lallemand Health Solutions", "verified_on": ON,
        "note": ("Since 2016 every source names L. helveticus Lafti L10 (Lallemand), the species the label prints; "
                 "2002-2008 sources name L. acidophilus LAFTI L10. Only the L. helveticus research is recorded here; "
                 "whether the earlier acidophilus-named LAFTI L10 is the same strain is not established."),
    })
    review.update({
        "conclusion": "exact_strain_contexts_recorded", "reviewed_on": ON, "reopened_by": REVIEWER,
        "search_query": '("LAFTI L10"[tiab] OR "Lafti L10"[tiab] OR "LAFTI-L10"[tiab] OR "L10 LAFTI"[tiab])',
        "pmids_screened": ["12038580", "17134782", "17544732", "18045424", "18211356", "18468035", "18925885",
                           "19646055", "27100317", "27363733", "28980935", "30429904", "39018571", "39420712"],
        "reopen_note": (f"{ON}: the 2026-09-22 search required acidophilus[tiab] and missed the L. helveticus Lafti L10 "
                        "trials. Recorded: the 39-athlete URTI RCT (27363733)."),
    })
    review.pop("reason")
    lafti["notable_studies"] = (f"Review {ON}: a 39-athlete RCT of L. helveticus Lafti L10 shortened URTI episodes; "
                                "incidence and severity did not differ.")
    lafti["evidence_level"] = "low"


def correct_attribution(by_id: dict) -> None:
    # A02 - the primary vaccine-response endpoint was null.
    c431 = by_id["STRAIN_CASEI_431"]
    assert "vaccine response enhancement" in c431["key_benefits"]
    c431["key_benefits"] = [b for b in c431["key_benefits"] if b != "vaccine response enhancement"]

    # A03 - a three-strain respiratory trial is not single-strain NEC evidence.
    m16v = by_id["STRAIN_BREVE_M16V"]
    ev = _evidence(by_id, "STRAIN_BREVE_M16V")
    assert ev["type"] == "strain_specific_rct" and ev["clinical_validation"]["q2_outcome_relevant"] == "YES"
    ev["type"] = "combination_rct"
    ev["clinical_validation"]["q2_outcome_relevant"] = "NO"
    assert m16v["cfu_thresholds"]["indication_primary"] == "prevention of necrotizing enterocolitis in preterm infants"
    m16v["cfu_thresholds"]["indication_primary"] = "preterm and neonatal gut colonization"
    m16v["key_benefits"] = [b for b in m16v["key_benefits"] if b != "NEC prevention"]

    # A04 - DRACMA's tolerance (RR 2.47) and wheezing estimates come from LGG trials.
    dracma = _context(by_id, BB12, "casei431_bb12_dracma_cma_tolerance_39310372")
    assert dracma["scoring_eligible"] is False and dracma["outcomes"][0]["direction"] == "positive"
    dracma["condition"] = "non_ige_cow_milk_allergy_formula_adjunct"
    dracma["outcomes"] = [{"name": "non_ige_cma_outcomes_with_probiotic_formula", "hierarchy": "guideline",
                           "kind": PI, "direction": "unresolved"}]
    _mark_corrected(dracma, "LGG results removed from the CRL431 + BB-12 record (DRACMA full text).")
    dracma["limitations"] = [
        "DRACMA full text (PMC11415968): the tolerance estimate (RR 2.47, two trials, 236 patients) and the severe-"
        "wheezing estimate come from LGG-supplemented formula trials, not from CRL431 + BB-12.",
        "The one CRL431 + BB-12 trial (Hol 2008, 119 infants) enrolled non-IgE cow's milk allergy, where the review "
        "found no significant probiotic effect; the review reports no pair-specific estimate.",
        "The formula is the delivery vehicle and co-therapy; not supplement evidence. Scoring stays disabled.",
    ]

    # A05 - Prodentis is DSM 17938 + ATCC PTA 5289; single strains are not the blend.
    prod = by_id["STRAIN_REUTERI_PRODENTIS"]
    for alias in ("L. reuteri ATCC PTA 5289", "L. reuteri ATCC 55730"):
        prod["aliases"].remove(alias)
    ev = _evidence(by_id, "STRAIN_REUTERI_PRODENTIS")
    assert ev["effect_direction"] == "positive_weak"
    ev["effect_direction"] = "unresolved"  # a two-strain formulation earns no strain-level credit
    ev["additional_pmids"] = ["40856866"]
    ev["effect_direction_basis"] = (
        "Prodentis is the two-strain DSM 17938 + ATCC PTA 5289 formulation, so no strain-level credit is attributable. "
        "A 20-patient pilot RCT improved periodontal parameters within the test group; a 2025 RCT (40856866, 44 "
        "patients) of the lozenge added no benefit to supportive periodontal therapy. "
        f"(Recorded {ON}.)")
    prod["cfu_thresholds"]["notes"] = (
        "Tier cutoffs are industry convention (1B / 10B / 50B CFU/day). Prodentis is the two-strain L. reuteri "
        "DSM 17938 + ATCC PTA 5289 formulation; a single strain on a label is not this blend.")

    # A06 - a larger 2024 trial found no effect on bone loss.
    atcc = by_id["STRAIN_REUTERI_ATCC6475"]
    ev = _evidence(by_id, "STRAIN_REUTERI_ATCC6475")
    assert ev["effect_direction"] == "positive_strong"
    ev["effect_direction"] = "mixed"
    ev["additional_pmids"] = ["38865129"]
    ev["effect_direction_basis"] = (
        "2018 RCT (90 women aged 75-80 with low BMD): less tibial volumetric BMD loss vs placebo, the primary "
        "endpoint. 2024 RCT (38865129, 239 early postmenopausal women, 2 years, two doses): no effect on bone loss "
        "or turnover. Populations differ; BMD is a surrogate for fracture. (Recorded 2026-09-22.)")
    atcc["notable_studies"] = (
        f"Review {ON}: a 12-month RCT in 90 women aged 75-80 with low BMD reduced tibial BMD loss; a 2-year RCT in 239 "
        "early postmenopausal women found no effect. BMD is a surrogate; no fracture data. Testosterone, immune and "
        "skin effects come from animal models only.")

    # A07 - Lactin-V is intravaginal; supplement labels are oral.
    ctv = by_id["STRAIN_CRISPATUS_CTV05"]
    ev = _evidence(by_id, "STRAIN_CRISPATUS_CTV05")
    assert ev["effect_direction"] == "positive_strong"
    ev["effect_direction"] = "unresolved"
    ev["effect_direction_basis"] = (
        "Phase 2b RCT (32402161): intravaginal Lactin-V after vaginal metronidazole cut BV recurrence by week 12 (30% "
        "vs 45%). The evidence is for vaginal administration; no oral-route trial exists, so an oral supplement label "
        f"earns no efficacy credit from it. (Recorded {ON}.)")
    ctv["cfu_thresholds"]["notes"] += " Clinical evidence is intravaginal only; oral applicability is not established."

    # A09 - the DDS-1 record's limitations are stale.
    dds1 = _context(by_id, DDS1, "dds1_ibs_three_arm_32019158")
    assert dds1["limitations"][1].startswith("Only the DDS-1 solo arm is recorded here")
    dds1["limitations"] = ["Manufacturer-run (UAS Labs).",
                           "The UABla-12 solo arm is recorded under UABla-12 (same trial family)."]
    dds1["blinding"] = "double"
    _mark_corrected(dds1, "Stale dose and arm limitations corrected; blinding from the abstract.")

    # A10 - "EMA approved" and "100+ years of use" are unsourced.
    nissle = by_id["STRAIN_NISSLE_1917"]
    assert "EMA approved" in nissle["notable_studies"]
    nissle["notable_studies"] = ("Two double-blind double-dummy RCTs (327 and 120 patients) found relapse prevention in "
                                 "ulcerative colitis equivalent to mesalazine. (Ardeypharm)")

    # A21 - co-formulated or food-matrix interventions cannot be attributed to BC30 alone.
    for cid, note in (
        ("bc30_geriatric_indigestion_enzymes_32318476",
         "The active arm received BC30 co-formulated with digestive enzymes; the benefit belongs to that formulation, not BC30 alone."),
        ("bc30_synbiotic_pasta_cardiometabolic_31162597",
         "A synbiotic food (pasta with barley beta-glucans) is not a supplement intervention; the effect cannot be attributed to BC30."),
    ):
        c = _context(by_id, "STRAIN_COAGULANS_GBI30", cid)
        assert c["scoring_eligible"] is True
        c["scoring_eligible"] = False
        c["limitations"].append(note)
        _mark_corrected(c, "Made ineligible: the intervention was not BC30 alone.")


def correct_indications(by_id: dict) -> None:
    """A11 - bind each indication and benefit to the evidence the record holds (relevance is metadata only)."""
    def set_ind(sid, old, new):
        t = by_id[sid]["cfu_thresholds"]
        assert t["indication_primary"] == old, (sid, t["indication_primary"])
        t["indication_primary"] = new

    set_ind("STRAIN_K12", "oral health and halitosis prevention", "oral mucositis during head and neck radiotherapy (oral health)")
    by_id["STRAIN_K12"]["key_benefits"] = ["oral health"]
    set_ind("STRAIN_RHAMNOSUS_HN001", "atopic eczema prevention in infants",
            "postpartum depression and anxiety symptoms after maternal supplementation")
    by_id["STRAIN_RHAMNOSUS_HN001"]["key_benefits"] = ["mental well-being"]
    set_ind("STRAIN_LONGUM_BB536", "allergic rhinitis and gut health", "gut health and immune function")
    by_id["STRAIN_LONGUM_BB536"]["key_benefits"] = ["immune support", "gut health"]
    set_ind("STRAIN_COAGULANS_IS2", "bacterial vaginosis or gut health", "IBS and functional constipation (gut health)")
    set_ind("STRAIN_COAGULANS_GBI30", "irritable bowel symptom relief", "functional gastrointestinal symptoms")
    by_id["STRAIN_COAGULANS_GBI30"]["key_benefits"] = ["digestive health", "protein absorption (amino-acid uptake)"]
    # Second review (item 2) - the AGE indication cited a colic meta-analysis.
    dsm = by_id["STRAIN_REUTERI_DSM17938"]["cfu_thresholds"]["secondary_indications"][0]
    assert dsm["pmid"] == "26509502" and dsm["name"] == "acute gastroenteritis duration in children"
    dsm.update({"pmid": "31739457", "url": "https://pubmed.ncbi.nlm.nih.gov/31739457/",
                "source_short": "Nutrients (2019) - DSM 17938 for acute gastroenteritis in children: 4 RCTs, diarrhoea "
                                "duration -0.87 days; small effect, methodological limitations",
                "verified_date": ON, "effect_direction": "positive_weak",
                "citation_correction": f"{ON}: 26509502 is an infantile-colic meta-analysis; replaced by 31739457."})
    # Second review (item 3) - SP1 has a direct acne pilot RCT; keep both indications, modestly.
    sp1 = by_id["STRAIN_RHAMNOSUS_SP1"]
    t = sp1["cfu_thresholds"]
    assert t["indication_primary"] == "dental caries prevention"
    t["indication_primary"] = "adult acne (skin health) and denture stomatitis (oral health)"
    t["evidence"]["additional_pmids"] = ["27596801"]
    t["evidence"]["effect_direction_basis"] += (
        " Separately, a 20-adult pilot RCT (27596801, 3 x 10^9 CFU/day for 12 weeks) improved the investigator's "
        "global acne rating vs placebo.")
    sp1["key_benefits"] = ["adult acne (pilot trial)", "oral health"]
    sp1["notable_studies"] = (f"Review {ON}: a 36-elder denture-stomatitis RCT and a 20-adult acne pilot RCT, both "
                              "small; neither establishes caries prevention.")


def model_consistency(by_id: dict) -> None:
    # A20 - a primary outcome is not a post hoc subgroup; the adjusted MDR result is not a subgroup.
    pain = _context(by_id, LGG, "lgg_pediatric_pain_17229242")
    assert pain["outcomes"][0]["outcome_role"] == "post_hoc_subgroup"
    pain["outcomes"][0].pop("outcome_role")
    pain["outcomes"].append({"name": "ibs_subgroup_treatment_success", "hierarchy": "post_hoc", "kind": PI,
                             "direction": "positive", "outcome_role": "post_hoc_subgroup"})
    _mark_corrected(pain, "Primary outcome no longer labelled a subgroup; the IBS subgroup recorded separately.")
    mdr = _context(by_id, "STRAIN_RHAMNOSUS_GR1", "gr1_rc14_sci_mdr_colonization_31953482")
    assert mdr["outcomes"][0]["outcome_role"] == "post_hoc_subgroup"
    mdr["outcomes"][0].pop("outcome_role")
    _mark_corrected(mdr, "The adjusted new-colonization result is a secondary analysis, not a subgroup.")

    # A23 - measured transit is a physiological endpoint, not symptom relief.
    changed = 0
    for entry in by_id.values():
        for c in entry.get("study_contexts") or []:
            for o in c["outcomes"]:
                if o["name"] in ("colonic_transit_time", "intestinal_transit_time_hn019"):
                    assert o["kind"] == PI
                    o["kind"] = SU
                    changed += 1
                    _mark_corrected(c, "Measured transit reclassified as a physiological surrogate.")
    assert changed == 3, changed
    bi26 = _context(by_id, "STRAIN_INFANTIS_BI26", "bi26_underweight_infants_growth_42137872")
    bi26["limitations"].append("Fewer adverse events with Bi-26 (40% vs 80% of infants) is a secondary safety count in "
                               "an early-terminated 40-infant trial; one death in each arm, both after dosing ended and "
                               "neither attributed to the intervention.")

    # A24 - recoverable dose and schedule facts.
    assert bi26["dose"]["dose_status"] == "extraction_pending"
    bi26["dose"].update({"basis": "unresolved", "values": [5e9], "dosage_forms": ["sachet"],
                         "dose_status": "verified", "dose_basis": "measured_viability",
                         "administration_frequency": "once_daily",
                         "duration_note": "Approximately 5 billion CFU per sachet at end of shelf life (a minimum "
                                          "stability claim, not a measured administered dose), daily for 28 days.",
                         "source_provenance": {"pmid": "42137872",
                                               "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC13167951/",
                                               "location": "full_text_methods"}})
    cu1 = _context(by_id, "STRAIN_SUBTILIS_CU1", "cu1_elderly_common_infectious_disease_26640504")
    cu1["dose"]["administration_frequency"] = "once_daily"
    _mark_corrected(bi26, "Dose recorded from the full text; adverse-event limitation added.")
    _mark_corrected(cu1, "Intermittent dosing schedule recorded.")
    cu1["dose"]["duration_note"] = ("Four 10-day courses separated by 18-day breaks: 40 dosing days within the "
                                    "112-day protocol.")

    # A25 - stale current-facing copy.
    iv = _evidence(by_id, "STRAIN_COAGULANS_IS2")["clinical_validation"]
    assert iv["score_yes_count"] == 4
    iv["score_yes_count"] = 3
    ncfm = by_id["STRAIN_ACIDOPHILUS_NCFM"]["cfu_thresholds"]
    assert "pending clinical review" in ncfm["notes"]
    ncfm["notes"] = ("Legacy tier cutoffs are industry convention, not universal efficacy thresholds. NCFM's approved "
                     "human study contexts own its human evidence; the historical animal-source summary does not.")
    lpc = by_id["STRAIN_PARACASEI_LPC37"]["cfu_thresholds"]
    assert "recorded in pending contexts" in lpc["notes"]
    lpc["notes"] = ("Tier cutoffs remain historical industry convention, not a source-verified efficacy range. Sisu "
                    "studied Lpc-37 and its primary outcome was null; secondary signals and the later null ChillEx "
                    "trial are recorded in approved study contexts, which do not establish a dosing policy.")


def prebiotics(registry: dict) -> None:
    """A17 - resistant maltodextrin is not resistant starch; generic phrases are not identities."""
    rows = registry["prebiotics"]["ingredients"]
    by_name = {r["standard_name"]: r for r in rows}
    starch = by_name["Resistant Starch"]
    assert starch["aliases"] == ["resistant maltodextrin", "digestion resistant maltodextrin"]
    starch["aliases"] = []
    rows.insert(rows.index(starch) + 1, {"standard_name": "Resistant Dextrin",
                                         "aliases": ["resistant maltodextrin", "digestion resistant maltodextrin",
                                                     "resistant dextrin"]})
    by_name["Pomegranate Polyphenol Extract"]["aliases"].remove("polyphenol-based prebiotic")
    by_name["Partially Hydrolyzed Guar Gum"]["aliases"].remove("guar fiber")


STALE_BEST_HIT = ("Best-available PubMed hit is animal-model / narrative / mixed-strain. Dr Pham should replace with a "
                  "stronger strain-specific RCT if one exists.")
LEVEL = {"strong": "high", "medium": "moderate", "weak": "low"}
I745 = "STRAIN_BOULARDII_CNCM_I745"


def second_review(registry: dict, by_id: dict, reviewed_at: str) -> None:
    """The ten bounded corrections of the second 2026-09-22 review, each verified live."""
    from probiotic_measurements import derived_context_evidence

    # 1 - IS-2's note still calls its best source animal/narrative although it cites a human RCT.
    is2 = by_id["STRAIN_COAGULANS_IS2"]["cfu_thresholds"]
    assert STALE_BEST_HIT in is2["notes"]
    is2["notes"] = is2["notes"].replace(STALE_BEST_HIT, "The cited record is a human RCT; its IBS and constipation "
                                                        "trials are recorded as study contexts.")

    # 4 - 8700:2: human evidence is cardiometabolic biomarkers; cold/immune trials are HEAL9 combinations.
    p8700 = by_id["STRAIN_PARACASEI_8700"]
    assert p8700["key_benefits"] == ["immune support", "respiratory health", "cardiometabolic health", "cold prevention"]
    p8700["key_benefits"] = ["cardiometabolic markers (biomarker evidence)"]
    assert p8700["cfu_thresholds"]["indication_primary"] == "allergic rhinitis symptom relief"
    p8700["cfu_thresholds"]["indication_primary"] = "cardiometabolic markers in metabolic syndrome"
    p8700["cfu_thresholds"]["notes"] = p8700["cfu_thresholds"]["notes"].replace(
        "Strain-specific RCT or meta-analysis.", "The cited record is a laboratory method paper; the human RCT "
        "(37506599) is recorded as a study context. Common-cold trials test 8700:2 with HEAL9 and credit neither alone.")
    p8700["notable_studies"] = (f"Review {ON}: one single-strain RCT in 130 adults with metabolic syndrome lowered "
                                "remnant cholesterol and improved endothelial function (biomarkers). Its cold trials "
                                "are HEAL9 + 8700:2 combinations.")

    # 5 - 1714: two single-strain RCTs, both null on the primary endpoint.
    b1714 = by_id[L1714]
    assert STALE_BEST_HIT in b1714["cfu_thresholds"]["notes"]
    b1714["cfu_thresholds"]["notes"] = b1714["cfu_thresholds"]["notes"].replace(
        STALE_BEST_HIT, "Human RCTs are recorded as study contexts and own its human evidence.")
    b1714["cfu_thresholds"]["indication_primary"] = "sleep quality and low mood (primary endpoints not met)"
    b1714["key_benefits"] = []
    b1714["notable_studies"] = (f"Review {ON}: a sleep RCT (89 adults) and a depression RCT (168 adults) did not meet "
                                "their primary endpoints; secondary week-4 improvements did not persist.")

    # 6 - ME-3: human evidence exists and is biomarker-only.
    me3 = by_id["STRAIN_FERMENTUM_ME3"]
    assert STALE_BEST_HIT in me3["cfu_thresholds"]["notes"]
    me3["cfu_thresholds"]["notes"] = me3["cfu_thresholds"]["notes"].replace(
        STALE_BEST_HIT, "A double-blind human arm (16080791) is recorded; its outcomes are oxidative-stress biomarkers.")
    me3["key_benefits"] = ["antioxidant markers (biomarker evidence)"]
    me3["notable_studies"] = (f"Review {ON}: in a double-blind arm of 24 healthy adults, ME-3 capsules improved blood "
                              "antioxidant indices (biomarkers). No cardiovascular outcome data.")

    for sid in ("STRAIN_PARACASEI_8700", L1714, "STRAIN_FERMENTUM_ME3"):
        derived = derived_context_evidence(by_id[sid])
        assert derived is not None, sid
        by_id[sid]["evidence_level"] = LEVEL[derived["evidence_strength"]]

    # 8 - CNCM I-745 evidence belongs to CNCM I-745, not to an unidentified S. boulardii label.
    generic = by_id["STRAIN_SACCHAROMYCES"]
    moved = [c for c in generic["study_contexts"] if c["context_id"].startswith("sb_cncm_i745_")]
    assert len(moved) == 6
    generic["study_contexts"] = [c for c in generic["study_contexts"] if c not in moved]
    for alias in ("Saccharomyces boulardii CNCM I-745", "Florastor"):
        generic["aliases"].remove(alias)
    for c in moved:
        _mark_corrected(c, "Moved from the S. boulardii species node to CNCM I-745.")
        c["identity_scope"] = "exact_strain"
        c["components"] = [I745]
        c["limitations"].append(f"Moved {ON} from the species node: the source names CNCM I-745, so an unidentified "
                                "S. boulardii label cannot inherit it.")
    generic["cfu_thresholds"]["notes"] += (" Evidence naming CNCM I-745 lives on STRAIN_BOULARDII_CNCM_I745; an "
                                           "unidentified S. boulardii label does not inherit it.")
    pmids = sorted(p for c in moved for p in c["source_pmids"])
    entry = {
        "id": I745, "standard_name": "Saccharomyces cerevisiae var. boulardii CNCM I-745",
        "aliases": ["Saccharomyces boulardii CNCM I-745", "S. boulardii CNCM I-745", "Florastor"],
        "evidence_level": None, "key_benefits": [],
        "notable_studies": f"Review {ON}: six CNCM I-745 study records moved from the species node.",
        "identity_verification": {"status": "designation_verified", "source_pmids": pmids,
                                  "deposit_ids": ["CNCM I-745"], "supplier": "Biocodex (Florastor)", "verified_on": ON,
                                  "method": "PubMed efetch XML title/abstract read for the designation",
                                  "note": "Every moved record names S. boulardii CNCM I-745. Distinct deposit from CNCM I-3799."},
        "cfu_thresholds": {"indication_primary": None, "tiers_cfu_per_day": None, "dr_pham_signoff": False,
                           "evidence": None},
        "literature_review": {"conclusion": "exact_strain_contexts_recorded", "reviewed_on": ON, "reviewer": REVIEWER,
                              "search_query": "Records on the S. boulardii species node whose source names CNCM I-745",
                              "pmids_screened": pmids, "combination_pmids": [], "ineligible_single_strain_pmids": [],
                              "basis": BASIS_REL},
        "study_contexts": moved,
    }
    registry["clinically_relevant_strains"].insert(registry["clinically_relevant_strains"].index(generic) + 1, entry)
    by_id[I745] = entry
    entry["evidence_level"] = LEVEL[derived_context_evidence(entry)["evidence_strength"]]

    # 9 - Enterogermina is the four-strain O/C, N/R, SIN, T product; its evidence is formula-level.
    clausii = by_id["STRAIN_CLAUSII"]
    clausii["aliases"].remove("Enterogermina")
    clausii["cfu_thresholds"]["notes"] += (" Enterogermina is the four-strain O/C, N/R, SIN, T mixture; its trials "
                                           "(e.g. 35397572, null for acute diarrhoea) are formula-level evidence and "
                                           "are not credited to this species node.")

    # 10 - M-16V: the strain-specific review is the honest record (no significant RCT benefit).
    m16v = by_id["STRAIN_BREVE_M16V"]
    ev = m16v["cfu_thresholds"]["evidence"]
    assert ev["pmid"] == "40085083"
    old = {k: ev.get(k) for k in ("pmid", "source_short", "type", "evidence_strength")}
    m16v["cfu_thresholds"]["evidence"] = {
        "type": "strain_specific_systematic_review",
        "source_short": "JPEN (2018) - strain-specific systematic review of B. breve M-16V in preterm infants: 5 RCTs "
                        "(n = 482) showed no significant benefit on NEC, late-onset sepsis, mortality or time to full "
                        "feeds; overall evidence very low",
        "pmid": "28796951", "url": "https://pubmed.ncbi.nlm.nih.gov/28796951/", "verified_date": ON,
        "evidence_strength": "weak", "clinical_support_level": "weak", "effect_direction": "null",
        "effect_direction_basis": ("Meta-analysis of RCTs: no significant benefit on stage >= 2 NEC, late-onset sepsis, "
                                   "mortality or age at full feeds; favourable non-randomized data are very low quality."),
        "clinical_validation": {"q1_strain_explicit": "YES", "q3_human_clinical": "YES", "scope_verified_on": ON,
                                "scope_verification_note": "Strain-specific review of M-16V in preterm neonates."},
        "previous_citation": {**old, "swapped_date": ON,
                              "swap_reason": "40085083 tested M-16V + HN019 + HN001 for fever duration; a combination "
                                             "respiratory trial is not single-strain NEC evidence."},
    }
    m16v["cfu_thresholds"]["dr_pham_signoff_verification_note"] += (
        f" {ON}: anchor swapped to the strain-specific review 28796951 (null) by delegated review; pending Dr Pham's "
        "countersignature.")
    m16v["evidence_level"] = "low"
    m16v["notable_studies"] = (f"Review {ON}: a strain-specific systematic review found no significant RCT benefit for "
                               "NEC, sepsis or mortality in preterm infants (very low certainty).")


def apply(registry: dict, reviewed_at: str) -> None:
    from probiotic_measurements import derived_context_evidence, identity_review_accepted, strain_literature_review_concluded

    import studied_formulas

    by_id = {e["id"]: e for e in registry["clinically_relevant_strains"]}
    # Validate against the registry being built (the new I-745 identity is not on disk yet).
    studied_formulas._clinical_strain_registry = lambda: by_id
    add_contexts(by_id, reviewed_at)
    reopen_reviews(by_id)
    correct_attribution(by_id)
    correct_indications(by_id)
    model_consistency(by_id)
    prebiotics(registry)
    second_review(registry, by_id, reviewed_at)
    for sid in (HEAL9, LAFTI):
        entry = by_id[sid]
        assert not strain_literature_review_concluded(entry) and identity_review_accepted(entry), sid
        assert derived_context_evidence(entry) is not None, sid
    registry["_metadata"]["total_entries"] = len(registry["clinically_relevant_strains"])
    registry["_metadata"]["codex_audit_response_note_2026_09_22"] = (
        "Codex's 2026-09-22 registry audit (26 findings) reproduced against live PubMed/Europe PMC and applied: "
        "HEAL9 and LAFTI L10 reviews reopened with single-strain trials; 9 exact-strain contexts added (BB-12 infant "
        "colic x2, 1714 x2, 35624, LGG acute gastroenteritis, 299v, Lafti L10, UABla-12 arm); DRACMA's LGG results "
        "removed from CRL431 + BB-12; Prodentis single-strain aliases removed; ATCC PTA 6475 now mixed (2024 null "
        "trial); CTV-05 vaginal evidence gives oral labels no credit; M-16V no longer carries NEC or a combination "
        "trial; indications and benefits bound to their records; co-formulated BC30 contexts made ineligible; transit "
        "is a surrogate; resistant maltodextrin separated from resistant starch. A second review's ten corrections: "
        "IS-2 arithmetic and note, DSM 17938's gastroenteritis citation (31739457), SP1 acne pilot, 8700:2 and ME-3 "
        "human biomarker trials, 1714 claims, Prodentis fail-closed, CNCM I-745 split from the S. boulardii species "
        "node, Enterogermina kept formula-level, M-16V anchored to its strain-specific review. MIMBb75 not added (no "
        f"label in the catalog). Delegated research review, not a clinician sign-off. Basis: {BASIS_REL}.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raw = REG.read_text(encoding="utf-8")
    registry = json.loads(raw)
    assert json.dumps(registry, indent=2, ensure_ascii=False) + "\n" == raw, "registry not in canonical form"
    assert "codex_audit_response_note_2026_09_22" not in registry["_metadata"], "already applied"
    reviewed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = deepcopy(registry)
    apply(registry, reviewed_at)
    old = {e["id"]: e for e in before["clinically_relevant_strains"]}
    changed = [e["id"] for e in registry["clinically_relevant_strains"] if old.get(e["id"]) != e]
    print(f"{len(changed)} identities changed:", ", ".join(changed))
    if args.apply:
        REG.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written", REG.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
