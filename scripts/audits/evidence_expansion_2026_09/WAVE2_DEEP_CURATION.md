# Wave 2 deep curation — all 25 curate identities read centrally (2026-09-18)

Every identity screening marked `curate` was re-read source by source against the live-verified
abstracts, with the catalog's measured label doses and resolved forms beside them. **Nothing was
authored into the registry, no score moved, no catalog rebuilt.** These are proposals.

## Outcome

| outcome | identities | Evidence=0 products |
|---|---:|---:|
| evidence ready, blocked upstream | 2 | 33 |
| hold + route to another owner | 4 | 66 |
| hold - integrity check outstanding | 1 | 21 |
| hold | 10 | 169 |
| not efficacy - route to another owner | 1 | 19 |
| no qualifying evidence | 1 | 16 |
| **total** | **25** | **432** |

The records proposed for approval would reach **0 products that sit at Evidence 0 today** (measured, `project_record_reach.py`). A further **33** are unreachable for a reason that has nothing to do with evidence — see below.

## Measured reach of each proposed record

| identity | dose floor | products carrying it | record would apply to | below floor / undosed | Evidence=0 reached |
|---|---:|---:|---:|---:|---:|
| `common_bean_extract` | 1000 mg | 22 | 16 | 6 | 16 |
| `amla` | 500 mg | 52 | 19 | 33 | 18 |
| `devils_claw` | none (cranberry precedent) | 25 | 25 | 0 | 16 |
| `senna` | none (cranberry precedent) | 15 | 15 | 0 | 15 |
| `schisandra_berry` | 1000 mg | 0 | 0 | 0 | 0 |
| `globe_artichoke` | none (cranberry precedent) | 0 | 0 | 0 | 0 |

## evidence ready, blocked upstream

**`schisandra_berry`** — 48 products, 19 at Evidence 0 — direction **positive_weak**; `rct_multiple`; PMIDs 32260466, 33710261; label median 175 mg; studied 1,000 mg/day Schisandra chinensis extract

Two independent single-ingredient placebo-controlled RCTs at 1 g/day for 12 weeks: quadriceps strength up in postmenopausal women (n=45) and knee extensor strength up 10.2 Nm (95% CI 3.7-16.8) in older adults on a walking programme, with no change in muscle mass, inflammatory or antioxidant markers. A 1,000 mg/day floor is required - the catalog median is 175 mg. The Omija+soybean mixture trial (35956334) and the multi-herb adaptogen trial (41656269) are combination products and are excluded. studied_population is older adults and must travel with the record. BLOCKED UPSTREAM, not by evidence: all 48 catalog rows are classified recognized_non_scorable by the cleaner, so this record would reach ZERO products however good it is. Routed to the identity/cleaner owner. The evidence itself is ready to author the moment those rows become scorable actives.

**`globe_artichoke`** — 37 products, 14 at Evidence 0 — direction **positive_weak**; `systematic_review_meta`; PMIDs 41270328, 34383355, 33197674; label median 125 mg; studied not stated in the syntheses; no dose policy proposed

Three independent ingredient-level meta-analyses of Cynara scolymus agree on modest, consistent effects: total and LDL cholesterol and triglycerides down, insulin and HOMA-IR down, ALT and ALP down, with fasting glucose, HbA1c and HDL unaffected - the 2025 synthesis calls them 'modest but significant'. Endpoints are clinical biomarkers, not patient-important outcomes, and the largest effects concentrate in NAFLD and hypertensive subgroups, both of which must travel with the record as studied_population. No dose is stated in any synthesis, so no dose policy is proposed. BLOCKED UPSTREAM, not by evidence: all 37 catalog rows are classified recognized_non_scorable by the cleaner, so this record would reach ZERO products. Routed to the identity/cleaner owner. The evidence itself is ready to author the moment those rows become scorable actives.

## hold + route to another owner

**`horsetail`** — 57 products, 18 at Evidence 0 — direction **positive_weak**; PMIDs 24723963, 35168030; label median 6.25 mg

Two single-ingredient RCTs of a standardised dry extract at 900 mg/day: an acute diuretic effect equivalent to hydrochlorothiazide 25 mg in healthy volunteers, and a 3-month antihypertensive effect in stage-I hypertension (SBP -12.6, DBP -8.1 mmHg) comparable to HCTZ. Held for scoring on two grounds: the catalog median is 6.25 mg (horsetail is a trace silica source in hair and nail formulas, ~150x below the studied dose), and diuresis and blood-pressure lowering are drug-like claims in a clinical population. The HCTZ-equivalent effect is a safety and interaction signal for anyone on diuretics or antihypertensives and is routed to that owner.

**`hoodia_gordonii`** — 18 products, 17 at Evidence 0 — direction **null**; PMIDs 21993434; label median 500 mg

