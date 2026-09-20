# Phase-3 Quarantine Remediation — Independent Integration & Release-Gate Report

**Prepared by:** integration owner (engineering), 2026-09-20
**Authority:** engineering validation only. This report does **not** constitute the licensed-pharmacist
clinical release decision required by the original Phase-3 process (§20 of the brief).

---

## A. Integration

| Item | Value |
|---|---|
| Frozen source branch | `remediation/quarantine-clearing-20260919` @ `4bd49c0d` |
| Remediation base / integration base | `124982a0` |
| Cherry-pick #1 | `77cbb38c` → `31c5d8ca` (**clean**) |
| Cherry-pick #2 | `7ebf6c46` → `e4f69906` (**clean**) |
| Documentation commits retained | `c68cb7eb` → `6dab0b77`, `af9ae8d6` → `ac4db509`, `4bd49c0d` → `095d27a1` |
| **Resulting integration HEAD** | **`095d27a1`** |
| Conflicts encountered | **0** |
| Runtime tree equality | `095d27a1^{tree}` = `4bd49c0d^{tree}` = `e40f06073d1c72564f58499bc3ed5e2e6ec4b2b9` — **byte-identical to the accepted frozen tip** |
| Integration worktree | `<worktree>` (clean worktree; the shared checkout was **not** used) |
| `main` / `origin/main` | `ad577f49` — **an ancestor** of the integration HEAD |

### Base-target note (§3 / §1 / §4 amendment)

The brief's §3 anticipates that the target may have advanced past the remediation base.
**It has not.** `main` and `origin/main` both remain `ad577f49`, which is an *ancestor* of the
branch lineage — i.e. `main` is 7 commits **behind** the remediation base, not ahead of it.

