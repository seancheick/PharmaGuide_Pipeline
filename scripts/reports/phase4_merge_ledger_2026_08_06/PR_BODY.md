# fix(scoring/export): safety projection parity, UC-II aliases, universal typed dose-safety, penalty registry

**Base** `main` @ `e69abdd1` · **Head** `codex/phase0-safety-alias` @ `ae451d17` (15 commits)

Closes the safety/export/dose-safety/tier contract work. Every product that moves is
enumerated and attributed in the merge ledger; nothing ships under a summary statistic.

---

## Phase mapping

| Phase | Content | Commit |
|---|---|---|
| **0** | Safety-field single projection + UC-II aliases (`UC II`, `uc_ii`) | `f3d82e7b` |
| **2** | Routing duplicate removed (~1.3k lines) | `f2da3d16` |
| **2** | Whole-number scores + explicit cap adjustment | `128e8dd2` |
| **3** | Universal typed dose safety + penalty registry + config provenance | `8b63fd0f` |
| **—** | ALCAR evidence form-scoping | `89ac5c4b` |
| **—** | L-carnitine evidence scoped by form | `0e23f556` |
| **—** | Release/pipeline ops (quarantine, storage contract, raw paths) | `b2a80914`, `1d845ed6`, `e7e86fc4`, `ae451d17` |
| **5** | Audit groundwork — evidence triage, reviewer benchmark | `93bcbee7`, `b9a07849`, `ae34b840` |

**Phase 4 is this PR.** Phase 5 calibration remains frozen.

---

## Scope — what is and is not here

**This PR includes two clinical-evidence commits** (ALCAR form scope + L-carnitine
daily-dose/deny-list). Their product impact is enumerated as `evidence_scope_carnitine`
and is separate from the safety/export/dose-safety contract work.

**Not in this PR:**
- BCAA mixture evidence — parked, fully characterised, separate PR after merge
- No evidence-reference recalibration
- No change to the 25% RDA dose window
- No change to the verification fail-open baseline
- No rubric denominator changes

---

## Merge ledger

`scripts/reports/phase4_merge_ledger_2026_08_06/`

| | |
|---|---|
| Products compared | **14,193** both sides, 0 only-in-one |
| Products changed | 256 |
| Score moved | 160 — 135 up / 25 down |
| Tier moved | 45 |
| Safety status moved | 89 |
| Assessment moved | 10 |
| B7 moved | 19 — 10 newly applied, 8 removed |
| **Unexpected** | **0** |
| **Double-B7 on pre-existing modules** | **0** |

### Attribution

| change_class | n |
|---|---|
| `evidence_scope_carnitine` | 137 |
| `export_safety_projection` | 81 |
| `penalty_registry_mirror` | 18 |
| `universal_b7_confirmed` | 10 |
| `unresolved_no_deduction` | 8 |
| `unresolved_caution` | 2 |

### Safety-status movement is one-directional

All **89** safety-status changes are `no_known_catalog_concern → caution`. Not one
product moves toward a less cautious state. This is the P0-1 fix landing: products
carrying a hard safety warning in the detail blob were exported as "no known concern"
because `product_safety_status` was never re-derived after the blob resolver ran.

### All three safety fields now agree — corpus-wide scan

Independent contradiction scan across all 14,193 products, on both trees:

| pattern | main `e69abdd1` | branch `ae451d17` |
|---|---|---|
| `safety_verdict=CAUTION` **and** `product_safety_status=no_known_catalog_concern` | **81** | **0** |
| legacy `verdict=CAUTION` **and** `product_safety_status=no_known_catalog_concern` | **81** | **0** |
| `product_safety_status=caution` without a CAUTION-class verdict | 0 | 0 |

Field agreement on the branch:

```
(no_known_catalog_concern, SAFE,    SAFE)        11,218
(no_known_catalog_concern, SAFE,    POOR)         2,094
(caution,                  CAUTION, CAUTION)        760
(blocked,                  BLOCKED, BLOCKED)        107
(no_known_catalog_concern, SAFE,    NOT_SCORED)      14
```

