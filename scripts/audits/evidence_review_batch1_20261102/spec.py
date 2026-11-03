"""Per-entry literature reviews for the first Evidence review batch (2026-11-03).

Every figure comes from the PubMed abstract read on 2026-11-03. None of this is a
clinician approval and none of it earns Evidence credit. Effect labels used here:
At study level, positive_weak means a significant finding the authors qualify (low certainty, high
heterogeneity or bias); mixed means findings differ by outcome, population or fiber
type; null means no significant benefit on the tested outcome; negative records an
observed harm. No record here uses positive_moderate or positive_strong.
"""

QUERIES = {
    "turmeric": ["turmeric_syn", "turmeric_rct"],
    "ginkgo": ["ginkgo_syn", "ginkgo_rct_dementia"],
    "methionine": ["methionine_all"],
    "fiber": ["fiber_syn"],
    "collagen": ["collagen_syn", "collagen_rct"],
}

RECORDS = {
    "turmeric": {
        "material_form": "Curcuma longa (turmeric) extract, including curcumin preparations; curcuminoid content and bioavailability preparation vary. Whole root powder, ratio extracts and unspecified turmeric are not settled by these studies",
        "population_context": "Adults with knee osteoarthritis, functional dyspepsia or non-alcoholic fatty liver disease; source-specific populations only",
        "documented_review_scope": {"scope": "ingredient", "require_source_label_form": True,
            "required_form_terms": ['extract', 'curcumin', 'curcuminoid', 'curcuminoids', 'meriva', 'bcm-95'],
            "excluded_form_terms": ['4:1', 'turmeric powder', 'root powder', 'rhizome powder'],
            "supported_outcomes": ['joint', 'digestive'],
            "studied_population": 'Adults with knee osteoarthritis or functional dyspepsia',
            "source_pmids": ['33511486', '40731001', '32926799', '34652861'], "reviewed_at": "2026-11-03"},
        "effect_direction": None,
        "applicability_status": "applicability_unestablished",
        "applicability_decision": (
            "Human trials tested specific Curcuma longa extracts. Knee-pain syntheses favor them with low certainty and heterogeneous preparations (33511486, 40731001); "
            "one RCT improved pain but not effusion-synovitis (32926799), and a curcumin trial improved functional dyspepsia scores (34652861). One small trial used 3 g/day whole powder (28443702), "
            "which does not settle whole root or unspecified turmeric. Findings are outcome-specific and a label's "
            "curcuminoid content may differ, so this review earns no Evidence credit. A row declaring a studied extract finishes at no credit, a row declaring whole powder or a ratio extract finishes as outside these studies, and a row stating no preparation stays open. Case reports link high-bioavailability curcumin formulations to acute liver injury (32656820); that signal is "
            "recorded here and does not change any safety owner."
        ),
        "studies": [
            dict(pmid="33511486", study_type="meta_analysis_rct", sample_size=1810,
                 primary_endpoint="Knee pain and physical function in knee osteoarthritis",
                 outcome="16 RCTs up to 16 weeks: less knee pain (SMD -0.82) and better function (SMD -0.75) than placebo, similar to NSAIDs; heterogeneous, moderate risk of bias.",
                 effect_direction="positive_weak", quote="Turmeric extracts significantly reduced knee pain"),
            dict(pmid="40731001", study_type="systematic_review_meta",
                 primary_endpoint="WOMAC pain in knee osteoarthritis across turmeric preparations",
                 outcome="17 studies in a network meta-analysis: all preparations reduced WOMAC pain versus placebo; authors rate certainty low.",
                 effect_direction="positive_weak", quote="the certainty of evidence remains low"),
            dict(pmid="32926799", study_type="randomized_double_blind_placebo_controlled", sample_size=70, duration="12 weeks",
                 primary_endpoint="Knee pain (VAS) and effusion-synovitis volume on MRI",
                 outcome="VAS pain improved by -9.1 mm versus placebo; effusion-synovitis volume did not change.",
                 effect_direction="mixed", quote="did not change effusion-synovitis volume"),
            dict(pmid="34652861", study_type="randomized_double_blind_placebo_controlled", sample_size=132, duration="4 weeks",
                 primary_endpoint="Severity of Dyspepsia Assessment in functional dyspepsia",
                 outcome="Pain and non-pain scores fell more than placebo and did not differ from omeprazole.",
                 effect_direction="positive_weak", quote="No significant difference was observed between curcumin and omeprazole groups"),
            dict(pmid="28443702", study_type="randomized_controlled_trial", sample_size=46, dose="3000 mg/day turmeric powder (6 x 500 mg capsules)", duration="12 weeks",
                 primary_endpoint="Glycemic indices and leptin in non-alcoholic fatty liver disease",
                 outcome="Glucose, insulin, HOMA-IR and leptin fell versus placebo; weight, BMI and liver enzymes did not change significantly.",
                 effect_direction="mixed", quote="Changes in weight, BMI and liver enzymes were not significant"),
            dict(pmid="32656820", study_type="case_series_systematic_review",
                 primary_endpoint="Acute liver injury reports after Curcuma longa supplements",
                 outcome="7 Tuscan cases and 23 published cases; the Tuscan cases involved high-bioavailability, high-dose curcumin or curcuminoid formulations. Case evidence, not an efficacy finding.",
                 effect_direction="negative", quote="confirmed the association between Curcuma longa and liver injury"),
        ],
    },
    "ginkgo": {
        "material_form": "Ginkgo biloba leaf extract, mainly standardized preparations such as EGb 761; undeclared extracts and crude leaf powder are not settled by these studies",
        "population_context": "Older adults with normal cognition, memory complaints, mild cognitive impairment or dementia; adults with tinnitus or intermittent claudication",
        "documented_review_scope": {"scope": "ingredient", "require_source_label_form": True,
            "required_form_terms": ['flavone glycoside', 'flavone glycosides', 'flavonol glycoside', 'flavonol glycosides', 'egb 761', 'egb761', 'ginkgold'],
            "excluded_form_terms": ['4:1', 'biloba powder', 'ginkgo powder', 'leaf powder'],
            "supported_outcomes": ['cognitive'],
            "studied_population": 'Older adults with normal cognition, memory complaints, mild cognitive impairment or dementia',
            "source_pmids": ['41641880', '20040554', '22959217', '36383762', '23744597'], "reviewed_at": "2026-11-03"},
        "effect_direction": None,
        "applicability_status": "applicability_unestablished",
        "applicability_decision": (
            "Large prevention trials of 120 mg twice daily found no reduction in Alzheimer's incidence or cognitive decline (20040554, 22959217). The 2026 Cochrane review (41641880) finds possible "
            "small to moderate benefits at six months in dementia and probably little or no effect in mild cognitive impairment. Reviews in tinnitus and intermittent claudication show little or no "
            "clinically significant benefit (36383762, 23744597). Findings concern standardized extracts, so this review earns no Evidence credit. A row declaring that standardization or "
            "a studied extract finishes at no credit, a row declaring crude powder or a ratio extract finishes as outside these studies, and an extract or plant name alone stays open. Interaction and bleeding warnings stay with their own owners."
        ),
        "notes": ("PMID 19017911 (GEM dementia prevention trial) has an unread erratum, JAMA 2008;300(23):2730, so it is retired from "
                  "qualifying_human_studies until that notice is read."),
        "studies": [
            dict(pmid="41641880", study_type="systematic_review_meta", sample_size=10613,
                 primary_endpoint="Global status, cognition, daily living and adverse events at six months",
                 outcome="82 studies: possible small to moderate benefits in dementia; probably little or no effect in mild cognitive impairment; uncertain in subjective complaints.",
                 effect_direction="mixed", quote="In people with dementia, there may be small to moderate benefits at six months"),
            dict(pmid="20040554", study_type="randomized_double_blind_placebo_controlled", sample_size=3069, dose="120 mg extract twice daily", duration="median 6.1 years",
                 primary_endpoint="Rates of cognitive decline on 3MSE, ADAS-Cog and domain scores",
                 outcome="Annual decline did not differ from placebo in any domain.",
                 effect_direction="null", quote="did not result in less cognitive decline in older adults"),
            dict(pmid="22959217", study_type="randomized_double_blind_placebo_controlled", sample_size=2854, dose="120 mg EGb 761 twice daily", duration="5 years",
                 primary_endpoint="Conversion to probable Alzheimer's disease",
                 outcome="HR 0.84 (95% CI 0.60-1.18; p=0.306) versus placebo.",
                 effect_direction="null", quote="did not reduce the risk of progression to Alzheimer's disease"),
            dict(pmid="36383762", study_type="systematic_review", sample_size=1915,
                 primary_endpoint="Tinnitus symptom severity and serious adverse effects",
                 outcome="12 studies: little to no effect on Tinnitus Handicap Inventory scores, with very low certainty; low-certainty little or no difference in bleeding or seizures.",
                 effect_direction="null", quote="Ginkgo biloba may have little to no effect"),
            dict(pmid="23744597", study_type="meta_analysis_rct", sample_size=739,
                 primary_endpoint="Absolute claudication distance",
                 outcome="14 trials; distance gain did not reach significance (P=0.06) and publication bias likely inflated it.",
                 effect_direction="null", quote="no evidence that Ginkgo biloba has a clinically significant benefit"),
        ],
    },
    "methionine": {
        "material_form": "L-methionine as an oral single amino acid supplement; not S-adenosylmethionine, selenomethionine, D-methionine or a methionine-loading test",
        "population_context": "Postmenopausal women with hot flashes, adults with AIDS-associated myelopathy, HIV-infected patients, and women with chronic urinary tract infection plus healthy controls",
        "effect_direction": "null",
        "applicability_status": "reviewed_null_evidence",
        "studied_dose_exposure": {"values": [1500, 2000, 4000, 6000], "unit": "mg", "basis": "daily_intake"},
        "applicability_decision": (
            "Placebo-controlled trials of oral L-methionine found no benefit for hot flashes (19407666) and no benefit in clinical measures "
            "in AIDS-associated myelopathy (15477550). One HIV trial reported only subgroup differences in CD4 decline (17006600). Supplementation "
            "raised plasma homocysteine (15870821, 19407666, 15477550). No trial establishes a general supplement benefit, so this review completes "
            "with no Evidence credit. Dietary essential-amino-acid adequacy is a separate question."
        ),
        "studies": [
            dict(pmid="19407666", study_type="randomized_controlled_trial", sample_size=51, dose="1 g twice daily, then 2 g twice daily", duration="12 weeks, then 8 weeks",
                 primary_endpoint="Percent change in hot flash composite score at week 12",
                 outcome="37.4% versus 33.4% decrease with placebo (P=0.60); fasting homocysteine rose.",
                 effect_direction="null", quote="there were no significant differences between the L-methionine and placebo groups"),
            dict(pmid="15477550", study_type="randomized_double_blind_placebo_controlled", sample_size=56, dose="6 g/day in two divided doses", duration="12 weeks",
                 primary_endpoint="Change in central conduction time in AIDS-associated myelopathy",
                 outcome="Nonsignificant change in conduction time (p=0.17), no effect on strength, spasticity or urinary function; serum homocysteine rose.",
                 effect_direction="null", quote="no benefit in any of the clinical measures"),
            dict(pmid="17006600", study_type="randomized_double_blind_placebo_controlled", sample_size=253,
                 primary_endpoint="Clinical and safety parameters in HIV infection",
                 outcome="After six months, differences were reported for women and for one trial center in CD4 decline, not a stated whole-trial benefit.",
                 effect_direction="mixed", quote="presented with a decreased level of decline in their CD4 counts"),
            dict(pmid="15870821", study_type="randomized_crossover", sample_size=20, dose="500 mg three times daily", duration="4 weeks",
                 primary_endpoint="Serum and urinary methionine, homocysteine and related amino acids",
                 outcome="Plasma homocysteine rose during L-methionine in patients and in healthy controls.",
                 effect_direction="negative", quote="Homocysteine plasma concentrations increased"),
        ],
    },
    "collagen": {
        "material_form": "Oral hydrolyzed collagen or collagen peptides; unspecified collagen, plain gelatin, undenatured type II collagen and co-active complexes such as BioCell are not settled by these studies",
        "population_context": "Mostly women aged 20 to 70 in skin trials; adults with knee osteoarthritis",
        "documented_review_scope": {"scope": "ingredient", "require_source_label_form": True,
            "required_form_terms": ['hydrolyzed', 'hydrolysate', 'collagen peptides', 'peptan', 'verisol', 'naticol'],
            "excluded_form_terms": ['biocell', 'undenatured', 'uc-ii', 'uc ii', 'nt2'],
            "supported_outcomes": ['skin', 'joint'],
            "studied_population": 'Mostly women aged 20 to 70 in skin trials; adults with knee osteoarthritis',
            "source_pmids": ['33742704', '37432180', '40324552', '42342959', '39212129'], "reviewed_at": "2026-11-03"},
        "effect_direction": None,
        "applicability_status": "applicability_unestablished",
        "applicability_decision": (
            "Pooled trials report favorable skin and knee-osteoarthritis measurements with high risk of bias, high heterogeneity or co-active formulations (33742704, 37432180, 42342959, 39212129). "
            "In one review those skin benefits were absent in non-pharmaceutical-funded and high-quality subgroups (40324552). This review does not change the clinician-signed limitation already on "
            "INGR_COLLAGEN_PEPTIDES. Findings are outcome-specific, so this review earns no Evidence credit. A row declaring hydrolyzed collagen or peptides finishes at no credit, a row declaring undenatured collagen or a co-active complex finishes as outside these studies, and collagen or gelatin alone stays open."
        ),
        "notes": ("PMID 31919527 (whey versus collagen peptides, muscle protein synthesis) has an unread corrigendum, PMID 33301004, so it is "
                  "retired from qualifying_human_studies until that notice is read."),
        "studies": [
            dict(pmid="33742704", study_type="meta_analysis_rct", sample_size=1125,
                 primary_endpoint="Skin wrinkles, hydration, elasticity and firmness",
                 outcome="19 studies: pooled results favored hydrolyzed collagen over placebo for hydration, elasticity and wrinkles.",
                 effect_direction="positive_weak", quote="favorable results of hydrolyzed collagen supplementation compared with placebo"),
            dict(pmid="37432180", study_type="meta_analysis_rct", sample_size=1721,
                 primary_endpoint="Skin hydration and elasticity",
                 outcome="26 RCTs: hydration and elasticity improved; authors identify several biases and call for larger trials.",
                 effect_direction="positive_weak", quote="The study also identified several biases in the included RCTs"),
            dict(pmid="40324552", study_type="meta_analysis_rct", sample_size=1474,
                 primary_endpoint="Skin hydration, elasticity and wrinkles by funding source and study quality",
                 outcome="23 RCTs: overall benefit, but no effect in non-pharmaceutical-funded or high-quality subgroups.",
                 effect_direction="mixed", quote="high-quality studies revealed no significant effect in all categories"),
            dict(pmid="42342959", study_type="systematic_review",
                 primary_endpoint="Skin outcomes, safety and quality of life",
                 outcome="25 RCTs without pooling: improvements in most trials, most at high risk of bias; authors call the evidence preliminary.",
                 effect_direction="positive_weak", quote="majority of included trials were rated as having a high risk of bias"),
            dict(pmid="39212129", study_type="meta_analysis_rct", sample_size=870,
                 primary_endpoint="Pain and function in knee osteoarthritis",
                 outcome="11 RCTs: improved function and pain with high heterogeneity (I2 75% and 88%).",
                 effect_direction="positive_weak", quote="oral collagen administration relieves OA symptoms"),
        ],
    },
}

