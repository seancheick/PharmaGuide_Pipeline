# Wave 2 owner packet — 50 identities searched, 25 deeply curated (2026-09-18)

**No production evidence write, no score movement, no catalog rebuild, no release.** Contexts are
authored as `source_verified_pending_clinical_review` and validated with `authoring=True`, which
refuses any other status. Approval is the owner's act.

## The expansion metric

Not the number of newly approvable records — the number of zeroes that now have an honest reason.

| measure | value |
|---|---:|
| identities searched | 50 |
| identities deeply curated (read source by source) | 25 |
| study contexts authored and validated | 6 |
| syntheses recorded as verified references (no dose stated) | 6 |
| context validation failures | 0 |
| Evidence=0 products in the wave's identities | 860 |
| Evidence=0 products this wave alone fully reviewed | 646 |
| ... with at least one identity reviewed by this wave | 33 |

Cumulative coverage, and the distinction between the three numbers, is owned by
`COVERAGE_MANIFEST.json` and pinned to a corpus snapshot - this packet does not restate it in its
own words. Snapshot: git `2341b4517f36`, 15109 scored products, 4231 at
Evidence 0.

| cumulative metric | products | share of the pinned 4231 |
|---|---:|---:|
| review state established (supported / null / held / no-qualifying / handoff) | **859** | **20.3%** |
| deep curated (read centrally, source by source) | 521 | 12.3% |
| score reachable by an APPROVED scoring record | 32 | - |

## Decision table

| identity | products | Ev=0 | contexts | direction | dose applicability | proposal | projected products | high risk |
|---|---:|---:|---:|---|---|---|---:|:--:|
| `common_bean_extract` | 22 | 21 | 1 | positive_weak | floor 1000 mg | APPROVED + APPLIED | 16 |  |
| `amla` | 52 | 19 | 1 | positive_weak | floor 500 mg | APPROVED + APPLIED | 18 |  |
| `devils_claw` | 25 | 16 | 0 | positive_weak | no dose policy | REVIEWED SUPPORTIVE, scoring HELD | 16 |  |
| `senna` | 15 | 15 | 0 | positive_strong | no dose policy | REVIEWED SUPPORTIVE, scoring HELD | 15 |  |
| `d_aspartic_acid` | 28 | 21 | 2 | null | 3-6 g/day | APPLIED as reviewed NULL (earns nothing) | 0 |  |
| `d_mannose` | 25 | 16 | 1 | null | 2 g/day | APPLIED as reviewed NULL (earns nothing) | 0 |  |
| `schisandra_berry` | 48 | 19 | 1 | positive_weak | floor 1000 mg | HOLD (blocked upstream, not by evidence) | 0 |  |
| `globe_artichoke` | 37 | 14 | 0 | positive_weak | no dose policy | HOLD (blocked upstream, not by evidence) | 0 |  |
| `horsetail` | 57 | 18 | 0 | positive_weak | - | HOLD + HANDOFF | 0 | yes |
| `hoodia_gordonii` | 18 | 17 | 0 | null | - | HOLD + HANDOFF | 0 | yes |
| `mucuna_pruriens` | 31 | 17 | 0 | not_an_efficacy_record | - | HOLD + HANDOFF | 0 | yes |
| `siberian_ginseng` | 25 | 14 | 0 | null | - | HOLD + HANDOFF | 0 | yes |
| `green_coffee_bean` | 76 | 21 | 0 | unresolved | - | HOLD (integrity) | 0 |  |
| `feverfew` | 21 | 20 | 0 | mixed | - | HOLD | 0 |  |
| `goji_berry` | 24 | 20 | 0 | positive_weak | - | HOLD | 0 |  |
| `theobromine` | 42 | 19 | 0 | mixed | - | HOLD | 0 |  |
| `oregano` | 20 | 18 | 0 | mixed | - | HOLD | 0 |  |
| `fennel` | 37 | 17 | 0 | positive_weak | - | HOLD | 0 |  |
| `cayenne_pepper` | 105 | 16 | 0 | mixed | - | HOLD | 0 |  |
| `tudca` | 16 | 16 | 0 | mixed | - | HOLD | 0 |  |
| `royal_jelly` | 17 | 15 | 0 | mixed | - | HOLD | 0 |  |
| `cat_s_claw` | 22 | 14 | 0 | mixed | - | HOLD | 0 |  |
| `holy_basil` | 37 | 14 | 0 | mixed | - | HOLD | 0 |  |
| `activated_charcoal` | 19 | 19 | 0 | not_applicable | - | HANDOFF | 0 | yes |
| `l_serine` | 26 | 16 | 0 | unresolved | - | REVIEWED_NO_QUALIFYING | 0 |  |

