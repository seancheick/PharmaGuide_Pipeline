#!/usr/bin/env python3
"""Wave 2 clinical curation: author study contexts for thirteen native strain identities.

Every context below was written from a PubMed title/abstract read on
2026-09-14 (PMIDs listed in READ_PMIDS; the full per-identity read log with
reviewed-but-not-recorded studies is wave2_read_log.md). Doses are recorded
only when the abstract states them; where the retrieved abstract text lost
the exponent the dose is left unresolved. Combination studies are authored
once under one owner and joined to every component through `components`;
they never become individual-strain applicability. Null and negative
results are kept.

No identity stubs are added in Wave 2: the DDS-1 combination partner
already exists as STRAIN_LACTIS_UABla12, and trials whose partner strains
have no registry identity stay reviewed-not-recorded in the read log.

Every context is source_verified_pending_clinical_review: nothing here can
score until a clinician flips it to clinician_approved. The registry is
normalized once to indent=2 / ensure_ascii=False on write (parsed content
is asserted identical before and after, apart from the additions).

    python3 scripts/audits/probiotic_curation_queue_2026_09_13/wave2_contexts.py
"""
from __future__ import annotations
import json, sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from studied_formulas import valid_native_study_context  # noqa: E402
from apply_batch1_disposition import DISPOSITION, _write_path  # noqa: E402

REG = ROOT / "scripts/data/clinically_relevant_strains.json"


RESPONSE = REG.parents[2] / "docs/plans/PROBIOTIC_EVIDENCE_REVIEW_RESPONSE_2026-09-14.json"
OWNER_DECISION_FIELDS = ("review_status", "clinical_review", "scoring_eligible", "rejection_reason")


def _declared_disposition_patches():
    """{context_id: [(field_path, new_value), ...]} declared by later source-bound dispositions,
    in application order: batch-1 first, then the 2026-09-14 review response."""
    patches = {}
    if DISPOSITION.exists():
        for patch in json.loads(DISPOSITION.read_text(encoding="utf-8"))["patches"]:
            patches.setdefault(patch["record_id"], []).append((patch["field_path"], patch["new_value"]))
    if RESPONSE.exists():
        for review in json.loads(RESPONSE.read_text(encoding="utf-8")).get("reviews", {}).values():
            for patch in review.get("patches", []):
                patches.setdefault(patch["record_id"], []).append((patch["field_path"], patch["new_value"]))
    return patches


def _response_decisions():
    """{context_id: decision} from the applied 2026-09-14 review response."""
    if not RESPONSE.exists():
        return {}
    return dict(json.loads(RESPONSE.read_text(encoding="utf-8")).get("decisions", {}))


def _write_path_appending(row, field_path, value):
    """Like _write_path but lets a patch append the next list item (a new outcome)."""
    parts = field_path.split(".")
    current = row
    for offset, raw in enumerate(parts):
        key, _, index = raw.partition("[")
        last = offset == len(parts) - 1
        if index:
            idx = int(index.rstrip("]"))
            seq = current.setdefault(key, [])
            if idx == len(seq) and last:
                seq.append(deepcopy(value))
                return
            if last:
                seq[idx] = deepcopy(value)
                return
            current = seq[idx]
            continue
        if last:
            current[key] = deepcopy(value)
            return
        current = current.setdefault(key, {})


PENDING = "source_verified_pending_clinical_review"
READ_PMIDS = {
    # B. coagulans Unique IS-2
    "31434935", "29695183", "30911991", "34599466", "40456531", "36372047", "41682832", "37686889",
    "35249118", "39866999",
    # B. coagulans MTCC 5856 (LactoSpore)
    "26922379", "29997457", "36862903", "38269290", "37335737",
    # L. acidophilus DDS-1 (+ UABla-12 combinations)
    "32019158", "27207411", "36308983", "33584665", "36071965", "26463725", "20642296",
    # L. plantarum 299v
    "37541528", "30388595", "39271063", "31816981", "32365981", "33015813", "12450890", "28101105",
    "22434095",
    # LA-5 / BB-12 combinations and BB-12-anchored records
    "41255078", "24772726", "17356555", "25588782", "21871144", "30439760", "39102225", "41748464",
    "39271904", "33811784", "39310372", "37020105",
    # L. helveticus R0052 + B. longum R0175
    "20974015", "32989186", "33658952", "37049546",
    # L. rhamnosus GR-1 + L. fermentum RC-14
    "34295831", "30932317", "32325794", "27590374", "31953482",
    # B. coagulans GBI-30, 6086
    "40707016", "31162597", "32318476",
    # B. breve M-16V
    "41515257", "41994268", "39915586",
    # L. plantarum LP01
    "29949873",
}


def ctx(context_id, pmids, *, owner, scope="exact_strain", components=None, age, population, purpose,
        condition, outcomes, family, limitations, basis="unresolved", values=(), forms=(), duration=None,
        co_therapies=(), design, n=None, blinding="unreported", funding="unreported", tier, registration=None,
        comparator=None, measurement_type="viable_count", unit=None):
    for pmid in pmids:
        assert pmid in READ_PMIDS, f"PMID {pmid} was not read this session"
    dose = {
        "basis": basis,
        "unit": unit or {"viable_count": "CFU", "spores": "spores"}.get(measurement_type, "CFU"),
        "values": list(values), "dosage_forms": list(forms),
        "duration_days": duration, "co_therapies": list(co_therapies),
    }
    # Keep the legacy default compact; the explicit field is required when a
    # source uses a non-CFU measurement so it cannot be mistaken for CFU.
    if measurement_type != "viable_count" or unit is not None:
        dose["measurement_type"] = measurement_type
    row = {
        "context_id": context_id,
        "source_pmids": list(pmids),
        "identity_scope": scope,
        "components": list(components or [owner]),
        "population": {"age_group": age, "description": population},
        "purpose": purpose,
        "condition": condition,
        "dose": dose,
        "outcomes": [{"name": name, "hierarchy": hier, "kind": kind, "direction": direction}
                     for name, hier, kind, direction in outcomes],
        "trial_family": family,
        "limitations": list(limitations),
        "review_status": PENDING,
        "study_design": design,
        "sample_size": n,
        "blinding": blinding,
        "funding": funding,
        "source_tier": tier,
        "trial_registration": registration,
        "authored_on": "2026-09-14",
        "authoring_method": "PubMed title/abstract read; Wave 2 bounded search (guidelines, meta-analyses, RCTs)",
    }
    if comparator:
        row["comparator"] = comparator
    return owner, row


PI, SU = "patient_important", "surrogate"
IS2, MTCC, DDS1, V299, LA5, BB12 = (
    "STRAIN_COAGULANS_IS2", "STRAIN_COAGULANS_MTCC5856", "STRAIN_ACIDOPHILUS_DDS1",
    "STRAIN_PLANTARUM_299V", "STRAIN_ACIDOPHILUS_LA5", "STRAIN_LACTIS_BB12")
R0052, R0175, GR1, RC14, GBI30, M16V, LP01 = (
    "STRAIN_HELVETICUS_R0052", "STRAIN_LONGUM_R0175", "STRAIN_RHAMNOSUS_GR1", "STRAIN_FERMENTUM_RC14",
    "STRAIN_COAGULANS_GBI30", "STRAIN_BREVE_M16V", "STRAIN_PLANTARUM_LP01")
LGG, UABLA12, CASEI431 = "STRAIN_LGG", "STRAIN_LACTIS_UABla12", "STRAIN_CASEI_431"

