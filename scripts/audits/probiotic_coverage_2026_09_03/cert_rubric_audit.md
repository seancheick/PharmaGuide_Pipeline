# Certification and Probiotic Rubric Audit

Audit date: 2026-09-03

Boundary: read-only audit against the current worktree implementation plus the original root corpus at `/Users/seancheick/Downloads/dsld_clean/scripts/products`. No production files changed. This report separates current resolver behavior from stale enriched artifacts already present in the root corpus.

**Final adjudication:** the September 4 addendum supersedes the early wording
“actual 100B row / real alias gap”: WF-edition equivalence to the audited UPC is
unproved. Its certification remains uncredited, not the product unscored. The
42-probiotic selection supersedes the earlier cross-module 30-ID sample. The
scope-default defect described below is fixed in this candidate. Rubric wording
suggestions are audit inputs, not accepted numerical-model changes; see
`rubric_decisions.md` for the final recommendations.

## Bottom line

1. The six comparator set in `scripts/audits/probiotic_rubric_2026_09_03/comparators.json` has only one Verification reduction: Garden of Life Dr. Formulated `326762` (`15 -> 9`). The other five comparators keep the same Verification pillar (`comparators.json:2413`, `audit_corpus.py:25-26`).
2. The Garden of Life drop is a mixed case:
   - real stale false credit in the root enriched corpus: product `326762` still carries `NSF Certified` for `Dr. Formulated Probiotics Immune 50B` and `NSF Sport` for `Garden of Life Sport Creatine Monohydrate + Probiotics Kosher 60 servings` in the original artifact (`/Users/seancheick/Downloads/dsld_clean/scripts/products/output_Garden_of_life_enriched/enriched/enriched_cleaned_batch_2.json:902492-902520`);
   - plus an unresolved edition-equivalence question: the registry contains `WF Dr. Formulated Probiotic 100B` as an NSF SKU (`scripts/data/cert_registry.json:41835-41846`), but this is not proof that it certifies the audited UPC.
3. The current resolver behavior is intentional for the false-positive cases. `scripts/tests/test_cert_resolver.py:525-537` and `:621-643` explicitly lock that `Probiotics 100 Billion` and `Probiotics 30 Billion` must not inherit `Immune 50B`, while `Probiotics Immune 50 Billion` may match the same registry row.
4. The current probiotic rubric still repeats the same underlying facts across Formulation, Dose, and Evidence:
   - Formulation: total CFU disclosed, CFU amount, named species diversity, clinical strain code count (`scripts/scoring_v4/modules/probiotic_formulation.py:54-120`);
   - Dose: per-strain CFU disclosure and CFU adequacy/proxy (`scripts/scoring_v4/modules/probiotic_dose.py:61-170`);
   - Evidence: strain clinical evidence and dose applicability (`scripts/scoring_v4/modules/probiotic_evidence.py:77-146`).
5. The pre-audit native research scope adapter collapsed missing specificity into `species_general`. This candidate fixes that to `scope_unresolved`, without using a missing-field correction as justification for a score lift.

## Comparator certification audit

Exact comparator Verification outcomes from `comparators.json`:

| ID | Product | Before | After | Current interpretation |
| --- | --- | ---: | ---: | --- |
| `250851` | Culturelle Digestive Daily Probiotic | 15 | 15 | unchanged; comparator already carries a valid `USP Verified` SKU match |
| `299239` | Ritual Synbiotic+ | 9 | 9 | unchanged; no certification credit in comparator |
| `307727` | Jarrow Saccharomyces Boulardii + MOS 5 Billion CFU | 6.5 | 6.5 | unchanged; only `ConsumerLab: claimed_only` |
| `326762` | Garden of Life Dr. Formulated Probiotics 100 Billion | 15 | 9 | only certification reduction in the six-product set |
| `327965` | Nature's Way Fortify Ultra Potency Optima Probiotic 100 Billion | 9 | 9 | unchanged; no certification credit in comparator |
| `PG_SUB_35E0BD3374BF494B80FEABE87FC559E7` | Seed DS-01 Daily Synbiotic | 9 | 9 | unchanged; no certification credit in comparator |

Garden of Life `326762` is the only comparator where the saved artifact and the current resolver materially disagree:

