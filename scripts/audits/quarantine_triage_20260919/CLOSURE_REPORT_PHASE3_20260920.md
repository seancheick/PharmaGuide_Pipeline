# Phase-3 Engineering Closure Report

Date: 2026-09-20
Role: lead engineering closer (Phase-3 remediation + evidence/scoring integration)
Scope: close the engineering phase end-to-end and land it on `main`.

Baseline at session start: `origin/main` = `ad577f49` (unchanged all session).
`main` moved twice during the session, both times by the integration owner — see §A.

---

## A. Repository

| Item | Value |
|---|---|
| Starting `main` / `origin/main` | `ad577f49` |
| `main` observed mid-session | `6f2bdc80` (fast-forward of the integration lineage) |
| `main` at closure | `236a9dc1` |
| Evidence-seam commits (all already on `main`) | `a8213c63` (canonical assessable-evidence contract + probiotic ownership), `6f2bdc80` (probiotic A/B report), `236a9dc1` (universal evidence resolver + shadow coverage) |
| Closure candidate | `closure/phase3-final-20260920` = `main` + this session's closure commit |
| Conflicts / reconciliations | **None.** The closure branch was rebased onto `main` twice as `main` advanced; the closure commit touches only tests and audit docs, so both rebases were clean and the exact-tree equality below held at each step. |

### Why "the seam" was already on main

At session start the evidence work existed as commits on the remediation lineage
(`31200ee8` + `f1410ee3`). Independently, the integration owner cherry-picked the same
content into the integration lineage (`a8213c63` + `6f2bdc80`) and fast-forwarded `main`
to it, then added `236a9dc1`.

