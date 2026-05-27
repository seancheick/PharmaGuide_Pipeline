# Wave 9.B.2 — Schema design: `display_layer` / background / deprecated routing for curated interactions

**Status:** Design-only proposal. **No data edits. No code changes. No test changes.** This document is the basis for a follow-up implementation batch (9.B.3) after clinician + Flutter sign-off.

**Generated:** 2026-05-27.

**Authority:** Wave 9.B classification report ([MINOR_ENTRY_CLASSIFICATION.md](MINOR_ENTRY_CLASSIFICATION.md), commit `6322fc8b`) established the two-lane policy: user-facing alert vs background insight, with a remove/deprecate path for entries that don't carry meaningful clinical signal. This doc proposes the concrete schema + pipeline changes to make those lanes real without breaking the existing alert contract.

---

## 1. Problem statement

The current schema treats every entry in `scripts/data/curated_interactions/*.json` as a candidate user-facing alert, distinguished only by `severity`. Wave 8 (`batch_critical_2026_05.json`) added a quality bar that **excludes `Minor` and `Monitor`** severities — but that bar is local to that one shard. The legacy `curated_interactions_v1.json` still carries **25 `Minor`-severity entries** which surface in the same alert layer as the high-severity ones, contributing the "PPI ↔ Vitamin C" noise pattern the clinician's two-lane framework was built to eliminate.

**Three classes of non-alert entries are emerging:**