The 2,094 `POOR` rows are **not** a contradiction: legacy `verdict` carries a
score-derived vocabulary, and `POOR` maps to "no known catalog safety concern" by the
documented compatibility contract. That population is unchanged by this PR
(2,097 → 2,094). Consumers must prefer `product_safety_status`; the legacy field
remains compatibility-only.

### B7 newly applied — 10, full list in `b7_movers.csv`

All on `sports` / `fiber_digestive`, routes that previously had **no B7 path at all**.
All −2.0, all scores down, two tier drops (Weak → Poor). Independently matches the
count measured by a separate method before this ledger existed.

### B7 removed — 8, the unresolved policy

Unresolved exposure no longer takes an unproven harm deduction; the assessment is
marked partial/review instead. The affected products are exactly the population
predicted when the defect was first documented: flush-free niacin ×2 and no-flush
niacin (inositol hexanicotinate) ×2 — compared against the nicotinic-acid limit — plus
potassium iodide 130 mg, a bone-strength collagen formula, and two others. Scores rise
because an unproven deduction was withdrawn, not because a finding was suppressed:
these products still carry CAUTION + review.

### Carnitine evidence scope — 137 movers, 126 up / 11 down

The ups are plain L-carnitine and L-carnitine tartrate gaining legitimate credit from
the corrected record. **Every one of the 11 declines is an acetylated or salt form
ceasing to borrow evidence from generic L-carnitine** — the exact purpose of the two
commits. No product is penalised; products stop being credited for evidence that was
never about their form or their dose.

| product | Δ | why |
|---|---|---|
| Carnitine 500 (Carnipure™) | −13.0 | Record corrected from a claimed 224 participants / 5 trials to the 28 people its two cited trials actually enrolled; "strong energy/heart" framing removed from recovery biomarkers. The largest drop belongs to the most inflated record. |
| Acetyl-L-Carnitine Arginate ×4, Advanced ALCAR | −7.9 each | Arginate is a distinct salt on the deny-list; stops borrowing generic L-carnitine evidence. |
| Cognitive Focus | −7.9 | Carries Acetyl-L-Carnitine HCl at **75 mg**, far below the 1,500–3,000 mg/day reviewed range. |
| Acetyl-L-Carnitine / ALCAR ×3 | −6.3 each | ALCAR scoped to its verified indication rather than broad focus/energy claims. |
| L-Carnitine 1000 Tropical Punch | −1.6 | L-carnitine tartrate — a permitted form; small shift from the corrected record, not exclusion. |

---

## Method, and its documented limit

```
method: score_and_export_on_fixed_enriched_snapshot
not_measured: ["re_enrichment_identity_matching"]
pins: { main: e69abdd1, branch: ae451d17 }
```

Both sides score the **same** enriched corpus (14,193 products, rebuilt on branch code
immediately before the run and verified stable across two counts) and run it through
`project_export_scored_artifact` with **real detail blobs**, so the export blob-warning
path is exercised rather than skipped.

Module, archetype and B7 are read from the pre-projection artifact
(`_v4_module_breakdown`, `dose_safety_evaluation`); score, tier, safety status and
verdict from the projected export row.

Enrichment is not re-run inside the ledger, so enricher-only identity re-matching is
out of scope; those effects were measured in their own commits.

---

## Risk

Score and status movement is **expected and enumerated**. The clinically significant
direction is that 89 products become *more* cautious and 10 gain a dose-safety
deduction that was previously invisible. The 8 products that lose a deduction do not
lose their warning — they lose an unproven number.

---

## Verification

```bash
scripts/test.sh fast -k "safety_parity or penalty_registry or dose_safety or uc_ii or collagen_taxonomy or export_gate or build_final_db"
```
**338 passed, 0 failed** at `ae451d17`.

Flutter tier authority audited end-to-end: every catalog surface (hero, search, compare,
breakdown, alternatives ranker, share, clinician report) consumes the shipped
`quality_tier`. The only remaining `legacyTierForScore` call is an onboarding preview
widget with a hardcoded score, and that fallback now mirrors the pipeline bands.

**Local dist:** rebuilt on branch code, `quality_score_version` `1.0.5-b7-single-source`,
`raw_score_v4_100` absent from the public export, 0 CAUTION-vs-no-known contradictions.
