# Research receipts: first Evidence review batch

Live PubMed esearch/efetch on 2026-11-03. No clinician approved any of this and no record earns Evidence credit. Retained query, count, title, publication types, MeSH, retraction state and abstract hash for each paper are in `receipts.json`. Effect-label rule is at the top of `spec.py`.

`verify_literature_records.py` on the four applied records: 20 studies, 0 findings, 0 retractions. It screens PubMed bibliography and abstracts only, not full text, dose, outcome or clinician approval. `verify_all_citations_content.py` has no config for this file, so that verifier does not cover it; `verify_literature_records.py` is the owner here.

Turmeric, ginkgo and collagen carry `applicability_unestablished`, so their record-level `effect_direction` is null under the literature contract. The labels below are study-level findings. Fiber was read but is not in the data; see `report.md`.

## turmeric

- **Result:** status `applicability_unestablished`, record effect null. Study-level findings: positive_weak 3, mixed 2, negative 1
- **Scope read:** Curcuma longa (turmeric) extract, including curcumin preparations; curcuminoid content and bioavailability preparation vary. Whole root powder, ratio extracts and unspecified turmeric are not settled by these studies
- **Search:** `("Curcuma"[Mesh] OR turmeric[tiab] OR "Curcuma longa"[tiab]) AND (meta-analysis[pt] OR systematic review[pt]) AND humans[mh] || (turmeric[ti] OR "Curcuma longa"[ti]) AND (randomized controlled trial[pt] OR clinical trial[pt]) AND humans[mh]`
- **Titles screened:** 314

