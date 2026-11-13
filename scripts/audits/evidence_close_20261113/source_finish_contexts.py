"""Thirteen no-credit source decisions, one per unread declared PMID (2026-11-13).

Each paper was read from its PubMed abstract (no PMC full-text copy was found for any).
A decision closes source review for that PMID only: no credit, no Dose
transfer, no invented arms. Applied by ``apply_source_finish.py``.
"""

REVIEWER = ("Claude agent review (claude-opus-5-5) of the PubMed abstract; agent review, not clinician "
            "review; independent abstract re-read by a fresh-context Claude agent")
NO_FULL_TEXT = "No PMC full-text copy was found in this review; decision made from the PubMed abstract. Publisher or other repository access was not established."


def context(record_id, pmid, slug, notes, limitations):
    return {
        "context_id": f"{record_id.lower()}_{pmid}_{slug}",
        "components": [record_id],
        "source_pmids": [pmid],
        "review_status": "rejected_source",
        "scoring_eligible": False,
        "clinical_review": {
            "reviewer": REVIEWER,
            "reviewed_at": "2026-11-13",
            "scope": "identity_dose_outcome_applicability",
            "notes": notes,
        },
        "dose": {"source_provenance": {
            "pmid": pmid,
            "location": "PubMed abstract.",
            "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        }},
        "limitations": [*limitations, NO_FULL_TEXT],
    }


CONTEXTS = [
    context("BRAND_SETRIA", "24791752", "body_stores_biomarker",
            "No efficacy credit: outcomes are glutathione levels in body compartments, an exposure biomarker; "
            "the abstract does not name the Setria material.",
            ["Abstract: 6-month double-blind placebo-controlled RCT in 54 healthy non-smoking adults, oral "
             "glutathione 250 or 1,000 mg/day. Blood glutathione rose versus baseline at 1, 3 and 6 months at "
             "both doses; at 6 months the high dose raised erythrocyte, plasma and lymphocyte levels 30-35% and "
             "buccal cells 260%, and the low dose raised blood and erythrocyte levels 17% and 29% (P < 0.05). "
             "In most cases levels returned to baseline after a 1-month washout. The oxidized-to-reduced "
             "glutathione ratio fell in both dose groups at 6 months.",
             "Secondary immune markers were measured in a subset only; natural killer cytotoxicity rose more "
             "than twofold versus placebo at 3 months in the high-dose group. Not a clinical outcome.",
             "Exact branded material identity is not stated in the abstract; no Setria-specific transfer."]),
    context("BRAND_BIOCELL", "22486722", "oa_symptoms_single_trial",
            "No credit transferred: one positive trial whose full text could not be read.",
            ["Abstract: randomized double-blind placebo-controlled trial, 80 adults with physician-verified "
             "hip and/or knee osteoarthritis and baseline pain of at least 4; 2 g/day BioCell Collagen for 70 "
             "days. Intent-to-treat VAS pain fell versus placebo at day 70 (p < 0.001); WOMAC improved at days "
             "35 (p = 0.017) and 70 (p < 0.001); physical activity improved at days 35 (p = 0.007) and 70 "
             "(p < 0.001); tolerability comparable to placebo.",
             "Positive finding preserved as reported; not independently replicated here. The first author's "
             "listed affiliation is AIBMR Life Sciences, Inc.; funding roles are not readable from the abstract."]),
    context("BRAND_BIOCELL", "31221944", "skin_appearance",
            "No credit: cosmetic skin-appearance outcomes in healthy women; full text not readable.",
            ["Abstract: 12-week double-blind placebo-controlled trial in 128 women aged 39-59 (113 completed); "
             "500 mg BioCell Collagen twice daily (1 g/day; at least 300 mg hydrolyzed type II collagen, 100 mg "
             "chondroitin sulfate, 50 mg hyaluronic acid per 500 mg).",
             "Reported versus placebo: facial lines and wrinkles (P = .019), crow's feet (P = .05), elasticity "
             "(P = .008), indirect cutaneous collagen content (P < .001), visual grading and wrinkle width "
             "(P = .046), and less dryness and erythema; no difference in skin-surface water content or "
             "retention; no reported adverse reactions. Instrumental and visual cosmetic endpoints, not a "
             "health outcome.",
             "A co-author (Schauss) is also first author of the BioCell osteoarthritis trial (PMID 22486722)."]),
    context("INGR_LION_MANE", "18844328", "mci_small_trial",
            "No credit transferred: small single trial; the benefit faded after stopping; full text not readable.",
            ["Abstract: double-blind parallel placebo-controlled trial in 30 Japanese adults aged 50-80 with "
             "mild cognitive impairment (15 per group); four 250 mg tablets containing 96% Yamabushitake "
             "(Hericium erinaceus) dry powder three times daily for 16 weeks, then 4 weeks off.",
             "Scores on a cognitive scale based on the Revised Hasegawa Dementia Scale were higher than placebo "
             "at weeks 8, 12 and 16 and fell significantly 4 weeks after intake stopped. No adverse laboratory "
             "effects were reported.",
             "The first author is affiliated with a mushroom producer (Hokuto Corporation). Preparation (part "
             "and extraction) is not further specified in the abstract; no transfer to extracts."]),
    context("INGR_INULIN", "35833477", "chicory_itf_meta",
            "No credit: microbiome-surrogate and pooled bowel-function findings across preparations; the main "
            "Methods update-search reconciliation stays unread.",
            ["Abstract: systematic review with random-effects meta-analyses of RCTs (at least 7 days) of "
             "chicory-derived inulin-type fructans at 3-20 g/day; Bifidobacterium abundance SMD 0.83 (95% CI "
             "0.58-1.08; 50 studies; 2,525 participants aged 0-83); bifidogenic in healthy and impaired "
             "populations except gastrointestinal disorders; bowel-function benefits in healthy subjects. "
             "Searches ran to January 2021. PROSPERO CRD42020162892.",
             "Two authors list BENEO-Institute affiliations. From this record's earlier 2026-11-08 agent review, "
             "not the abstract: the four recovered publisher supplements retain mixed, null and adverse "
             "gastrointestinal secondary findings, and the main-text update-search reconciliation is unread.",
             "Bifidobacterium abundance is a surrogate, not a clinical benefit. Pooled preparations and ages do "
             "not establish equivalence for any one product's inulin or FOS."]),
    context("PRECLIN_ASTAXANTHIN_GENERIC", "32755613", "cardiometabolic_meta",
            "No credit: mostly null cardiometabolic biomarkers; the positive findings are small or subgroup-only.",
            ["Abstract: meta-analysis of 14 eligible articles (RCTs per the title). No association with fasting glucose, HbA1c, total or LDL "
             "cholesterol, triglycerides, BMI, body weight, or systolic or diastolic blood pressure.",
             "HDL cholesterol rose by a weighted mean of 1.473 mg/dL (95% CI 0.319-2.627). CRP fell only in "
             "subgroups of at least 12 weeks or more than 12 mg/day; the abstract reports these CRP units "
             "inconsistently (mg/l and mg/dl).",
             "Biomarker outcomes only; no clinical endpoint."]),
    context("PRECLIN_ASTAXANTHIN_GENERIC", "35091276", "oxidative_inflammation_meta",
            "No credit: oxidative-stress and inflammation biomarkers only, from small pooled trials.",
            ["Abstract: systematic review and meta-analysis of 12 placebo-controlled RCTs (380 participants). "
             "Malondialdehyde fell (SMD -0.95; 95% CI -1.67 to -0.23), notably in type 2 diabetes; IL-6 fell in "
             "type 2 diabetes (-0.70 pg/mL); CRP and TNF-alpha did not change significantly.",
             "Few trials for other oxidative markers; in overweight subjects astaxanthin appeared to improve "
             "superoxide dismutase activity and reduce serum isoprostane. Biomarker outcomes only; no clinical "
             "endpoint."]),
    context("PRECLIN_ASTAXANTHIN_GENERIC", "38243785", "fatigue_cognition_exercise_meta",
            "No credit: fatigue rests on two studies, cognition is not significant, and the exercise gains depend on "
            "concurrent training.",
            ["Abstract: meta-analysis of 11 RCTs (346 healthy participants). Two studies showed a trend toward "
             "less subjective fatigue. After 8-12 weeks, cognitive accuracy was called marginally significant "
             "by the authors (SMD 0.12; 95% CI -0.02 to 0.26, which includes zero); reaction time was not "
             "significant (SMD -0.08; 95% CI -0.26 to 0.10).",
             "With regular training, fat oxidation (SMD 2.56) and physical performance (SMD 0.62) improved; "
             "subgroups favored aerobic exercise (SMD 0.45), at least 20 mg/day and more than 12 weeks. The abstract's interval for the "
             "longer-duration subgroup (SMD 0.66; 95% CI 0.13-0.63) does not contain its point estimate.",
             "Exercise outcomes are combined with training and do not transfer to a general fatigue or "
             "cognition benefit."]),
    context("INGR_BLACK_SEED_OIL", "21675032", "t2dm_seed_capsule_doses",
            "No credit: seed-capsule adjunct dose study in type 2 diabetes with no placebo arm stated; not the oil.",
            ["Abstract: 94 adults with type 2 diabetes on oral hypoglycemic drugs randomized to 1, 2 or 3 g/day "
             "Nigella sativa seed capsules for 3 months. At 2 g/day fasting glucose, 2-hour glucose and HbA1c "
             "(-1.52%) fell from baseline, HOMA2 insulin resistance fell (P < 0.01) and beta-cell function rose "
             "(P < 0.02); 1 g/day showed non-significant trends; 3 g/day added no further benefit. Renal and "
             "hepatic function were not adversely affected.",
             "Comparisons in the abstract are against baseline across dose groups; no placebo group is stated.",
             "Seed capsules, not black seed oil; adjunct use in diabetes does not transfer to general use."]),
    context("INGR_BLACK_SEED_OIL", "37341696", "blood_pressure_meta",
            "No credit: small pooled blood-pressure reductions with very high heterogeneity.",
            ["Abstract: updated systematic review and random-effects meta-analysis of RCTs in adults (searched "
             "to August 2022). Systolic -3.06 mmHg (95% CI -3.89 to -2.22; I-squared 84.7%) and diastolic "
             "-2.69 mmHg (95% CI -3.72 to -1.66; I-squared 97.3%).",
             "The abstract does not state the number of trials, the preparations or the populations; seed and "
             "oil preparations cannot be separated from it."]),
    context("INGR_BLACK_SEED_OIL", "40210172", "t2dm_cardiometabolic_meta",
            "No credit: adjunct findings limited to type 2 diabetes, with mixed preparations and several null "
            "outcomes.",
            ["Abstract: meta-analysis of 16 RCTs in type 2 diabetes. Fasting glucose -21.43 mg/dL, HbA1c -0.44, "
             "total cholesterol -18.80 mg/dL and LDL -19.53 mg/dL. No significant effect on 2-hour glucose, "
             "insulin, HOMA, triglycerides, HDL, liver enzymes, creatinine, weight or BMI.",
             "Fasting glucose fell in trials longer than 8 weeks; subgroups suggested HbA1c, HOMA and LDL effects with the oil form, more than 1 g/day and 8 weeks "
             "or less. Population-specific adjunct evidence; no transfer to people without diabetes."]),
    context("INGR_SEA_BUCKTHORN", "20554904", "dry_eye_single_trial",
            "No credit transferred: one trial with mixed significance across analyses; full text not readable.",
            ["Abstract: double-blind randomized parallel trial in 100 adults aged 20-75 with dry eye symptoms "
             "(86 completed); 2 g/day sea buckthorn oil or placebo oil for 3 months, fall to winter.",
             "Tear osmolarity rose less than placebo (ITT P = 0.04; per protocol P = 0.02). Redness differed in "
             "ITT (P = 0.04) but not per protocol (P = 0.11); burning differed per protocol (P = 0.04) but not "
             "in ITT (P = 0.05).",
             "Oil preparation only; the seed versus pulp source is not specified in the abstract."]),
    context("INGR_SEA_BUCKTHORN", "36043374", "metabolic_syndrome_meta",
            "No credit: lipid changes confined to people with abnormal lipids, with high heterogeneity.",
            ["Abstract: meta-analysis of 15 RCTs. Overall, triglycerides, total cholesterol and LDL fell and HDL "
             "rose (SMD scale); subgroup analysis found lipid reductions only in people with abnormal lipid "
             "metabolism. No effect on blood glucose, blood pressure or BMI.",
             "Authors report high heterogeneity that persists after subgroup analysis; the abstract does not "
             "describe the preparations."]),
]
