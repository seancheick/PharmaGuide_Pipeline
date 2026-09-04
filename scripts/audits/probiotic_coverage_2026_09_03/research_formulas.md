# Probiotic formula evidence audit — 2026-09-03

Scope: exact-formula evidence review for the bounded comparator set, with live primary-literature checks for the matched Seed DS-01, Garden of Life 100 Billion, and Nature's Way Fortify Optima 100 Billion formulas. This is research-only. It does not infer per-strain CFU from total CFU/AFU and does not treat absence of an exact-formula paper as negative efficacy evidence.

## Bottom line

| Formula | Label-grounded match status | Coverage classification | Why |
|---|---|---|---|
| Seed DS-01 Daily Synbiotic | Exact formula match established | `formula_specific_clinical` | Three live PubMed records describe the same 24-strain + 400 mg pomegranate + ViaCap product at 53.6 billion AFU/day. One is a symptom RCT; two are smaller mechanistic RCTs sharing protocol `NCT04171466`. |
| Garden of Life Dr. Formulated Probiotics 100 Billion | No exact-formula paper found | `strain_only_mixed_indirect` | The searched exact product name had no Europe PMC/PubMed hits. The closest clinical paper is a different 5-strain blend, not this labeled formula and not blinded/placebo-controlled. Several cited strain PMIDs are nonclinical or off-indication. |
| Nature's Way Fortify Ultra Potency Optima Probiotic 100 Billion | No exact-formula paper found | `strain_only_mixed_indirect` | The searched exact product name had no relevant PubMed formula paper. The nearest human GI paper is the same non-exact 5-strain open-label blend, and only partially overlaps this 13-strain label. Several matched PMIDs are nonclinical, off-indication, or null on the primary endpoint. |

## Label-grounded formula snapshots

Observed label provenance:

- Seed exact commercial label: `manual_labels/product_submissions/PG_SUB_35E0BD3374BF494B80FEABE87FC559E7.json`
- Comparator audit snapshots: `scripts/audits/probiotic_rubric_2026_09_03/comparators.json`

### Seed DS-01

Observed from local label + trial full texts:

- 24 named strains across four probiotic blends.
- Total daily potency: `53.6 billion AFU`.
- Prebiotic: `400 mg Indian pomegranate extract`.
- Delivery: capsule-in-capsule / ViaCap.
- Trial dosing nuance: the 6-week symptom RCT used `1 capsule daily for days 1-3, then 2 capsules daily`; the 91-day mechanistic papers used `2 capsules daily`.

### Garden of Life Dr. Formulated Probiotics 100 Billion

Observed from `comparators.json` plus the live DSLD/HelloPharmacist label snippet surfaced during search:

- Named matched strains in current audit snapshot: `B. lactis HN019`, `B. lactis Bl-04`, `L. paracasei Lpc-37`, `L. rhamnosus HN001`, `L. rhamnosus GG`, `L. acidophilus NCFM`.
- The fresh manifest-owned label replay for `326762` contains 18 named strains,
  including LS-33 and a separate Upcycled Postbiotic Blend. BB536 appeared in a
  live commercial snippet, not this audited label; do not transfer it across
  editions. Exact source inputs are recorded in the targeted replay.
- No exact per-strain clinical dose established from the searched literature for this full commercial formula.

### Nature's Way Fortify Optima 100 Billion

Observed from `comparators.json`:

- Total probiotic blend: `100 billion CFU`.
- Proprietary probiotic blend with nested `Bifidobacteria Blend` and `Lactobacilli Blend`.
- Current matched strains: `L. rhamnosus GG`, `L. acidophilus NCFM`, `L. paracasei Lpc-37`, `L. rhamnosus HN001`, `B. lactis Bl-04`, `B. lactis Bi-07`, `B. lactis HN019`.
- Additional named label strains in the local fingerprint include `B. longum infantis Bi-26`, `L. acidophilus La-14`, `L. brevis Lbr-35`, `L. casei Lc-11`, `L. gasseri Lg-36`, `L. plantarum Lp-115`, `L. salivarius Ls-33`, plus `chicory root fiber` and `gum acacia fiber`.
- No exact paper found for this full labeled 13-strain + prebiotic commercial formula.

## Exact-formula primary records inspected

### Seed DS-01 exact formula

