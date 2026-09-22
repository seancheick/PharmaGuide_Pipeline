#!/usr/bin/env python3
"""Apply Dr Pham's 2026-09-22 clinical review of the probiotic sign-off sheet.

The sheet (https://claude.ai/artifact/3Bhz3oj3qgLBsYZz3iwiof) asked her for
three decisions holding 55 products, a confirm-or-withdraw on 23 sign-offs
recorded in her name by an automated PMID check, and an optional spot-check of
the 18 closure-D1 study records. Her reply was relayed by Sean on 2026-09-22.

Every PMID she cited was content-verified against live PubMed (efetch XML) and,
where the abstract was silent, the open-access full text (Europe PMC) before
anything here was written. The ledger (per-PMID title, design and the claim it
supports) is ``PHAM_REVIEW_20260922.json`` - the basis every record cites.

Her rule, applied throughout: clinically reviewed does not mean clinically
effective. A null trial closes a review and earns no efficacy credit; secondary
and surrogate findings stay labelled as such; nothing crosses a strain boundary
or escapes a combination into one of its components.

Each entry is edited explicitly and asserted against its current value first,
one at a time; there is no bulk transform.

    python3 scripts/audits/closure_20260921/pham_review_20260922.py          # dry run
    python3 scripts/audits/closure_20260921/pham_review_20260922.py --apply
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
BASIS_REL = "scripts/audits/closure_20260921/PHAM_REVIEW_20260922.json"
ON = "2026-09-22"
REVIEWER = "Dr Pham (clinical review 2026-09-22)"
VERIFIED_BY = "Dr Pham (2026-09-22 clinical review) + agent:claude-code (PubMed API-verified 2026-09-22)"
STALE_NOTE = ("Strain referenced but evidence is adjacent (review / co-studied paper). "
              "Dr Pham may upgrade citation when signing off.")

BI07, BB12, LA5 = "STRAIN_LACTIS_BI07", "STRAIN_LACTIS_BB12", "STRAIN_ACIDOPHILUS_LA5"
HEAL9, P8700 = "STRAIN_PLANTARUM_HEAL9", "STRAIN_PARACASEI_8700"
GR1, RC14 = "STRAIN_RHAMNOSUS_GR1", "STRAIN_FERMENTUM_RC14"
R0052, R0175 = "STRAIN_HELVETICUS_R0052", "STRAIN_LONGUM_R0175"
LC01 = "UNREGISTERED:Lacticaseibacillus casei LC-01"
PRIMAL_INFANTIS = "UNREGISTERED:Bifidobacterium longum subsp. infantis (PRIMAL strain, not named)"


def _sign(entry: dict, note: str, *, signed: bool = True) -> None:
    thresholds = entry["cfu_thresholds"]
    thresholds["dr_pham_signoff"] = signed
    thresholds["dr_pham_signoff_verified_by"] = VERIFIED_BY
    thresholds["dr_pham_signoff_verified_date"] = ON
    thresholds["dr_pham_signoff_verification_note"] = f"Dr Pham {ON}: {note}"


def _replace_note(entry: dict, old: str, new: str) -> None:
    notes = entry["cfu_thresholds"]["notes"]
    assert notes.count(old) == 1, (entry["id"], old)
    entry["cfu_thresholds"]["notes"] = notes.replace(old, new)


def _countersign(context: dict, reviewed_at: str, note: str) -> None:
    review = context["clinical_review"]
    review["countersigned_by"] = REVIEWER
    review["countersigned_at"] = reviewed_at
    review["countersign_note"] = note


def _review(reviewed_at: str, decision: str) -> dict:
    return {"reviewer": REVIEWER, "reviewed_at": reviewed_at,
            "scope": "identity_dose_outcome_applicability", "basis": BASIS_REL, "decision": decision}


# ---------------------------------------------------------------- 1a / 1b ---

def restore_bi07_bb12(by_id: dict, reviewed_at: str) -> None:
    from probiotic_measurements import derived_context_evidence

    bi07 = by_id[BI07]
    assert bi07["cfu_thresholds"]["dr_pham_signoff"] is False
    assert bi07["cfu_thresholds"]["evidence"]["type"] == "unverified_reference"
    bi07["cfu_thresholds"]["evidence"] = None
    _sign(bi07, "sign-off restored on identity-correct human evidence. PMID 36149331 (two randomized, placebo- "
          "and lactase-controlled crossover lactose-challenge trials of Bi-07 alone, 2 x 10^12 CFU taken with the "
          "challenge): the prespecified primary outcome, breath-hydrogen iAUC, improved in both trials - a surrogate "
          "of acute lactose digestion; GI symptoms were secondary and not improved; nausea rose with Bi-07 in Booster "
          "Omega (OR 4.0). PMID 21436726 tested NCFM + Bi-07 together (primary global relief and satisfaction; "
          "bloating secondary) and gives Bi-07 alone no credit. Clinically reviewed; not evidence of broad GI "
          "symptom efficacy or of ordinary daily-use benefit.")
    _replace_note(bi07, "Native clinical credit is on hold pending identity-correct evidence review.",
                  f"Clinically reviewed {ON} (Dr Pham): the exact-strain evidence is an acute lactose-digestion "
                  "surrogate from single challenges, so it earns no efficacy credit.")
    bi07["notable_studies"] = (f"Dr Pham review {ON}: two randomized crossover lactose-challenge trials of Bi-07 alone "
                               "improved breath hydrogen (primary surrogate) without GI-symptom benefit, with more "
                               "nausea in one trial; an NCFM + Bi-07 bloating trial is combination evidence (primary "
                               "outcomes negative, bloating secondary).")
    for context in bi07["study_contexts"]:
        _countersign(context, reviewed_at, {
            "bi07_lactose_challenges_36149331": "Single-strain credit is the lactose-digestion surrogate only; note the nausea signal.",
            "ncfm_bi07_bloating_21436726": "Combination evidence only; zero Bi-07-alone credit.",
        }[context["context_id"]])
    derived = derived_context_evidence(bi07)
    assert derived["effect_direction"] == "unresolved", derived
    bi07["evidence_level"] = {"strong": "high", "medium": "moderate", "weak": "low"}[derived["evidence_strength"]]

    bb12 = by_id[BB12]
    assert bb12["cfu_thresholds"]["dr_pham_signoff"] is False
    assert bb12["cfu_thresholds"]["evidence"]["type"] == "unverified_reference"
    bb12["cfu_thresholds"]["evidence"] = None
    _sign(bb12, "sign-off restored; human evidence reviewed - mixed/limited. PMID 26382580 (1,248 adults, BB-12 1 or "
          "10 billion CFU/day vs placebo for 4 weeks): GI well-being not improved; the original defecation-frequency "
          "responder endpoint missed significance (OR 1.31, 95% CI 0.98-1.75, P = .071); a tightened responder "
          "definition and mean defecation frequency were favourable. PMID 39271904 (71 preterm infants <= 32 weeks, "
          "BB-12 alone): lower serum inflammatory markers and less feeding intolerance; specialised neonatal "
          "population; dose not in the abstract. Combination studies credit no single strain.")
    _replace_note(bb12, "The research candidate is not a clinician-approved replacement and does not establish a "
                  "continuous dose range.",
                  f"Clinically reviewed {ON} (Dr Pham): human evidence mixed/limited. The 1B and 10B CFU/day arms "
                  "performed similarly and do not establish a continuous dose range.")
    bb12["notable_studies"] = (f"Dr Pham review {ON}: human evidence reviewed, mixed/limited. A 1,248-adult RCT (1B "
                               "or 10B CFU/day for 4 weeks) did not meet its original defecation-frequency responder "
                               "endpoint or improve global GI well-being; a tightened responder definition and mean "
                               "defecation frequency were favourable. A 71-infant preterm trial of BB-12 alone "
                               "reported lower inflammatory markers and less feeding intolerance.")
    notes = {"bb12_low_stool_frequency_26382580": "Primary endpoints not met; favourable findings are secondary or post hoc.",
             "bb12_preterm_inflammation_feeding_39271904": "BB-12-only human evidence; biomarker-led, specialised neonatal population, dose not stated."}
    for context in bb12["study_contexts"]:
        if context["context_id"] in notes:
            _countersign(context, reviewed_at, notes[context["context_id"]])
    derived = derived_context_evidence(bb12)
    assert derived["effect_direction"] == "null", derived
    bb12["evidence_level"] = {"strong": "high", "medium": "moderate", "weak": "low"}[derived["evidence_strength"]]


# ---------------------------------------------------------------------- 1c ---

def approve_la5_combinations(by_id: dict, reviewed_at: str) -> None:
    contexts = {c["context_id"]: c for c in by_id[LA5]["study_contexts"]}

    yogurt = contexts["la5_bb12_lc01_yogurt_aad_30439760"]
    assert yogurt["review_status"] == "adjudication_required" and "context_schema_version" not in yogurt
    yogurt.update({
        "components": [LA5, BB12, LC01],
        "dose": {"basis": "unresolved", "unit": "CFU", "values": [], "dosage_forms": ["yogurt"],
                 "duration_days": None, "co_therapies": ["antibiotic therapy"],
                 "dose_status": "extraction_pending", "dose_basis": "not_applicable",
                 "duration_basis": "tied_to_cotherapy",
                 "duration_note": "200 mL of yogurt daily, started within 48 h of beginning antibiotics and "
                                  "continued until 5 days after stopping them"},
        "limitations": [
            "No benefit: antibiotic-associated diarrhoea in 23.0% with the probiotic yogurt vs 17.6% with placebo "
            "yogurt (absolute risk reduction -5.35%, 95% CI -15.4% to 4.7%; P = 0.30).",
            "The tested yogurt contained three strains: LA-5, BB-12 and L. casei LC-01. LC-01 has no registry "
            "identity and is recorded as an unregistered component; no component-level credit.",
            f"Approved {ON} by Dr Pham as a literal combination record: a null multistrain RCT is evidence about "
            "the multistrain formulation.",
        ],
        "review_status": "clinician_approved", "blinding": "double",
        "comparator": "placebo yogurt (S. thermophilus and L. delbrueckii subsp. bulgaricus); unblinded no-yogurt control",
        "context_schema_version": "1.1.0", "evidence_role": "direct_rct",
        "component_registration_status": "unregistered_components_present", "scoring_eligible": True,
        "clinical_review": _review(reviewed_at, "approve_as_combination_record"),
    })

    primal = contexts["la5_bb12_primal_preterm_mdro_39102225"]
    assert primal["review_status"] == "adjudication_required" and "context_schema_version" not in primal
    each = 1.5e9
    primal.update({
        "components": [LA5, BB12, PRIMAL_INFANTIS],
        "dose": {"basis": "discrete_daily_arms", "unit": "CFU", "values": [each], "dosage_forms": ["capsule"],
                 "duration_days": 28, "co_therapies": [], "dose_status": "verified",
                 "dose_basis": "per_strain_daily", "duration_basis": "fixed_protocol",
                 "component_doses": [{"component": c, "dose_cfu_per_day": each}
                                     for c in (LA5, BB12, PRIMAL_INFANTIS)],
                 "duration_note": "One daily-dose capsule diluted in human milk or formula for 28 days, "
                                  "starting within the first 72 hours of life",
                 "source_provenance": {"pmid": "39102225",
                                       "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12549143/",
                                       "location": "full_text_methods"}},
        "limitations": [
            "Primary endpoint null: MDRO+ colonization at day 30 in 37.4% vs 37.5% (adjusted RR 0.99, 95% CI "
            "0.54-1.81; interim analysis of 219 infants). The eubiosis score, a microbiota surrogate, improved.",
            "The tested mixture also contained an unnamed B. longum subsp. infantis strain, recorded as an "
            "unregistered component; no component-level credit.",
            "Hospital neonatal population, not a consumer supplement indication; environmental uptake of the "
            "B. infantis strain occurred in 49% of sampled control infants.",
            f"Approved {ON} by Dr Pham as a literal combination record: a null multistrain RCT is evidence about "
            "the multistrain formulation.",
        ],
        "review_status": "clinician_approved", "blinding": "double",
        "comparator": "placebo (cornstarch powder)", "trial_registration": "DRKS00013197",
        "context_schema_version": "1.1.0", "evidence_role": "direct_rct",
        "component_registration_status": "unregistered_components_present", "scoring_eligible": True,
        "clinical_review": _review(reviewed_at, "approve_as_combination_record"),
    })


# ---------------------------------------------------------- 2: confirmed ---

def confirm(by_id: dict) -> None:
    def ev(sid):
        return by_id[sid]["cfu_thresholds"]["evidence"]

    lgg = by_id["STRAIN_LGG"]
    assert ev("STRAIN_LGG")["evidence_strength"] == "strong"
    ev("STRAIN_LGG")["evidence_strength"] = "medium"
    lgg["evidence_level"] = "moderate"
    _sign(lgg, "confirmed. PMID 26756877 (ESPGHAN 2016) recommends LGG for paediatric antibiotic-associated "
          "diarrhoea prevention from strain-specified RCTs: moderate quality of evidence, strong recommendation. "
          "Recorded as medium because this field grades evidential certainty, not recommendation strength.")

    sb = by_id["STRAIN_SACCHAROMYCES"]
    assert ev("STRAIN_SACCHAROMYCES")["evidence_strength"] == "strong"
    ev("STRAIN_SACCHAROMYCES")["evidence_strength"] = "medium"
    sb["evidence_level"] = "moderate"
    _sign(sb, "confirmed. PMID 26756877: paediatric antibiotic-associated diarrhoea prevention, moderate quality of "
          "evidence, strong recommendation (recorded as medium certainty). For C. difficile-associated diarrhoea "
          "the paper grades the evidence low quality with a conditional recommendation; the strong label does not "
          "extend to that indication.")

    shirota = by_id["STRAIN_CASEI_SHIROTA"]
    assert "effect_direction" not in ev("STRAIN_CASEI_SHIROTA")
    ev("STRAIN_CASEI_SHIROTA").update({
        "effect_direction": "null",
        "effect_direction_basis": "Meta-analysis 36372047 found no significant stool-frequency effect for Shirota; "
                                  "direct RCT 23432408 found no advantage over control at alpha = .05; the older "
                                  "RCT 14631461 was favourable. Reviewed null, not positive constipation credit.",
        "additional_pmids": ["23432408", "14631461"],
    })
    shirota["evidence_level"] = "moderate"
    shirota["notable_studies"] = (f"Dr Pham review {ON}: strain-specific constipation evidence is null in the pooled "
                                  "analysis and the 2013 RCT; an older 2003 RCT was favourable.")
    _replace_note(shirota, STALE_NOTE, f"Citation clinically reviewed {ON} (Dr Pham): null constipation evidence.")
    _sign(shirota, "confirmed as legitimate null strain-specific evidence. PMID 36372047 addresses Shirota and reports "
          "no significant pooled stool-frequency benefit; RCT 23432408 found no advantage over control at alpha = "
          ".05; the older RCT 14631461 was favourable. Keep the review; no positive constipation credit.")

    mtcc = by_id["STRAIN_COAGULANS_MTCC5856"]
    _replace_note(mtcc, STALE_NOTE, f"Citation clinically reviewed {ON} (Dr Pham).")
    _sign(mtcc, "confirmed. PMID 37686889 (network meta-analysis of 81 IBS RCTs) is outcome- and strain-specific: "
          "MTCC 5856 ranked favourably for abdominal pain and for IBS-D stool form. Medium is defensible.")

    _sign(by_id["STRAIN_REUTERI_DSM17938"], "confirmed. PMID 29390535 is directly strain-specific (32 RCTs, 2,242 "
          "infants; favourable crying-duration result for DSM 17938).")
    _sign(by_id["STRAIN_K12"], "confirmed. PMID 38215354: randomized double-blind placebo-controlled trial, n = 160 "
          "patients undergoing head-and-neck radiotherapy; primary severe oral mucositis 36.6% vs 54.2% (P = .0351). "
          "Strong is reasonable for this population and use only.")

    hn019 = by_id["STRAIN_LACTIS_HN019"]
    assert ev("STRAIN_LACTIS_HN019")["effect_direction"] == "null"
    _sign(hn019, "confirmed as strong null evidence. PMID 39356506: 229-person triple-blind RCT; no difference from "
          "placebo in the primary complete-spontaneous-bowel-movement outcome (P = .37). No constipation efficacy "
          "credit from this trial.")

    p299v = by_id["STRAIN_PLANTARUM_299V"]
    assert ev("STRAIN_PLANTARUM_299V")["evidence_strength"] == "strong"
    ev("STRAIN_PLANTARUM_299V")["evidence_strength"] = "medium"
    p299v["evidence_level"] = "moderate"
    _sign(p299v, "confirmed. PMID 11711768 is a direct single-strain double-blind RCT, but with 40 patients (20 per "
          "arm); recorded as medium because strength reflects sample size and replication.")

    b35624 = by_id["STRAIN_INFANTIS_35624"]
    assert "effect_direction" not in ev("STRAIN_INFANTIS_35624")
    ev("STRAIN_INFANTIS_35624").update({
        "effect_direction": "null",
        "effect_direction_basis": "Meta-analysis 28166427 separates single-strain from composite trials: the three "
                                  "single-strain 35624 trials did not improve abdominal pain, bloating/distension or "
                                  "bowel-habit satisfaction. Composite-probiotic benefits are not attributable to 35624.",
    })
    b35624["key_benefits"] = [b for b in b35624["key_benefits"] if b != "IBS relief"]
    assert b35624["notable_studies"] == "Multiple RCTs for IBS, particularly women"
    b35624["notable_studies"] = (f"Dr Pham review {ON}: in the 2017 meta-analysis the three single-strain 35624 IBS "
                                 "trials did not improve abdominal pain, bloating or bowel-habit satisfaction.")
    _sign(b35624, "confirmed as strong null/mixed evidence. PMID 28166427 separates single-strain from composite "
          "trials; the three single-strain studies showed no significant effect on abdominal pain, bloating/"
          "distension or bowel-habit satisfaction. No positive IBS credit.")

    bb536 = by_id["STRAIN_LONGUM_BB536"]
    _replace_note(bb536, STALE_NOTE, f"Citation clinically reviewed {ON} (Dr Pham).")
    _sign(bb536, "confirmed. PMID 23192454: direct double-blind study, n = 45 elderly tube-fed patients; faecal "
          "bifidobacteria increased, influenza-vaccine HI titres did not; the immune findings were biomarker or "
          "subgroup results. Medium is appropriate.")

    hn001 = by_id["STRAIN_RHAMNOSUS_HN001"]
    assert ev("STRAIN_RHAMNOSUS_HN001")["evidence_strength"] == "strong"
    ev("STRAIN_RHAMNOSUS_HN001")["evidence_strength"] = "medium"
    hn001["evidence_level"] = "moderate"
    _sign(hn001, "confirmed. PMID 28943228 is valid single-strain randomized human evidence, but postpartum "
          "depression and anxiety were an explicit secondary outcome (primary: offspring eczema at 12 months); "
          "recorded as medium for the mood indication.")

    sp1 = by_id["STRAIN_RHAMNOSUS_SP1"]
    _replace_note(sp1, STALE_NOTE, f"Citation clinically reviewed {ON} (Dr Pham).")
    _sign(sp1, "confirmed. PMID 30963591: randomized triple-blind trial of SP1 alone in 36 institutionalized elders "
          "with denture stomatitis; severity and Candida counts improved. Small trial; medium is appropriate.")


# ------------------------------------------------------- 2: replacements ---

REPLACEMENTS = {
    "STRAIN_COAGULANS_SNZ1969": {
        "old": "36372047", "new": "34119240", "strength": "medium", "direction": "positive_weak",
        "source_short": "Food Res Int (2021) - randomized placebo-controlled trial of B. coagulans SNZ 1969 alone, "
                        "n = 80 adults with mild intermittent constipation, 8 weeks",
        "basis": "Colonic transit time, complete spontaneous bowel movements (weeks 2 and 9) and bowel discomfort "
                 "improved vs placebo.",
        "why": "PMID 36372047 does not name SNZ 1969 (its abstract names B. coagulans Unique IS2); replaced by the "
               "direct SNZ 1969 RCT 34119240.",
        "scope": "SNZ 1969 named as the sole intervention vs placebo.",
    },
    "STRAIN_M18": {
        "old": "32250565", "new": "23449874", "strength": "medium", "direction": "positive_weak",
        "additional": ["37764667"],
        "source_short": "J Med Microbiol (2013) - randomized double-blind placebo-controlled trial of S. salivarius "
                        "M18 alone in 100 caries-active children, 3 months",
        "basis": "Plaque scores were lower with M18 at treatment end (P = 0.05). A 2023 RCT of an M18-only lozenge "
                 "(37764667, >= 5 x 10^8 CFU per lozenge, young adults with gingivitis) reduced the Gingival Index.",
        "why": "PMID 32250565 is an in-vitro study and cannot carry human evidence; replaced by the direct M18 RCT "
               "23449874 (supported by 37764667).",
        "scope": "M18 named as the sole intervention vs placebo in both trials (37764667 full text: Dentoblis, "
                 "S. salivarius M18 only).",
    },
    "STRAIN_COAGULANS_GBI30": {
        "old": "29196920", "new": "33110439", "strength": "medium", "direction": "unresolved",
        "source_short": "Nutr Metab (Lond) (2020) - randomized double-blind crossover trial, n = 30; milk protein "
                        "with vs without GBI-30, 6086 (1 x 10^9 CFU/day) for two weeks",
        "basis": "Primary outcomes are postprandial amino-acid AUC, Cmax and Tmax - pharmacokinetic surrogates, as "
                 "the registry records plasma amino-acid responses elsewhere. No patient-important outcome, and "
                 "none for the IBS indication, so no efficacy direction is established.",
        "why": "PMID 29196920 is a manufacturer-linked narrative review; replaced by the direct randomized "
               "crossover study 33110439.",
        "scope": "Randomized, double-blind, crossover design confirmed in the full text (PMC7585191); the control "
                 "arm is protein alone.",
    },
    "STRAIN_REUTERI_ATCC6475": {
        "old": "36261538", "new": "29926979", "strength": "medium", "direction": "positive_weak",
        "source_short": "J Intern Med (2018) - randomized placebo-controlled double-blind trial, 90 women aged "
                        "75-80 with low BMD, L. reuteri ATCC PTA 6475 10^10 CFU/day for 12 months",
        "basis": "Predefined primary endpoint met: less loss of tibia total volumetric BMD vs placebo (ITT mean "
                 "difference 1.02%, 95% CI 0.02-2.03); secondary bone variables were not significant in ITT.",
        "why": "PMID 36261538 is an exploratory secondary analysis of 20 selected good and poor responders; "
               "replaced by the primary RCT 29926979.",
        "scope": "ATCC PTA 6475 named as the sole intervention vs placebo.",
    },
    "STRAIN_CRISPATUS_CTV05": {
        "old": "35659905", "new": "32402161", "strength": "strong", "direction": "positive_strong",
        "additional": ["35659905"],
        "source_short": "N Engl J Med (2020) - phase 2b randomized double-blind placebo-controlled trial of "
                        "Lactin-V (L. crispatus CTV-05), 228 women after metronidazole for bacterial vaginosis",
        "basis": "Primary outcome met: BV recurrence by week 12 in 30% vs 45% (RR 0.66, 95% CI 0.44-0.87, "
                 "P = .01). The 66-person immunology substudy 35659905 is supportive mechanistic evidence only.",
        "why": "PMID 35659905 is an immunology substudy (IL-1 alpha, soluble E-cadherin); replaced by the primary "
               "phase-2b efficacy RCT 32402161.",
        "scope": "CTV-05 named as the sole intervention vs placebo; vaginal administration.",
    },
}


def replace_citations(by_id: dict, abstracts: dict) -> None:
    for sid, spec in REPLACEMENTS.items():
        entry = by_id[sid]
        old = entry["cfu_thresholds"]["evidence"]
        assert old["pmid"] == spec["old"], (sid, old["pmid"])
        evidence = {
            "type": "strain_specific_rct", "source_short": spec["source_short"], "pmid": spec["new"],
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{spec['new']}/", "verified_date": ON,
            "evidence_strength": spec["strength"],
            "clinical_support_level": {"strong": "high", "medium": "moderate"}[spec["strength"]],
            "effect_direction": spec["direction"], "effect_direction_basis": spec["basis"],
            "clinical_validation": {"q1_strain_explicit": "YES", "q3_human_clinical": "YES",
                                    "scope_verified_on": ON, "scope_verification_note": spec["scope"]},
            "previous_citation": {"pmid": old["pmid"], "source_short": old.get("source_short"),
                                  "type": old.get("type"), "evidence_strength": old.get("evidence_strength"),
                                  "swap_reason": f"Dr Pham {ON}: {spec['why']}", "swapped_date": ON},
        }
        if spec.get("additional"):
            evidence["additional_pmids"] = spec["additional"]
        assert spec["new"] in abstracts and all(p in abstracts for p in spec.get("additional", []))
        entry["cfu_thresholds"]["evidence"] = evidence
        entry["evidence_level"] = {"strong": "high", "medium": "moderate"}[spec["strength"]]
        _sign(entry, f"citation replaced. {spec['why']} {spec['basis']}")
        if STALE_NOTE in entry["cfu_thresholds"]["notes"]:
            _replace_note(entry, STALE_NOTE, f"Citation replaced after clinical review {ON} (Dr Pham).")
    atcc = by_id["STRAIN_REUTERI_ATCC6475"]
    assert atcc["notable_studies"].endswith("Human trials ongoing. (BioGaia)")
    atcc["notable_studies"] = (f"Dr Pham review {ON}: a 12-month RCT in 90 older women with low BMD met its primary "
                               "endpoint (less tibial volumetric BMD loss vs placebo). Testosterone, immune and skin "
                               "effects come from animal models only.")
    # Benefits resting only on animal models are not claims of this human record.
    assert atcc["key_benefits"] == ["bone health", "testosterone support", "immune modulation", "skin health"]
    atcc["key_benefits"] = ["bone health"]


# ---------------------------------------------------------- 2: withdrawn ---

WITHDRAWN = {
    HEAL9: {"pmid": "31734734", "partners": "L. paracasei 8700:2 (Probi Defendum)",
            "why": "PMID 31734734 tested HEAL9 + L. paracasei 8700:2 together, never HEAL9 alone, and was "
                   "under-recruited (131 randomized of 320 planned)",
            "identity": ["31734734"]},
    GR1: {"pmid": "12628548", "partners": "L. fermentum (now L. reuteri) RC-14",
          "why": "PMID 12628548 gave GR-1 + RC-14 together to every active participant; no component attribution",
          "identity": ["12628548"]},
    RC14: {"pmid": "12628548", "partners": "L. rhamnosus GR-1",
           "why": "PMID 12628548 gave GR-1 + RC-14 together; the paper's L. fermentum RC-14 naming is taxonomy "
                  "and provenance, not independent efficacy",
           "identity": ["12628548"]},
    R0052: {"pmid": "20974015", "partners": "B. longum R0175",
            "why": "PMID 20974015 studied the R0052 + R0175 formulation in humans; it cannot support R0052 alone",
            "identity": ["20974015"]},
    R0175: {"pmid": "20974015", "partners": "L. helveticus R0052",
            "why": "PMID 20974015 studied the R0052 + R0175 formulation in humans; it cannot support R0175 alone",
            "identity": ["20974015"]},
    LA5: {"pmid": "34405373", "partners": "B. lactis BB-12 (and in some trials LGG or other strains)",
          "why": "PMID 34405373 is ex vivo work on isolated human monocytes cultured with LA-5, not a "
                 "supplementation trial; the human LA-5 evidence found is combination evidence, which cannot "
                 "credit LA-5 alone",
          "identity": ["30439760", "39102225"]},
}


def withdraw(by_id: dict, contexts_by_pmid: dict) -> None:
    for sid, spec in WITHDRAWN.items():
        entry = by_id[sid]
        thresholds = entry["cfu_thresholds"]
        assert thresholds["dr_pham_signoff"] is True and thresholds["evidence"]["pmid"] == spec["pmid"], sid
        assert thresholds["dr_pham_signoff_verified_by"] == "agent:claude-code", sid
        assert "literature_review" not in entry and "identity_verification" not in entry, sid
        old = thresholds["evidence"]
        thresholds["evidence"] = None
        _sign(entry, f"withdrew the cited record as single-strain evidence: {spec['why']}. Reviewed - no qualifying "
                     "single-strain human evidence currently credited; the combination evidence stays at the "
                     "combination level.", signed=False)
        combination = sorted({pmid for c in entry.get("study_contexts") or [] for pmid in c["source_pmids"]}
                             | set(contexts_by_pmid.get(sid, [])))
        entry["literature_review"] = {
            "conclusion": "no_qualifying_human_evidence", "reason": "combination_only_human_research",
            "reviewed_on": ON, "reviewer": REVIEWER,
            "search_query": "Clinical adjudication of the cited record and the strain's recorded human studies, "
                            "with a PubMed search for a direct single-strain human trial (Dr Pham, 2026-09-22)",
            "pmids_screened": sorted(set(combination) | {spec["pmid"]}),
            "combination_pmids": combination,
            "ineligible_single_strain_pmids": [],
            "basis": BASIS_REL,
            "note": f"{spec['why']}. Tested with {spec['partners']}.",
            # What happened to the record that used to support this strain.
            "withdrawn_citation": {"pmid": old["pmid"], "source_short": old.get("source_short"),
                                   "type": old.get("type"), "evidence_strength": old.get("evidence_strength"),
                                   "withdrawn_on": ON, "withdrawn_by": REVIEWER, "reason": spec["why"]},
        }
        entry["identity_verification"] = {
            "status": "designation_verified", "source_pmids": spec["identity"], "deposit_ids": [],
            "verified_on": ON, "method": "PubMed efetch XML title/abstract read for the designation and species",
            "note": f"{ON}: the designation and species are named in PMID(s) {', '.join(spec['identity'])}.",
        }
        entry["evidence_level"] = "none"
        entry["key_benefits"] = []
        entry["notable_studies"] = (f"Dr Pham review {ON}: no qualifying single-strain human evidence. Human trials "
                                    f"test it only in combination with {spec['partners']}; those are recorded as "
                                    "combination studies and credit no single strain.")
        for old in (STALE_NOTE, "Strain-specific RCT or meta-analysis."):
            if old in thresholds["notes"]:
                _replace_note(entry, old, f"Cited record withdrawn as single-strain evidence {ON} (Dr Pham).")


def combination_records(by_id: dict, reviewed_at: str) -> dict:
    """The combination trials she kept as combination records, where none existed yet."""
    heal9 = {
        "context_id": "heal9_8700_child_common_cold_31734734", "source_pmids": ["31734734"],
        "identity_scope": "combination", "components": [HEAL9, P8700],
        "population": {"age_group": "child", "description": "131 healthy children aged 1-6 attending day care "
                                                             "(106 completed), one common-cold season"},
        "purpose": "prevention", "condition": "common_cold_children_day_care",
        "dose": {"basis": "unresolved", "unit": "CFU", "values": [1e9], "dosage_forms": [], "duration_days": 91,
                 "duration_as_printed": {"value": 3, "unit": "months"}, "co_therapies": [],
                 "dose_status": "combination_total_only", "dose_basis": "combination_total_daily",
                 "administration_frequency": "once_daily", "duration_basis": "fixed_protocol"},
        "outcomes": [
            {"name": "nasal_congestion_runny_nose_severity", "hierarchy": "unresolved", "kind": "patient_important", "direction": "positive"},
            {"name": "concomitant_medication_use", "hierarchy": "unresolved", "kind": "patient_important", "direction": "positive"},
            {"name": "day_care_absence_projected", "hierarchy": "post_hoc", "kind": "patient_important", "direction": "unresolved"},
        ],
        "trial_family": "probi_defendum_children_31734734",
        "limitations": [
            "Combination product (HEAL9 + L. paracasei 8700:2, Probi Defendum) with no single-strain arm; no "
            "component attribution.",
            "Under-recruited: 131 randomized of 320 planned; the day-care absence and daily-severity findings come "
            "from projecting the data to the planned sample size.",
            "The abstract does not name a primary endpoint.",
        ],
        "review_status": "clinician_approved", "study_design": "rct", "sample_size": 131, "blinding": "double",
        "funding": "unreported", "source_tier": "C", "trial_registration": None, "comparator": "placebo",
        "authored_on": ON, "authoring_method": "PubMed title/abstract read (efetch XML) for Dr Pham's 2026-09-22 review",
        "context_schema_version": "1.1.0", "evidence_role": "direct_rct",
        "component_registration_status": "fully_registered", "scoring_eligible": True,
        "clinical_review": _review(reviewed_at, "approve_as_combination_record"),
    }
    gr1 = {
        "context_id": "gr1_rc14_healthy_women_vaginal_flora_12628548", "source_pmids": ["12628548"],
        "identity_scope": "combination", "components": [GR1, RC14],
        "population": {"age_group": "adult", "description": "64 healthy women; daily oral capsules for 60 days"},
        "purpose": "physiology", "condition": "vaginal_microbiota_healthy_women",
        "dose": {"basis": "unresolved", "unit": "CFU", "values": [], "dosage_forms": ["capsule"],
                 "duration_days": 60, "co_therapies": [], "dose_status": "extraction_pending",
                 "dose_basis": "not_applicable", "duration_basis": "fixed_protocol"},
        "outcomes": [
            {"name": "asymptomatic_bv_microflora_restored_to_lactobacilli", "hierarchy": "unresolved", "kind": "surrogate", "direction": "positive"},
            {"name": "vaginal_lactobacilli_yeast_coliforms", "hierarchy": "unresolved", "kind": "surrogate", "direction": "positive"},
        ],
        "trial_family": "gr1_rc14_healthy_women_12628548",
        "limitations": [
            "Every active participant took GR-1 + RC-14 together; no component attribution.",
            "Microscopy flora restoration (37% vs 13%, P = 0.02) and culture counts are microbiota measures in "
            "healthy women, not symptomatic outcomes.",
            "Dose not stated in the abstract.",
        ],
        "review_status": "clinician_approved", "study_design": "rct", "sample_size": 64, "blinding": "unreported",
        "funding": "unreported", "source_tier": "C", "trial_registration": None, "comparator": "placebo",
        "authored_on": ON, "authoring_method": "PubMed title/abstract read (efetch XML) for Dr Pham's 2026-09-22 review",
        "context_schema_version": "1.1.0", "evidence_role": "direct_rct",
        "component_registration_status": "fully_registered", "scoring_eligible": True,
        "clinical_review": _review(reviewed_at, "approve_as_combination_record"),
    }
    added = {}
    for owner, context in ((HEAL9, heal9), (GR1, gr1)):
        existing = by_id[owner].setdefault("study_contexts", [])
        assert context["context_id"] not in {c["context_id"] for c in existing}
        existing.append(context)
        added[owner] = context["source_pmids"]
    # A partner that holds no copy still screened the trial.
    return {RC14: ["12628548"], R0175: ["20974015"]} | added


# ------------------------------------------ explicit direction on every summary ---
# Her rule, made total: a missing direction is unresolved, never positive (the scorer
# now fails closed). Every strain summary states its direction from the verified
# cited record:
#   positive_strong - the source's main between-group (or pooled) result for the strain is positive;
#   positive_weak   - positive only within-group, in one dose arm, as a secondary outcome or a ranking;
#   null            - the main result for the strain did not differ from control;
#   unresolved      - surrogate-only, a combination the strain cannot claim, or no human outcome.
# evidence_strength (certainty) is left as reviewed; direction is a separate axis.

DIRECTIONS = {
    "STRAIN_LGG": ("positive_strong", "ESPGHAN 2016 recommends LGG for paediatric AAD prevention (strong recommendation, "
                   "moderate quality of evidence)."),
    "STRAIN_SACCHAROMYCES": ("positive_strong", "ESPGHAN 2016 recommends S. boulardii for paediatric AAD prevention "
                             "(strong recommendation, moderate quality); C. difficile use is conditional, low quality."),
    "STRAIN_REUTERI_DSM17938": ("positive_strong", "Network meta-analysis (32 RCTs, 2,242 infants): DSM 17938 reduced "
                                "crying duration, the primary outcome."),
    "STRAIN_K12": ("positive_strong", "Primary outcome met: severe oral mucositis 36.6% vs 54.2% (P = .0351)."),
    "STRAIN_PLANTARUM_299V": ("positive_strong", "Between-group: abdominal pain resolved in all 20 treated vs 11 of 20 "
                              "placebo patients (P = 0.0012)."),
    "STRAIN_COAGULANS_MTCC5856": ("positive_weak", "Network meta-analysis ranking (SUCRA) for abdominal pain and IBS-D "
                                  "stool form; a ranking, not a direct between-group estimate."),
    "STRAIN_RHAMNOSUS_HN001": ("positive_weak", "Lower postpartum depression and anxiety scores, a secondary outcome "
                               "(primary: offspring eczema)."),
    "STRAIN_RHAMNOSUS_SP1": ("positive_weak", "Denture-stomatitis severity and Candida counts fell significantly within "
                             "the probiotic group only; small trial (n = 36)."),
    "STRAIN_REUTERI_PRODENTIS": ("positive_weak", "Pilot RCT (n = 20): periodontal parameters improved within the test "
                                 "group; no between-group estimate in the abstract."),
    "STRAIN_COAGULANS_IS2": ("positive_weak", "Primary aim was protein absorption (plasma amino acids, a surrogate); "
                             "leg-press and vertical-jump power improved as secondary outcomes."),
    "STRAIN_GASSERI_SBT2055": ("positive_weak", "Visceral fat fell from baseline in both dose groups and not in control; "
                               "the abstract reports within-group changes."),
    "STRAIN_GASSERI_BNR17": ("positive_weak", "Visceral fat fell vs placebo in the high-dose arm only (P = .038); waist "
                             "changes were within-group."),
    "STRAIN_ACIDOPHILUS_DDS1": ("positive_strong", "Single-strain DDS-1 arm vs placebo met the primary outcome, abdominal "
                                "pain severity (P = 0.001), with IBS-SSS improvement."),
    "STRAIN_LACTIS_UABla12": ("positive_strong", "Single-strain UABla-12 arm vs placebo met the primary outcome, abdominal "
                              "pain severity (P = 0.001), with IBS-SSS improvement."),
    "STRAIN_LONGUM_BB536": ("unresolved", "Faecal bifidobacteria rose and influenza-vaccine HI titres did not change; the "
                            "immune findings are biomarkers or subgroup results. Surrogate-only, so no efficacy credit "
                            "(the GBI-30 rule)."),
    "STRAIN_BREVE_M16V": ("unresolved", "The cited RCT tested M-16V + HN019 + HN001 together (fever duration shortened "
                          "for the mixture); a combination result cannot credit M-16V alone."),
    "STRAIN_CASEI_431": ("null", "Human RCT (n = 1,104): the primary outcome, influenza seroprotection, was not "
                         "improved; upper-respiratory symptom duration was shorter as a secondary outcome."),
    "STRAIN_PARACASEI_8700": ("unresolved", "The cited record is a PCR identification method paper; no human outcome."),
    "STRAIN_ACIDOPHILUS_NCFM": ("unresolved", "The cited record is a monocolonized-mouse study; no human outcome."),
    "STRAIN_SUBTILIS_DE111": ("unresolved", "The cited record is a mouse study; no human outcome."),
    "STRAIN_LACTIS_BL04": ("unresolved", "The cited record is an in-vitro study; no human outcome."),
    "STRAIN_FERMENTUM_ME3": ("unresolved", "The cited record is a narrative article; no human outcome reported."),
    "STRAIN_LONGUM_1714": ("unresolved", "The cited record is a genomics and neurotranscriptomics laboratory study; no "
                           "human outcome."),
    "STRAIN_CLAUSII": ("unresolved", "The cited record is a narrative review with no pooled effect estimate."),
}

# Source-type labels the 2026-04-21 automated pass got wrong, corrected from the live record.
TYPE_FIXES = {
    "STRAIN_CASEI_431": ("animal_model", "strain_specific_rct"),
    "STRAIN_ACIDOPHILUS_DDS1": ("limited_or_non_clinical_source", "strain_specific_rct"),
    "STRAIN_LACTIS_UABla12": ("limited_or_non_clinical_source", "strain_specific_rct"),
    "STRAIN_PARACASEI_8700": ("animal_model", "laboratory_method_study"),
    "STRAIN_FERMENTUM_ME3": ("animal_model", "narrative_review"),
    "STRAIN_LONGUM_1714": ("animal_model", "laboratory_study"),
}
DDS1_UABLA12_TITLE = ("Nutrients (2020) - Lactobacillus acidophilus DDS-1 and Bifidobacterium lactis UABla-12 improve "
                      "abdominal pain severity and symptomology in irritable bowel syndrome: randomized controlled trial")


def record_directions(by_id: dict) -> None:
    for sid, (direction, basis) in DIRECTIONS.items():
        evidence = by_id[sid]["cfu_thresholds"]["evidence"]
        assert isinstance(evidence, dict) and not evidence.get("effect_direction"), sid
        evidence["effect_direction"] = direction
        evidence["effect_direction_basis"] = f"{basis} (Direction recorded {ON} from the verified cited record.)"
    for sid, (old, new) in TYPE_FIXES.items():
        evidence = by_id[sid]["cfu_thresholds"]["evidence"]
        assert evidence["type"] == old, (sid, evidence["type"])
        evidence["type"] = new
        evidence["type_correction"] = f"{ON}: the live PubMed record is a {new.replace('_', ' ')}, not {old.replace('_', ' ')}."
    for sid in ("STRAIN_ACIDOPHILUS_DDS1", "STRAIN_LACTIS_UABla12"):
        evidence = by_id[sid]["cfu_thresholds"]["evidence"]
        assert evidence["source_short"] == "Nutrients — " and evidence["clinical_validation"]["q1_strain_explicit"] == "NO"
        evidence["source_short"] = DDS1_UABLA12_TITLE
        evidence["clinical_validation"]["q1_strain_explicit"] = "YES"
        evidence["clinical_validation"]["scope_verified_on"] = ON
        evidence["clinical_validation"]["scope_verification_note"] = (
            "Three-arm RCT with separate single-strain DDS-1 and UABla-12 arms vs placebo (1 x 10^10 CFU/day, 6 weeks).")
    c431 = by_id["STRAIN_CASEI_431"]["cfu_thresholds"]["evidence"]
    c431["clinical_validation"] = {"q1_strain_explicit": "YES", "q3_human_clinical": "YES", "scope_verified_on": ON,
                                   "scope_verification_note": "Randomized double-blind placebo-controlled trial, "
                                   "1,104 healthy adults, >= 10^9 CFU L. casei 431 daily for 42 days."}
    c431["type_correction"] += (" Dr Pham's 2026-04-21 downgrade cited the animal-model label; the strength stays at "
                                "her 'weak' pending her re-review.")
    replaced = REPLACEMENTS["STRAIN_REUTERI_ATCC6475"]
    atcc = by_id["STRAIN_REUTERI_ATCC6475"]["cfu_thresholds"]["evidence"]
    assert atcc["effect_direction"] == replaced["direction"] == "positive_weak"
    atcc["effect_direction"] = "positive_strong"  # the predefined primary endpoint was met


def nissle(by_id: dict) -> None:
    """Dr Pham's 2026-09-22 adjudication: affirmative active-comparator evidence, not null,
    and not ordinary placebo-superiority credit."""
    entry = by_id["STRAIN_NISSLE_1917"]
    evidence = entry["cfu_thresholds"]["evidence"]
    assert evidence["pmid"] == "15479682" and evidence["clinical_validation"]["q3_human_clinical"] == "NO"
    evidence.update({
        "type": "strain_specific_active_comparator_rct",
        "evidence_strength": "medium", "clinical_support_level": "moderate",
        "effect_direction": "unresolved",
        "effect_direction_basis": (
            "Randomized double-blind double-dummy trial, 327 adults with ulcerative colitis in remission, Nissle 1917 vs "
            "mesalazine for 12 months: the prespecified primary aim, equivalence in preventing relapse, was met "
            "(per-protocol relapse 36.4% vs 33.9%, equivalence p = 0.003); a 120-patient double-blind trial (9354192) "
            "found similar relapse rates. Affirmative active-comparator evidence, not a null result. The scorer has no "
            "weighting for equivalence against an active control, so it earns no placebo-superiority credit until one "
            f"exists (Dr Pham, {ON})."),
        "additional_pmids": ["9354192"],
    })
    evidence["clinical_validation"].update({"q3_human_clinical": "YES", "scope_verified_on": ON,
                                            "scope_verification_note": "Human RCT; the comparator is mesalazine, not placebo."})
    assert entry["key_benefits"] == ["ulcerative colitis remission", "IBD support", "intestinal barrier function"]
    entry["key_benefits"] = ["ulcerative colitis remission"]
    entry["evidence_level"] = "moderate"
    _sign(entry, "the replacement citation 15479682 is a substantial human efficacy trial, not 'not a human trial': "
          "randomized, double-blind, double-dummy, 327 adults with ulcerative colitis in remission, Nissle 1917 vs "
          "mesalazine for 12 months, prespecified equivalence in relapse prevention met. Record as positive/supportive "
          "active-comparator equivalence evidence for UC maintenance, medium strength, not the evidential class of "
          "placebo superiority; no ordinary superiority credit until the scorer can weight active-comparator "
          "evidence.")


# ------------------------------------------------------------ 3: spot-check ---

def spot_check(by_id: dict, reviewed_at: str) -> None:
    d1 = [c for e in by_id.values() for c in e.get("study_contexts") or []
          if (c.get("clinical_review") or {}).get("reviewer", "").startswith("Claude Opus 5 research review (closure D1")]
    assert len(d1) == 18, len(d1)
    for context in d1:
        _countersign(context, reviewed_at, "Section 3 spot-check: disposition unchanged.")
    cu1 = next(c for c in d1 if c["context_id"] == "cu1_elderly_common_infectious_disease_26640504")
    cu1["limitations"][0] = ("The primary endpoint, cumulative days with common infectious-disease symptoms in all "
                             "100 participants, was not reduced (5.1 vs 6.6 days, P = 0.2015).")
    cu1["limitations"][1] = ("The fewer respiratory-infection episodes come from a post hoc analysis of the "
                             "44-participant biological-sampling subset (the authors note it may be chance); the "
                             "immune findings come from the same subset.")
    cu1["limitations"].append("PMID 27825987 is the safety characterization of the same CU1 program, not "
                              "independent confirmatory efficacy evidence.")
    cu1["clinical_review"]["countersign_note"] = (
        "Section 3 spot-check: primary clinical endpoint null; the respiratory finding is a post hoc n = 44 subset "
        "result; 27825987 is safety data. Disposition unchanged.")


# ----------------------------------------------------------------- driver ---

def apply(registry: dict, abstracts: dict, reviewed_at: str) -> list[str]:
    from probiotic_measurements import identity_review_accepted, strain_literature_review_concluded
    from studied_formulas import valid_native_study_context

    by_id = {e["id"]: e for e in registry["clinically_relevant_strains"]}
    restore_bi07_bb12(by_id, reviewed_at)
    approve_la5_combinations(by_id, reviewed_at)
    confirm(by_id)
    replace_citations(by_id, abstracts)
    screened = combination_records(by_id, reviewed_at)
    withdraw(by_id, screened)
    nissle(by_id)
    record_directions(by_id)
    spot_check(by_id, reviewed_at)

    for sid in WITHDRAWN:
        assert strain_literature_review_concluded(by_id[sid]) and not identity_review_accepted(by_id[sid]), sid
    known = set(by_id)
    for entry in by_id.values():
        for context in entry.get("study_contexts") or []:
            review = context.get("clinical_review") or {}
            if review.get("basis") != BASIS_REL and review.get("countersigned_by") != REVIEWER:
                continue  # only the records this review wrote or countersigned
            for component in context["components"]:
                if component in known:
                    assert valid_native_study_context(context, component), (entry["id"], context["context_id"])
    for sid in (BI07, BB12):
        assert identity_review_accepted(by_id[sid]), sid
    directions = {"positive_strong", "positive_weak", "mixed", "null", "negative", "unresolved"}
    for entry in by_id.values():
        evidence = (entry.get("cfu_thresholds") or {}).get("evidence")
        if evidence:
            assert evidence.get("effect_direction") in directions, entry["id"]

    # Three 2026-04-21 records name only the agent as verifier although their own
    # note records Dr Pham's review and downgrade; the verifier field follows the note.
    for sid in ("STRAIN_PARACASEI_8700", "STRAIN_CLAUSII", "STRAIN_CASEI_431"):
        thresholds = by_id[sid]["cfu_thresholds"]
        assert thresholds["dr_pham_signoff_verified_by"] == "agent:claude-code", sid
        assert "2026-04-21: Dr Pham reviewed + downgraded" in thresholds["dr_pham_signoff_verification_note"], sid
        thresholds["dr_pham_signoff_verified_by"] = "Dr Pham (2026-04-21 review and downgrade) + agent:claude-code"
    signed = [e for e in by_id.values() if (e.get("cfu_thresholds") or {}).get("dr_pham_signoff") is True]
    assert not [e["id"] for e in signed if e["cfu_thresholds"].get("dr_pham_signoff_verified_by") == "agent:claude-code"]
    meta = registry["_metadata"]
    meta["signoff_status_note"] = (
        f"{len(signed)}/{len(by_id)} entries carry a clinician sign-off, each recorded by Dr Pham or a clinical "
        f"reviewer (2026-04-21 or {ON}); none rests on an automated PMID check alone. On {ON} Dr Pham restored "
        "Bi-07 and BB-12 (suspended 2026-09-04) on identity-correct human evidence, confirmed 12 citations, replaced "
        "5 with direct human trials and withdrew 6 as single-strain evidence (combination or ex vivo records). "
        "Sign-off does not establish positive effect, applicability to every label, or completeness of the "
        "literature search.")
    old = "Bi-07 and BB-12 stay under their suspended clinician sign-off."
    assert old in meta["literature_review_note_2026_09_22"]
    meta["literature_review_note_2026_09_22"] = meta["literature_review_note_2026_09_22"].replace(
        old, "Bi-07 and BB-12 were left to the clinician gate (restored by Dr Pham the same day; see "
             "clinical_review_note_2026_09_22).")
    meta["clinical_review_note_2026_09_22"] = (
        f"Dr Pham's clinical review of the {ON} sign-off sheet: Bi-07 and BB-12 sign-offs restored (reviewed, not "
        "broadly effective); the two held LA-5 + BB-12 trials approved as literal combination records with their "
        "unregistered third strain; 12 sign-offs confirmed (LGG, S. boulardii, 299v and HN001 recorded as medium; "
        "Shirota and 35624 null), 5 citations replaced with direct human trials (SNZ 1969, M18, GBI-30 6086, ATCC "
        "PTA 6475, CTV-05), 6 withdrawn as single-strain evidence (HEAL9, GR-1, RC-14, R0052, R0175, LA-5); the 18 "
        "closure-D1 records countersigned (CU1 wording corrected); Nissle 1917 recorded as human active-comparator "
        "equivalence evidence (no superiority credit until the scorer can weight it). Every strain evidence summary "
        "now states an explicit effect_direction (a missing one scores nothing), and six mislabelled source types "
        f"were corrected from the live records. Every cited PMID content-verified live. Basis: {BASIS_REL}.")
    return sorted(set(WITHDRAWN) | set(REPLACEMENTS) | set(DIRECTIONS) | {BI07, BB12, HEAL9, GR1, "STRAIN_NISSLE_1917"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raw = REG.read_text(encoding="utf-8")
    registry = json.loads(raw)
    assert json.dumps(registry, indent=2, ensure_ascii=False) + "\n" == raw, "registry not in canonical form"
    ledger = json.loads((ROOT / BASIS_REL).read_text(encoding="utf-8"))
    assert all(not row["claims_failed"] for row in ledger["pmids"].values()), "unverified claim in the ledger"
    reviewed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = deepcopy(registry)
    apply(registry, ledger["pmids"], reviewed_at)
    changed = [a["id"] for a, b in zip(registry["clinically_relevant_strains"], before["clinically_relevant_strains"])
               if a != b]
    print(f"{len(changed)} identities changed:", ", ".join(changed))
    if args.apply:
        REG.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written", REG.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