- current root enriched artifact still stores two discovered SKU certs (`...enriched_cleaned_batch_2.json:902492-902520`);
- current resolver logic treats both mismatches as non-scoring because SKU/product identity must survive strength, edition, form, and token guards (`scripts/cert_resolver.py:763-980`);
- the negative control is locked in tests (`scripts/tests/test_cert_resolver.py:621-643`).

## Garden of Life root cause

There are two separate Garden of Life stories; they should not be conflated.

### 1. Real false-positive stale artifact

The original root enriched payload for `326762` still embeds:

- `NSF_CERTIFIE_90843FED563A` matched to `Dr. Formulated Probiotics Immune 50B`;
- `NSF_SPORT_0E6998E18D30` matched to `Garden of Life Sport Creatine Monohydrate + Probiotics Kosher 60 servings`.

Those are visible in the root corpus at `/Users/seancheick/Downloads/dsld_clean/scripts/products/output_Garden_of_life_enriched/enriched/enriched_cleaned_batch_2.json:902492-902520`.

Under the current resolver, both candidates fail because identity is re-checked after brand match and before scoring authority is granted (`scripts/cert_resolver.py:841-873`, `:931-958`).

### 2. Unresolved equivalence to the WF 100B edition

The current registry snapshot dated 2026-06-15 does contain:

- `NSF_CERTIFIE_E2DDAEBDC7A7`
- product `WF Dr. Formulated Probiotic 100B`
- scope `sku`
- form `Capsule`

at `scripts/data/cert_registry.json:41835-41846`.

The problem is not “no registry record.” The problem is that the current resolver still treats that row as unresolved because:

- the registry shorthand includes `WF`;
- the registry name is singular `Probiotic` while the product label is `Probiotics 100 Billion`;
- there is no reviewed override for `dsld_id=326762`, while neighboring Garden of Life product-line overrides do exist for other products (`scripts/data/curated_overrides/cert_verification_overrides.json:12496-12605`).

So the Garden of Life comparator reduction is best classified as:

- fixed false positives removed: yes;
- missing proof that the WF listing covers the audited product: yes; this is not yet a confirmed alias defect.

That is narrower than “resolver bug.” The resolver is doing what its current contract says to do.

## Ten deterministic reduced rows

Source queue: `scripts/audits/probiotic_rubric_2026_09_03/verification_review_queue.json`. Queue headline counts:

- 534 reduced Verification rows total (`verification_review_queue.json:1-6`);
- 40 rows with Verification increases also recorded there (`verification_review_queue.json:1-6`);
- row-level buckets from the saved queue:
  - 281 rows with no `candidate_certifications`;
  - 163 rows with `needs_review` only;
  - 24 rows with `brand_only` only;
  - 33 rows with `claimed_only` only;
  - 33 rows with mixed scopes.

Deterministic sample used here: first reduced row per brand from the saved queue.