CONTEXTS = [
    # -------------------------------------------------- B. coagulans Unique IS-2
    ctx("is2_adult_ibs_multicenter_31434935", ["31434935"], owner=IS2, age="adult",
        population="136 adults with Rome III IBS randomized (153 enrolled), multicenter, India",
        purpose="treatment", condition="irritable_bowel_syndrome",
        basis="discrete_daily_arms", values=[2e9], duration=56,
        outcomes=[("abdominal_pain_and_discomfort", "primary", PI, "positive"),
                  ("complete_spontaneous_bowel_movements", "primary", PI, "positive"),
                  ("serum_cytokines", "unresolved", SU, "null")],
        family="unique_is2_adult_ibs_31434935", design="rct", n=136, blinding="double", funding="industry", tier="C",
        limitations=["Manufacturer authorship (Unique Biotech); serum cytokines did not change alongside the symptom improvements."]),
    ctx("is2_pediatric_ibs_chewable_29695183", ["29695183"], owner=IS2, age="child",
        population="141 children 4-12 years with IBS, chewable tablet once daily",
        purpose="treatment", condition="pediatric_irritable_bowel_syndrome", duration=56, forms=["chewable tablet"],
        outcomes=[("abdominal_pain_intensity", "unresolved", PI, "positive")],
        family="unique_is2_pediatric_ibs_29695183", design="rct", n=141, funding="industry", tier="C",
        limitations=["Daily CFU dose not machine-readable in the retrieved abstract; manufacturer-affiliated authors.",
                     "Endpoint hierarchy not stated in the abstract."]),
    ctx("is2_functional_constipation_30911991", ["30911991"], owner=IS2, age="adult",
        population="100 adults with functional constipation, India",
        purpose="treatment", condition="functional_constipation",
        basis="discrete_daily_arms", values=[2e9], duration=28,
        outcomes=[("spontaneous_bowel_movements_3_or_more_per_week", "unresolved", PI, "positive")],
        family="unique_is2_fc_30911991", design="rct", n=100, funding="industry", tier="C",
        registration="CTRI/2017/11/010539",
        limitations=["Manufacturer-affiliated authors; endpoint hierarchy not stated in the abstract."]),
    ctx("is2_constipation_lactulose_cotherapy_34599466", ["34599466"], owner=IS2, age="adult",
        population="150 adults with functional constipation randomized to IS-2 plus lactulose, lactulose alone, or placebo",
        purpose="treatment", condition="functional_constipation",
        basis="discrete_daily_arms", measurement_type="spores", values=[2e9], duration=28,
        co_therapies=["lactulose 10 g/day"],
        comparator="lactulose monotherapy (second active arm) and placebo",
        outcomes=[("stool_frequency_vs_lactulose", "unresolved", PI, "mixed"),
                  ("stool_consistency", "unresolved", PI, "positive"),
                  ("incomplete_evacuation", "unresolved", PI, "positive"),
                  ("abdominal_pain", "unresolved", PI, "positive")],
        family="unique_is2_fc_lactulose_34599466", design="rct", n=150, funding="industry", tier="C",
        registration="CTRI/2018/11/016399",
        limitations=["The stool-frequency advantage over lactulose alone was transient and not significant at end of trial.",
                     "Every active arm contained lactulose; nothing here is monotherapy evidence."]),
    ctx("is2_infrequent_bowel_movements_40456531", ["40456531"], owner=IS2, age="adult",
        population="144 healthy adults with infrequent bowel movements (3-7 complete spontaneous BMs/week)",
        purpose="treatment", condition="infrequent_bowel_movements",
        basis="discrete_daily_arms", values=[2e9], duration=28,
        outcomes=[("bowel_movement_frequency", "unresolved", PI, "positive"),
                  ("stool_consistency", "unresolved", PI, "positive"),
                  ("gastrointestinal_symptoms", "unresolved", PI, "null"),
                  ("quality_of_life", "unresolved", PI, "null"),
                  ("gut_microbiota_composition", "unresolved", SU, "null")],
        family="pepsico_is2_bm_40456531", design="rct", n=144, funding="industry", tier="C",
        registration="NCT05123664",
        limitations=["Sponsor-run (PepsiCo/Nutrasource); frequency effect modest (p=0.037) in a healthy population; symptoms, QoL and microbiota unchanged."]),
    ctx("is2_chronic_constipation_meta_36372047", ["36372047"], owner=IS2, age="adult",
        population="Adults with chronic constipation in 30 probiotic RCTs; strain-level subgroups reported",
        purpose="treatment", condition="chronic_constipation",
        outcomes=[("constipation_response_probiotics_class", "primary", PI, "positive"),
                  ("stool_frequency_is2_subgroup", "unresolved", PI, "null")],
        family="meta_chronic_constipation_36372047", design="meta_analysis", tier="B",
        limitations=["The class-level benefit is not IS-2 evidence: the IS-2 subgroup was NOT significant for stool frequency (species-level B. lactis was).",
                     "Pooled trials overlap the IS-2 constipation RCT contexts already recorded; not an independent confirmation."]),
    ctx("is2_ibs_strain_level_metas_41682832", ["41682832", "37686889"], owner=IS2, age="adult",
        population="Adults with IBS: a 2026 strain-specific meta-analysis and a 2023 outcome-specific network meta-analysis",
        purpose="treatment", condition="irritable_bowel_syndrome",
        outcomes=[("ibs_symptom_efficacy_strain_level", "unresolved", PI, "positive"),
                  ("abdominal_pain_ranking", "unresolved", PI, "positive")],
        family="meta_ibs_rankings_is2", design="meta_analysis", tier="B",
        registration="PROSPERO CRD420251047092 (2026 meta)",
        limitations=["Both analyses pool the same underlying IS-2 trials already recorded (PMIDs 31434935, 29695183); two meta-analyses of one evidence base count once.",
                     "Rankings are indirect strain-level comparisons, not pooled IS-2 effect sizes with certainty grades."]),
    ctx("is2_whey_protein_strength_35249118", ["35249118"], owner=IS2, age="adult",
        population="Resistance-trained males co-supplementing whey protein for 60 days",
        purpose="physiology", condition="protein_absorption_and_muscle_performance",
        basis="discrete_daily_arms", values=[2e9], duration=60, co_therapies=["whey protein 20 g/day"],
        outcomes=[("plasma_bcaa_absorption", "unresolved", SU, "positive"),
                  ("leg_press_strength", "unresolved", PI, "positive"),
                  ("vertical_jump", "unresolved", PI, "positive")],
        family="unique_is2_whey_35249118", design="rct", funding="mixed", tier="D",
        registration="CTRI/2017/03/008117",
        limitations=["Surrogate-heavy; industry co-authors; performance findings from a small trained-athlete sample."]),
    ctx("is2_moderate_covid19_adjunct_39866999", ["39866999"], owner=IS2, age="adult",
        population="56 adults with moderate COVID-19 on standard treatment; three arms (B. coagulans UBBC-07, IS-2, placebo)",
        purpose="treatment", condition="moderate_covid19_adjunctive_care",
        basis="discrete_daily_arms", measurement_type="spores", values=[4e9], duration=14,
        co_therapies=["standard COVID-19 treatment"],
        outcomes=[("serum_ferritin", "unresolved", SU, "positive"),
                  ("d_dimer", "unresolved", SU, "positive"),
                  ("crp_ldh_il6", "unresolved", SU, "null")],
        family="is2_covid_adjunct_39866999", design="rct", n=56, tier="D",
        limitations=["Small three-arm trial (about 19 per arm) with inflammatory-marker surrogates only; ferritin fell in both probiotic arms, D-dimer only in the IS-2 arm.",
                     "The UBBC-07 arm is a different, non-registry strain; published in Cureus.",
                     "2 x 10^9 spores twice daily (4 x 10^9/day)."]),
    # -------------------------------------------- B. coagulans MTCC 5856 (LactoSpore)
    ctx("mtcc5856_ibs_d_pilot_26922379", ["26922379"], owner=MTCC, age="adult",
        population="36 adults with diarrhea-predominant IBS at three centres, India; standard care in both arms",
        purpose="treatment", condition="irritable_bowel_syndrome_diarrhea_predominant",
        basis="discrete_daily_arms", values=[2e9], duration=90, co_therapies=["standard care"],
        outcomes=[("bloating", "unresolved", PI, "positive"),
                  ("vomiting", "unresolved", PI, "positive"),
                  ("diarrhea", "unresolved", PI, "positive"),
                  ("abdominal_pain", "unresolved", PI, "positive"),
                  ("stool_frequency", "unresolved", PI, "positive")],
        family="sabinsa_mtcc5856_ibsd_26922379", design="rct", n=36, funding="industry", tier="D",
        limitations=["Pilot size (n=36); manufacturer-run (Sami/Sabinsa)."]),
    ctx("mtcc5856_mdd_with_ibs_29997457", ["29997457"], owner=MTCC, age="adult",
        population="40 adults with major depressive disorder and IBS, India",
        purpose="treatment", condition="major_depression_with_irritable_bowel_syndrome",
        basis="discrete_daily_arms", measurement_type="spores", values=[2e9], duration=90,
        outcomes=[("hamilton_depression_score", "unresolved", PI, "positive"),
                  ("madrs_score", "unresolved", PI, "positive"),
                  ("ces_d_score", "unresolved", PI, "positive"),
                  ("ibs_quality_of_life", "unresolved", PI, "positive"),
                  ("serum_myeloperoxidase", "unresolved", SU, "positive")],
        family="sabinsa_mtcc5856_mdd_ibs_29997457", design="rct", n=40, funding="industry", tier="D",
        limitations=["Pilot size (n=40); manufacturer-run; a single trial carries every mood endpoint."]),
    ctx("mtcc5856_functional_gas_bloating_36862903", ["36862903"], owner=MTCC, age="adult",
        population="70 adults with functional gas and bloating (66 completed)",
        purpose="treatment", condition="functional_gas_and_bloating",
        basis="discrete_daily_arms", measurement_type="spores", values=[2e9], duration=28,
        outcomes=[("gsrs_indigestion_score", "unresolved", PI, "positive"),
                  ("patient_global_assessment", "unresolved", PI, "positive")],
        family="sabinsa_mtcc5856_bloating_36862903", design="rct", n=70, funding="industry", tier="D",
        limitations=["Manufacturer-run; four-week duration; endpoint hierarchy not stated in the abstract."]),
    ctx("mtcc5856_pediatric_acute_diarrhea_38269290", ["38269290"], owner=MTCC, age="child",
        population="110 children 1-10 years with acute diarrhea; oral rehydration solution and zinc in both arms",
        purpose="treatment", condition="pediatric_acute_gastroenteritis", basis="discrete_daily_arms",
        measurement_type="spores", values=[8e8], forms=["sachet"], duration=5,
        co_therapies=["oral rehydration solution", "zinc"],
        outcomes=[("diarrhea_duration", "unresolved", PI, "positive"),
                  ("stool_frequency", "unresolved", PI, "null")],
        family="mtcc5856_pediatric_diarrhea_38269290", design="rct", n=110, funding="industry", tier="C",
        registration="CTRI/2022/06/043239",
        limitations=["Duration fell (51.3 vs 62.7 h, p=0.011) but stool frequency did not differ.",
                     "Each sachet contained 4 x 10^8 spores and was taken twice daily (8 x 10^8 spores/day); ORS and zinc were co-therapies."]),
    ctx("mtcc5856_healthy_microbiome_37335737", ["37335737"], owner=MTCC, age="adult",
        population="30 healthy adults; microbiome and safety study",
        purpose="physiology", condition="gut_microbiome_composition", duration=28,
        outcomes=[("gut_microbiome_composition", "unresolved", SU, "null")],
        family="sabinsa_mtcc5856_microbiome_37335737", design="rct", n=30, funding="industry", tier="D",
        limitations=["Gut microbiome composition essentially unchanged; the abstract states 2 x 10^9 CFU per capsule without capsules/day, so the daily dose is unresolved."]),
    ctx("mtcc5856_ibs_strain_level_metas_41682832", ["41682832", "37686889"], owner=MTCC, age="adult",
        population="Adults with IBS: a 2026 strain-specific meta-analysis and a 2023 outcome-specific network meta-analysis",
        purpose="treatment", condition="irritable_bowel_syndrome",
        outcomes=[("ibs_quality_of_life", "unresolved", PI, "positive"),
                  ("abdominal_pain_ranking", "unresolved", PI, "positive"),
                  ("ibs_d_stool_form_ranking", "unresolved", PI, "positive")],
        family="meta_ibs_rankings_mtcc5856", design="meta_analysis", tier="B",
        registration="PROSPERO CRD420251047092 (2026 meta)",
        limitations=["Both analyses pool the same underlying MTCC 5856 trials already recorded (PMIDs 26922379, 29997457); two meta-analyses of one evidence base count once.",
                     "Rankings are indirect strain-level comparisons, not pooled effect sizes with certainty grades."]),
    # ------------------------------------------------------ L. acidophilus DDS-1
    ctx("dds1_ibs_three_arm_32019158", ["32019158"], owner=DDS1, age="adult",
        population="330 adults with IBS randomized across placebo, DDS-1 and UABla-12 solo arms",
        purpose="treatment", condition="irritable_bowel_syndrome", duration=42,
        outcomes=[("abdominal_pain_severity_nrs", "primary", PI, "positive"),
                  ("ibs_severity_score", "unresolved", PI, "positive")],
        family="uas_dds1_uabla12_ibs_32019158", design="rct", n=330, funding="industry", tier="C",
        limitations=["Manufacturer-run (UAS Labs); the daily CFU dose is printed with a stripped exponent in the retrieved abstract and is recorded as unresolved.",
                     "Only the DDS-1 solo arm is recorded here; the UABla-12 solo arm remains future curation under its own identity."]),
    ctx("dds1_lactose_intolerance_crossover_27207411", ["27207411"], owner=DDS1, age="adult",
        population="Adults with lactose intolerance; crossover with 4-week arms, washout, and a 6-hour lactose challenge",
        purpose="challenge", condition="lactose_intolerance", duration=28,
        outcomes=[("challenge_diarrhea_score", "unresolved", PI, "positive"),
                  ("abdominal_cramping", "unresolved", PI, "positive"),
                  ("vomiting", "unresolved", PI, "positive"),
                  ("overall_symptom_score", "unresolved", PI, "positive")],
        family="dds1_lactose_intolerance_27207411", design="crossover_rct", funding="industry", tier="D",
        limitations=["Dose not stated in the abstract; industry authorship (Nebraska Cultures); sample size not stated in the abstract."]),
    ctx("dds1_lactose_intolerance_sr_36308983", ["36308983"], owner=DDS1, age="adult",
        population="Adults with lactose intolerance in a systematic review of probiotic trials",
        purpose="treatment", condition="lactose_intolerance",
        outcomes=[("lactose_intolerance_symptoms", "unresolved", PI, "positive")],
        family="dds1_lactose_intolerance_27207411", design="systematic_review", tier="B",
        registration="PROSPERO CRD42022295691",
        limitations=["LOW certainty; no pooling was possible; the review's DDS-1 evidence is the crossover trial already recorded (PMID 27207411), so this shares its trial family."]),
    ctx("dds1_night_shift_stress_markers_33584665", ["33584665"], owner=DDS1, age="adult",
        population="Night-shift workers, DDS-1 solo arm (29 per arm), 14 days",
        purpose="physiology", condition="anticipatory_stress_markers_night_shift", duration=14,
        outcomes=[("pre_shift_anticipatory_stress_markers", "unresolved", SU, "positive"),
                  ("stress_marker_night_shift_interactions", "unresolved", SU, "null")],
        family="dds1_night_shift_33584665", design="rct", tier="D",
        registration="ANZCTR 12617001552370",
        limitations=["Serum stress markers are surrogates; pre-shift moderation without interaction effects across the night shift makes the record mixed.",
                     "Only the DDS-1 solo arm of a multi-arm trial is recorded here; total trial size not captured."]),
    ctx("dds1_ibs_network_meta_37686889", ["37686889"], owner=DDS1, age="adult",
        population="Adults with IBS in a 2023 outcome-specific network meta-analysis",
        purpose="treatment", condition="irritable_bowel_syndrome",
        outcomes=[("ibs_severity_score_ranking", "unresolved", PI, "positive")],
        family="uas_dds1_uabla12_ibs_32019158", design="meta_analysis", tier="B",
        limitations=["DDS-1 ranked first for IBS-SSS improvement (SUCRA 92.9%), an indirect ranking resting on the single DDS-1 IBS RCT already recorded (PMID 32019158); shares its trial family."]),
    ctx("dds1_uabla12_pediatric_constipation_36071965", ["36071965"], owner=DDS1, scope="combination",
        components=[DDS1, UABLA12], age="child",
        population="92 children with functional constipation, chewable tablet",
        purpose="treatment", condition="pediatric_functional_constipation",
        basis="discrete_daily_arms", values=[5e9], duration=28, forms=["chewable tablet"],
        outcomes=[("stool_frequency_normalization_time", "unresolved", PI, "positive")],
        family="dds1_uabla12_pediatric_fc_36071965", design="rct", n=92, blinding="single", funding="industry", tier="D",
        limitations=["Single-blind; industry involvement (Sirio/Chr. Hansen).",
                     "5 x 10^9 CFU/day is the two-strain combination total, never an individual dose."]),
    ctx("dds1_uabla12_fos_pediatric_ari_26463725", ["26463725"], owner=DDS1, scope="combination",
        components=[DDS1, UABLA12], age="child",
        population="315 children randomized (225 analyzed) with household exposure to acute respiratory infection",
        purpose="prevention", condition="pediatric_acute_respiratory_infections",
        basis="discrete_daily_arms", values=[5e9], co_therapies=["fructooligosaccharide"],
        outcomes=[("ari_incidence", "primary", PI, "null"),
                  ("symptom_resolution_time", "secondary", PI, "positive"),
                  ("ari_severity", "secondary", PI, "positive")],
        family="gerasimov_dds1_uabla12_ari_26463725", design="rct", n=315, tier="C",
        limitations=["Primary incidence endpoint null (57% vs 65%, p=0.261); only resolution time and severity differed.",
                     "Synbiotic with fructooligosaccharide; 5 x 10^9 CFU/day is the combination total."]),
    ctx("dds1_uabla12_fos_atopic_dermatitis_20642296", ["20642296"], owner=DDS1, scope="combination",
        components=[DDS1, UABLA12], age="child",
        population="90 children 1-3 years with moderate-to-severe atopic dermatitis",
        purpose="treatment", condition="pediatric_atopic_dermatitis",
        basis="discrete_daily_arms", values=[1e10], duration=56, co_therapies=["fructooligosaccharide"],
        outcomes=[("scorad_percentage_decrease", "unresolved", PI, "positive"),
                  ("topical_corticosteroid_use", "unresolved", PI, "positive")],
        family="gerasimov_dds1_uabla12_ad_20642296", design="rct", n=90, tier="C",
        limitations=["Synbiotic with fructooligosaccharide; 5 x 10^9 CFU twice daily (1 x 10^10/day) is the combination total.",
                     "SCORAD reported as percentage decrease (33.7% vs 19.4%)."]),
    # --------------------------------------------------------- L. plantarum 299v
    ctx("lp299v_ibs_meta_37541528", ["37541528"], owner=V299, age="adult",
        population="Adults with IBS in an 82-RCT (n=10,332) systematic review and meta-analysis",
        purpose="treatment", condition="irritable_bowel_syndrome",
        outcomes=[("ibs_global_symptom_improvement", "unresolved", PI, "positive")],
        family="meta_299v_ibs_37541528", design="meta_analysis", tier="B",
        limitations=["The 299v-specific conclusion is graded LOW certainty by the reviewers; no 299v RCT is separately recorded this wave, so this meta is the strain's IBS record."]),
    ctx("lp299v_mdd_ssri_cognition_30388595", ["30388595", "39271063"], owner=V299, age="adult",
        population="79 adults with major depressive disorder randomized (60 analyzed) as SSRI augmentation for 8 weeks, Poland",
        purpose="treatment", condition="cognitive_symptoms_in_major_depression", duration=56,
        co_therapies=["SSRI antidepressant"],
        outcomes=[("attention_and_perceptivity_test", "unresolved", PI, "positive"),
                  ("california_verbal_learning_test", "unresolved", PI, "positive"),
                  ("plasma_kynurenine", "unresolved", SU, "positive"),
                  ("depression_severity_between_groups", "unresolved", PI, "unresolved")],
        family="sanprobi_299v_mdd_cognition", design="rct", n=79, tier="D",
        limitations=["Cognition-scoped record: the abstract does not report a between-group depression-severity improvement.",
                     "The metabolomics companion (PMID 39271063) is the same cohort; one trial family.",
                     "Dose not stated in the retrieved abstracts."]),
    ctx("lp299v_iron_absorption_meta_31816981", ["31816981"], owner=V299, age="adult",
        population="8 studies (n=950) of 299v and iron absorption or iron status",
        purpose="physiology", condition="iron_absorption",
        outcomes=[("iron_absorption", "primary", SU, "positive"),
                  ("iron_status_markers", "unresolved", SU, "null")],
        family="meta_299v_iron_absorption_31816981", design="meta_analysis", tier="B",
        limitations=["Absorption (SMD 0.55) is an acute surrogate; the longer iron-status studies were mostly unchanged."]),
    ctx("lp299v_female_athletes_iron_32365981", ["32365981"], owner=V299, age="adult",
        population="53 iron-deficient female athletes randomized (39 completed) to 20 mg iron with or without 299v for 4-12 weeks",
        purpose="treatment", condition="iron_deficiency_female_athletes",
        co_therapies=["iron 20 mg/day"],
        outcomes=[("serum_ferritin", "unresolved", SU, "null"),
                  ("reticulocyte_hemoglobin", "unresolved", SU, "null"),
                  ("poms_vigor", "unresolved", PI, "positive"),
                  ("exercise_performance", "unresolved", PI, "unresolved")],
        family="probi_299v_athletes_iron_32365981", design="rct", n=53, funding="industry", tier="D",
        limitations=["Ferritin (p=0.056) and reticulocyte hemoglobin (p=0.083) missed significance; performance inconclusive; industry involvement (Probi/Nature's Bounty).",
                     "Variable 4-12 week duration; dose not stated in the abstract."]),
    ctx("lp299v_cancer_home_enteral_nutrition_33015813", ["33015813"], owner=V299, age="adult",
        population="35 cancer patients on home enteral nutrition, Poland",
        purpose="treatment", condition="nutritional_status_home_enteral_nutrition",
        basis="discrete_daily_arms", values=[2e10], duration=28,
        outcomes=[("serum_albumin", "unresolved", SU, "positive"),
                  ("vomiting", "unresolved", PI, "positive"),
                  ("flatulence", "unresolved", PI, "positive"),
                  ("overall_nutritional_status", "unresolved", PI, "null"),
                  ("quality_of_life", "unresolved", PI, "null")],
        family="299v_cancer_hen_33015813", design="rct", n=35, tier="D",
        limitations=["Small (n=35); overall nutritional status and between-group quality of life unchanged."]),
    ctx("lp299v_smokers_cardiovascular_markers_12450890", ["12450890"], owner=V299, age="adult",
        population="36 smokers consuming 400 mL/day of a 299v rose-hip drink for 6 weeks",
        purpose="physiology", condition="cardiovascular_risk_markers_smokers",
        basis="discrete_daily_arms", values=[2e10], duration=42, forms=["rose-hip drink"],
        outcomes=[("systolic_blood_pressure", "unresolved", SU, "positive"),
                  ("serum_leptin", "unresolved", SU, "positive"),
                  ("fibrinogen", "unresolved", SU, "positive")],
        family="299v_smokers_cvd_12450890", design="rct", n=36, tier="D",
        limitations=["Small 2002 trial in a food matrix (400 mL x 5 x 10^7 CFU/mL = 2 x 10^10/day); risk-marker surrogates only."]),
    ctx("lp299v_exam_stress_cortisol_28101105", ["28101105"], owner=V299, age="adult",
        population="41 university students during exam stress, 14 days",
        purpose="physiology", condition="exam_stress_cortisol_response", duration=14,
        outcomes=[("salivary_cortisol_rise_prevention", "unresolved", SU, "positive"),
                  ("salivary_iga", "unresolved", SU, "null")],
        family="299v_exam_stress_28101105", design="rct", n=41, tier="D",
        registration="NCT02974894",
        limitations=["Salivary cortisol is a stress surrogate; no clinical anxiety or mood endpoint; dose not stated in the abstract."]),
    ctx("lp299v_colon_resection_22434095", ["22434095"], owner=V299, age="adult",
        population="75 adults undergoing elective colon resection",
        purpose="prevention", condition="postoperative_outcomes_colon_resection",
        outcomes=[("enteric_bacterial_load", "unresolved", SU, "null"),
                  ("bacterial_translocation", "unresolved", SU, "null"),
                  ("postoperative_complications", "unresolved", PI, "null")],
        family="299v_colon_resection_22434095", design="rct", n=75, tier="D",
        limitations=["All endpoints null; dose not stated in the abstract."]),
    # ------------------------------------ L. acidophilus LA-5 + B. lactis BB-12
    ctx("la5_bb12_nonconstipated_ibs_41255078", ["41255078"], owner=LA5, scope="combination",
        components=[LA5, BB12], age="adult",
        population="200 adults with non-constipated IBS, 84 days",
        purpose="treatment", condition="irritable_bowel_syndrome", duration=84,
        outcomes=[("ibs_gis_response", "unresolved", PI, "positive"),
                  ("ibs_severity_abdominal_pain", "unresolved", PI, "positive"),
                  ("abdominal_distension", "unresolved", PI, "positive"),
                  ("quality_of_life", "unresolved", PI, "positive")],
        family="la5_bb12_ibs_41255078", design="rct", n=200, tier="C",
        limitations=["Combination evidence; nothing here attributes the effect to either strain alone; dose not stated in the abstract."]),
    ctx("la5_bb12_aad_incidence_24772726", ["24772726"], owner=LA5, scope="combination",
        components=[LA5, BB12], age="adult",
        population="Adults on cefadroxil or amoxicillin in a multicentric trial; 14 days of LA-5 + BB-12",
        purpose="prevention", condition="antibiotic_associated_diarrhea", duration=14,
        co_therapies=["cefadroxil or amoxicillin"],
        outcomes=[("aad_incidence", "primary", PI, "null"),
                  ("diarrhea_duration", "unresolved", PI, "positive"),
                  ("severe_diarrhea_subgroup", "post_hoc", PI, "positive")],
        family="la5_bb12_aad_24772726", design="rct", tier="C",
        limitations=["Primary incidence endpoint null (10.8% vs 15.6%, p=0.19); duration (2 vs 4 days) and a severe-diarrhea subgroup differed.",
                     "Sample size not captured from the abstract."]),
    ctx("lgg_la5_bb12_hospital_aad_17356555", ["17356555"], owner=LA5, scope="combination",
        components=[LGG, LA5, BB12], age="adult",
        population="87 hospitalized adults on antibiotics receiving a fermented milk with LGG, La-5 and Bb-12 for 14 days",
        purpose="prevention", condition="antibiotic_associated_diarrhea", duration=14, forms=["fermented milk"],
        co_therapies=["antibiotic therapy"],
        outcomes=[("aad_incidence", "unresolved", PI, "positive")],
        family="lgg_la5_bb12_hospital_aad_17356555", design="rct", n=87, tier="D",
        limitations=["Three-strain fermented milk (5.9% vs 27.6%); food matrix; nothing attributes the effect to a single strain."]),
    ctx("lgg_la5_bb12_pediatric_aad_25588782", ["25588782"], owner=LA5, scope="combination",
        components=[LGG, LA5, BB12], age="child",
        population="70 children 1-12 years on antibiotics receiving 200 g/day of a yogurt with LGG, Bb-12 and La-5",
        purpose="prevention", condition="pediatric_antibiotic_associated_diarrhea", forms=["yogurt 200 g/day"],
        co_therapies=["antibiotic therapy"],
        outcomes=[("severe_diarrhea_episodes", "unresolved", PI, "positive")],
        family="lgg_la5_bb12_pediatric_aad_25588782", design="rct", n=70, tier="D",
        limitations=["Severe diarrhea 0 vs 6 episodes (p=0.025) in a small yogurt trial; three-strain food matrix."]),
    ctx("la5_bb12_hpylori_yogurt_aad_21871144", ["21871144"], owner=LA5, scope="combination",
        components=[LA5, BB12], age="adult",
        population="88 Helicobacter pylori-infected adults in a three-arm fruit-yogurt trial spanning an eradication week",
        purpose="prevention", condition="antibiotic_associated_diarrhea_h_pylori_eradication", duration=56,
        forms=["fruit yogurt"], co_therapies=["Helicobacter pylori eradication therapy"],
        outcomes=[("aad_days", "unresolved", PI, "positive"),
                  ("h_pylori_urease_activity", "unresolved", SU, "null")],
        family="la5_bb12_hpylori_yogurt_21871144", design="rct", n=88, tier="D",
        limitations=["AAD days 4 vs 10 vs 10 across arms; urease activity fell in ALL milk arms, so that change is not attributable to the probiotic.",
                     "Food matrix; dose not stated in the abstract."]),
    ctx("la5_bb12_lc01_yogurt_aad_30439760", ["30439760"], owner=LA5, scope="combination",
        components=[LA5, BB12], age="adult",
        population="314 hospitalized adults on antibiotics receiving a yogurt with LA-5, BB-12 and LC-01",
        purpose="prevention", condition="antibiotic_associated_diarrhea", forms=["yogurt"],
        co_therapies=["antibiotic therapy"],
        outcomes=[("aad_incidence", "unresolved", PI, "null")],
        family="la5_bb12_lc01_aad_30439760", design="rct", n=314, tier="C",
        limitations=["Null result (23.0% vs 17.6%).",
                     "The studied product was a THREE-strain yogurt; the third strain L. casei LC-01 has no registry identity, so this record understates the formulation. A two-strain product matching these components was not what was tested."]),
    ctx("la5_bb12_primal_preterm_mdro_39102225", ["39102225"], owner=LA5, scope="combination",
        components=[LA5, BB12], age="infant",
        population="618 preterm infants 28-32 weeks in the PRIMAL phase 3 trial",
        purpose="prevention", condition="multidrug_resistant_organism_colonization_preterm",
        outcomes=[("mdro_colonization", "primary", SU, "null"),
                  ("gut_eubiosis_score", "secondary", SU, "positive")],
        family="primal_preterm_39102225", design="rct", n=618, tier="C",
        limitations=["Primary MDRO-colonization endpoint null; eubiosis is a microbiota surrogate.",
                     "The studied product also contained an unnamed B. longum subsp. infantis component with no registry identity; this record understates the formulation.",
                     "Hospital neonatal population; not a consumer supplement indication; dose not stated in the abstract."]),
    ctx("lgg_la5_bb12_propact_offspring_ad_41748464", ["41748464"], owner=LA5, scope="combination",
        components=[LGG, LA5, BB12], age="infant",
        population="Offspring of 415 pregnant women in the ProPACT trial of maternal LGG, La-5 and Bb-12 supplementation",
        purpose="prevention", condition="childhood_atopic_dermatitis",
        outcomes=[("offspring_atopic_dermatitis", "unresolved", PI, "positive")],
        family="propact_maternal_probiotic", design="rct", n=415, tier="C",
        limitations=["Authored from a longitudinal T-cell immunology companion whose abstract restates the parent trial's atopic-dermatitis reduction; the parent outcome paper was not read this wave.",
                     "Maternal supplementation with offspring outcomes; dose not stated in the abstract."]),
    # ---------------------------------------------------- BB-12-anchored records
    ctx("bb12_preterm_inflammation_feeding_39271904", ["39271904"], owner=BB12, age="infant",
        population="71 preterm infants at or below 32 weeks, BB-12 as the sole probiotic",
        purpose="prevention", condition="preterm_inflammation_and_feeding_intolerance",
        outcomes=[("serum_tlr4_nfkb_il1b_tnfa", "unresolved", SU, "positive"),
                  ("feeding_intolerance", "unresolved", PI, "positive")],
        family="bb12_preterm_inflammation_39271904", design="rct", n=71, tier="D",
        limitations=["Surrogate-heavy inflammatory-marker panel; hospital neonatal population; dose not stated in the abstract."]),
    ctx("lgg_bb12_pediatric_ad_prevention_meta_33811784", ["33811784"], owner=BB12, scope="combination",
        components=[LGG, BB12], age="infant",
        population="21 RCTs (n=5406) of probiotics for pediatric atopic-dermatitis prevention; network meta-analysis",
        purpose="prevention", condition="childhood_atopic_dermatitis",
        outcomes=[("atopic_dermatitis_risk_lgg_bb12", "primary", PI, "positive")],
        family="meta_pediatric_ad_prevention_33811784", design="meta_analysis", tier="B",
        limitations=["The LGG + Bb-12 node estimate (RR 0.50) is graded LOW quality by the reviewers.",
                     "Pooled trials overlap the ProPACT family context recorded this wave; not an independent confirmation of it."]),
    ctx("casei431_bb12_dracma_cma_tolerance_39310372", ["39310372"], owner=BB12, scope="combination",
        components=[CASEI431, BB12], age="infant",
        population="Infants with cow's milk allergy fed extensively hydrolyzed casein formula with L. casei CRL431 and Bb-12; WAO DRACMA systematic review",
        purpose="treatment", condition="cow_milk_allergy_tolerance_acquisition",
        co_therapies=["extensively hydrolyzed casein formula"],
        outcomes=[("cow_milk_tolerance_acquisition", "guideline", PI, "positive"),
                  ("severe_wheezing", "guideline", PI, "positive")],
        family="dracma_sr_cma_39310372", design="systematic_review", tier="B",
        limitations=["LOW certainty (tolerance RR 2.47); the formula itself is the delivery vehicle and co-therapy, so this is not supplement evidence.",
                     "Medical condition (cow's milk allergy) managed under clinical supervision."]),
    ctx("lgg_bb12_preterm_administration_route_37020105", ["37020105"], owner=BB12, scope="combination",
        components=[LGG, BB12], age="infant",
        population="68 preterm neonates randomized to direct LGG + Bb-12 administration or administration via the lactating mother",
        purpose="physiology", condition="preterm_gut_microbiota_colonization",
        comparator="administration to the lactating mother (route comparison)",
        outcomes=[("bifidobacterial_colonization_direct_administration", "unresolved", SU, "positive"),
                  ("microbiota_change_via_maternal_route", "unresolved", SU, "null")],
        family="bb12_lgg_preterm_route_37020105", design="rct", n=68, tier="D",
        limitations=["Route-comparison design without placebo; microbiota composition is a surrogate; dose not stated in the abstract."]),
    # ------------------------------- L. helveticus R0052 + B. longum R0175 pair
    ctx("r0052_r0175_psychological_distress_20974015", ["20974015"], owner=R0052, scope="combination",
        components=[R0052, R0175], age="adult",
        population="Healthy human volunteers taking the R0052 + R0175 formulation for 30 days (Messaoudi 2011)",
        purpose="treatment", condition="psychological_distress", duration=30,
        outcomes=[("hscl90_global_severity", "unresolved", PI, "positive"),
                  ("hospital_anxiety_depression_scale", "unresolved", PI, "positive"),
                  ("urinary_free_cortisol", "unresolved", SU, "positive")],
        family="cerebiome_healthy_distress_20974015", design="rct", tier="D",
        limitations=["Dose and sample size not stated in the retrieved abstract; the paper's rat arm is not a human context."]),
    ctx("r0052_r0175_mdd_bdnf_secondary_32989186", ["32989186"], owner=R0052, scope="combination",
        components=[R0052, R0175], age="adult",
        population="110 adults with major depressive disorder randomized (78 analyzed), 8 weeks; probiotic vs prebiotic vs placebo",
        purpose="treatment", condition="major_depressive_disorder", duration=56,
        outcomes=[("depressive_symptoms_parent_trial", "unresolved", PI, "positive"),
                  ("serum_bdnf", "unresolved", SU, "positive")],
        family="kazemi_mdd", design="rct", n=110, tier="D",
        limitations=["Secondary (BDNF) analysis of the Kazemi cohort; the parent trial's primary outcome paper was not read this wave, and its depression improvement is restated in this abstract.",
                     "Dose not stated in the retrieved abstract."]),
    ctx("r0052_r0175_mdd_open_pilot_33658952", ["33658952"], owner=R0052, scope="combination",
        components=[R0052, R0175], age="adult",
        population="10 treatment-naive adults with major depressive disorder; open-label single-arm pilot",
        purpose="treatment", condition="major_depressive_disorder",
        basis="discrete_daily_arms", values=[3e9], duration=56,
        outcomes=[("affective_symptoms", "unresolved", PI, "positive")],
        family="r0052_r0175_open_pilot_33658952", design="open_label", n=10, blinding="open", tier="E",
        limitations=["No control arm; ten participants; hypothesis-generating only."]),
    ctx("r0052_r0175_healthy_adults_null_37049546", ["37049546"], owner=R0052, scope="combination",
        components=[R0052, R0175], age="adult",
        population="135 healthy adults, 4 weeks",
        purpose="physiology", condition="psychological_wellbeing_healthy_adults", duration=28,
        outcomes=[("whole_sample_psychological_outcomes", "primary", PI, "null"),
                  ("lifestyle_interaction_effects", "post_hoc", PI, "positive")],
        family="r0052_r0175_healthy_null_37049546", design="rct", n=135, tier="C",
        registration="NCT04823533",
        limitations=["No significant whole-sample effects; the lifestyle-interaction finding is exploratory."]),
    # ------------------------------- L. rhamnosus GR-1 + L. fermentum RC-14 pair
    ctx("gr1_rc14_bv_metronidazole_adjunct_34295831", ["34295831"], owner=GR1, scope="combination",
        components=[GR1, RC14], age="adult",
        population="126 women with bacterial vaginosis on metronidazole, 30 days of oral GR-1 + RC-14",
        purpose="treatment", condition="bacterial_vaginosis", duration=30,
        co_therapies=["metronidazole"],
        outcomes=[("bv_cure_rate_30_and_90_days", "unresolved", PI, "null"),
                  ("strain_detection_vaginal_fecal", "unresolved", SU, "null")],
        family="gr1_rc14_bv_adjunct_34295831", design="rct", n=126, tier="C",
        limitations=["Cure rates did not differ at 30 or 90 days and the administered species were rarely detected in vaginal or fecal microbiota."]),
    ctx("gr1_rc14_pregnancy_bv_30932317", ["30932317"], owner=GR1, scope="combination",
        components=[GR1, RC14], age="adult",
        population="238 pregnant women analyzed, oral supplementation from 9-14 weeks gestation",
        purpose="prevention", condition="bacterial_vaginosis_pregnancy",
        basis="discrete_daily_arms", values=[5e9],
        outcomes=[("bacterial_vaginosis_18_20_weeks", "unresolved", PI, "null"),
                  ("vaginal_colonization", "unresolved", SU, "null"),
                  ("microbiota_composition", "unresolved", SU, "null")],
        family="gr1_rc14_pregnancy_bv_30932317", design="rct", n=238, tier="C",
        limitations=["Null throughout; 2.5 x 10^9 CFU of each strain (5 x 10^9/day combination total, never an individual dose)."]),
    ctx("gr1_rc14_pregnancy_colonization_32325794", ["32325794"], owner=GR1, scope="combination",
        components=[GR1, RC14], age="adult",
        population="38 pregnant women at risk for preterm labor; open crossover",
        purpose="physiology", condition="vaginal_colonization_pregnancy",
        outcomes=[("vaginal_colonization_administered_strains", "unresolved", SU, "null")],
        family="gr1_rc14_pregnancy_colonization_32325794", design="crossover_rct", n=38, blinding="open", tier="D",
        limitations=["Open crossover; colonization of the administered strains was rare."]),
    ctx("gr1_rc14_gbs_colonization_27590374", ["27590374"], owner=GR1, scope="combination",
        components=[GR1, RC14], age="adult",
        population="99 group B Streptococcus-positive pregnant women at 35-37 weeks gestation",
        purpose="treatment", condition="group_b_streptococcus_colonization",
        outcomes=[("gbs_conversion_to_negative", "unresolved", SU, "positive")],
        family="gr1_rc14_gbs_27590374", design="rct", n=99, tier="C",
        limitations=["Conversion to GBS-negative on admission (42.9% vs 18.0%, p=0.007) is a colonization surrogate, not an infection outcome; dose not stated in the abstract."]),
    ctx("gr1_rc14_sci_mdr_colonization_31953482", ["31953482"], owner=GR1, scope="combination",
        components=[GR1, RC14], age="adult",
        population="207 adults with spinal cord injury in the four-arm ProSCIUTTU trial (including an LGG-BB12 arm)",
        purpose="prevention", condition="multidrug_resistant_gram_negative_colonization",
        outcomes=[("new_multiresistant_gram_negative_colonization", "secondary", SU, "positive"),
                  ("existing_colonization_clearance", "secondary", SU, "null")],
        family="prosciuttu", design="rct", n=207, tier="C",
        limitations=["Secondary colonization analysis (OR 0.10 for new colonization, no clearing effect); the trial's UTI primary paper was not read this wave.",
                     "Population-specific (spinal cord injury); colonization is a microbiological surrogate."]),
    # ---------------------------------------------- B. coagulans GBI-30, 6086
    ctx("bc30_functional_gi_complaints_40707016", ["40707016"], owner=GBI30, age="adult",
        population="111 healthy adults with functional gastrointestinal complaints",
        purpose="treatment", condition="functional_gastrointestinal_complaints",
        basis="discrete_daily_arms", values=[1e9], duration=28,
        outcomes=[("stool_frequency", "unresolved", PI, "positive"),
                  ("stool_consistency", "unresolved", PI, "positive"),
                  ("constipation_proportion", "unresolved", PI, "positive")],
        family="kerry_bc30_gi_40707016", design="rct", n=111, funding="industry", tier="C",
        registration="NCT06644001",
        limitations=["Sponsor-run (Kerry); endpoint hierarchy not stated in the abstract."]),
    ctx("bc30_synbiotic_pasta_cardiometabolic_31162597", ["31162597"], owner=GBI30, age="adult",
        population="41 adults consuming a whole-grain pasta with BC30 and barley beta-glucans for 12 weeks",
        purpose="physiology", condition="inflammation_and_lipid_markers", duration=84,
        forms=["whole-grain pasta"], co_therapies=["barley beta-glucans"],
        outcomes=[("hs_crp", "primary", SU, "null"),
                  ("lipid_profile", "primary", SU, "null"),
                  ("subgroup_signals", "post_hoc", SU, "positive")],
        family="bc30_pasta_synbiotic_31162597", design="rct", n=41, blinding="single", tier="D",
        limitations=["Primary hs-CRP and lipid endpoints null overall; only subgroups moved.",
                     "Food matrix and beta-glucan co-therapy confound any strain attribution; single-blind."]),
    ctx("bc30_geriatric_indigestion_enzymes_32318476", ["32318476"], owner=GBI30, age="adult",
        population="Elderly adults with functional indigestion; open-label, BC30 co-formulated with digestive enzymes, 5 days",
        purpose="treatment", condition="functional_indigestion_elderly", duration=5,
        co_therapies=["digestive enzymes (co-formulated)"],
        outcomes=[("dyspepsia_severity", "unresolved", PI, "positive")],
        family="bc30_geriatric_enzymes_32318476", design="open_label", blinding="open", tier="E",
        limitations=["Open label; attribution confounded by the co-formulated digestive enzymes; five-day duration."]),
    # --------------------------------------------------------- B. breve M-16V
    ctx("m16v_simpro_five_year_followup_41515257", ["41515257"], owner=M16V, age="infant",
        population="Extremely preterm infants below 28 weeks from the SiMPro trial followed to five years",
        purpose="prevention", condition="extremely_preterm_five_year_outcomes",
        comparator="triple-strain arm (M-16V + M-63 + BB536); no placebo arm",
        outcomes=[("neurodevelopment_5_years", "unresolved", PI, "null"),
                  ("growth_5_years", "unresolved", PI, "null"),
                  ("blood_pressure_5_years", "unresolved", SU, "null"),
                  ("atopy_5_years", "unresolved", PI, "null")],
        family="simpro_5y_followup_41515257", design="rct", tier="D",
        limitations=["Comparative single- vs triple-strain design without placebo: 'null' here means the arms were comparable, not that M-16V lacks effect versus no treatment.",
                     "Hospital neonatal population; dose and follow-up sample size not captured from the abstract."]),
    ctx("m16v_neonatal_jaundice_adjunct_41994268", ["41994268"], owner=M16V, age="infant",
        population="79 neonates with jaundice under phototherapy in a four-arm trial (control / M-16V / Bb-12 / M-16V + Bb-12), 30 days",
        purpose="treatment", condition="neonatal_jaundice_phototherapy_adjunct", duration=30,
        co_therapies=["phototherapy"],
        outcomes=[("defecation_frequency", "unresolved", SU, "positive"),
                  ("transcutaneous_bilirubin_decline", "unresolved", SU, "positive"),
                  ("hospital_stay_duration", "unresolved", PI, "positive")],
        family="m16v_bb12_jaundice_41994268", design="rct", n=79, funding="mixed", tier="D",
        limitations=["About 20 infants per arm; the Bb-12 arm's neurodevelopment-domain signals are not recorded under this identity.",
                     "Industry-adjacent authorship (Diprobio); dose not stated in the abstract."]),
    ctx("m16v_synbiotic_formula_csection_39915586", ["39915586"], owner=M16V, age="infant",
        population="284 healthy cesarean-born infants randomized to a synbiotic formula with M-16V and scGOS/lcFOS versus a prebiotic-only formula",
        purpose="physiology", condition="gut_microbiota_after_cesarean_birth",
        forms=["infant formula"], co_therapies=["scGOS/lcFOS prebiotic blend"],
        comparator="prebiotic-only formula",
        outcomes=[("bifidobacterial_restoration", "unresolved", SU, "positive")],
        family="danone_m16v_csection_39915586", design="rct", n=284, funding="industry", tier="C",
        registration="NCT03520764",
        limitations=["Microbiota restoration is a surrogate; formula matrix with prebiotic co-therapy; sponsor-run (Danone)."]),
    # --------------------------------------------------------- L. plantarum LP01
    ctx("lp01_bb12_synbiotic_constipation_29949873", ["29949873"], owner=LP01, scope="combination",
        components=[LP01, BB12], age="adult",
        population="85 adults with Rome III functional constipation taking a synbiotic with LP01, BB-12 and prebiotics for 12 weeks",
        purpose="treatment", condition="functional_constipation", duration=84,
        co_therapies=["prebiotic fibers (synbiotic formulation)"],
        outcomes=[("stool_evacuation", "unresolved", PI, "null"),
                  ("pac_sym", "unresolved", PI, "null"),
                  ("pac_qol", "unresolved", PI, "null")],
        family="lp01_bb12_synbiotic_fc_29949873", design="rct", n=85, tier="D",
        limitations=["No endpoint reached significance versus placebo (high placebo response); synbiotic formulation.",
                     "This null is currently LP01's only registry-recordable RCT: the rest of its trial base uses non-registry partner strains (see wave2_read_log.md)."]),
]


