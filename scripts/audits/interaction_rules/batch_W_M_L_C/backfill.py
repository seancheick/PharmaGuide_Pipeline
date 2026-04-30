#!/usr/bin/env python3
"""
Batch W/M/L/C — clinician-locked interaction rules (2026-04-30).

Adds 35 new drug_class_rules across four families:
  W (warfarin/anticoagulants): 10 rules — W1-W9, W11-W12 (W10 bromelain deferred, no subject_ref)
  M (MAO inhibitors):           7 rules — M1, M3-M8 (M2 tyramine deferred, no subject_ref)
  L (lithium):                  7 rules — L1-L7
  C (CYP3A4 / grapefruit):     10 rules — C1-C10

Plus pre-seeded pregnancy_lactation tags from clinician notes for affected
subjects (Ginkgo, Dong Quai, Panax Ginseng, Yohimbe, Goldenseal, Berberine).

Schema unchanged — drug_class_rules already supports the full payload
(severity, evidence_level, mechanism, action, sources, alert_headline,
alert_body, informational_note).

Idempotent: re-running detects existing rules by drug_class_id+subject and
skips. Subjects with no existing rule entry get a new entry created.

Deferred (flagged for next batch — no subject_ref in current refs):
  W10  Bromelain × anticoagulants     (severity: monitor)
  M2   Tyramine-rich extracts × MAOIs  (severity: contraindicated; Section 6 open call)

Section 6 open severity calls — locked to Position A per clinician table:
  M2  Tyramine × MAOIs        → contraindicated  [DEFERRED — no subject_ref]
  M5  Yohimbe × MAOIs         → contraindicated  [APPLIED]
  L4  Turmeric × Lithium      → monitor          [APPLIED]
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "ingredient_interaction_rules.json"

# Common source URLs (clinician references)
SRC_NIH_K = "https://ods.od.nih.gov/factsheets/VitaminK-HealthProfessional/"
SRC_NCCIH = "https://www.nccih.nih.gov/health"
SRC_MHRA_CRANBERRY = "https://www.gov.uk/drug-safety-update/cranberry-juice-and-warfarin"
SRC_MEDLINEPLUS = "https://medlineplus.gov/druginfo/natural"
SRC_PUBMED = "https://pubmed.ncbi.nlm.nih.gov"


def rule(severity, evidence_level, mechanism, action, headline, body, note, sources):
    return {
        "severity": severity,
        "evidence_level": evidence_level,
        "mechanism": mechanism,
        "action": action,
        "sources": sources,
        "alert_headline": headline,
        "alert_body": body,
        "informational_note": note,
    }


# ---------------------------------------------------------------------------
# Rule manifest: list of (subject_ref_db, subject_canonical_id, drug_class_id, rule_payload, optional pregnancy_seed)
# ---------------------------------------------------------------------------

# Drug-class rule template builder for warfarin/anticoagulants family
def w_rule(severity, mech, action, headline, body, note, sources):
    return rule(severity, "established", mech, action, headline, body, note, sources)


W_RULES = [
    # W1 Vitamin K × anticoagulants
    ("ingredient_quality_map", "vitamin_k", "anticoagulants", w_rule(
        "avoid",
        "Vitamin K opposes warfarin's anticoagulant action via the vitamin-K-dependent clotting cascade. INR destabilization risk; clinical principle is intake consistency, not absolute abstinence.",
        "If you take warfarin or another vitamin-K antagonist, do not start, stop, or change vitamin K intake without checking with your prescriber. Keep daily intake consistent.",
        "May counteract warfarin",
        "Vitamin K can reduce the effect of warfarin and similar blood thinners. Talk to your prescriber before adding a vitamin K supplement and keep your daily intake steady.",
        "Vitamin K affects how warfarin works — relevant to anyone on warfarin or coumarin anticoagulants.",
        [f"{SRC_NIH_K}", f"{SRC_PUBMED}/16009864/", f"{SRC_PUBMED}/16027256/"],
    )),
    # W2 Ginkgo × anticoagulants/antiplatelets
    ("ingredient_quality_map", "ginkgo", "anticoagulants", w_rule(
        "avoid",
        "Ginkgo inhibits platelet aggregation (PAF antagonism). Bleeding risk amplified with warfarin or antiplatelet therapy.",
        "If you take warfarin, aspirin, or another antiplatelet/anticoagulant, avoid ginkgo unless your prescriber clears it.",
        "Bleeding risk with blood thinners",
        "Ginkgo can thin the blood and may increase bleeding when combined with warfarin or antiplatelet medication.",
        "Ginkgo has antiplatelet activity — relevant to anyone on blood-thinning medication.",
        [f"{SRC_PUBMED}/26604801/", f"{SRC_PUBMED}/9355003/"],
    )),
    # W3 Garlic × anticoagulants/antiplatelets
    ("ingredient_quality_map", "garlic", "anticoagulants", w_rule(
        "monitor",
        "Allicin/ajoene give garlic mild antiplatelet activity at supplement doses (≥600 mg/day extract). Standalone risk modest; severity escalates when combined with antiplatelets.",
        "If you take warfarin or an antiplatelet, monitor for bruising or bleeding when adding a garlic supplement.",
        "Mild bleeding risk with blood thinners",
        "High-dose garlic supplements can mildly thin the blood. Combined with warfarin or aspirin-type drugs, this can increase bleeding risk.",
        "Garlic supplements at high dose can affect platelet function — relevant to anyone on blood thinners.",
        [f"{SRC_PUBMED}/17875983/"],
    )),
    # W4 Fish oil / omega-3 × anticoagulants/antiplatelets
    ("ingredient_quality_map", "fish_oil", "anticoagulants", w_rule(
        "caution",
        "Antiplatelet/antithrombotic at high dose. Most dietary doses (1-2 g/day EPA+DHA) clinically insignificant; ≥3 g/day raises bleeding risk in patients on warfarin or antiplatelets.",
        "If you take warfarin or an antiplatelet, talk to your prescriber before using fish oil ≥3 g/day. Doses below 3 g/day are generally well tolerated.",
        "Bleeding risk at high doses",
        "Fish oil at 3 g/day or higher can thin the blood. Combined with warfarin or antiplatelet medication, this raises bleeding risk.",
        "Omega-3 has dose-dependent antiplatelet activity — most relevant at total EPA+DHA ≥3 g/day.",
        [f"{SRC_PUBMED}/17786535/", f"{SRC_PUBMED}/24620997/"],
    )),
    # W5 Turmeric × anticoagulants
    ("ingredient_quality_map", "turmeric", "anticoagulants", w_rule(
        "caution",
        "Antiplatelet activity at clinical doses (≥500 mg curcuminoids). Multiple case reports of INR elevation with warfarin. Culinary turmeric doses do not interact meaningfully.",
        "If you take warfarin or an antiplatelet, talk to your prescriber before using high-dose turmeric or curcumin extracts (≥500 mg curcuminoids/day).",
        "May increase bleeding with warfarin",
        "High-dose turmeric or curcumin extracts can thin the blood and raise INR in people on warfarin. Cooking-amount turmeric is fine.",
        "Standardized curcumin extracts have antiplatelet activity at clinical doses — relevant to anyone on blood thinners.",
        [f"{SRC_PUBMED}/26361079/"],
    )),
    ("ingredient_quality_map", "curcumin", "anticoagulants", w_rule(
        "caution",
        "Curcumin has antiplatelet activity at clinical doses (≥500 mg/day). Multiple case reports of INR elevation with warfarin.",
        "If you take warfarin or an antiplatelet, talk to your prescriber before using curcumin extracts ≥500 mg/day.",
        "May increase bleeding with warfarin",
        "High-dose curcumin extracts can thin the blood and raise INR in people on warfarin.",
        "Curcumin has antiplatelet activity at clinical doses — relevant to anyone on blood thinners.",
        [f"{SRC_PUBMED}/26361079/"],
    )),
    # W6 St John's Wort × warfarin (CYP3A4 induction)
    ("ingredient_quality_map", "st_johns_wort", "anticoagulants", w_rule(
        "contraindicated",
        "CYP3A4 induction reduces warfarin S-enantiomer exposure → loss of anticoagulation. Documented thrombotic events including strokes and pulmonary emboli.",
        "Do not combine St. John's Wort with warfarin or other vitamin-K antagonists. Discuss alternatives with your prescriber.",
        "Do not combine with warfarin",
        "St. John's Wort speeds up the breakdown of warfarin, which can stop it from working and lead to dangerous blood clots.",
        "St. John's Wort is a strong CYP3A4 inducer — relevant to anyone on warfarin or many other prescription drugs.",
        [f"{SRC_PUBMED}/12190769/", f"{SRC_PUBMED}/12595722/"],
    )),
    # W7 CoQ10 × warfarin
    ("ingredient_quality_map", "coq10", "anticoagulants", w_rule(
        "monitor",
        "Structural similarity to vitamin K; mild reduction in warfarin effect at high dose (≥100 mg/day). Effect is small but documented.",
        "If you take warfarin, mention CoQ10 supplements to your prescriber. INR monitoring may need to be adjusted.",
        "May mildly reduce warfarin effect",
        "CoQ10 is structurally similar to vitamin K and can slightly reduce how well warfarin works at higher doses.",
        "CoQ10 may affect INR at high doses — relevant to anyone on warfarin.",
        [f"{SRC_PUBMED}/15100776/"],
    )),
    # W8 Dong Quai × anticoagulants
    ("ingredient_quality_map", "dong_quai", "anticoagulants", w_rule(
        "avoid",
        "Coumarin content plus antiplatelet phytochemicals. Multiple case reports of INR elevation in patients on warfarin.",
        "If you take warfarin or an antiplatelet, avoid dong quai unless cleared by your prescriber.",
        "Bleeding risk with blood thinners",
        "Dong quai contains natural coumarins and antiplatelet compounds. Combined with warfarin, this can dangerously raise INR.",
        "Dong quai has documented warfarin interaction — relevant to anyone on blood thinners.",
        [f"{SRC_PUBMED}/10440462/"],
    )),
    # W9 Ginseng × warfarin
    ("ingredient_quality_map", "ginseng", "anticoagulants", w_rule(
        "caution",
        "Mixed evidence — some studies show reduced INR (efficacy reduction); others null. Effect appears variable across products and individuals.",
        "If you take warfarin, talk to your prescriber before using ginseng. INR may need re-checking after starting.",
        "May affect warfarin levels",
        "Panax ginseng has mixed evidence for changing how warfarin works. INR monitoring is recommended if you start a ginseng supplement.",
        "Ginseng may interact with warfarin — relevant to anyone on anticoagulants.",
        [f"{SRC_PUBMED}/15226167/"],
    )),
    # W10 Bromelain — DEFERRED (no subject_ref in current refs)
    # W11 Vitamin E × anticoagulants
    ("ingredient_quality_map", "vitamin_e", "anticoagulants", w_rule(
        "caution",
        "Antiplatelet activity at high doses (≥400 IU/day) via vitamin K-epoxide reductase competition.",
        "If you take warfarin or an antiplatelet, talk to your prescriber before using vitamin E ≥400 IU/day.",
        "Bleeding risk at high doses",
        "Vitamin E above 400 IU/day can mildly thin the blood and raise bleeding risk when combined with warfarin or aspirin-type drugs.",
        "Vitamin E at high dose has antiplatelet effect — relevant to anyone on blood thinners.",
        [f"{SRC_PUBMED}/17984381/", f"{SRC_PUBMED}/9619397/"],
    )),
    # W12 Cranberry × warfarin
    ("ingredient_quality_map", "cranberry", "anticoagulants", w_rule(
        "monitor",
        "Inhibits CYP2C9 → may increase warfarin S-enantiomer exposure → ↑ INR. UK MHRA issued formal advisory in 2003; clinical evidence since has been mixed but the signal is real at high cranberry doses.",
        "If you take warfarin, monitor INR when using cranberry extract or drinking ≥1 L cranberry juice/day.",
        "May raise INR on warfarin",
        "High-dose cranberry extracts or large amounts of cranberry juice can raise INR in people on warfarin. Mention cranberry use to your prescriber.",
        "Cranberry may increase warfarin levels at high doses — UK MHRA issued an advisory.",
        [SRC_MHRA_CRANBERRY, f"{SRC_PUBMED}/16846311/"],
    )),
]


def m_rule(severity, mech, action, headline, body, note, sources, evidence_level="established"):
    return rule(severity, evidence_level, mech, action, headline, body, note, sources)


M_RULES = [
    # M1 PEA × MAOIs
    ("ingredient_quality_map", "phenylethylamine", "maois", m_rule(
        "contraindicated",
        "PEA is a direct MAO substrate; combination with MAOIs causes hypertensive crisis.",
        "Do not combine PEA-containing supplements with MAOIs. Discontinue MAOI for the appropriate washout period before any PEA-containing product.",
        "Do not combine with MAOIs",
        "PEA combined with MAO-inhibitor antidepressants can cause a dangerous spike in blood pressure.",
        "PEA is an MAO substrate — relevant to anyone taking phenelzine, tranylcypromine, selegiline, or related drugs.",
        [f"{SRC_PUBMED}/8854272/"],
    )),
    # M2 Tyramine — DEFERRED
    # M3 5-HTP × MAOIs
    ("ingredient_quality_map", "5_htp", "maois", m_rule(
        "contraindicated",
        "Serotonin precursor combined with MAOI inhibition → serotonin syndrome.",
        "Do not combine 5-HTP with MAOIs. Allow appropriate washout between MAOI discontinuation and 5-HTP use.",
        "Do not combine with MAOIs",
        "5-HTP raises serotonin levels and can cause serotonin syndrome when combined with MAO-inhibitor antidepressants.",
        "5-HTP increases serotonin — relevant to anyone on MAOIs, SSRIs, SNRIs, or other serotonergic drugs.",
        [f"{SRC_PUBMED}/9764773/"],
    )),
    # M3 alt — L-Tryptophan × MAOIs (new rule entry — l_tryptophan has no rule yet)
    ("ingredient_quality_map", "l_tryptophan", "maois", m_rule(
        "contraindicated",
        "Serotonin precursor combined with MAOI inhibition → serotonin syndrome.",
        "Do not combine L-tryptophan with MAOIs.",
        "Do not combine with MAOIs",
        "L-tryptophan raises serotonin levels and can cause serotonin syndrome when combined with MAO-inhibitor antidepressants.",
        "L-tryptophan increases serotonin — relevant to anyone on MAOIs, SSRIs, SNRIs, or other serotonergic drugs.",
        [f"{SRC_PUBMED}/9764773/"],
    )),
    # M4 St John's Wort × MAOIs
    ("ingredient_quality_map", "st_johns_wort", "maois", m_rule(
        "contraindicated",
        "Hypericin has weak MAO-A inhibition; combination duplicates mechanism → serotonin syndrome and hypertensive risk.",
        "Do not combine St. John's Wort with MAOIs.",
        "Do not combine with MAOIs",
        "St. John's Wort has its own MAO-inhibiting activity. Combined with prescription MAOIs, this can cause serotonin syndrome or dangerous blood pressure changes.",
        "St. John's Wort has serotonergic and MAO-A activity — relevant to anyone on MAOIs.",
        [f"{SRC_PUBMED}/12595722/"],
    )),
    # M5 Yohimbe × MAOIs (Section 6 Position A: contraindicated)
    ("ingredient_quality_map", "yohimbe", "maois", m_rule(
        "contraindicated",
        "Alpha-2 antagonist increases norepinephrine release; combined with MAO inhibition → severe hypertension. Common in pre-workout and male-enhancement stacks where users may not connect the dots.",
        "Do not combine yohimbe with MAOIs. Many pre-workout and male-enhancement supplements contain yohimbe — read labels carefully.",
        "Do not combine with MAOIs",
        "Yohimbe combined with MAO-inhibitor antidepressants can cause severe high blood pressure. Many pre-workout and 'male enhancement' supplements contain yohimbe.",
        "Yohimbe is a sympathomimetic — relevant to anyone on MAOIs.",
        [f"{SRC_PUBMED}/11448560/"],
    )),
    # M6 Ginseng × MAOIs (caution)
    ("ingredient_quality_map", "ginseng", "maois", m_rule(
        "caution",
        "Multiple case reports of hypertensive episodes when combined with MAOIs (especially phenelzine). Evidence is thinner than M1-M5 but real.",
        "If you take an MAOI, talk to your prescriber before using Panax or American ginseng.",
        "May raise blood pressure with MAOIs",
        "Panax ginseng combined with MAO-inhibitor antidepressants has been linked to high blood pressure in case reports.",
        "Ginseng may interact with MAOIs — relevant to anyone on phenelzine or similar drugs.",
        [f"{SRC_PUBMED}/3624381/"],
        evidence_level="possible",
    )),
    # M7 Hordenine × MAOIs
    ("banned_recalled_ingredients", "ADD_HORDENINE", "maois", m_rule(
        "contraindicated",
        "Hordenine is a β-PEA analog and direct MAO substrate. Often combined with PEA in pre-workout / fat-burner stacks, compounding the risk.",
        "Do not combine hordenine with MAOIs. Avoid pre-workout and fat-burner products listing hordenine if you take an MAOI.",
        "Do not combine with MAOIs",
        "Hordenine works like PEA and can cause dangerous blood pressure changes with MAO-inhibitor antidepressants.",
        "Hordenine is an MAO substrate — relevant to anyone on MAOIs.",
        [f"{SRC_PUBMED}/17612452/"],
    )),
    # M8 SAMe × MAOIs
    ("ingredient_quality_map", "same", "maois", m_rule(
        "avoid",
        "Methyl donor with antidepressant activity; serotonergic potentiation when combined with MAOIs raises serotonin syndrome risk.",
        "If you take an MAOI, avoid SAMe unless cleared by your prescriber. Allow washout if switching.",
        "Avoid combining with MAOIs",
        "SAMe has antidepressant-like activity. Combined with MAO-inhibitor antidepressants, it can raise the risk of serotonin syndrome.",
        "SAMe is serotonergic — relevant to anyone on MAOIs or other antidepressants.",
        [f"{SRC_PUBMED}/12420308/"],
    )),
]


def l_rule(severity, mech, action, headline, body, note, sources, evidence_level="established"):
    return rule(severity, evidence_level, mech, action, headline, body, note, sources)


L_RULES = [
    # L1 Caffeine × lithium
    ("ingredient_quality_map", "caffeine", "lithium", l_rule(
        "caution",
        "Caffeine increases renal clearance of lithium → reduced levels and reduced efficacy. Withdrawal of caffeine raises levels → toxicity risk. Bidirectional risk: keep caffeine intake CONSISTENT, not just low.",
        "If you take lithium, keep your daily caffeine intake steady. Sudden increases or decreases in caffeine can change your lithium levels.",
        "Keep caffeine intake consistent",
        "Caffeine changes how your kidneys clear lithium. Big changes in coffee, tea, or caffeine pill use can swing lithium levels in either direction. Talk to your prescriber if your caffeine habits are changing.",
        "Caffeine affects lithium clearance — relevant to anyone on lithium therapy.",
        [f"{SRC_PUBMED}/7775360/"],
    )),
    # L2 Psyllium × lithium
    ("ingredient_quality_map", "psyllium", "lithium", l_rule(
        "monitor",
        "Reduces lithium absorption when taken concurrently. Separate dosing by 1-2 hours.",
        "If you take lithium, separate psyllium and high-fiber supplements from your lithium dose by at least 2 hours.",
        "May reduce lithium absorption",
        "Psyllium and other high-fiber supplements can reduce how much lithium your body absorbs if taken at the same time. Space them apart by 2 hours.",
        "Psyllium can interfere with lithium absorption — relevant to anyone on lithium.",
        [f"{SRC_PUBMED}/2295586/"],
    )),
    # L3 Sodium × lithium (new subject_ref)
    ("ingredient_quality_map", "sodium", "lithium", l_rule(
        "monitor",
        "High sodium intake increases lithium clearance. Low sodium increases lithium retention → toxicity risk. Like caffeine, the principle is consistency.",
        "If you take lithium, keep sodium intake stable. Avoid sudden low-sodium diets or salt-tablet supplements without prescriber approval.",
        "Keep sodium intake stable",
        "Big swings in sodium intake change your lithium levels. Talk to your prescriber before starting a low-sodium diet or salt supplement.",
        "Sodium intake affects lithium levels bidirectionally — relevant to anyone on lithium therapy.",
        [f"{SRC_PUBMED}/8590902/"],
    )),
    # L4 Turmeric × lithium (Section 6 Position A: monitor)
    ("ingredient_quality_map", "turmeric", "lithium", l_rule(
        "monitor",
        "NSAID-like prostaglandin inhibition is theoretical for curcumin specifically; clinical lithium-elevation evidence absent. Severity reflects conservative safety posture given lithium's narrow therapeutic index, not an established interaction.",
        "If you take lithium, mention high-dose turmeric or curcumin to your prescriber. Monitoring is precautionary — clinical evidence is limited.",
        "Mention to your prescriber",
        "High-dose turmeric or curcumin may theoretically affect lithium levels via NSAID-like mechanisms, though clinical evidence is limited. Precautionary advice only.",
        "Conservative posture for lithium given narrow therapeutic index — clinical evidence for curcumin specifically is absent.",
        [f"{SRC_PUBMED}/12674015/"],
        evidence_level="possible",
    )),
    ("ingredient_quality_map", "curcumin", "lithium", l_rule(
        "monitor",
        "Theoretical NSAID-like mechanism; no documented clinical lithium-elevation cases. Conservative posture given lithium's narrow therapeutic index.",
        "If you take lithium, mention curcumin extracts to your prescriber.",
        "Mention to your prescriber",
        "High-dose curcumin extracts may theoretically affect lithium levels. Clinical evidence is limited; the advice is precautionary.",
        "Conservative monitor posture — clinical evidence absent for curcumin specifically.",
        [f"{SRC_PUBMED}/12674015/"],
        evidence_level="possible",
    )),
    # L5 Magnesium × lithium
    ("ingredient_quality_map", "magnesium", "lithium", l_rule(
        "monitor",
        "May reduce lithium absorption when co-ingested. Separate doses by 2 hours.",
        "If you take lithium, separate magnesium supplements from your lithium dose by at least 2 hours.",
        "Space doses 2 hours apart",
        "High-dose magnesium taken at the same time as lithium may reduce absorption. Take them at least 2 hours apart.",
        "Magnesium can affect lithium absorption — relevant to anyone on lithium therapy.",
        [f"{SRC_PUBMED}/29363269/"],
    )),
    # L6 Iodine/kelp × lithium
    ("ingredient_quality_map", "iodine", "lithium", l_rule(
        "caution",
        "Lithium is goitrogenic; supplemental iodine combined with lithium amplifies hypothyroidism risk. Both substances independently affect thyroid function. Iodine/kelp is common in 'thyroid support' formulas where users may not connect the dots.",
        "If you take lithium, talk to your prescriber before using iodine, kelp, or bladderwrack supplements. Routine thyroid monitoring is important.",
        "Hypothyroidism risk with lithium",
        "Lithium can suppress thyroid function. Iodine and kelp supplements compound this risk — read labels on 'thyroid support' formulas.",
        "Iodine sources stack thyroid risk with lithium — relevant to anyone on lithium therapy.",
        [f"{SRC_PUBMED}/19500763/"],
    )),
    # L7 Dandelion × lithium
    ("ingredient_quality_map", "dandelion", "lithium", l_rule(
        "monitor",
        "Diuretic effect → potential lithium concentration via fluid/sodium depletion. Same mechanism family as the established lithium-thiazide warning. Common in 'detox' and 'liver support' supplements.",
        "If you take lithium, talk to your prescriber before using dandelion extract. Watch for signs of lithium toxicity (tremor, confusion, GI upset).",
        "May raise lithium levels",
        "Dandelion is a mild diuretic. Like prescription diuretics, it can raise lithium levels. Common in 'detox' and 'liver support' supplements.",
        "Dandelion's diuretic effect can raise lithium — relevant to anyone on lithium therapy.",
        [f"{SRC_PUBMED}/19678785/"],
        evidence_level="possible",
    )),
]


def c_rule(severity, mech, action, headline, body, note, sources, evidence_level="established"):
    return rule(severity, evidence_level, mech, action, headline, body, note, sources)


# C1-C3, C8-C10: subject = citrus_bergamot (clinician grouped grapefruit + bergamot)
C_RULES = [
    # C1 Grapefruit/bergamot × statins
    ("ingredient_quality_map", "citrus_bergamot", "statins", c_rule(
        "avoid",
        "Furanocoumarins inhibit intestinal CYP3A4 → ↑ statin AUC 5-15× → rhabdomyolysis risk. Affects simvastatin and lovastatin most; atorvastatin smaller effect; pravastatin and rosuvastatin minimal.",
        "If you take simvastatin or lovastatin, avoid grapefruit and bergamot products. Pravastatin or rosuvastatin are safer alternatives if grapefruit cannot be eliminated.",
        "Muscle-toxicity risk with statins",
        "Grapefruit and bergamot block an enzyme that breaks down certain statins, dramatically raising drug levels and the risk of muscle damage.",
        "Grapefruit/bergamot interact with simvastatin and lovastatin — relevant to anyone on those statins.",
        [f"{SRC_PUBMED}/23184849/"],
    )),
    # C2 Grapefruit/bergamot × calcium channel blockers
    ("ingredient_quality_map", "citrus_bergamot", "calcium_channel_blockers", c_rule(
        "avoid",
        "Same CYP3A4 inhibition mechanism. Increased exposure to felodipine and nifedipine raises hypotension and edema risk.",
        "If you take a calcium channel blocker, avoid grapefruit and bergamot products. Talk to your prescriber.",
        "May lower blood pressure too much",
        "Grapefruit and bergamot can boost levels of calcium channel blockers, leading to dangerously low blood pressure or swelling.",
        "Grapefruit/bergamot affect calcium channel blockers — relevant to anyone on felodipine, nifedipine, or related drugs.",
        [f"{SRC_PUBMED}/23184849/"],
    )),
    # C3 Grapefruit/bergamot × immunosuppressants
    ("ingredient_quality_map", "citrus_bergamot", "immunosuppressants", c_rule(
        "contraindicated",
        "Same CYP3A4 mechanism. Tacrolimus and cyclosporine have narrow therapeutic indices; toxic levels cause nephrotoxicity.",
        "If you take tacrolimus or cyclosporine, do not consume grapefruit or bergamot products. This is a strict contraindication.",
        "Do not combine with transplant drugs",
        "Grapefruit and bergamot can push tacrolimus and cyclosporine to toxic levels, damaging the kidneys. Strict avoidance is required.",
        "Grapefruit/bergamot are contraindicated with transplant immunosuppressants.",
        [f"{SRC_PUBMED}/26929736/"],
    )),
    # C4 St John's Wort × CYP3A4 substrates (broad set)
    ("ingredient_quality_map", "st_johns_wort", "immunosuppressants", c_rule(
        "contraindicated",
        "CYP3A4 induction (opposite mechanism to grapefruit) → reduced exposure to tacrolimus, cyclosporine → therapy failure and transplant rejection.",
        "Do not combine St. John's Wort with transplant immunosuppressants.",
        "Do not combine with transplant drugs",
        "St. John's Wort speeds up the breakdown of tacrolimus and cyclosporine. This can cause transplant rejection.",
        "St. John's Wort is a strong CYP3A4 inducer — opposite mechanism to grapefruit (drug failure, not toxicity).",
        [f"{SRC_PUBMED}/12595722/"],
    )),
    ("ingredient_quality_map", "st_johns_wort", "oral_contraceptives", c_rule(
        "contraindicated",
        "CYP3A4 induction reduces ethinyl estradiol exposure → contraception failure and breakthrough bleeding documented in clinical literature.",
        "Do not rely on oral contraceptives while using St. John's Wort. Use additional non-hormonal contraception or discontinue St. John's Wort.",
        "May cause contraception failure",
        "St. John's Wort lowers the level of birth-control pills in your blood and can lead to unintended pregnancy.",
        "St. John's Wort reduces oral contraceptive efficacy.",
        [f"{SRC_PUBMED}/12595722/"],
    )),
    # C5 Goldenseal × CYP3A4 substrates
    ("ingredient_quality_map", "goldenseal", "cyp3a4_substrates", c_rule(
        "avoid",
        "Strong CYP3A4 inhibitor in vitro and in vivo (berberine + hydrastine). Also affects CYP2D6.",
        "If you take prescription drugs metabolized by CYP3A4 or CYP2D6, avoid goldenseal unless your prescriber clears it.",
        "Affects how many drugs are processed",
        "Goldenseal blocks two enzymes that break down many prescription drugs. This can raise drug levels and side-effect risk.",
        "Goldenseal is a strong CYP3A4 and CYP2D6 inhibitor — relevant to anyone on prescription drugs metabolized by these enzymes.",
        [f"{SRC_PUBMED}/18180278/"],
    )),
    # C6 Schisandra × CYP3A4 substrates
    ("botanical_ingredients", "schisandra_berry", "cyp3a4_substrates", c_rule(
        "caution",
        "Schizandrol-rich extracts inhibit CYP3A4. Some clinical interactions documented with tacrolimus and sirolimus. Common in adaptogen blends used by transplant-recovery population.",
        "If you take a CYP3A4-substrate prescription drug, talk to your prescriber before using schisandra. Especially relevant for transplant patients on tacrolimus or sirolimus.",
        "May affect prescription drug levels",
        "Schisandra can change levels of certain prescription drugs by inhibiting a key liver enzyme. Especially important for transplant patients.",
        "Schisandra inhibits CYP3A4 — relevant to anyone on prescription drugs metabolized by that enzyme.",
        [f"{SRC_PUBMED}/17877974/"],
    )),
    # C7 Berberine × CYP3A4 substrates
    ("ingredient_quality_map", "berberine_supplement", "cyp3a4_substrates", c_rule(
        "caution",
        "In-vitro CYP3A4 inhibition; clinical effect modest at typical doses (≥500 mg/day). Increasingly common in metabolic-health supplements.",
        "If you take a CYP3A4-substrate prescription drug, talk to your prescriber before adding a berberine supplement.",
        "May affect prescription drug levels",
        "Berberine can mildly slow the breakdown of certain prescription drugs. Mention berberine use to your prescriber if you take other medications.",
        "Berberine inhibits CYP3A4 at clinical doses — relevant to anyone on prescription drugs metabolized by that enzyme.",
        [f"{SRC_PUBMED}/22931302/"],
    )),
    # C8 Grapefruit/bergamot × amiodarone
    ("ingredient_quality_map", "citrus_bergamot", "antiarrhythmics", c_rule(
        "avoid",
        "CYP3A4 inhibition combined with amiodarone's intrinsic QT-prolongation amplifies torsades de pointes risk. Documented cases.",
        "If you take amiodarone, avoid grapefruit and bergamot products.",
        "Heart-rhythm risk with amiodarone",
        "Grapefruit and bergamot raise amiodarone levels and increase the risk of dangerous heart rhythms.",
        "Grapefruit/bergamot stack QT risk with amiodarone.",
        [f"{SRC_PUBMED}/10691759/"],
    )),
    # C9 Grapefruit/bergamot × DOACs
    ("ingredient_quality_map", "citrus_bergamot", "anticoagulants", c_rule(
        "caution",
        "CYP3A4 + P-gp inhibition increases DOAC (apixaban, rivaroxaban) exposure → bleeding risk.",
        "If you take apixaban or rivaroxaban, talk to your prescriber before using grapefruit or bergamot products.",
        "May increase bleeding risk",
        "Grapefruit and bergamot can raise levels of newer blood thinners like apixaban and rivaroxaban, increasing bleeding risk.",
        "Grapefruit/bergamot affect DOACs through CYP3A4 and P-gp.",
        [f"{SRC_PUBMED}/23590328/"],
    )),
    # C10 Grapefruit/bergamot × oral contraceptives
    ("ingredient_quality_map", "citrus_bergamot", "oral_contraceptives", c_rule(
        "monitor",
        "CYP3A4 inhibition may modestly increase ethinyl estradiol exposure. Effect is documented but small.",
        "If you take oral contraceptives, mention regular grapefruit or bergamot intake to your prescriber.",
        "Mildly raises hormone levels",
        "Grapefruit and bergamot can mildly increase estrogen levels from birth-control pills. Effect is small but documented.",
        "Grapefruit/bergamot mildly raise oral contraceptive levels.",
        [f"{SRC_PUBMED}/8961038/"],
    )),
]

ALL_RULES = W_RULES + M_RULES + L_RULES + C_RULES

# Pregnancy/lactation pre-seeds (clinician notes from Section 2)
PREG_LACT_SEEDS = {
    # (db, canonical_id) -> (preg_cat, lact_cat, evidence_level, mechanism, notes, headline, body, note, sources)
    ("ingredient_quality_map", "ginkgo"): {
        "pregnancy_category": "caution",
        "evidence_level": "limited",
        "mechanism": "Antiplatelet activity raises bleeding-risk concerns in pregnancy and labor.",
        "notes": "Use caution in pregnancy due to bleeding-risk profile, especially around delivery.",
    },
    ("ingredient_quality_map", "dong_quai"): {
        "pregnancy_category": "avoid",
        "evidence_level": "moderate",
        "mechanism": "Uterine stimulant; traditional abortifacient.",
        "notes": "Avoid in pregnancy — uterine stimulant activity.",
    },
    ("ingredient_quality_map", "ginseng"): {
        "pregnancy_category": "caution",
        "evidence_level": "limited",
        "mechanism": "Insufficient safety data in pregnancy; emmenagogue-like reports.",
        "notes": "Use caution in pregnancy — limited safety data.",
    },
    ("ingredient_quality_map", "yohimbe"): {
        "pregnancy_category": "avoid",
        "evidence_level": "limited",
        "mechanism": "Sympathomimetic; potential adverse cardiovascular effects in pregnancy.",
        "notes": "Avoid in pregnancy — sympathomimetic activity.",
    },
    ("ingredient_quality_map", "goldenseal"): {
        "pregnancy_category": "avoid",
        "evidence_level": "moderate",
        "mechanism": "Berberine displaces bilirubin from albumin → neonatal kernicterus concern.",
        "notes": "Avoid in pregnancy and lactation — berberine kernicterus concern.",
        "lactation_category": "avoid",
    },
    ("ingredient_quality_map", "berberine_supplement"): {
        "pregnancy_category": "caution",
        "evidence_level": "limited",
        "mechanism": "Same berberine mechanism as goldenseal at lower doses.",
        "notes": "Use caution in pregnancy and lactation — berberine kernicterus concern at high doses.",
    },
}

DEFAULT_LACT_NOTE = "Limited data — discuss with your healthcare provider before use during pregnancy or breastfeeding."


def find_rule(rules, db, canonical_id):
    for r in rules:
        sref = r.get("subject_ref", {})
        if sref.get("db") == db and sref.get("canonical_id") == canonical_id:
            return r
    return None


def make_subject_id(db, canonical_id):
    db_short = {
        "ingredient_quality_map": "IQM",
        "banned_recalled_ingredients": "BANNED",
        "botanical_ingredients": "BOTAN",
        "harmful_additives": "ADDITIVE",
        "other_ingredients": "OTHER",
    }.get(db, "GEN")
    return f"RULE_{db_short}_{canonical_id.upper()}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(DATA_PATH) as f:
        data = json.load(f)
    rules = data["interaction_rules"]

    appended = 0
    new_entries = 0
    preg_seeded = 0

    for db, cid, drug_class_id, payload in ALL_RULES:
        rule_obj = find_rule(rules, db, cid)
        if rule_obj is None:
            rule_obj = {
                "id": make_subject_id(db, cid),
                "subject_ref": {"db": db, "canonical_id": cid},
                "condition_rules": [],
                "drug_class_rules": [],
                "dose_thresholds": [],
                "pregnancy_lactation": {
                    "pregnancy_category": "no_data",
                    "lactation_category": "no_data",
                    "evidence_level": "no_data",
                    "notes": DEFAULT_LACT_NOTE,
                    "sources": [],
                },
                "last_reviewed": "2026-04-30",
                "review_owner": "pharmaguide_clinical_team",
            }
            rules.append(rule_obj)
            new_entries += 1

        # Upsert: clinician-locked payload always wins on calibration conflicts.
        # If rule exists with matching drug_class_id, replace it in place
        # (preserves array order). Otherwise append.
        dcrs = rule_obj.setdefault("drug_class_rules", [])
        new_dcr = {"drug_class_id": drug_class_id, **payload}
        replaced = False
        for i, dcr in enumerate(dcrs):
            if dcr.get("drug_class_id") == drug_class_id:
                # Skip if already identical (true idempotency)
                if dcr == new_dcr:
                    replaced = True
                    break
                dcrs[i] = new_dcr
                appended += 1
                replaced = True
                break
        if not replaced:
            dcrs.append(new_dcr)
            appended += 1

    # Apply pregnancy/lactation pre-seeds
    for (db, cid), seed in PREG_LACT_SEEDS.items():
        rule_obj = find_rule(rules, db, cid)
        if rule_obj is None:
            continue
        pl = rule_obj.get("pregnancy_lactation") or {}
        rule_obj["pregnancy_lactation"] = pl
        # Only apply seed if pregnancy_category is empty/unset/no_data
        current = pl.get("pregnancy_category")
        if current in (None, "", "no_data"):
            pl["pregnancy_category"] = seed["pregnancy_category"]
            pl["evidence_level"] = seed.get("evidence_level", "limited")
            pl.setdefault("mechanism", seed.get("mechanism", ""))
            pl["notes"] = seed.get("notes", pl.get("notes", DEFAULT_LACT_NOTE))
            if "lactation_category" in seed:
                pl["lactation_category"] = seed["lactation_category"]
            elif pl.get("lactation_category") in (None, "", "no_data"):
                pl["lactation_category"] = "caution"
            preg_seeded += 1

    # Bump metadata
    md = data.setdefault("_metadata", {})
    md["last_updated"] = "2026-04-30"
    md["total_rules"] = len(rules)
    md["total_entries"] = len(rules)

    print(f"Drug-class rules appended:        {appended}")
    print(f"New rule entries created:         {new_entries}")
    print(f"Pregnancy/lactation seeds applied: {preg_seeded}")
    print(f"Total rules now:                  {len(rules)}")

    if args.dry_run:
        print("\n[dry-run] would write changes")
        return 0

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
