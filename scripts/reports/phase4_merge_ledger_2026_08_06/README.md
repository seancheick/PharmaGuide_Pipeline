# Phase 4 merge ledger — `codex/phase0-safety-alias` → `main`

Product-level change ledger for the merge gate. Every product whose score,
tier, safety status, assessment, verdict, pillar or B7 differs between the two
trees is enumerated and assigned a `change_class` plus an `expected_reason`.
Anything unattributable lands in `unexpected`, which blocks the merge.

## Pins

| | |
|---|---|
| baseline | `origin/main` **e69abdd1** — *fix(scoring): stabilize joint collagen routing (#52)* |
| candidate | `codex/phase0-safety-alias` **ae451d17** — *fix(release): make orphan quarantine survive listing lag* |
| enriched snapshot | `scripts/products/*/enriched/` — 14,193 products, identical input to both sides |
| detail blobs | `scripts/dist/detail_blobs/` — passed through so the export blob-warning path is exercised |
| BCAA WIP | **excluded** — parked at `stash@{0}` "bcaa-evidence-wip" before the run |

## Method, and what it does not cover

```
enriched product ──> build_scored_artifact ──> project_export_scored_artifact ──> row
                          │                              │
                          └── module, archetype,         └── score, tier, safety_status,
                              B7, dose dimensions            assessment, verdict, blocking_reason
```

`method: score_and_export_on_fixed_enriched_snapshot`
`not_measured: ["re_enrichment_identity_matching"]`

**Measured.** Stage-3 scoring and the export projection, including the ALCAR /
L-carnitine *scoring-path* effects (daily-dose comparator fix, exact-form
deny-list).

**Not measured.** Enrichment is not re-run, so enricher-only identity
re-matching is out of scope. Those effects were measured in their own commits
(`89ac5c4b`, `0e23f556`). This is an accepted tradeoff for the merge gate; a
full Clean→Enrich double run is only warranted if v2 shows a large
unexplained residue.

## A defect in ledger v1, and the fix

`project_export_scored_artifact` **drops `v4_breakdown`**. v1 read `b7`,
`module` and `archetype` off the projected row, so all three came back empty on
*both* sides. That made `b7_moved: 0` a measurement artifact rather than a
finding, and left the `universal_b7_confirmed` and `unresolved_no_deduction`
branches unreachable — precisely the classes the merge most needs proven.

v2 reads those fields from the pre-projection artifact and the consumer-facing
fields from the projected row. v1's `unexpected == 0` was **not** a trustworthy
PASS and was not treated as one.

## `change_class` enum

| class | meaning |
|---|---|
| `export_safety_projection` | `product_safety_status` / verdict / blocking reason reconciled |
| `uc_ii_alias` | joint dose identity restored (`UC II`, `uc_ii`) |
| `universal_b7_confirmed` | B7 applied on a route that previously had none |
| `unresolved_no_deduction` | unresolved no longer deducts; partial / review instead |
| `unresolved_caution` | gate CAUTION + review for an unresolved exposure |
| `penalty_registry_mirror` | penalty mirrored or relocated to its owning pillar |
| `public_cap_presentation` | cap adjustment / whole-number reconcile only |
| `tier_label_only` | score unchanged, tier string now pipeline-owned |
| `config_version_stamp` | metadata only |
| `evidence_scope_carnitine` | ALCAR / L-carnitine evidence scoping carried on this branch |
| `unexpected` | **blocks merge** |

`evidence_scope_carnitine` is a first-class class, not a residue bucket. The
branch is not purely architectural: it carries two clinical-evidence commits,
and folding their movers into `penalty_registry_mirror` would have hidden them.

## Files

| file | contents |
|---|---|
| `summary.json` | pins, method, counts, crosstab, top-20 deltas, gate results |
| `changed_products.csv` | every mover, with class and expected_reason |
| `safety_status_movers.csv` | full list — not a sample |
| `b7_movers.csv` | every B7 attribution |
| `double_b7_suspects.csv` | modules that already had B7 now deducting more — must be empty |
| `unexpected.csv` | must be empty |

## Gates

- `unexpected == 0`
- `no_double_b7_on_old_modules` — the universal adapter must not stack on top of
  a module's own B7 deduction (`generic`, `multi_or_prenatal`, `b_complex`)
- `both_sides_full_corpus` — 14,193 on each side, zero only-in-one
- every safety-status mover attributed and reviewable in prose
