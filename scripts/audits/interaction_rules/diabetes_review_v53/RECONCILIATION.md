# Diabetes Rule Review — Reconciliation Report

**Reviewer baseline**: `ingredient_interaction_rules_Reviewed.json` @ schema 5.2.0, 129 entries
**Live baseline**:     `ingredient_interaction_rules.json` @ schema 5.3.0, 145 entries
**Generated**: 2026-05-05
**Scope**: Phase 1 — content cleanup only. No schema changes. Diabetes condition only.

---

## Snapshot delta (5.2.0 → 5.3.0)

- **126** rules in both files (most reviewer comments still apply directly)
- **16** rules added since reviewer's snapshot (not analyzed — defer to a later review pass)
- **1** rule renamed/removed (`silymarin` in 5.2.0 → no exact match in 5.3.0)

### Added since reviewer (out of scope this phase)

| db | canonical_id |
|---|---|
| banned_recalled_ingredients | ADD_HORDENINE, BANNED_BITTER_ORANGE, BANNED_PENNYROYAL, BANNED_TANSY |
| harmful_additives | ADD_TYRAMINE_RICH_EXTRACT |
| botanical_ingredients | bupleurum_root, ginkgo_biloba_leaf, white_mulberry |
| ingredient_quality_map | bromelain, holy_basil, l_carnitine, l_tryptophan, maca, phenylethylamine, same, sodium |

---

## Reviewer worklist vs. live state

Status legend:
- **APPLY** — change is valid and not yet present in 5.3.0
- **DONE** — already implemented in 5.3.0 (no action needed)
- **DEFER-PHASE-2** — requires schema change (medication-aware escalation)
- **VERIFY** — already implemented but reviewer's source citation should be re-confirmed
- **N/A** — ingredient missing or out-of-scope

| # | Ingredient | Live state (diabetes) | Reviewer recommendation | Verdict | Phase 1 action |
|---|---|---|---|---|---|
| 1 | aloe_vera | monitor / **theoretical** | upgrade evidence to `limited` (oral aloe has human glucose/HbA1c data) | **APPLY** | Edit evidence_level: theoretical → limited; add note distinguishing oral vs topical |
| 2 | alpha_lipoic_acid | caution / probable + dose_threshold | mild softening of severity in low-risk users | **DEFER-PHASE-2** | Needs medication-class gating; defer |
| 3 | berberine_supplement | avoid / established + **dose threshold** (≥1500mg→avoid, <1500→caution) + drug-class threshold for hypoglycemics | "caution by default, avoid only with insulin/sulfonylurea" | **DONE** (effectively) | Already dose-gated and drug-class-gated. Mechanism text could drop "comparable to metformin" if present — VERIFY current copy |
| 4 | bitter_melon | caution / probable | soften "plant insulin analog" copy in mechanism | **APPLY** | Mechanism rewrite (remove insulin-replacement framing) |
| 5 | black_seed_oil | caution / probable | possibly downgrade unless dose/extract standardized | **DEFER-PHASE-2** | Needs dose gate; not in current threshold set |
| 6 | chromium | monitor / probable | keep severity; reviewer suggests `limited`-style evidence | **APPLY (low-priority)** | Optional: tighten mechanism wording; severity stays |
| 7 | cinnamon | monitor / probable | acknowledge mixed evidence in mechanism text | **APPLY** | Mechanism rewrite to acknowledge conflicting trials (per NCCIH) |
| 8 | fenugreek | caution / probable | improve headline | **APPLY** | Headline: "Caution with diabetes" → "May lower blood sugar — monitor if using diabetes medication" |
| 9 | fiber | monitor / probable | add medication-timing note | **APPLY** | Add `informational_note` about 2-hour separation from oral meds |
| 10 | garlic | caution / probable + dose_threshold | downgrade to monitor for glucose alone | **APPLY** | Severity: caution → monitor (glucose alone); the bleeding/anticoagulant rules stay |
| 11 | ginseng | monitor / probable | keep | **DONE** | None |
| 12 | gymnema_sylvestre | caution / probable | **REMOVE "beta-cell regeneration" claim** (urgent) | **APPLY (urgent)** | Mechanism rewrite per reviewer's draft text |
| 13 | inositol | informational / probable | keep | **DONE** | None |
| 14 | l_carnitine | informational / probable | keep | **DONE** | None |
| 15 | magnesium | monitor / **established** | downgrade evidence (interaction NOT established) | **APPLY (urgent)** | evidence_level: established → probable |
| 16 | olive_leaf | caution / probable + dose_threshold | dose/extract gate | **DONE** (dose-gated) | None — verify dose threshold copy |
| 17 | psyllium | monitor / established | add medication-timing note | **APPLY** | Add `informational_note` about oral-med spacing |
| 18 | stinging_nettle | caution / probable | downgrade unless strong extract/dose | **DEFER-PHASE-2** | Needs extract/dose gate |
| 19 | tribulus | monitor / probable | downgrade evidence to `limited` | **APPLY** | evidence_level: probable → limited |
| 20 | vanadyl_sulfate | caution / probable + dose_threshold | keep + add toxicity warning | **APPLY (low)** | Add safety note about heavy-metal/toxicity to `informational_note` |
| 21 | vitamin_b3_niacin | caution / established + **dose threshold** (>1000mg→avoid, ≤1000→monitor) | dose-gate (already done) | **DONE** | Already dose-gated; verify multivitamin doses don't trip |
| 22 | vitamin_d | monitor / probable | downgrade to informational unless deficient | **DEFER-PHASE-2** | Engine has no deficiency state; severity stays `monitor` until user-profile layer carries lab status |
| 23 | white_mulberry | caution / established + dose_threshold | scope to leaf extract / DNJ-standardized | **DEFER-PHASE-2** | Needs form-scoped variant; touches form_scope architecture |

