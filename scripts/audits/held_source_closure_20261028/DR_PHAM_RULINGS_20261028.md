# Dr. Pham's signed rulings — October 28, 2026 (binding for this batch)

Source: the signed scientific review relayed by Sean on 2026-10-28 ("Dr Pham has reviewed and
approved the supplied scientific framework and the decisions within their stated scope"). Encode as
`clinical_review: {reviewer: "Dr. Pham", reviewed_at: "2026-10-28", scope:
"identity_dose_outcome_applicability"}`. Keep earlier signatures at their own dates. Do not ask again
for decisions already given.

## Governing principles
- Credit only for the outcome actually demonstrated, at its certainty, with the preparation and
  population limits the evidence supports. A label's wellness wording never widens it.
- A completed negative closes the research task; it never authorizes credit. A completed zero is
  "no applicable qualifying support", never "not studied".
- An unresolved source/integrity hold stays held even when no points are given. An optional stronger
  claim must not block a correctly completed limited assessment.
- No production weight, floor or band change in this batch (point-band calibration is a separate,
  measured batch). Do not change release gates or weaken validators.
- A no-credit decision uses the existing reference-only path (study_type/evidence_level "reference",
  approved non-eligible contexts with true directions).

## Date-restricted holds — what resolves each kind
| Kind | Resolves it |
|---|---|
| Freshness only | Documented current PubMed search with eligibility screening; confirm or revise the conclusion. |
| Old trial with a correction | Read the correction's actual content and its effect; a newer unrelated trial does not repair it. |
| Preparation/population mismatch | Exact source-to-label correspondence; recency cannot prove equivalence. |
| Incomplete extraction | Actual methods/intervention/comparator/population/regimen/outcomes, or a documented reporting limit. |
| Missing clinical acceptance | Her exact decision, never an inferred one. |

## Per-record rulings
| Record | Ruling | Encoding |
|---|---|---|
| INGR_CRANBERRY | Conditional moderate credit: recurrent-UTI prevention in women with prior UTIs. No treatment, no other populations. | Close with credit inside the existing applicability (required cranberry fruit forms). The record-level hold is resolved by this ruling. |
| INGR_POTASSIUM | Nutrition credit stays on the nutrition pathway. BP: larger response in hypertensives, exposure measured as urinary potassium, no capsule dose; no CV-prevention credit. | BP context approved, **not** credit-bearing (exposure is not a supplement dose). Reference-only for this clinical record; nutrition floor untouched. |
| INGR_GARLIC | Partial, preparation-specific BP credit; modest; no single effect size or dose for every extract. | Credit for BP in hypertensive adults, limited to the studied preparations (named in the source), with that limitation. |
| INGR_PLANT_STEROLS | Strong LDL evidence in studied preparations (food carriers, timing matter); a generic capsule does not inherit food-matrix evidence. | Reference-only for retail supplements unless the source shows capsule/tablet trials; if it does, credit only for that format. |
| INGR_ASHWAGANDHA | Credit for stress only with the exact studied standardized extract (Sensoril is root+leaf). No transfer to generic powder. | Generic record: completed no-credit (reference-only). KSM-66/Sensoril/Shoden brand records carry the credit. Remove KSM-66 contexts whose PMIDs are not in this record's references. |
| INGR_INOSITOL | At most limited, narrow PCOS credit (specific cycle/metabolic findings). No hormone-balance, ovarian or fertility claim; no preferred form/dose. | Limited credit for cycle regularity in women with PCOS; excluded claim terms for fertility. |
| INGR_RHODIOLA | Moderate conditional endurance credit; no energy, mood, anti-inflammatory or disease claims. | Close with credit for endurance only. |
| INGR_DIGESTIVE_ENZYMES | Limited credit for the exact studied formula only; enzyme names alone do not prove matching activity. | Credit only where the label is the exact studied formula. |
| INGR_CHONDROITIN_SULFATE | No routine knee/joint credit (2026 ACR recommends against routine use). | Completed no-credit, reference-only. |
| INGR_COLLAGEN_PEPTIDES | Withhold skin-aging credit. Knee-pain credit only after exact-source acceptance (optional future). | Complete as no-credit for skin (reference path); list knee pain as optional future qualification. |
| INGR_ECHINACEA | No general prevention/treatment credit; possible weak benefit for particular preparations remains open. | Reference-only path; reword any "uniformly negative" text to the qualified conclusion. Verify products. |
| INGR_CINNAMON_EXTRACT | Retain the integrity hold; no categorical zero across outcomes. | Held until the Khan 2003 expression of concern is read and its effect reconciled (agent work). |
| INGR_GABA | Very limited possible stress credit; little or no sleep credit. | Not "no evidence". The current scorer cannot express "very limited" without the band calibration, so: completed limited assessment, no points now, stress noted for the calibration batch. Sleep excluded. |
| INGR_OMEGA3 | Not in the new ruling; her earlier decision stands (date-restricted; reject preparation-wide CV/mood). | Credit only after a documented current search confirms the conclusion (freshness rule). |
| PRECLIN_PQQ | Keep the correction hold. The BDNF trial was a combined PQQ/hydrogen product, not isolated PQQ. | Held until the correction notice content for 34415830 is read and reconciled. No generic cognitive credit. |
| PRECLIN_CORDYCEPS | No generic stamina credit; not "all trials null" (Cs-4 exploratory signals; PeakO2 multi-mushroom; 2024 biomarker study). | Keep the approved non-scoring contexts for 20804368 and 27408987; extract 38501161's context (agent work); reconcile the old register entry. |
| BRAND_THERACURMIN | Keep narrow holds; possible limited credit needs the exact preparation and the outstanding acceptance. | Held. Name the exact remaining acceptance (memory 29246725). |
| INGR_LACTOFERRIN | No new affirmative credit until source data and applicability are reconciled (hemoglobin unit). | Held. |

## Second ruling set (relayed 2026-10-28)
Three separate outcomes must stay separate: a completed literature review, an approved scientific
conclusion, and a specific retail product earning points (product applicability).

| Record | Ruling | Encoding |
|---|---|---|
| BRAND_NIAGEN | No clinical-benefit credit for NAD+ elevation alone; keep it as verified biochemical target engagement. Clinical outcomes heterogeneous or null; never "no human research". | Completed no-credit, reference path, NAD+ finding kept with its true direction. |
| STRAIN_BB12 | Credit for infant colic in breastfed infants (exact BB-12 strain RCTs, n=80 and n=192); no transfer to adult digestion. | Credit scoped to infant colic and the exact strain; excluded adult digestive claims. |
| INGR_BEETROOT | Exercise credit requires a verified nitrate amount and a comparable preparation; "beetroot powder 500 mg" does not establish nitrate exposure. | Credit only where the label states nitrate (form/standardization term); otherwise not applicable. |
| INGR_GREEN_TEA | Implement the liver-safety warning from established evidence (concentrated extracts; EFSA ≥800 mg EGCG/day, no safe threshold); keep brewed tea vs extract distinct. | Already implemented: banned_recalled watchlist entry (safety_warning) and interaction rules on liver disease. No pending safety signature blocks the clinical record. |

## Third ruling set — corrections (relayed 2026-10-28)
| Record | Correction | Encoding |
|---|---|---|
| INGR_CHONDROITIN_SULFATE + INGR_GLUCOSAMINE_SULFATE | ACR (Sept 2026) recommends against both; VA/DoD (May 2026) finds evidence insufficient for or against. Never zero one while keeping broad credit for the other. | One shared standard for both, reconciled against both guidelines and exact-preparation evidence; identical rationale text in both patches. |
| INGR_WHEY_PROTEIN | Mixed-protein review can be rejected as whey-specific proof, but whey has its own evidence (2026 whey/soy meta-analysis: strength favorable, lean mass not significant; 2026 network meta-analysis: strength and fat-free mass positive) and a nutritional role. | Not "no applicable evidence". Assess whey-specific sources and scope any credit to the demonstrated outcome/population. |
| PRECLIN_BETAINE_ANHYDROUS | 2024 SR/MA: lower-body strength positive; other exercise outcomes null. | No generic credit; a categorical zero needs care. Assess outcome-scoped credit for lower-body strength. |
| INGR_LACTOFERRIN | 35276902 is free in PMC; body reports hemoglobin 11.80 g/L, abstract says g/dL. | Use full text and forest plot; record the abstract/body discrepancy; resolve the retracted included trial before accepting the pooled inference. |
| PRECLIN_HUPERZINE_A | 24086396 (PMC3781107) and 24639880 (PMC3930088) are free full texts; dementia populations with risk-of-bias limits. | Extract from full text and included-study tables, not abstracts. No transfer to healthy-adult focus claims. |
| INGR_SEA_BUCKTHORN | PMID 23472020 is a broiler-chicken experiment. | Never human clinical evidence; may stay as explicitly labeled animal research. |

## Fourth ruling set — boundaries for every credit decision (relayed 2026-10-28)
**Consistency rule:** the preparation-specific standard that rejects a mixed-protein review for whey
applies equally to BCAAs, berberine, omega-3 and every branded botanical study.
**Wording rule:** a no-credit claim is never "no relevant human research" when human research exists.
**Abstract rule:** an abstract can establish a narrow fact (nonhuman study, explicit null endpoint,
different combination). It cannot qualify a positive synthesis when the protocol, included trials,
corrections or risk of bias are unresolved and a full text is available.
**Retracted included trial:** identify the exact trial, whether and where it contributed to the pooled
estimate, and whether the remaining findings survive (selenium retraction notice 34745288 confirmed).
**No primary endpoint designated:** may contribute, but never invent a primary designation or give it
the certainty of a prespecified, multiplicity-controlled result.

| Record(s) | Boundary |
|---|---|
| INGR_COQ10 | Conditional credit: adjunctive heart-failure outcomes only. Exclude energy, statin-myopathy relief, CV prevention in healthy adults. |
| INGR_BRANCHED_CHAIN_AMINO_ACIDS | Limited credit: exercise-related muscle soreness only. Not strength, endurance or muscle growth. |
| INGR_BETA_ALANINE | High-intensity exercise under repeated-use (weeks) protocols; a single small pre-workout serving does not inherit it. |
| BRAND_KSM66, BRAND_SENSORIL, BRAND_SHODEN | Exact standardized material, studied stress outcome, applicable population. Sensoril is root+leaf; do not require root-only. |
| INGR_WHITE_KIDNEY_BEAN | Limited: the studied standardized Phaseolean extract and regimen (66 enrolled, 45 days, manufacturer-employed investigators). Brand alone is not maximum credit. |
| BRAND_TESTOFEN, BRAND_TESNOR, BRAND_RELORA, BRAND_NITROSIGINE | Limited, outcome-specific, exact branded formula. Hormone biomarkers, perceived stress and acute vascular measures are not fertility, long-term health or disease prevention. Relora: limited stress credit, outcome-hierarchy uncertainty kept (56 completers, 4 weeks; free full text). |
| PRECLIN_BERBERINE_GENERIC, INGR_BERBERINE_HCL, INGR_PANTETHINE, INGR_QUERCETIN | Tight claims; form, dose and population kept; glycemic/lipid changes are not prevention of clinical events (2026 ACC/AHA advises against relying on supplements for dyslipidemia). |
| INGR_GINGER | Studied nausea contexts only. |
| INGR_VITAMIN_C | Nutrition stays on the nutrition pathway; clinical credit only for cold severity within the review's scope (15 comparisons, 10 RCTs); no assumed primary-endpoint superiority. |
| INGR_CERAMIDES | Applicable skin outcomes only. |
| BRAND_UCII | Exact undenatured type-II collagen and knee outcome; distinguish ingredient mass from native collagen content. |
| PRECLIN_DGL | GutGard exact formula only (glabridin/glycyrrhizin specification); not ordinary licorice root. |
| BRAND_LJ100 | No credit from Physta trials (identity correction accepted). |
| INGR_GABA, PRECLIN_BETAINE_ANHYDROUS, INGR_GINSENG | Product claims may get zero, but wording must state the existing human findings: GABA preliminary mixed stress findings; betaine limited positive exercise results; ginseng favorable pooled results in some disease-related fatigue populations, no healthy-adult energy benefit. |
| BRAND_PUREWAY_C, INGR_ECHINACEA, PRECLIN_RESVERATROL, PRECLIN_HUPERZINE_A | No-credit decisions accepted (no outcome superiority; no general cold prevention; no longevity or healthy-adult cognition). Huperzine still re-extracted from full text. |
| INGR_CRANBERRY, INGR_RHODIOLA | Credit only where the product matches the studied source/preparation; not every retail formulation. Cranberry: FDA qualified-claim criteria are not generalized. |
| INGR_POTASSIUM | **Revised:** 40612568 is randomized potassium-supplementation trials with urinary potassium as the exposure indicator. That limits dose equivalence; it does not erase the BP findings in hypertensive populations. Evidence (BP, hypertensive adults) and Dose stay separate judgments. |
| INGR_OMEGA3 | Keep the date-restricted CV-claim hold until the evidence update is reconciled; nutritional EPA/DHA contribution is separate from clinical-event efficacy. |
| INGR_GREEN_TEA | Liver warnings already implemented through the safety owner. The clinical record keeps its specific missing acceptance as a governance dependency. |
| PRECLIN_CORDYCEPS | 38501161: 14 adults, muscle-tissue responses after exercise; not improved endurance, strength or meaningful recovery. |

## Fifth ruling set — scientific and release audit (relayed 2026-10-28)
Four things stay separate: evidence about the ingredient; applicability to the retail product; Dose
adequacy; assessment completion. A scientific zero, a product-specific zero and an unfinished review are
never interchangeable. Preferred public no-credit wording: "The reviewed research does not establish a
qualifying benefit for this product's assessed use."
**Mixed-preparation syntheses:** do not discard them wholesale; examine the applicable constituent trials
and independently relevant syntheses. A newer or larger study deserves consideration, not automatic
dominance (risk of bias, material specificity, independent trial families, endpoint).
**Null primary:** constrains certainty and claims; does not erase verified secondary findings. Whether
limited credit may rest on a verified secondary finding is an explicit scoring-policy decision (the
calibration batch); never promote a secondary to primary.

| Record | Ruling |
|---|---|
| INGR_OMEGA3 | Approve removing routine retail heart-event-prevention credit (VITAL, STRENGTH, 2026 ACC/AHA, Sept 2026 ACC statement). Preserve EPA/DHA nutritional credit (fish, krill, algae all count when EPA/DHA is disclosed), exact-formulation matching, and dose/population-specific AF safety (2026 MA of 35 RCTs: OR 1.43 mainly in high-CV-risk patients on >1,500 mg/day). Prescription EPA is never transferred. Mood: no blanket credit. EPA/DHA targets are a reviewed nutritional-contribution policy, not an RDA. |
| INGR_PLANT_STEROLS | Reopen. PMID 24144075 is a meta-analysis of 8 capsule/tablet trials (1–3 g/day, LDL about −0.31 mmol/L). Weigh with the 2026 ACC/AHA advice against relying on supplements. A limited preparation-specific LDL biomarker finding may be supportable; no CV-event credit. |
| STRAIN_BB12 / STRAIN_LGG (backed file) | Approve one scoring owner (strain registry); backed records research-only. BB-12 evidence inventory must check the September 2026 RCT PMID 42775119 (78 completers, full text) for strain identity, risk of bias and replication; no automatic extra points. Signature bookkeeping keeps the historical "not a clinician sign-off" note. |
| INGR_INOSITOL | At most low credit for verified PCOS cycle-regularity findings; never "normalizes cycles". No pregnancy, live birth, infertility or hormone-balance credit. The new outcome term must not match broad label phrases. |
| INGR_BEETROOT | Evidence may recognize a verified beetroot/nitrate performance relationship without a nitrate label; Dose stays unassessable against a nitrate benchmark when nitrate is unknown. Remove the nitrate applicability gate. Correct wording: female-specific 2025 MA shows power SMD 0.38; elite-athlete 2026 review shows some favorable results. |
| BRAND_MITOPURE, BRAND_SUNTHEANINE | Keep the hierarchy; record verified secondary findings (Mitopure strength; Suntheanine sleep subscales, 30 adults) as limited. Points from secondaries wait for the explicit calibration decision. |
| BRAND_SUNFIBER | Agree, with population/regimen/endpoint distinctions and PHGG label match. |
| INGR_BIOTIN | No beauty credit; nutrition stays; keep lab-test interference warnings. |
| INGR_MILK_THISTLE, INGR_ACETYL_L_CARNITINE, INGR_RED_YEAST_RICE, PRECLIN_CURCUMIN_GENERIC, PRECLIN_SULFORAPHANE, PRECLIN_CORDYCEPS, PRECLIN_ZINC_CARNOSINE | Qualified product-claim zeros accepted; wording keeps the existing human research (NAFLD trials; neuropathy trials; monacolin K variability; specific curcumin preparations; 2025 prediabetes RCT missed primary; Cs-4/PeakO2; polaprezinc adjunct to H. pylori therapy). |
| INGR_HMB | Restrictive conclusion supported by a March 2026 MA (13 RCTs, 561 older adults, no meaningful gains with resistance training); deduplicate the shared-placebo trial family; never "never shown any result". |
| INGR_FOLATE_MTHF | Remove 25943647 and 25733468 from any 5-MTHF intervention chain (background only). Folate nutrition separate. Folic acid, not 5-MTHF, is the form shown to prevent neural-tube defects; never transfer that outcome. |
| BRAND_ASTAREAL | Conditional, not automatically zero: verify the exact AstaReal material and independent support before brand credit. |
| INGR_CINNAMON_EXTRACT | Held. Provide study weights and an exclusion sensitivity analysis, or say why it cannot be done. |
| PRECLIN_PQQ | Held for the corrected table; never manufacture numbers. |
| INGR_INULIN | 34555168 full text is open (PMC8970830); use it. |
| INGR_WHEY_PROTEIN | 42625626 full text is open (PMC13490089; 36 RCTs, network MA). Use it; the 30–35 g/day plateau is not a Dose benchmark. |
| INGR_DIGESTIVE_ENZYMES | The trial names a fungal-fermentation multi-enzyme blend, not unequivocally Poolzyme Multi; exact-brand credit needs study-material identification and activities or manufacturer correspondence. |
| INGR_LACTOFERRIN, INGR_SELENIUM | Continue the retracted-trial analysis (PMC8838920; PMC10951571). Selenium findings concern thyroid labs in Hashimoto's. |
| INGR_VITAMIN_B6, INGR_ST_JOHNS_WORT, INGR_BLACK_COHOSH, INGR_CHLORELLA, BRAND_SETRIA, INGR_COLLAGEN_PEPTIDES, INGR_GREEN_TEA, STRAIN_SBOULARDII | Holds stand as stated; nutrition, interaction and liver-safety warnings are unaffected by an open efficacy hold. |
| Branded/preparation credits (CoQ10, KSM-66, Sensoril, Shoden, UC-II, Testofen, Tesnor, Phaseolean, etc.) | Accept as scoped. Run exact regression controls so a label's wellness word ("heart", "immune", "energy", "balance", "mobility") never makes an unrelated study applicable. |