1. PMID [41599868](https://pubmed.ncbi.nlm.nih.gov/41599868/)  
   Full text: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12845427/>

- Design: randomized, double-blind, placebo-controlled decentralized trial.
- Population: generally healthy adults with self-reported bloating/indigestion.
- Enrollment/completion: `350` baseline; `219` had evaluable week-6 data.
- Dose: DS-01 `53.6 billion AFU + 400 mg pomegranate extract` daily for 6 weeks; `1 capsule daily for 3 days`, then `2 capsules daily`.
- Outcomes: clinical symptom outcomes, not just surrogates. Reported improvements in GI quality-of-life, bloating/gas, abdominal discomfort, constipation symptoms, and regularity versus placebo at week 6.
- Funding/conflicts: funded by Seed Health; two authors employees/shareholders; advisors disclosed. Trial operations reported as independent via Radicle.
- Applicability read: strongest exact-formula evidence in this bounded set.
- Limitations: attrition was substantial; symptom outcomes are commercial-sponsor-funded single-trial evidence.

2. PMID [40944126](https://pubmed.ncbi.nlm.nih.gov/40944126/)  
   Full text: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12430871/>

- Design: randomized, placebo-controlled trial.
- Population: healthy adults.
- Enrollment/completion: `32` randomized, `27` completed.
- Dose: `2 capsules daily`, same DS-01 formula at `53.6 billion AFU + 400 mg pomegranate extract`, for `91 days`.
- Outcomes: mechanistic/surrogate, not symptom efficacy. Microbiome composition, urinary urolithin A, fecal butyrate, serum CRP, safety.
- Funding/conflicts: funded by Seed Health; employee/shareholder and advisor conflicts disclosed.
- Applicability read: confirms exact formula identity and biologic activity, but does not independently establish symptom benefit.

3. PMID [41750436](https://pubmed.ncbi.nlm.nih.gov/41750436/)  
   Full text: <https://pmc.ncbi.nlm.nih.gov/articles/PMC12937403/>

- Design: randomized, placebo-controlled proof-of-mechanism trial.
- Population: healthy adults undergoing standardized antibiotics.
- Enrollment/completion: `32` randomized, `21` completed. Local prior review remains correct that this shares protocol `NCT04171466` with PMID 40944126 and should not be summed as independent enrollment.
- Dose: same DS-01 formula for `91 days`; all participants also received `ciprofloxacin 500 mg BID + metronidazole 500 mg TID` for the first 7 days.
- Outcomes: mechanistic/surrogate. Microbiome diversity, acetate, butyrate, urolithin A, `p`-cresol sulfate, gut barrier integrity, safety.
- Funding/conflicts: funded by Seed Health; employee/shareholder and advisor conflicts disclosed.
- Applicability read: relevant for antibiotic-perturbed mechanistic recovery only. It is not direct evidence of preventing antibiotic-associated diarrhea.

Seed disposition: exact commercial formula has real human evidence, but only one publication directly measures patient GI symptoms. The other two are supportive mechanistic companion papers, not bonus-count independent replications.

## Non-exact human paper closest to Garden/Fortify strain overlap

### PMID [34028393](https://pubmed.ncbi.nlm.nih.gov/34028393/)
Full text: <https://pmc.ncbi.nlm.nih.gov/articles/PMC8989638/>

- Design: open-label, multicenter, single-arm study; no placebo group.
- Population: adults `18-75` with functional GI symptoms.
- Enrollment: `188` enrolled.
- Dose: once-daily 30-day capsule with exact disclosed per-strain doses: `Bl-04 2.5B CFU`, `Bi-07 2.5B CFU`, `HN019 2.0B CFU`, `NCFM 2.5B CFU`, `Lpc-37 2.5B CFU`.
- Outcomes: patient-reported improvement in overall GI well-being and symptom questionnaires; no blinded comparator.
- Funding: medical writing funded by Salix Pharmaceuticals.
- Applicability read: this is useful contextual human evidence for a 5-strain subset, especially for Fortify where all five named strains are present on label, but it is not exact evidence for either Garden or Fortify because:
  - Fortify contains many additional undisclosed-share strains and a different commercial formulation.
  - Garden includes a different broader formula plus prebiotic/postbiotic additions and does not map cleanly to this exact 5-strain capsule.
  - The study design is open-label and cannot separate placebo response from treatment effect.

## Matched strain records actually inspected

The audit question here is not "does some literature exist for a strain somewhere?" but "what does the currently matched PMID actually show?" Several currently matched records are weaker or less applicable than their support label suggests.

### B. lactis HN019 — PMID [39356506](https://pubmed.ncbi.nlm.nih.gov/39356506/)
Full text: <https://pmc.ncbi.nlm.nih.gov/articles/PMC11447574/>

- Design: randomized triple-blind placebo-controlled clinical trial.
- Population: adults `18-70` in Shanghai with functional constipation.
- Enrollment: `229` randomized.
- Dose: `7.0 x 10^9 CFU/day` at start, `4.69 x 10^9 CFU/day` at end, for `8 weeks`.
- Primary outcome: complete spontaneous bowel movements.
- Result: null on the primary endpoint versus placebo.
- Secondary signals: nominal differences in abdominal pain and bloating, but hierarchical testing stopped after the null primary result.
- Funding/conflicts: funded in full by Danisco China; sponsor involved in planning, statistical analysis, and interpretation.
- Read: this is a real human GI RCT and exact strain match, but the currently matched PMID is not a clean "high-strength positive" anchor.

### L. paracasei Lpc-37 — PMID [33385020](https://pubmed.ncbi.nlm.nih.gov/33385020/)
Full text: <https://pmc.ncbi.nlm.nih.gov/articles/PMC7770962/>

- Design: randomized, double-blind, placebo-controlled parallel trial.
- Population: healthy adults `18-45` under chronic stress stratification.
- Enrollment: `120` randomized; `113` per-protocol analyzed.
- Dose: `1.75 x 10^10 CFU/day` for `5 weeks`.
- Outcomes: stress physiology, perceived stress, anxiety-related measures; not GI symptom efficacy.
- Read: human and strain-specific, but off-indication for digestive claims and not exact-label-dose evidence.

### L. rhamnosus HN001 — PMID [28943228](https://pubmed.ncbi.nlm.nih.gov/28943228/)
Full text: <https://pmc.ncbi.nlm.nih.gov/articles/PMC5652021/>

- Design: randomized, double-blind, placebo-controlled trial.
- Population: pregnant women recruited at `14-16` weeks gestation in New Zealand.
- Enrollment/completion: `423` randomized; `380` completed the psychological outcomes questionnaire.
- Dose: `6 x 10^9 CFU/day` from enrollment through birth and to 6 months postpartum if breastfeeding.
- Outcomes: postpartum depression/anxiety symptom scores; primary parent trial outcome was infant eczema, not GI.
- Funding/conflicts: supported by New Zealand public/university funding plus Fonterra support; Fonterra provided capsules/randomization but reportedly no role in analysis or writing.
- Read: strong human RCT, but population and endpoint are far from adult digestive probiotic marketing.

### L. rhamnosus GG — PMID [26756877](https://pubmed.ncbi.nlm.nih.gov/26756877/)

- Record type: ESPGHAN Working Group recommendation/systematic review article, not a new primary efficacy trial.
- Population/endpoint: children; antibiotic-associated diarrhea prevention.
- Read: useful background that LGG has pediatric AAD evidence, but this PMID is not direct adult digestive-blend efficacy evidence for Garden or Fortify.

### L. acidophilus NCFM — PMID [24717228](https://pubmed.ncbi.nlm.nih.gov/24717228/)
Full text: <https://pmc.ncbi.nlm.nih.gov/articles/PMC4153766/>

- Model: monocolonized germ-free mice.
- Outcomes: metabolomics, bile acid and vitamin E acetate metabolism.
- Read: nonclinical only. This PMID cannot support human GI efficacy by itself.

### B. lactis Bl-04 — PMID [38665561](https://pubmed.ncbi.nlm.nih.gov/38665561/)
Full text: <https://pmc.ncbi.nlm.nih.gov/articles/PMC11043947/>

- Model: in vitro innate antiviral-response experiments.
- Outcomes: cytokine/transcriptomic antiviral-response signals; no human clinical endpoint.
- Read: nonclinical only. This PMID cannot support human digestive efficacy by itself.

### B. lactis Bi-07 — PMID [17408927](https://pubmed.ncbi.nlm.nih.gov/17408927/)

- Model: rifaximin-resistance genetic/proteomic characterization.
- Outcomes: antibiotic-resistance lab characterization, not patient outcomes.
- Read: nonclinical only. This PMID cannot support human GI efficacy by itself.

## Relevant related human study not currently used by the cited Bi-07/NCFM matches

### NCFM + Bi-07 combination — PMID [21436726](https://pubmed.ncbi.nlm.nih.gov/21436726/)
Full text: <https://pmc.ncbi.nlm.nih.gov/articles/PMC4372813/>

- Design: double-blind, placebo-controlled clinical trial.
- Population: `60` adults with nonconstipation functional bowel disorders.
- Dose: `2 x 10^11 CFU/day` combined NCFM + Bi-07 for `8 weeks`.
- Outcomes: abdominal bloating improved versus placebo; global relief endpoints were less prominent than the bloating signal.
- Read: this is clinically more relevant than PMIDs 24717228 and 17408927 for digestive applicability, but it still does not rescue exact-formula evidence for Garden or Fortify because:
  - it is a 2-strain combination, not either full commercial formula;
  - the tested dose is disclosed for the pair, not for the undisclosed per-strain shares inside the commercial blends.

## Formula-specific audit disposition

### Seed DS-01

- Classification: `formula_specific_clinical`
- Confidence statement: moderate.
- Rationale: exact formula, exact total AFU, exact prebiotic, and exact delivery system are all confirmed in live clinical publications. Only one paper directly measures patient GI symptoms; the others are mechanistic and overlapping-protocol support.

### Garden of Life Dr. Formulated Probiotics 100 Billion

- Classification: `strain_only_mixed_indirect`
- Search coverage: partial, bounded by the queries below; no numeric or categorical confidence in absence is inferred.
- Rationale:
  - no exact product-name hit was found in Europe PMC/PubMed searches on 2026-09-03;
  - closest overlapping human GI study is a different 5-strain open-label blend;
  - currently matched strain PMIDs include off-indication RCTs, a pediatric recommendation article, and nonclinical records.
- Important distinction: this is absence of found exact-formula evidence, not evidence the product is ineffective.

### Nature's Way Fortify Optima 100 Billion

- Classification: `strain_only_mixed_indirect`
- Search coverage: partial, bounded by the queries below; no numeric or categorical confidence in absence is inferred.
- Rationale:
  - no relevant exact-formula PubMed paper was found for the commercial product name;
  - the nearest human GI paper is the 5-strain open-label blend with exact disclosed doses, only partially overlapping the full 13-strain commercial label;
  - the strongest current exact-strain digestive record among matched PMIDs, HN019 `39356506`, is null on its primary endpoint;
  - several other current matched PMIDs are nonclinical or off-indication.
- Important distinction: this is absence of found exact-formula evidence, not evidence the product is ineffective.

## Query log

Live literature checks performed on `2026-09-03`.

### Europe PMC / PubMed exact-name and exact-combination searches

- `"Garden of Life" AND "Probiotics 100 Billion"` -> `0` Europe PMC hits.
- `"Fortify Optima" AND probiotic` -> `1` Europe PMC hit, but it was unrelated to this oral GI formula.
- `"DS-01" AND synbiotic` -> hits included PMIDs `41599868`, `41750436`, `40944126`.
- `"Bl-04" AND "Bi-07" AND "HN019" AND "NCFM" AND "Lpc-37"` -> hit list included PMID `34028393`.

### Primary records inspected directly

- PubMed: `41599868`, `40944126`, `41750436`, `34028393`, `39356506`, `33385020`, `28943228`, `26756877`, `24717228`, `38665561`, `17408927`, `21436726`
- PMC full texts used where available:
  - <https://pmc.ncbi.nlm.nih.gov/articles/PMC12845427/>
  - <https://pmc.ncbi.nlm.nih.gov/articles/PMC12430871/>
  - <https://pmc.ncbi.nlm.nih.gov/articles/PMC12937403/>
  - <https://pmc.ncbi.nlm.nih.gov/articles/PMC8989638/>
  - <https://pmc.ncbi.nlm.nih.gov/articles/PMC11447574/>
  - <https://pmc.ncbi.nlm.nih.gov/articles/PMC7770962/>
  - <https://pmc.ncbi.nlm.nih.gov/articles/PMC5652021/>
  - <https://pmc.ncbi.nlm.nih.gov/articles/PMC4153766/>
  - <https://pmc.ncbi.nlm.nih.gov/articles/PMC11043947/>
  - <https://pmc.ncbi.nlm.nih.gov/articles/PMC4372813/>

## Actionable takeaways for bounded coverage work

1. Seed can legitimately stay in an exact-formula bucket, but publication count should not be stacked as independent clinical proof.
2. Garden and Fortify should not be treated as exact-formula clinically established products from the searched evidence.
3. Fortify/Garden strain support should be downgraded conceptually from "all strong human digestive evidence" to a mixed set:
   - some direct human strain/context support,
   - some off-indication human support,
   - some nonclinical-only support,
   - and one null-primary-endpoint HN019 RCT.
4. Unknown per-strain shares inside the commercial blends remain unknown. None of the records above justify converting total-CFU labels into per-strain clinical-dose applicability.
