# Phase-3 Engineering Closure Report

Date: 2026-09-20
Role: lead engineering closer (Phase-3 remediation + evidence/scoring integration)
Scope: close the engineering phase end-to-end and land it on `main`.

Baseline at session start: `origin/main` = `ad577f49` (unchanged all session).
`main` advanced **three** times during the session, every time by the integration owner's
parallel session, and the closure branch was rebased onto each new tip and revalidated —
see §A and §A.1.

---

## A. Repository

| Item | Value |
|---|---|
| Starting `main` / `origin/main` | `ad577f49` |
| `main` advances observed mid-session | `6f2bdc80` → `236a9dc1` → `4e5f4bda` → `78ad21fd` (all by the integration owner's concurrent session) |
| `main` at closure | **`78ad21fd`** |
| Validation-pipeline SHA (what the replay tested) | `4e5f4bda` — the last commit this session that touched the clean/enrich/score path; `78ad21fd` is proven pipeline-inert (§A.1) |
| Evidence-owner commits (all already on `main`) | `a8213c63` (canonical assessable-evidence contract + probiotic ownership), `6f2bdc80` (probiotic A/B report), `236a9dc1` (universal evidence resolver + shadow coverage), `4e5f4bda` (canonical-nutrient authority routing; removes the local whitelist), `78ad21fd` (Phase-4 shadow literature resolution + provenance gates) |
| Closure candidate | `closure/phase3-final-20260920` tip **`0eec550e`** = `main` (`78ad21fd`) + this session's four commits (three test/docs, one data-metadata fix) |
| Conflicts / reconciliations | **None.** The closure branch was rebased onto `main` four times as `main` advanced; every rebase was clean and the exact-manifest equality below held at each step. One genuine defect in a concurrent commit was found and repaired by this session — see *One repair to a concurrent commit* below. |

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
| `4e5f4bda` (the replay "after" arm's pipeline) | 267 | `e9b86701a41483ea…` |
| `78ad21fd` (= `main`) | 268 | `8a0057255fcad370…` |
| closure tip `899cba40` before the repair | 268 | **`8a0057255fcad370…`** ← identical to `main` |
| **final closure tip `0eec550e`** | 268 | `…` — differs from `main` by exactly one metadata field (§ repair) |

This is the guarantee that the replay below describes the code that ships. The closure
commits are documentation, tests and one metadata repair — none of which the clean/enrich/
score path reads:

- `78ad21fd` added `scripts/evidence_resolver.py` + `scripts/data/literature_evidence_records.json`,
  and **`evidence_resolver.py` has zero importers** (verified by grep across `scripts/`;
  `clean_dsld_data.py`, `enrich_supplements_v3.py` and `score_products_v4.py` contain zero
  references to it or to the new JSON). It is shadow-mode work, and its own commit message
  claims "zero score changes in shadow mode" — which the import graph confirms rather than
taking on trust.

### One repair to a concurrent commit

`78ad21fd` shipped a genuine repo-contract violation, caught by re-running the tier at the
final tip instead of assuming it still held:

```
test_pipeline_integrity.py::TestDatabaseSchemaIntegrity::test_schema_version_contract
  1 schema_version mismatch(es):
  literature_evidence_records.json: schema_version='1.0.0' belongs to namespace 1, expected 5.x
```

`scripts/reference_data_schema.py` states the rule in its own docstring — version 1 owns
vocabularies/small control artifacts, version 6 owns interaction/certification contracts,
and **every other top-level reference database stays in the version 5 enrichment
namespace**; `validate_reference_schema_version` enforces it and `preflight.py` uses the
same validator. The new file declared `1.0.0`.

Repaired in `0eec550e` by declaring `5.0.0` — a brand-new file has no prior revision
history, so it declares the namespace base. Metadata only: `total_entries` (23) already
matched the actual record count, and no record content changed. The file is read solely by
`evidence_resolver.py`, so the repair cannot alter scoring. This is the only change this
session made to a file another session authored, and it is flagged here so the evidence
owner can see it.

### A.1 Reconciling a target that moved three times

`main` was under active development by a parallel session for the whole closure. Each move
was handled the same way — **rebase onto the new tip, then re-derive the evidence at the new
tip** — rather than assuming a clean cherry-pick implies semantic compatibility:

| Move | What landed | Pipeline-affecting? | Action |
|---|---|---|---|
| `ad577f49` → `6f2bdc80` | the evidence seam (canonical assessable-evidence contract, probiotic ownership) + its A/B report | yes | rebased; re-verified tree equivalence with my own cherry-pick of the same content |
| `6f2bdc80` → `236a9dc1` | universal evidence resolver + shadow coverage (one new module, `scripts/evidence_resolver.py`) | no — nothing in the pipeline imports it | rebased; manifest confirmed unchanged except the added file |
| `236a9dc1` → `4e5f4bda` | canonical-nutrient authority routing: `rda_optimal_uls.json` aliases added, local whitelist removed from `evidence_resolver.py`, `scoring_reference_resolver.py` exposes `rda_ul_reference_entry` | **yes** — `rda_optimal_uls.json` is read by `scoring_v4/modules/generic_dose.py`, so UL resolution can move scores | rebased **and re-ran the full validation at the new tip** |
| `4e5f4bda` → `78ad21fd` | Phase-4 shadow literature resolution + provenance gates (`evidence_resolver.py`, new `literature_evidence_records.json`) | **no** — `evidence_resolver.py` has zero importers and the pipeline entry points contain zero references to it or its JSON | rebased; re-ran the tier at the new tip, which **found the schema-version defect it introduced** and repaired it (§ repair) |

The `4e5f4bda` move is the one that could move scores, so it was proven rather than
assumed. Two comparisons were run against freshly built arms:

- **`236a9dc1` → `4e5f4bda`, scored level, all 15,412 records:**
  `score_changes: 0`, `conclusion_changes: 0`, `quarantine_exits: 0`,
  `quarantine_entries: 0`, `safety_changes: 0`, `outside_expected_families: 0`,
  `max_abs_delta: 0`. `4e5f4bda` is a **behaviour-preserving refactor** on this corpus —
  exactly what replacing a private whitelist with the canonical owner should be.
- **Representation level, same two arms:** all 15,414 signature records are semantically
  **identical** (0 differing records, 0 differing fields). The two signature files differ
  only in *line order*, because the audit tool writes them from a parallel worker pool;
  comparisons are keyed by product id, so this cannot affect a result. (Worth recording as
  a tool caveat: the signature JSONL is order-nondeterministic and must never be compared
  by file hash.)

Because `4e5f4bda` is a no-op at both levels, the mandated `095d27a1` → final-tip replay
gives **the same numbers as the closure increment**, and the arm rebuilt at the final tip is
the arm the report's results describe:

| Comparison | Records | Score changes | Conclusions | Exits | New quarantine | Safety | Outside families | Max \|Δ\| |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `095d27a1` → final tip (mandated) | 15,412 | **28** | **29** | 0 | **1** | 0 | **0** | 12.2 |
| `236a9dc1` → final tip (`4e5f4bda` increment) | 15,412 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

`78ad21fd` was **not** replayed, deliberately: its two pipeline-adjacent files are provably
unreachable from the clean/enrich/score path (grep-verified above), so a `4e5f4bda` →
`78ad21fd` arm would be a 15,412-record comparison of identical behaviour. What it *did*
require — and got — was a tier re-run, which is what surfaced its schema-version defect.

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

Run on the **final** closure tip (`0eec550e`, rebased onto `main` = `78ad21fd`) in a clean
dedicated worktree (`scripts/test.sh fast`; counts and sanitised skip census preserved as
`FAST_TIER_CLOSURE_20260920.md` alongside this report). The tier was run three times this
session — at `236a9dc1`, at `4e5f4bda`, and at the final tip — because re-running it at each
new `main` is what caught the concurrent commit's schema-version defect instead of assuming
the previous result still held.

```
15835 passed, 196 skipped in 428.55s (0:07:08)
```

| | Count |
|---|---:|
| passed | **15,835** |
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

Test-count reconciliation across the three runs: `15,825` at `236a9dc1`; `+2` from
`4e5f4bda`'s two `test_evidence_resolver.py` regressions; `+8` collected from `78ad21fd`
(`7` passing, `1` failing) ; and the repair of that one failure turns the final tally into
`15,835 passed / 0 failed`. Passed count rose by exactly the number of tests added, and the
skip count never moved from 196.

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

**Before** = `095d27a1` (the validated Phase-3 integration). **After** = the **final closure
tip** on `main`'s tip `4e5f4bda` — the arm was rebuilt at the final tip after `main`
moved, not reused from the earlier `236a9dc1` run (§A.1). Identical frozen raw corpus for
both arms (15,414 raw records, same input fingerprint), driven through the production entry
points by `drive_pipeline_ab.py`, then compared by BOTH harnesses:
`compare_scored_arms.py` (scores, conclusions, quarantine, Safety — the release-relevant
level) and `full_corpus_replay.py --compare` (row-level representation).

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

These are the **final-tip** numbers (`095d27a1` → `4e5f4bda` + closure). They are identical
to the `236a9dc1`-tip run because `4e5f4bda` is a proven no-op on this corpus at both the
scored and representation levels (§A.1) — the two independent comparisons agree exactly, so
the conclusions in §C.1–§C.3 apply unchanged to the shipped tip.

Artifacts: `/tmp/final_scored_BD.json` (scored, mandated comparison), `/tmp/final_scored_CD.json`
(`4e5f4bda` increment, all zeros), `/tmp/final_rowlevel_BD.json` (row-level, mandated
comparison). Durable copies of the decisive numbers are in
`CLOSURE_ROWLEVEL_REPLAY_20260920.json`.

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

**One upstream cause, three pillar-level mechanisms.** Every one of the 28 changes is a
consequence of the same upstream change — discrete enzyme identities (`protease`, `lactase`,
`papain`, …) replacing the single collapsed `digestive_enzymes` identity — but *which pillar*
it shows up in differs, and getting that wrong would misreport the product-level facts. Each
product below was classified by comparing its six pillar scores (`dose`, `evidence`,
`formulation`, `safety_hygiene`, `transparency`, `verification`) in both arms. Because
`quality_score_v4_100` is exactly the sum of earned pillar points (verified: for `182908`,
`12.8 + 0 + 12.0 + 10 + 6.0 + 10.0 = 50.8`), the pillar deltas reconcile to the total
exactly on every row.

**Mechanism A — unearned evidence credit withdrawn (23 of 28).**
`INGR_DIGESTIVE_ENZYMES` in `backed_clinical_studies.json` previously listed
`pancreatic enzymes`, `lipase`, `protease`, `amylase` **as aliases of the multi-enzyme
complex entry**, which let a standalone `Protease 10 mg` row inherit human evidence for a
five-enzyme fungal formulation. The seam narrows the aliases to `digestive enzyme complex`,
`multi-enzyme blend`, `fungal multi-enzyme complex` and states the limit in the entry's own
notes. Single-product probe of `63666`: the Evidence pillar moves from
`raw_evidence 11.0 / evaluated_applicable / score 12.2` to `raw_evidence 0.0 /
not_yet_reviewed / clinical_review_not_covered / score 0` — 11 points of inherited credit
withdrawn. **This direction is conservative: it removes credit.**

**Mechanism B — a formulation penalty stops applying (12 of 28, overlapping A).**
The collapsed aggregate identity carried the verdict *"Uses basic or low-cost ingredient
forms."* (6.7/20). The discrete enzyme identities have **no** form-quality rating in the
current data, so the pillar reports the neutral state *"Ingredient-form quality is not rated
in PharmaGuide's current data."* (12.0/20 for `182908`). This is a **gain**, and it is the sole
reason `182908` / `184300` (+5.3) and `18480` (+3.3) move upward while their rubric raw score
falls (35.2 → 30.2). It is not an evidence gain and not a Safety change.

**Mechanism C — a transparency deduction changes (1 product).** `82372` Beanaid:
transparency 15.0/15 → 13.5/15 (−1.5) with the reason string unchanged ("Fully transparent
label — every amount is disclosed"); the readiness record shows its enzyme assessment moving
from `digestive_enzymes` (2 × `not_applicable`) to `alpha_galactosidase`. Same upstream
cause, third pillar.

| DSLD | Product | before → after | Δ | evidence Δ | formulation Δ | mechanism |
|---|---|---|---:|---:|---:|---|
| `63666` | Lactase Enzyme Formula | 72.7 → 60.5 | −12.2 | −12.2 | 0.0 | A |
| `213833` | Dairy Defense | 72.7 → 60.5 | −12.2 | −12.2 | 0.0 | A |
| `246207` | Lactase Enzyme Formula | 72.7 → 60.5 | −12.2 | −12.2 | 0.0 | A |
| `327990` | Lactase Enzyme | 72.7 → 60.5 | −12.2 | −12.2 | 0.0 | A |
| `182908` | Gluten/Dairy Digest | 45.5 → 50.8 | +5.3 | 0.0 | +5.3 | B |
| `184300` | Gluten/Dairy Digest | 45.5 → 50.8 | +5.3 | 0.0 | +5.3 | B |
| `18480` | BioCore Recovery Enzymes | 55.8 → 59.1 | +3.3 | 0.0 | +3.3 | B |
| `2505` | Enhanced Super Digestive Enzymes With Probiotics | 58.6 → 56.2 | −2.4 | −2.4 | 0.0 | A |
| `28720` | Omega-Zyme Digestive Enzyme Blend | 49.4 → 47.2 | −2.2 | −2.2 | 0.0 | A |
| `28733` | Omega-Zyme Digestive Enzyme Blend | 45.9 → 43.7 | −2.2 | −2.2 | 0.0 | A |
| `29499` | Wobenzym N | 69.6 → 67.4 | −2.2 | −2.2 | 0.0 | A |
| `327997` | Mega-Zyme Pancreatic & Systemic Enzymes | 54.2 → 52.0 | −2.2 | −2.2 | 0.0 | A |
| `332937` | Mega-Zyme Pancreatic & Systemic Enzymes | 54.2 → 52.0 | −2.2 | −2.2 | 0.0 | A |
| `293872` | A.I. Enzymes | 73.1 → 71.3 | −1.8 | −1.8 | 0.0 | A |
| `29295` | Intensive Strength Digest 13 | 63.8 → 62.1 | −1.7 | −2.2 | +0.5 | A+B |
| `49563` | Enzyme 13 | 63.8 → 62.1 | −1.7 | −2.2 | +0.5 | A+B |
| `1840` | Multi-Enzyme Formula | 56.0 → 54.4 | −1.6 | −2.2 | +0.6 | A+B |
| `1841` | Multi-Enzyme Formula | 56.0 → 54.4 | −1.6 | −2.2 | +0.6 | A+B |
| `43649` | MegaZymes | 72.8 → 71.2 | −1.6 | −1.6 | 0.0 | A |
| `43650` | MegaZymes | 72.8 → 71.2 | −1.6 | −1.6 | 0.0 | A |
| `31999` | Digestive Enzymes | 54.1 → 52.6 | −1.5 | −2.2 | +0.7 | A+B |
| `42260` | Super Digestive Enzymes | 57.1 → 55.6 | −1.5 | −2.2 | +0.7 | A+B |
| `82372` | Beanaid | 57.1 → 55.6 | −1.5 | 0.0 | 0.0 | **C** (transparency −1.5) |
| `29143` | B-Complex With B-12 | 71.8 → 70.4 | −1.4 | −1.4 | 0.0 | A |
| `28479` | Acid Defense | 58.0 → 57.0 | −1.0 | −1.6 | +0.6 | A+B |
| `277020` | Super Papaya Enzyme Mint Flavored 45 mg | 52.4 → 51.9 | −0.5 | −2.2 | +1.7 | A+B |
| `18382` | Milk Thistle Sport | 72.5 → 72.9 | +0.4 | 0.0 | +0.4 | B |
| `267299` | Gluten-Free Support | 67.4 → 67.5 | +0.1 | 0.0 | +0.1 | B |

All 28 are **expected** given the identity change, all sit inside the enzyme family, and no
Safety field changed on any of the 29. Every tier assignment was preserved. Nothing was
fabricated, no dose changed, and the two products that gained the most gained from a
*withdrawn penalty* rather than from new credit.

**Open follow-up for the formulation owner (not a blocker):** PharmaGuide previously attached
a "basic or low-cost form" verdict to the aggregate enzyme identity. After specialization no
form verdict attaches to the discrete enzyme identities, so the penalty silently disappears
for 12 products (max +5.3). Whether discrete enzyme identities should carry a form verdict,
or whether *unrated* is the intended state, is a formulation-model question — it is recorded
here rather than resolved unilaterally, because changing it would move scores again.

### C.2 The 3 non-enzyme-named products are enzyme-bearing

`29143` carries a standalone `Protease 10 mg`; `18382` carries a `CereCalase`
proprietary enzyme blend; `267299` carries a `Gluten Enzyme Blend` plus two probiotics.
The scored harness independently reports `outside_expected_families: 0`.

### C.3 New quarantine entry `269360` — root cause and verdict

| | Before (`095d27a1`) | After (final tip) |
|---|---|---|
| `scoring_status` | scored | **not_scored** |
| `not_scorable_reason` | `null` | **`incomplete_product_data`** |
| `score_unavailable_reason` | `null` | **`blocked_by_completeness_gate`** |
| `quality_score_v4_100` / `raw_score_v4_100` | 50.4 / 32.3 | `null` / `null` |
| `quality_tier` / `verdict` / `display_100` | Poor / `POOR` / `50/100` | `null` / `NOT_SCORED` / `N/A` |
| `unmapped_actives_total` | 0 | **1** |
| route reason | `taxonomy:fiber_digestive` | `taxonomy:general_supplement` |
| identity readiness | `complete` (`mapped_count` 2, coverage 1.0, `mapped_scoring_actives`) | `incomplete` (`mapped_count` 1, coverage 0.5, `scoring_identity_incomplete`) |
| dose readiness | 2 of 2 material actives assessed | 1 of 1 material active assessed |
| Safety fields | — | **unchanged** (all Safety fields byte-identical) |

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

> **SUPERSEDED IN PART (2026-09-20) — see
> `source_resolution_20260920/SOURCE_RESOLUTION_RECEIPTS_20260920.json` and
> `SOURCE_RECONCILIATION_20260920.md`.** A follow-on source-resolution phase went back to
> live NIH DSLD, the archived DSLD label images (the scans matching each product/version),
> DSLD sibling label records and manufacturer panels, and closed the *source* rows below.
> E2 ×6: `328644`/`223563`/`223572` are now `source_verified_correction` (vitamin-A unit
> `mcg RAE`), while `231334`/`231335`/`263865` are `source_insufficient_keep_withheld`
> (the record reproduces the printed panel and no UL claim depends on the denomination).
> Vitamin-A form gap: the printed OTHER INGREDIENTS blend names `Natural beta-Carotene`,
> so the form is source-established. Folate residuals: the Bulk 1340 panel has two printed
> value columns (water / 2% milk) and `243808` is the only record that splits one folic-acid
> form row into two. `269360` Serrapeptase: the panel declares `40,000 SPU`. No row below is
> a source question any more; only the dose-safety reconciliation change, the EDTA policy,
> the standardization-marker policy, the discrete-enzyme formulation policy, the
> provitamin-A UL applicability question and the pharmacist sign-off remain.

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
| `/tmp/audit_base_int.json` (stale pre-final row-level audit) | Marked **SUPERSEDED** inside the committed `INTEGRATION_REPORT_PHASE3_20260920.md`, together with its raw counters *quoted inline* and the two keying artifacts that explain them — so the note stands on its own after the `/tmp` scratch data is deleted. It predates the final arms and its `lost_dose_owner` / `lost_safety_rows` / `de_eligibilized_without_provenance` numbers must not be cited |
| `full_corpus_replay.py` | Classifier extended with `identity_refinement_no_behavioral_delta`; the tool now names a 471-product identity refactor instead of reporting it as "outside expected families". No pipeline file touched |
| `CLOSURE_ROWLEVEL_REPLAY_20260920.json` | **New** — durable row-level replay detail (15,414 signatures compared, per-product deltas) |
| `phase3_closure_dispositions_20260920.json` | **New** — durable per-product closure ledger with owners and evidence |
| `CLOSURE_SCORED_REPLAY_095d27a1_to_final_20260920.json` | **New** — the mandated scored-level comparison output (full detail, 15,412 records) |
| `CLOSURE_SCORED_REPLAY_236a9dc1_to_final_20260920.json` | **New** — the `4e5f4bda` increment (all zeros), proving it behaviour-preserving |
| `CLOSURE_REPORT_PHASE3_20260920.md` / `FAST_TIER_CLOSURE_20260920.md` | **New** — this report and the tier evidence |

All of the above are committed, contain no machine-specific paths (the two scored artifacts
were checked for absolute-path leaks: zero found), and are sufficient to explain every
number in this report without an ephemeral worktree.

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
| New false clears | **NO** | 0 quarantine exits; the single *new* quarantine (`269360`) closes a prior false clear rather than creating one — it was previously scored while its only active had no declared amount anywhere on the record |
| New false quarantines | **NO** | 1 new quarantine (`269360`) root-caused as *correct* — it closes a prior false clear (no declared amount anywhere on the record, unmapped-for-scoring identity) |
| Unexplained score changes | **NO** | all 28 classified per product by pillar comparison into three mechanisms from **one** upstream cause (discrete enzyme identities replacing the collapsed `digestive_enzymes` identity): evidence credit withdrawn (23), aggregate-identity formulation penalty withdrawn (12, overlapping), one transparency deduction shift (`82372`). Pillar deltas reconcile to each total exactly |
| Unexpected score-bearing cross-family effects | **NO** | `outside_expected_families: 0` at the scored level; at the representation level 471/472 are a named no-behavioural-delta identity refinement |
| Static audit findings | **0** |
| Test failures | **0** — full fast tier at the final tip: `15,835 passed / 0 failed / 196 skipped` in 428.55 s; 0 errors; 0 collection errors |
| New failures introduced by concurrent `main` commits | **one, found and repaired** — `78ad21fd`'s `literature_evidence_records.json` declared `schema_version 1.0.0` against the repo's version-5 data namespace, failing `TestDatabaseSchemaIntegrity::test_schema_version_contract`; repaired in `0eec550e` (metadata only). Not suppressed or allowlisted |
| Unresolved regressions | **NO** | final failure set is empty; the static audit is clean; both replay harnesses agree |

---

## I. Final status

**Engineering work complete:** **YES** — the evidence seam is on `main`, the static audit is
clean, the closure validation passed, and every remaining item is an authority decision or a
separately-owned, fully-characterised change.

**Main updated and verified:** **YES** — `origin/main` fast-forwarded from `ad577f49` to the
closure tip and verified equal to local `main`. Structure of the landed history:

- validation pipeline SHA `4e5f4bda` (the last commit touching the clean/enrich/score path);
- `78ad21fd` on top (pipeline-inert, verified by import graph);
- this session's four commits: `f87750b2` (hermetic probiotic tests + marker-scope coverage +
  level-named family count), `2c382f2f` (closure report + replay evidence), `899cba40`
  (rebase/evidence update), `0eec550e` (data-metadata repair).

See §A for the manifest proof that the documentation commits change zero pipeline files, and
§A.1 for the replay re-run at the validated tip. Verification:

```bash
git fetch origin && git log --oneline -3 origin/main   # tip = closure docs commit
git diff --stat origin/main main                        # empty
git status --short                                      # empty
```

**Phase-3 engineering closed:** **YES**

**Remaining clinical/policy work:**
licensed-pharmacist release sign-off; EDTA ×16 safety-policy disposition; the E2 ×6 and
Vitamin-A printed-source receipts; the folate de-duplication change (dose-safety owner).

**Production release approved:** **NO** — production is a separate gate that additionally
requires the pharmacist release authority and the policy dispositions above. Engineering
does not replace that authority.
