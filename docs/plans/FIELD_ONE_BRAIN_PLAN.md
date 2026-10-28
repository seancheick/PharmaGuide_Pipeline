# Field one-brain plan: evidence and dose clinical data

Status: Phase 1 census complete (October 28, 2026). Sean's rulings below replace the
recommendations in the item text where they differ.

## Sean's rulings, October 28

- **Items 1–5 are approved conditionally.** Before removing anything, confirm the values and
  every producer and consumer (fixtures included). Original signed records and approvals stay as
  they are. No Evidence, Dose, safety, readiness or app output may change unless it is intended.
  - Item 2: the predicate goes beside the clinical evidence schema. If the two fields disagree,
    validation must fail rather than whichever field is checked first winning.
  - Item 3: `highest_ul` stays distinct from the life-stage `data[].ul`. It must never stand in
    for the applicable age or pregnancy UL.
  - Item 4: rename only where the values state the same fact. The five records with both endpoint
    fields are reviewed one by one.
  - Item 5: normalize names without obscuring who signed what.
- **Item 6 is held.** Classify the 111 disagreements first, show that `dose_basis` is
  authoritative, and keep any provenance only `dose.basis` holds. Delete it only after that, with
  regression proof.
- **Item 7:** split the three meanings. `evidence_grade` is not publication design, so don't derive
  the app's meta-analysis badge from it. The 31 app badge cases are preserved, or any change is
  documented and validated. Pipeline and app change together.
- **Item 8:** retire `score_contribution` after checking every consumer and keeping the export
  versioned and compatible.
- **Item 9:** migrate the numbers and keep their source. A verified studied regimen stays
  attributed to its source and context. A studied amount never becomes a minimum effective dose.
  Unsupported numbers leave scoring and the public contract only after their provenance is kept.
- **Item 10:** separate the observed effect from the review result. The 46 `positive_moderate`
  judgments are kept as recorded until their typed meaning and scoring treatment are set. No
  Evidence eligibility may change unintentionally.
- **Item 11:** merge only representations that are truly duplicates. Registry-wide certainty,
  outcome-specific support and review status stay separate where they mean different things.
  Settle the three conflicting records individually, and keep the app contract stable.
- **Item 12: the merge into `health_goals_supported` is rejected.** Endpoints, studied
  conditions, measured outcomes, product purpose and consumer goals are different facts.
  - Reviewed contexts and signed applicability decisions are the scientific authority for
    supported outcomes.
  - Consumer goal categories come from an explicit, reviewed mapping.
  - Prose and tags may inform the UI but must never create Evidence eligibility on their own.
  - This is the highest-priority behavioral correction.
- **Additional work:**
  - Check the folate entry in the elevated-floor allowlist (folic-acid NTD evidence must not
    transfer to 5-MTHF).
  - Give `clinical_matches` an explicit, versioned export projection.
  - Move hard-coded Evidence magnitudes into `quality_score.json`, with the evidence-calibration
    session.
  - Settle what the 43 therapeutic `upper_limit` values mean before anything moves.
  - Re-verify the `study_design` and `evidence_level` overlaps against current main.
- **Prevention:**
  - Semantic field ownership in `source_of_truth_matrix.json`.
  - Strict curated-data schemas and cross-field invariants.
  - Export compatibility tests.
  - A CI ratchet with exact, per-path exceptions.

Lane boundaries: `generic_evidence.py` belongs to the evidence-calibration session while its
branch is changing it. That session declined the override deletion and the magnitude move for its
batch and handed both back to this lane, to do after its branch merges. Nothing edits the BCS or strain files until `claude/held-source-closure` merges.

## Progress, October 28 (branch `claude/xenodochial-matsumoto-ebd04b`)