### Headline copy refresh (cross-cutting)

Reviewer flagged generic "Caution with diabetes" headlines as noisy. Phase 1 rewrites the diabetes `alert_headline` for these rules to condition-specific phrasing (within the 20–60 char limit):

| Pattern | New headline |
|---|---|
| Glucose-lowering herb | "May lower blood sugar" |
| Post-meal glucose ingredient | "May reduce glucose after meals" |
| High-dose niacin | "High-dose niacin may raise blood sugar" |
| Fiber/psyllium | "May change med timing and post-meal glucose" |
| Weak evidence | "May affect glucose trends in some people" |

---

## Phase 1 worklist (10 APPLY items)

Atomic, no schema change, all reversible:

1. **gymnema_sylvestre** — rewrite diabetes mechanism (remove "beta-cell regeneration") **[urgent]**
2. **magnesium** — diabetes evidence_level: `established` → `probable` **[urgent]**
3. **aloe_vera** — diabetes evidence_level: `theoretical` → `limited`; add oral-vs-topical note
4. **bitter_melon** — diabetes mechanism rewrite (drop insulin-analog framing)
5. **cinnamon** — diabetes mechanism rewrite (acknowledge mixed evidence)
6. **fiber** — add `informational_note` about 2-hour med spacing
7. **psyllium** — add `informational_note` about med spacing
8. **garlic** — diabetes severity: `caution` → `monitor` (glucose-only; bleeding rules unchanged)
9. **tribulus** — diabetes evidence_level: `probable` → `limited`
10. **fenugreek** — diabetes alert_headline rewrite

Plus headline-only refreshes for: chromium, vanadyl_sulfate (safety note add), berberine (drop "comparable to metformin" if present).

## Phase 2 backlog (7 items, schema change required)

- alpha_lipoic_acid, black_seed_oil, stinging_nettle, vitamin_d, white_mulberry — need medication-class or form-scoped gating
- vitamin_d — needs user-profile deficiency state
- Architectural: `severity_escalation[]` field driven by `drug_class_id` / `condition_id` / `user_history`

## Already done in 5.3.0 (5 items)

berberine_supplement, ginseng, inositol, l_carnitine, olive_leaf, vitamin_b3_niacin (6 actually) — verify URL citations during step 3.

---

## Source verification queue (step 3)

URLs cited by reviewer that must be content-verified before we ship Phase 1 edits:

- NCCIH: aloe-vera, ginger, asian-ginseng, providers/digest/type-2-diabetes-and-dietary-supplements
- NIH ODS: Chromium, Magnesium fact sheets
- PubMed: 18380993 (niacin), 24438170 (fenugreek), 34467577 (gymnema)
- PMC: PMC5839379 (berberine/metformin), PMC9709280 (berberine), PMC5321430 (mulberry)
- LiverTox NBK590483 (bitter melon)

Run `scripts/api_audit/verify_pubmed_references.py` on the PMIDs and confirm fact sheet URLs resolve before any commit.

---

## Recommended commit cadence

- One commit per APPLY item (10 commits) — never batch.
- Each commit message includes: ingredient, fields changed, primary source URL.
- Run after every commit:
  ```
  python3 -m pytest scripts/tests/ -k interaction -q
  python3 scripts/validate_safety_copy.py
  python3 scripts/tools/split_rules_by_condition.py  # refresh views
  ```
- After all 10: bump `_metadata.schema_version` → `5.3.1`, update `last_updated`, push as one PR.