## Proposal rollup

| proposal | identities | Evidence=0 products |
|---|---:|---:|
| HOLD | 10 | 169 |
| HOLD + HANDOFF | 4 | 66 |
| APPROVED + APPLIED | 2 | 40 |
| REVIEWED SUPPORTIVE, scoring HELD | 2 | 31 |
| APPLIED as reviewed NULL (earns nothing) | 2 | 37 |
| HOLD (blocked upstream, not by evidence) | 2 | 33 |
| HOLD (integrity) | 1 | 21 |
| HANDOFF | 1 | 19 |
| REVIEWED_NO_QUALIFYING | 1 | 16 |

## Reasons

**`common_bean_extract`** — APPROVED + APPLIED

PMID 42066439 is ingredient-level (oral WKBE, 8 RCTs, n=543, weight -1.62 kg 95% CI -1.99 to -1.25). Catalog prints white kidney bean extract uniformly. Caveat: alpha-amylase inhibitor extracts are not standardised by inhibitor units, so label mg is not a potency guarantee, and the pooled effect is small. APPLIED 2026-09-18 as INGR_WHITE_KIDNEY_BEAN, positive_weak, 1,000 mg/day applicability floor; 16 of 22 products qualify, 16 of them at Evidence 0 today.

**`amla`** — APPROVED + APPLIED

PMID 37296402 (9 studies, EO 500-1500 mg/day): LDL-C -15.08 mg/dL, VLDL -5.43, TG -22.35, hsCRP -1.70, with the authors' own caution about heterogeneity. PMID 36934568 (5 RCTs) agrees. A 500 mg/day floor is proposed because that is the lowest dose the syntheses cover; the catalog median is 120 mg, so most products would NOT qualify - that is the point of the floor. The branded AMX-160 RCT (40262554) supports but does not define the record and carries an erratum; the amla syrup alopecia trial (37487962) is off-axis and excluded. APPLIED 2026-09-18 as INGR_AMLA, positive_weak, 500 mg/day floor; 19 of 52 products qualify. Limitations verified and recorded on the record after independent review: prediction intervals cross null for LDL-C (-48.29 to 18.13) and triglycerides (-73.47 to 28.77), I2 is 77% and 62%, only hs-CRP is homogeneous, the two syntheses overlap rather than replicate, and the endpoints are biomarkers not events. MEASURED CONSEQUENCE THE OWNER SHOULD SEE: three single-active products (Capros amla extract at exactly 500 mg) go from Evidence 0.0 to 13.2, because the existing primary-mass floor pays 14.0 x 0.85 when a mass-dominant active carries a systematic-review record. That is the scorer's existing behaviour, not a new rule, and it is the largest rise in the batch.

**`devils_claw`** — REVIEWED SUPPORTIVE, scoring HELD

Cochrane 2016 update (PMID 26630428, 14 RCTs, 2,050 participants): Harpagophytum procumbens seems to reduce pain more than placebo, evidence moderate quality at best. The 2007 Cochrane (17202897) is superseded and carries an erratum, so it is not cited. No dose policy is proposed: trials dose by harpagoside content and labels print extract mg, and inventing an equivalence is forbidden. Cranberry is the precedent for a record that deliberately carries no dose policy. APPLIED 2026-09-18 as INGR_DEVILS_CLAW at REFERENCE TIER - reviewed and supportive, scoring nothing. Independent review was right on both counts and both were verified live: the 14 RCTs / 2,050 participants are the Cochrane review's totals across SIX herbal medicines (corrected to 197, the largest devil's-claw-specific trial), and the studied exposure is 50-100 mg/day of harpagoside (PMID 10101629: 600/1200 mg of extract WS 1531 containing 50/100 mg harpagoside; PMID 12509627: Doloteffin with 60 mg). The one catalog label stating harpagoside delivers about 10.5 mg/day, five times below the lowest studied dose.

**`senna`** — REVIEWED SUPPORTIVE, scoring HELD