| ID | Brand | Product | Queue drop | Exact current decision | Audit classification |
| --- | --- | --- | --- | --- | --- |
| `182716` | Life Extension | Super Omega-3 EPA/DHA with Sesame Lignans & Olive Fruit Extract | `15 -> 9` | `ConsumerLab: brand_only` | expected strict removal; brand has cert, product not in registry |
| `313924` | Thorne | Super EPA Pro | `15 -> 9` | `NSF Sport: claimed_only` via rejected override; `USP Verified: claimed_only` | expected strict removal; manual rejection already encoded |
| `287361` | Member's Mark | 10 Strain Probiotic | `13 -> 4` | `USP Verified: needs_review` for `Member's Mark 10 Strain Probiotic Digestive Care Supplement Capsules` | likely alias/product-line review gap, not auto-scoring authority |
| `241612` | Nature's Bounty | Fish Oil | `15 -> 9` | discovery none; probing finds `USP Verified: needs_review` on `Fish Oil 1400 mg Softgels` | expected strict withholding on generic label lacking strength/form identity |
| `326762` | Garden of Life Dr. Formulated | Probiotics 100 Billion | `15 -> 9` | discovery none; probes hit `NSF Certified: needs_review`, `NSF Sport: needs_review`, `ConsumerLab: needs_review` | mixed case: stale false credit removed, plus missing alias/scope for actual 100B NSF row |
| `273197` | OLLY | Kids Multi + Probiotic Yum Berry Punch | `15 -> 7` | `NSF Certified: needs_review` for `KIDS MULTI + PROBIOTIC` | likely explicit review/alias gap; not a scoring-safe auto-match |
| `233682` | Garden of Life Raw Probiotics | Women | `15 -> 9` | discovery none; probe finds `NSF Certified: needs_review` on `Dr Formulated Probiotics Women’s Once Daily 40B` | expected strict withholding across different product line / sub-brand |
| `268690` | SR Sports Research | Whey Protein Isolate Dutch Chocolate | `15 -> 5` | `Informed Sport: needs_review`; `Informed Choice: brand_only`; `IFOS: claimed_only` | likely flavor/product-line review gap for Informed Sport; correct IFOS rejection |
| `302756` | Nature Made | Vitamin B-12 500 mcg | `15 -> 6` | `USP Verified: claimed_only` via rejected override | expected strict removal; old cluster was a false-positive transfer |
| `179618` | Nature Made Kids First | Fish Oil Gummies | `15 -> 7` | `USP Verified: claimed_only` via rejected override | expected strict removal; gummy cannot inherit softgel cert |

Notes:

- The OLLY family has explicit rejected overrides for nearby probiotic-only and non-matching rows against the `KIDS MULTI + PROBIOTIC` registry record (`scripts/data/curated_overrides/cert_verification_overrides.json:12261-12346`), which supports keeping these rows non-scoring until individually reviewed.
- The current resolver’s “no discovery” state is expected because `discover_verified_programs()` only returns `sku` or `product_line`, never `needs_review`/`brand_only`/`claimed_only` (`scripts/cert_resolver.py:963-980`).

## Real bugs vs alias/scope gaps

Bounded conclusion from the sample above:

- Real stale/false-credit bug in existing artifact: confirmed for Garden of Life `326762`.
- Expected strict rejections or correct withholding: Life Extension, Thorne, Nature's Bounty generic Fish Oil, Garden of Life Raw Probiotics Women, Nature Made B-12, Nature Made Kids First.
- Likely reviewable alias/scope/product-line gaps rather than scoring bugs: Member's Mark `287361`, OLLY `273197`, SR Sports Research `268690`, plus Garden of Life `326762` for the actual `WF Dr. Formulated Probiotic 100B` NSF row.

I did not complete a full 534-row root-cause classification. This report stops at the bounded sample the parent thread asked for.

## Probiotic repeated-credit map

Current source path:

- Formulation counts declared potency and composition breadth (`scripts/scoring_v4/modules/probiotic_formulation.py:77-84`);
- Dose counts disclosure quality and adequacy/proxy (`scripts/scoring_v4/modules/probiotic_dose.py:101-157`);
- Evidence counts researched strain support and applicability (`scripts/scoring_v4/modules/probiotic_evidence.py:91-111`).

That means the same underlying facts can influence multiple pillars:

1. Aggregate CFU affects:
   - Formulation `total_cfu_disclosed` and `cfu_amount`;
   - Dose `cfu_adequacy` through aggregate proxy when strain-level disclosure is absent.
2. Number of named strains/species affects:
   - Formulation `named_species_diversity`;
   - Transparency strain-identity messaging indirectly;
   - Evidence reach because more named strains can expose more clinical records, even though undosed contextual evidence is capped.
3. Count of reviewed clinical strains affects:
   - Formulation `clinical_strain_codes`;
   - Evidence `strain_clinical_evidence`.

The current code already narrows some over-credit:

- undosed contextual strain evidence is capped to the strongest single native record (`scripts/scoring_v4/modules/probiotic_evidence.py:150-190`; guarded by `scripts/tests/test_v4_probiotic_evidence_p23.py:139-154`);
- aggregate CFU is not treated as per-strain disclosure (`scripts/scoring_v4/modules/probiotic_dose.py:10-17`, `:101-116`);
- AFU formula evidence does not back-fill per-strain CFU or independent clinical count (`scripts/scoring_v4/modules/probiotic_formulation.py:85-96`, `scripts/scoring_v4/modules/probiotic_dose.py:70-82`).

## Initial rubric suggestions — superseded by rubric_decisions.md

Global weights stay unchanged in this batch. The suggestions below are retained
as initial review inputs, not the accepted next implementation. The final review
found that renaming points alone would leave the underlying double-credit
assumptions intact; `rubric_decisions.md` owns that follow-up.

1. Keep Formulation `cfu_amount` and `total_cfu_disclosed`, but describe them as potency/disclosure signals, not dose adequacy. Dose already owns adequacy.
2. Keep Formulation `clinical_strain_codes`, but treat the consumer meaning as identity richness / traceability, not “research credit.” Evidence already owns the research claim.
3. Treat `named_species_diversity` as a formulation variety descriptor, not an implied superiority signal. The current curve already avoids infinite reward; the wording should be equally conservative.
4. Introduce a non-affirmative native scope state for missing specificity:
   - current adapter defaults absent `q1_strain_explicit` and absent strain-specific `type` to `species_general` (`scripts/probiotic_measurements.py:163-174`);
   - presentation then emits `research_match_status = species_level` after review (`scripts/enrich_supplements_v3.py:672-681`, `:704-710`).
   - recommended report-only design: missing `q1`/type specificity should become `scope_unresolved`, not affirmative `species_general`.
5. Preserve the existing contextual numeric evidence where exact identity is already established and legacy signoff exists, but keep the UI state non-affirmative:
   - scoring can continue to grant contextual `strain_clinical_evidence` under the current exact-identity acceptance path;
   - Flutter-facing `research_match_status='scope_unresolved'` should map to fallback `none`, not to an affirmative species-level badge.

That preserves the parent thread’s stated intent: do not zero out existing contextual reviewed evidence, but stop overstating certainty when specificity metadata is absent.

## Existing replay tool and representative selection

The existing replay tool is `scripts/audits/scoring_applicability_2026_09_03/audit_corpus.py`.

Why it is the right tool:

- it reads source inputs from the original root corpus (`audit_corpus.py:22`, `:139-149`, `:216-234`);
- it can point implementation at a different checkout via `--implementation-root` (`audit_corpus.py:206-207`, `:245-255`);
- it supports explicit bounded replay via `--target-ids` (`audit_corpus.py:205`, `:239-245`);
- it records certification/evidence before/after details for review targets (`audit_corpus.py:183-195`).

Current built-in deterministic selection policy:

- one lowest `sha256("20260903:"+id)` winner per `(brand_dir, _v4_module)` bucket (`audit_corpus.py:219-233`);
- plus every submission id beginning `PG_SUB_`;
- plus explicit canaries/review targets (`audit_corpus.py:25-26`, `:228-232`).

For a bounded 30-50 product certification/rubric replay, the cleanest reuse is:

1. keep the existing selector logic;
2. derive a deterministic subset from that selector output;
3. pass those IDs via `--target-ids` so the replay stays source-bound and reproducible.

### Superseded cross-module 30-ID subset — do not use

This subset was derived from the existing selector output, then sorted deterministically by `(module, brand, sha256("20260903:"+id))` and truncated to 30 IDs:

`239519,302660,242998,321377,307566,71700,60736,327564,46352,179966,4242,201100,313359,336846,204418,201215,239738,284189,211618,174855,253785,278554,251338,267566,302641,255590,178561,36250,273729,241684`

For the probiotic/certification-specific spot check, I would additionally force-include the six review targets already encoded in the audit runner:

`PG_SUB_35E0BD3374BF494B80FEABE87FC559E7,299239,250851,327965,307727,326762`

That yields a deterministic 36-ID replay without inventing a new selection rule.

## Open items intentionally left incomplete

1. I did not classify all 534 reduced Verification rows.
2. I did not run any operational rebuild or full replay from this thread.
3. I did not propose a production fix; this report only documents the execution path and bounded implications.

## 2026-09-04 addendum: live NSF check for Garden of Life `326762`

Scope of this addendum:

- primary external source: current NSF Dietary Supplement listing only
- local label source: root corpus cleaned/enriched payloads for `326762`
- no inference from other retailer pages, archived pages, or non-NSF registries

### Live NSF source

As of Friday, September 4, 2026, NSF still lists the following on its primary Dietary Supplement registry page:

- company/listing page: `https://info.nsf.org/Certified/Dietary/Listings.asp?Company=C0266676&Standard=173`
- registry entry text observed on that page:
  - `WF Dr. Formulated Probiotic 100B`
  - form `Capsule`
  - manufacturer's recommended daily serving size `1 Capsule`