Consequence (verified independently, consistent with the prior agent's finding): the two-commit set
is **not** self-sufficient on `main`. A probe worktree at `main` produces
`CONFLICT (content) in scripts/data/ingredient_quality_map.json` on `git cherry-pick -n 77cbb38c`,
because `77cbb38c`'s IQM blob is reconciled against `124982a0`'s 636-entry set (Nickel/Tin identities
etc.) and `main`'s IQM has neither those entries nor the dependent test files.

**Therefore integration was performed on `124982a0`**, which is:
* the branch's declared base,
* the base against which the accepted fast-tier evidence was recorded, and
* an ancestor of `main`, so the result promotes to `main` by fast-forward/merge without conflict.

Because `main` is an ancestor, the *whole lineage* `77037d9f..4bd49c0d` also integrates
conflict-free — the opposite of the two-commit subset. Which packaging is accepted (final increment
only vs. whole lineage) is an owner decision, not an integrator decision.

No peer work was discarded, reset, stashed, staged, or folded in. Nothing was pushed.

---

## B. Tests

Same machine, same environment, same tree layout — base arm vs. integrated arm:

| Arm | Tree | Result | Failure set |
|---|---|---|---|
| Base | `/tmp/pg_base` @ `124982a0` | **1 failed, 15,769 passed, 189 skipped** (271.60s) | `{static_audit}` |
| Integrated | `095d27a1` | **1 failed, 15,789 passed, 189 skipped** (290.63s) | `{static_audit}` |

* **New failures introduced by the remediation: 0.**
* **Pre-existing failures: 1**, identical in both arms:
  `scripts/tests/test_scoring_source_of_truth_audit.py::test_static_audit_current_v4_modules_have_no_forbidden_fallbacks`
  → `Finding(code='V4_IQD_INGREDIENTS_FALLBACK', ... scripts/scoring_v4/modules/generic_evidence.py:472 reads forbidden ... fallback field')`
* Pass delta +20 = the new remediation regression tests. Skip count identical (189).
* The remediation team's recorded counts (15,787/191) differ only because that run used a
  differently-populated tree; the **failure set is identical** and the recorded conclusion holds:
  the post-remediation failure set equals the base failure set.
* Quarantine/readiness, schema, vocabulary, cleaner/normalizer, scoring-input contract, Safety,
  identity-integrity, evidence/scoring and static audits are all inside this tier.

---

## C. Full frozen-corpus replay

Harness: `scripts/audits/quarantine_triage_20260919/drive_pipeline_ab.py` (clean → enrich → score,
15,412 records per arm, **identical raw corpus** for both arms) compared with
`scripts/audits/quarantine_triage_20260919/compare_scored_arms.py`.

This is a **same-input** A/B — the only comparison that supports causal attribution (§9).
Deltas measured against the *shipped* baseline carry input drift and are deliberately **not** used
for attribution.

| # | Output | Result |
|---|---|---|
| 1 | Products replayed | **15,412 before / 15,412 after** (`only_in_before` = 0, `only_in_after` = 0) |
| 2 | Crashes | **0** / 0 (`crash_like_before` = 0, `crash_like_after` = 0) |
| 3 | Representation changes | 922 products; roles + ledger, reconciled exactly (below) |
| 4 | Numerical score changes | **15** (max \|Δ\| = 24.9) — table below |
| 5 | Quarantine exits | **6** — all attributable, all in contract families A/B/C |
| 6 | New quarantine entries | **0** |
| 7 | Safety-gate changes | **0** |
| 8 | Changes outside expected families | **0** |
| 9 | Largest score deltas | `294897` **+24.9**; next `40603` **+2.7**; all others ≤ ±2.6 |

`bookkeeping_only_changes` = **15,391** — every one a single-field inert metadata annotation
`forms: [] → ["ALA"]` (verified score-inert: the forms field does not feed the scorer; a targeted
scored A/B on affected products differs only in `scored_date`).

### Representation changes — exact reconciliation (corpus-wide row roles)

| Role | Before | After | Δ |
|---|---:|---:|---:|
| `active_scorable` | 79,706 | 79,357 | **−349** |
| `blend_header_total` | 5,914 | 5,913 | −1 |
| `daily_value_no_amount` | 0 | **279** | **+279** |
| `nested_display_only` | 27,857 | 27,857 | 0 |
| `source_descriptor` | 1 | 1 | 0 |
| `specification_limit` | 0 | **1** | **+1** |
| `standardization_marker` | 0 | **12** | **+12** |

**Arithmetic closes:** −350 rows left the scorable-active band; +292 were re-roled in place
(279 %DV-without-amount → contract D, 12 standardization markers → contract C,
1 contaminant specification limit → contract B); net **−58** rows left the active display.

Source-row ledger, which proves nothing was silently lost:

| Counter | Before | After | Δ |
|---|---:|---:|---:|
| `raw_actives_count` (source rows) | 189,639 | 189,639 | **0** |
| `active_rows` (displayed actives) | 113,478 | 113,420 | −58 |
| `label_ledger_omissions` | 68,232 | 68,294 | **+62** |

**Every one of the 58 rows that left the active display is covered by the +62 ledger omissions**
(each carrying `raw_source_path` + `raw_source_text`). Zero source rows lost, zero raw actives lost.

### Score changes (all 15) — every one attributable

| DSLD | Product | Before | After | Δ | Responsible component |
|---|---|---:|---:|---:|---|
| 294897 | Krill Oil Softgels 500 mg | 40.1 | 65.0 | **+24.9** | omega aggregate ownership → dose 0→13, evidence floor 5.51→10, concentration band added |
| 40603 | Capture | 56.8 | 59.5 | +2.7 | evidence floor / formulation component |
| 302759 | Calcium 600 mg | 79.4 | 76.8 | −2.6 | evidence floor |
| 44423 | Deglycyrrhized Licorice Root Extract | 66.5 | 68.4 | +1.9 | evidence floor |
| 216776 | Herbal Complex | 72.1 | 74.0 | +1.9 | evidence floor |
| 246421 | Triple Immune Power Natural Berry Citrus | 38.6 | 37.5 | −1.1 | evidence floor |
| 16801 | Lean Muscle Meal Chocolate | 53.2 | 54.0 | +0.8 | evidence floor |
| 16846 | Lean Muscle Meal Vanilla | 47.9 | 48.7 | +0.8 | evidence floor |
| 78016 | Alive! Sport Tropical Fruit | 76.6 | 75.8 | −0.8 | evidence floor |
| 214452 | Earth Source Organic Cold-Milled Flax | 58.6 | 59.1 | +0.5 | evidence floor |
| 269824 | Women's Prenatal Gummies with Folic Acid | 70.6 | 70.2 | −0.4 | evidence floor |
| 270736 | Women's Prenatal Gummies | 70.6 | 70.2 | −0.4 | evidence floor |
| 15919 | Multi Vitamin+ Apricot-Mango | 39.1 | 39.3 | +0.2 | evidence floor |
| 15923 | Multi Vitamin+ Cherry-Pomegranate | 39.1 | 39.3 | +0.2 | evidence floor |
| 77254 | Male Multiple | 68.2 | 68.4 | +0.2 | evidence floor |

No component is a *global* weight/threshold change (§18). The +24.9 outlier is the intended
contract-A fix and is a *positive* signal, not a debugging anomaly: the parent's 300 mg is now the
dose owner where previously the product carried zero-dose children.

### Quarantine exits (6) — all in contract families

| DSLD | Product | Before | After | Gate cleared | Contract |
|---|---|---|---|---|---|
| 75188 | Fish Oil | `not_scored / blocked_by_completeness_gate` | `scored`, `score_candidate` | completeness | **A** omega aggregate ownership |
| 243713 | Fish Oil | `not_scored / blocked_by_completeness_gate` | `scored`, `score_candidate` | completeness | **A** |
| 75291 | Fish Oil Lemon | `not_scored / blocked_by_completeness_gate` | `scored`, `score_candidate` | completeness | **A** |
| 216948 | PM Phytogen Complex | `not_scored / blocked_by_completeness_gate` | `scored`, `score_candidate` | completeness | **C** Pueraria standardization |
| 232718 | Longevity A.I. | `not_scored / blocked_by_completeness_gate` | `scored`, `score_candidate` | completeness | **C** Withaferin A |
| 328464 | Ginkgo Biloba Certified Extract 120 mg | `not_scored / blocked_by_completeness_gate` | `scored`, `score_candidate` | completeness | **B** contaminant specification limit |

**No new quarantine entries. No Safety-gate change. No exit outside the intended families.**

---

## D. Behavioral-contract verification (empirical, on the integrated code)

### A. Omega-3 aggregate ownership — PASS (both cases)

`75188`, `243713`, `75291` — before: 2 phantom actives `DHA 0.0 unspecified`,
`EPA 0.0 unspecified`; after: **1 active** `Total Omega-3 Fatty Acids — 300 mg`.
The parent quantity survived as the dose owner and was **not** transferred to EPA/DHA.
DHA/EPA are recorded in `label_ledger_omissions` with explicit `raw_source_path`
(`ingredientRows[3].forms[0/1]`) and `raw_source_text` — traceable, not silently dropped.

Independent amount case: where a label declares independent EPA/DHA quantities they remain
independently scoreable (no site transfers a parent total downward).

*Contract-gap note (non-blocking — see §I.2):* the omission `omission_reason` for these aggregate
children is `duplicate_source_line`. That is **not** a free-form string: it is a member of a closed,
validated set, so the remediation is *forced* to reuse it —
the vocabulary has no value expressing "subordinate to a dosed parent". This is an expressiveness
**gap in the contract**, not a code-quality nit, and changing it is a contract change with its own
replay requirement.

### B. Specification/contaminant limits — PASS (contextual, not ppm-driven)

`328464` Ginkgolic Acid row after integration:

```
raw_source_path          ingredientRows[0].nestedRows[0]
parentBlend              "Ginkgo biloba Leaf Extract"
isNestedIngredient       true      nested_depth 1
cleaner_row_role         specification_limit
score_eligible_by_cleaner false
score_exclusion_reason   specification_limit_contaminant
dose_class               specification_limit
quantity / unit          1.0 ppm        (preserved)
```

Preserved as specification/provenance metadata; removed from score eligibility. The Ginkgo extract
row itself stays `active_scorable` (120 mg) as the dose owner.

**ppm alone did not determine the role:** corpus-wide there is exactly **1** ppm/ppb row, it is
*nested under a parent*, and no top-level ppm/ppb ingredient disappeared. No broad ppm/ppb
extinction (§10 stop condition).

### C. Botanical standardization relationships — PASS

* `216948`: `standardized Pueraria mirifica root extract — 80 mg` remains the primary botanical/dose
  owner; `Miroestrol 16 mcg` and `Isoflavonoids 16 mcg` remain traceable standardization
  constituents (12 `standardization_marker` roles corpus-wide).
* `232718`: `Withaferin A — 12 mg` preserved with quantity, ashwagandha parent provenance, canonical
  identity — **and Safety**:

  | | Before | After |
  |---|---|---|
  | `safety_verdict` | CAUTION | **CAUTION** |
  | `safety_signal_reason` | `B0_WATCHLIST_SUBSTANCE` | **`B0_WATCHLIST_SUBSTANCE`** |
  | `product_safety_status` | `caution` | **`caution`** |
  | `mapped_coverage` | 0.6667 | 1.0 |
  | `scoring_status` | `not_scored` | `scored` |

  Only the completeness/mapping gate cleared. **Safety is byte-identical.**
  Identity remediation did not bypass Safety. (§5F PASS)

### D. %DV without amount — PASS

279 rows re-roled to `daily_value_no_amount`; none became scoreable, and no
reverse-calculation from %DV exists anywhere in the diff.

### E. No plausibility-based unit repair — PASS

The remediation introduces no mg↔mcg, IU, or DFE/RAE reinterpretation. `unit_conversions` and the
correction-receipt path are untouched by `77cbb38c`/`7ebf6c46`. The `1 ppm` value was preserved
verbatim rather than "repaired".

### F. Safety independence — PASS

0 Safety-gate changes corpus-wide; the one product whose watchlist classification was at risk
(`232718`) retains it unchanged. No valid Safety rule was disabled by identity work.

### `7ebf6c46` independent verification (§7)

Diff is **4 added lines in one test file** (`scripts/tests/test_cross_db_overlap_guard.py`), adding
exactly `("withaferin_a","WATCH_WITHAFERIN_A")` and `("miroestrol","RISK_MIROESTROL")` to the
intentional dual-classification exact-set. Banned checks, recalled checks, the exact-set assertion
(`observed_parent_ids`), the permissive-negative check
(`assert ("citrus_bioflavonoids","RISK_BITTER_ORANGE") not in observed_parent_ids`), and the status
validation (`assert all(status in {"high_risk","watchlist"} ...)`) are **all untouched**.
No broadening. **PASS.**

---

## E. Remaining problems

1. **`V4_IQD_INGREDIENTS_FALLBACK` — `scoring_v4/modules/generic_evidence.py:472`.**
   Code: `iqd = product.get("ingredient_quality_data")` … `iqd["ingredients"]` read.
   Present at base `124982a0`; **not** present on `main`. Not a regression of this remediation.
   *Status: open, with an identified owner and an existing uncommitted fix — see §F blocker.*
2. **Peer uncommitted dependency (integration-hygiene blocker).** See §F.
3. E2 unit-corruption cases ×6 — unresolved; require source evidence, **no** plausibility repair.
4. `needs_info` ×4 (`12300`, `75291`, `254396`, `254413`) — **`75291` RATIFIED** as
   `needs_info → fixed_mechanically after direct source verification` (§I.1). The other three
   (`12300`, `254396`, `254413`) still require source evidence.
5. EDTA ×16 (all BulkSupplements) — Safety **policy** disposition, not normalization. Standalone
   orally marketed EDTA must not be silently reclassified as an excipient; calcium disodium vs.
   disodium EDTA must stay distinguishable. **Owner: Safety policy. Not an engineering call.**
6. Vitamin-A form/completeness gap — the affected rows carry **two competing quantity variants**;
   this is a *source-ambiguity* condition, not a missing-amount condition.
7. Bulk 1340 residual — heterogeneous family (legitimate max-labeled-exposure Safety findings,
   stale source, duplicated folate rows in ≥1 historical record, Vitamin-A form issues).
   **Do not treat as one bug.**
8. Stale-source handling — all 21 re-checked Bulk 1340 SKUs returned
   **`unchanged_since_snapshot`**; the handoff's stale-source hypothesis is **not** supported by
   the live comparison. Source refresh remains a deliberate, auditable pipeline operation.

---

## F. Blocker — integration hygiene: the peer seam is not committed

The clean integration worktree **still fails** `V4_IQD_INGREDIENTS_FALLBACK`, so `scripts/test.sh fast`
is **1 failed / 15,789 passed / 189 skipped**, not 0 failures.

The shared checkout `<shared-checkout>` @ `4bd49c0d` **passes** that test — but
only because of a peer session's **uncommitted** working-tree changes. Verified directly:

```
SHARED (4bd49c0d + peer uncommitted):   1 passed in 0.16s
CLEAN  (095d27a1, no peer diff):        1 failed in 0.16s
```

The peer's `scripts/scoring_v4/modules/generic_evidence.py` hunk deletes exactly:

```diff
-    iqd = product.get("ingredient_quality_data")
-    if isinstance(iqd, dict) and isinstance(iqd.get("ingredients"), list):
-        candidate_rows = [r for r in iqd["ingredients"] if isinstance(r, dict)]
```

and adds probiotic-disposition wiring (`has_probiotic_component`, `disposition_state`).

Peer-dirty **tracked** files (8) in the shared checkout:

```
 M scripts/data/backed_clinical_studies.json
 M scripts/data/ingredient_quality_map.json            (4333 lines changed)
 M scripts/enrich_supplements_v3.py
 M scripts/scoring_v4/modules/generic_evidence.py      <-- the fallback
 M scripts/scoring_v4/modules/probiotic_evidence.py
 M scripts/studied_formulas.py                          (127 added lines)
 M scripts/supplement_taxonomy.py
 M scripts/tests/test_existing_iqm_identity_recovery.py
```

With 8 tracked files including a large IQM overhaul plus a new `studied_formulas` block, this is a
**substantial independent feature in flight**, not a one-line fix.

**Required action (peer owner):**
1. commit the change;
2. run its focused tests (probiotic cross-module evidence, generic evidence, fallback guard);
3. hand the **exact commit SHA** to the integrator.

**Then (integrator):** fresh-fetch `main`; integrate that commit normally; re-run the fallback guard,
the probiotic/evidence tests, and the same-input A/B if that path can alter output.

**Do not** copy the file out of the peer's dirty checkout, and **do not** silently allowlist the
finding. No waiver has been recorded by an owner.

---

## G. Health assessment

| Question | Answer | Evidence |
|---|---|---|
| Known data loss | **NO** | `raw_actives_count` 189,639 → 189,639 (Δ 0); 58 display rows removed, offset by +62 ledger omissions with source paths |
| Fabricated doses | **NO** | no synthesized/equal-split/inferred amounts; parent quantities never transferred downward |
| Lost Safety signals | **NO** | 0 Safety-gate changes; `232718` CAUTION + `B0_WATCHLIST_SUBSTANCE` identical before/after |
| New false clears | **NO** | 6 exits, each mapped to a named contract family A/B/C; 0 outside expected families |
| New false quarantines | **NO** | 0 new quarantine entries |
| Unexpected cross-family changes | **NO** | `outside_expected_families` = 0 |
| New unresolved regressions | **NO** | failure set identical to base; pass delta +20 |

---

## H. Final recommendation

**Integration complete:** **YES** — `095d27a1`, tree byte-identical to the accepted frozen tip,
0 conflicts, cherry-pick order preserved, no peer work touched.

**Ready for main:** **NO** — one blocker remains: the peer session's uncommitted
`generic_evidence.py` fallback deletion / probiotic seam must be committed and integrated before the
final tree can satisfy the 0-failure release gate. Until then there is no single canonical final
brain: the clean tree fails and the shared checkout passes only because of an uncommitted change.

**Ready for production:** **NO** — additionally requires the outstanding release process:
licensed-pharmacist clinical sign-off (§20), the EDTA ×16 Safety-policy disposition,
the E2 ×6 source corrections, and the Bulk 1340 / Vitamin-A source work.

**Remediation branch safe to delete:** **NO** — retain
`remediation/quarantine-clearing-20260919` until the accepted changes are durable on the
integration/main lineage *and* these audit artifacts are preserved.

### Conditions to flip "Ready for main" to YES

1. peer commit integrated by exact SHA (and re-run of the fallback guard + probiotic/evidence tests);
2. `scripts/test.sh fast` → **0 failures** on the exact final SHA (repair data against the canonical
   IQM schema; **do not loosen tests**);
3. `git fetch origin`; clean worktree; no staged changes; no uncommitted peer dependencies;
4. freeze that SHA and stop mutation — no further remediation/scoring change after the freeze.

### Integral recommendation

The remediation logic itself is **sound and evidence-supported**: every gate output is attributed,
the ledger reconciles exactly, and the seven healthy/health assessment questions all answer NO.
The residual risk is **integration hygiene, not logic**.

---

## I. Ratifications and open decisions

### I.1 DSLD 75291 — exit RATIFIED (product-specific verification, not neighbour inference)

§14 required that these four SKUs not be judged from neighbouring records. `75291`'s exit was
justified against **its own frozen source record** (`/tmp/pipelineA/raw/75291.json`):

```
ingredientRows[3]  name='Total Omega-3 Fatty Acids'
                   quantity=300, unit='mg'                 <-- its own declared label value
                   servingSizeQuantity=1, servingSizeUnit='Softgel Capsule(s)'
                   forms=['Docosahexaenoic Acid','Eicosapentaenoic Acid']   <-- forms, no independent amounts
```

The 300 mg is declared on 75291's own label, and no independent EPA/DHA quantity exists anywhere in
the record. The DHA/EPA entries are **forms of the parent row**, not independently dosed actives.
The parent therefore correctly owns the dose.

**Ledger disposition:** `needs_info` → **`fixed_mechanically after direct source verification`**.
This is product-specific source verification, not inference from the other GNC fish oils.

### I.2 Omission-reason vocabulary is a closed contract (not a rename)

`scripts/enrichment_contract_validator.py:188`

```python
LABEL_LEDGER_OMISSION_REASONS = frozenset({
    "nutrition_fact_not_applicable",
    "decorative_or_header_text",
    "duplicate_source_line",
    "empty_source_text",
    "unsupported_source_structure",
})
```

* enforced at `enrichment_contract_validator.py:2009` (out-of-set reason → contract violation,
  `expected=sorted(LABEL_LEDGER_OMISSION_REASONS)`);
* pinned by `test_H7_omission_reason_closed_set_accepts_exact_values`
  (`scripts/tests/test_contract_validation.py:1445`) over exactly those five values;
* **untouched by the remediation** — `git log 124982a0..HEAD -- scripts/enrichment_contract_validator.py` is empty.

**Decision:** `duplicate_source_line` is retained for the omega aggregate children. A more accurate
code (`subordinate_to_dosed_parent` / `constituent_without_independent_dose`) is a **contract change**
requiring the frozenset update, the H7 test extension, and a fresh enrichment-stage replay.
It is a deliberate follow-up and is **not a release blocker**, because no downstream clinical or
audit contract currently depends on the distinction — the omitted rows remain fully traceable
(`raw_source_path` + `raw_source_text` are preserved on every ledger entry).

### I.3 Open decisions requiring owners other than engineering

| Item | Owner |
|---|---|
| EDTA ×16 standalone oral product treatment | **Safety policy** |
| E2 ×6 unit-corruption correction receipts | source/clinical |
| Bulk 1340 residuals + Vitamin-A form/completeness gap | source/clinical |
| `V4_IQD_INGREDIENTS_FALLBACK` seam | evidence/scoring session (see handoff) |
| Clinical release sign-off | **licensed pharmacist** (§20) |

**Peer handoff issued:** `.agents/HANDOFF_TO_EVIDENCE_OWNER_PHASE3_20260920.md`
(in the shared checkout, git-ignored so the frozen branch worktree stays clean).

---

## J. Reproduce

Paths below use placeholders: `<worktree>` = the integration worktree, `<shared-checkout>` = the
primary checkout. The frozen raw corpus root is given as a user-relative `~/Downloads/...` path.
Scratch replay outputs were written under `/tmp` and are named inline. No credentials, tokens or
personal data appear in these artifacts.

```bash
cd <worktree>
source <shared-checkout>/scripts/python_env.sh
RAW=~/Downloads/PharmaGuide_Datasets/staging/brands
H=scripts/audits/quarantine_triage_20260919

# same-input A/B (two arms, ~30-35 min each, ~2 GB)
$PG_PYTHON $H/drive_pipeline_ab.py --arm base       --scripts-dir /tmp/pg_base/scripts \
  --raw-root "$RAW" --out-root /tmp/pipelineA --enrich-workers 2
$PG_PYTHON $H/drive_pipeline_ab.py --arm integrated --scripts-dir "$PWD/scripts" \
  --raw-root "$RAW" --out-root /tmp/pipelineB --enrich-workers 2

# attribution
$PG_PYTHON $H/compare_scored_arms.py \
  --before /tmp/pipelineA/scored_records.jsonl \
  --after  /tmp/pipelineB/scored_records.jsonl \
  --out    /tmp/scored_diff_base_vs_int.json \
  --expected-ids /tmp/expected_union.json \
  --label-before "base 124982a0 (same inputs)" \
  --label-after  "integrated 095d27a1 (same inputs)"

# cleaner-level invariants and Phase-3 dispositions
$PG_PYTHON $H/audit_cleaner_deltas.py ...
$PG_PYTHON $H/phase3_disposition.py ...

# suite
./scripts/test.sh fast
```

---

## K. Sealed Phase-3 disposition (accepted by the release owner)

**Phase-3 integration is FROZEN at `095d27a1`.** No further Phase-3 engineering changes are to be
made while the independent evidence-scoring seam is outstanding.

### Verdict

```
Integration complete:                          YES
Phase-3 remediation regression identified:    NO
Ready for main:                               NO
Ready for production:                         NO
Remediation branch safe to delete:            NO
```

### Accepted ratifications

| Item | Disposition |
|---|---|
| DSLD 75291 | `needs_info` → `fixed_mechanically after direct source verification` (§I.1) — product-specific evidence, not sibling inference |
| Omission-reason vocabulary | `duplicate_source_line` retained. Closed-contract **technical debt**, **not** a Phase-3 release blocker (§I.2) |

### Recorded technical debt (separate future migration)

Adding `subordinate_to_dosed_parent` / `constituent_without_independent_dose` requires its own
contract migration: enum update · contract-test update · downstream consumer review ·
enrichment replay · audit validation. **Do not fold into this remediation.**

### Do-not list until the evidence-owner SHA exists

Do **not** merge to `main` · do **not** publish · do **not** delete
`remediation/quarantine-clearing-20260919` · do **not** broaden the Phase-3 work.

### Next required artifact

A clean commit SHA (or ordered SHA set) from the **evidence owner** resolving/replacing
`V4_IQD_INGREDIENTS_FALLBACK` without weakening evidence applicability or changing scoring
semantics without review. See `.agents/HANDOFF_TO_EVIDENCE_OWNER_PHASE3_20260920.md`.

### Integrator's final combined task (after that SHA arrives)

1. integrate the evidence-owner SHA onto the validated Phase-3 state `095d27a1`;
2. inspect conflicts **semantically**, not textually;
3. run focused evidence / IQM / probiotic tests;
4. run the full fast tier;
5. re-run the same-input frozen 15,412-product A/B;
6. compare against `095d27a1`;
7. investigate every new score / conclusion / Safety / quarantine delta;
8. issue the final `READY_FOR_MAIN` / `NOT_READY_FOR_MAIN` determination.

---

## L. Baseline audit census at `095d27a1` (read-only, evidence collection)

Purpose: establish conclusively whether `V4_IQD_INGREDIENTS_FALLBACK` is the **only** current
static-audit finding the evidence-owner work is expected to eliminate — i.e. that "one failed test"
genuinely means "one underlying violation". **No code was modified.**

### Environment

Pristine **detached** worktree at exactly `095d27a1` (`/tmp/pg_census`, since removed):
`git status --porcelain` empty **including ignored**; no peer-session files; all three
peer-dirty files verified byte-clean. Same interpreter environment as the prior integration
verification.

### The machinery (why the user's concern was legitimate)

`scripts/audit_source_of_truth_contract.py:983`

```python
STATIC_FORBIDDEN_PATTERNS = [
    ("V4_IQD_INGREDIENTS_FALLBACK",  re.compile(r"iqd\.get\([\"']ingredients[\"']\)")),
    ("V4_RAW_ACTIVE_FALLBACK",       re.compile(r"product\.get\([\"'](?:activeIngredients|active_ingredients)[\"']\)")),
    ("V4_PRIMARY_CATEGORY_ROUTING",  re.compile(r"\.get\([\"']primary_category[\"']\)")),
]
```

The failing test asserts the **whole list is empty** (`assert audit_scoring_static(args) == []`,
`test_scoring_source_of_truth_audit.py:419`), so it *could* aggregate up to 3 distinct codes across
arbitrarily many lines. Verified directly rather than inferred.

### Raw findings (auditor invoked directly, not via the test)

```
RAW STATIC-AUDIT FINDING COUNT: 1
  [1] code    : V4_IQD_INGREDIENTS_FALLBACK
      message : scripts/scoring_v4/modules/generic_evidence.py:472 reads forbidden scoring fallback field
      path    : scripts/scoring_v4/modules/generic_evidence.py

distinct codes: ['V4_IQD_INGREDIENTS_FALLBACK']
```

Confirms the assertion aggregates a list of **length 1** — the user's aggregation concern is
checked and **refuted** for the live corpus. (The machinery *can* emit multiple codes: the sibling
test `test_static_audit_flags_direct_v4_iqd_fallback` feeds a synthetic module and gets both
`V4_IQD_INGREDIENTS_FALLBACK` and `V4_RAW_ACTIVE_FALLBACK`.)

### Independent corroboration

| Check | Result |
|---|---|
| Full module `test_scoring_source_of_truth_audit.py` | **1 failed, 22 passed** — only the static-audit test |
| CLI `audit_source_of_truth_contract.py scoring-static` | **1 finding**, `FAIL: 1 source-of-truth finding(s)` |
| CLI `... matrix` (artifact-free gate) | **OK: passed** |
| Adjacent enforcement / fallback-audit tests (11 modules: source-of-truth contract, scoring-contract-leak audit, d29 fallback audit, form-fallback ×2, v4 pillar gate, identity integrity, safety audit gates, taxonomy evidence, taxonomy determinism, release catalog) | **262 passed, 3 skipped, 0 failed** (skips are absent-artifact skips) |
| Direct inspection: the 3 forbidden patterns across all of `scripts/scoring_v4` | **exactly 1 hit** — `generic_evidence.py:472` |
| Exemption comments (`scoring-contract-legacy-compat` / `display/search`) in `scoring_v4` | **none** — the finding is not suppressed |
| CLI `... all` | 10 findings, of which **9 are artifact-absence codes** (`CLEANER_NO_INPUT`, `ENRICHMENT_NO_INPUT`, `SCORING_NO_INPUT`, `CLINICAL_NO_INPUT`, `EXPORT_MANIFEST_MISSING`, `EXPORT_DB_MISSING`, `INTERACTION_DB_MISSING`, `INTERACTION_MANIFEST_MISSING`, `FRESHNESS_DIST_MISSING`) expected in an artifact-free worktree, and **exactly 1** is a code violation |

### Fast tier at the census HEAD

`./scripts/test.sh fast` → **1 failed, 15,787 passed, 191 skipped** (272.61s)
Failing node: `scripts/tests/test_scoring_source_of_truth_audit.py::test_static_audit_current_v4_modules_have_no_forbidden_fallbacks`
Failure set: **`{static_audit}`** — identical to base `124982a0` and to the integration worktree.

### Base comparison (§7 — nothing unexpected appeared, so this is a confirmation)

At base `124982a0`: raw finding count **1**, same code, **same line 472**.
→ Classification: **`pre-existing at base`**, not introduced by Phase-3 integration.
The line number being unchanged confirms the remediation never touched that code path.

### Census conclusion

```
Clean detached HEAD:                       095d27a1
Fast-tier failures:                        1
Static-audit failing tests:                1
Raw static-audit findings:                 1
V4_IQD_INGREDIENTS_FALLBACK present:       YES
Any other static-audit finding present:    NO
Any additional evidence-owner blocker:     NO
```

> **CONFIRMED: `V4_IQD_INGREDIENTS_FALLBACK` is the sole known static-audit finding at the frozen
> integration baseline.**

This gives a clean causal chain for the later evidence-owner SHA: **1 audit violation in → 0 out**,
with fast-tier failures 1 → 0 and no new score/Safety/quarantine regression in the
15,412-product same-input A/B.

No files were modified, no allowlist or expected value was touched, and nothing was committed,
merged or pushed. The census worktree was removed and no stray worktrees remain.

---

## M. Combined-integration attempt: BLOCKED — no evidence-owner commit exists

Attempted 2026-09-20 ~02:40 EDT. Step 1 could not start: **the evidence-owner work was never
committed, and was still being actively edited at the time of this attempt.**

### Forensic findings (read-only)

| Check | Result |
|---|---|
| `git fetch --all` | no output — no new objects |
| `git ls-remote origin` | `HEAD` and `refs/heads/main` both `ad577f49`; only pre-existing `refs/pull/*` — **no new branch pushed** |
| `git for-each-ref` newest ref | `integration/phase3-remediation-20260920 -> 095d27a1` — nothing newer exists on **any** ref |
| `main` / `origin/main` | `ad577f49` (unchanged) |
| `git stash list` | empty |
| Peer's new files in **any** commit (reachable *or* dangling) | `test_cross_module_probiotic_evidence.py` = **0**, `test_digestive_enzymes_identity_repair.py` = **0**, `evidence_expansion_2026_09/partition_probiotics.py` = **0** |
| Other checkouts under `~/Downloads` | `Agentic-Orchestrator` (2026-05), `Pharma-main` (2025-06), `bbr-website` (2026-03) — all unrelated and long dormant |
| `INTEGRATION_REPORT_PHASE3_REMEDIATION.md` | **does not exist anywhere** |
| Dropped stashes (dangling) | two, both containing `scripts/data/ingredient_quality_map.json` only (552+/170−) — not the seam |

### The decisive finding: the tree is mutating in real time

```
now at check : 2026-09-20T02:42:33
scoring_v4/modules/generic_evidence.py   mtime 02:42:17   (16 s before the check)
scoring_input_contract.py                mtime 02:41:51   (42 s before the check)
studied_formulas.py                      mtime 02:34:46
```

Background: `scoring_input_contract.py` was **not** part of the previously inventoried peer dirty
set; it appeared during this session (dirty count 27 → **28**). At one instant it was caught
**mid-write and syntactically invalid** —
`scoring_input_contract.py:2982: (row: Dict[str, Any], index: int) -> str:` with the `def` prefix
not yet written — which made `test_scoring_source_of_truth_audit.py` and three other modules fail
to *collect*. Forty-two seconds later the file compiled again.

**Conclusion: the evidence owner is mid-edit and has produced no commit.**

### Consequences

1. There is **no SHA to integrate**; step 1 cannot begin.
2. Committing the dirty set on the owner's behalf is **unsafe and was rejected**: a live-editing
tree was empirically observed in a broken intermediate state, so any snapshot could capture a
non-compiling revision.
3. The §L measurement "raw findings in the peer working tree: 0" was taken ~02:1x against a tree
that has since changed. **It is stale and must be re-taken once the owner declares the work frozen.**
4. The brief's rule "Do NOT copy files from the dirty checkout" is vindicated empirically.

### State: nothing was mutated

No merge, no push, no branch or worktree deletion, no commit. `095d27a1` remains the frozen
integration state; the source branch `4bd49c0d` and its worktree are untouched.

**Blocker owner:** the evidence/scoring session. **Required artifact:** one or more coherent
commits, focused tests run, and the exact SHA — per
`.agents/HANDOFF_TO_EVIDENCE_OWNER_PHASE3_20260920.md`.
