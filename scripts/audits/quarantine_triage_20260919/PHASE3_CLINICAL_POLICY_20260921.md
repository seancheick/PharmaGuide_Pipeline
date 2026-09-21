# PharmaGuide — Phase-3 clinical policy record (final)

Date: **2026-09-21**
Phase: **Phase 3 (quarantine remediation / clinical sign-off)**

## Clinical authority

| | |
|---|---|
| Clinical reviewer | **Dr. Pham** |
| Team | **PharmaGuide Clinical Team** |
| Decision date | **2026-09-21** |
| Policy decisions | Approved as documented below |
| Overall | **APPROVED WITH SPECIFIED PRODUCTS HELD** |

Per PharmaGuide owner governance, Dr. Pham / PharmaGuide Clinical Team is
sufficient clinical sign-off authority for Phase 3. No licence number, state
licence, credential verification, external attestation, or additional
pharmacist paperwork is required by that governance, and none is recorded here.

The clinical team's supplied review response is the supporting review artifact
for these decisions.

## Policy ledger

| Policy | Status |
|---|---|
| Standalone oral EDTA (16 products) | `BLOCKED_SAFETY_CARD_NO_SCORE` |
| Botanical standardization constituents (5 products) | `CONTAINED_CONSTITUENT_MODEL_APPROVED` |
| Discrete-enzyme Formulation treatment | `NOT_INDIVIDUALLY_RATED_APPROVED` |
| Beta-carotene / Vitamin-A UL | `PREFORMED_VITAMIN_A_ONLY` |

No clinical policy field remains TBD, pending, awaiting review, or awaiting a
pharmacist.

---

## 1. Standalone oral EDTA — `BLOCKED_SAFETY_CARD_NO_SCORE`

**Decision.** The 16 standalone, deliberately orally marketed BulkSupplements
EDTA products are **BLOCKED**, remain **consumer-visible through a Safety
card**, and receive **no conventional PharmaGuide quality score**.

| | |
|---|---|
| Disodium edetate (8) | 252358, 253339, 253350, 253357, 312449, 312450, 312451, 312452 |
| Calcium disodium edetate (8) | 252426, 253331, 253335, 253336, 311259, 311260, 311261, 311262 |

Invariants recorded as binding:

* disodium edetate and calcium disodium edetate remain **distinct
  identities** and are never collapsed into a generic "EDTA" safety identity;
* the disposition states **non-routine chelation requiring clinical review**;
  it is **not** a claim that the labelled oral dose is proven acutely toxic;
* EDTA declared as a formulation excipient is **out of scope**.

**Implementation.** Two policy entries in
`scripts/data/banned_recalled_ingredients.json`
(`BANNED_NON_ROUTINE_CHELATOR_EDETATE_DISODIUM`,
`BANNED_NON_ROUTINE_CHELATOR_CALCIUM_DISODIUM_EDETATE`), authored for the
declared-active label role only, with reason semantics
`NON_ROUTINE_CHELATOR` / `CLINICIAN_REVIEW_REQUIRED`. Consumer copy is authored
in the registry's own Safety-card fields (`safety_warning_one_liner` ≤ 80
chars, `safety_warning` ≤ 200 chars) rather than hard-coded in the client.

Applied by `scripts/audits/quarantine_triage_20260919/apply_edta_non_routine_chelator_policy.py`
(idempotent). Public authority for the policy basis: FDA, *Questions and
Answers on Unapproved Chelation Products* — FDA has never approved any
chelation product for over-the-counter use, and approved chelation products
require a prescription and clinical supervision.

**Engineering note.** Two general, opt-in gate capabilities were added to
support this policy honestly rather than as a product-id special case:

* `verdict_reason_code` — an entry may name its own machine reason code, so the
  exported `blocking_reason` states the *policy* rather than the registry tier.
* `role_scope_out_of_scope: "not_applicable"` — a rule authored for specific
  label roles treats another role as **out of scope** instead of an unresolved
  policy question. Out-of-scope occurrences leave the product payload
  byte-identical to a label that never named the substance (no verdict, no
  quarantine, no audit marker).

---

## 2. Botanical standardization constituents — `CONTAINED_CONSTITUENT_MODEL_APPROVED`

**Decision.** The parent standardized botanical extract is the dose-bearing
formulation identity. A quantified constituent declared beneath it remains
visible, retains its declared quantity and parent/source provenance, is **not**
counted as additional additive mass, and remains available to Safety matching
and to evidence matching where appropriate.

Products reviewed: **216948, 232718, 216776, 44423, 77254**.