The strongest positive evidence in the wave, and the one that needs a human decision rather than a scoring one. Two independent evidence-based reviews both give senna GRADE A / good evidence as a first-line OTC laxative for chronic constipation, and a third found it superior to or as effective as other laxatives in long-term care. No dose policy is proposed: senna is dosed by sennoside content and all 15 catalog rows print 150 mg of senna leaf extract, so an equivalence would have to be invented. FLAGGED HIGH-RISK: senna is a stimulant laxative, the reviews themselves report abdominal pain, cramping, diarrhoea and nausea, and long-term use raises dependence and electrolyte concerns. Whether a stimulant laxative should earn positive Evidence credit in a consumer supplement score is a product-policy question for the owner, not an evidence question. APPLIED 2026-09-18 as INGR_SENNA at REFERENCE TIER - reviewed and supportive, scoring nothing. Independent review was right about the lineage and it was verified live: PMID 35943487 states it is 'a synopsis of an updated systematic review the authors conducted', so it is not a second independent grade-A confirmation; confidence lowered from high to medium. PMID 29885259 is independent but modest (7 RCTs, 444 long-term-care patients, authors cautioning on duration and quality). 0 of 15 catalog labels state sennosides, so nothing establishes the studied exposure. Stimulant-laxative adverse effects routed to the safety owner and NOT netted against the efficacy direction.

**`d_aspartic_acid`** — APPLIED as reviewed NULL (earns nothing)

Three single-ingredient RCTs, all null for testosterone: 6 g/day for 12 weeks in resistance-trained men (no change in TT or FT), 3 g/day crossover in climbers (no effect on T, cFT, LH), 6 g/day for 14 days in boxers (no effect). The one positive result (40248985) is a three-component combination (DAA + ubiquinol + zinc) in an infertility clinic population and may not lend its direction. Material and dose map cleanly; blocked only by the parked null decision. APPLIED 2026-09-18 as INGR_D_ASPARTIC_ACID, reviewed null, earning zero affirmative credit. A 3,000 mg/day floor applies for the same reason.

**`d_mannose`** — APPLIED as reviewed NULL (earns nothing)

PMID 38587819 (JAMA Intern Med 2024, n=598, placebo-controlled, 2 g/day, 6 months) null on its primary endpoint (51.0% vs 55.7%, RD -5%, 95% CI -13% to 3%); PMID 41004704 (2025, 6 RCTs, n=1,167) RR 0.57 (0.29-1.15). Older positive syntheses rest on open-label studies. Fully scorer-compatible; blocked only by the parked null-direction decision. APPLIED 2026-09-18 as INGR_D_MANNOSE, reviewed null, earning zero affirmative credit under the null = 0.0 decision. A 2,000 mg/day floor keeps products below the studied exposure from being characterised by a result at a dose they do not deliver.

**`schisandra_berry`** — HOLD (blocked upstream, not by evidence)

Two independent single-ingredient placebo-controlled RCTs at 1 g/day for 12 weeks: quadriceps strength up in postmenopausal women (n=45) and knee extensor strength up 10.2 Nm (95% CI 3.7-16.8) in older adults on a walking programme, with no change in muscle mass, inflammatory or antioxidant markers. A 1,000 mg/day floor is required - the catalog median is 175 mg. The Omija+soybean mixture trial (35956334) and the multi-herb adaptogen trial (41656269) are combination products and are excluded. studied_population is older adults and must travel with the record. BLOCKED UPSTREAM, not by evidence: all 48 catalog rows are classified recognized_non_scorable by the cleaner, so this record would reach ZERO products however good it is. Routed to the identity/cleaner owner. The evidence itself is ready to author the moment those rows become scorable actives.

**`globe_artichoke`** — HOLD (blocked upstream, not by evidence)

Three independent ingredient-level meta-analyses of Cynara scolymus agree on modest, consistent effects: total and LDL cholesterol and triglycerides down, insulin and HOMA-IR down, ALT and ALP down, with fasting glucose, HbA1c and HDL unaffected - the 2025 synthesis calls them 'modest but significant'. Endpoints are clinical biomarkers, not patient-important outcomes, and the largest effects concentrate in NAFLD and hypertensive subgroups, both of which must travel with the record as studied_population. No dose is stated in any synthesis, so no dose policy is proposed. BLOCKED UPSTREAM, not by evidence: all 37 catalog rows are classified recognized_non_scorable by the cleaner, so this record would reach ZERO products. Routed to the identity/cleaner owner. The evidence itself is ready to author the moment those rows become scorable actives.