The only oral RCT (PMID 21993434, 49 overweight women, 1,110 mg Hoodia gordonii purified extract twice daily = 2,220 mg/day for 15 days) found NO significant effect on ad libitum energy intake or body weight, and significant increases in blood pressure, pulse, heart rate, bilirubin and alkaline phosphatase with worse tolerability than placebo (nausea, emesis, skin sensation disturbance). Efficacy is held twice over: the direction is null, and the studied dose is about four times the 500 mg catalog median, so it would not apply even if null records were approvable. The vital-sign and liver-enzyme signal is the actionable part and is routed to the safety owner.

**`mucuna_pruriens`** — 31 products, 17 at Evidence 0 — direction **not_an_efficacy_record**; PMIDs 28679598, 41269916, 15548480; label median 500 mg

Every Parkinson's trial dose Mucuna as a LEVODOPA SUBSTITUTE at drug scale: 12.5-17.5 mg/kg of L-dopa equivalent, or 15-30 GRAMS of seed powder, compared head to head against dispersible levodopa/benserazide. PMID 41269916 runs MP powder as levodopa monotherapy for 12 months. This is not supplement-efficacy evidence and must not become an efficacy direction for a 500 mg capsule. The actionable finding is the opposite one: these products deliver unsupervised L-dopa, which interacts with carbidopa/levodopa, MAO inhibitors and antipsychotics. Routed to the safety and interaction owner. The seminal-parameter trial (18001713) is an uncontrolled-design infertility study and is not used.

**`siberian_ginseng`** — 25 products, 14 at Evidence 0 — direction **null**; PMIDs 14971626, 11099371, 15207399, 15190050; label median 375 mg

Three trials null on their primary endpoints: chronic fatigue ('overall efficacy was not demonstrated'), endurance cycling at 1,200 mg/day (no difference in steady-state substrate use or 10-km time), and a quality-of-life trial where the social-functioning gain at 4 weeks had attenuated by 8 weeks. The fourth is the reason for a handoff rather than a record: Eleutherococcus senticosus significantly RAISED 90-minute, 120-minute and AUC postprandial glucose. Held twice over - the direction is null and the null was measured at 1,200 mg/day against a 375 mg catalog median - and the glycemic signal is routed to the safety owner.

## hold - integrity check outstanding

**`green_coffee_bean`** — 76 products, 21 at Evidence 0 — direction **unresolved**

All four selected sources are meta-analyses and the identity's own retrieval contains two retracted green-coffee-extract records (22291473, 25340633). No record may be authored until each synthesis's included-study list is checked against those PMIDs.

## hold

**`feverfew`** — 21 products, 20 at Evidence 0 — direction **mixed**; PMIDs 22529203, 14973986; label median 300 mg

The AAN guideline's Level B names MIG-99, a specific CO2 extract, not feverfew generally; the Cochrane review of generic feverfew (5 trials, 343 patients) reports mixed results. The other two selected trials are combination designs (acupuncture arm; sublingual feverfew+ginger). Catalog rows are mostly unspecified feverfew, and the potency axis is parthenolide, not extract mg. Same material-scope shape as Permixon.

**`goji_berry`** — 24 products, 20 at Evidence 0 — direction **positive_weak**; PMIDs 37773857, 28401234; label median 1000 mg

Every synthesis is on Lycium barbarum polysaccharide-standardised preparations or berry/juice exposures; catalog rows are unspecified goji berry at 1,000 mg and extract mg does not state LBP content. A retracted LBP trial (29527188) sits in the same literature and must be checked against each meta-analysis's included list first.

**`theobromine`** — 42 products, 19 at Evidence 0 — direction **mixed**; PMIDs 37615657, 33188564; label median 200 mg

The metabolic-syndrome trial (erratum-flagged) was null on body weight, BMI, blood pressure and fasting lipids and positive only on lipid RATIOS, with a low-calorie diet co-intervention in both arms - a null primary may not become a positive direction through secondary findings. The exercise evidence is a single 7-15 subject study inside a systematic review whose subject is theophylline.

**`oregano`** — 20 products, 18 at Evidence 0 — direction **mixed**; PMIDs 16881679, 34496170, 36609950; label median 150 mg

Three different exposures and three different questions: essential oils of Origanum dubium and O. vulgare hirtum in 34 athletes (HDL-C up over 14 days), oregano phenolics in fortified juice at 300-600 mg/day which was NULL on serum lipids and lipid peroxidation, and a network meta-analysis in which O. vulgare was best for chronic rhinosinusitis without polyps at LOW certainty. The cleanest placebo-controlled supplement exposure is the null one. Catalog forms split between oil of oregano and leaf extract, which are not the same exposure.

