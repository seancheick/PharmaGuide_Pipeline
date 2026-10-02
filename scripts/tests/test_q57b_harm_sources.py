"""LEDGER Q57b (2026-10-02): every harm claim in these banned_recalled entries is either
backed by a source Claude read or weakened/removed to what the evidence supports.

Q57 removed their only (ghost) citations. Sources were found by research agents and each
abstract, label or report was read before use; receipts and the per-entry before/after
table: scripts/audits/pending_items_20260926/q57b_harm_sources_20261002.md. Safety copy
(safety_warning, one-liner) is Sean-owned and unchanged; flags are in that file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARM_CLAIMS = {"mechanism_of_harm", "clinical_outcomes"}

# Entries whose harm claims Q57b re-sourced.
ENTRIES = [
    "ADD_HORDENINE",
    "ADD_RED3",
    "ADULTERANT_RIMONABANT",
    "BANNED_14_BUTANEDIOL",
    "BANNED_7_HYDROXYMITRAGYNINE",
    "BANNED_ADD_PHTHALATES",
    "BANNED_ADD_SYNTHETIC_FOOD_ACIDS",
    "BANNED_BMPEA",
    "BANNED_COMFREY_INTERNAL",
    "BANNED_DMAA",
    "BANNED_DMHA",
    "BANNED_EPHEDRA",
    "BANNED_FASORACETAM",
    "BANNED_FDC_RED_2_AMARANTH",
    "BANNED_HIGENAMINE",
    "BANNED_IBOTENIC_ACID",
    "BANNED_IGF1",
    "BANNED_MUSCIMOL",
    "BANNED_PHENIBUT",
    "BANNED_S23",
    "BANNED_SR9009",
    "BANNED_TIANEPTINE",
    "BANNED_YELLOW_OLEANDER_RECENT",
    "HIGH_RISK_CHAPARRAL",
    "HIGH_RISK_PENNYROYAL",
    "HM_ARSENIC",
    "HM_CADMIUM",
    "HM_LEAD",
    "NOOTROPIC_9MEBC",
    "NOOTROPIC_ADRAFINIL",
    "NOOTROPIC_BROMANTANE",
    "NOOTROPIC_FLMODAFINIL",
    "NOOTROPIC_OMBERACETAM",
    "NOOTROPIC_PHENYLPIRACETAM",
    "PEPTIDE_MELANOTAN_II",
    "PHARMA_LORCASERIN",
    "RC_CARDARINE_ANALOGS",
    "RECALLED_HYDROXYCUT",
    "RECALLED_JACK3D",
    "RECALLED_OXYELITE_PRO",
    "RISK_BITTER_ORANGE",
    "RISK_GERMANIUM",
    "RISK_GREEN_TEA_EXTRACT_HIGH",
    "RISK_KAVA",
    "RISK_YOHIMBE",
    "SARM_ANDARINE",
    "SARM_CARDARINE",
    "SARM_LIGANDROL",
    "SARM_OSTARINE",
    "SARM_RAD140",
    "SCHED_AMANITA_MUSCARIA",
    "SCHED_PSILOCIN",
    "SCHED_PSILOCYBIN",
    "STIM_METHYLHEXANAMINE_ANALOGS"
]

# Stored claims the evidence did not support, removed or rewritten (exact former wording).
REMOVED = {
    "BANNED_DMAA": [
        "It has been linked to heart attacks, strokes, deaths (including military personnel), and psychiatric events."
    ],
    "BANNED_DMHA": [
        "Like DMAA, it raises blood pressure, heart rate, and has been linked to cardiovascular events."
    ],
    "BANNED_BMPEA": [
        "BMPEA has stimulant activity; it raises blood pressure and heart rate and has structural similarity to amphetamines.",
        "(Pawar et al. 2013)"
    ],
    "BANNED_EPHEDRA": [
        "Citing more than 18,000 adverse event reports and documented heart attacks, strokes and deaths, FDA banned"
    ],
    "BANNED_HIGENAMINE": [
        "At doses used in pre-workout supplements it elevates heart rate and blood pressure; cardiovascular adverse events have been reported."
    ],
    "STIM_METHYLHEXANAMINE_ANALOGS": [
        "Like DMAA, these compounds raise blood pressure and heart rate and have been associated with cardiovascular events."
    ],
    "ADD_HORDENINE": [
        "concentrated in supplements at pharmacological doses.",
        "Frequently combined with other stimulants in weight-loss and pre-workout products, amplifying cardiovascular risk."
    ],
    "RISK_BITTER_ORANGE": [
        "a sympathomimetic amine that binds adrenergic receptors similarly to ephedrine.",
        "FDA has received adverse event reports including hypertension, tachycardia, stroke, and myocardial infarction associated with bitter orange supplements. At doses used in supplements, synephrine may raise blood pressure and heart rate, particularly in combination with caffeine. Its cardiovascular risk profile closely mirrors the pattern that led to ephedra's federal ban."
    ],
    "RISK_YOHIMBE": [
        "FDA has received adverse event reports of anxiety, hypertension, tachycardia, and cardiac arrhythmia from yohimbe supplements. At doses found in supplements, yohimbine can trigger dangerous blood pressure spikes in individuals with hypertension or cardiovascular disease. Drug interactions include dangerous potentiation with antidepressants, antihypertensives, and stimulants."
    ],
    "RECALLED_JACK3D": [
        "was recalled after the product — which contained DMAA (1,3-dimethylamylamine) as an active ingredient — was linked to two deaths of US military personnel during exercise, as well as multiple hospitalizations from hemorrhagic stroke and heart attack."
    ],
    "RECALLED_OXYELITE_PRO": [
        "over 97 cases reported, 44 hospitalizations, 3 liver transplants, and 1 death."
    ],
    "RECALLED_HYDROXYCUT": [
        "was linked to 23 reports of serious liver injury including one death before FDA issued a consumer warning and initiated a voluntary recall in 2009. The original formulation contained a combination including hydroxycitric acid (Garcinia cambogia) and other ingredients. The exact hepatotoxic mechanism was not isolated to a single ingredient."
    ],
    "SARM_ANDARINE": [
        "At doses used in supplements, it has caused reversible visual disturbances — yellow-tinted vision and difficulty adapting to light and dark — as well as androgenic suppression of testosterone."
    ],
    "SARM_CARDARINE": [
        "Clinical trials were halted in 2007 after it caused rapid multi-tissue carcinogenesis in animal studies at doses resembling those used in supplements."
    ],
    "RC_CARDARINE_ANALOGS": [
        "whose parent compound caused rapid multi-tissue carcinogenesis in animal trials.",
        "Products containing Cardarine derivatives should be treated with the same concern as the parent compound."
    ],
    "SARM_LIGANDROL": [
        "Case reports have documented drug-induced liver injury and testosterone suppression in otherwise healthy users taking doses typical of supplement use."
    ],
    "SARM_OSTARINE": [
        "Documented risks include testosterone and LH suppression, liver enzyme elevation, and cardiovascular effects."
    ],
    "BANNED_S23": [
        "it suppresses LH, FSH, and sperm production at moderate doses.",
        "and carries the same risks as other SARMs (endocrine suppression, hepatotoxicity)."
    ],
    "BANNED_SR9009": [
        "Important note: animal studies suggest it has near-zero oral bioavailability, meaning supplement products claiming metabolic or endurance benefits are likely fraudulent in addition to selling an unapproved compound."
    ],
    "BANNED_IGF1": [
        "At supraphysiological levels, IGF-1 promotes cell proliferation and may accelerate growth of existing tumors. No safe supplement dose has been established."
    ],
    "PEPTIDE_MELANOTAN_II": [
        "Serious safety concerns include: melanoma risk (promoting pre-existing melanocytic lesions), nausea and vomiting, spontaneous penile erections, and the near-universal practice of injection by users — creating sterility and contamination risks that do not apply to oral supplements."
    ],
    "PHARMA_LORCASERIN": [
        "users receive a withdrawn drug with confirmed cancer risk signals,"
    ],
    "NOOTROPIC_9MEBC": [
        "studied in preclinical neurochemistry for dopaminergic effects. No human safety data exists.",
        "At the same time, β-carbolines as a class include monoamine oxidase inhibitors, raising the risk of dangerous drug-supplement interactions with serotonergic medications."
    ],
    "NOOTROPIC_ADRAFINIL": [
        "Adrenal and cardiovascular effects mirror modafinil."
    ],
    "NOOTROPIC_BROMANTANE": [
        "At high doses it has shown dopaminergic effects and the potential for psychostimulant dependence."
    ],
    "NOOTROPIC_FLMODAFINIL": [
        "a synthetic difluoro analog of modafinil with greater potency.",
        "No human clinical safety data exists."
    ],
    "NOOTROPIC_OMBERACETAM": [
        "Psychoactive mechanism: potentiates AMPA/NMDA receptors; safety data in humans at supplement doses is absent."
    ],
    "NOOTROPIC_PHENYLPIRACETAM": [
        "At pharmacological doses it produces stimulant and nootropic effects similar to controlled stimulants."
    ],
    "BANNED_FASORACETAM": [
        "was investigated as a pharmaceutical for ADHD in adolescents but failed clinical trials and was never approved."
    ],
    "BANNED_PHENIBUT": [
        "is a CNS depressant with GABAergic and GHB receptor activity",
        "It causes physical dependence and severe withdrawal (anxiety, insomnia, psychosis) even after short-term use at doses found in supplements. Overdose with sedatives or alcohol can be fatal."
    ],
    "BANNED_TIANEPTINE": [
        "acts as a full agonist at mu-opioid receptors at the doses found in US supplement products.",
        "At doses used in supplements (well above the therapeutic range of 12.5mg/day used in Europe), it causes"
    ],
    "BANNED_14_BUTANEDIOL": [
        "— with a narrow therapeutic window made worse because conversion speed varies by individual"
    ],
    "BANNED_7_HYDROXYMITRAGYNINE": [
        "with full mu-opioid receptor agonist potency estimated at 13 times greater than morphine by weight. It is responsible for most of kratom's opioid effects.",
        "Products containing isolated or concentrated 7-HMG carry full opioid overdose risk."
    ],
    "SCHED_AMANITA_MUSCARIA": [
        "In 2024, Diamond Shruumz brand gummies (containing Amanita muscaria extract) triggered a multistate outbreak with 70+ hospitalizations, seizures, loss of consciousness, and deaths."
    ],
    "BANNED_MUSCIMOL": [
        "It is a potent GABA-A receptor agonist causing sedation, euphoria, altered perception, and at higher doses: seizures, loss of consciousness, and respiratory depression. The margin between psychoactive and toxic doses is narrow and highly variable.",
        "Muscimol itself (as isolated compound or concentrated extract) has been marketed in gummies and capsules, leading to the 2024 Diamond Shruumz mass poisoning event."
    ],
    "BANNED_IBOTENIC_ACID": [
        "Decarboxylates to muscimol during drying/processing. The combination of ibotenic acid (excitotoxin) and muscimol (GABAergic sedative) creates an unpredictable and dangerous pharmacological profile. Ibotenic acid is used in neuroscience research to create brain lesions — its neurotoxicity is well-established."
    ],
    "BANNED_COMFREY_INTERNAL": [
        "causing hepatic veno-occlusive disease (Budd-Chiari syndrome), progressive liver failure, and cancer.",
        "There is no safe intake level for hepatotoxic PAs."
    ],
    "HIGH_RISK_CHAPARRAL": [
        "contains nordihydroguaiaretic acid (NDGA), which has been associated with at least 18 cases of severe liver injury in the literature, including hepatitis, cirrhosis, and fulminant liver failure requiring transplantation.",
        "The mechanism involves reactive NDGA metabolites that form adducts with liver proteins."
    ],
    "HIGH_RISK_PENNYROYAL": [
        "metabolized by CYP2E1 to the reactive hepatotoxin menthofuran.",
        "Even a few milliliters of the essential oil can cause fulminant liver failure and death. The oil was historically used as an abortifacient — making it particularly dangerous during pregnancy.",
        "Topical use at very low concentrations is less concerning."
    ],
    "RISK_KAVA": [
        "has been associated with over 100 documented cases of severe liver injury globally, including hepatitis, cirrhosis, and liver failure requiring transplantation.",
        "The mechanism may involve kavalactone metabolites (pipermethystine) or CYP2D6/CYP3A4 inhibition causing drug interactions.",
        "At-risk populations include people with liver disease or those taking hepatotoxic medications."
    ],
    "RISK_GREEN_TEA_EXTRACT_HIGH": [
        "is associated with drug-induced liver injury (DILI) when taken at doses exceeding approximately 800mg EGCG per day.",
        "The European Food Safety Authority (EFSA) issued a warning in 2018 that GTE preparations providing ≥800mg EGCG/day taken on an empty stomach 'raise concerns for liver safety.'",
        "At doses found in typical green tea beverages and low-dose extracts, the risk is not significant — the concern is concentrated extract supplements specifically."
    ],
    "BANNED_YELLOW_OLEANDER_RECENT": [
        "contains cardiac glycosides (thevetin A and B, cerberin) that cause life-threatening cardiotoxicity — bradycardia, heart block, ventricular arrhythmia — at very low doses.",
        "in multiple documented cases, where the substitution was not disclosed on labels."
    ],
    "RISK_GERMANIUM": [
        "Inorganic germanium compounds (germanium dioxide, organic germanium carboxylate) were marketed",
        "Japan reported over 30 deaths from kidney failure associated with inorganic germanium use. The compound accumulates in the kidneys and peripheral nerves, causing progressive and irreversible nephropathy and peripheral neuropathy.",
        "Products containing inorganic germanium compounds should be considered immediately unsafe."
    ],
    "HM_ARSENIC": [
        "It also causes peripheral neuropathy, cardiovascular disease, and diabetes. Organic arsenic (found in seafood) is less toxic.",
        "In supplements, arsenic contamination is most common in rice protein, kelp, spirulina, certain Ayurvedic preparations, and marine-sourced ingredients."
    ],
    "HM_CADMIUM": [
        "causing progressive renal tubular damage and ultimately kidney failure (itai-itai disease at high environmental exposures). It also causes bone demineralization by interfering with vitamin D metabolism. IARC Group 1 carcinogen (lung cancer, endometrial cancer evidence).",
        "Common in plant-based supplements grown in cadmium-rich soils (cocoa, leafy greens, grains)."
    ],
    "HM_LEAD": [
        "is a cumulative neurotoxin with no established safe blood level, particularly for cognitive development in children. It distributes to bone, brain, kidney, and liver. Chronic low-level exposure impairs IQ, attention, and impulse control in children; in adults it raises cardiovascular risk.",
        "Lead contamination in supplements is common in mineral products, certain botanicals, and products manufactured with inadequate heavy metal testing."
    ],
    "BANNED_ADD_PHTHALATES": [
        "Packaging contaminants that leach from plastic bottles and containers into supplements. Powerful endocrine disruptors linked to reproductive harm, developmental issues, and cancer (DEHP classified IARC Group 2B, possibly carcinogenic, Monograph Vol 101, 2013). 2024-2025 research continues to find widespread contamination in supplements packaged in plastic. Choose glass packaging when possible. Not intentionally added but common contaminant."
    ],
    "BANNED_ADD_SYNTHETIC_FOOD_ACIDS": [
        "Synthetic acids may have different effects than natural food acids. Can contribute to dental erosion and digestive issues."
    ],
    "BANNED_FDC_RED_2_AMARANTH": [
        "— specifically bladder and mammary tumors in animal studies, though the data were considered inconclusive by some scientists"
    ]
}


def _entries() -> dict:
    data = json.loads((ROOT / "data" / "banned_recalled_ingredients.json").read_text())
    return {e["id"]: e for e in data["ingredients"]}


@pytest.mark.parametrize("entry_id", ENTRIES)
def test_harm_claims_cite_a_read_source(entry_id):
    refs = _entries()[entry_id].get("references_structured") or []
    cited = [r for r in refs if HARM_CLAIMS & set(r.get("supports_claims") or []) and r.get("url")]
    assert cited, f"{entry_id} has no source for its harm claims"


@pytest.mark.parametrize("entry_id", sorted(REMOVED))
def test_unsupported_claims_stay_removed(entry_id):
    reason = _entries()[entry_id]["reason"]
    assert [frag for frag in REMOVED[entry_id] if frag in reason] == []
