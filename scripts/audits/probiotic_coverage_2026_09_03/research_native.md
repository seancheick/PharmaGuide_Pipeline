# Probiotic native-evidence coverage note

Date reviewed: 2026-09-03
Scope: bounded primary-literature check for the three reviewed products only. This is not an exhaustive search claim.

## Label identity snapshot

### Culturelle Digestive Daily Probiotic

- Official product page: https://culturelle.com/products/digestive-daily-probiotic
- Current live page states the product contains clinically studied *Lactobacillus rhamnosus* GG and "deliver[s] the clinically proven effective amount of 10 billion CFUs" and claims reduction of occasional gas, bloating, and diarrhea plus "travel-associated digestive issues."
- Native strain on the audited label: LGG, 10 billion CFU/day.
- Important scope issue: the live commercial claim is broad digestive support, but the currently cited native evidence in the repo is largely antibiotic-associated diarrhea (AAD), especially pediatric AAD. That is not enough to confer blanket broad digestive efficacy.

### Ritual Synbiotic+

- Official product page: https://ritual.com/products/synbiotic-plus-for-gut-health
- Live page states "Probiotics LGG and BB-12 and prebiotics PreforPro help soothe occasional gas, bloating, and abdominal discomfort."
- Live label exposure is a combined probiotic blend of 40 mg / 11 billion CFU total for LGG + BB-12, plus PreforPro 15 mg and tributyrin 300 mg.
- Important scope issue: the label does not disclose per-strain CFU for LGG vs BB-12, so even when primary human evidence exists for either strain, dose transfer to the exact label is unresolved.

### Jarrow Saccharomyces Boulardii + MOS 5 Billion CFU

- Official product page: https://jarrow.com/products/saccharomyces-boulardii-mos-5-billion-cfu-delayed-release-veggie-caps
- Live page describes a probiotic yeast with MOS prebiotic, "5 billion CFU," support for intestinal health/microflora balance, and language about people with greater need for intestinal support such as travelers.
- Native label exposure: *Saccharomyces boulardii* 5 billion CFU/day plus MOS. No strain code is exposed on the public product page reviewed here.
- Important scope issue: much of the stronger modern literature is strain-specific to CNCM I-745 or antibiotic-context use. The audited Jarrow label page reviewed here does not expose CNCM I-745 identity.

## Verified PMID checks

- PMID 26756877 verified: https://pubmed.ncbi.nlm.nih.gov/26756877/
  - Secondary pediatric AAD guideline/review; explicitly strain-specific but not a primary dose-window source for broad digestive claims.
- PMID 33295643 verified: https://pubmed.ncbi.nlm.nih.gov/33295643/
  - Secondary acute infectious diarrhea review; not suitable as native-dose proof for these labels.
- PMID 38271203 could not be verified on 2026-09-03.
  - Europe PMC query `EXT_ID:38271203 AND SRC:MED` returned no record.
  - PubMed should not be treated as verified for BB-12 until replaced with a real PMID.

## Primary human evidence worth keeping distinct

### LGG: meaningful primary records

1. PMID 17229242 — https://pubmed.ncbi.nlm.nih.gov/17229242/
   - Title: A randomized double-blind placebo-controlled trial of Lactobacillus GG for abdominal pain disorders in children.
   - Primary-paper dose extracted from the paper PDF: LGG `3 x 10^9 CFU` twice daily orally for `4 weeks`.
   - Population: 104 children age 6-16 with functional dyspepsia, IBS, or functional abdominal pain.
   - Outcome: overall treatment success improved vs placebo; benefit concentrated in pediatric IBS subgroup; no benefit for FD or generic FAP subgroups.
   - Why it matters: this is real strain-specific human evidence for pediatric abdominal-pain disorders, not adult general digestive support, not gas/bloating broad-label proof, and not AAD.
   - Transfer limit: pediatric functional GI disorder context only. Do not use as adult broad-digestive or diarrhea/travel proof.

2. PMID 21078735 — https://pubmed.ncbi.nlm.nih.gov/21078735/
   - Title: A randomized controlled trial of Lactobacillus GG in children with functional abdominal pain.
   - Population: 141 children with IBS or functional pain.
   - Outcome: reduced abdominal pain frequency and severity vs placebo, mainly in children with IBS; benefit persisted in follow-up.
   - Dose: not extracted from the PubMed abstract during this bounded pass, so do not use this paper alone to create a native dose window from this note.
   - Transfer limit: pediatric recurrent abdominal pain/IBS context only.

3. Existing secondary AAD anchor remains indication-limited, not blanket:
   - PMID 26365389 — https://pubmed.ncbi.nlm.nih.gov/26365389/
   - Meta-analysis found LGG helpful for AAD overall, but adult subgroup was not significant except a subset receiving *H. pylori* eradication therapy.
   - This strengthens the point that "LGG has evidence" is too coarse; indication and co-therapy matter.