**`fennel`** — 37 products, 17 at Evidence 0 — direction **positive_weak**; PMIDs 34187122, 33182553, 33725577; label median 237 mg

The dysmenorrhea effect is real and replicated: PMID 34187122 pooled 7 placebo-controlled trials at SMD -0.632 (95% CI -0.827 to -0.436) with I2 = 0%. Held anyway, on exposure: none of the three meta-analyses states a single dose or preparation, the underlying trials mix seed powder, extract capsules and essential-oil drops, and every catalog row's form resolves to (none). Applying it would mean assuming a preparation the label does not state. Routed to the normalization owner as a form-resolution request, not recorded as absent evidence.

**`cayenne_pepper`** — 105 products, 16 at Evidence 0 — direction **mixed**; PMIDs 33262398, 24267043; label median 33.4 mg

Four materials and four questions. The meta-analysis (PMID 33262398, 11 studies, n=609) reports LDL-C SMD -0.39 (95% CI -0.72 to -0.07) but its own PREDICTION interval is -1.28 to 0.50, and body weight is only marginal (P = 0.09). The one trial at a catalog-relevant supplement dose - 500 mg cayenne delivering 1.25 mg capsaicin - was explicitly NULL for thermogenesis and fat oxidation. The remaining two are a paprika carotenoid extract for bone turnover and an acute thermogenesis study with an erratum. Catalog median is 33 mg and 95 of 109 rows have no resolved form. Capsaicin content, not cayenne milligrams, is the potency axis.

**`tudca`** — 16 products, 16 at Evidence 0 — direction **mixed**; PMIDs 20522594, 27503949, 25664595, 12183720; label median 500 mg

Every endpoint is a biomarker or a disease-specific outcome: insulin sensitivity by tracer/clamp in insulin-resistant subjects, flow-mediated dilation during a glucose challenge, ALSFRS-R slope in ALS (a serious clinical population, and the record carries an erratum), and TPN-associated cholestasis in neonates, which was NULL. There is no general-use patient-important outcome here, and the studied doses sit above the uniform 500 mg catalog amount.

**`royal_jelly`** — 17 products, 15 at Evidence 0 — direction **mixed**; PMIDs 41401249, 31126561; label median 1000 mg

The postmenopausal-symptom effect is real but thin: PMID 41401249 reports SMD 0.73 (95% CI 0.50-0.96, I2 = 0%) and states in the same breath that this rests on TWO studies and 312 participants at moderate quality, with no dose given. The identity's other outcome is null - PMID 31126561 found royal jelly did not improve fasting plasma glucose or HbA1c. Held on the thin base, the absent dose and the population restriction; a Wave 3 candidate if the owner wants it.

**`cat_s_claw`** — 22 products, 14 at Evidence 0 — direction **mixed**; PMIDs 11603848, 11515716, 25495394; label median 240 mg

Species and material do not line up with the catalog. The osteoarthritis trial used Uncaria GUIANENSIS and reported no significant reduction in pain at rest or at night or in knee circumference; the immune trial used C-Med-100, a branded U. tomentosa extract, with a vaccine-antibody biomarker endpoint; the third is a Phase II quality-of-life study in advanced cancer patients. All 25 catalog rows read cat's claw (unspecified).

**`holy_basil`** — 37 products, 14 at Evidence 0 — direction **mixed**; PMIDs 8880292, 26571987; label median 450 mg

The glycemic evidence is a 1996 single-blind crossover in patients with type 2 diabetes plus a Cochrane review of Chinese herbal medicines that explicitly warns about low methodological quality, small samples and few trials. The cognition signal is one small RCT of a specific ethanolic O. sanctum leaf extract. The fourth selected record is a multi-herb adaptogen formula. Clinical population, old evidence, and a preparation the catalog does not state.

## not efficacy - route to another owner

**`activated_charcoal`** — 19 products, 19 at Evidence 0 — direction **not_applicable**; PMIDs 19194372; label median 560 mg

Screening called this curate; central reading says otherwise. The single source is a meta-analysis of 64 controlled studies showing activated charcoal REDUCES DRUG EXPOSURE by 88% when given immediately and still significantly at 4 hours. That is decontamination pharmacology and a drug-interaction signal, not efficacy for the detox use these 19 products are sold for. Routed to the interaction owner.

## no qualifying evidence

**`l_serine`** — 26 products, 16 at Evidence 0 — direction **unresolved**; label median 1650 mg

None of the three selected records is single-ingredient L-serine efficacy evidence for a general use: PMID 32520991 co-administers L-serine with EPA so the pain result cannot be attributed, PMID 41265180 is four n-of-1 trials in children with GRIN2B neurodevelopmental disorder, and PMID 37242260 is a personalisation survey across several sleep supplements rather than a placebo-controlled L-serine trial. Screening called this curate; central reading downgrades it.

