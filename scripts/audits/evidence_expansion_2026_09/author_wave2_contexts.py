#!/usr/bin/env python3
"""Author Wave 2 pending study contexts against the frozen contract (no production write).

Contexts are authored ONLY as ``source_verified_pending_clinical_review``; the
validator is run with ``authoring=True`` so this run cannot mint its own
approval. Every quote is extracted programmatically from the stored live
abstract and asserted to be an exact contiguous substring - a curation run never
retypes a source.

"Not approvable today" is not "do not curate": a null or held identity is
authored in full and its production proposal is marked HOLD with the reason.

    python3 scripts/audits/evidence_expansion_2026_09/author_wave2_contexts.py \
        --candidates-dir <dir> --dose-profiles <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from clinical_evidence_schema import validate_ingredient_context  # noqa: E402

ABSTRACTS: dict[str, str] = {}


def quote(pmid: str, needle: str, *, span: int = 0) -> str:
    """The sentence containing `needle`, asserted to be an exact substring."""
    text = ABSTRACTS[pmid]
    index = text.find(needle)
    if index < 0:
        raise SystemExit(f"QUOTE NOT IN ABSTRACT: {pmid}: {needle!r}")
    start = text.rfind(". ", 0, index)
    start = 0 if start < 0 else start + 2
    end = text.find(". ", index + len(needle))
    end = len(text) if end < 0 else end + 1
    for _ in range(span):
        nxt = text.find(". ", end)
        end = len(text) if nxt < 0 else nxt + 1
    result = text[start:end].strip()
    if result not in text:
        raise SystemExit(f"EXTRACTED QUOTE NOT CONTIGUOUS: {pmid}")
    return result


def base(context_id, pmids, components, scope, identity, condition, purpose, design,
         sample_size, comparator, blinding="double", funding="unreported",
         exposure_basis="supplement_dose", route="oral", evidence_role="direct_rct",
         trial_family=None, population=None, human_status="confirmed",
         source_integrity="none", **extra):
    context = {
        "context_id": context_id,
        "context_schema_version": "1.1.0",
        "source_pmids": list(pmids),
        "components": list(components),
        "identity_scope": scope,
        "identity": identity,
        "exposure_basis": exposure_basis,
        "route": route,
        "evidence_role": evidence_role,
        "component_registration_status": "fully_registered",
        "condition": condition,
        "purpose": purpose,
        "trial_family": trial_family or context_id,
        "population": population or {"age_group": "adult"},
        "study_design": design,
        "blinding": blinding,
        "funding": funding,
        "sample_size": sample_size,
        "comparator": comparator,
        "human_status": human_status,
        "source_integrity": source_integrity,
        "review_status": "source_verified_pending_clinical_review",
        "scoring_eligible": False,
    }
    context.update(extra)
    return context


# The frozen contract requires every context to carry at least one positive dose value.
# A systematic review that states no dose therefore cannot be authored AS a context without
# inventing one. Those syntheses are recorded the way the registry already records
# authoritative sources - on the proposal, with their verified spans - rather than being
# forced into a shape that would need a fabricated number. No field was added to the contract.
DOSE_LESS_SYNTHESES = {
    "d_mannose_recurrent_uti_meta_41004704",
    "common_bean_extract_weight_meta_42066439",
    "devils_claw_low_back_pain_cochrane_26630428",
    "senna_chronic_constipation_otc_review_33767108",
    "globe_artichoke_cardiometabolic_meta_41270328",
    "green_coffee_cardiovascular_meta_34981487",
}


def build() -> list[dict]:
    C = []

    # ---------------- d-mannose: clean, fully curated, HELD on null semantics ----------------
    C.append(base(
        "d_mannose_recurrent_uti_prophylaxis_38587819", ["38587819"], ["d_mannose"],
        "exact_form", {"chemical_form": "d-mannose powder"},
        "recurrent_urinary_tract_infection_prophylaxis_women", "prevention", "rct", 598,
        "placebo", funding="public",
        population={"age_group": "adult", "description":
                    "Women 18 or older living in the community with primary-care records of at least 2 UTIs "
                    "in 6 months or 3 in 12 months; mean age 58"},
        dose={"measurement_type": "mass", "unit": "g", "values": [2], "dose_status": "verified",
              "dose_basis": "nominal_assigned_arm", "duration_basis": "fixed_protocol", "duration_days": 180, "dosage_forms": ["powder"],
              "co_therapies": [],
              "source_provenance": {"pmid": "38587819", "location": "abstract",
                                    "quote": quote("38587819", "Two grams daily of d-mannose powder")}},
        outcomes=[{"name": "medically_attended_clinically_suspected_uti_within_6_months",
                   "hierarchy": "primary", "kind": "patient_important", "direction": "null",
                   "outcome_role": "direct_between_group_effect"},
                  {"name": "symptom_duration_antibiotic_use_time_to_next_uti_hospital_admission",
                   "hierarchy": "secondary", "kind": "patient_important", "direction": "null"}],
        outcome_provenance=[{"pmid": "38587819", "location": "abstract",
                             "quote": quote("38587819", "risk difference, -5%")},
                            {"pmid": "38587819", "location": "abstract",
                             "quote": quote("38587819", "There were no statistically significant differences in any secondary outcome")}],
        limitations=["Primary-care population with a history of recurrent UTI, not general adult use.",
                     "The studied 2 g/day sits at the 75th percentile of the measured catalog label "
                     "distribution (median 1,000 mg), so most products deliver less than the studied exposure."]))
    C.append(base(
        "d_mannose_recurrent_uti_meta_41004704", ["41004704"], ["d_mannose"],
        "exact_form", {"chemical_form": "d-mannose"},
        "recurrent_urinary_tract_infection_prophylaxis", "prevention", "meta_analysis", 1167,
        "placebo_or_antibiotic", blinding="not_applicable", evidence_role="systematic_review",
        population={"age_group": "adult", "description":
                    "Patients at high risk for recurrent UTI; 521 of 534 D-mannose recipients were women"},
        dose={"measurement_type": "mass", "unit": "mg", "reported_regimen": "not stated in the synthesis",
              "dose_status": "source_not_reported", "dose_basis": "not_applicable",
              "duration_basis": "not_recorded", "dosage_forms": [], "co_therapies": []},
        outcomes=[{"name": "recurrent_uti_incidence", "hierarchy": "primary", "kind": "patient_important",
                   "direction": "null", "outcome_role": "direct_between_group_effect"}],
        outcome_provenance=[{"pmid": "41004704", "location": "abstract",
                             "quote": quote("41004704", "D-mannose was not associated with a reduction")}],
        limitations=["The synthesis states no dose, so it cannot establish an applicable exposure by itself.",
                     "Six RCTs of mixed comparators (no intervention or antibiotics) pooled together."],
        included_study_pmids="extraction_pending"))

    # ---------------- white kidney bean extract: the approval candidate ----------------
    C.append(base(
        "common_bean_extract_weight_meta_42066439", ["42066439"], ["common_bean_extract"],
        "botanical_preparation",
        {"botanical_species": "Phaseolus vulgaris", "plant_part": "seed (white kidney bean)",
         "preparation": "oral white kidney bean extract, alpha-amylase inhibitor rich; inhibitor units not standardised across trials"},
        "overweight_and_obesity_body_composition", "treatment", "meta_analysis", 543,
        "placebo", blinding="not_applicable", evidence_role="systematic_review",
        population={"age_group": "adult", "description": "Adults with overweight and obesity"},
        dose={"measurement_type": "mass", "unit": "mg",
              "reported_regimen": "pooled across 8 RCTs; the synthesis states no single dose",
              "dose_status": "source_not_reported", "dose_basis": "not_applicable",
              "duration_basis": "not_recorded", "dosage_forms": [], "co_therapies": []},
        outcomes=[{"name": "body_weight", "hierarchy": "primary", "kind": "patient_important",
                   "direction": "positive", "outcome_role": "direct_between_group_effect"},
                  {"name": "bmi_fat_mass_waist_hip_circumference", "hierarchy": "secondary",
                   "kind": "surrogate", "direction": "positive"},
                  {"name": "fasting_glucose_triglycerides_insulin", "hierarchy": "secondary",
                   "kind": "surrogate", "direction": "null"}],
        outcome_provenance=[{"pmid": "42066439", "location": "abstract",
                             "quote": quote("42066439", "reductions in weight (MD -1.62 kg")},
                            {"pmid": "42066439", "location": "abstract",
                             "quote": quote("42066439", "No significant differences were observed in fasting blood glucose")}],
        limitations=["Eight RCTs and 543 participants is a small pooled base for an ingredient-level claim.",
                     "Alpha-amylase inhibitor extracts are not standardised by inhibitor units, so label "
                     "milligrams do not establish equivalent activity. No potency conversion is proposed."],
        included_study_pmids="extraction_pending"))
    C.append(base(
        "common_bean_extract_phaseolean_rct_39170208", ["39170208"], ["common_bean_extract"],
        "branded_material",
        {"branded_material": "Phaseolean", "standardization": "standardised water extract of Phaseolus vulgaris",
         "botanical_species": "Phaseolus vulgaris", "plant_part": "seed"},
        "overweight_and_obesity_body_composition", "treatment", "rct", 66, "placebo",
        population={"age_group": "adult", "description": "Overweight or obese participants; 62 of 66 completed"},
        dose={"measurement_type": "mass", "unit": "mg", "values": [1500, 3000],
              "dose_status": "verified", "dose_basis": "nominal_assigned_arm",
              "duration_basis": "fixed_protocol", "duration_days": 45, "dosage_forms": ["capsule"], "co_therapies": [],
              "reported_regimen": "500 mg or 1000 mg per meal, three times a day before meals",
              "normalization": {"basis": "The source states the daily totals itself (1,500 and 3,000 mg/day); "
                                "the per-meal regimen is preserved beside them and no conversion was applied."},
              "source_provenance": {"pmid": "39170208", "location": "abstract",
                                    "quote": quote("39170208", "Phaseolean® 1500 mg/day")}},
        outcomes=[{"name": "body_weight", "hierarchy": "primary", "kind": "patient_important",
                   "direction": "positive", "outcome_role": "direct_between_group_effect"},
                  {"name": "bmi_body_fat_skinfold_waist_hip_thigh", "hierarchy": "secondary",
                   "kind": "surrogate", "direction": "positive"}],
        outcome_provenance=[{"pmid": "39170208", "location": "abstract",
                             "quote": quote("39170208", "showing significant differences between the Phaseolean")}],
        limitations=["A branded standardised extract; it supports the ingredient-level synthesis but does not "
                     "establish that every white kidney bean extract is equivalent.",
                     "The lower dose outperformed the higher one, which the source notes without explaining."]))

    # ---------------- amla ----------------
    C.append(base(
        "amla_cardiometabolic_meta_37296402", ["37296402"], ["amla"],
        "botanical_preparation",
        {"botanical_species": "Phyllanthus emblica (Emblica officinalis)", "plant_part": "fruit",
         "preparation": "oral Emblica officinalis fruit preparations, 500-1500 mg/day"},
        "cardiovascular_risk_markers_adults", "treatment", "meta_analysis", 0, "placebo",
        blinding="not_applicable", evidence_role="systematic_review",
        population={"age_group": "adult", "description": "Adults; parallel-group and crossover trials"},
        dose={"measurement_type": "mass", "unit": "mg", "values": [500, 1500],
              "dose_status": "verified", "dose_basis": "nominal_assigned_arm",
              "duration_basis": "participant_specific", "dosage_forms": [], "co_therapies": [],
              "source_provenance": {"pmid": "37296402", "location": "abstract",
                                    "quote": quote("37296402", "EO dosage ranging from 500 mg/day to 1500 mg/day")}},
        outcomes=[{"name": "ldl_cholesterol", "hierarchy": "primary", "kind": "surrogate",
                   "direction": "positive", "outcome_role": "direct_between_group_effect"},
                  {"name": "vldl_triglycerides_hscrp", "hierarchy": "secondary",
                   "kind": "surrogate", "direction": "positive"}],
        outcome_provenance=[{"pmid": "37296402", "location": "abstract",
                             "quote": quote("37296402", "significant composite effect at lowering low-density lipoprotein cholesterol")}],
        limitations=["The authors state the results should be interpreted with caution because of statistical "
                     "and clinical heterogeneity in a limited number of trials.",
                     "Endpoints are cardiovascular risk markers, not patient-important outcomes.",
                     "The measured catalog label median is 120 mg/day, far below the studied 500-1500 mg range."],
        included_study_pmids="extraction_pending"))

    # ---------------- devil's claw ----------------
    C.append(base(
        "devils_claw_low_back_pain_cochrane_26630428", ["26630428"], ["devils_claw"],
        "botanical_preparation",
        {"botanical_species": "Harpagophytum procumbens", "plant_part": "root/tuber",
         "preparation": "oral extract standardised to harpagoside content; the review states no extract-milligram equivalent"},
        "nonspecific_low_back_pain", "treatment", "meta_analysis", 2050, "placebo",
        blinding="not_applicable", evidence_role="systematic_review",
        population={"age_group": "adult",
                    "description": "Adults over 18 with acute, sub-acute or chronic non-specific low back pain"},
        dose={"measurement_type": "mass", "unit": "mg",
              "reported_regimen": "standardised to harpagoside content; no extract-milligram dose stated",
              "dose_status": "source_not_reported", "dose_basis": "not_applicable",
              "duration_basis": "not_recorded", "dosage_forms": [], "co_therapies": []},
        outcomes=[{"name": "low_back_pain", "hierarchy": "primary", "kind": "patient_important",
                   "direction": "positive", "outcome_role": "direct_between_group_effect"}],
        outcome_provenance=[{"pmid": "26630428", "location": "abstract",
                             "quote": quote("26630428", "Harpagophytum procumbens (devil's claw)")}],
        limitations=["The review's own grading is that the evidence for devil's claw was of moderate quality at best.",
                     "Trials dose by harpagoside content while labels print extract milligrams; no conversion is "
                     "proposed and none may be inferred.",
                     "The 2007 Cochrane version (PMID 17202897) is superseded and carries an erratum; it is not cited."],
        included_study_pmids="extraction_pending"))

    # ---------------- senna ----------------
    C.append(base(
        "senna_chronic_constipation_otc_review_33767108", ["33767108"], ["senna"],
        "botanical_preparation",
        {"botanical_species": "Senna alexandrina", "plant_part": "leaf",
         "preparation": "oral senna; dosed as sennosides, which the reviews do not convert to extract milligrams"},
        "chronic_constipation", "treatment", "meta_analysis", 0, "placebo_or_active",
        blinding="not_applicable", evidence_role="systematic_review",
        population={"age_group": "adult", "description": "Adults with chronic constipation using OTC products"},
        dose={"measurement_type": "mass", "unit": "mg",
              "reported_regimen": "sennoside dosing; no extract-milligram equivalent stated",
              "dose_status": "source_not_reported", "dose_basis": "not_applicable",
              "duration_basis": "not_recorded", "dosage_forms": [], "co_therapies": []},
        outcomes=[{"name": "chronic_constipation_relief", "hierarchy": "primary",
                   "kind": "patient_important", "direction": "positive",
                   "outcome_role": "direct_between_group_effect"}],
        outcome_provenance=[{"pmid": "33767108", "location": "abstract",
                             "quote": quote("33767108", "We found good evidence to recommend polyethylene glycol or senna")}],
        limitations=["Senna is a stimulant laxative: the same reviews report diarrhoea, nausea, bloating and "
                     "abdominal pain as common adverse events, and long-term use raises dependence and "
                     "electrolyte concerns. Routed to the safety owner.",
                     "Dosed by sennoside content; all 15 catalog rows print 150 mg of senna leaf extract and no "
                     "conversion may be inferred."],
        included_study_pmids="extraction_pending"))

    # ---------------- d-aspartic acid: fully curated, null, HELD ----------------
    C.append(base(
        "d_aspartic_acid_testosterone_trained_men_28841667", ["28841667"], ["d_aspartic_acid"],
        "exact_form", {"chemical_form": "d-aspartic acid"},
        "basal_testosterone_resistance_trained_men", "treatment", "rct", 22, "placebo",
        population={"age_group": "adult",
                    "description": "Healthy resistance-trained men aged 18-36 with at least 2 years of training"},
        dose={"measurement_type": "mass", "unit": "g", "values": [6], "dose_status": "verified",
              "dose_basis": "nominal_assigned_arm", "duration_basis": "fixed_protocol", "duration_days": 84,
              "dosage_forms": [], "co_therapies": [],
              "source_provenance": {"pmid": "28841667", "location": "abstract",
                                    "quote": quote("28841667", "D-aspartic acid (6 g.d-1, DAA)")}},
        outcomes=[{"name": "basal_total_and_free_testosterone", "hierarchy": "primary",
                   "kind": "surrogate", "direction": "null",
                   "outcome_role": "direct_between_group_effect"},
                  {"name": "estradiol", "hierarchy": "secondary", "kind": "surrogate",
                   "direction": "negative"}],
        outcome_provenance=[{"pmid": "28841667", "location": "abstract",
                             "quote": quote("28841667", "No change in basal TT or FT were observed")}],
        limitations=["22 participants.",
                     "The studied 6 g/day is 2.5x the measured catalog label median of 2,400 mg."]))
    C.append(base(
        "d_aspartic_acid_hpg_axis_climbers_29893592", ["29893592"], ["d_aspartic_acid"],
        "exact_form", {"chemical_form": "d-aspartic acid"},
        "hypothalamic_pituitary_gonadal_biomarkers_male_athletes", "treatment", "crossover_rct", 16,
        "placebo", blinding="single",
        population={"age_group": "adult", "description": "Male climbers maintaining normal weekly training"},
        dose={"measurement_type": "mass", "unit": "g", "values": [3], "dose_status": "verified",
              "dose_basis": "nominal_assigned_arm", "duration_basis": "fixed_protocol", "duration_days": 14,
              "dosage_forms": [], "co_therapies": [],
              "source_provenance": {"pmid": "29893592", "location": "abstract",
                                    "quote": quote("29893592", "a DAA (3 g/day) or placebo")}},
        outcomes=[{"name": "serum_testosterone_free_testosterone_luteinizing_hormone", "hierarchy": "primary",
                   "kind": "surrogate", "direction": "null",
                   "outcome_role": "direct_between_group_effect"}],
        outcome_provenance=[{"pmid": "29893592", "location": "abstract",
                             "quote": quote("29893592", "The DAA supplement did not significantly affect serum T")}],
        limitations=["16 participants, single-blinded.",
                     "Short 2-week exposure."]))

    # ---------------- schisandra: evidence ready, blocked upstream ----------------
    C.append(base(
        "schisandra_muscle_strength_older_adults_33710261", ["33710261"], ["schisandra_berry"],
        "botanical_preparation",
        {"botanical_species": "Schisandra chinensis", "plant_part": "fruit",
         "preparation": "Schisandra chinensis Baillon extract"},
        "skeletal_muscle_strength_older_adults", "treatment", "rct", 0, "placebo",
        population={"age_group": "older_adult",
                    "description": "Older adults performing regular low-intensity walking, 30-60 min/day on at least 3 days/week"},
        dose={"measurement_type": "mass", "unit": "g", "values": [1], "dose_status": "verified",
              "dose_basis": "nominal_assigned_arm", "duration_basis": "fixed_protocol", "duration_days": 84,
              "dosage_forms": [], "co_therapies": ["low-intensity walking programme in both arms"],
              "source_provenance": {"pmid": "33710261", "location": "abstract",
                                    "quote": quote("33710261", "received either 1 g SCe/d or a placebo")}},
        outcomes=[{"name": "knee_extensor_strength", "hierarchy": "primary", "kind": "surrogate",
                   "direction": "positive", "outcome_role": "direct_between_group_effect"},
                  {"name": "muscle_mass_inflammatory_and_antioxidative_markers_quality_of_life",
                   "hierarchy": "secondary", "kind": "surrogate", "direction": "null"}],
        outcome_provenance=[{"pmid": "33710261", "location": "abstract",
                             "quote": quote("33710261", "higher increase in right knee extensor strength")},
                            {"pmid": "33710261", "location": "abstract",
                             "quote": quote("33710261", "no differences were observed in the muscle mass")}],
        limitations=["Strength improved but muscle mass did not, and quality of life did not.",
                     "Studied at 1 g/day against a measured catalog label median of 175 mg.",
                     "Every catalog row for this identity is classified recognized_non_scorable upstream, so this "
                     "record would reach no product until that classification changes."]))

    # ---------------- globe artichoke: evidence ready, blocked upstream ----------------
    C.append(base(
        "globe_artichoke_cardiometabolic_meta_41270328", ["41270328"], ["globe_artichoke"],
        "botanical_preparation",
        {"botanical_species": "Cynara scolymus", "plant_part": "leaf",
         "preparation": "oral artichoke supplementation; the synthesis states no single dose"},
        "cardiometabolic_risk_markers_adults", "treatment", "meta_analysis", 0, "placebo",
        blinding="not_applicable", evidence_role="systematic_review",
        population={"age_group": "adult",
                    "description": "Adults; the largest effects concentrate in NAFLD and hypertensive subgroups"},
        dose={"measurement_type": "mass", "unit": "mg",
              "reported_regimen": "not stated in the synthesis", "dose_status": "source_not_reported",
              "dose_basis": "not_applicable", "duration_basis": "not_recorded",
              "dosage_forms": [], "co_therapies": []},
        outcomes=[{"name": "total_and_ldl_cholesterol_triglycerides", "hierarchy": "primary",
                   "kind": "surrogate", "direction": "positive",
                   "outcome_role": "direct_between_group_effect"},
                  {"name": "insulin_and_homa_ir_alt_alp", "hierarchy": "secondary",
                   "kind": "surrogate", "direction": "positive"},
                  {"name": "fasting_blood_glucose_hba1c_hdl_creatinine", "hierarchy": "secondary",
                   "kind": "surrogate", "direction": "null"}],
        outcome_provenance=[{"pmid": "41270328", "location": "abstract",
                             "quote": quote("41270328", "Artichoke supplementation may offer modest but significant")},
                            {"pmid": "41270328", "location": "abstract",
                             "quote": quote("41270328", "whereas fasting blood glucose and HbA1c were unaffected")}],
        limitations=["All endpoints are clinical biomarkers, not patient-important outcomes.",
                     "No dose is stated, so no dose policy can be proposed.",
                     "Every catalog row for this identity is classified recognized_non_scorable upstream, so this "
                     "record would reach no product until that classification changes."],
        included_study_pmids="extraction_pending"))

    # ---------------- green coffee bean: integrity-checked ----------------
    C.append(base(
        "green_coffee_cardiovascular_meta_34981487", ["34981487"], ["green_coffee_bean"],
        "botanical_preparation",
        {"botanical_species": "Coffea (unroasted bean)", "plant_part": "seed (green coffee bean)",
         "preparation": "green coffee bean extract; chlorogenic-acid standardisation varies across trials"},
        "cardiovascular_risk_factors_adults", "treatment", "meta_analysis", 637, "placebo",
        blinding="not_applicable", evidence_role="systematic_review",
        population={"age_group": "adult", "description": "Adults across 15 studies and 19 arms"},
        dose={"measurement_type": "mass", "unit": "mg",
              "reported_regimen": "not stated in the synthesis", "dose_status": "source_not_reported",
              "dose_basis": "not_applicable", "duration_basis": "not_recorded",
              "dosage_forms": [], "co_therapies": []},
        outcomes=[{"name": "total_cholesterol", "hierarchy": "primary", "kind": "surrogate",
                   "direction": "positive", "outcome_role": "direct_between_group_effect"},
                  {"name": "fasting_plasma_glucose_blood_pressure_body_weight_bmi", "hierarchy": "secondary",
                   "kind": "surrogate", "direction": "positive"},
                  {"name": "triglycerides_hdl_hba1c_homa_ir", "hierarchy": "secondary",
                   "kind": "surrogate", "direction": "null"}],
        outcome_provenance=[{"pmid": "34981487", "location": "abstract",
                             "quote": quote("34981487", "significantly reduced levels of total cholesterol")},
                            {"pmid": "34981487", "location": "abstract",
                             "quote": quote("34981487", "No significant effect was detected for triglycerides")}],
        limitations=["Integrity check performed 2026-09-18: this synthesis's PubMed-indexed reference list "
                     "(33 references) does NOT contain the retracted green-coffee trial PMID 22291473. The other "
                     "three selected green coffee sources have no indexed reference list, so the same check could "
                     "not be run on them and they are excluded from this record.",
                     "Effect sizes are small and several were driven by individual studies on the authors' own "
                     "sensitivity analysis.",
                     "Chlorogenic acid content, not extract milligrams, is the studied potency axis."],
        included_study_pmids="extraction_pending"))

    return C


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates-dir", required=True, type=Path)
    args = parser.parse_args()
    for path in sorted(args.candidates_dir.glob("*.json")):
        for record in json.loads(path.read_text())["records"]:
            ABSTRACTS[record["pmid"]] = record.get("abstract") or ""

    built = build()
    contexts = [c for c in built if c["context_id"] not in DOSE_LESS_SYNTHESES]
    syntheses = []
    for c in built:
        if c["context_id"] not in DOSE_LESS_SYNTHESES:
            continue
        record = {k: v for k, v in c.items() if k != "dose"}
        record["recorded_as"] = "authoritative_synthesis_reference"
        record["why_not_a_context"] = (
            "The frozen context contract requires at least one positive dose value. This synthesis "
            "states no dose, and inventing one is forbidden, so it is recorded on the proposal as a "
            "verified source rather than as a study context.")
        record["dose_as_reported"] = c["dose"].get("reported_regimen")
        syntheses.append(record)
    known = {c for ctx in built for c in ctx["components"]}
    failures = 0
    by_identity: dict[str, list[dict]] = {}
    for ctx in contexts:
        errors = validate_ingredient_context(ctx, known_component_ids=known, authoring=True)
        if errors:
            failures += 1
            print(f"  FAIL {ctx['context_id']}: {errors}")
        by_identity.setdefault(ctx["components"][0], []).append(ctx)
    payload = {"_metadata": {
        "wave": "evidence-expansion Wave 2 (2026-09)",
        "status": "AUTHORED, PENDING OWNER REVIEW - nothing here is applied, scored or written to scripts/data",
        "contract": "scripts/clinical_evidence_schema.py validate_ingredient_context (schema 1.1.0 + ingredient lane), authoring=True",
        "review_status_policy": "Every context is source_verified_pending_clinical_review. Approval is the owner's act.",
        "quote_policy": "Every quote was extracted programmatically from the stored live abstract and asserted to be an exact contiguous substring. No quote was retyped.",
        "not_approvable_is_not_uncurated": "Identities whose production proposal is HELD (null direction, upstream blockage, preparation unresolved) are authored in full anyway; the hold is recorded on the proposal, not by leaving the evidence uncurated.",
        "dose_less_synthesis_policy": (
            "A systematic review that states no dose is recorded as a verified source on the proposal, "
            "not as a study context: the frozen contract requires a positive dose value and no number "
            "may be invented to satisfy it."),
        "contexts": len(contexts), "syntheses_recorded_as_references": len(syntheses),
        "identities": len({c for ctx in built for c in ctx["components"]}),
        "validation_failures": failures},
        "contexts_by_identity": by_identity,
        "syntheses_recorded_as_references": syntheses}
    (OUT / "wave2_contexts.json").write_text(json.dumps(payload, indent=1))
    print(json.dumps(payload["_metadata"], indent=1))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