**`horsetail`** — HOLD + HANDOFF

Two single-ingredient RCTs of a standardised dry extract at 900 mg/day: an acute diuretic effect equivalent to hydrochlorothiazide 25 mg in healthy volunteers, and a 3-month antihypertensive effect in stage-I hypertension (SBP -12.6, DBP -8.1 mmHg) comparable to HCTZ. Held for scoring on two grounds: the catalog median is 6.25 mg (horsetail is a trace silica source in hair and nail formulas, ~150x below the studied dose), and diuresis and blood-pressure lowering are drug-like claims in a clinical population. The HCTZ-equivalent effect is a safety and interaction signal for anyone on diuretics or antihypertensives and is routed to that owner.

**`hoodia_gordonii`** — HOLD + HANDOFF

The only oral RCT (PMID 21993434, 49 overweight women, 1,110 mg Hoodia gordonii purified extract twice daily = 2,220 mg/day for 15 days) found NO significant effect on ad libitum energy intake or body weight, and significant increases in blood pressure, pulse, heart rate, bilirubin and alkaline phosphatase with worse tolerability than placebo (nausea, emesis, skin sensation disturbance). Efficacy is held twice over: the direction is null, and the studied dose is about four times the 500 mg catalog median, so it would not apply even if null records were approvable. The vital-sign and liver-enzyme signal is the actionable part and is routed to the safety owner.

**`mucuna_pruriens`** — HOLD + HANDOFF

Every Parkinson's trial dose Mucuna as a LEVODOPA SUBSTITUTE at drug scale: 12.5-17.5 mg/kg of L-dopa equivalent, or 15-30 GRAMS of seed powder, compared head to head against dispersible levodopa/benserazide. PMID 41269916 runs MP powder as levodopa monotherapy for 12 months. This is not supplement-efficacy evidence and must not become an efficacy direction for a 500 mg capsule. The actionable finding is the opposite one: these products deliver unsupervised L-dopa, which interacts with carbidopa/levodopa, MAO inhibitors and antipsychotics. Routed to the safety and interaction owner. The seminal-parameter trial (18001713) is an uncontrolled-design infertility study and is not used.

**`siberian_ginseng`** — HOLD + HANDOFF

Three trials null on their primary endpoints: chronic fatigue ('overall efficacy was not demonstrated'), endurance cycling at 1,200 mg/day (no difference in steady-state substrate use or 10-km time), and a quality-of-life trial where the social-functioning gain at 4 weeks had attenuated by 8 weeks. The fourth is the reason for a handoff rather than a record: Eleutherococcus senticosus significantly RAISED 90-minute, 120-minute and AUC postprandial glucose. Held twice over - the direction is null and the null was measured at 1,200 mg/day against a 375 mg catalog median - and the glycemic signal is routed to the safety owner.

**`green_coffee_bean`** — HOLD (integrity)

All four selected sources are meta-analyses and the identity's own retrieval contains two retracted green-coffee-extract records (22291473, 25340633). No record may be authored until each synthesis's included-study list is checked against those PMIDs.

**`feverfew`** — HOLD

The AAN guideline's Level B names MIG-99, a specific CO2 extract, not feverfew generally; the Cochrane review of generic feverfew (5 trials, 343 patients) reports mixed results. The other two selected trials are combination designs (acupuncture arm; sublingual feverfew+ginger). Catalog rows are mostly unspecified feverfew, and the potency axis is parthenolide, not extract mg. Same material-scope shape as Permixon.

**`goji_berry`** — HOLD

Every synthesis is on Lycium barbarum polysaccharide-standardised preparations or berry/juice exposures; catalog rows are unspecified goji berry at 1,000 mg and extract mg does not state LBP content. A retracted LBP trial (29527188) sits in the same literature and must be checked against each meta-analysis's included list first.

**`theobromine`** — HOLD

The metabolic-syndrome trial (erratum-flagged) was null on body weight, BMI, blood pressure and fasting lipids and positive only on lipid RATIOS, with a low-calorie diet co-intervention in both arms - a null primary may not become a positive direction through secondary findings. The exercise evidence is a single 7-15 subject study inside a systematic review whose subject is theophylline.

**`oregano`** — HOLD