Approved conceptual role: `contained_standardization_constituent`.

### Terminology decision (recorded, not blocking)

The runtime name for this role is currently **`standardization_marker`**
(cleaner `cleaner_row_role`, `dose_class`, `score_exclusion_reason`
`standardization_marker_of_dosed_parent`). Dr. Pham prefers language that does
not imply these constituents are inert analytical metadata.

**Phase-3 decision: do not rename the enum in this phase.** The literal rename
reaches the cleaner's row-role enum, the form-fallback audit
(`other_ingredients.json`), the replay classifier, and six test modules — that
is exactly the broad schema/replay churn the clinical direction said not to
hold the phase for.

**Recorded meaning:** `standardization_marker` means a **contained quantified
constituent** of a dosed parent extract, not necessarily an inert marker.

**Non-blocking technical-debt item:** rename
`standardization_marker` → `contained_standardization_constituent` as a
bounded follow-up migration with its own replay.

---

## 3. Discrete-enzyme formulation — `NOT_INDIVIDUALLY_RATED_APPROVED`

**Decision.** Removal of generic collapsed `digestive_enzymes` evidence
inheritance is approved. There must be no generic evidence transfer from a
multi-enzyme formulation to unrelated discrete identities (protease, lipase,
amylase, lactase, serrapeptase, alpha-galactosidase, and other individually
modelled enzymes).

Approved clinical meaning: **no qualifying enzyme-specific formulation
evidence has been applied.**

Approved consumer presentation: **"Not individually rated"** — *we don't
currently apply enzyme-specific formulation evidence to this ingredient.*

Preferred internal semantics: `formulation_evidence_state =
NOT_INDIVIDUALLY_RATED`, `formulation_credit = none`, `formulation_penalty =
none`.

**Implementation: no new mechanism was invented.** The Formulation pillar
already owns this: `_pillar_formulation` detects an unrated form
(`iqm_form_quality_assessed_count == 0`) and applies the multi/prenatal panel's
own neutral floor (`_unrated_form_neutral_ratio`) with the reason *"Ingredient-
form quality is not rated in PharmaGuide's current data."* — i.e. the state is
**not evaluated** (neutral), not "average", and not zero. No new denominator or
normalisation was introduced.

This is **not a permanent exemption class**: once qualifying direct evidence
exists for a discrete enzyme, the row becomes rateable through the normal
rules.

---

## 4. Beta-carotene / Vitamin-A UL — `PREFORMED_VITAMIN_A_ONLY`

**Decision (closed).** Only **preformed** vitamin A (retinol, retinyl esters,
and other applicable preformed forms) participates in the preformed Vitamin-A
UL. Beta-carotene and other provitamin-A carotenoids contribute **0** to that
UL.

The resolved Bulk 1340 products supplying approximately 6.0–6.834 mg
supplemental beta-carotene receive **no retinol-UL penalty** and **no high-dose
beta-carotene Safety warning** at those resolved doses.

This behaviour was already implemented and regression-tested during Phase 3
(`rda_optimal_uls.json` declares *"UL applies to preformed vitamin A only, not
beta-carotene"*; the dose lane resolves a provitamin-A row to
`beta_carotene_no_established_ul` / `provitamin_a_carotenoid_no_established_ul`
in `_NO_UL_REASONS`; the vitamin-A pregnancy interaction gate excludes
`beta_carotene` / `mixed_carotenoids`). **Verified intact. Do not reopen.**

## 4.1 Validation

| Gate | Result |
|---|---|
| Static source-of-truth audit (`scoring-static`) | **OK, 0 findings** |
| Registry accuracy audit (`audit_banned_recalled_accuracy.py`) | **Status: pass**, 0 errors, 0 warnings, `missing_cui_annotations=0` |
| Fast tier | **15,928 passed / 0 failed / 196 skipped / 0 errors** (4:12) |
| Targeted suites | 519 passed / 7 skipped |
| Frozen-corpus replay | see "Measured effect" above |

Evidence: `FAST_TIER_CLINICAL_POLICY_20260921.md`.

## 5. Future beta-carotene Safety rule — recorded, not a Phase-3 blocker

Dr. Pham additionally recommended a future **stack-aware, personalized**
beta-carotene rule:

* `< 15 mg/day` supplemental beta-carotene → no high-dose beta-carotene penalty;
* `>= 15 mg/day` + current/former smoker or significant asbestos exposure →
  personalized CAUTION;
* `>= 20 mg/day` + those risk factors → stronger CAUTION;
* `>= 20 mg/day` with risk status unknown → contextual high-dose card.