# Read and retained, but not applied to the data. Moving fiber off its generated record ends the only
# gap on 3 probiotic products (59635, 241707, 276704), which then finish through a fiber row: the probiotic
# release branch reads the module result, not the row. Sean's November 3 decision keeps those holds and rejects
# a module-specific shortcut, so this waits until that branch reads rows like the generic one.
WITHHELD = {
    "fiber": {
        "material_form": "Named fibers studied in these reviews: psyllium, pectin, galactomannan and glucomannan (konjac). Fiber declared as a class or unspecified is not settled by these studies",
        "population_context": "Adults with chronic constipation, type 2 diabetes, dyslipidemia or elevated blood pressure; adults with overweight or obesity",
        "effect_direction": None,
        "applicability_status": "applicability_unestablished",
        "studied_dose_exposure": {},
        "applicability_decision": (
            "Pooled randomized trials favor supplemental fiber for chronic constipation, mainly psyllium and pectin above 10 g/day (35816465), and soluble fiber for glycemic control in type 2 diabetes, "
            "LDL cholesterol and blood pressure (33162192, 36796439, 37833676), with differences by fiber type including galactomannan (36811560). Glucomannan did not produce significant weight loss (24533610). "
            "A label that states only dietary, soluble or insoluble fiber does not identify the studied fiber or dose. Rows stay open and this review earns no Evidence credit."
        ),
        "studies": [
            dict(pmid="35816465", study_type="meta_analysis_rct", sample_size=1251,
                 primary_endpoint="Treatment response, stool output and symptoms in chronic constipation",
                 outcome="16 RCTs: response RR 1.48 (95% CI 1.17-1.88), with significant effects for psyllium and pectin and only at higher doses; more flatulence.",
                 effect_direction="positive_weak", quote="psyllium and pectin having significant effects"),
            dict(pmid="33162192", study_type="meta_analysis_rct", sample_size=1517,
                 primary_endpoint="Glycemic control in type 2 diabetes",
                 outcome="29 RCTs: HbA1c MD -0.63% and fasting glucose MD -0.89 mmol/L versus control diets.",
                 effect_direction="positive_weak", quote="supplemental soluble dietary fiber significantly reduced glycosylated hemoglobin"),
            dict(pmid="36796439", study_type="meta_analysis_rct", sample_size=14505,
                 primary_endpoint="Blood lipids per 5 g/day of soluble fiber",
                 outcome="181 RCTs: LDL cholesterol MD -8.28 mg/dL overall.",
                 effect_direction="positive_weak", quote="There was a significant reduction in LDL cholesterol"),
            dict(pmid="37833676", study_type="meta_analysis_rct", sample_size=5985,
                 primary_endpoint="Systolic and diastolic blood pressure",
                 outcome="83 studies: SBP WMD -1.36 mmHg and DBP WMD -0.72 mmHg.",
                 effect_direction="positive_weak", quote="Soluble fiber supplementation significantly decreased SBP"),
            dict(pmid="36811560", study_type="systematic_review_meta", sample_size=2685,
                 primary_endpoint="Glycemic and lipid outcomes by fiber type in type 2 diabetes",
                 outcome="46 RCTs of 16 fiber types: rankings differ by fiber and outcome; low or moderate certainty for most comparisons.",
                 effect_direction="mixed", quote="Most comparisons had a low or moderate certainty of evidence"),
            dict(pmid="24533610", study_type="meta_analysis_rct",
                 primary_endpoint="Body weight in overweight and obesity",
                 outcome="8 pooled RCTs: weight difference MD -0.22 kg (95% CI -0.62 to 0.19), not significant.",
                 effect_direction="null", quote="does not show that glucomannan intake generates statistically significant weight loss"),
        ],
    },
}