**Proof the two are the same content:** `git rev-parse d9b66618^{tree}` (my closure
branch's base, which had the seam cherry-picked by me) equals `git rev-parse 6f2bdc80^{tree}`
(their lineage) — both `e04ea2cb420fcd96a83bf013ebddf47edc83514c`. No parallel content
diverged, so the closure branch was simply re-based onto their lineage rather than merged.

### The closure commit changes zero pipeline files

Committed-blob manifest over `scripts/*.py` + `scripts/scoring_v4/*.py` + `scripts/data/*.json`:

| Ref | Files | Manifest |
|---|---:|---|
| `095d27a1` (replay "before") | 266 | `833eebcaf075a1bc…` |
| `6f2bdc80` | 266 | `8434f879d07503ec…` |
| `main` (`236a9dc1`) | 267 | `f6aed1aee2ea1c48…` |
| closure tip | 267 | `f6aed1aee2ea1c48…` ← **identical to main** |

This is the guarantee that the replay below describes the code that ships: the closure
commit is documentation + tests only, so the arm's pipeline and `main`'s pipeline are the
same 267 blobs. (`main` differs from `6f2bdc80` by exactly one added file,
`scripts/evidence_resolver.py`, which nothing in the pipeline imports.)

### Remote

- `origin/main` was `ad577f49` and an ancestor of `main` throughout → clean fast-forward.
- Pushed and verified; see §H for the final value.

---

## B. Tests

### Focused validation run this session

| Suite | Result |
|---|---|
| `test_scoring_source_of_truth_audit.py` | **23 passed** — the pre-existing `V4_IQD_INGREDIENTS_FALLBACK` failure is **gone** |
| raw static-audit census (`audit_source_of_truth_contract.py scoring-static`) | `OK: scoring-static source-of-truth audit passed` — **0 findings** |
| `test_standardization_marker_generalization.py` (new, 5 tests) | **5 passed** |
| `test_cross_module_probiotic_evidence.py` — clean worktree (no corpus) | **1 passed / 7 skipped**, 0 failed |
| `test_cross_module_probiotic_evidence.py` — shared checkout (corpus present) | **8 passed** |

### Full fast tier

Run on the final closure candidate in a clean dedicated worktree at the closure tip
(`scripts/test.sh fast`; counts and sanitised skip census preserved as
`FAST_TIER_CLOSURE_20260920.md` alongside this report):

```
15825 passed, 196 skipped in 352.95s (0:05:52)
```

| | Count |
|---|---:|
| passed | **15,825** |
| **failed** | **0** |
| skipped | 196 |
| collection errors | **0** |
| errors | **0** |

The 196 skips are all environmental opt-outs already conventional in this repository —
enriched corpora not present in the worktree, `PG_RUN_LOCAL_REVIEW_TESTS` /
`PG_RUN_OCR_FIDELITY_TESTS` not set, shipped detail blobs unbuilt, a plan file held only
in the user's plan store. Seven of them are this session's change: see below.

### The two failure classes that stood in the way are both closed

**1. `static_audit` (the last known failure) is gone.** In the earlier clean-worktree run
at `095d27a1` the fast tier was `1 failed / 15,826 passed / 152 skipped` with failure set
`{static_audit}`. It is now 0 failed. The fix is the seam commit already on `main`
(`a8213c63`): `scoring_v4/modules/generic_evidence.py` no longer reaches for the forbidden
`iqd.get("ingredients")` fallback — it delegates to the canonical contract. Nothing was
allowlisted.

**2. The 7 new hard failures in `test_cross_module_probiotic_evidence.py` are fixed
properly.** That test file (added with the evidence seam) loaded
`scripts/products/output_*_enriched/enriched/*.json` directly and hard-failed with
`FileNotFoundError` in any checkout without the locally-built, gitignored corpus — i.e. on
any clean clone or CI box. Because the failure is environmental rather than logical, the
fix follows the repository's own existing convention (`pytest.skip("enriched corpus not
present")`, used by `test_red_yeast_rice_alias_coverage.py` and others): the two loaders
now skip when the corpus is absent and run exactly as before when it is present. Verified
in both environments:

- clean closure worktree, no corpus → **1 passed / 7 skipped / 0 failed**
- shared checkout, corpus present → **8 passed / 0 failed**

No assertion was weakened, no test was deleted and no path was allowlisted; the tested
behaviour is unchanged wherever the data exists.

### What this closes

The single static finding that blocked the integration report (`V4_IQD_INGREDIENTS_FALLBACK`
in `scoring_v4/modules/generic_evidence.py`) is **resolved by the seam commit**, not
allowlisted: the forbidden `iqd.get("ingredients")` fallback no longer exists in that
module, and `_assessable_active_ingredients` now delegates to the canonical contract
`scoring_input_contract.get_assessable_evidence_ingredients`. That contract owns every
structural exclusion (headers/totals/compound duplicates/inactives, Nutrition Facts
declarations) and resolves identities through the IQM, so the replacement is deterministic
and fails conservatively rather than silently falling back to raw rows.

---

## C. Final same-input A/B replay

**Before** = `095d27a1` (the validated Phase-3 integration). **After** = the closure tip.
Identical frozen raw corpus for both arms (15,414 raw records), driven through the
production entry points by `drive_pipeline_ab.py`.

### Scored level (`compare_scored_arms.py`)

| # | Output | Result |
|---|---|---|
| 1 | Products replayed | **15,412 / 15,412** (`only_in_before` = 0, `only_in_after` = 0) |
| 2 | Crashes | **0** / 0 |
| 3 | Representation changes | 472 (row-level detail below) |
| 4 | Numerical score changes | **28** |
| 5 | Conclusion changes | **29** |
| 6 | Quarantine exits | **0** |
| 7 | New quarantine entries | **1** — `269360` Serrapeptase 40,000 SPU; expected and correct (§C.3) |
| 8 | Safety-gate changes | **0** |
| 9 | Score-bearing outside-family changes | **0** |
| 10 | Largest score deltas | `63666` / `213833` / `327990` / `246207` each **−12.2**; then `182908` / `184300` **+5.3**; `18480` **+3.3**; all others ≤ ±2.4 |

### Representation level (`full_corpus_replay.py --compare`)

| Output | Result |
|---|---|
| Records compared | 15,414 |
| Unchanged | 14,942 |
| Changed | 472 |
| Crashes | 0 / 0 |
| Input fingerprint mismatches | **0** (`fingerprint_verified: true` — same corpus, proven) |
| Only in base / only in after | none |
| Family: `identity_refinement_no_behavioral_delta` | **471** |
| Family: `omega_aggregate_owner` | 1 |
| Family: `outside_expected_families` | **0** |

The 471 are **discrete-enzyme identity specialization**: rows that used to collapse onto
the generic `digestive_enzymes` canonical now carry their own identity (`protease`,
`lipase`, `lactase`, `cellulase`, `papain`, `amylase`, `serrapeptase`, `xylanase`, …).
Verified lossless across all 472:

- role histogram **identical for 472/472** (no row changed its cleaner role),
- nutrition signature **unchanged for 472/472**,
- `actives`, `eligible`, `dosed_eligible` counts **identical for 472/472**,
- 467/472 have byte-identical full count vectors; the other 5 differ only in `display`
  (+1…+3) and `ledger_omissions` (−1…−3) — i.e. one collapsed ledger entry split into
  per-enzyme entries. Nothing was dropped.

Artifact: `CLOSURE_ROWLEVEL_REPLAY_20260920.json` (full per-product detail).

### C.1 The 28 score changes are the intended closure of unsupported evidence transfer

`INGR_DIGESTIVE_ENZYMES` in `backed_clinical_studies.json` previously listed
`pancreatic enzymes`, `lipase`, `protease`, `amylase` **as aliases of the multi-enzyme
complex entry**. That let a standalone `Protease 10 mg` row inherit human evidence for a
five-enzyme fungal formulation — unsupported evidence transfer. The seam narrows the
aliases to `digestive enzyme complex`, `multi-enzyme blend`, `fungal multi-enzyme complex`
and states the limitation explicitly in the entry's own notes ("Does not transfer to
standalone protease, lipase, amylase, cellulase, or animal pancreatin").

Consequence: standalone-enzyme rows lose unearned evidence credit. Every affected product
is in the digestive/systemic enzyme family:

| DSLD | Product | Brand | Δ |
|---|---|---|---:|
| 63666, 213833, 327990, 246207 | Lactase Enzyme Formula / Dairy Defense / Lactase Enzyme | Nature's Way | −12.2 each |
| 182908, 184300 | Gluten/Dairy Digest | Pure Encapsulations | +5.3 each |
| 18480 | BioCore Recovery Enzymes | GNC Pro Performance | +3.3 |
| 2505, 332937, 28720, 28733, 29499, 327997, 293872, 29295, 49563, 43649, 43650, 1840, 1841, 42260, 82372, 31999, 28479, 277020 | enzyme/blend products | Life Extension, Nature's Way, Garden of Life, Pure Encapsulations, Nature's Bounty, MegaFood, GNC, CVS | −0.5 … −2.4 |
| 29143 | B-Complex With B-12 (contains a standalone `Protease 10 mg`) | Nature's Bounty | −1.4 |
| 18382 | Milk Thistle Sport (contains `CereCalase` enzyme blend) | GNC | +0.4 |
| 267299 | Gluten-Free Support (contains `Gluten Enzyme Blend` + 2 probiotics) | Garden of Life | +0.1 |

The four −12.2 products share one mechanism, confirmed by single-product probe:
`quality_pillars_v4.evidence` moves from `raw_evidence: 11.0 / evaluated_applicable`
to `raw_evidence: 0.0 / display_state: not_yet_reviewed / evidence_result_state:
clinical_review_not_coupled` — the previously-inherited 11 points are withdrawn.
**This is conservative: it removes credit, and no score moved upward for an unsupported
reason.** No Safety field changed on any of the 29.

### C.2 The 3 non-enzyme-named products are enzyme-bearing

`29143` carries a standalone `Protease 10 mg`; `18382` carries a `CereCalase`
proprietary enzyme blend; `267299` carries a `Gluten Enzyme Blend` plus two probiotics.
The scored harness independently reports `outside_expected_families: 0`.

### C.3 New quarantine entry `269360` — root cause and verdict

| | Before (`095d27a1`) | After (closure) |
|---|---|---|
| `scoring_status` | scored | **not_scored** |
| `quality_score_v4_100` | 50.4 | `null` |
| `unmapped_actives_total` | 0 | **1** |
| route reason | `taxonomy:fiber_digestive` | `taxonomy:general_supplement` |
| identity readiness | `complete` (`mapped_count` 2, coverage 1.0, `mapped_scoring_actives`) | `incomplete` (`mapped_count` 1, coverage 0.5, `scoring_identity_incomplete`) |
| dose readiness | 2 material actives, all assessed | 1 material active, all assessed |

**Mechanism.** The label declares `Serrapeptase Enzyme = 0 NP` with the form
`Serratia sp.` — there is **no declared enzyme activity amount anywhere on the record**;
`40,000 SPU` appears only in the product *name*. The taxonomy repair routes serrapeptase
as a systemic enzyme rather than as a digestive-enzyme product (the IQM's own
`serrapeptase` entry, product-owner approved 2026-09-19, states: *"It is not a digestive
enzyme… Systemic action, NOT a digestive enzyme. Measured in SPU. Decoupled from
digestive taxonomy."*). Under the systemic/general route the row — which is
`role_classification: active_unmapped` with `score_exclusion_reason:
no_quality_map_match` — now counts against identity coverage, so coverage is 0.5 and the
completeness gate blocks the product.

Both arms produce **byte-identical enriched rows** for this product (verified by
single-product clean+enrich A/B in each worktree), so this is a routing/readiness
consequence, not a representation change.

**Verdict: expected and correct — it closes a prior false clear.** Before the change the
product was scored while its only active had no declared amount and an
unmapped-for-scoring identity. PharmaGuide's rule is that a product stays quarantined when
the data is genuinely insufficient, and the amount may not be inferred from the product
name. Recommended path to resolution: a reviewed label-correction receipt supplying the
printed SPU amount (or a source refresh), owner **source/clinical** — not a pipeline change.

---

## D. Standardization-marker rule scope (reviewed, retained)

The rule under review (`enhanced_normalizer._is_standardization_marker_row` +
`_parent_is_standardized_botanical_extract`): a nested row with a positive mcg/mg quantity
whose parent is a *dosed standardized botanical extract* is a **marker of that parent**,
not an independent active.

**Verdict: structurally correct; retained unchanged.** It keys on nesting + a dosed parent
(`parentBlendMass` numeric) + parent-naming semantics + a declared constituent quantity.
No product ids and no nutrient allowlist appear in it, and both the tests and this review
include a negative control (a nested constituent under a *non*-standardized extract stays
an ordinary scoreable active).

It affects **five** products — the two Phase-3 targets plus three that were never targets:

| DSLD | Product | Parent(s) | Constituent(s) re-roled | Score before → after | Tiers | Safety before → after |
|---|---|---|---|---|---|---|
| 216948 | PM Phytogen Complex | standardized Pueraria mirifica root extract 80 mg | Miroestrol 16 mcg, Isoflavonoids 16 mcg | — → 49.6 (`blocked_by_completeness_gate` → `scored`) | Poor | CAUTION `B0_HIGH_RISK_SUBSTANCE` → **identical** |
| 232718 | Longevity A.I. | Ashwagandha extract (std. to 3% withaferin A) | Withaferin A 12 mg | — → 46.2 (`blocked_by_completeness_gate` → `scored`) | Poor | CAUTION `B0_WATCHLIST_SUBSTANCE` → **identical** |
| 216776 | Herbal Complex | six `standardized <botanical> extract` parents @ 100 mg | Triterpene Glycosides 0.5 mg, Alkaloids 3 mg, Polyphenols 15/30 mg, Echinacosides 4 mg, Glycyrrhizin 1 mg, Oleuropein 6 mg | 72.1 → 74.0 | Good → Good | SAFE → **identical** |
| 44423 | Deglycyrrhized Licorice Root Extract | standardized Deglycyrrhized Licorice extract 250 mg | Glycyrrhizin 3 mg (<1%) | 66.5 → 68.4 | Needs improvement → same | SAFE → **identical** |
| 77254 | Male Multiple | standardized American Ginseng 25 mg, standardized Korean Ginseng 25 mg | Ginsenosides 2.5 mg (10%), 2 mg (8%) | 68.2 → 68.4 | Needs improvement → same | CAUTION `B0_WATCHLIST_EXCIPIENT_WARNING_ONLY` → **identical** |

Why each constituent is **not** independently scoreable: on every one of these labels the
parent is literally named a *standardized* extract and is dosed, and the child's amount is
exactly the parent's stated percentage (3% of 100 mg = 3 mg; 30% of 100 mg = 30 mg; 6% of
100 mg = 6 mg; <1% of 250 mg ≈ 3 mg). The child is the extract's own standardization
disclosure, not a separate exposure — the same structural treatment PharmaGuide already
applies to omega constituents. The dose-bearing identity is the extract, which stays
scoreable.

**Safety is provably unaffected**: for all five products every Safety field
(`safety_verdict`, `product_safety_status`, `_v4_safety_gate`, `_v4_safety_signal_reason`,
`safety_signal_reason`, `badges`, `safety_review_records`) is byte-identical between arms,
including the Withaferin A watchlist on 232718 and the high-risk-substance signal on
216948. Identity remediation did not bypass Safety.

The three non-target products move by **+1.9 / +1.9 / +0.2** (all tier-preserving): the
extract parent still earns the evidence, and removing derived-constituent rows from the
denominator slightly raises the average. None of the three is quarantined.

New regression coverage: `scripts/tests/test_standardization_marker_generalization.py`
(5 tests) reproduces the archived Solgar label structures and pins (a) all six dosed
parents survive with their dose and stay scoreable, (b) every constituent resolves to
`standardization_marker` with its declared quantity retained as disclosure under its own
parent, including the two independent Polyphenols disclosures (15 mg and 30 mg), and
(c) a plain (non-standardized) extract sibling is not treated as a marker parent.

---

## E. Remaining problems

**Engineering work is complete on all of these.** What remains is authority, not code.

| Item | Status | Owner |
|---|---|---|
| Licensed-pharmacist clinical release sign-off | Outstanding | Pharmacist release authority |
| EDTA ×16 standalone orally marketed products | Safety/policy disposition pending; representation and evidence package complete | Safety policy |
| E2 ×6 unit-corruption receipts | Proven upstream-persistent (`unchanged_since_snapshot` for all six); no safe auto-correction; candidate corrections documented | Source/clinical (printed label) |
| Vitamin-A form/completeness gap (Bulk 1340 ×5) | Root cause pinned; no data loss; requires a printed form declaration | Source/clinical |
| Folate parent+form double count (3 residual shapes) | Characterised, blast-radius measured, pre-existing (identical at base); needs one reviewed dose-safety change | Dose-safety owner |
| `omission_reason` enum debt (omega children reuse `duplicate_source_line`) | Accepted technical debt, not a blocker | — |
| Trivial hygiene: `supplement_taxonomy._ENZYME_CANONICAL_IDS` lists `lactase`, `alpha_galactosidase`, `pancreatin`, `cellulase` twice | Inert (frozenset literal dedups). **Left unchanged on purpose** so the replay arm's pipeline stays byte-identical to `main`; recorded here as a one-line cleanup for the next commit | Integrator |

### E.1 E2 ×6 — upstream-persistent unit defects, no safe correction yet

`compare_snapshot_live.py` against `api.ods.od.nih.gov/dsld/v9/label/{id}`:
**all six return `unchanged_since_snapshot`.** No refresh resolves them.

| DSLD | Declared (frozen) | Reading |
|---|---|---|
| 223563 | Vitamin A `900 mg RAE` [60%DV]; Vitamin D3 `100 mg` [660%DV] | Value 900 corroborated by its own %DV under a 1500 mcg RAE reference → unit glyph wrong. **Vitamin D3 row is not corroborated** (100 mcg vs 20 mcg DV is 500%, not 660%) → its *value* is uncertain too |
| 223572 | Vitamin A `900 mg RAE` [60%DV]; Vitamin D3 `50 mg` [330%DV] | Same family, exactly half the D3 amount; same ambiguity |
| 231334 | Vitamin A `6000 mcg DFE` [667%DV]; Vitamin E `134 mcg` [893%DV] | 6000/6.67 = 900 mcg RAE (the published Vitamin A DV) and 134/8.93 = 15.0 mg (the published Vitamin E DV) → **values and %DVs agree**; the *denominations* are wrong (`DFE` for Vitamin A; `mcg` for Vitamin E, should be `mg`) |
| 231335 | identical to 231334 | same |
| 263865 | Vitamin A `6000 mcg DFE` [667%DV]; Vitamin E `134 mg` [893%DV] | **Vitamin E is already correct here** — this sibling record is the independent cross-record corroboration for 231334/231335 |
| 328644 | Vitamin A `1300 mg RAE` [100%DV] | 1300 mcg RAE is exactly the pregnancy/lactation Vitamin A DV, and the product is a prenatal |

Nothing was auto-corrected, for three separate reasons: the team's rule requires the
*printed* source to establish the unit; no plausibility-based `mg↔mcg` conversion is
permitted; and at least one row (223563/223572 Vitamin D3) has an uncorroborated **value**,
so a unit-only receipt would still be wrong. Existing coverage already pins the
prohibition (`TestNoFabricatedDoses::test_corrupted_unit_never_auto_converted`).

### E.2 Vitamin-A form/completeness gap — no data loss, precise failure path

Single-product probe of frozen `228823` through the closure cleaner+enricher:

```
Vitamin A row: cleaner_row_role=active_scorable, score_eligible_by_cleaner=true,
               canonical_id=vitamin_a, quantity=3000.0 mcg, dose_class=therapeutic_mass
typed dose assessment:
  conversion_rule_id   vitamin_a_unknown
  conversion_status    converted
  normalized_value     3000.0  normalized_unit mcg
  ul_assessment_status unresolved_form
  ul_value             null     ul_unit  mcg RAE
  pct_ul               null
  reason_code          unknown_vitamin_form
  readiness            incomplete
```

**Failure path:** the label declares Vitamin A with no form (no "Form: as …" note, so
retinol vs beta-carotene is undetermined). Without a form the engine cannot select the
retinol-RAE upper limit, so it refuses to make a UL claim and marks that one assessment
incomplete. That single row is `ingredientRows[5]`, which is why
`assessment_readiness.dose.incomplete_source_row_refs = ["ingredientRows[5]"]` (27 of 28
material rows assessed) and the product is gated. The quantity, unit and %DV are all
preserved and mutually consistent (3000 mcg ↔ 334%DV and 3417 mcg ↔ 380%DV both resolve
against a 900 mcg RAE reference). **Nothing is discarded and no form is invented.**
Recommended correction: a reviewed form-provenance determination from the printed label.
Do not relax the form requirement and do not default to retinol.

### E.3 Folate parent+form double count — pre-existing, precisely characterised

Corpus-wide there are **58** folate dose-safety flags; **55** are already correctly
reconciled as parent-total + form-breakdown duplicates. Three are not — and all three are
**byte-identical at base `124982a0` and at `095d27a1`** (same `pct_ul`, `penalized`,
`state`), so this is pre-existing behaviour, not a regression of the remediation.

| DSLD | Product | Source shape | Why unreconciled | Material impact |
|---|---|---|---|---|
| 201420 | Male Multiple (Solgar) | `Folic Acid 1333 mcg DFE` + nested `Folic Acid 800 mcg` | the declared-total row is *named* "Folic Acid", which is not in `_FOLATE_PARENT_NAMES`, so both rows are treated as additive forms | low — independently over-UL on niacin 171%, magnesium 114%, zinc 125% |
| 246430 | PreNatal Nutrients (Pure Encapsulations) | `Folate 1667 mcg DFE` + nested `Folic Acid 400 mcg` | 1667 = 1000 mcg L-5-MTHF + 400×1.7 (680) DFE; the child is a **partial** breakdown already inside the total, but the recognizer requires the forms to *fully* account for the parent | highest — the folate flag is the product's **only** dose-safety finding, on an otherwise 85.9-scoring prenatal (informational: `penalized: false`, product still scored) |
| 243808 | Bulk 1340 Strawberries & Cream | `Folate 725/667 mcg DFE` + **two sibling children** `Folic Acid 435 mcg` and `400 mcg` | the same declared form is split across serving-size variants; both are converted (×1.7 ×2 servings = 1479 and 1360) and **summed** to 2839 against a parent of 1450 → 4289 mcg DFE → 257% | low — independently over-UL on niacin 286% and magnesium 126% |

Recommended change (one reviewed, tested change, owned by the dose-safety/folate owner):
complete the existing contract rather than widen it — (a) recognise the declared-total row
by exposure basis / DFE unit instead of by a parent-name vocabulary that omits
"Folic Acid"; (b) treat a nested form row of the same canonical nutrient as part of the
declared total even when it is a subset; (c) collapse sibling form rows carrying the same
form name and basis to one exposure instead of summing them. Two of the three sit within
0.05 percentage points of the existing reconciliation tolerance (228823 passes at
26/1334 = 1.95% against a ≈2% limit), so this must be a deliberate change with these three
as fixtures, not an opportunistic edit. Existing owners:
`test_folate_dose_basis_reconciliation.py`, `test_dose_safety_shared_contract.py`.

---

## F. Artifacts corrected and preserved

| Artifact | Action |
|---|---|
| `INTEGRATION_REPORT_PHASE3_20260920.md` row 8 | Corrected: the bare `0` is replaced by **`0 score-bearing / 55 representation-only`**, with a new *"Levels of outside expected families"* subsection naming both harness levels and why they differ |
| `INTEGRATION_REPORT_PHASE3_20260920.md` §G | "New false clears" and "Unexpected cross-family changes" rows now name the level explicitly |
| `/tmp/audit_base_int.json` (stale pre-final row-level audit) | Marked **SUPERSEDED** in-repo with the two keying artifacts that explained its counters, and a pointer to the authoritative results |
| `full_corpus_replay.py` | Classifier extended with `identity_refinement_no_behavioral_delta`; the tool now names a 471-product identity refactor instead of reporting it as "outside expected families". No pipeline file touched |
| `CLOSURE_ROWLEVEL_REPLAY_20260920.json` | **New** — durable row-level replay detail (15,414 signatures compared, per-product deltas) |
| `phase3_closure_dispositions_20260920.json` | **New** — durable per-product closure ledger with owners and evidence |

---

## G. Cleanup

| Item | Action |
|---|---|
| Audit reports + replay scripts | Preserved and committed under `scripts/audits/quarantine_triage_20260919/` |
| `remediation/quarantine-clearing-20260919` | Deleted (content is on `main`; no unique unresolved work — its tip is `f1410ee3`, whose tree equals `main`'s pre-evidence-resolver tree) |
| `integration/phase3-remediation-20260920` | Deleted after `main` contains the same commits |
| Temporary worktrees (`/private/tmp/pg_base`, `/private/tmp/pg_before_095d27a1`, `/private/tmp/closed`, the closure worktree) | Removed |
| Scratch datasets (`/tmp/pipelineA`, `/tmp/pipelineB`, `/tmp/pipelineC`, ~14 GB each) | Removed after the evidence above was committed |
| Shared checkout | Left clean, on `main`, with none of this session's work stashed or staged outside its own commits |

---

## H. Health statement

| Question | Answer | Evidence |
|---|---|---|
| Known data loss | **NO** | representation replay: role histogram identical 472/472, nutrition unchanged 472/472, `actives`/`eligible`/`dosed_eligible` identical 472/472; the 5 count deltas are display rows *gaining* entries (omissions fall); 0 records only-in-either arm |
| Fabricated doses | **NO** | no unit conversion, no %DV back-calculation, no inferred amount anywhere in this session; every quantity in the closing documentation is read from a source row |
| Lost Safety signals | **NO** | scored replay `safety_changes: 0`; all 29 changed products carry identical Safety fields; the five marker products carry identical Safety gates, signals and verdicts |
| New false clears | **NO** | 0 quarantine exits in the closure increment |
| New false quarantines | **NO** | 1 new quarantine (`269360`) root-caused as *correct* — it closes a prior false clear (no declared amount anywhere on the record, unmapped-for-scoring identity) |
| Unexplained score changes | **NO** | all 28 attributed to one mechanism: closure of unsupported multi-enzyme-complex → discrete-enzyme evidence transfer |
| Unexpected score-bearing cross-family effects | **NO** | `outside_expected_families: 0` at the scored level; at the representation level 471/472 are a named no-behavioural-delta identity refinement |
| Static audit findings | **0** |
| Test failures | **0** — full fast tier `15,825 passed / 0 failed / 196 skipped` in 352.95 s; 0 errors; 0 collection errors |

---

## I. Final status

**Engineering work complete:** **YES** — the evidence seam is on `main`, the static audit is
clean, the closure validation passed, and every remaining item is an authority decision or a
separately-owned, fully-characterised change.

**Main updated and verified:** **YES** — see §A/§H.

**Phase-3 engineering closed:** **YES**

**Remaining clinical/policy work:**
licensed-pharmacist release sign-off; EDTA ×16 safety-policy disposition; the E2 ×6 and
Vitamin-A printed-source receipts; the folate de-duplication change (dose-safety owner).

**Production release approved:** **NO** — production is a separate gate that additionally
requires the pharmacist release authority and the policy dispositions above. Engineering
does not replace that authority.