| PMID | Design | n | Endpoint | Finding | Abstract words |
|---|---|---|---|---|---|
| [33511486](https://pubmed.ncbi.nlm.nih.gov/33511486/) | meta_analysis_rct | 1810 | Knee pain and physical function in knee osteoarthritis | 16 RCTs up to 16 weeks: less knee pain (SMD -0.82) and better function (SMD -0.75) than placebo, similar to NSAIDs; heterogeneous, moderate risk of bias. | "Turmeric extracts significantly reduced knee pain" |
| [40731001](https://pubmed.ncbi.nlm.nih.gov/40731001/) | systematic_review_meta | not stated | WOMAC pain in knee osteoarthritis across turmeric preparations | 17 studies in a network meta-analysis: all preparations reduced WOMAC pain versus placebo; authors rate certainty low. | "the certainty of evidence remains low" |
| [32926799](https://pubmed.ncbi.nlm.nih.gov/32926799/) | randomized_double_blind_placebo_controlled | 70 | Knee pain (VAS) and effusion-synovitis volume on MRI | VAS pain improved by -9.1 mm versus placebo; effusion-synovitis volume did not change. | "did not change effusion-synovitis volume" |
| [34652861](https://pubmed.ncbi.nlm.nih.gov/34652861/) | randomized_double_blind_placebo_controlled | 132 | Severity of Dyspepsia Assessment in functional dyspepsia | Pain and non-pain scores fell more than placebo and did not differ from omeprazole. | "No significant difference was observed between curcumin and omeprazole groups" |
| [28443702](https://pubmed.ncbi.nlm.nih.gov/28443702/) | randomized_controlled_trial | 46 | Glycemic indices and leptin in non-alcoholic fatty liver disease | Glucose, insulin, HOMA-IR and leptin fell versus placebo; weight, BMI and liver enzymes did not change significantly. | "Changes in weight, BMI and liver enzymes were not significant" |
| [32656820](https://pubmed.ncbi.nlm.nih.gov/32656820/) | case_series_systematic_review | not stated | Acute liver injury reports after Curcuma longa supplements | 7 Tuscan cases and 23 published cases; the Tuscan cases involved high-bioavailability, high-dose curcumin or curcuminoid formulations. Case evidence, not an efficacy finding. | "confirmed the association between Curcuma longa and liver injury" |

## ginkgo

- **Result:** status `applicability_unestablished`, record effect null. Study-level findings: null 4, mixed 1
- **Scope read:** Ginkgo biloba leaf extract, mainly standardized preparations such as EGb 761; undeclared extracts and crude leaf powder are not settled by these studies
- **Search:** `("Ginkgo biloba"[Mesh] OR ginkgo[tiab]) AND (meta-analysis[pt] OR systematic review[pt]) AND humans[mh] || ("Ginkgo biloba"[Mesh] OR ginkgo[tiab]) AND (randomized controlled trial[pt]) AND (dementia[tiab] OR cognitive[tiab] OR memory[tiab]) AND humans[mh]`
- **Titles screened:** 341

- **Retired:** PMID 19017911 (GEM dementia prevention trial) has an unread erratum, JAMA 2008;300(23):2730, so it is retired from qualifying_human_studies until that notice is read.

| PMID | Design | n | Endpoint | Finding | Abstract words |
|---|---|---|---|---|---|
| [41641880](https://pubmed.ncbi.nlm.nih.gov/41641880/) | systematic_review_meta | 10613 | Global status, cognition, daily living and adverse events at six months | 82 studies: possible small to moderate benefits in dementia; probably little or no effect in mild cognitive impairment; uncertain in subjective complaints. | "In people with dementia, there may be small to moderate benefits at six months" |
| [20040554](https://pubmed.ncbi.nlm.nih.gov/20040554/) | randomized_double_blind_placebo_controlled | 3069 | Rates of cognitive decline on 3MSE, ADAS-Cog and domain scores | Annual decline did not differ from placebo in any domain. | "did not result in less cognitive decline in older adults" |
| [22959217](https://pubmed.ncbi.nlm.nih.gov/22959217/) | randomized_double_blind_placebo_controlled | 2854 | Conversion to probable Alzheimer's disease | HR 0.84 (95% CI 0.60-1.18; p=0.306) versus placebo. | "did not reduce the risk of progression to Alzheimer's disease" |
| [36383762](https://pubmed.ncbi.nlm.nih.gov/36383762/) | systematic_review | 1915 | Tinnitus symptom severity and serious adverse effects | 12 studies: little to no effect on Tinnitus Handicap Inventory scores, with very low certainty; low-certainty little or no difference in bleeding or seizures. | "Ginkgo biloba may have little to no effect" |
| [23744597](https://pubmed.ncbi.nlm.nih.gov/23744597/) | meta_analysis_rct | 739 | Absolute claudication distance | 14 trials; distance gain did not reach significance (P=0.06) and publication bias likely inflated it. | "no evidence that Ginkgo biloba has a clinically significant benefit" |

## methionine

- **Result:** null; status `reviewed_null_evidence`. Study-level findings: null 2, mixed 1, negative 1
- **Scope read:** L-methionine as an oral single amino acid supplement; not S-adenosylmethionine, selenomethionine, D-methionine or a methionine-loading test
- **Search:** `("L-methionine"[tiab] OR "methionine supplementation"[tiab] OR "oral methionine"[tiab] OR "Methionine/administration and dosage"[Mesh] OR "Methionine/therapeutic use"[Mesh]) AND (randomized controlled trial[pt] OR clinical trial[pt] OR meta-analysis[pt] OR systematic review[pt]) AND humans[mh]`
- **Titles screened:** 449

| PMID | Design | n | Endpoint | Finding | Abstract words |
|---|---|---|---|---|---|
| [19407666](https://pubmed.ncbi.nlm.nih.gov/19407666/) | randomized_controlled_trial | 51 | Percent change in hot flash composite score at week 12 | 37.4% versus 33.4% decrease with placebo (P=0.60); fasting homocysteine rose. | "there were no significant differences between the L-methionine and placebo groups" |
| [15477550](https://pubmed.ncbi.nlm.nih.gov/15477550/) | randomized_double_blind_placebo_controlled | 56 | Change in central conduction time in AIDS-associated myelopathy | Nonsignificant change in conduction time (p=0.17), no effect on strength, spasticity or urinary function; serum homocysteine rose. | "no benefit in any of the clinical measures" |
| [17006600](https://pubmed.ncbi.nlm.nih.gov/17006600/) | randomized_double_blind_placebo_controlled | 253 | Clinical and safety parameters in HIV infection | After six months, differences were reported for women and for one trial center in CD4 decline, not a stated whole-trial benefit. | "presented with a decreased level of decline in their CD4 counts" |
| [15870821](https://pubmed.ncbi.nlm.nih.gov/15870821/) | randomized_crossover | 20 | Serum and urinary methionine, homocysteine and related amino acids | Plasma homocysteine rose during L-methionine in patients and in healthy controls. | "Homocysteine plasma concentrations increased" |

## collagen

- **Result:** status `applicability_unestablished`, record effect null. Study-level findings: positive_weak 4, mixed 1
- **Scope read:** Oral hydrolyzed collagen or collagen peptides; unspecified collagen, plain gelatin, undenatured type II collagen and co-active complexes such as BioCell are not settled by these studies
- **Search:** `("collagen peptides"[tiab] OR "collagen hydrolysate"[tiab] OR "hydrolyzed collagen"[tiab] OR "hydrolysed collagen"[tiab] OR "collagen supplementation"[tiab] OR gelatin[ti]) AND (meta-analysis[pt] OR systematic review[pt]) AND humans[mh] || ("collagen peptides"[tiab] OR "collagen hydrolysate"[tiab] OR "hydrolyzed collagen"[tiab] OR "hydrolysed collagen"[tiab] OR "collagen supplementation"[tiab]) AND (oral[tiab] OR supplement*[tiab]) AND randomized controlled trial[pt] AND humans[mh]`
- **Titles screened:** 142

- **Retired:** PMID 31919527 (whey versus collagen peptides, muscle protein synthesis) has an unread corrigendum, PMID 33301004, so it is retired from qualifying_human_studies until that notice is read.

| PMID | Design | n | Endpoint | Finding | Abstract words |
|---|---|---|---|---|---|
| [33742704](https://pubmed.ncbi.nlm.nih.gov/33742704/) | meta_analysis_rct | 1125 | Skin wrinkles, hydration, elasticity and firmness | 19 studies: pooled results favored hydrolyzed collagen over placebo for hydration, elasticity and wrinkles. | "favorable results of hydrolyzed collagen supplementation compared with placebo" |
| [37432180](https://pubmed.ncbi.nlm.nih.gov/37432180/) | meta_analysis_rct | 1721 | Skin hydration and elasticity | 26 RCTs: hydration and elasticity improved; authors identify several biases and call for larger trials. | "The study also identified several biases in the included RCTs" |
| [40324552](https://pubmed.ncbi.nlm.nih.gov/40324552/) | meta_analysis_rct | 1474 | Skin hydration, elasticity and wrinkles by funding source and study quality | 23 RCTs: overall benefit, but no effect in non-pharmaceutical-funded or high-quality subgroups. | "high-quality studies revealed no significant effect in all categories" |
| [42342959](https://pubmed.ncbi.nlm.nih.gov/42342959/) | systematic_review | not stated | Skin outcomes, safety and quality of life | 25 RCTs without pooling: improvements in most trials, most at high risk of bias; authors call the evidence preliminary. | "majority of included trials were rated as having a high risk of bias" |
| [39212129](https://pubmed.ncbi.nlm.nih.gov/39212129/) | meta_analysis_rct | 870 | Pain and function in knee osteoarthritis | 11 RCTs: improved function and pain with high heterogeneity (I2 75% and 88%). | "oral collagen administration relieves OA symptoms" |

## fiber (read, not applied)

- **Result:** not applied to the data. Study-level findings: positive_weak 4, mixed 1, null 1
- **Scope read:** Named fibers studied in these reviews: psyllium, pectin, galactomannan and glucomannan (konjac). Fiber declared as a class or unspecified is not settled by these studies
- **Search:** `("Dietary Fiber"[Mesh] OR "fiber supplement*"[tiab] OR "fibre supplement*"[tiab] OR "fiber supplementation"[tiab] OR "fibre supplementation"[tiab]) AND (supplement*[tiab]) AND (meta-analysis[pt]) AND humans[mh]`
- **Titles screened:** 163

| PMID | Design | n | Endpoint | Finding | Abstract words |
|---|---|---|---|---|---|
| [35816465](https://pubmed.ncbi.nlm.nih.gov/35816465/) | meta_analysis_rct | 1251 | Treatment response, stool output and symptoms in chronic constipation | 16 RCTs: response RR 1.48 (95% CI 1.17-1.88), with significant effects for psyllium and pectin and only at higher doses; more flatulence. | "psyllium and pectin having significant effects" |
| [33162192](https://pubmed.ncbi.nlm.nih.gov/33162192/) | meta_analysis_rct | 1517 | Glycemic control in type 2 diabetes | 29 RCTs: HbA1c MD -0.63% and fasting glucose MD -0.89 mmol/L versus control diets. | "supplemental soluble dietary fiber significantly reduced glycosylated hemoglobin" |
| [36796439](https://pubmed.ncbi.nlm.nih.gov/36796439/) | meta_analysis_rct | 14505 | Blood lipids per 5 g/day of soluble fiber | 181 RCTs: LDL cholesterol MD -8.28 mg/dL overall. | "There was a significant reduction in LDL cholesterol" |
| [37833676](https://pubmed.ncbi.nlm.nih.gov/37833676/) | meta_analysis_rct | 5985 | Systolic and diastolic blood pressure | 83 studies: SBP WMD -1.36 mmHg and DBP WMD -0.72 mmHg. | "Soluble fiber supplementation significantly decreased SBP" |
| [36811560](https://pubmed.ncbi.nlm.nih.gov/36811560/) | systematic_review_meta | 2685 | Glycemic and lipid outcomes by fiber type in type 2 diabetes | 46 RCTs of 16 fiber types: rankings differ by fiber and outcome; low or moderate certainty for most comparisons. | "Most comparisons had a low or moderate certainty of evidence" |
| [24533610](https://pubmed.ncbi.nlm.nih.gov/24533610/) | meta_analysis_rct | not stated | Body weight in overweight and obesity | 8 pooled RCTs: weight difference MD -0.22 kg (95% CI -0.62 to 0.19), not significant. | "does not show that glucomannan intake generates statistically significant weight loss" |
