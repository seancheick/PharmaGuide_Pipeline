# Q58 routing: impact report (2026-10-02)

Branch `claude/q58-routing`. Not released. Stops here for Sean's review.

## Measured on the shipped corpus

- 15,421 enriched products (38 brands): **0** match any of the 84 records (enriched `contaminant_data` and full scored records); **0** carry `safety_review_records` (no product is quarantined today).
- Warning titles for all 9,875 products with any safety flag: **0** changed between the old tree (`claude/q58-verification`) and the new tree.
- So today: 0 products newly BLOCKED, 0 no longer BLOCKED, 0 moved to or out of quarantine, 0 label changes, 0 recall changes, 0 cannabis/THC changes. Every change below is latent: it decides what the next label that names one of these substances gets.

## Route per record (synthetic label through the real gate and export)

Before: 81 QUARANTINE (not found on scan), 3 never matches (historical).  
After: 47 BLOCKED, 12 QUARANTINE (not found on scan), 12 never matches (historical), 12 UNSAFE (recall), 1 never matches (disabled).

| Record | Route | Reader label | One-liner |
|---|---|---|---|
| ADD_HEXADRONE | BLOCKED | Not lawful as a supplement | Designer anabolic steroid. Stop using and talk to your doctor. |
| ADD_HORDENINE | BLOCKED | Not lawful as a supplement | Stimulant at supplement doses. Stop using this product. |
| ADD_THYROGEN | BLOCKED | Not lawful as a supplement | Prescription biologic, not a supplement. Stop using and talk to your doctor. |
| ADULTERANT_MELOXICAM | BLOCKED | Hidden drug | Prescription NSAID hidden in supplements. Stop using and talk to your doctor. |
| ADULTERANT_METFORMIN | BLOCKED | Hidden drug | Prescription drug hidden in supplements. Stop using and talk to your doctor. |
| ADULTERANT_RIMONABANT | BLOCKED | Hidden drug | Rejected drug hidden in supplements. Stop using and talk to your doctor. |
| ADULTERANT_TESTOSTERONE_PROPIONATE | BLOCKED | Hidden drug | Hidden injectable steroid in supplements. Stop using and talk to your doctor. |
| BANNED_ACONITE | BLOCKED | Unverified ingredient | Cardiotoxic botanical. Stop using and talk to your doctor. |
| BANNED_CALAMUS_ACORUS_CALAMUS | BLOCKED | Not lawful as a supplement | US-prohibited botanical, cancer concerns. Stop using and talk to your doctor. |
| BANNED_CLENBUTEROL | BLOCKED | Unverified ingredient | Unapproved beta-agonist drug. Stop using and talk to your doctor. |
| BANNED_DETERENOL_ISOPROPYLNORSYNEPHRINE | BLOCKED | Unverified ingredient | Stimulant linked to heart risk. Stop using and talk to your doctor. |
| BANNED_DMSA_SUCCIMER | BLOCKED | Not lawful as a supplement | Prescription chelator, not a supplement. Stop using and talk to your doctor. |
| BANNED_DNP | BLOCKED | Not lawful as a supplement | Industrial chemical linked to deaths. Stop using and talk to your doctor. |
| BANNED_IBOTENIC_ACID | BLOCKED | Unverified ingredient | Neurotoxic mushroom compound. Stop using and talk to your doctor. |
| BANNED_IGF1 | BLOCKED | Unverified ingredient | Prescription growth-factor drug. Stop using and talk to your doctor. |
| BANNED_MUSCIMOL | BLOCKED | Unverified ingredient | Psychoactive mushroom compound. Stop using and talk to your doctor. |
| BANNED_SR9009 | BLOCKED | Unverified ingredient | Unapproved research compound. Stop using and talk to your doctor. |
| BANNED_USNIC_ACID | BLOCKED | Unverified ingredient | Liver-toxic compound. Stop using and talk to your doctor. |
| PEPTIDE_BPC157 | BLOCKED | Unverified ingredient | Unapproved experimental peptide. Stop using and talk to your doctor. |
| PEPTIDE_TB500 | BLOCKED | Unverified ingredient | Unapproved synthetic peptide. Stop using and talk to your doctor. |
| PHARMA_DAPOXETINE | BLOCKED | Hidden drug | Prescription SSRI hidden in supplements. Stop using and talk to your doctor. |
| PHARMA_LORCASERIN | BLOCKED | Hidden drug | Withdrawn Rx drug hidden in supplements. Stop using and talk to your doctor. |
| RECALLED_BEAUTY_911 | BLOCKED | Hidden drug | Contains a withdrawn prescription drug — stop using and talk to your doctor. |
| RECALLED_BIG_DICK_ENERGY | BLOCKED | Hidden drug | Contains hidden prescription drugs — stop using and talk to your doctor. |
| RECALLED_CANDY_POWER_FOR_MAN | BLOCKED | Hidden drug | Contains a hidden prescription drug — stop using and talk to your doctor. |
| RECALLED_DEEP | BLOCKED | Hidden drug | Contains a hidden designer ED drug — stop using and talk to your doctor. |
| RECALLED_ERECTUS_PLUS | BLOCKED | Hidden drug | Contains hidden prescription drugs — stop using and talk to your doctor. |
| RECALLED_GE_LABS_YKARINE | BLOCKED | Hidden drug | Recalled product with hidden steroid. Stop using and talk to your doctor. |
| RECALLED_LUZE_FIT_INTENSITY | BLOCKED | Hidden drug | Contains a withdrawn prescription drug — stop using and talk to your doctor. |
| RECALLED_MAXMAN_COFFEE | BLOCKED | Hidden drug | Contains hidden prescription drugs — stop using and talk to your doctor. |
| RECALLED_MIRACLE_POWER_OF_KING_KONG_HONEY | BLOCKED | Hidden drug | Contains a hidden prescription drug — stop using and talk to your doctor. |
| RECALLED_SENSUAL_MIRACLE_HONEY | BLOCKED | Hidden drug | Contains hidden prescription drugs — stop using and talk to your doctor. |
| RECALLED_ZUBB | BLOCKED | Hidden drug | Contains a hidden prescription drug — stop using and talk to your doctor. |
| SCHED_AMANITA_MUSCARIA | BLOCKED | Unverified ingredient | Psychoactive mushroom, 2024 outbreak. Stop using and talk to your doctor. |
| SCHED_PSILOCIN | BLOCKED | Controlled substance | DEA Schedule I substance. Stop using and talk to your doctor. |
| SCHED_PSILOCYBIN | BLOCKED | Controlled substance | DEA Schedule I controlled substance. Stop using and talk to your doctor. |
| SPIKE_AMINOTADALAFIL | BLOCKED | Hidden drug | Designer ED drug hidden in supplements — stop using and talk to your doctor. |
| SPIKE_CHLOROPRETADALAFIL | BLOCKED | Hidden drug | Designer ED drug hidden in supplements. Stop using and talk to your doctor. |
| SPIKE_DEXAMETHASONE | BLOCKED | Hidden drug | Prescription steroid hidden in supplements. Stop using and talk to your doctor. |
| SPIKE_DICLOFENAC | BLOCKED | Hidden drug | Prescription NSAID hidden in supplements. Stop using and talk to your doctor. |
| SPIKE_FLUOXETINE | BLOCKED | Hidden drug | Rx antidepressant hidden in supplements. Stop using and talk to your doctor. |
| SPIKE_METHOCARBAMOL | BLOCKED | Hidden drug | Rx muscle relaxant hidden in supplements. Stop using and talk to your doctor. |
| SPIKE_PHENOLPHTHALEIN | BLOCKED | Hidden drug | Removed laxative drug hidden in supplements. Stop using and talk to your doctor. |
| SPIKE_PROPOXYPHENYLSILDENAFIL | BLOCKED | Hidden drug | Designer ED drug hidden in supplements. Stop using and talk to your doctor. |
| SPIKE_SILDENAFIL | BLOCKED | Hidden drug | Prescription drug hidden in supplements. Stop using and talk to your doctor. |
| SPIKE_TADALAFIL | BLOCKED | Hidden drug | Prescription drug hidden in supplements. Stop using and talk to your doctor. |
| WADA_TRAMADOL | BLOCKED | Controlled substance | Prescription opioid, federally controlled. Stop using and talk to your doctor. |
| ADD_N_PHENETHYL_DIMETHYLAMINE | QUARANTINE (not found on scan) | Unsafe ingredient | Designer stimulant. Stop using this product and talk to your doctor. |
| BANNED_FASORACETAM | QUARANTINE (not found on scan) | Unverified ingredient | Failed investigational drug. Stop using and talk to your doctor. |
| BANNED_IGF1_LR3 | QUARANTINE (not found on scan) | Unverified ingredient | Unapproved peptide drug. Stop using and talk to your doctor. |
| BANNED_SUNIFIRAM | QUARANTINE (not found on scan) | Unverified ingredient | Untested synthetic nootropic. Stop using and talk to your doctor. |
| NOOTROPIC_9MEBC | QUARANTINE (not found on scan) | Unverified ingredient | Untested synthetic compound. Stop using and talk to your doctor. |
| NOOTROPIC_BROMANTANE | QUARANTINE (not found on scan) | Not lawful as a supplement | Not a lawful US supplement ingredient. Stop using and talk to your doctor. |
| NOOTROPIC_FLMODAFINIL | QUARANTINE (not found on scan) | Unverified ingredient | Designer analog of a controlled drug. Stop using and talk to your doctor. |
| NOOTROPIC_PIRACETAM | QUARANTINE (not found on scan) | Unverified ingredient | Rx drug abroad, unapproved in the US. Stop using and talk to your doctor. |
| RC_CARDARINE_ANALOGS | QUARANTINE (not found on scan) | Not lawful as a supplement | Cancer-linked designer drug. Stop using and talk to your doctor. |
| SPIKE_TIANEPTINE_ANALOGUES | QUARANTINE (not found on scan) | Unsafe ingredient | Designer opioid-like substances. Stop using and talk to your doctor. |
| SYNTH_CUMYL_PICA | QUARANTINE (not found on scan) | Unverified ingredient | Synthetic cannabinoid linked to deaths. Stop using and talk to your doctor. |
| WADA_CANNABIS | QUARANTINE (not found on scan) | Prohibited in sport | WADA-prohibited in competition. Talk to your team physician. |
| RECALLED_BIQ_FEL | UNSAFE (recall) | Recalled product | Contains hidden prescription drugs — stop using and talk to your doctor. |
| RECALLED_BLUE_BULL_EXTREME | UNSAFE (recall) | Recalled product | Class I recall — sildenafil-spiked. Stop using and talk to your doctor. |
| RECALLED_BONER_BEARS_HONEY | UNSAFE (recall) | Recalled product | Class I recall — sildenafil + tadalafil. Stop using and talk to your doctor. |
| RECALLED_GREEN_LUMBER | UNSAFE (recall) | Recalled product | Recalled product hidden prescription drug. Stop using and talk to your doctor. |
| RECALLED_MODERN_WARRIOR | UNSAFE (recall) | Recalled product | Recalled product with hidden stimulants. Stop using and talk to your doctor. |
| RECALLED_MR7_SUPER_700000 | UNSAFE (recall) | Recalled product | Hidden two prescription drugs. Stop using and talk to your doctor. |
| RECALLED_REBOOST_CLEARLIFE_NASAL_SPRAY | UNSAFE (recall) | Recalled product | Recalled for microbial contamination. Do not use this recalled product. |
| RECALLED_RED_BULL_EXTREME | UNSAFE (recall) | Recalled product | Class I recall — sildenafil-spiked. Stop using and talk to your doctor. |
| RECALLED_RHEUMACARE_CAPSULES | UNSAFE (recall) | Recalled product | Recalled for extreme lead levels. Stop and test. |
| RECALLED_SILINTAN | UNSAFE (recall) | Recalled product | Recalled product hidden prescription NSAID. Stop using and talk to your doctor. |
| RECALLED_SILUETAYA_TEJOCOTE | UNSAFE (recall) | Recalled product | Class I FDA recall — yellow oleander substitution. Stop immediately. |
| RECALLED_X10_NATURAL_ENHANCEMENT | UNSAFE (recall) | Recalled product | Contains hidden prescription drugs — stop using and talk to your doctor. |
| SPIKE_METHYL7K | never matches (disabled) |  | Potent semi-synthetic opioid-like compound. Stop using and talk to your doctor. |
| RECALLED_AONIC_COMPLETE_HERS | never matches (historical) |  | Class II recall — microbial contamination. Do not use this recalled product. |
| RECALLED_AONIC_COMPLETE_HIS | never matches (historical) |  | Class II recall — microbial contamination. Do not use this recalled product. |
| RECALLED_DIVIDED_SUNSET_COLLAGEN_PEPTIDES | never matches (historical) |  | Class II FDA recall — undeclared egg allergen. Do not use this recalled product. |
| RECALLED_GOLD_STAR_DISTRIBUTION | never matches (historical) |  | Potential Salmonella contamination recall. Do not use this recalled product. |
| RECALLED_HYDROXYCUT | never matches (historical) |  | Recalled product linked to liver injury. Do not use this recalled product. |
| RECALLED_IMU_TEK_COLOSTRUM_5_CAPSULES | never matches (historical) |  | Class II recall — possible under-processing. Do not use this recalled product. |
| RECALLED_IMU_TEK_COLOSTRUM_5_POWDER | never matches (historical) |  | Class II recall — possible under-processing. Do not use this recalled product. |
| RECALLED_JACK3D | never matches (historical) |  | Recalled DMAA product linked to deaths. Do not use this recalled product. |
| RECALLED_LIVE_IT_UP_SUPER_GREENS | never matches (historical) |  | Recalled for potential Salmonella. Do not use this recalled product. |
| RECALLED_OXYELITE_PRO | never matches (historical) |  | Recalled product linked to liver transplants. Do not use this recalled product. |
| RECALLED_PURITY_PRODUCTS_MY_BLADDER | never matches (historical) |  | Recalled for E. coli contamination. Do not use this recalled product. |
| RECALLED_ROSABELLA_MORINGA | never matches (historical) |  | Recalled for potential Salmonella. Do not use this recalled product. |