Three different exposures and three different questions: essential oils of Origanum dubium and O. vulgare hirtum in 34 athletes (HDL-C up over 14 days), oregano phenolics in fortified juice at 300-600 mg/day which was NULL on serum lipids and lipid peroxidation, and a network meta-analysis in which O. vulgare was best for chronic rhinosinusitis without polyps at LOW certainty. The cleanest placebo-controlled supplement exposure is the null one. Catalog forms split between oil of oregano and leaf extract, which are not the same exposure.

**`fennel`** — HOLD

The dysmenorrhea effect is real and replicated: PMID 34187122 pooled 7 placebo-controlled trials at SMD -0.632 (95% CI -0.827 to -0.436) with I2 = 0%. Held anyway, on exposure: none of the three meta-analyses states a single dose or preparation, the underlying trials mix seed powder, extract capsules and essential-oil drops, and every catalog row's form resolves to (none). Applying it would mean assuming a preparation the label does not state. Routed to the normalization owner as a form-resolution request, not recorded as absent evidence.

**`cayenne_pepper`** — HOLD

Four materials and four questions. The meta-analysis (PMID 33262398, 11 studies, n=609) reports LDL-C SMD -0.39 (95% CI -0.72 to -0.07) but its own PREDICTION interval is -1.28 to 0.50, and body weight is only marginal (P = 0.09). The one trial at a catalog-relevant supplement dose - 500 mg cayenne delivering 1.25 mg capsaicin - was explicitly NULL for thermogenesis and fat oxidation. The remaining two are a paprika carotenoid extract for bone turnover and an acute thermogenesis study with an erratum. Catalog median is 33 mg and 95 of 109 rows have no resolved form. Capsaicin content, not cayenne milligrams, is the potency axis.

**`tudca`** — HOLD

Every endpoint is a biomarker or a disease-specific outcome: insulin sensitivity by tracer/clamp in insulin-resistant subjects, flow-mediated dilation during a glucose challenge, ALSFRS-R slope in ALS (a serious clinical population, and the record carries an erratum), and TPN-associated cholestasis in neonates, which was NULL. There is no general-use patient-important outcome here, and the studied doses sit above the uniform 500 mg catalog amount.

**`royal_jelly`** — HOLD

The postmenopausal-symptom effect is real but thin: PMID 41401249 reports SMD 0.73 (95% CI 0.50-0.96, I2 = 0%) and states in the same breath that this rests on TWO studies and 312 participants at moderate quality, with no dose given. The identity's other outcome is null - PMID 31126561 found royal jelly did not improve fasting plasma glucose or HbA1c. Held on the thin base, the absent dose and the population restriction; a Wave 3 candidate if the owner wants it.

**`cat_s_claw`** — HOLD

Species and material do not line up with the catalog. The osteoarthritis trial used Uncaria GUIANENSIS and reported no significant reduction in pain at rest or at night or in knee circumference; the immune trial used C-Med-100, a branded U. tomentosa extract, with a vaccine-antibody biomarker endpoint; the third is a Phase II quality-of-life study in advanced cancer patients. All 25 catalog rows read cat's claw (unspecified).

**`holy_basil`** — HOLD

The glycemic evidence is a 1996 single-blind crossover in patients with type 2 diabetes plus a Cochrane review of Chinese herbal medicines that explicitly warns about low methodological quality, small samples and few trials. The cognition signal is one small RCT of a specific ethanolic O. sanctum leaf extract. The fourth selected record is a multi-herb adaptogen formula. Clinical population, old evidence, and a preparation the catalog does not state.

**`activated_charcoal`** — HANDOFF

Screening called this curate; central reading says otherwise. The single source is a meta-analysis of 64 controlled studies showing activated charcoal REDUCES DRUG EXPOSURE by 88% when given immediately and still significantly at 4 hours. That is decontamination pharmacology and a drug-interaction signal, not efficacy for the detox use these 19 products are sold for. Routed to the interaction owner.

**`l_serine`** — REVIEWED_NO_QUALIFYING

None of the three selected records is single-ingredient L-serine efficacy evidence for a general use: PMID 32520991 co-administers L-serine with EPA so the pain result cannot be attributed, PMID 41265180 is four n-of-1 trials in children with GRIN2B neurodevelopmental disorder, and PMID 37242260 is a personalisation survey across several sleep supplements rather than a placebo-controlled L-serine trial. Screening called this curate; central reading downgrades it.

