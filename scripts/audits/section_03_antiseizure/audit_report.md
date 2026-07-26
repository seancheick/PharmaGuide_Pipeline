# Section 3 — Antiseizure medication relationships

**Date:** 2026-07-26 · **Applier:** `apply.py` (idempotent) · **Tests:** `scripts/tests/test_med_nutrient_antiseizure.py`

## The defect

All seven `DEP_ANTICONVULSANTS_*` records were attributed to `class:anticonvulsants`
— 40 members spanning drugs with **opposite** hepatic pharmacology. Each record's
own mechanism prose already named the real actors; the attribution never followed
it. A levetiracetam, lamotrigine or gabapentin patient was therefore warned about
CYP450-induction effects those drugs do not cause.

`class:anticonvulsants` had no other consumer — no interaction rule references it —
so the blast radius was exactly these seven records.

## Two mechanisms, two attributions

| Record | Mechanism in its own prose | Was | Now |
|---|---|---|---|
| VITAMIND | enzyme induction | `enzyme_inducing_…` | unchanged (still `needs_revision`) |
| CALCIUM | secondary to vitamin D + phenytoin direct | `anticonvulsants` | `enzyme_inducing_…` |
| VITAMINK | CYP2C9 induction | `anticonvulsants` | `enzyme_inducing_…` |
| FOLATE | phenytoin / carbamazepine conjugase + DHFR + CYP | `anticonvulsants` | `enzyme_inducing_…` |
| LCARNITINE | valproate acylcarnitine conjugation | `anticonvulsants` | `class:valproate` |
| BIOTIN | valproyl β-oxidation, biotinidase inhibition | `anticonvulsants` | `class:valproate` |
| VITAMINB12 | "may reduce" / "may also increase" | `anticonvulsants` | **suppressed** (`needs_revision`) |

## `class:valproate` (new)

One moiety, four dispensed salts — the form on the label must not decide whether
the patient is warned. All content-verified live against RxNorm on 2026-07-26:

| rxcui | name |
|---|---|
| 266856 | divalproex sodium (Depakote) |
| 9919 | sodium valproate |
| 40254 | valproate |
| 11118 | valproic acid |

Kept deliberately separate from `class:enzyme_inducing_antiseizure_medications`:
valproate **inhibits** CYP450, so it shares none of the induction-driven
depletions. ATC `N03AG01`.

## Decisions and why

- **B12 suppressed, not deleted.** Its mechanism hedges ("may reduce"), its
  `evidence_level` is only `probable`, and its sole source is an NLM *catalog*
  entry rather than a study. Shipping a B12 depletion claim against a whole
  antiseizure class on that basis over-warns. It returns with a content-verified
  PMID and a drug-specific scope.
- **Prose rewritten alongside the attribution.** FOLATE dropped valproate from its
  mechanism/recommendation; BIOTIN dropped carbamazepine. Repointing a `drug_ref`
  while leaving text that names out-of-scope drugs is how stale wording reaches
  the app blob — a dedicated test asserts the copy never claims "all seizure
  medications".
- **Carbamazepine–biotin deferred.** Real but far weaker than the valproate
  evidence, and the two act by different mechanisms, so it does not belong in a
  valproate-scoped record. Recorded in the inducer class note beside the existing
  oxcarbazepine deferral.
- **Sprint 3's freeze lock was narrowed, not deleted.** It said these records
  "must NOT be repointed *in Sprint 3*", and its stated concern was that biotin
  and L-carnitine must never ride the enzyme-inducing class. Section 3 performed
  the review the freeze was waiting on; the durable clinical invariant survives as
  `test_valproate_records_never_ride_the_enzyme_inducing_class`.

## Verification

- `verify_drug_class_rxcuis.py` — 818 rxcuis / 39 classes, all resolve to their authored drug
- `verify_medication_depletion_identifiers.py` — all direct-drug rxcuis + class refs resolve
- `scripts/test.sh fast` — 10,819 passed, 0 failed
- App: reference data synced, `med_nutrient_bundled_parity_test` green, 384 stack/interaction tests green
- Content hash `sha256:76a4368…` → `sha256:d883d89…`, repinned in the pipeline artifact test and the app parity test

## Still open in Section 3

1. **`DEP_ANTICONVULSANTS_VITAMIND` is still suppressed** (`needs_revision`) — the
   attribution is right but it needs a content-verified PMID to ship.
2. **B12 needs a real citation** and a drug-specific scope before it can return.
3. **Citations generally** — five of the seven records still cite NIH ODS fact
   sheets rather than primary literature. Only VITAMINK carries a PMID (14506311).
4. **`class:valproate` reaches devices only after the next interaction-DB
   release** — the bundled SQLite predates it, so the two valproate records do not
   match yet (fails safe: no match, no warning).
5. **`class:anticonvulsants` now has one remaining consumer** (the suppressed B12
   record). Retiring or repurposing the 40-member class is a separate decision.