This matches the cached registry row already present in `scripts/data/cert_registry.json:41835-41846`.

### Local label facts for `326762`

Root corpus label facts from `/Users/seancheick/Downloads/dsld_clean/scripts/products/output_Garden_of_life/cleaned/cleaned_batch_2.json`:

- id `326762`
- brand `Garden of Life Dr. Formulated`
- full name `Probiotics 100 Billion`
- UPC `6 58010 13179 7`
- product version code `DFP100BL-012522`
- net contents `30 Vegetarian Capsule(s)`
- serving size `1 Capsule(s)`
- no `WF` token in `fullName`
- no `WF` or `Whole Foods` mention in the saved label statements

The enriched root payload carries the same identity fields.

### Match conclusion

Current evidence proves:

- same potency band: yes, `100B`
- same dosage form: yes, capsule / vegetarian capsule
- same serving cadence: yes, 1 capsule
- same broad line family: likely, both are Dr. Formulated probiotic capsule SKUs

Current evidence does **not** prove:

- that NSF's `WF` prefix is just a harmless alias for the exact `326762` SKU
- that the NSF row and local label share the same UPC
- that the NSF row and local label share the same product version / edition
- that the NSF row is not a retailer-specific or alternate-edition member of the same family

Bounded decision: `326762` remains **unresolved**, not exact-proven.