| Item | State | Commit |
|---|---|---|
| 2 | Done. `clinical_evidence_schema.is_reference_only` serves all four call sites; `db_integrity` fails a record whose two fields disagree (0 today). | 9d5871522 |
| 3 | Done. Top-level `ul` and `unofficial_ul` removed from all 77 entries (76 nulls, plus boron's 20, which equals its `highest_ul`). The authority owner fact reports `highest_ul` as the adult maximum. The semantic fingerprint doesn't cover either key, and Flutter reads neither. | 720e95812 |
| 1 | Pipeline side done. One passthrough constant without the six dead keys; `facts_owned` names `max_studied_clinical_dose`. The `generic_evidence` override and magnitudes are handed to evidence-calibration. | 0d0548199 |
| 4 | Done for `effect` → `effect_direction` (39) and `design` → `study_type` (45), checked value for value, with a ratchet test. **Kept apart:** `primary_endpoint` names what was measured and `outcome` states what was found (the 5 records that hold both show this), so they are different facts. | 30d1f4a40 |
| 5 | Waits for held-source-closure (BCS). | |
| Therapeutic legacy fields retired | Done; see below. | (this commit) |

**Therapeutic legacy fields retired (Sean, October 28).**
- **Removed from all 43 records:** `upper_limit`, `typical_dosing_range`, `common_serving_size`
  and `evidence_tier`.
  - No pipeline, export or Flutter reader used them; only tests pinned them.
  - Every record's approved `reference_semantics` says its sources set no universal minimum,
    optimum or safety upper limit, and that is where the studied regimens live.
  - None of the 34 numerical upper limits was an established, applicable UL. The UL owner has
    no established UL for any of these ids; lutein is `not_established_insufficient_data`.
- **`upper_limit_notes` became `notes` (41 records):**
  - 29 carried over unchanged.
  - 12 edited to remove safe maxima, universal doses and preparation-equivalence claims.
  - 2 dropped (eggshell membrane, milk thistle), because they held only such claims and no
    caution.
  - Medication, pregnancy, bleeding, coumarin, cyanogenic, thyroid and immune cautions are kept,
    and a test pins 13 of them.
- **`common_use`:** dose thresholds and one comparative-bioavailability claim removed in 3 records.
- **Receipt:** per-record old values and dispositions are in
  `scripts/audits/field_one_brain_20261028/therapeutic_legacy_fields_receipt.json`.
- **Guards:**
  - `db_integrity_sanity_check.check_rda_therapeutic` rejects the five retired keys. On the old
    data it reports 215 findings; on the candidate, 0.
  - `test_retired_dose_and_ceiling_fields_stay_retired` also rejects generic safe-maximum and
    universal-dose wording.
- **Docs:** `DATABASE_SCHEMA.md` §27 and `_metadata` (schema 5.1.0) now describe the actual
  meaning.

**Candidate checkpoint (b070650b0 plus records).**
- Replay of 1,111 frozen products: 0 differ from main.
- Local rung with the real corpus: 536 passed, 24 declared opt-in skips, and 10 failures in the
  `e1_2_2` canaries against the 2026-10-18 baseline.
  - The failures already exist on main. Fresh canary rebuilds from main e6885790d are identical
    to the candidate's.
  - The main checkout passes only because its `reports/canary_rebuild` files date from
    2026-10-18.
  - The baseline needs a reviewed refresh before release. LEDGER has the details.
- Final source commit c20edc773: the replay changes 0 of 1,111 products. The collagen, gelatin and
  UC-II approved-purpose edits are editorial corrections (Sean, October 28) with no new approval.
  Canary drift is itemized in `scripts/audits/field_one_brain_20261028/canary_baseline_drift.md`.

**Replay (items 1–4).**
- Inputs: the 1,111-product frozen raw set at `~/pg_quality/held_closure_20261028/frozen`.
- Baseline: main e6885790d (`base.jsonl` from the held-source session).
- Candidate: 30d1f4a40 (`~/pg_quality/field_one_brain_20261028/cand.jsonl`, run from clean through
  enrich to score).
- Result: 0 of 1,111 products differ in any captured field (total, pillars, status, route,
  reasons, purpose), and `compare` returns an empty delta.
- Fresh-context review of the four commits found no defects.
- `scripts/test.sh local` had 0 failures (409 passed), but it refuses the run because this
  worktree has no corpus or build (161 skips on missing local data). It must be re-run from a
  checkout that has the corpus.
- Release note: the app's bundled `assets/reference_data/rda_optimal_uls.json` still matches the
  file before 720e95812. The reference-data sync (`scripts/sync_flutter_reference_data.py`,
  checked by `preflight.py`) has to run before an app release.
- Limit: the capture ran without `--full --blob`, so it doesn't prove byte equality of the enriched
  record or the detail blob. No curated record carried the removed passthrough keys, and the
  removed UL keys were never exported.

**Item 6 classification (read-only; deletion still held).** All 160 legacy `dose.basis`
contexts have `context_schema_version` 1.1.0, and `dose_basis` wins whenever both are present.
The 111 disagreements fall into two groups:
- **104 are `unresolved`.** That was the extraction-state placeholder before schema 1.1.0, and
  `dose_status` now records the same state: source_not_reported 29, extraction_pending 37,
  verified 30, combination_total_only 7, conflicting_source_values 1.
- **7 are `discrete_daily_arms`.** In each, `dose_basis` is the more specific value
  (`combination_total_daily` in 6 and `measured_viability` in 1).

Neither group holds information the frozen fields lack. These contexts are clinician-signed and no
hash binds them, so the proposal is: write the 160 `(context_id, dose.basis)` pairs to an audit
receipt, then delete the field and the fallback. Sean approves before it lands.

**Folate elevated floor: reproduced.** The `_CONSENSUS_GOLD_STANDARD` entry `vitamin_b9_folate`
(justified by folic-acid NTD consensus) only ever reaches `INGR_FOLATE_MTHF`. That record is a
biomarker/PK `rct_single`, and its single context is pending review. The entry lifts the floor
from 11 to 17.
- Live probe on main code: dsld 284181 "5-MTHF 1 mg" has a floor of 17.0.
- 11 stored products carry it: Pure Encapsulations 184302, 184894, 184899, 246424, 293963,
  293964 and 299031; Thorne 284181, 284182 and 337850; Life Extension 232417.
- **Resolved on `claude/serene-dubinsky-479574` (evidence-calibration lane), commit 37d74d5b1.**
  It deletes the whole allowlist, so an elevated floor now needs a replicated reviewed body.
  Verified with `git grep _CONSENSUS_GOLD_STANDARD claude/serene-dubinsky-479574`. That lane
  measured the 11 products dropping from 18.9 to 12.2 Evidence. Folate keeps only the 10-point
  DRI nutrition-authority floor.
- After that branch merges, this lane rebases onto it (lines 117–150 changed) and then takes
  the `base_points`/`multiplier` override deletion and the move of
  `STUDY_TYPE_BASE_POINTS`/`EVIDENCE_LEVEL_MULTIPLIERS` into config. The evidence-calibration
  session handed both back to this lane on October 28, together with routing
  `generic_evidence.py:718`'s `study_type`-only reference check through
  `clinical_evidence_schema.is_reference_only`. Its batch head is 6ff44af2e, and it confirmed
  the 11 folate products are exactly its measured movers (Evidence 18.9 → 12.2; for example,
  284181 goes from 97.9 to 91.2). `study_type_vocab.json` also carries `base_points`, pinned by
  `test_study_type_vocab_contract`.

**Therapeutic `upper_limit` (read-only).** Of 43 entries, 34 hold a value and 9 are null. None of
the 34 is a sourced UL:
- 15 equal the top of the typical range.
- The rest are unsourced ceilings (for example ashwagandha 1000 and curcumin 8000).
- The 9 nulls follow the reviewed pattern "A safety upper limit is not established by …".
- Lutein contradicts the UL owner: 40 mg here, but `rda_optimal_uls` says
  `not_established_insufficient_data`.

Sean decided (October 28): retire the field, don't null it, and review the related descriptive
fields in the same batch. That work is done in the "Therapeutic legacy fields retired" entry
below.

Scope: `backed_clinical_studies.json` (BCS, 210 records), `clinically_relevant_strains.json`
(132), `literature_evidence_records.json` (816), `rda_therapeutic_dosing.json` (44),
`rda_optimal_uls.json` (77), the Evidence/Dose blocks of `quality_score.json`, and their readers
in the pipeline and in the Flutter app (`/Users/seancheick/PharmaGuide ai/lib`).

Census base: `origin/main` = `e6885790d`. Counts below come from that tree. Re-run each evidence
command before acting, because `claude/held-source-closure` and later merges will move them.

## Owner Check

- Owner of clinical-record fields: `scripts/clinical_evidence_schema.py` (context schema 1.1.0)
  and `scripts/db_integrity_sanity_check.py` (record enums). Evidence:
  `rg -n "study_design|scoring_eligible|dose_basis" scripts/clinical_evidence_schema.py`.
- Owner of numerical dose meaning: `reference_semantics` in each data file, checked by
  `scripts/dose_assessment.py::_positive_clinical_benchmark_records` and
  `schemas/dose_reference_semantics.schema.json`. Evidence:
  `rg -n reference_semantics scripts/dose_assessment.py`.
- Owner of evidence magnitudes: `quality_score.json` `evidence_magnitudes.generic` (being
  recalibrated by the evidence-calibration session).
- Matrix: no concept owns the clinical vocabularies themselves (`evidence_level`,
  `effect_direction`, `study_type`). Searched `source_of_truth_matrix.json` for the four data
  files; it lists only `scoring_input_contract`, `quality_pillars_v4_contract`,
  `product_level_scoring_evidence`, `prebiotic_identity` and `clinical_exposure_assessments`.
- Export seam: `build_final_db.py:8066` ships `evidence_data.clinical_matches` verbatim, so every
  key the enricher passes through (`enrich_supplements_v3.py` ~16335 and ~16446) is in the public
  detail blob.
- Will NOT create: a new field, registry, vocabulary file or scorer. Every merge below deletes
  or renames toward an existing owner. The two places that would need a new name (items 11 and
  12) are left to Sean.

## How to read each item

Class follows AGENTS.md "One brain": **false dual brain** (same meaning, two homes: delete the
weaker), **one policy, many consumers** (keep, share one result), **two policies, one topic**
(keep both, unify the contract). "One name, two meanings" is the reverse defect: split it.

## A. Safe merges (no score, safety or export change expected)

### 1. Dead passthrough keys and a magnitude override nobody uses
- Fields: `max_clinical_dose`, `max_studied_dose`, `typical_effective_dose`, `base_points`,
  `multiplier`, `computed_score`.
- Evidence: zero BCS records carry any of them (census:
  `python3 -c "import json;d=json.load(open('scripts/data/backed_clinical_studies.json'))['backed_clinical_studies'];print({k:sum(k in r for r in d) for k in ['max_clinical_dose','max_studied_dose','typical_effective_dose','base_points','multiplier','computed_score']})"`).
  The enricher copies them in two duplicated `optional_fields` lists.
  `generic_evidence._entry_raw_points` lets a record's `base_points`/`multiplier` override the
  configured magnitudes, which would be a second home for scoring numbers.
  `evidence_resolver.OWNER_CAPABILITY_MAP` claims BCS owns `max_clinical_dose`, which no record has.
- Class: false dual brain (dead copies).
- Move: delete the six keys from both passthrough lists and fold the two lists into one module
  constant; delete the override branch in `_entry_raw_points`; change `facts_owned` to
  `max_studied_clinical_dose`.
- Consumers: `enrich_supplements_v3.py`, `scoring_v4/modules/generic_evidence.py`,
  `evidence_resolver.py`. Flutter reads none of them.
- Risk: low. The replay must show zero diff. The `generic_evidence.py` edit is in the
  evidence-calibration lane, so agree the order with that session first.

### 2. "Reference-only" is decided in two fields
- Fields: BCS `study_type == "reference"` and `evidence_level == "reference"`.
- Evidence: all 45 reference records carry both values together. Four call sites in two files test both:
  `rg -n '"study_type", "evidence_level"' scripts` (`evidence_resolver.py:404`, `:941`;
  `clinical_applicability.py:492`, `:573`).
- Class: one policy, many consumers.
- Move: one helper, `clinical_evidence_schema.is_reference_only(entry)`, called by all four
  sites, plus an integrity rule that the two values agree. No data change.
- Risk: low.

### 3. Three upper-limit names in `rda_optimal_uls.json`
- Fields: top-level `ul`, `unofficial_ul`, `highest_ul`, and per-group `data[].ul`.
- Evidence: only boron has `ul` and `unofficial_ul` (20 each, equal to its `highest_ul`).
  `unofficial_ul` has zero readers. `evidence_resolver.py:877` puts top-level `ul` into
  `owner_facts` (null for 76 of 77 nutrients) and also reads a `category` key the file doesn't have.
- Class: false dual brain.
- Owner: `highest_ul` for the adult top value; `data[].ul` per life-stage group.
- Move: delete `ul` and `unofficial_ul` from boron; point `owner_facts` at `highest_ul` and drop
  `category`. Leave `cdrr` alone (sodium's CDRR is a different meaning).
- Consumers: `evidence_resolver.py`, `verify_rda_uls.py`, `reference_data_contract.py` (which
  reads `data[].ul`, so it is unaffected). Nothing exports `owner_facts`.
- Risk: low. This deletes data, so **Sean** approves the two boron keys.

### 4. Field renames inside the literature records' study lists
- Fields: `qualifying_human_studies[]` has `effect` (39) beside `effect_direction` (176), `design`
  (45) beside `study_type` (234), and `primary_endpoint` (39) beside `outcome` (266). No study has
  both names of a pair except 5 with `primary_endpoint` and `outcome`.
- Evidence: the census above. No production code reads these sub-fields; `evidence_resolver`
  reads only `pmid`, and the verifiers read `pmid` and `title`.
- Class: false dual brain (rename drift).
- Move: `effect` → `effect_direction` and `design` → `study_type`, through `data_batch.py check`
  with one result per entry. `primary_endpoint` stays separate from `outcome`: the value review
  showed it names what was measured, while `outcome` states what was found.
- Risk: low; data-only, and no consumer changes.

### 5. Two notes keys on BCS references, and a reviewer-name spelling
- Fields: `references_structured[].note` (54) and `.notes` (40), never both on one reference.
  `study_contexts[].clinical_review.reviewer` is "Dr. Pham" (49) or "Dr Pham" (4).
- Class: false dual brain (rename drift) and vocabulary drift.
- Move: `note` → `notes` (AGENTS.md reuses `notes`); normalize the reviewer to one spelling, which
  **Sean** picks. Check `probiotic_measurements.py` and `build_final_db.py` (`"reviewer"`,
  `"note"`) before the commit; they appear to read other objects.
- Risk: low.

### 6. `dose.basis` beside `dose.dose_basis` in study contexts
- Evidence: 159 strain contexts and 1 BCS context carry both, and 111 strain contexts disagree.
  `probiotic_measurements.py:~685` already says `dose_basis` wins whenever it is present, and all
  160 have it, so `dose.basis` never decides anything.
- Class: false dual brain, with a legacy copy that contradicts the owner.
- Move: delete `dose.basis` from the 160 contexts, and the fallback
  `return dose.get("basis")`, once a fail-first test pins `dose_basis` as the only input.
- Risk: zero behavior expected; replay to prove it. This deletes curated data, so it needs
  **Sean**, and it waits for `claude/held-source-closure` (which edits the strain file).

## B. Merges that change a public field or need a clinical decision

### 7. `published_studies` means three different things (split it)
- Evidence: 465 string entries. 458 are design labels ("RCT" 185, "meta-analysis" 87,
  "systematic_review" 79, "mechanistic", "animal", "brand"…). 7 are PMIDs, and all 7 are already in
  `references_structured`. None are integers.
- Readers, one per meaning:
  - `clinical_applicability.py:504` and `evidence_resolver.py:581` read it as a PMID list.
  - `generic_evidence._published_study_count` reads it as a count, through an integer branch no
    record reaches.
  - Flutter `evidence_section.dart::_hasMetaAnalysisSignal` reads it as design text.
- Class: one name, three meanings.
- Owners: PMIDs → `references_structured[].pmid`; publication design → the record's `study_type`
  and each reference's PubMed `publication_types`; count → `published_studies_count`.
  `evidence_grade` is certainty, not publication design (Sean's ruling).
- Move: delete `published_studies` from the 210 records, the passthrough and the three pipeline
  readers. In Flutter, keep the meta-analysis badge on a publication-design source. Any change to
  the 31 affected badge cases must be documented and validated before it ships.
- Measurement: 31 records get their meta signal in Flutter only from `published_studies`. Before
  the change, check that those 31 reach the same Evidence-section tier from `evidence_grade`.
- Risk: medium. It is a public blob field read by Flutter, so both repos change together.
  **Sean** approves the contract change.

### 8. `score_contribution` is a stale copy of a scorer decision
- Evidence: values are tier_1 156, tier_2 27, tier_3 24 and null 3. The scorer never reads it
  (`rg -w score_contribution scripts --type py`: only the integrity enum check and the
  passthrough). It contradicts the scorer: the 45 reference records score 0 points, yet 14 of them
  are tier_1. Flutter has `score_contribution_tier_vocab.json`, but no widget reads the field from
  a match.
- Class: false dual brain.
- Move: delete the field, its passthrough and enum check, and the unused Flutter vocab file and
  loader.
- Risk: low on behavior, but it removes a blob field, so it needs **Sean**.

### 9. BCS dose numbers that the dose-meaning owner says are not benchmarks
- Fields: `min_clinical_dose` (11), `max_studied_clinical_dose` (10), `dose_unit` (11) and
  `dose_range` (3, prose).
- Evidence:
  `python3 -c "import sys;sys.path.insert(0,'scripts');import dose_assessment as d;print(len(d._positive_clinical_benchmark_records()))"`
  prints 0. Every one of the 11 records' `reference_semantics.reference_type` is
  `discrete_studied_regimen` (KSM-66, lactoferrin, Carnipure, OptiMSM, MSM, Tesnor) or
  `no_benchmark` (L-carnitine, ALCAR, BCAA, L-arginine, Sytrinol), so Dose never uses these numbers.
  They still ship in the blob, though no Flutter code reads them. Some repeat
  `rda_therapeutic_dosing.typical_dosing_range` (ashwagandha 250–600 = KSM-66 250/600).
  `studied_regimens` (4 records) is the structured owner of studied-regimen bounds.
- Class: two policies, one topic. Approved `reference_semantics` versus older numbers.
- Recommendation: delete the four fields from those 11 records and the passthrough. Keep the
  `_positive_clinical_benchmark_records` code path: it is a dormant data-driven gate that a future
  approved `supported_minimum` would use.
- Alternative: move the 6 `discrete_studied_regimen` bounds into `studied_regimens` with notes.
  That would add new studied-regimen display rows, so it is a separate source-verified batch.
- **Sean**: deletion, or migration into `studied_regimens`.

### 10. Literature `effect_direction` also stores the review result (split it)
- Evidence: of 816 values, 132 are effects (positive_moderate 46, positive_weak 43, mixed 18,
  null 12, negative 8, positive_strong 5). The other 684 are review results:
  applicability_unestablished 363, no_qualifying_human_evidence 152, not_efficacy_relevant 144,
  identity_material_unresolved 25. Those duplicate `applicability_status` (613 present).
  `evidence_resolver.py` (step 7) and `verify_semantic_applicability.py` branch on both kinds.
- Class: one name, two meanings.
- Move: the review result lives only in `applicability_status`. For the 203 records that lack
  it, copy today's `effect_direction` only when that value is a review result
  (applicability_unestablished, no_qualifying_human_evidence, not_efficacy_relevant,
  identity_material_unresolved). Effect values such as `positive_moderate` are never copied. `effect_direction` keeps only the effect
  vocabulary, or null. Update the two readers.
- Vocabulary drift: `positive_moderate` exists only in the literature records and in
  `dose_assessment._POSITIVE_BENCHMARK_DIRECTIONS`. It isn't in BCS, the strain file, the
  `quality_score.json` multipliers or the Flutter vocab. Literature records are not scored by the
  multiplier, so this changes no score today.
- **Sean**: whether `positive_moderate` joins the shared vocabulary, or each one is mapped to
  weak or strong. Mapping them is a clinical call.
- Risk: medium, because it touches the resolver's dispositions. The replay must show zero
  disposition change.

### 11. Strain evidence grade spelled three ways
- Fields: registry `evidence_level` (none 78, low 26, moderate 21, high 7),
  `cfu_thresholds.evidence.evidence_strength` (strong/medium/weak, 34) and
  `cfu_thresholds.evidence.clinical_support_level` (high/moderate/weak, 22).
- Evidence:
  - Code translates between the spellings at read time:
    `enrich_supplements_v3._derive_clinical_support_level` and `studied_formulas.py:728`
    (`clinical_support_level or evidence_strength`, mapping strong→high and medium→moderate).
  - All 22 stored `clinical_support_level` values equal the mapped `evidence_strength`.
  - `evidence_level: none` always pairs with `literature_review.conclusion:
    no_qualifying_human_evidence` (78 of 78).
  - One record has `evidence_level` moderate but `evidence_strength` weak, and two have
    `evidence_level` high with no strength recorded.
- Class: false dual brain.
- Move: delete the stored `clinical_support_level`. The enricher keeps deriving it, and the
  exported field Flutter reads at `probiotic_section.dart:97` stays. Make `evidence_strength` the
  only stored grade. Leave `evidence_level` as the registry-wide review state until the three
  disagreeing records are settled.
- **Sean** or Dr Pham settles those three records. Waits for `claude/held-source-closure`.
- Related: the enricher copies the strain grade into `probiotic_data.clinical_strains[].evidence_level`.
  That is the same key `clinical_matches[].evidence_level` uses with the BCS scope vocabulary.
  Renaming the strain copy is a new export name, so it needs **Sean**.

### 12. One meaning ("what the evidence supports") in five fields
- Fields: `primary_outcome` (176, goal labels), `health_goals_supported` (210, goal labels),
  `endpoint_relevance_tags` (210, tags), `key_endpoints` (210, free text) and
  `applicability.supported_outcomes` (31).
- Evidence:
  - `evidence_resolver._evidence_entry_purposes` joins the first four into one string for
    `evidence_indication_categories`, which then drives purpose matching. That can move Evidence
    points.
  - 22 `primary_outcome` values are not among their record's goals.
  - The tag vocabulary drifts (joint_pain/joint_health, eye_health/eye_vision,
    digestive/digestive_health, cardiovascular/cardiovascular_health, muscle_growth/
    muscle_strength/muscle_recovery) and doesn't map one-to-one onto goals (`glycemic_control`
    co-occurs most with Cardiovascular, not Blood Sugar).
  - `supported_outcomes` has two meanings. As a join key against `study_contexts[].condition`
    (`clinical_applicability.py:606`) it matches in only 5 of 31 records. The other 26 hold goal
    labels, tags or prose, and are read as purpose text.
  - Flutter reads none of these fields from a match.
- Class: two policies on one topic (goals versus tags), plus one name with two meanings.
- Recommendation:
  - `health_goals_supported` is the only purpose owner, in the app's `user_goals` vocabulary.
  - Fold each `primary_outcome` into goals, then delete it.
  - Remove the tags from purpose derivation and delete them once the replay shows no purpose loss.
  - Keep `key_endpoints` as provenance text only.
  - Restrict `supported_outcomes` to condition ids that exist in the record's contexts.
- **Sean**: this can move scores through purpose matching, so it needs the `/pg-scoring-change`
  procedure. If Sean wants the purpose half of `supported_outcomes` kept under its own name, that
  is a new field.

## C. Kept as they are, with the reason

- `scoring_eligible` at record, context and reference level: it means the same thing at each
  level ("may this object earn affirmative credit"), and `clinical_applicability.py:480-560` plus
  `evidence_resolver.clinical_record_sources_eligible` combine the three. One policy, many
  subjects. Keep.
- `unit` beside `reference_semantics.units`: equal in 77 of 77 UL entries and 44 of 44
  therapeutic entries. The semantics block is the hashed approval record (`reference_semantics_sha256`), so its
  unit is provenance. Keep both and add an integrity test that they are equal.
- `ui_evidence_scope` is computed from `evidence_level` by one helper. One policy, many
  consumers.
- `rda_therapeutic_dosing` legacy fields: retired on Sean's October 28 decision (see Progress).

## D. Out of scope here (follow-ups)

- `evidence_level` also names interaction-rule strength and IQM form evidence. Flutter already
  splits the interaction meaning (`evidence_strength_vocab.dart`). This belongs to the
  interaction-rules work.
- `STUDY_TYPE_BASE_POINTS` and `EVIDENCE_LEVEL_MULTIPLIERS` are hard-coded magnitudes in
  `generic_evidence.py:64-88`, breaking the "every magnitude in `quality_score.json`" rule. The
  multipliers also carry alias spellings (`product_rct`, `product`…) that no data uses. Hand this
  to the evidence-calibration session.
- Context `study_design` is free text in BCS (93 distinct values) but an enum in the strain file
  (`studied_formulas.py:1000`), under the same schema version 1.1.0. That needs a per-context
  clinical classification batch.

## Phase 2 order and gates

Preconditions: Sean approves this plan, and `claude/held-source-closure` has merged to `main`.
That branch touches the strain file today and is expected to rewrite BCS records. Before editing
`generic_evidence.py` or `quality_score.json`, message the evidence-calibration session.

| Commit | Item | Files | Gate |
|---|---|---|---|
| 1 | 1 dead keys and override | enricher, generic_evidence, evidence_resolver | fail-first test, focused tests, replay zero diff |
| 2 | 2 reference-only helper | evidence_resolver, clinical_applicability, integrity | focused tests, replay zero diff |
| 3 | 3 UL names | rda_optimal_uls, evidence_resolver | data_batch check, focused tests |
| 4 | 4 literature study renames | literature_evidence_records | data_batch check, verifier dry-run |
| 5 | 5 notes and reviewer | BCS | data_batch check, replay zero diff |
| 6 | 6 `dose.basis` | strains, BCS, probiotic_measurements | fail-first test, replay zero diff |
| 7+ | 7–12 per Sean's decisions | per item | full behavioral gate; both repos for 7 and 8 |

Each commit:
- covers one class;
- applies data through `scripts/data_batch.py`, with a per-entry list;
- names its owner and consumer tests;
- runs focused rungs only (`scripts/test.sh fast <files>`).

The finished candidate gets:
- one replay (`scripts/audits/quality_redesign/replay.py` freeze-raw → snapshot → compare), on
  the labels touched by items 7, 9, 10 and 12 plus unaffected controls;
- `scripts/test.sh local`;
- green `pipeline-tests` CI.

Expected movement is zero for items 1–6 and 8. Items 7, 9, 10 and 12 must show a reviewed reason
for every change.