### BB-12: meaningful primary records

1. PMID 26382580 — https://pubmed.ncbi.nlm.nih.gov/26382580/
   - Title: Effect of the probiotic strain *Bifidobacterium animalis* subsp. *lactis*, BB-12, on defecation frequency in healthy subjects with low defecation frequency and abdominal discomfort: a randomised, double-blind, placebo-controlled, parallel-group trial.
   - Full-text source: https://pmc.ncbi.nlm.nih.gov/articles/PMC4657032/
   - Dose: `1 billion CFU/day` or `10 billion CFU/day` once daily for `4 weeks`.
   - Population: 1248 healthy adults with low defecation frequency and abdominal discomfort.
   - Outcome: original stool-frequency responder endpoint P=.071 and global abdominal discomfort endpoint not significant. A revised responder criterion and average stool frequency were favorable.
   - Why it matters: a verified replacement candidate with mixed results, not an unconditional positive trial. It requires clinician review before a production PMID swap.
   - Transfer limit: adults with low stool frequency. Not proof of broad digestive comfort, not proof of immune claims, and not directly transferable to Ritual because the label does not disclose BB-12's per-strain CFU.

2. PMID 25588782 — https://pubmed.ncbi.nlm.nih.gov/25588782/
   - Title: Can probiotic yogurt prevent diarrhoea in children on antibiotics? A double-blind, randomised, placebo-controlled study.
   - Full-text source: https://pmc.ncbi.nlm.nih.gov/articles/PMC4298112/
   - Dose extracted from full text: probiotic yogurt 200 g/day containing mean `5.2 x 10^9 CFU/day` LGG + mean `5.9 x 10^9 CFU/day` Bb-12 + mean `8.3 x 10^9 CFU/day` La-5 for the duration of antibiotic treatment.
   - Population: children age 1-12 taking antibiotics.
   - Outcome: reduced minor and severe AAD vs pasteurized yogurt control.
   - Why it matters: this is meaningful combo evidence involving both LGG and Bb-12.
   - Transfer limit: pediatric antibiotic-exposed yogurt matrix with an added third strain. Not Ritual Synbiotic+ and not a direct basis for general digestive symptom credit.

### Saccharomyces boulardii: meaningful primary records

1. PMID 41675330 — https://pubmed.ncbi.nlm.nih.gov/41675330/
   - Title: Adjunctive use of *Saccharomyces boulardii* versus bismuth subsalicylate in the management of non-*Clostridioides difficile* nosocomial diarrhea in severely ill patients: a three-arm randomized controlled trial.
   - Full-text source: https://pmc.ncbi.nlm.nih.gov/articles/PMC12887278/
   - Dose extracted from full text: Bioflor `250 mg` capsule twice daily for `5 days`.
   - Population: 72 hospitalized adults with new non-CDI nosocomial diarrhea.
   - Outcome: no significant benefit vs standard care across stool weight, stool frequency, or stool consistency.
   - Why it matters: this is a primary human null record that prevents simplistic "S. boulardii always works for diarrhea" scoring.
   - Transfer limit: hospitalized adult nosocomial-diarrhea treatment context, product identity not matched to Jarrow, mg not CFU, and strain code not established from this note.

2. Species-level positive evidence is still context-bound, not exact-label proof:
   - PMID 26216624 — https://pubmed.ncbi.nlm.nih.gov/26216624/
   - Secondary meta-analysis supports *S. boulardii* for prevention of AAD in children and adults on antibiotics.
   - Useful for "species has human evidence" only.
   - Not enough for exact-strain identity transfer to Jarrow because the audited label page reviewed here does not expose CNCM I-745 or another strain code.

## Product-by-product disposition

### Culturelle LGG 10B

- Real human evidence exists for LGG, but it splits across distinct contexts:
  - pediatric functional abdominal pain / IBS
  - pediatric AAD
  - adult AAD or *H. pylori* adjunct settings with weaker or narrower support
- The current scoring risk is over-transfer from antibiotic-context or pediatric studies into a broad adult digestive label.
- Conservative research conclusion:
  - keep LGG as a genuine native researched strain
  - do not award broad dose applicability from pediatric AAD alone
  - if adding a reviewed primary record, pediatric abdominal-pain/IBS evidence is more honest than pretending the broad label is directly proven

### Ritual LGG + BB-12 + PreforPro