That means I do **not** recommend authoring a verified per-product override for `326762` from the current evidence set. A safe override would need an exact same-SKU proof source, such as:

- NSF detail page or backing document with UPC / item code / version evidence, or
- a first-party label/source document showing `WF Dr. Formulated Probiotic 100B` and the same UPC `658010131797` / version `DFP100BL-012522`.

Without that proof, the resolver should continue to withhold scoring authority for this row.

## 2026-09-04 addendum: probiotic-only representative replay set

The earlier 30-ID list was not appropriate for probiotic review because it was truncated from a cross-module selector. This addendum replaces it with a probiotic-only deterministic sample derived from the actual scored corpus.

### Population scanned

- total probiotic scored rows observed: `551`
- source: all files under `/Users/seancheick/Downloads/dsld_clean/scripts/products/output_*_scored/scored/*.json`
- inclusion rule: `_v4_module == "probiotic"`

### Deterministic selection method

1. Build the full 551-row probiotic population from scored artifacts.
2. Bucket each row by observed scored-artifact fields:
   - CFU band: `unknown`, `none`, `0_9`, `10_49`, `50_99`, `100_plus`
   - native matched-strain count band from formulation metadata:
     - `clinical_unknown`
     - `clinical_0`
     - `clinical_1_3`
     - `clinical_4_plus`
   - dose basis:
     - `per_strain_cfu_disclosed`
     - `aggregate_cfu_modeled_proxy`
     - `no_cfu_adequacy_credit`
     - `direct_strain_mass_no_cfu_floor`
     - `unknown_dose_basis`
3. Select one deterministic representative per bucket using `sha256("20260904-probiotic:"+id)`.
4. Force-include the six required review targets:
   - `PG_SUB_35E0BD3374BF494B80FEABE87FC559E7`
   - `299239`
   - `250851`
   - `327965`
   - `307727`
   - `326762`
5. Fill to 42 rows with deterministic brand-diverse additions, then deterministic remainder.

This produces a bounded probiotic-only review set without inventing any new manual sampling rule.

### Observed coverage in the 42-ID probiotic set

- CFU bands:
  - `0_9`: 19
  - `10_49`: 10
  - `50_99`: 3
  - `100_plus`: 5
  - `none`: 3
  - `unknown`: 2
- Native matched-strain count bands:
  - `clinical_0`: 10
  - `clinical_1_3`: 22
  - `clinical_4_plus`: 8
  - `clinical_unknown`: 2