## Cannabis / THC measurement (route held for Sean)

Proposed route: `WADA_CANNABIS` blocks as "Not lawful as a supplement" (FDA: THC products are excluded from the supplement definition, 21 U.S.C. 321(ff)(3)(B); hemp THC is excepted from Schedule I) with "Prohibited in sport" as information. Matching is exact on its aliases (THC, tetrahydrocannabinol, delta-9 forms, marijuana); hemp seed, hemp protein and hemp extract strings do not match. CBD is a separate, already-verified record (BANNED_CBD_US).

| Label text category | Products | Distinct strings (top) |
|---|---|---|
| THC / tetrahydrocannabinol declared | 0 |  |
| delta-9 / delta-8 / HHC | 0 |  |
| marijuana / cannabis extract | 0 |  |
| full/broad-spectrum hemp extract | 39 | Broad Spectrum Hemp extract blend (21); Broad Spectrum Hemp extract Blend (9); Broad Spectrum Phytocannabinoids (4); Broad Spectrum Hemp Oil extract (3) |
| hemp aerial parts / flower / leaf | 1 | Hemp Oil (aerial plant parts) extract (1) |
| hemp seed oil | 8 | Hemp Seed Oil (8) |
| hemp seed / hemp hearts | 4 | Hemp seed Protein (4) |
| hemp protein | 14 | Hemp Protein (14); organic Hemp Protein (3) |
| other hemp extract / oil | 49 | Hemp Extract (41); Hemp extract (32); Broad Spectrum Hemp extract blend (21); Broad Spectrum Hemp extract Blend (9) |
| CBD / cannabidiol | 33 | Cannabidiol (33); CBD+ Focus Blend (1); CBD+ Inflammatory Response Blend (1); CBD+ Relax Blend (1) |
| other cannabinoids (CBG, CBN, CBC) | 0 |  |