**15 mg/day is a PharmaGuide operational threshold, not an official UL.**
There is no established beta-carotene UL.

This is **not** a Phase-3 release blocker: the Phase-3 products are
approximately 6–6.8 mg/day. Recorded here as the durable clinical/Safety
specification for a future stack-Safety phase.

---

## Measured effect — full frozen corpus

Same-input A/B over the complete frozen raw ingest corpus, base `b4ae13f6`
(`origin/main` at session start) versus the implemented candidate. Both arms
read byte-identical raw records, and the input fingerprint was verified.

| Measurement | Result |
|---|---|
| Row-level (`full_corpus_replay.py`) | 15,414 records compared, **15,414 unchanged, 0 representation changes**, 0 crashes, 0 input-fingerprint mismatches |
| Scored (`compare_scored_arms.py`) | 15,412 records compared, **0 score changes**, 16 conclusion changes, 16 Safety changes, **0 quarantine exits, 0 quarantine entries** |
| Changes outside the approved policy family | **0** |
| Largest score delta | **0** (no score moved at all) |

**Every changed id is one of the 16 standalone oral EDTA products** — the
conclusion-change set equals the EDTA set exactly. The 8 corpus products that
declare EDTA as a formulation excipient (`19178`, `200816`, `239860`, `239862`,
`256963`, `259473`, `327891`, `333921`) are **byte-identical** between arms at
both the scored and the enriched levels.

Evidence: `PHASE3_CLINICAL_ROWLEVEL_REPLAY_b4ae13f6_20260921.json`,
`PHASE3_CLINICAL_SCORED_REPLAY_b4ae13f6_20260921.json`.

### Which tree the replay validates

The only runtime surface this phase changes is
`scripts/scoring_v4/gate_safety.py` (an opt-in `verdict_reason_code` override and
an opt-in role-scope declaration) and the two authored policy entries in
`scripts/data/banned_recalled_ingredients.json`. Nothing else the clean → enrich
→ score path loads was modified, which is exactly what the 0
representation-change result shows. The post-replay edits are
non-pipeline: `cross_db_overlap_allowlist.json` is read only by
`db_integrity_sanity_check.py`, plus the three test re-baselines below and this
documentation.

## Deliberate test re-baselines

Three existing tests pinned the *pre-policy* classification. Each was updated to
the new truth, with the guard it exists for preserved — not weakened.

| Test | What changed | Why it is not a weakening |
|---|---|---|
| `test_cross_db_overlap_guard.py` | 5 new `banned:harmful` allowlist entries in `cross_db_overlap_allowlist.json` for `disodium edta`, `edta disodium`, `calcium disodium edta`, `edetate calcium disodium`, `calcium edta` | The guard exists to force an explicit, reviewed exception for cross-database term overlap. This **is** that review: the overlap is deliberate role-scoped dual-recognition (`banned_recalled` holds the declared-active policy verdict; `harmful_additives` keeps the excipient classification). The guard still fails on any unreviewed overlap, and the allowlist's non-stale/unique assertions still hold. |
| `test_preparation_identity_projection.py` | the two EDTA parametrizations now expect `recognition_source == "banned_recalled_ingredients"` instead of `"harmful_additives"` | The guard is "a recognized-but-identity-less row must not widen the required primary denominator". That still holds: `is_excipient is True`, `canonical_id is None`, coverage 1.0 and identity readiness `complete` are all still asserted. Only the owning safety source moved, because `banned_recalled` outranks `harmful_additives`. |
| `test_safety_recognition_aliases.py` | the two EDTA word-order variants now expect the policy identity; a new test pins the calcium form to its own distinct identity | The guard is "these real label forms must not surface as false identity gaps". Still asserted (the lookup must return a hit). The test got **stronger**: it now also proves the two chelating salts do not collapse into one safety identity. |

No test was deleted, skipped, or allowlisted to reach green, and no assertion was
turned into a permissive one. `test_identity_safety_separation.py` (canonical id
never comes from safety DBs) still passes unchanged.

## Status

| | |
|---|---|
| Source/data unresolved | **0** |
| Engineering unresolved | **0** |
| Clinical policy unresolved | **0** |
| Products with an undefined disposition | **0** |
| Phase-3 implementation | **COMPLETE** |
| Phase-3 clinical approval | **APPROVED WITH SPECIFIED PRODUCTS HELD** |

Phase-3 approval does **not** require every product to receive a score.
Products already dispositioned as source-insufficient, intentional
non-scoreable, policy-blocked, or Safety-card/no-score remain valid completed
dispositions; none were reopened to increase catalog coverage.