- I did not find an exact-product primary human trial in this bounded pass.
- The best directly usable BB-12 primary digestive paper is PMID 26382580, but it is stool-frequency focused and still does not solve label dose exposure because Ritual discloses only total blend CFU.
- The best combo LGG/BB-12 primary paper found here is PMID 25588782, but it is pediatric, antibiotic-context, yogurt-matrix, and includes La-5.
- Conservative research conclusion:
  - suspend the unverified BB-12 PMID 38271203; replacement requires the registry's clinician review, not an automatic swap
  - keep `strain_dose_unknown` / no exact label dose applicability unless a real per-strain exposure source is found
  - do not let AAD combo evidence unlock broad occasional gas/bloating/abdominal-discomfort applicability

### Jarrow S. boulardii + MOS 5B

- No exact-bottle primary trial found in this bounded pass.
- There is real species-level evidence for antibiotic-context diarrhea prevention, but the stronger modern literature is commonly strain-specific and/or antibiotic-context specific.
- The null adult nosocomial-diarrhea RCT (PMID 41675330) is important because it shows context dependence even within diarrhea outcomes.
- Conservative research conclusion:
  - do not treat species-level AAD literature as exact-strain or exact-label proof for this Jarrow bottle
  - if a native record is added, it should preserve unresolved strain identity and context limits

## Concrete curated-record candidates

1. `STRAIN_LGG_PED_FAPD_17229242`
   - PMID: 17229242
   - population: children 6-16 with FAPD; strongest signal in IBS subgroup
   - indication: pediatric functional abdominal pain / IBS
   - dose: `3 x 10^9 CFU` twice daily for `4 weeks`
   - direction: positive_moderate
   - limitations: not adult; not general gas/bloating; not antibiotic-context; not travel

2. `STRAIN_BB12_LOW_STOOL_FREQ_26382580`
   - PMID: 26382580
   - population: healthy adults with low defecation frequency and abdominal discomfort
   - indication: stool-frequency / constipation-like digestive support
   - dose: `1 x 10^9 CFU/day` and `1 x 10^10 CFU/day` for `4 weeks`
   - direction: positive_mixed
   - limitations: original primary responder and global-discomfort results not significant; revised responder and average-frequency results favorable. Not direct Ritual label exposure because per-strain dose is undisclosed. Pending clinician approval, retained only as a research candidate.

3. `COMBO_LGG_BB12_LA5_PED_AAD_25588782`
   - PMID: 25588782
   - population: children on antibiotics
   - indication: prevention of antibiotic-associated diarrhea
   - dose: LGG `5.2 x 10^9 CFU/day` + Bb-12 `5.9 x 10^9 CFU/day` + La-5 `8.3 x 10^9 CFU/day` in yogurt during antibiotic course
   - direction: positive_strong
   - limitations: combo only; pediatric; antibiotic-context; yogurt matrix; not Ritual Synbiotic+

4. `STRAIN_SBOULARDII_NOSOCOMIAL_NULL_41675330`
   - PMID: 41675330
   - population: hospitalized adults with non-CDI nosocomial diarrhea
   - indication: treatment of established nosocomial diarrhea
   - dose: `250 mg` twice daily for `5 days`
   - direction: null
   - limitations: not exact Jarrow product; strain code unresolved from this pass; mg exposure not CFU

## Contract recommendation

Yes: stronger production contract is warranted.

Single blanket strain windows are too coarse for probiotics. At minimum, a reviewed native record should carry:

- `identity_level`: species | strain | commercial_formula
- `indication`: e.g. pediatric IBS, adult low stool frequency, AAD prevention, *H. pylori* adjunct, nosocomial diarrhea treatment
- `target_population`: age band + health context
- `co_therapy_context`: antibiotics / eradication therapy / none
- `dose_exposure_type`: per-strain exact | combined blend only | mg only | undisclosed
- `formulation_matrix`: capsule / yogurt / fermented milk / formula-specific
- `applicability_rule`: exact label, exact strain but dose-unresolved, species-only, or non-transferable

That would prevent a single adult AAD or pediatric AAD paper from unlocking broad digestive applicability points on unrelated labels.

## Query log

Reviewed on 2026-09-03.

- `site:culturelle.com Digestive Daily Probiotic LGG 10 billion inulin official`
- `site:ritual.com Synbiotic+ LGG BB-12 PreforPro official label`
- `site:jarrow.com Saccharomyces Boulardii + MOS 5 Billion CFU official`
- Europe PMC / PubMed exact-ID checks:
  - `EXT_ID:26756877 AND SRC:MED`
  - `EXT_ID:33295643 AND SRC:MED`
  - `EXT_ID:38271203 AND SRC:MED`
- Europe PMC bounded topic searches:
  - `"Lactobacillus rhamnosus GG" functional abdominal pain randomized placebo`
  - `"Bifidobacterium animalis" "BB-12" randomized abdominal discomfort`
  - `"Saccharomyces boulardii" antibiotic-associated diarrhea randomized`
  - `"Saccharomyces boulardii" nosocomial diarrhea randomized`
