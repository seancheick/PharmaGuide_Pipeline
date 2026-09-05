# Lost botanical evidence joins — individual dispositions, 2026-09-05

Source of the inventory: every product in
`corpus_preparation_continuation_accepted.json` whose recomputed evidence set
lost an entry (`evidence_before` minus `evidence_after`), excluding the
previously reviewed zinc-lozenge and beta-carotene scoping. Each label below
was re-enriched through the candidate enricher and its actual source rows,
projected identities and registry entries were read before any decision.
Primary abstracts were fetched live from NCBI EFetch on 2026-09-05.

## Why the joins broke

The preferred-name/identity projection now assigns narrower botanical ids
(`astragalus_root`, `echinacea_purpurea_aerial`, `ceylon_cinnamon`,
`black_garlic`, `grape`). `_clinical_study_match` is exact: it compares the
row name, standard name, source text and form candidates with the entry's
standard name and aliases. None of those registry entries named the projected
preparation, so the match silently stopped with an empty `rejected_evidence`.
That is a reachability gap, not a reviewed scientific denial.

## Joined after source review (registry 5.3.12)

| Family | Labels | Source read | Decision |
| --- | --- | --- | --- |
| Echinacea | 260118, 318188 (GNC "Echinacea purpurea powder" 500 mg); 200789, 206905 (Nature's Way "organic Echinacea purpurea" 600 mg / 1.2 g) → `echinacea_purpurea_aerial` | PMID 24554461, Cochrane 2014: 24 double-blind trials, 4,631 participants, "different species and parts of plant", seven trials of E. purpurea aerial-part preparations; conclusions mixed/weak | Add exact registry-projected preparation names `echinacea purpurea aerial`, `echinacea purpurea herb`, `echinacea purpurea root extract`. Family-level join only; effect stays `positive_weak`; no dose threshold. |
| Astragalus | 74595, 863 (GNC "Astragalus root powder" 500 mg); 222704 (Nutricost 550 mg) → `astragalus_root` | PMID 37952511, 2023 systematic review/meta-analysis: 19 human studies, 1,094 participants, immune markers, substantial heterogeneity; preparations/routes not itemised in the abstract | Add `astragalus root`: the root (Radix Astragali, huang qi) is the medicinal part the family already names. Notes state that the pooled interventions do not establish preparation, route or dose equivalence. |

Real-label result after the edit (candidate enricher): all seven labels reach
their entry through the exact source row (`matched_source_row_refs` = the
active's own path); 243147 Cranberry & D-Mannose already re-matched through the
5.3.11 `cranberry fruit concentrate` alias.

## Explicit reviewed denial (registry 5.3.12)

| Family | Labels | Source read | Decision |
| --- | --- | --- | --- |
| Ceylon cinnamon | 330605 (BulkSupplements "Ceylon Cinnamon Bark Extract" 1,000 mg), 269403 (Nutricost "organic Ceylon Cinnamon powder"), 271345 (Spring Valley "Ceylon Cinnamon, Powder", form Cinnamomum verum) → `ceylon_cinnamon` | PMID 24019277, Allen 2013: 10 RCTs, 543 type 2 diabetes patients, cinnamon 120 mg–6 g/day; no Ceylon-specific subgroup; the registry family and aliases are Cassia/Cinnulin | `applicability` exclusion-only scope: `excluded_canonical_ids: [ceylon_cinnamon]` plus Ceylon/verum/zeylanicum/true-cinnamon excluded form words; no source-word requirement, so misspelled but correctly mapped generic labels (62194 "Cinnammon") keep the family evidence. Aliases `ceylon cinnamon` and `cinnamomum verum` exist only so the exclusion is recorded as `clinical_identity_excluded` on the real label path (previously the denial was invisible). Cassia bark extract keeps its evidence (test). |

## Reviewed, not joined (genuine incomplete review)

- **Fermented black garlic 302657** ("Black Garlic Bulb Extract" 500 mg,
  S-allyl cysteine form → `black_garlic`). INGR_GARLIC cites PMID 32010325
  (Ried 2020): garlic supplements in hypertensive adults, 12 trials / 553
  participants, with the narrative centred on Kyolic aged garlic extract.
  Black garlic is a heat-aged whole-bulb preparation; no black-garlic trial is
  in the registry. No join; zero credit here is absence of review, not evidence
  of ineffectiveness.
- **BioVin Advanced 269265 / 302705** (Doctor's Best red grape extract 60 mg →
  `grape`). PRECLIN_RESVERATROL pools isolated-resveratrol trials; a 60 mg whole
  red-grape extract is a different intervention and no resveratrol content is
  declared. No join.
- **Gluten/Dairy Digest 182908 / 184300** (BioCore DPP-IV 100 mg; protease
  members are `nested_display_only`). INGR_DIGESTIVE_ENZYMES cites one
  multi-enzyme dyspepsia trial (PMID 37976892). A DPP-IV gluten/dairy protease
  is not that intervention, and undosed display-only children cannot own
  evidence under the source-owner rule. No join.
- **Cognigrape 304628**: removal of borrowed grape-seed evidence stands (fruit
  extract, not seed). Its dose pillar (20/20) is supplied by the B6/B12
  RDA/UL window proxy while the 250 mg primary botanical has no assessment;
  see the dose-method finding below.

Negative controls for all three families are pinned in
`test_botanical_lost_match_dispositions.py` (`_clinical_study_match` returns
None for the label vocabulary).

## Other lost matches, classified from the accepted report

- INGR_GREEN_TEA (36): matcha/whole-leaf `clinical_form_mismatch`, Centrum
  `clinical_identity_excluded`, and GNC formulas with no evidence change — the
  reviewed green-tea scope (see `green_tea_scope_research.md`).
- INGR_CRANBERRY (26): GNC multivitamins that became `not_scored` identity
  holds or kept their evidence score; only 243147 was a real loss and is back.
- PRECLIN_BOSWELLIA (11): ten BulkSupplements resin-extract labels restored by
  5.3.11; Thorne 284229 unchanged.
- BRAND_KSM66 (6): `clinical_form_mismatch` on generic ashwagandha labels; the
  generic INGR entry still supplies 14.7. This is the branded boundary working.
- PRECLIN_RESVERATROL (7): five Life Extension Mix labels are identity holds;
  two BioVin labels reviewed above.
- INGR_L_ARGININE (6), INGR_INULIN (4), BRAND_MERIVA (1): evidence pillar
  unchanged (other matches dominate); STRAIN_SBOULARDII 264610 is the
  intended Jarrow yeast-extract correction; INGR_GRAPE_SEED_EXTRACT 304628 is
  the intended Cognigrape correction.
- INGR_LEMON_BALM (2), INGR_DIGESTIVE_ENZYMES (2), INGR_GLUCOSAMINE_SULFATE /
  INGR_CHONDROITIN_SULFATE 17186: small evidence changes; 17186 carries a
  separate header-identity defect (see the source-ownership note).

## Dose-pillar changes named in handoff §6 (old code `cea87d01` vs checkpoint)

Old-code detail was obtained by running the same harness with
`--implementation-root` at `continuation-baseline.1ZPh87`
(`corpus_dose_attribution_control_cea87d01_6.json`). All five used
`botanical_clinical_dose_v1` (band 10.0) under old code and now use another
method: 304643 Prostate Health and 33167 Re-Shred → RDA/UL window proxy;
257098 Melatonin → `sleep_support_clinical_dose_v1` (3 mg, standard band);
304628 Brain Fuel → RDA/UL window proxy driven by B6/B12; 223536 Shiitake 7.5 g
→ `partial_credit_without_rda_proxy` (16.0, `individual_quantified_dose_no_rda_reference`)
with formulation collapsing 7.2 → 0.8. The printed amounts did not change; the
identity corrections moved these products off the botanical dose path. Whether
the receiving paths are the right semantics (a gummy scoring 20/20 dose on two
vitamins; a mushroom powder earning partial credit with no reference) is a
dose-policy decision, recorded below.

## Registry-wide findings requiring a decision (not changed)

1. **Enrollment convention conflict.** `DATABASE_SCHEMA.md` defines
   `total_enrollment` as the largest trial enrollment from ClinicalTrials.gov;
   registry 5.3.11 set cranberry (8,857) and Boswellia (545) to the cited
   review's pooled participants. Live abstracts show stored values that match
   neither convention: astragalus 112 (review 1,094), echinacea 719 (review
   4,631), cinnamon 229 (review 543), garlic 3,411 (review 553). Enrollment
   feeds `_enrollment_multiplier` bands (0.6–1.2), so the convention changes
   points. Left unchanged pending a registry-wide rule.
2. **Registry counts feed the depth bonus.** `_published_study_count` falls
   back to `registry_completed_trials_count`; 5.3.11 removed those counts for
   cranberry (111 → band 0.5) and Boswellia (25 → band 0.25), which is a
   numerical effect of that patch beyond the match repairs. Other entries still
   carry them.
3. **Branded entries with generic aliases** (15 of 56): see the source-ownership
   note; the PS entry is the concrete case.
4. **Dose-method semantics** for products whose primary active has no
   reference (Cognigrape, shiitake) and for the essential-vitamin proxy
   supplying a whole-product dose story.

## Independent review of the 5.3.11 patch on real labels (first full-corpus pass)

The first full comparison (`corpus_continuation_2026_09_05_full.json`) exposed
14 decreases since the accepted checkpoint. Each was traced to its source row:

| Products | Cause | Disposition |
| --- | --- | --- |
| 74761, 243146 (GNC "Boswellia Extract 450 mg"), 47945/75017 (Metabolic Elite), 273861, 12196, 19436 (Apres-Flex), 337853/337859 (Casperome) | 5.3.11 `required_form_terms` did not contain the printed extract spellings ("Boswellia serrata gum extract", "…AKBA standardized extract (wood) resin", "Apres-Flex", "Casperome / Indian Frankincense Phytosome"), so real extract labels were rejected as `clinical_form_mismatch` | Added `gum extract`, `standardized extract`, `apres flex`, `casperome`, `frankincense phytosome` to PRECLIN_BOSWELLIA. Family-level extract joins only. 243146 stays unmatched: its source row prints only "Boswellia serrata" with a boswellic-acid form while the product title says extract — recorded as ambiguous, not restored. |
| 74399 (Pacran cranberry concentrate powder), 184792 (PACRAN cranberry powder) | Old code credited both through scoring-contract recovery; the recovery never stamped the row it recovered from, so the 5.3.11 source-required scope rejected it as unresolved with no visible record | `_stamp_recovery_source_ref` binds each recovered entry to its exact row; the same evaluator then reads that row's own words. Seed-oil exclusion still holds (test). |
| 62194 (Spring Valley "Cinnammon" 1 g) | My first cinnamon policy required a source word; the label is misspelled but correctly mapped | Cinnamon policy is now an exclusion-only scope (Ceylon by canonical id or form words); no source-word requirement. |
| 330604 (BulkSupplements Ceylon) | `clinical_identity_excluded` | Intended reviewed denial. |
| 243132 (Herb 360 Grape Seed) | A grape-seed blend had carried cranberry evidence; the cranberry scope now rejects it (`clinical_form_mismatch`) | Correct removal of a mismatched identity. |

Unexpected increases traced:

- 312860 "Astragalus membranaceus Root Extract" 1,300 mg and 216796's
  "standardized Astragalus extract" reach INGR_ASTRAGALUS through the
  root/extract aliases — family-level, consistent within one label.
- 328831 Thorne "Ginseng Plus": the row "Botalys" (form "Korean Red Ginseng
  Root Extract") carries cleaner identity `astragalus_root` because
  `botanical_ingredients.json` listed "Botalys" as an astragalus alias.
  Botalys is a ginseng brand; the alias is removed so future cleaning maps it
  correctly. The read-only replay re-enriches from already-cleaned rows and
  therefore still shows this product with astragalus evidence (56.9 → 71.6);
  that number is a known wrong-identity artifact until the product is
  re-cleaned in the operational rebuild.

Two broad-suite failures remain and are attributed to the 5.3.11 cranberry
entry, not to this continuation: `primary_outcome` "Prevention of recurrent
symptomatic urinary tract infections" is outside the LOCKED 15-label
`primary_outcome_vocab.json` (app-facing evidence chips), and
`health_goals_supported: []` fails the DB integrity non-empty rule. The
vocabulary and goal lists have no urinary entry, so resolving this is a
taxonomy decision (add a urinary outcome/goal, or choose an existing label);
it was not made here. Boswellia's outcome was mapped to the existing
"Joint & Bone Health" label.