No label in the corpus declares THC, delta-9/delta-8 THC, marijuana or a cannabis extract; the route would change 0 products today.

## Safety copy changed (Sean-owned; approve or amend before release)

Each change applies a 2026-10-02 decision: Category 1 copy may not claim a legal status; copy that now ships on a blocked page must not be stronger than its read evidence (ibotenic acid, IGF-1, SR9009, clenbuterol, Amanita, per the fresh review); Gold Star, Hydroxycut, lorcaserin, hexadrone and tramadol wording as directed; two one-liners shortened to the 80-character limit.

| Record | Field | Before | After |
|---|---|---|---|
| ADD_HEXADRONE | safety_warning | A Schedule III designer anabolic steroid. Supplement products containing it are adulterated under US law and are linked to liver injury. Stop and consult a doctor. | A designer anabolic steroid that FDA says cannot be sold as a dietary supplement. Anabolic steroids are linked to liver injury. Stop and consult a doctor. |
| ADD_HEXADRONE | one-liner | Schedule III designer steroid. Stop using and talk to your doctor. | Designer anabolic steroid. Stop using and talk to your doctor. |
| ADD_THYROGEN | safety_warning | A prescription thyroid-cancer biologic found in some products labeled as supplements. Its presence indicates unlawful drug inclusion; stop the supplement and consult a doctor. | A prescription thyroid-cancer biologic. As an approved biologic it cannot be sold as a dietary supplement. Stop the product and consult a doctor. |
| ADD_THYROGEN | one-liner | Prescription biologic hidden in supplements. Stop using and talk to your doctor. | Prescription biologic, not a supplement. Stop using and talk to your doctor. |
| BANNED_CLENBUTEROL | safety_warning | A beta-agonist drug found undeclared in performance and weight-loss supplements — risk of rapid heart rate, tremor, and dangerous blood-pressure changes. Stop the supplement and consult a doctor. | A beta-agonist drug used without medical supervision for bodybuilding and weight loss, linked to rapid heart rate, heart-rhythm problems and heart muscle injury. Stop and consult a doctor. |
| BANNED_CLENBUTEROL | one-liner | Illicit drug found in supplements. Stop using and talk to your doctor. | Unapproved beta-agonist drug. Stop using and talk to your doctor. |
| BANNED_DETERENOL_ISOPROPYLNORSYNEPHRINE | safety_warning | A stimulant that mimics adrenaline, found in weight-loss products. Associated with cardiovascular risk; not a lawful supplement ingredient. Stop and consult a doctor. | A stimulant that mimics adrenaline, found in weight-loss products. Associated with cardiovascular risk. Stop and consult a doctor. |
| BANNED_DETERENOL_ISOPROPYLNORSYNEPHRINE | one-liner | Unlawful stimulant linked to heart risk. Stop using and talk to your doctor. | Stimulant linked to heart risk. Stop using and talk to your doctor. |
| BANNED_DMSA_SUCCIMER | one-liner | Prescription chelator hidden in supplements. Stop using and talk to your doctor. | Prescription chelator, not a supplement. Stop using and talk to your doctor. |
| BANNED_IBOTENIC_ACID | safety_warning | A neurotoxic amino acid in Amanita mushrooms that acts on NMDA receptors and can cause excitotoxic brain injury. Not a lawful supplement ingredient. Stop and consult a doctor. | A neurotoxic compound in Amanita mushrooms. Poisonings from mushrooms containing it cause stomach upset, agitation and deep sedation, sometimes needing a breathing tube. Stop and consult a doctor. |
| BANNED_IGF1 | safety_warning | A synthetic growth-factor drug with no recognized US supplement status. Use is associated with hypoglycemia, tumor growth, and acromegaly risk. Stop and consult a doctor. | A prescription growth-factor drug with no recognized US supplement status. In children treated with the injected drug, low blood sugar was common and tumours were reported. Stop and consult a doctor. |
| BANNED_IGF1 | one-liner | Unapproved drug, not a supplement. Stop using and talk to your doctor. | Prescription growth-factor drug. Stop using and talk to your doctor. |
| BANNED_MUSCIMOL | safety_warning | A potent GABA-A agonist from Amanita mushrooms — associated with sedation, altered perception, and at higher doses seizures. Not a lawful supplement ingredient. Stop and consult a doctor. | A potent GABA-A agonist from Amanita mushrooms — associated with sedation, altered perception, and at higher doses seizures. Stop and consult a doctor. |
| BANNED_SR9009 | safety_warning | An experimental research compound — never approved for human use and not a lawful supplement ingredient. Poor oral bioavailability plus safety unknowns. Stop and consult a doctor. | An experimental research compound never approved for human use. Its safety in people is unknown, and one case of liver injury has been reported. Stop and consult a doctor. |
| BANNED_USNIC_ACID | safety_warning | A lichen-derived compound linked to severe liver injury in weight-loss and energy products. Not a lawful supplement ingredient in this use profile. Stop and consult a doctor. | A lichen-derived compound linked to severe liver injury in weight-loss and energy products. Stop and consult a doctor. |
| PEPTIDE_BPC157 | safety_warning | An unapproved synthetic peptide studied only in animal models. Not a lawful US dietary ingredient; long-term human safety is unknown. Stop and consult a doctor before continuing use. | An unapproved synthetic peptide studied only in animal models. Long-term human safety is unknown. Stop and consult a doctor before continuing use. |
| PEPTIDE_TB500 | safety_warning | An unapproved synthetic peptide. Not a lawful US dietary ingredient; safety and purity of gray-market products are unverified. Stop and consult a doctor. | An unapproved synthetic peptide. Safety and purity of gray-market products are unverified. Stop and consult a doctor. |
| PHARMA_LORCASERIN | safety_warning | A withdrawn prescription weight-loss drug found undeclared in supplements. FDA pulled it from the US market in 2020 after a study linked it to cancer risk. Stop and consult a doctor. | A withdrawn prescription weight-loss drug found undeclared in supplements. FDA requested its withdrawal from the US market in 2020 after a study linked it to cancer risk. Stop and consult a doctor. |
| RECALLED_GOLD_STAR_DISTRIBUTION | safety_warning | Products from this brand faced FDA enforcement for serious manufacturing violations — linked to Salmonella contamination and sanitation issues. Stop and consult a doctor if symptoms develop. | Products held at this distributor's warehouse were recalled for rodent and bird contamination and potential Salmonella contamination. Stop and consult a doctor if symptoms develop. |
| RECALLED_GOLD_STAR_DISTRIBUTION | one-liner | Salmonella contamination recall. Do not use this recalled product. | Potential Salmonella contamination recall. Do not use this recalled product. |
| RECALLED_HYDROXYCUT | safety_warning | Hydroxycut was recalled in 2009 after being linked to 23 reports of severe liver injury and one death. Stop any remaining product and consult a doctor if symptoms develop. | Recalled in 2009 after FDA received 23 reports of serious health problems, including liver injuries from jaundice to transplant, and one death. Stop any remaining product. |
| SCHED_AMANITA_MUSCARIA | safety_warning | A psychoactive mushroom associated with a 2024 multi-state outbreak of serious illness. Not a lawful supplement ingredient; linked to hallucinations and seizures. Stop and consult a doctor. | A psychoactive mushroom associated with a 2024 multi-state outbreak of serious illness. Linked to hallucinations and seizures. Stop and consult a doctor. |
| SCHED_AMANITA_MUSCARIA | one-liner | Psychoactive mushroom, 2024 outbreak. Stop using and talk to your doctor. | Psychoactive mushroom linked to poisonings. Stop using and talk to your doctor. |
| WADA_TRAMADOL | safety_warning | A prescription opioid added to the WADA in-competition prohibited list in 2024. Competitive athletes should talk to their physician about alternatives and testing windows. | A prescription opioid and federally controlled substance that should not be in a dietary supplement. WADA also prohibits it in competition. Stop using it and talk to your doctor. |
| WADA_TRAMADOL | one-liner | WADA-prohibited in competition since 2024. Talk to your physician. | Prescription opioid, federally controlled. Stop using and talk to your doctor. |