| Class | Examples (from 9.B classification) | What it should do in the app |
|---|---|---|
| **Background insight** | `DSI_STATINS_COQ10` (CoQ10 as SAMS mitigation), `DSI_CORTICO_CALCIUM_VITD` (standard prophylaxis, not warning), `DSI_DM_MAGNESIUM` (beneficial co-admin in T2DM) | Visible in a "health insights" / "profile" view; never interruptive |
| **Deprecated** | `DSI_SSRI_FISHOIL` (entry's own text says "no significant adverse interaction is known"); future retractions | Hidden from app; retained as audit record |
| **Alert** (current default) | `DSI_STATINS_RYR`, `DSI_LEVOTHYROXINE_COFFEE`, the Wave 8 critical set | Interruptive alert on product scan |

The schema needs to encode these three lanes without breaking the existing contract or duplicating data across multiple files.

---

## 2. Existing infrastructure to reuse (don't reinvent)

Before adding new fields, audit what's already there. The current `interaction_db.sqlite` `interactions` table (per `scripts/build_interaction_db.py:281`) already has:

| Existing field | Purpose | Reuse?  |
|---|---|---|
| `severity` | Major / Moderate / Minor / Monitor / Contraindicated | Already lane-correlated. The Wave 8 shard's "no Minor" bar is policy applied to severity. |
| `retired_at` (TEXT, nullable) | ISO timestamp when entry was retired | **Yes — this is the deprecation primitive.** Don't invent `deprecated_at`. |
| `retired_reason` (TEXT, nullable) | Free-text reason for retirement | **Yes — reuse for deprecation rationale.** |
| `alert_style` (TEXT, nullable) | `NULL` (default = clinical pairwise alert) or `"food_advisory_note"` (soft UI card) | **Adjacent concern (rendering style)**, not lane membership. Keep distinct. |
| `bidirectional`, `dose_dependent`, `dose_threshold_text` | Other axes of the same entry | Unrelated to lane decision. |

**Conclusion:** the schema already has a deprecation primitive (`retired_at` + `retired_reason`). The gap is the **background lane** — entries that are live and clinically valid but should not interrupt. That's the new field this doc proposes.

---

## 3. Three options compared

### Option A — `display_layer` field on each entry (clinician's lean)

Add a single new optional field on each curated interaction entry:

```json
{
  "id": "DSI_STATINS_COQ10",
  "...": "...",
  "severity": "Minor",
  "display_layer": "background",
  "background_rationale": "CoQ10 is studied as mitigation for statin-associated muscle symptoms, not an adverse interaction. Belongs in profile-informed insights, not user-facing alerts.",
  "...": "..."
}
```

**Pros:**
- One source of truth — all interaction data stays in `curated_interactions/*.json`.
- Cleanly filterable: app queries `WHERE display_layer = 'alert' AND retired_at IS NULL`.
- Migration is field-additive, backward compatible (absent = "alert").
- Lane decision is per-entry; clinician can move one entry at a time without file surgery.
- `display_layer` slots cleanly next to existing `alert_style` (lane = "is this an alert at all"; style = "how is it rendered if it is").

**Cons:**
- Three states (`alert` / `background` / `deprecated`) overlap with existing `retired_at` for deprecation.
- A new field in the SQLite schema means one more index + nullable column.

### Option B — Separate shards per lane

Move background entries to a new file `scripts/data/curated_interactions/background_insights_v1.json`; deprecated entries to `scripts/data/curated_interactions/deprecated_interactions_v1.json`. Each shard has its own `_metadata.purpose` declaring its lane.

**Pros:**
- File path itself communicates lane membership.
- No new column in the curated-interaction schema or in `interactions` SQLite table.
- Wave 8's per-shard test pattern already exists (`test_wave8_critical_interactions.py` locks `batch_critical_2026_05.json`).

**Cons:**
- Demoting an entry requires moving it between files — high-friction edit, easy to drop fields in transit.
- Three shards' worth of `_metadata.total_entries` to keep in sync.
- `build_interaction_db.py` already globs all `*.json`, so the SQLite layer still needs SOME signal to distinguish lane — i.e. it ends up needing the field anyway, just inferred from filename. That's fragile.
- Audit gates (e.g., `audit_source_of_truth_contract.py interaction`) currently look at the unified DB; per-shard policy becomes a parallel validation surface.

### Option C — Hybrid: `display_layer` field, reuse existing `retired_at` for deprecation

Add `display_layer` field with only two values: `"alert"` (default) and `"background"`. **Deprecation continues to use the existing `retired_at` + `retired_reason` columns**, which the schema already supports.

**Pros:**
- Minimal schema delta: ONE new field, not two states reinventing what `retired_at` already does.
- Backward compatible: absent `display_layer` ⇒ alert.
- Deprecation pathway already wired (build pipeline + Supabase already know about `retired_at`).
- App contract: `is_active_alert = display_layer == 'alert' AND retired_at IS NULL`.

**Cons:**
- Slightly less symmetric than Option A's three-value enum. A reader has to know that "deprecated" lives in a different field.
- Naming: `display_layer = "background"` plus `retired_at IS NOT NULL` together describe "this WAS background, then got retracted" — the combination is meaningful but has a learning curve.

---

## 4. Recommendation: **Option C** (hybrid)

Option C is the smallest delta to a working schema. It reuses the existing deprecation primitive (`retired_at`) rather than duplicating it, and adds one well-scoped field (`display_layer`) for the new axis (alert vs background).

Concrete spec follows in §5.

If during implementation we hit a case where deprecation reason needs more structure than free-text `retired_reason` (e.g., enum: `evidence_retracted` / `superseded_by_better_entry` / `no_actionable_signal`), that's a small follow-up. Out of scope here.

---

## 5. Field specification

### 5.1 New field on each curated interaction entry

```yaml
display_layer:
  type: string
  enum: [alert, background]
  default: alert              # absent ⇒ alert (backward compat)
  required: false             # field is OPTIONAL in the curated-interactions schema
  description: >
    Which app surface this entry should appear on. "alert" entries fire
    as interruptive warnings on product scan when the user's medication
    profile matches. "background" entries are surfaced in a non-
    interruptive "health insights" view and never interrupt.

    Deprecated entries (no longer live) use the existing `retired_at`
    field; do not set display_layer = "deprecated".
```

### 5.2 New optional field for B-lane entries

```yaml
background_rationale:
  type: string
  required: false             # required iff display_layer == "background"
  description: >
    One-sentence clinical explanation of why this entry is in the
    background lane. Encodes the lane decision so a future reviewer
    can audit without re-reading the full mechanism/management text.

    Examples:
      "CoQ10 is studied as mitigation for SAMS, not an adverse interaction."
      "Standard prophylaxis for glucocorticoid-induced osteoporosis."
      "Beneficial co-admin in T2DM; framing as 'interaction' is inaccurate."
```

### 5.3 Severity ↔ lane invariant

Add as a verified-on-build invariant (not a schema-required field):

| `display_layer` | Allowed `severity` values | Rationale |
|---|---|---|
| `alert` (default) | Major, Moderate, Contraindicated | Minor must not surface as alert. The Wave 8 quality bar generalized. |
| `background` | Minor, Monitor | Background entries are explicitly the low-severity / educational layer. |

This means once `display_layer` exists, **Minor entries must declare `display_layer: "background"` explicitly** OR be deprecated (`retired_at` set). The verify pipeline catches the policy contradiction.

### 5.4 Deprecation continues to use existing fields

```yaml
retired_at: "<ISO timestamp>"     # already in schema
retired_reason: "<free text>"     # already in schema
```

No new fields for the deprecated state. The combination `retired_at IS NOT NULL` means "do not serve to users; keep as audit record."

---

## 6. Migration plan

Five phases. Each phase is a separate atomic commit per the Wave 6.Y discipline. **No phase touches a clinical entry's mechanism/management text** — those are clinician-authored content and are out of scope.

### Phase 1 — Schema + verifier (no data edits) **[~Batch 9.B.3]**

1. Extend the curated-interaction JSON Schema (if one exists at `scripts/contracts/...`) or document the field in `scripts/INTERACTION_RULE_AUTHORING_SOP.md` if no machine-readable schema is published.
2. Add `verify_interactions.py` checks:
   - **Check 12 — display_layer enum:** if present, must be `"alert"` or `"background"`. Reject anything else.
   - **Check 13 — severity-lane invariant:** if `display_layer == "alert"` (or absent), severity must be `Major | Moderate | Contraindicated`. If `display_layer == "background"`, severity must be `Minor | Monitor`. If `retired_at` is set, no severity-lane check (any value allowed; entry is not user-facing).
   - **Check 14 — background entries must carry rationale:** if `display_layer == "background"`, `background_rationale` must be non-empty.
3. Add unit tests for the three new checks.
4. **No data file changes.** The new invariant doesn't fire because no entry has `display_layer` set yet, and the legacy 25 Minor entries don't yet have `display_layer: "alert"` declared explicitly — they pass via the "absent ⇒ alert" backward-compat rule, BUT Check 13 will flag them as policy violations (severity=Minor in alert lane). Phase 1 deliberately leaves that flag *visible* in the report so Phase 2 can address it.

> **Decision needed from clinician at Phase 1:** does Check 13 fire as `error` (build blocks) or `warning` (build proceeds, report surfaces)? My recommendation: `warning` for one release cycle, then promote to `error` once the 25 Minor entries are classified.

### Phase 2 — Build pipeline + SQLite + Supabase

1. Add two new columns to the `interactions` SQLite table:
   ```sql
   display_layer        TEXT NOT NULL DEFAULT 'alert',
   background_rationale TEXT
   ```
2. Add a partial index for fast alert-filter:
   ```sql
   CREATE INDEX idx_int_display_layer
     ON interactions(display_layer, retired_at)
     WHERE retired_at IS NULL;
   ```
3. Bump `interaction_db_version` in `interaction_db_metadata` (e.g., `1.0.0` → `1.1.0`).
4. `release_interaction_artifact.py` — already stages the SQLite to dist; ensure the new columns ride along.
5. Supabase export: add a migration to the published interaction table (`ALTER TABLE ... ADD COLUMN display_layer TEXT NOT NULL DEFAULT 'alert'; ADD COLUMN background_rationale TEXT;`). Existing rows backfill via the default; no row-by-row migration needed.
6. Audit gate (`audit_source_of_truth_contract.py interaction`): document the new columns in the contract; assert they exist post-build.

> **Decision needed for clinician + app team:** Supabase schema migration timing — when can the column add land in the production Supabase project? My recommendation: lands with the Phase 2 commit; app reads the column tolerantly (treats absent as `'alert'`) until Phase 4.

### Phase 3 — Backfill explicit `display_layer: "alert"` on the 123 entries that currently pass via the backward-compat default

Mechanical edit, zero clinical content change:
- For every entry in `curated_interactions/*.json` where `severity ∈ {Major, Moderate, Contraindicated}` and `retired_at` is unset, set `display_layer: "alert"` explicitly.
- Test: assert all "live alert" entries have `display_layer: "alert"` explicitly declared post-Phase-3.
- Atomic commit.

After Phase 3: the *absence* of `display_layer` means "this entry was missed by Phase 3 and needs review" — a strong signal for the lane-policy verifier to flag.

### Phase 4 — Flutter contract update

App-side work:
1. The current alert query (whatever it is — likely something like `SELECT * FROM interactions WHERE ... matches profile`) filters by `display_layer = 'alert' AND retired_at IS NULL`.
2. A new query path for the "health insights" view (background lane): `SELECT * FROM interactions WHERE display_layer = 'background' AND retired_at IS NULL`.
3. Deprecated entries (`retired_at IS NOT NULL`) are never queried by the user-facing app; they remain in the DB as audit record for clinical review.
4. Backward-compat: the app must tolerate rows where `display_layer` is `NULL` (treat as `'alert'`) for the brief window between Phase 2 and Phase 3.

> **Decision needed for app team:** is there a "background insights" / "profile guidance" screen already? If not, this design unlocks it — but creating the screen is a product/design decision, not a data decision. The schema is forward-compatible regardless of whether the screen exists; background entries simply lie dormant in the DB until the screen ships.

### Phase 5 — Per-entry classification commits (Batch 9.B.4+)

Per the Wave 9.B classification report, the 25 Minor entries each get a per-entry commit:
- Lane B entries: set `display_layer: "background"` + add `background_rationale`. Keep `severity: "Minor"`. Atomic commit per entry (one CSV row at a time, mirroring Wave 6.Y discipline).
- Lane C entries: set `retired_at` + `retired_reason`. Leave `display_layer` unset (irrelevant once retired).
- Lane D entries: hold until evidence research completes, then either promote to alert (severity upgrade + remain alert lane) or set to background.

Each commit:
1. Write failing regression test asserting the new lane state.
2. Apply the edit.
3. Run `verify_interactions.py --check-pubmed`.
4. Run `rebuild_interaction_db.sh --offline`.
5. Run `audit_source_of_truth_contract.py interaction`.
6. Atomic commit.

---

## 7. Verifier / audit changes summary

| Hook | Change | Phase |
|---|---|---|
| `verify_interactions.py` Check 12 | Reject `display_layer` outside `{alert, background}` | 1 |
| `verify_interactions.py` Check 13 | Severity-lane invariant (Major+ ↔ alert, Minor/Monitor ↔ background) | 1 (warning) → 3 (error) |
| `verify_interactions.py` Check 14 | `display_layer="background"` requires non-empty `background_rationale` | 1 |
| `build_interaction_db.py` schema | Add `display_layer`, `background_rationale` columns + index | 2 |
| `audit_source_of_truth_contract.py interaction` | Assert new columns exist + count by lane | 2 |
| `release_interaction_artifact.py` | Bump version, stage new schema | 2 |
| Supabase migration | `ALTER TABLE` for the published interaction table | 2 |
| Wave 8 test (`test_wave8_critical_interactions.py`) | Optional: assert critical batch entries have `display_layer = "alert"` (or absent) | 3 |

---

## 8. Backward compatibility contract

| Reader | Behavior before migration | After migration | Compatibility guarantee |
|---|---|---|---|
| `verify_interactions.py` | No `display_layer` field | Optional field; absent ⇒ alert | Tolerant — same as today |
| `build_interaction_db.py` | SQLite has columns up through `practical_guidance` | Adds 2 more nullable columns | Tolerant — old reader queries that don't `SELECT *` keep working |
| `audit_source_of_truth_contract.py` | Reads the SQLite directly | Reads new columns | Tolerant — fail loud only on missing columns post-Phase-2 |
| Flutter app (current) | Treats all entries as alerts | Should filter by `display_layer = 'alert'` after Phase 4 | **Must tolerate `display_layer = NULL` as `'alert'`** during the Phase 2 → Phase 3 window |
| Supabase consumers | Existing columns | New columns nullable | Tolerant — existing select queries unaffected |

**Key guarantee:** no entry's current behavior changes until its `display_layer` is explicitly set. Phase 3 is a no-op for users (every alert that was alerting yesterday alerts today; just the column is now explicitly written rather than defaulted). The only behavior change happens entry-by-entry in Phase 5 when a specific Minor entry is moved to background or retired.

---

## 9. Examples (three concrete entries the clinician named)

### 9.1 `DSI_SSRI_FISHOIL` — Lane C (deprecate)

**Current state (excerpt):**
```json
{
  "id": "DSI_SSRI_FISHOIL",
  "severity": "Minor",
  "interaction_effect_type": "Neutral",
  "mechanism": "Omega-3 fatty acids are studied as adjunctive therapy for depression and have no pharmacokinetic interaction with SSRIs. No significant adverse interaction is known. EPA-rich formulations may even have...",
  "management": "Fish oil is generally compatible with SSRIs...",
  "source_pmids": []
}
```

**Proposed state under this design (Phase 5):**
```json
{
  "id": "DSI_SSRI_FISHOIL",
  "severity": "Minor",
  "...": "...",
  "retired_at": "2026-05-XXTHH:MM:SSZ",
  "retired_reason": "Entry's own mechanism text states 'no significant adverse interaction is known' — does not meet the threshold for a curated interaction. Generic high-dose omega-3 antiplatelet effect is covered by anticoagulant/antiplatelet entries; SSRI framing adds noise without clinical signal. Wave 9.B classification, 2026-05-27."
}
```

Note: `display_layer` is **not set** for retired entries. The combination `retired_at IS NOT NULL` is the deprecation signal.

### 9.2 `DSI_STATINS_COQ10` — Lane B (background)

**Current state (excerpt):**
```json
{
  "id": "DSI_STATINS_COQ10",
  "severity": "Minor",
  "interaction_effect_type": "Neutral",
  "mechanism": "Statins inhibit HMG-CoA reductase, which also reduces endogenous CoQ10 synthesis. Some patients experience statin-associated muscle symptoms (SAMS). CoQ10 supplementation is studied as mitigation...",
  "management": "CoQ10 (100-200 mg/day) is widely used to offset statin-related muscle symptoms..."
}
```

**Proposed state (Phase 5):**
```json
{
  "id": "DSI_STATINS_COQ10",
  "severity": "Minor",
  "...": "...",
  "display_layer": "background",
  "background_rationale": "CoQ10 is studied as MITIGATION for statin-associated muscle symptoms (SAMS), not an adverse interaction. Surfacing as an alert would invert the clinical signal — patients reading 'interaction warning' would draw the wrong conclusion. Belongs in profile-informed insights."
}
```

### 9.3 `DSI_CORTICO_CALCIUM_VITD` — Lane B (background, beneficial nutrient pair)

**Current state (excerpt):**
```json
{
  "id": "DSI_CORTICO_CALCIUM_VITD",
  "severity": "Minor",
  "interaction_effect_type": "Neutral",
  "mechanism": "Long-term corticosteroid use reduces calcium absorption and increases urinary calcium excretion, leading to bone loss. Calcium and vitamin D supplementation is recommended as a preventive measure...",
  "management": "Supplementation with calcium (1000-1200 mg/day) and vitamin D (800-1000 IU/day) is standard practice for patients on long-term corticosteroids."
}
```

**Proposed state (Phase 5):**
```json
{
  "id": "DSI_CORTICO_CALCIUM_VITD",
  "severity": "Minor",
  "...": "...",
  "display_layer": "background",
  "background_rationale": "Calcium + vitamin D supplementation is STANDARD PROPHYLAXIS for glucocorticoid-induced osteoporosis (ACR / IOF guidelines), not an adverse interaction. This is recommended care, not a warning. Background insight only — the alert layer would misframe the clinical guidance."
}
```

---

## 10. What's NOT in this design

- **The 24 individual demotion/promotion decisions for the remaining Minor entries.** Each is a clinical decision per Wave 9.B classification report; the schema unlocks them but doesn't decide them.
- **Flutter UI for the background insights screen.** That's a product/design decision. The schema is forward-compatible whether the screen exists or not.
- **Telemetry on which alerts fire / which background entries get viewed.** Separate concern.
- **Retroactive renaming of legacy `Minor`-severity entries.** Severity values stay; only `display_layer` and `retired_at` change.
- **Modifying any entry's mechanism/management text.** Clinician-authored content, untouched.
- **Changing the Wave 8 `batch_critical_2026_05.json` test policy.** Wave 8's "Major/Moderate only" lock stands; this design generalizes the same idea to the legacy shard.

---

## 11. Open questions for clinician + app team

1. **Check 13 enforcement level (Phase 1):** `warning` for one cycle then promote to `error`, or `error` immediately? My recommendation: warning first (the 25 Minor legacy entries will fire it; processing them is Batch 9.B.4+ work).

2. **Supabase migration window (Phase 2):** is there a release calendar / freeze period I should align with? Or land with the Phase 2 commit and let the column propagate?

3. **Background-insights surface (Phase 4):** does the Flutter app already have a "profile health insights" / "supplement-medication considerations" view, or does this design require building it? If the latter, background entries lie dormant in the DB until the view ships — that's a feature delay, not a data delay.

4. **Retired-entry retention:** indefinitely keep retired entries in the SQLite DB for clinical-audit record, OR purge after N years? My recommendation: keep indefinitely; the retirement timestamp itself is the historical record.

5. **`display_layer` default policy after Phase 3:** Once Phase 3 explicitly tags all live alert entries, should the schema make `display_layer` **required** (no implicit default)? My recommendation: yes, after Phase 3 lands — explicitness everywhere, the implicit "absent ⇒ alert" rule becomes a footgun for new authors.

6. **Severity vs lane separation is now explicit:** does the clinician want to preserve `Minor` as a meaningful severity value at all, or collapse all Minor entries into either `background` (Lane B) or `retired` (Lane C)? Open philosophical question — the Wave 8 batch effectively already chose "no Minor in production"; this design lets `Minor` live on, just routed away from alerts.

---

## 12. Implementation order (recap)

```
Phase 1  (Batch 9.B.3 — schema + verifier, no data edits)        [next, on approval]
Phase 2  (Batch 9.B.4 — SQLite columns + Supabase + audit)       [after Phase 1 approval]
Phase 3  (Batch 9.B.5 — backfill display_layer:"alert" on 123)   [mechanical bulk, atomic commit]
Phase 4  (Batch 9.B.6 — Flutter contract update)                 [app team]
Phase 5  (Batches 9.B.7+ — per-entry classification, one at a time per Wave 6.Y discipline)
```

Each phase ships behind the same gates that landed Batches 1–9.B.1: failing-test-first, verify_interactions, rebuild_interaction_db, audit_source_of_truth_contract, atomic commit.

This is the smallest delta that unlocks the two-lane policy without breaking the existing contract. Awaiting clinician + Flutter team sign-off before Phase 1.