- Dose-basis coverage:
  - `aggregate_cfu_modeled_proxy`: 17
  - `per_strain_cfu_disclosed`: 11
  - `no_cfu_adequacy_credit`: 11
  - `direct_strain_mass_no_cfu_floor`: 1
  - `unknown_dose_basis`: 2

Interpretation:

- the set includes the six required products
- it includes high-CFU probiotic anchors, low-CFU consumer gummies/chewables, zero/unknown-CFU negatives, aggregate-proxy cases, per-strain disclosed cases, one direct-mass-floor case, and two unknown-code / nonstandard cases
- formula-backed cases are not richly surfaced as a scored-artifact stratum in the 551-row baseline; the forced Seed submission remains the explicit studied-formula representative in this set

### 42 probiotic review IDs

`213086,180210,178453,178450,278521,19171,18201,200928,250864,250851,250859,267569,246009,207050,250917,250916,82389,250224,178848,206314,326762,222763,233085,267301,297695,28961,276704,307727,287478,287475,239178,54459,205129,273450,327965,245992,299239,PG_SUB_35E0BD3374BF494B80FEABE87FC559E7,217189,80971,79324,328844`

### 42 probiotic review rows

| ID | Brand | Product | CFU band | Native strain band | Dose basis |
| --- | --- | --- | --- | --- | --- |
| `213086` | Airborne | Airborne + Probiotic Assorted Fruit Flavors | `0_9` | `clinical_1_3` | `no_cfu_adequacy_credit` |
| `180210` | Airborne Plus | Probiotic Assorted Fruit Flavors | `0_9` | `clinical_1_3` | `no_cfu_adequacy_credit` |
| `178453` | Bayer One A Day | TruBiotics with Immune Support Advantage | `0_9` | `clinical_1_3` | `aggregate_cfu_modeled_proxy` |
| `178450` | Bayer One A Day | TruBiotics | `0_9` | `clinical_1_3` | `aggregate_cfu_modeled_proxy` |
| `278521` | CVS Health | Adult Probiotic Gummies Strawberry | `0_9` | `clinical_1_3` | `per_strain_cfu_disclosed` |
| `19171` | CVS Pharmacy | Probiotic Acidophilus | `0_9` | `clinical_1_3` | `no_cfu_adequacy_credit` |
| `18201` | CVS Pharmacy | Digestive Probiotic | `0_9` | `clinical_0` | `aggregate_cfu_modeled_proxy` |
| `200928` | Centrum | Centrum Multi + Probiotics Adults 50+ | `0_9` | `clinical_0` | `no_cfu_adequacy_credit` |
| `250864` | Culturelle | Digestive Daily Probiotic | `10_49` | `clinical_1_3` | `per_strain_cfu_disclosed` |
| `250851` | Culturelle | Digestive Daily Probiotic | `10_49` | `clinical_1_3` | `per_strain_cfu_disclosed` |
| `250859` | Culturelle | Digestive Daily Probiotic | `10_49` | `clinical_1_3` | `per_strain_cfu_disclosed` |
| `267569` | Culturelle | Ultimate Balance for Antibiotics | `none` | `clinical_1_3` | `direct_strain_mass_no_cfu_floor` |
| `246009` | Culturelle Baby | Baby Calm + Comfort | `0_9` | `clinical_1_3` | `per_strain_cfu_disclosed` |
| `207050` | Culturelle Digestive Health | Daily Probiotic Orange Chewables | `10_49` | `clinical_1_3` | `per_strain_cfu_disclosed` |
| `250917` | Culturelle Kids | Purely Probiotics Daily Chewables Bursting Berry Flavor! | `0_9` | `clinical_1_3` | `per_strain_cfu_disclosed` |
| `250916` | Culturelle Kids | Purely Probiotics Chewables Bursting Berry Flavor! | `0_9` | `clinical_1_3` | `per_strain_cfu_disclosed` |
| `82389` | Doctor's Best | Oral Probiotic Natural Strawberry Flavor | `0_9` | `clinical_0` | `no_cfu_adequacy_credit` |
| `250224` | Emergen-C | Probiotics + Orange | `0_9` | `clinical_1_3` | `per_strain_cfu_disclosed` |
| `178848` | Equate | Extra Care Probiotic | `10_49` | `clinical_1_3` | `aggregate_cfu_modeled_proxy` |
| `206314` | GNC Milestones | Baby Probiotic Drop Unflavored | `0_9` | `clinical_0` | `no_cfu_adequacy_credit` |
| `326762` | Garden of Life Dr. Formulated | Probiotics 100 Billion | `100_plus` | `clinical_4_plus` | `aggregate_cfu_modeled_proxy` |
| `222763` | Garden of Life Dr. Formulated CBD Probiotics | Inflammatory Response CBD 10 mg | `unknown` | `clinical_unknown` | `unknown_dose_basis` |
| `233085` | Garden of Life Dr. Formulated Probiotics | Women's Daily Care 40 Billion CFU Guaranteed | `10_49` | `clinical_1_3` | `aggregate_cfu_modeled_proxy` |
| `267301` | Garden of Life Dr. Formulated Probiotics | Mood+ 50 Billion Guaranteed | `50_99` | `clinical_4_plus` | `aggregate_cfu_modeled_proxy` |
| `297695` | Garden of Life Primal Defense | HSO Probiotic Formula | `0_9` | `clinical_4_plus` | `aggregate_cfu_modeled_proxy` |
| `28961` | Garden of Life Primal Defense | HSO Probiotic Formula | `none` | `clinical_1_3` | `no_cfu_adequacy_credit` |
| `276704` | HUM | Skin Heroes Pre+Probiotic | `none` | `clinical_4_plus` | `no_cfu_adequacy_credit` |
| `307727` | Jarrow Formulas | Saccharomyces Boulardii + MOS 5 Billion CFU | `0_9` | `clinical_1_3` | `per_strain_cfu_disclosed` |
| `287478` | MegaFood | MegaFlora Women's Probiotic | `50_99` | `clinical_1_3` | `aggregate_cfu_modeled_proxy` |
| `287475` | MegaFood | MegaFlora Plus | `50_99` | `clinical_0` | `aggregate_cfu_modeled_proxy` |
| `239178` | Nature's Bounty | Chewable Probiotic Acidophilus Natural Strawberry Flavor | `0_9` | `clinical_0` | `aggregate_cfu_modeled_proxy` |
| `54459` | Nature's Way | Primadophilus Intensive | `100_plus` | `clinical_0` | `aggregate_cfu_modeled_proxy` |
| `205129` | Nature's Way | Fortify Optima Probiotic Intensive 200 Billion | `100_plus` | `clinical_1_3` | `aggregate_cfu_modeled_proxy` |
| `273450` | Nature's Way | Fortify Men's Probiotic 30 Billion | `10_49` | `clinical_4_plus` | `aggregate_cfu_modeled_proxy` |
| `327965` | Nature's Way | Fortify Ultra Potency Optima Probiotic 100 Billion | `100_plus` | `clinical_4_plus` | `aggregate_cfu_modeled_proxy` |
| `245992` | Pure Encapsulations | PureBi-Ome G.I. | `10_49` | `clinical_0` | `aggregate_cfu_modeled_proxy` |
| `299239` | Ritual | Synbiotic+ | `10_49` | `clinical_1_3` | `aggregate_cfu_modeled_proxy` |
| `PG_SUB_35E0BD3374BF494B80FEABE87FC559E7` | Seed | DS-01 Daily Synbiotic | `unknown` | `clinical_unknown` | `unknown_dose_basis` |
| `217189` | Solgar | Advanced Acidophilus | `100_plus` | `clinical_0` | `no_cfu_adequacy_credit` |
| `80971` | Solgar | Advanced 40+ Acidophilus | `0_9` | `clinical_4_plus` | `no_cfu_adequacy_credit` |
| `79324` | Solgar | Advanced Multi-Billion Dophilus | `0_9` | `clinical_4_plus` | `per_strain_cfu_disclosed` |
| `328844` | Thorne | Women's Daily Probiotic | `10_49` | `clinical_0` | `no_cfu_adequacy_credit` |

Use this 42-ID set, not the earlier cross-module 30-ID truncation, for bounded probiotic replay/review.