Still flagged for Q61 (unchanged): hordenine one-liner "Stimulant at supplement doses" (animal evidence only); Rheumacare "extreme lead levels ... Stop and test".

## Code changes

- `scoring_v4/gate_safety.py::_hard_policy_missing_requirements`: a record with `legal_status_enum: under_review` (no US determination) needs a read source tagged `clinical_risk` (human harm, or an authority's stated safety risk; `clinical_outcomes` alone is not enough because it also tags efficacy and product-analysis papers) instead of a government source; without one it stays quarantined (`verified_harm_evidence`). All other records keep the government-source requirement. No current verified banned/recalled record has `under_review`.
- `build_final_db.py::_BANNED_TITLE_PREFIX_BY_LEGAL_STATUS`: `under_review` reads "Unverified ingredient" (was "Unapproved ingredient"); a recalled product reads "Recalled product" (was "Recalled ingredient"); the core-row recall title and the safety-flag title now go through the same prefix owner. Measured: 0 shipped titles change.
- No new field, status value or verdict. Recalls keep the existing UNSAFE verdict, which the app renders as a hard block with no score; "BLOCKED" for recalls would be a verdict-contract change and is not made here.

## Category 1 under the tightened definition

Kept (identity confident, human harm or FDA safety-risk source read, no US determination): aconite, clenbuterol, deterenol, ibotenic acid, IGF-1, muscimol, SR9009 (one liver-injury case report; borderline), usnic acid, BPC-157, TB-500, Amanita muscaria. Amanita muscaria lost the aliases *A. pantherina*, "panther cap" (a different species; its own identity is a Q62 item) and "legal shrooms" (no identity). Muscimol, ibotenic acid and Amanita also carry a verified Louisiana ban (R.S. 40:989.5, Act 154 of 2025; R.S. 40:989.1, 2005) as a state row.
Moved to quarantine (no human harm evidence): fasoracetam (its trial showed no adverse-event difference from placebo), IGF-1 LR3, sunifiram, 9-MeBC, bromantane, flmodafinil, CUMYL-PICA.
Moved to regulatory block: DNP (FDA 2026-06-04 notice: "illegally marketed as a weight-loss product and not approved by FDA for any use").

## Capability gap

Rule B (block a known lot) is not supported: the enricher reads `recall_scope` only as a yes/no switch and labels carry no lot numbers, so every recall match is by product name. Ended recalls now keep their lots in `recall_scope.lots` for the day lot or UPC identifiers reach the matcher.

## Not done here

Cannabis route (waits for Sean's review of the measurement above); Q61 copy, Q62 aliases, Q60 Yellow 5/6, Q63, Q64; the separate `is_confirmed_ban_or_recall` reason-code defect (spawned task). No release.

## Fresh-context review (independent agent, 2026-10-02)

Verdict: merge after fixes. Narrow and deterministic; 0 changed outcomes outside Q58 (old vs new code on the new data, every banned/recalled record, active and inactive roles). Resolved: (1) unsupported copy that would now ship was corrected (table above); (2) Amanita aliases for another species and a marketing phrase removed; IGF-1 already excludes deer antler, velvet and colostrum labels by negative match terms; (3) the harm check now keys on `clinical_risk` only, and each Category 1 harm source was tagged after reading; (6) test nits fixed (Amanita pins `under_review`; the identifier test calls the gate's own harm check). Left for Sean: deterenol (only harm source is a multi-stimulant product; the reason now says so) and SR9009 (one case report) are the two borderline Category 1 records. Not changed: empty `verified_sources` on Category 1 decisions (the field lists government sources only; no reader); internal `source_category` values (not exported); Live it Up negative-match tests now pass trivially because the record is historical.
