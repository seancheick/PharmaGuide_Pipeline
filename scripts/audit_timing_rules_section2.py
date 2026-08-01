#!/usr/bin/env python3
"""Section 2: audit each timing rule and set its publication status.

Every rule id is listed explicitly below with a disposition and a reason. The
script asserts that the set of ids it knows about exactly equals the set in the
artifact, so a rule can never be skipped silently — the failure mode that makes
batch edits on clinical data unsafe.

A rule is promoted to `verified` ONLY when all of these hold:
  * the cited source was content-verified against PubMed and actually supports
    TIMING, not merely a mechanism;
  * its canonical tags resolve to products in the shipped catalog;
  * it carries positive and negative catalog canaries;
  * its category / actionability / evidence / authority are individually
    assigned.

Anything else stays `needs_revision` (suppressed at runtime) or moves to the
rejection ledger. There is deliberately no fourth state.

All PMIDs referenced here were content-verified against PubMed on 2026-08-01.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
RULES = DATA / "timing_rules.json"
LEDGER = DATA / "timing_rules_rejected.json"

LEVOTHYROXINE_LABEL_SOURCE = {
    "source_type": "fda",
    "label": (
        "DailyMed - SYNTHROID (levothyroxine sodium) tablets, section 17 "
        "Patient Counseling Information: do not take within 4 hours of iron "
        "and calcium supplements or antacids"
    ),
    "url": (
        "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?"
        "setid=1e11ad30-1041-4520-10b0-8f9d30d30fcc"
    ),
}

# ---------------------------------------------------------------------------
# VERIFIED — source content-verified, identity reachable, canaries authored.
# ---------------------------------------------------------------------------
VERIFIED: dict[str, dict] = {
    # VERIFIED 2026-08-01 against PubMed 29046302, content-verified via API:
    # Ahmad Fuzi SF et al. "A 1-h time interval between a meal containing iron
    # and consumption of tea attenuates the inhibitory effects on iron
    # absorption: a controlled trial in a cohort of healthy UK women using a
    # stable iron isotope." Am J Clin Nutr 2017;106(6):1413-21.
    # DOI 10.3945/ajcn.117.161364, NCT02365103.
    #
    # INTERVAL CORRECTED 2 HOURS -> 1 HOUR. The previous 2-hour figure had no
    # source; this is the only human trial that manipulates the interval at
    # all. Absorption: 5.7% with water, 3.6% with tea simultaneously, 5.7% with
    # tea 1 h postmeal. Inhibition fell from 37.2% to 18.1% - attenuated by
    # about half, NOT abolished, which the copy says plainly.
    #
    # DIRECTION: the trial gave tea one hour AFTER the meal. It did not test
    # tea before. A symmetric separate_from cannot express that, so the advice
    # states what was actually tested. Note the contrast with coffee, where
    # Morck 1983 (PMID 6402915) found the opposite asymmetry - coffee 1 h
    # BEFORE a meal caused no decrease, while coffee 1 h after inhibited as
    # much as simultaneous ingestion. Direction is not transferable between
    # these beverages.
    #
    # IDENTITY: scoped to tea-derived products only - extract, EGCG, and leaf
    # forms. All six tags carry the tea polyphenols the trial implicates, which
    # is precisely what the rejected coffee rule could not claim: `caffeine` is
    # not coffee-derived, so a caffeine tablet contains none of the responsible
    # compounds. Excluding the extract forms would be incoherent, since a
    # standardised EGCG capsule delivers more of the causative compound than a
    # cup of tea.
    #
    # Evidence is `probable`, not `established`: n=12, iron-replete non-anemic
    # women, and the trial studied brewed tea while the catalog carries tea
    # supplements. actionability is `optional` because the clinical relevance
    # sits with iron-deficient users, who were not the population studied.
    "timing_egcg_iron_separate": {
        "ingredient1_tags": [
            "green_tea_extract",
            "egcg",
            "green_tea",
            "green_tea_leaf",
            "black_tea_leaf",
            "oolong_tea_leaf",
        ],
        "ingredient2_tags": ["iron"],
        "category": "important_separation",
        "actionability": "optional",
        "evidence_level": "probable",
        "source_authority": "clinical_study",
        "applies_to": "any",
        "relation": {"type": "separate_from", "minimum_hours": 1},
        "advice": (
            "Green tea can reduce how much iron your body absorbs. Leaving "
            "about an hour between them may help - in a trial, tea taken an "
            "hour after an iron-rich meal roughly halved the effect rather "
            "than removing it."
        ),
        "mechanism": (
            "Tea polyphenols bind nonheme iron in the gut lumen and form "
            "complexes that are not absorbed. Ahmad Fuzi 2017 measured "
            "fractional iron absorption of 5.7% with water, 3.6% with tea "
            "taken simultaneously, and 5.7% with tea taken one hour after the "
            "meal; the inhibitory effect fell from 37.2% to 18.1%. The trial "
            "used brewed tea in 12 iron-replete women, so applying it to tea "
            "supplements is an extrapolation on form, and the effect is "
            "attenuated rather than eliminated by the interval."
        ),
        "add_source": {
            "source_type": "pubmed",
            "label": (
                "Ahmad Fuzi SF et al - A 1-h time interval between a meal "
                "containing iron and consumption of tea attenuates the "
                "inhibitory effects on iron absorption. Am J Clin Nutr 2017"
            ),
            "url": "https://pubmed.ncbi.nlm.nih.gov/29046302/",
        },
        "canaries": {
            "positive": ["229960", "17105"],
            "negative": ["180249"],
        },
    },
    # VERIFIED 2026-08-01 against PubMed 20200983, content-verified via API:
    # Mulligan GB, Licata A. "Taking vitamin D with the largest meal improves
    # absorption and results in higher serum levels of 25-hydroxyvitamin D."
    # J Bone Miner Res. 2010 Apr;25(4):928-30. DOI 10.1002/jbmr.67.
    # Mean 25(OH)D rose 30.5 -> 47.2 ng/mL, an average increase of 56.7%.
    #
    # CITATION CORRECTION: this paper is widely cited as "Mulligan & Felton",
    # including in the review notes that prompted this lookup. The second
    # author is LICATA. The wrong name was one lookup away from entering the
    # artifact.
    #
    # Evidence is `probable`, not `established`: n=17, prospective cohort with
    # NO CONTROL ARM, single centre, and the population was selected for
    # already failing to respond to treatment - the setup most prone to
    # regression to the mean. The instruction itself was directly tested, which
    # is why it clears `possible`.
    #
    # The previously cited LPI vitamin D page is REPLACED, not supplemented:
    # verification found the word "meal" appears zero times on it.
    "timing_vitamin_d_with_food": {
        "ingredient1_tags": ["vitamin_d"],
        "category": "how_to_take",
        "actionability": "optional",
        "evidence_level": "probable",
        "source_authority": "clinical_study",
        "applies_to": "standalone",
        "advice": (
            "Vitamin D is fat-soluble, and taking it with your largest meal "
            "may improve absorption - a small study saw blood levels rise by "
            "about half."
        ),
        "mechanism": (
            "Vitamin D is fat-soluble, so co-ingested dietary fat stimulates "
            "bile release and mixed-micelle formation that carry it across the "
            "intestinal wall. Mulligan and Licata 2010 measured a 56.7% mean "
            "rise in serum 25(OH)D after patients moved their usual dose to "
            "the largest meal of the day. The study was an uncontrolled cohort "
            "of 17 treatment non-responders, so the size of the effect should "
            "be read cautiously."
        ),
        "replace_sources": [
            {
                "source_type": "pubmed",
                "label": (
                    "Mulligan GB, Licata A - Taking vitamin D with the largest "
                    "meal improves absorption and results in higher serum "
                    "levels of 25-hydroxyvitamin D. J Bone Miner Res. 2010"
                ),
                "url": "https://pubmed.ncbi.nlm.nih.gov/20200983/",
            }
        ],
        "canaries": {"positive": ["12016"], "negative": ["278010"]},
    },
    # VERIFIED 2026-08-01 against LPI coenzyme-Q10, retrieved as raw HTML (the
    # page 403s automated fetchers). Verbatim: "Coenzyme Q10 is fat-soluble and
    # is best absorbed with fat in a meal." Copy now mirrors that sentence —
    # the previous wording claimed absorption "increases significantly", a
    # magnitude the page never gives.
    "timing_coq10_with_food": {
        "ingredient1_tags": ["coq10"],
        "category": "how_to_take",
        "actionability": "optional",
        "evidence_level": "probable",
        "source_authority": "reference",
        "applies_to": "standalone",
        "advice": "CoQ10 is fat-soluble and is best absorbed with fat in a meal.",
        "canaries": {"positive": ["17550"], "negative": ["278010"]},
    },
    # VERIFIED 2026-08-01 against LPI lipoic-acid, raw HTML. The source is MORE
    # specific than the rule was. Verbatim: "Oral lipoic acid supplements are
    # better absorbed on an empty stomach than with food: taking lipoic acid
    # with food (versus without food) decreased peak plasma lipoic acid
    # concentrations by about 30% and total plasma lipoic acid concentrations
    # by about 20%" and "it is generally recommended that lipoic acid be taken
    # 30 min prior to a meal".
    #
    # Modelled as before_event/meal rather than the vaguer empty_stomach, so
    # the instruction anchors to something the user defines. Evidence is
    # `probable`, not `established`: the page rests this on one small 1996 PK
    # study of the racemic form and states no R-lipoic acid food-effect data
    # has been published.
    "timing_ala_empty_stomach": {
        "ingredient1_tags": ["alpha_lipoic_acid"],
        "category": "how_to_take",
        "actionability": "optional",
        "evidence_level": "probable",
        "source_authority": "reference",
        "applies_to": "standalone",
        "relation": {
            "type": "before_event",
            "event": "meal",
            "minimum_minutes": 30,
        },
        "advice": (
            "Alpha-lipoic acid is better absorbed on an empty stomach - it is "
            "generally taken about 30 minutes before a meal. Taking it with "
            "food lowers peak blood levels by roughly 30 percent."
        ),
        "canaries": {"positive": ["17323"], "negative": ["278010"]},
    },
    # VERIFIED 2026-08-01 against
    # https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/ .
    # This is the one rule of the six ODS-cited ones whose strong verb survives
    # contact with its source, verbatim: "Because the digestive tract requires
    # fat to absorb vitamin E, people with fat-malabsorption disorders are more
    # likely to become deficient than people without such disorders."
    #
    # The page states physiology, not an instruction, so the timing advice is
    # an extrapolation: evidence_level drops to `possible` and actionability to
    # `optional`. Copy is rewritten to state the supported clause rather than
    # imply the page issued a directive.
    "timing_vitamin_e_with_food": {
        "ingredient1_tags": ["vitamin_e"],
        "category": "how_to_take",
        "actionability": "optional",
        "evidence_level": "possible",
        "source_authority": "reference",
        "applies_to": "standalone",
        "advice": (
            "Vitamin E is fat-soluble and the digestive tract needs fat to "
            "absorb it, so pairing it with a meal containing some fat is "
            "sensible."
        ),
        "canaries": {"positive": ["17092"], "negative": ["278010"]},
    },
    # VERIFIED 2026-08-01 against the SYNTHROID label (AbbVie, setid
    # 1e11ad30-1041-4520-10b0-8f9d30d30fcc, SPL v1537, effective 2024-02-20).
    # The 4-hour interval is the LABEL'S, not the pharmacokinetic study's.
    # Section 17 Patient Counseling: "Inform patients that agents such as iron
    # and calcium supplements and antacids can decrease the absorption of
    # levothyroxine. Instruct patients not to take levothyroxine sodium tablets
    # within 4 hours of these agents." Singh 2001 (PMID 11716045) stays as
    # supporting magnitude evidence (T4 absorption 83.7 percent to 57.9
    # percent) but establishes the interaction, not the interval.
    #
    # Citation note: section 7.1 names calcium carbonate and ferrous sulfate
    # only as examples of PHOSPHATE BINDERS. The supplement-level instruction
    # lives in section 17, so that is what is cited.
    "timing_calcium_iron_thyroid_separate": {
        "ingredient1_tags": ["calcium"],
        "category": "important_separation",
        "actionability": "recommended",
        "evidence_level": "established",
        "source_authority": "fda_label",
        "applies_to": "any",
        "add_source": LEVOTHYROXINE_LABEL_SOURCE,
        "canaries": {"positive": ["183946"], "negative": ["180249"]},
    },
    # Same label authority, iron side. NIH ODS independently corroborates:
    # "advise against administering levothyroxine within 4 hours of iron
    # supplements".
    "timing_thyroid_med_iron_separate": {
        "ingredient2_tags": ["iron"],
        "category": "important_separation",
        "actionability": "recommended",
        "evidence_level": "established",
        "source_authority": "fda_label",
        "applies_to": "any",
        "add_source": LEVOTHYROXINE_LABEL_SOURCE,
        "canaries": {"positive": ["17105", "217573"], "negative": ["180249"]},
    },
    # P0. Was reaching 4 of 13,271 products: the rule aliased to soy /
    # soy_protein, neither of which the catalog emits. Messina & Redmond 2006
    # (PMID 16571087): soy foods "by inhibiting absorption, may increase the
    # dose of thyroid hormone required by hypothyroid patients." Skelin 2017
    # (PMID 28153426) independently lists soybeans among the substances with
    # "the greatest impact on the reduction of absorption".

    # Singh 2001 (PMID 11716045): coadministered calcium carbonate cut T4
    # absorption from 83.7% to 57.9% of the dose. Skelin 2017 lists calcium
    # carbonate/citrate/acetate as established and clinically significant, and
    # states the interaction "can be avoided by separating the administration".

    # Skelin 2017 lists iron sulfate among the established, clinically
    # significant reducers of levothyroxine absorption.

    # Sourced to the DailyMed levothyroxine label, which directs separating
    # interfering medicines by at least 4 hours. This is the one rule in the
    # file whose authority is genuinely fda_label.

    # Hallberg 1991 (PMID 1984335): 50-60% reduction in iron absorption at
    # 300-600 mg calcium. Hallberg 1992 (PMID 1600930) replicates and locates
    # the effect in the mucosal cell.

    # Kordas & Stoltzfus 2004 (PMID 15173386): "iron does seem to reduce the
    # absorption of zinc". A review, and the antagonism is dose-dependent — the
    # existing 25 mg iron gate is retained rather than firing at any dose.

    # Arendt & Skene 2005 (PMID 15649736), melatonin as a chronobiotic. The
    # 30-60 minute window is authored in the rule's own advice text and is
    # relative to the user's intended sleep, never to a clock hour.

}

# ---------------------------------------------------------------------------
# REJECTED — moved to the ledger, removed from the runtime artifact.
# ---------------------------------------------------------------------------
REJECTED: dict[str, str] = {
    "timing_ashwagandha_with_food": (
        "FABRICATED CAUSALITY, AND IT BURIES A SAFETY SIGNAL. Verified "
        "2026-08-01 against https://www.nccih.nih.gov/health/ashwagandha : "
        "'empty stomach', 'with food' and 'with a meal' each appear ZERO "
        "times. The page says only 'In some individuals, ashwagandha "
        "preparations may cause drowsiness, stomach upset, diarrhea, and "
        "vomiting.' The rule invented both the with-food instruction and the "
        "claim that 'most' GI effects occur on an empty stomach. Worse, the "
        "same page carries 'Although it is rare, there have been a number of "
        "cases that link liver injury to ashwagandha supplements', which the "
        "rule omits entirely. Framing nausea and abdominal discomfort as a "
        "dosing-technique problem could lead a user to read early "
        "drug-induced-liver-injury symptoms as something food will fix. The "
        "ashwagandha surface should carry the liver-injury line before it "
        "carries any timing tip."
    ),
    "timing_magnesium_with_food": (
        "RIGHT HAZARD, WRONG MECHANISM, UNSOURCED FIX. Verified 2026-08-01 "
        "against https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/ : "
        "'empty stomach', 'with food' and 'with a meal' each appear ZERO "
        "times. The GI effect is real and documented, but the page attributes "
        "it to DOSE and SALT FORM, not administration timing: 'The diarrhea "
        "and laxative effects of magnesium salts are due to the osmotic "
        "activity of unabsorbed salts in the intestine and colon', and 'The "
        "forms of magnesium that are most commonly reported to cause diarrhea "
        "include magnesium carbonate, chloride, gluconate, and oxide.' Food "
        "is not the lever the source identifies - dose and form are. A "
        "dose/form rule is authorable from this page; a timing rule is not."
    ),
    "timing_fat_soluble_vitamins_with_food": (
        "SOURCE CONTAINS NO SUCH GUIDANCE. Verified 2026-08-01 against "
        "https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/ : the page "
        "never mentions dietary fat in relation to vitamin A absorption and "
        "issues no administration instruction. What it does say cuts the other "
        "way — 'The absorption of preformed vitamin A esters from dietary "
        "supplements is 70%-90%, and that of beta-carotene ranges from 8.7% to "
        "65%.' Supplements contain preformed esters, which already absorb at "
        "70-90%. The identity is also unusable as scoped: the catalog tags "
        "'Beta Carotene 7,500 mcg' as `vitamin_a`, so retinol and provitamin "
        "carotenoids cannot be distinguished by tag."
    ),
    "timing_vitamin_k_with_food": (
        "CONTRADICTED BY ITS OWN SOURCE. The rule claimed 'absorption is "
        "minimal without dietary lipids'. Verified 2026-08-01 against "
        "https://ods.od.nih.gov/factsheets/VitaminK-HealthProfessional/ , confirmed by "
        "raw-HTML grep: 'The absorption rate of phylloquinone in its free form "
        "is approximately 80%, but its absorption rate from foods is "
        "significantly lower.' The word 'minimal' does not appear on the page. "
        "The fat benefit the page describes applies to phylloquinone FROM "
        "VEGETABLES, where chloroplast binding is the limiting factor, not to "
        "supplements — 'the body absorbs only 4% to 17% as much phylloquinone "
        "from spinach as from a tablet'. The rule transplanted a food-matrix "
        "finding onto supplements and inverted the magnitude. Identity was "
        "separately defective: `vitamin_k` reaches 248 of 802 vitamin-K "
        "products; the catalog emits vitamin_k1 (633) and vitamin_k2 (193)."
    ),
    "timing_zinc_with_food": (
        "SOURCE DOES NOT SUPPORT IT, AND OMITS A REAL TRADEOFF. Verified "
        "2026-08-01 against https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional/ , "
        "confirmed by raw-HTML grep: 'empty stomach' and 'with food' both "
        "appear zero times. The page attributes GI symptoms to DOSE, not to an "
        "empty stomach — 'High zinc intakes can cause nausea, dizziness, "
        "headaches, gastric distress, vomiting, and loss of appetite' — so the "
        "rule invented its causal mechanism. With-food dosing also carries an "
        "undisclosed cost the page does state: 'Phytates ... bind some "
        "minerals such as zinc in the intestine and form an insoluble complex "
        "that inhibits zinc absorption.' A dose-scoped tolerability rule could "
        "be authored later; this one cannot be repaired by rewording."
    ),
    "timing_omega3_with_meal": (
        "ALL THREE SUB-CLAIMS ABSENT FROM THE SOURCE. Verified 2026-08-01 "
        "against https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/ : "
        "the page contains no with-meal instruction, no meal-size variable, "
        "and no claim that food reduces fishy burps. It confirms the side "
        "effects exist ('unpleasant taste, bad breath, heartburn, nausea...') "
        "but attributes bioavailability to chemical form, not meals — "
        "'re-esterified triglycerides, natural triglycerides, and free fatty "
        "acids have somewhat higher bioavailability than ethyl esters'. The "
        "'largest meal' specificity was the most fabricated element."
    ),
    "timing_iron_empty_stomach": (
        "THE SOURCE SAYS THE OPPOSITE. Verified 2026-08-01 against "
        "https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/ and confirmed by "
        "raw-HTML grep: 'empty stomach' x0, 'tea' x0, 'coffee' x0, 'dairy' x0. "
        "The page's ONLY administration statement is 'Taking iron supplements "
        "with food can help minimize these adverse effects.' The rule led with "
        "empty-stomach dosing and named dairy, tea and coffee, none of which "
        "the page mentions. Its calcium sentence is also self-hedged: 'Calcium "
        "might interfere with the absorption of iron, although this effect has "
        "not been definitively established.' Superseded by "
        "timing_iron_with_food_gi, authored from the quote above."
    ),
    "timing_iron_vitamin_c_together": (
        "CONTRADICTED BY A RANDOMIZED TRIAL. The mechanism is real — Hallberg "
        "1989 (PMID 2507689) supports ascorbate enhancing nonheme iron "
        "absorption within a meal — but the clinical question was settled "
        "against the rule. Li et al. 2020 (PMID 33136134, JAMA Netw Open, "
        "equivalence RCT, 440 adults with iron-deficiency anemia) concluded: "
        "'oral iron supplements alone were equivalent to oral iron supplements "
        "plus vitamin C in improving hemoglobin recovery and iron absorption. "
        "These findings suggest that on-demand vitamin C supplements are not "
        "essential to take along with oral iron supplements for patients with "
        "IDA.' A per-meal absorption effect that does not change hemoglobin "
        "recovery is not a reason to instruct co-dosing. The rule also never "
        "scoped itself to nonheme iron, which is the only form the mechanism "
        "applies to."
    ),
    "timing_curcumin_with_fat_and_pepper": (
        "SAFETY, AND THE CITED SOURCE DOES NOT MAKE THE CLAIM. The rule told "
        "users to add black pepper / piperine with no reference to their "
        "medication list. Verification on 2026-08-01 found NCCIH makes no such "
        "claim at all: its turmeric page mentions piperine only as a "
        "bioavailability aid, and the words 'cytochrome' and 'P-glycoprotein' "
        "do not appear on it or on its herb-drug-interactions page. What IS "
        "established, from separate sources that must not be fused: piperine "
        "raises exposure to phenytoin (PMID 16767797), propranolol and "
        "theophylline (PMID 1815977) and carbamazepine (PMID 19283724) in "
        "human PK studies, whose authors attribute the effect to ABSORPTION; "
        "and piperine inhibits CYP3A4 and P-glycoprotein in vitro (PMID "
        "12130727, Caco-2 and human liver microsomes). Recommending an extra "
        "bioactive substance is not timing guidance. A fat-with-meal rule "
        "could be researched separately."
    ),
    "timing_coffee_iron_separate": (
        "NO HONEST IDENTITY IN THIS SCHEMA. The science is sound: Morck 1983 "
        "(PMID 6402915) measured a 39% reduction in iron absorption from a "
        "meal taken with coffee, and found 'No decrease in iron absorption "
        "occurred when coffee was consumed 1 h before a meal'. But the actor "
        "is coffee the beverage, and the shipped catalog emits no `coffee` tag "
        "(nearest: green_coffee_bean 18 products, coffee_fruit 13, "
        "chlorogenic_acids 2). Coffee is a dietary exposure, not a stack row. "
        "The rule was therefore keyed to `caffeine`, which the app expanded to "
        "include `guarana`, so 270 products received advice about a beverage "
        "they do not contain. Re-pointing the identity cannot fix this. "
        "Rejected rather than suppressed so the false identity cannot be "
        "inherited by a future promotion. Reintroduce only when the app can "
        "represent dietary exposure; caffeine and guarana are permanently "
        "locked as negative canaries."
    ),
    "timing_thyroid_med_coffee_separate": (
        "NO HONEST IDENTITY IN THIS SCHEMA. Same blocker, and clinically the "
        "more important of the two: Benvenga 2008 (PMID 18341376) measured "
        "coffee lowering T4 absorption by 27-36%, and Skelin 2017 (PMID "
        "28153426) ranks coffee among the substances with the greatest impact "
        "on levothyroxine absorption. The medication side is sound (RxCUI "
        "10582); the coffee side has no catalog identity, and keying it to "
        "`caffeine` meant a caffeine tablet triggered advice about espresso "
        "and levothyroxine. Rejected rather than suppressed so the identity "
        "cannot be inherited. This is the highest-value rule to reinstate once "
        "a dietary-exposure surface exists."
    ),
    "timing_vitamin_b12_folate_together": (
        "The advice is a no-op: it states the two 'can be taken together at any "
        "time of day', which is an explicit assertion that timing does not "
        "matter — yet it was encoded as a scheduling constraint. Its source is "
        "the NIH ODS folate factsheet, a general reference that establishes "
        "metabolic interdependence, not co-administration benefit. A shared "
        "biological pathway is not evidence for simultaneous dosing. It was "
        "also unreachable: it aliased to `vitamin_b12` and `folate`, neither of "
        "which the catalog emits (the real tags are vitamin_b12_cobalamin, "
        "1580 products, and vitamin_b9_folate, 1399). Fixing the identity would "
        "only make a rule that advises nothing reachable by 2,979 products."
    ),
}

# ---------------------------------------------------------------------------
# NEEDS REVISION — suppressed at runtime, each with the specific blocker.
# ---------------------------------------------------------------------------
NEEDS_REVISION: dict[str, str] = {
    "timing_thyroid_med_magnesium_separate": (
        "NOT LABEL-SUPPORTED AS WRITTEN. Verification on 2026-08-01 read the "
        "SYNTHROID label (setid 1e11ad30-1041-4520-10b0-8f9d30d30fcc, SPL "
        "v1537) and the generic in full: magnesium is never named as a "
        "SUPPLEMENT. Every occurrence is either 'magnesium hydroxides' (an "
        "antacid) or 'magnesium stearate' (an excipient), and the antacid row "
        "in section 7.1 carries no interval at all - it says only 'Monitor "
        "patients appropriately.' Section 17 does place antacids inside the "
        "4-hour instruction, so a magnesium-ANTACID rule may be defensible, "
        "but a standalone magnesium-supplement rule at 4 hours is not. This "
        "rule was briefly promoted on the assumption the label covered it; "
        "reading the label removed it. Needs either an antacid-scoped rewrite "
        "or a source that addresses magnesium salts."
    ),
    "timing_melatonin_before_bed": (
        "INTERVAL AND AUTHORITY BOTH OVERCLAIMED. Arendt & Skene 2005 (PMID 1"
        "5649736) supports melatonin as a chronobiotic and says exogenous mel"
        "atonin is 'most effective around dusk and dawn', but it never states"
        " a 30-60 minute pre-sleep window — the number in the advice has no c"
        "ited source. PubMed also types it as a narrative Review, not a syste"
        "matic review, so the authority assigned during the first pass was an"
        " overclaim. The rule's own source entry additionally typed a pubmed."
        "ncbi.nlm.nih.gov URL as `reference`. Separately, one window cannot c"
        "over immediate-release, prolonged-release, phase-shifting and jet-la"
        "g use at different doses. Blocked on an interval source and a form/p"
        "urpose scope."
    ),
    "timing_iron_zinc_separate": (
        "INTERVAL UNSUPPORTED BY CITED SOURCE. Kordas & Stoltzfus 2004 (PMID "
        "15173386) states 'iron does seem to reduce the absorption of zinc' b"
        "ut establishes no interval, and argues the enterocyte DMT1 is an unl"
        "ikely site. The 25 mg fasting-iron gate is retained and correct. Blo"
        "cked on interval evidence."
    ),
    "timing_iron_calcium_separate": (
        "INTERVAL UNSUPPORTED BY CITED SOURCE. Hallberg 1991 (PMID 1984335) a"
        "nd 1992 (PMID 1600930) establish a 50-60% acute reduction in iron ab"
        "sorption at 300-600 mg calcium and locate the effect in the mucosal "
        "cell. Neither tests or recommends a 2-hour separation, and neither a"
        "ddresses whether spacing changes iron status over time. Blocked on i"
        "nterval evidence."
    ),
    "timing_thyroid_med_soy_separate": (
        "IDENTITY FIXED, INTERVAL NOT. The reachability defect is corrected —"
        " the rule now names `soybean` and `soy_isoflavones` instead of `soy`"
        " and `soy_protein`, which the catalog never emits. Messina & Redmond"
        " 2006 (PMID 16571087) supports the interaction: soy foods 'by inhibi"
        "ting absorption, may increase the dose of thyroid hormone required'."
        " Neither that review nor Skelin 2017 states 4 hours. Also unresolved"
        ": whether concentrated isoflavone supplements and soy foods warrant "
        "the same instruction. Blocked on the label plus that scope decision."
    ),
    "timing_calcium_vitamin_d_together": (
        "The cited source (PMID 21118827) is the IOM dietary reference intake "
        "report for calcium and vitamin D. It establishes daily intake "
        "requirements; it says nothing about swallowing the two together. "
        "knowledge/timing-rules-research.md reaches the same conclusion: "
        "'STRONG but STATUS, not same-pill timing'. Pending clinician decision "
        "to remove or re-author as adequacy guidance."
    ),
    "timing_quercetin_vitamin_c_together": (
        "The cited Linus Pauling Institute flavonoid page does not establish "
        "that vitamin C enhances quercetin absorption. Mechanism-only "
        "co-administration advice. Pending clinician decision."
    ),
    "timing_calcium_carbonate_with_food": (
        "PIPELINE DEPENDENCY, not a clinical defect. Recker 1985 (PMID 4000241) "
        "is strong: calcium carbonate absorption is impaired under fasting "
        "conditions in achlorhydria, and 'Administration of calcium carbonate "
        "as part of a normal breakfast resulted in completely normal "
        "absorption'. But the catalog emits zero `calcium_carbonate` tags, so "
        "the rule is unreachable. Blocked on the pipeline emitting a calcium "
        "form identity. Valid science must not be rejected for a catalog gap."
    ),
    "timing_probiotics_by_formulation": (
        "Tompkins 2011 (PMID 22146689) is an in vitro digestive-model study, "
        "not a clinical one, and supports 'with or just prior to a meal "
        "containing some fats'. Identity is also fragmented: the `probiotics` "
        "tag reaches 10 products while the catalog carries 60+ distinct "
        "`*_probiotic_blend` tags and 695 products flagged is_probiotic. Needs "
        "a pipeline-level probiotic identity plus an evidence downgrade."
    ),
    "timing_bromelain_timing_by_purpose": (
        "Castell 1997 (PMID 9252520) demonstrates that undegraded bromelain "
        "reaches plasma after oral dosing. It does not establish the rule's "
        "purpose-dependent claim (empty stomach for systemic effect vs with "
        "food for digestion). Needs a source that addresses administration "
        "timing."
    ),
    "timing_l_theanine_caffeine_together": (
        "Owen 2008 (PMID 18681988) is a real randomized crossover showing "
        "L-theanine plus caffeine improves attention-switching. But that is a "
        "combination-effect finding, not timing guidance, and it lands in the "
        "`optional` category which requires explicit clinician approval before "
        "it may render. Pending that approval."
    ),
    "timing_psyllium_water_med_spacing": (
        "MedlinePlus supports spacing psyllium from medicines, and the relation "
        "is now honestly modelled as separate_from_medications with no invented "
        "second bottle. Held pending clinician sign-off on applying a blanket "
        "3-hour window to every medication rather than per-drug."
    ),
}



# ---------------------------------------------------------------------------
# NEWLY AUTHORED — written FROM a verified quote, not inherited from the corpus.
#
# The original corpus was written claim-first with an authoritative URL attached
# afterwards, which is why 5 of 6 ODS-cited rules failed verification. These are
# authored the other way round: the quote came first.
# ---------------------------------------------------------------------------
NEW_RULES: list[dict] = [
    {
        "id": "timing_iron_with_food_gi",
        "ingredient1": "iron",
        "ingredient1_tags": ["iron"],
        "timing_relation": {"type": "with_food"},
        "category": "how_to_take",
        "applies_to": "standalone",
        "actionability": "optional",
        "source_authority": "reference",
        "review_status": "verified",
        "advice": (
            "Higher-dose iron can cause nausea, constipation or stomach "
            "upset. Taking it with food can help minimize this."
        ),
        "mechanism": (
            "NIH ODS states plainly: 'High-dose iron supplements can also "
            "cause gastrointestinal effects, including gastric upset, "
            "constipation, nausea, abdominal pain, vomiting, and diarrhea. "
            "Taking iron supplements with food can help minimize these "
            "adverse effects.' Food can reduce iron absorption, so this is a "
            "tolerability tradeoff rather than an absorption optimisation, "
            "which is why it is actionability=optional."
        ),
        "score_impact": 0,
        "evidence_level": "probable",
        "sources": [
            {
                "source_type": "nih_ods",
                "label": (
                    "NIH ODS - Iron Fact Sheet for Health Professionals: "
                    "taking iron supplements with food can help minimize "
                    "gastrointestinal adverse effects"
                ),
                "url": "https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/",
            }
        ],
        "canaries": {"positive": ["17105", "217573"], "negative": ["278010"]},
        "reviewed_on": "2026-08-01",
        "supersedes": "timing_iron_empty_stomach",
    },
]

def main() -> int:
    data = json.loads(RULES.read_text(encoding="utf-8"))
    rules = data["timing_rules"]
    by_id = {r["id"]: r for r in rules}

    # Newly authored rules are appended before coverage is checked, so they
    # are audited by the same guard as everything else.
    # NEW_RULES is the authoritative definition, not a one-time insert: this
    # script must converge to the same artifact however many times it runs, so
    # an already-present newly-authored rule is REPLACED rather than skipped.
    for new in NEW_RULES:
        fresh = json.loads(json.dumps(new))
        if new["id"] in by_id:
            existing = by_id[new["id"]]
            existing.clear()
            existing.update(fresh)
        else:
            rules.append(fresh)
            by_id[new["id"]] = rules[-1]

    # Dispositions must be mutually exclusive. Without this, a rule listed in
    # two dicts resolves to whichever loop runs last — which silently held
    # timing_egcg_iron_separate at needs_revision while it also sat in
    # VERIFIED, and no gate would have caught it.
    for a_name, a, b_name, b in (
        ("VERIFIED", VERIFIED, "NEEDS_REVISION", NEEDS_REVISION),
        ("VERIFIED", VERIFIED, "REJECTED", REJECTED),
        ("NEEDS_REVISION", NEEDS_REVISION, "REJECTED", REJECTED),
    ):
        overlap = set(a) & set(b)
        assert not overlap, (
            f"{sorted(overlap)} appear in both {a_name} and {b_name} — a rule "
            f"has exactly one disposition"
        )

    known = set(VERIFIED) | set(REJECTED) | set(NEEDS_REVISION) | {
        n["id"] for n in NEW_RULES
    }
    shipped = set(by_id)
    # The guard that makes this safe to run as one pass: nothing is skipped.
    # A REJECTED id may already be absent (the script is re-runnable), but an
    # id in the artifact that no disposition covers is a hard error — that is
    # exactly the silent skip this guard exists to prevent.
    unaudited = shipped - known
    unknown = known - shipped - set(REJECTED)
    assert not unaudited and not unknown, (
        f"audit coverage mismatch — unaudited: {sorted(unaudited)}, "
        f"unknown: {sorted(unknown)}"
    )

    for rule_id, updates in VERIFIED.items():
        rule = by_id[rule_id]
        canaries = updates.pop("canaries")
        add_source = updates.pop("add_source", None)
        new_advice = updates.pop("advice", None)
        new_relation = updates.pop("relation", None)
        replacement_sources = updates.pop("replace_sources", None)
        if replacement_sources:
            # Replace, never append: the old citation did not support the claim,
            # and leaving it in would let a reader think two sources agreed.
            rule["sources"] = replacement_sources
        new_mechanism = updates.pop("mechanism", None)
        if new_mechanism:
            rule["mechanism"] = new_mechanism
        if new_relation:
            rule["timing_relation"] = new_relation
        if new_advice:
            rule["advice"] = new_advice
        if add_source and not any(
            src["url"] == add_source["url"] for src in rule.get("sources", [])
        ):
            # Prepend: the interval authority must be the first thing a reader
            # sees, ahead of the supporting magnitude study.
            rule.setdefault("sources", []).insert(0, add_source)
        rule.update(updates)
        rule["review_status"] = "verified"
        rule["canaries"] = canaries
        rule.pop("_relation_is_migration_placeholder", None)

    for rule_id, reason in NEEDS_REVISION.items():
        rule = by_id[rule_id]
        rule["review_status"] = "needs_revision"
        rule["review_note"] = reason
        rule["reviewed_on"] = "2026-08-01"
        # Structured so the remaining work is measurable rather than a vague
        # permanent suppression.
        blockers = []
        if "INTERVAL UNSUPPORTED" in reason or "INTERVAL NOT" in reason:
            blockers.append("interval_not_supported_by_cited_source")
        if "IDENTITY IMPOSSIBLE" in reason or "identity" in reason.lower():
            blockers.append("canonical_identity_unresolved")
        if "not content-verified" in reason:
            blockers.append("citation_not_content_verified")
        if "PIPELINE DEPENDENCY" in reason:
            blockers.append("catalog_identity_missing_upstream")
        if "clinician" in reason.lower():
            blockers.append("awaiting_clinician_decision")
        if "SAFETY" in reason:
            blockers.append("safety_concern")
        rule["review_blockers"] = blockers or ["citation_not_content_verified"]

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    existing = {e["id"] for e in ledger["rejected"]}
    for rule_id, reason in REJECTED.items():
        if rule_id in existing or rule_id not in by_id:
            continue
        rule = by_id[rule_id]
        ledger["rejected"].append(
            {
                "id": rule_id,
                "prior_claim": rule["advice"],
                "rejection_reason": reason,
                "source_reviewed": [
                    s.get("url", "") for s in rule.get("sources", [])
                ],
                "reviewer": "engineering — source content-verified against PubMed 2026-08-01",
                "reviewed_on": "2026-08-01",
                "superseding_rule": None,
                # Fingerprint so a reintroduction under a different id or
                # slightly reworded advice is still detectable.
                "clinical_fingerprint": {
                    "ingredient1": rule.get("ingredient1"),
                    "ingredient2": rule.get("ingredient2"),
                    "ingredient1_tags": rule.get("ingredient1_tags"),
                    "ingredient2_tags": rule.get("ingredient2_tags"),
                    "ingredient1_rxcuis": rule.get("ingredient1_rxcuis"),
                    "ingredient2_rxcuis": rule.get("ingredient2_rxcuis"),
                    "timing_relation": rule.get("timing_relation"),
                    "mechanism": rule.get("mechanism"),
                },
            }
        )
    ledger["_metadata"]["total_entries"] = len(ledger["rejected"])
    LEDGER.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    kept = [r for r in rules if r["id"] not in REJECTED]
    verified = sum(1 for r in kept if r["review_status"] == "verified")
    data["timing_rules"] = kept
    data["_metadata"]["total_entries"] = len(kept)
    # Metadata must describe the artifact's actual state, so a reader (or a
    # release gate) can tell at a glance how much of the file is live without
    # counting rules by hand.
    data["_metadata"]["last_updated"] = "2026-08-01"
    data["_metadata"]["clinical_review_version"] = "timing-section-2"
    data["_metadata"]["runtime_policy"] = "verified_only"
    data["_metadata"]["status_counts"] = {
        "verified": verified,
        "needs_revision": len(kept) - verified,
        "rejected": len(ledger["rejected"]),
    }
    RULES.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    verified = sum(1 for r in kept if r["review_status"] == "verified")

    print(f"rules: {len(rules)} -> {len(kept)} (rejected {len(REJECTED)})")
    print(f"verified: {verified}   needs_revision: {len(kept) - verified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