def main():
    raw = REG.read_text()
    reg = json.loads(raw)
    before = deepcopy(reg)
    entries = {e["id"]: e for e in reg["clinically_relevant_strains"]}
    meta = reg["_metadata"]
    if meta.get("version") == "2.4.0":
        # This is a one-time data migration, but the documented command is
        # safe to rerun. Validate the materialized rows byte-for-byte instead
        # of appending duplicates or silently accepting a partial application.
        # Later source-bound dispositions (apply_batch1_disposition.py) patch
        # individual fields of some Wave 2 rows without changing review status;
        # a stored row must equal either the authored row or the authored row
        # with exactly those declared patches applied.
        stored = {c.get("context_id"): c for e in entries.values()
                  for c in e.get("study_contexts", []) if isinstance(c, dict)}
        patches = _declared_disposition_patches()
        decisions = _response_decisions()
        for owner, row in CONTEXTS:
            expected = deepcopy(row)
            for field_path, new_value in patches.get(row["context_id"], []):
                _write_path_appending(expected, field_path, new_value)
            current = stored.get(row["context_id"])
            decision = decisions.get(row["context_id"])
            if decision and isinstance(current, dict):
                # The owner's final status and its provenance come from the
                # applied review response, not from this authoring script;
                # verify the status matches the decision, then carry the
                # decision fields into the expected row.
                wanted = {"reject": "rejected_source",
                          "needs_source_clarification": "adjudication_required"}.get(decision, "clinician_approved")
                assert current.get("review_status") == wanted, (
                    f"{row['context_id']}: status {current.get('review_status')!r} != decision {decision!r}")
                for key in OWNER_DECISION_FIELDS:
                    if key in current:
                        expected[key] = deepcopy(current[key])
                if decision == "needs_source_clarification":
                    # A hold appends its reason to limitations; the authored
                    # limitations must still be present, in order, at the front.
                    authored = expected.get("limitations", [])
                    assert current.get("limitations", [])[:len(authored)] == authored, (
                        f"{row['context_id']}: authored limitations were altered by the hold")
                    expected["limitations"] = deepcopy(current["limitations"])
            assert current in (row, expected), (
                f"Wave 2 is marked applied but {row['context_id']} differs or is missing")
            assert owner in entries and row["context_id"] in {
                c.get("context_id") for c in entries[owner].get("study_contexts", [])
            }
        print(f"Wave 2 already applied; verified {len(CONTEXTS)} contexts; no changes written")
        return
    added = 0
    for owner, row in CONTEXTS:
        entry = entries[owner]
        for component in row["components"]:
            assert component in entries, (row["context_id"], component)
        assert valid_native_study_context(row, owner), f"invalid context {row['context_id']}"
        existing = entry.setdefault("study_contexts", [])
        assert all(c.get("context_id") != row["context_id"] for c in existing), f"duplicate {row['context_id']}"
        assert not any(set(c.get("source_pmids", [])) == set(row["source_pmids"]) and c.get("condition") == row["condition"]
                       for c in existing), f"same sources already authored under {owner}: {row['context_id']}"
        existing.append(row)
        added += 1
    assert meta["version"] == "2.3.0", meta["version"]
    meta["version"] = "2.4.0"
    meta["last_updated"] = "2026-09-14"
    meta["native_context_note_2026_09_14"] = (
        f"Wave 2 bounded curation: {added} study contexts authored for STRAIN_COAGULANS_IS2, "
        "STRAIN_COAGULANS_MTCC5856, STRAIN_ACIDOPHILUS_DDS1, STRAIN_PLANTARUM_299V, STRAIN_ACIDOPHILUS_LA5, "
        "STRAIN_LACTIS_BB12, STRAIN_HELVETICUS_R0052, STRAIN_RHAMNOSUS_GR1, STRAIN_COAGULANS_GBI30, "
        "STRAIN_BREVE_M16V and STRAIN_PLANTARUM_LP01 (R0175, RC14, UABla12, CRL-431 and LGG join through "
        "combination contexts; no identity stubs were added). Every context is "
        "source_verified_pending_clinical_review; optional study_design / sample_size / blinding / funding / "
        "source_tier / trial_registration describe quality and never score. Null and negative results are kept. "
        "Publication families (trial_family) mark papers from one cohort so they cannot count as independent "
        "confirmations.")
    # Everything other than the additions must be unchanged.
    after = deepcopy(reg)
    for entry in after["clinically_relevant_strains"]:
        entry.pop("study_contexts", None)
    for entry in before["clinically_relevant_strains"]:
        entry.pop("study_contexts", None)
    for key in ("version", "last_updated", "native_context_note_2026_09_14"):
        after["_metadata"].pop(key, None); before["_metadata"].pop(key, None)
    assert after == before, "unexpected change outside study_contexts / metadata"
    # Wave 1 contexts must survive untouched.
    kept_2026_09_13 = sum(1 for e in reg["clinically_relevant_strains"]
                          for c in e.get("study_contexts", []) if c.get("authored_on") == "2026-09-13")
    assert kept_2026_09_13 == 50, kept_2026_09_13
    REG.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    total = sum(len(e.get("study_contexts", [])) for e in reg["clinically_relevant_strains"])
    print(f"authored {added} contexts; registry now holds {total} contexts across "
          f"{sum(1 for e in reg['clinically_relevant_strains'] if e.get('study_contexts'))} identities")


if __name__ == "__main__":
    main()
