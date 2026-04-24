# Flutter Handoff — E1 Release (Canonical, Implementation-Ready)

**Pipeline release live:** `v2026.04.23.000925`
**Doc rewrite:** 2026-04-23 (dedup pass — replaced 3 conflicting priority lists with one; added all tickets accumulated mid-sprint)
**Release D addendum:** 2026-04-24 — goal-matching contract v6.0.0 + cluster-ingredient alias map + single-ingredient override + enrichment hardening + product-name fallback synthesizer (**E1.16–E1.23** SHIPPED, FLTR-21/22/23 OPEN, awaiting full pipeline rebuild). E1.21–E1.23 are post-rebuild bugfixes discovered from the first 8,169-product dashboard snapshot: score-formula MAX-of-required-weights, synthesizer name-read fallback, and absorption-enhancer sub-threshold demotion.

**From:** Pipeline / scoring / data-contract side
**To:** Flutter app team
**Purpose:** Implement post-E1 UI correctness, safety rendering, profile filtering, and product-detail hierarchy without ambiguity.

**Status legend:**
- `[x]` shipped and simulator-verified
- `[-]` in progress
- `[ ]` not started
- `[~]` deferred / Release C
- `[P]` pipeline follow-up (not Flutter)

---

# 0. Executive Summary

The backend is now deterministic, clinically safer, and structured. The frontend must:

1. **Respect safety priority above all**
2. **Render correct fields (no inference)**
3. **Filter warnings based on profile**
4. **Avoid duplication and noise**
5. **Prevent unsafe actions (stack, interpretation, etc.)**

---

# 1. GLOBAL RULES (NON-NEGOTIABLE)

## 1.1 BLOCKED MODE OVERRIDE (highest priority)

Before rendering ANY product UI:

```dart
if (product.verdict == 'BLOCKED') {
  renderBlockedScreen(product);
  return;
}
```

When BLOCKED:

* ❌ No score
* ❌ No ingredients
* ❌ No warnings list
* ❌ No stack interaction
* ❌ No formulation analysis
* ❌ No "safe" messaging

Only render the **Blocked Screen**.

**Distinction:** `UNSAFE` verdict does NOT take this override. UNSAFE still renders the full detail screen so users see context and alerts.

## 1.2 SAFETY PRIORITY HIERARCHY

Rendering follows this strict order:

1. BLOCKED
2. BANNED / CONTRAINDICATED
3. UL EXCEEDED
4. MAJOR INTERACTIONS
5. MODERATE INTERACTIONS
6. DOSE QUALITY (well_dosed, low_dose)
7. QUALITY SIGNALS

Higher priority ALWAYS overrides lower.

**Examples:**
* Vitamin A 25,000 IU → ❌ NOT "well dosed" → ✅ UL alert (or "Dose not evaluated" if pipeline sets skip_ul_check)
* Blocked product → ignore ALL other signals

## 1.3 PIPELINE IS THE SOURCE OF TRUTH

The UI must interpret the pipeline — it does NOT reinterpret it. When the pipeline sets `skip_ul_check=true`, `display_mode_default='suppress'`, etc., the UI respects that decision verbatim. Only exception: a **temporary Flutter dose guardrail** is allowed (§5.11) to downgrade high-severity warnings on low-dose ingredients until the pipeline fix lands.

---

# 2. NON-NEGOTIABLE RENDERING RULES

## 2.1 Never render raw ingredient `name` when `display_label` exists

```dart
final title = ingredient.displayLabel?.trim().isNotEmpty == true
    ? ingredient.displayLabel!
    : ingredient.name;
```

**Why:** `name` is canonical / internal. `display_label` is what the user should see.

**Example:** `name: "Vitamin A"`, `display_label: "Vitamin A Palmitate"` → render "Vitamin A Palmitate".

## 2.2 Never infer dose in Flutter

Use only `display_dose_label`. Do not reconstruct from quantity/unit if the pipeline provided a display string.

If `display_dose_label == "Amount not disclosed"`, the UI must not imply adequacy.

## 2.3 Never show profile-gated warnings unless the profile matches

Warnings with `display_mode_default: "suppress"` must be filtered against user profile. This is critical.

## 2.4 Never style `product_status` as safety

`product_status` is:

* not an alert
* not a safe chip
* not a warning
* not part of score math
* not a verdict modifier

It belongs in a neutral **Concerns** layer (not the Alerts layer).

## 2.5 Never flatten safety severity into one chip style

A banned-substance alert and an anti-caking excipient must not look visually equivalent.

## 2.6 Never claim "Safe to add" on a BLOCKED/UNSAFE product

Three defensive layers (§5.16):
- UI guard in PGStackActionButtons._handleAdd short-circuits before the sheet
- Domain guard in StackActions.addProduct throws StackAddBlockedException
- Sheet-level guard swaps the success banner for a hard-block banner if the sheet is ever reached directly

## 2.7 Never promote generic precautions to "applies to you"

Split warnings into two buckets (FLTR-18):
- **Applies to you**: ONLY profile-matched items
- **Other precautions**: everything else, collapsed by default

A non-kidney user must never see a kidney-disease warning presented as a personal alert.

---

# 3. PRODUCT DETAIL ARCHITECTURE (target)

The target page structure (FLTR-3 final state). Current implementation sits between today's layout and this target.

```
Header              → name, brand, score, verdict, grade
Decision strip      → score summary + one-line verdict
Why this score      → positive drivers only
Tradeoffs           → neutral caveats (proprietary blend, filler load, limited dose disclosure)
Applies to you      → profile-matched warnings ONLY (FLTR-18)
Other precautions   → non-profile precautions, collapsed (FLTR-18)
Alerts              → UL exceeded, banned/recalled, contraindications, major interactions
Concerns            → product_status chip (discontinued), additive concerns, added sugar
Active Ingredients  → name (incl. form), dose, dose-safety badge, form quality (FLTR-20)
Other Ingredients   → inactives, collapsed by default
Deep dive           → evidence, ingredient rationale, citations
```

---

# 4. TICKET BOARD

## 4.1 RELEASE A — Safety overrides (SHIPPED)

### FLTR-10 — BLOCKED MODE override `[x]`
BLOCKED verdict early-returns to `BlockedProductView`. No score/ingredients/stack-action surface. UNSAFE stays on full detail.

Commits: `2f857a5` base override, `b66ac8f` blob enrichment (substance_name + safety_warning_one_liner + safety_warning), `5fda6c6` FDA reference link.

### FLTR-11 — Dose-vs-UL badge override `[x]`
Per-ingredient `_SafetyTag` respects `rda_ul_data.analyzed_ingredients[].skip_ul_check`. Three states: `exceedsUl` ("High dose"), `skip` ("Dose not evaluated"), `withinLimits` (bioScore tiers).

Commits: `2f9176f` v1 (superseded), `77410a2` schema fix (rda_ul_data + skip_ul_check).

### FLTR-16 — Stack safety gate `[x]`
Three defensive layers blocking unsafe add: UI guard in `_handleAdd`, domain guard in `StackActions.addProduct` throwing `StackAddBlockedException`, sheet-level guard swapping the success banner.

Commit: `94c326d`.

### FLTR-17 — Ingredient name truncation (partial) `[-]`
BlockedProductView uses `SelectableText` for the banned substance reason → no truncation. Active/banned ingredient truncation in other contexts still pending.

---

## 4.2 RELEASE B — Safety/UX correctness (IN PROGRESS)

### FLTR-1 — Profile-filtered warnings `[x]`
`matchesProfile` iterates all `condition_ids[]` and `drug_class_ids[]`. ANY overlap with user profile returns true. Plural arrays are primary, singular preserved as derived getters. Legacy fallback checks plural lists.

Commit: `f555d45`. 12 tests covering 5 handoff scenarios + multi-tag regression pin.

### FLTR-5 — UL alert surfacing `[x]`
Extracts `rda_ul_data.analyzed_ingredients[].warnings[]` into synthesized `InteractionWarning` rows (severity=avoid, displayModeDefault='critical'). Appears in the alert list alongside interaction cards. Respects skip_ul_check.

Commit: `ebb1c8f`. 6 unit tests.

### FLTR-4 — product_status chip `[x]`
`ProductStatusChip` renders pipeline's `display` verbatim as a grey subdued tile. Forward-compat with future `type` values. Mounted as a sliver under the header.

Commit: `2c8e856`. 4 widget tests.

### FLTR-2 — Display fields (partial) `[x]`
Ingredient title uses `display_label` (fixes Vitamin A → "Vitamin A Palmitate"). Dose uses `display_dose_label`.

`display_badge` deferred — current pipeline emits all `no_data`; existing `_SafetyTag` (FLTR-11) already produces equivalent labels.

`standardization_note` deferred — not populated in inspected blobs.

Commit: `457d95c`.

### FLTR-SEARCH — Multi-word tokenize (baseline) `[x]`
FTS5 query splits on whitespace, ANDs each token with prefix match. Fixes "thorne vitamin a" → 0 results regression.

Commit: `6679722`. Phase 2.5 typo tolerance / relevance boost / ingredient-level search deferred.

---

### BATCH 1 — Trust & correctness layer (MUST SHIP TOGETHER)

The order below is intentional — each builds on the previous without fighting it.

### FLTR-12 — Warning dedup `[x]`
Commit: `5c72c19`. `InteractionWarning.dedupe` static helper collapses duplicates via composite key
`(sorted condition_ids, sorted drug_class_ids, normalized headline, normalized body)` — severity excluded so "monitor" and "caution" versions of the same message collapse; highest severity wins. First-occurrence order preserved. 11 tests covering identical collapse, severity-wins, whitespace/case normalization, condition/drug-class discrimination, authored-field priority, order preservation, edge cases. Wired into `_parseWarnings` after concat.

### FLTR-14 — Collapse safe-tier warnings `[x]`
Commit: `7f9f8da`. `InteractionWarningsList` partitions sorted warnings into `loud` (severity != safe) and `safeTier` (severity == safe). Safe-tier never renders full cards:
- loud empty + safeTier empty → existing "No known interactions" GOOD-news card
- loud empty + safeTier non-empty → single tappable `N low-concern note(s) ›` row
- loud non-empty → header + loud cards (count pill reflects loud only); safeTier appended as summary row below

Tap → minimal `_LowConcernNotesSheet` listing items verbatim. `Severity.informational` deliberately stays in the loud list — that's FLTR-18's "Other precautions" home, not here.

6 widget tests.

### FLTR-13 — Warning wording rewrites `[x]`
Commit: `ff2d919`.

Source audit found only 2 user-facing strings in Flutter:
- `_titleFor('avoid')` → "Avoid — conflicts with your profile" swapped to "Avoid — relevant to your profile" (keep "Conflict" for contraindicated tier only).
- `_WhyThisMayAffectYou` section heading "Why this may affect you" swapped to "Relevant to your health".

"Harmful additive" → "Additive concern" is effectively already neutral at the pipeline level: live blobs emit `title: "Contains {X}"` with body `"Flow agent — low overall concern."` (confirmed on dsld 245269/323076/336311/337873/323129/337868). No Flutter literal to replace.

Deterministic string swaps — no new tests; covered by existing regression suite.

### FLTR-19 — Discontinued chip UX polish `[x]`
Commit: `869f3e7`.

- Removed the info_outline icon (was a hidden affordance — looked tappable, wasn't)
- Whole row is now tappable; trailing `chevron_right` signals it
- Humanized date via `DateFormat.yMMMd()` — "Nov 28, 2017" instead of "2017-11-28"
- Label word: "Product discontinued" (reads as status, not adjective)
- Tap opens a minimal bottom sheet with plain-language explanation
- Forward-compatible `_typeLabels` map: discontinued / off_market / reformulated / limited_availability / seasonal; unknown types or unparseable dates fall back to the pipeline's `display` string verbatim

9 widget tests covering humanized label (known types), malformed-date fallback, row-tap opens sheet, no info-icon, chevron present, and forward-compat display fallback.

**Placement:** stays in the Concerns area (sliver below the header). Never in warnings/interactions/header alerts.

### FLTR-18 — "Applies to you" vs "Other precautions" split `[x]`
Commit: `53e4bd2`.

Loud warnings (everything except Severity.safe) split into two sections when the user has any declared profile data:
- **Applies to you** — `matchesProfile` returns true; always expanded; full cards; count pill
- **Other precautions** — everything else; collapsed by default with a "`N general precautions`" count row + chevron; tap to expand

Empty profile falls back to the pre-FLTR-18 single combined section so unprofiled surfaces don't collapse everything into "Other". Safe-tier continues to collapse via FLTR-14 regardless.

Converted `InteractionWarningsList` from StatelessWidget → StatefulWidget for the "Other" expand toggle. Extracted `_sectionHeader` and `_loudCards` as shared helpers so combined and split paths use one renderer.

8 widget tests (empty profile stays combined; profile+match shows Applies; Other starts collapsed; tap reveals cards; singular/plural count; applies-only/other-only boundaries; drug-class match; safe-tier still collapses alongside).

---

### FLTR-11a — Temporary Flutter dose guardrail `[x]`
Commit: `d360ec0`.

Narrow rule: if warning.severity ≥ caution AND warning.ingredient_name is in the allowlist AND disclosed `quantity` (same unit) < clinical threshold → downgrade to `monitor`.

**Never downgrades:**
- `contraindicated` (hard stops stay hard)
- `monitor` / `informational` / `safe` (already non-alarming)
- Ingredients outside the allowlist (UI never fabricates thresholds it wasn't told about)

**Allowlist:** `niacin` 35 mg, `vitamin b3 (niacin)` 35 mg, `chromium` 200 mcg. Kept intentionally small; extend only with clinical evidence.

**New additions on `InteractionWarning`:**
- `ingredientName` field (parsed from blob `ingredient_name`)
- `copyWithSeverity(Severity)` method for the downgrade step

**New helpers in `dose_safety.dart`:**
- `downgradeIfLowDose({severity, ingredient})` → `Severity?`
- `indexIngredientsByStandardName(List<Map>)` for fast lookup

Applied in `_DetailSection.build` after the profile filter, before passing to `InteractionWarningsList`. A new `guardedWarnings` list replaces the previous direct use of `filteredWarnings`.

**Deletion contract:** when E1.11 ships, delete the `_lowDoseThresholds` block, `downgradeIfLowDose`, `indexIngredientsByStandardName`, the guardrail loop in `_DetailSection.build`, and the 15 tests. No structural coupling to the rest of the codebase.

15 unit tests covering threshold hit/miss/boundary, severity tier never-touches, unknown-ingredient passthrough, unit mismatch, case-insensitive name matching, missing inputs, and the indexer.

---

### BATCH 2 — Architectural (ship after Batch 1 verify)

### FLTR-20 — Merge Active Ingredients + Form & Absorption `[~]`
Currently two separate cards show the same ingredient twice in two systems.

**Phase 1 (UI merge only, this batch):**
- Each active row shows: `{nutrient} (as {form}) — {dose}` + `{dose-safety badge}` + `{form-quality tag}`
- Example: `Vitamin A (as Palmitate) — 25,000 IU` / badge `Dose not evaluated` / tag `Excellent form` (colored: excellent/good/low)
- Remove the separate Form & Absorption card
- If a summary card is kept, name it "Why the ingredient quality scored well", not a second ingredient list

**Constraint:** UI merge only. Do NOT mutate the ingredient data model. Multi-form ingredients stay in the blob shape they ship in.

**Phase 2 (out of scope, pipeline follow-up E1.14):** normalize ingredient model to `{nutrient, forms[], dose_per_form}` aligned with scoring engine.

---

## 4.2.D RELEASE D — Goal-matching surfacing (NEW, OPEN)

These two are non-blocking enhancements that surface fields the pipeline now emits. Both are pure UI additions; no contract change.

### FLTR-21 — "Solo ingredient" badge on synergy cluster card `[ ]`
The pipeline now emits `synergy_detail.clusters[*].single_ingredient_match: bool`. When true, the cluster qualified via a lone primary ingredient at adequate dose (e.g. magnesium-only earning sleep_stack). Rendering a small badge ("Single-ingredient match" / "Solo headliner") on the cluster card helps users understand why a calcium-only product earned the bone goal.

**Where:** `lib/features/product_detail/widgets/pipeline_sections/synergy_detail_section.dart`. Read `cluster['single_ingredient_match']` (defaults to `false`). Add a chip next to the evidence-tier pill when true.

**Acceptance:** A solo-magnesium product surfaces "Single-ingredient match" beside the `sleep_stack` cluster. Multi-ingredient matches do not surface the badge.

### FLTR-22 — "Inferred from label" disclosure for synthetic actives `[ ]`
The pipeline injects a small number of synthetic ingredients (≤ 2 per product) into `display_ingredients` with `display_type: "inferred_from_name"`, `provenance: "product_name_fallback"`, `confidence: "inferred_high"`, `score_included: false`. These come from products like "DHA 1,000 mg Lemon Flavor" where the parser missed the headline ingredient.

**Where:** ingredient list render in product detail. When `display_ingredients[i].display_type == "inferred_from_name"`, render the row with a subtle subtitle ("inferred from product label") or info-icon tooltip. Builds user trust through transparency.

**Acceptance:** "DHA 1,000 mg Lemon Flavor" shows DHA 1000 mg in the ingredient list with the "inferred from label" disclosure. Standard parser-extracted ingredients render identically to today (no badge).

---

## 4.3 RELEASE C — UX redesign (DEFERRED)

### FLTR-3 — Five-layer product detail redesign `[~]`
Full §3 architecture. Multiple sections need re-ordering + styling pass.

### FLTR-6 — Inactive duplication cleanup `[~]`
Render inactive ingredients from `inactive_ingredients[]` only. Don't double up from additive arrays.

### FLTR-7 — Delete stale RDA file `[~]`
Delete `data/rda_optimal_uls.json` (runtime uses `assets/reference_data/rda_optimal_uls.json`).

### FLTR-8 — Warning grouping refinement `[~]`
Superset of FLTR-12. Stronger visual grouping of related warnings even after dedup (e.g., all kidney warnings as one accordion).

### FLTR-9 — Ingredient ordering `[~]`
Actives sorted by: (1) dose disclosed, (2) dose desc, (3) no-dose after disclosed. Inactives collapsed below.

### FLTR-15 — Discontinued warning filter `[~]`
Defensive: filter legacy `type == "status"` warnings so they never appear alongside the FLTR-4 chip. Current pipeline emits 0 of these; add the filter only if regression observed.

### FitScore +3 anomaly `[~]`
FitScore badge shows "+3 fit" on products when no user profile is completed. Must suppress badge until profile is at least partially set.

### FLTR-SEARCH Phase 2.5 `[~]`
- Typo tolerance (FTS5 trigram tokenizer OR edit-distance fallback)
- Brand-exact relevance boost over substring
- Ingredient-level search (match "magnesium glycinate" to products carrying it)
- "Did you mean?" nearest-neighbor suggestion on brand dictionary

---

# 5. DETAILED IMPLEMENTATION NOTES

## 5.1 FLTR-1 — Profile Filter (shipped)

```dart
bool matchesProfile({
  required Set<String> userConditions,
  required Set<String> userDrugClasses,
}) {
  if (conditionIds.any(userConditions.contains)) return true;
  if (drugClassIds.any(userDrugClasses.contains)) return true;
  return false;
}
```

Render filter (unchanged since existing 3-rule was correct):
```dart
warnings.where((w) {
  if (w.matchesProfile(...)) return true;
  final mode = w.displayModeDefault;
  if (mode == 'critical' || mode == 'informational') return true;
  if (mode == 'suppress') return false;
  // Legacy blob fallback: hide if tagged, show if generic.
  if (w.conditionIds.isNotEmpty) return false;
  if (w.drugClassIds.isNotEmpty) return false;
  return true;
}).toList();
```

## 5.2 FLTR-2 — Display fields (shipped)

```dart
final title = ingredient.displayLabel?.isNotEmpty == true
    ? ingredient.displayLabel!
    : ingredient.name;

final dose = ingredient.displayDoseLabel?.isNotEmpty == true
    ? ingredient.displayDoseLabel!
    : '—';
```

Badge mapping (future — when pipeline populates `display_badge`):
* `well_dosed` → "Well dosed"
* `low_dose` → "Low dose"
* `high_dose` → "High dose"
* `not_disclosed` → "Not disclosed"
* `no_data` → hide or mute

## 5.3 FLTR-4 — product_status (shipped)

Shape:
```json
{
  "product_status": {
    "type": "discontinued",
    "date": "2017-11-28",
    "display": "Discontinued · 2017-11-28"
  }
}
```

Rules:
* `product_status == null` → hide
* present → neutral grey chip in Concerns section (§3)
* Use `display` verbatim in current impl; humanize via FLTR-19

Future-proof types: `discontinued`, `off_market`, `reformulated`, `limited_availability`, `seasonal` — all render the same way.

## 5.4 FLTR-5 — UL alert rendering (shipped)

UL data lives in `blob.rda_ul_data.analyzed_ingredients[].warnings[]`, NOT in top-level `warnings[]`. Synthesize per-ingredient:

```dart
final synthesized = extractUlExceedances(ulAnalysis).map((e) =>
  InteractionWarning(
    severity: Severity.avoid,
    evidenceLevel: EvidenceLevel.established,
    title: 'Exceeds upper limit: ${e.standardName}',
    mechanism: e.warning,
    displayModeDefault: 'critical',
  )).toList();
```

Respects `skip_ul_check` (no synthetic alert when pipeline opts out).

UL source priority: `ul_for_default_profile ?? highest_ul`.

## 5.5 FLTR-10 — BLOCKED mode (shipped)

```dart
if (product.verdict == 'BLOCKED') {
  return BlockedProductView(
    dsldId: widget.dsldId,
    productName: productName,
    brandName: brandName,
    verdict: verdict,
    blockingReason: blockingReason,
    shareTitle: _product?.shareTitle,
    shareDescription: _product?.shareDescription,
    shareHighlights: _product?.shareHighlights,
  );
}
```

BlockedProductView watches `detailBlobProvider(dsldId)`. When the blob loads and carries `banned_substance_detail`, the view promotes:
- `substance_name` under "Why it's blocked"
- `safety_warning_one_liner` replaces generic banner copy
- `safety_warning` replaces the generic educational paragraph

Falls back to `blockingReason` from products_core + static educational text when blob absent.

FDA reference link: prefers `banned_substance_detail.source_url` (future pipeline field), falls back to FDA CDER tainted-supplements database.

## 5.6 FLTR-11 — Dose-vs-UL (shipped)

```dart
enum DoseSafety { skip, exceedsUl, withinLimits }

DoseSafety resolveDoseSafety({
  required Map<String, dynamic> ingredient,
  required List<Map<String, dynamic>>? ulAnalysis,
})
```

Routes through `rda_ul_data.analyzed_ingredients[]`, matches by `standard_name` (case-insensitive, whitespace-tolerant). Compares `quantity` (NOT `per_day_max`) against `ul_for_default_profile ?? highest_ul`.

Three states → three badges:
- `exceedsUl` → "High dose" (severityAvoid, warning icon)
- `skip` → "Dose not evaluated" (insufficientData, help icon)
- `withinLimits` → falls through to bioScore tiers

## 5.7 FLTR-12 — Dedup (in progress)

Composite dedup key:
```dart
String displayKey(InteractionWarning w) {
  final conditions = [...w.conditionIds]..sort();
  final drugClasses = [...w.drugClassIds]..sort();
  final severity = w.severity.name;
  final headline = (w.displayHeadline).trim().toLowerCase();
  final body = (w.displayBody).trim().toLowerCase();
  return '${w.type}|$severity|${conditions.join(',')}|${drugClasses.join(',')}|$headline|$body';
}
```

When collision: keep highest severity, drop the rest.

Normalize severity first: `monitor` and `caution` versions of the same message must collapse together (pick highest).

## 5.8 FLTR-13 — Wording (not started)

| Current | New |
|---|---|
| "Harmful additive: X" | "Additive concern: X" |
| "Conflict with your profile" | "Relevant to your profile" |
| "Why this may affect you" | "Relevant to your health" |

Verify source per string: whether it lives in Flutter or in the blob. If blob, override in the render-side string map; file pipeline ticket for canonical source update.

## 5.9 FLTR-14 — Collapse safe-tier (not started)

Rendering rules:
- Safe-tier warnings (severity == safe, type in {informational flow-agent, low overall concern}) never appear as full cards
- Aggregate into one collapsed summary row: `N low-concern notes ›`
- When no non-safe warnings exist for a section: render `No significant interactions found`
- Expandable: tap row → show the individual safe items in a sheet

## 5.10 FLTR-16 — Stack safety gate (shipped)

Three layers:
```dart
// 1. UI guard (PGStackActionButtons._handleAdd)
if (isUnsafeVerdict(product.verdict)) {
  showSnackBar('This product cannot be added due to safety concerns.');
  return;
}

// 2. Domain guard (StackActions.addProduct)
if (isUnsafeVerdict(product.verdict)) {
  throw StackAddBlockedException(dsldId: product.dsldId, verdict: product.verdict);
}

// 3. Sheet-level guard (_SafetyCheckSheet)
if (isUnsafeVerdict(productVerdictFromBlob)) {
  return _UnsafeProductBanner();
}
```

`isUnsafeVerdict` = BLOCKED or UNSAFE. `isBlockedVerdict` = BLOCKED only.

## 5.11 FLTR-11a — Temporary dose guardrail (not started)

```dart
/// Pre-pipeline defensive rule — prevents low-dose ingredients from
/// firing pharmacologic-level severity. Remove when E1.11 ships.
bool shouldDowngradeSeverity(
  InteractionWarning w,
  Map<String, dynamic> ingredient,
) {
  if (w.severity.weight < Severity.caution.weight) return false;
  final id = (ingredient['standard_name'] ?? '').toString().toLowerCase();
  final qty = (ingredient['quantity'] as num?)?.toDouble() ?? 0;
  final threshold = _lowDoseThresholds[_canonicalize(id)];
  if (threshold == null) return false;
  return qty > 0 && qty < threshold;
}

const _lowDoseThresholds = <String, double>{
  'niacin': 35,           // mg — RDA UL for non-pharmacologic use
  'vitamin b3 (niacin)': 35,
  'chromium': 200,        // mcg — typical prenatal range ceiling
  // keep list small and explicit; extend only with clinical evidence
};
```

Applied in `_DetailSection.build` before the render filter: downgrade severity to `monitor` (or `informational` if it was already < major) when the rule fires. Log the downgrade to telemetry so we can measure pipeline E1.11 coverage later.

## 5.12 FLTR-18 — Personalization split (not started)

Replace the current single `filteredWarnings` list with two lists:

```dart
final applies = <InteractionWarning>[];
final other = <InteractionWarning>[];
for (final w in warnings) {
  if (!_shouldShow(w, userConditions, userDrugClasses)) continue;
  if (w.matchesProfile(userConditions: userConditions, userDrugClasses: userDrugClasses)) {
    applies.add(w);
  } else {
    other.add(w);
  }
}
```

Render:
- **Applies to you** — full-width cards, severity sorted
- **Other precautions** — collapsed by default with a count (`3 general precautions ›`); expand on tap

Both sections respect severity sort internally.

## 5.13 FLTR-19 — Discontinued chip polish (not started)

Format:
```
Product discontinued · Nov 28, 2017
```

- Drop the info icon
- Parse `date` field from `product_status` block, format as `MMM d, yyyy`
- Keep `display` as a fallback when `date` is absent
- Wrap in `InkWell` → bottom sheet with explanation

**Placement:** Concerns section. Never alongside warnings/interactions/header alerts.

## 5.14 FLTR-20 — Ingredient + form merge (Batch 2)

Phase 1 row layout:
```
Vitamin A (as Palmitate)        25,000 IU
● Dose not evaluated  Excellent form  vitamins
```

- Title: `{standard_name} (as {form-if-present})` — pull form from blob's `extracted_forms[0].display_form` or `matched_form`
- Dose: `display_dose_label`
- Badge 1: dose-safety (FLTR-11)
- Badge 2: form-quality tag (colored: excellent/good/low) from scoring engine's form tier
- Remove the separate "Form & Absorption" card

**Data constraint:** UI merge only. Do NOT mutate the ingredient data model. Multi-form ingredients keep their blob shape — forward-compat with E1.14 normalization.

## 5.15 Severity Mapping (UI Contract)

| Severity          | UI Style              | Layer                                 |
| ----------------- | --------------------- | ------------------------------------- |
| `contraindicated` | red banner / red chip | Alerts                                |
| `major`           | red                   | Alerts                                |
| `moderate`        | orange                | Alerts or Tradeoffs depending on type |
| `minor`           | yellow/neutral amber  | Tradeoffs                             |
| `informational`   | grey                  | Concerns / Other precautions          |
| `safe`            | n/a                   | Collapsed — never a full card         |

Alerts layer only includes: contraindicated, major, UL exceedance, banned substance / recalled, truly safety-relevant moderate alerts. Do NOT flood Alerts with minor informational text.

## 5.16 Category Enforcement (render contract)

| Warning type       | Correct section |
| ------------------ | --------------- |
| interaction        | Alerts          |
| contraindication   | Alerts          |
| UL exceeded        | Alerts          |
| banned substance   | Alerts (or Blocked mode) |
| excipients / flow agents | Tradeoffs or Concerns |
| discontinued       | Concerns        |
| additive concern   | Concerns        |

**Never** render excipients / flow agents / anti-caking in the interaction cards section.

---

# 6. PIPELINE FOLLOW-UPS (not Flutter)

These are filed for the pipeline team based on what Flutter discovered during Release A/B work.

### E1.6 — Vitamin A skip_ul_reason misfire `[P]`
`skip_ul_reason="unknown_vitamin_form"` fires even when `matched_form="retinyl palmitate"` is resolved in the ingredient block. Form detection for the UL-skip rule should consult the same `matched_form` output.

### E1.7 — Ingredient `form` field empty `[P]`
Many ingredients have `form=""` while `display_label` / `extracted_forms[0].display_form` / `matched_form` carry the correct form. The `form` column should be populated from the same source.

### E1.8 — `blocking_reason` column enum `[P]`
Every blocked product in `products_core` has `blocking_reason = 'banned_ingredient'`. Consider emitting the substance name here too so non-blob contexts (search thumbnails, stack banners) can reference it.

### E1.9 — Duplicate DSLD listings `[P]`
Same product appears 2× with different scores (e.g., GNC Women's Ultra Mega: 51 and 56). Decide between dedup-by-fingerprint or expose a "variants" relationship.

### E1.10 — FTS index rebuild `[P]`
For FLTR-SEARCH Phase 2.5: rebuild FTS index with trigram tokenizer, add ingredient tokens (so "magnesium glycinate" finds products carrying it), add brand-exact relevance boost.

### E1.11 — Dose-aware warning severity `[P]` ⚠️ CRITICAL
Current state: pipeline fires warnings by ingredient presence regardless of dose. A prenatal with 10–20 mg niacin fires the same severity as pharmacologic 500 mg niacin.

Required rule:
1. Condition match
2. Evidence match
3. **Dose threshold match**

If dose threshold is not met → downgrade to informational or monitor. Do not label as avoid.

Until this lands, Flutter applies a temporary guardrail (FLTR-11a).

### E1.12 — Warning dedup at pipeline level `[P]`
Pipeline currently emits `"Vitamin A / pregnancy"` twice inside the same `warnings[]` and also duplicates across `warnings` ↔ `warnings_profile_gated`. Flutter dedupes at render (FLTR-12) but pipeline should also.

### E1.13 — Pre-sorted profile buckets `[P]`
Pipeline could pre-split warnings into `applies_to_profile` vs `other_precautions` buckets based on anonymous-default profile matching, reducing Flutter responsibility.

### E1.14 — Ingredient data model normalization `[P]`
Normalize to `{nutrient, forms[], dose_per_form}` aligned with scoring engine. Enables FLTR-20 Phase 2 proper fix.

### E1.15 — `banned_substance_detail.source_url` field `[P]`
Add per-substance reference URL (FDA, EU, WHO, etc.) to the banned_substance_detail block. Flutter already reads this with an FDA fallback.

---

## 6.1 E1.16 — Goal-matching contract refactor `[x]` SHIPPED (2026-04-24)

**What changed.** `scripts/data/user_goals_to_clusters.json` schema **v5.2.0 → v6.0.0**. `compute_goal_matches()` rewritten. Goals are now pipeline-owned; Flutter does intersection only.

**Simplified per-goal contract** (exactly six fields):
- `id`, `user_facing_goal`, `cluster_weights`, `required_clusters`, `blocked_by_clusters`, `min_match_score`
- Dropped: `goal_category`, `goal_priority`, `core_clusters`, `anti_clusters`, `cluster_limits`, `confidence_threshold`, `conflicting_goals`, `synergy_goals`.

**Matching algorithm (pipeline):**
```
for each goal:
  skip if any blocked_by_clusters present in product_clusters
  skip if required_clusters non-empty and none present
  score_full     = matched_weight / sum(cluster_weights.values())
  score_required = matched_required_weight / sum(required_cluster_weights)
  score = max(score_full, score_required)
  include if score >= min_match_score
goal_match_confidence = avg(matched_scores), 2-dp
```

**Canonical Flutter IDs enforced** (18 total): `GOAL_SLEEP_QUALITY, GOAL_REDUCE_STRESS_ANXIETY, GOAL_INCREASE_ENERGY, GOAL_DIGESTIVE_HEALTH, GOAL_WEIGHT_MANAGEMENT, GOAL_CARDIOVASCULAR_HEART_HEALTH, GOAL_HEALTHY_AGING_LONGEVITY, GOAL_BLOOD_SUGAR_SUPPORT, GOAL_IMMUNE_SUPPORT, GOAL_FOCUS_MENTAL_CLARITY, GOAL_MOOD_EMOTIONAL_WELLNESS, GOAL_MUSCLE_GROWTH_RECOVERY, GOAL_JOINT_BONE_MOBILITY, GOAL_SKIN_HAIR_NAILS, GOAL_LIVER_DETOX, GOAL_PRENATAL_PREGNANCY, GOAL_HORMONAL_BALANCE, GOAL_EYE_VISION_HEALTH`.

**Renames applied** (3/18 legacy → canonical): `GOAL_JOINT_BONE_HEALTH` → `GOAL_JOINT_BONE_MOBILITY`, `GOAL_HORMONE_BALANCE` → `GOAL_HORMONAL_BALANCE`, `GOAL_EYE_VISION` → `GOAL_EYE_VISION_HEALTH`.

**Bug fix (critical).** The previous `compute_goal_matches` was reading `synergy_detail.clusters_matched` — a path that does NOT exist in the enrichment output — so every product shipped with `goal_matches: []`. Fixed to read `formulation_data.synergy_clusters[*].cluster_id` (the real source of truth from `enrich_supplements_v3.py::_collect_synergy_data`). Rebuilding the final DB will now populate these fields correctly for all 13,236 products.

**Contract columns** (unchanged):
- `products_core.goal_matches` (TEXT / JSON array of goal IDs)
- `products_core.goal_match_confidence` (REAL / 0.0–1.0 average)

**Orphan clusters mapped to goals:**
- `omega3_niacin_lipid` → GOAL_CARDIOVASCULAR_HEART_HEALTH (required, weight 0.9)
- `blood_pressure_support` → GOAL_CARDIOVASCULAR_HEART_HEALTH (required, 1.0) + GOAL_HEALTHY_AGING_LONGEVITY (0.5)
- `wound_healing` → GOAL_SKIN_HAIR_NAILS (required, 0.6)
- `nerve_health_neuropathy_support` → GOAL_BLOOD_SUGAR_SUPPORT (diabetic neuropathy, 0.4)

**Other goal-mapping touch-ups:**
- `GOAL_SLEEP_QUALITY.blocked_by_clusters`: removed `focus_attention_support`. Magnesium products that incidentally tag both sleep + focus clusters no longer false-exclude from Sleep. Only `pre_workout_energy` remains as a sleep blocker.

**Flutter impact:** consume `product.goalMatches` + `product.goalMatchConfidence` and compute `userGoals ∩ productGoalMatches`. Already shipped — no Flutter change required. Fallback calculator in `e2a_goal_calculator.dart` patched to use v6.0.0 field names (`blocked_by_clusters`, `required_clusters`, `min_match_score`).

## 6.2 E1.17 — Cluster-ingredient alias map `[x]` SHIPPED (2026-04-24)

**New file:** `scripts/data/cluster_ingredient_aliases.json` (schema v1.0.0, 25 canonical entries, ~80 aliases).

Recovers ~200 catalog products where the DSLD parser wrote `coenzyme q10` but the cluster ingredient is `coq10`, or `docosahexaenoic acid` vs `dha`. Aliases flow through `_collect_synergy_data` with the same match rigor as canonical (exact / loose substring / word-boundary).

**Governance guarantees** (pinned by `test_cluster_ingredient_aliases.py`):
- No alias string may belong to two canonical keys (catches the classic ALA = alpha-lipoic-acid / alpha-linolenic-acid ambiguity)
- No generic marketing terms (`support`, `complex`, `blend`) permitted as aliases
- Aliases ≥ 3 chars, canonicals lowercase

**Flutter impact:** none. Alias resolution is pipeline-only; Flutter does not consume `cluster_ingredient_aliases.json`.

## 6.3 E1.18 — Synergy-cluster single-ingredient override `[x]` SHIPPED (2026-04-24)

**Schema bump:** `scripts/data/synergy_cluster.json` v5.0.0 → v5.1.0 (additive fields, backward-compatible).

17 clusters now carry two opt-in fields:
- `allow_single_ingredient: true`
- `primary_ingredients: [...]` — curated subset of `ingredients[]` that qualify as solo headliners

Canonical single-ingredient pairings enabled:
| Cluster | Solo primary ingredients |
|---|---|
| `sleep_stack` | magnesium, magnesium glycinate, melatonin, l-theanine, theanine, suntheanine, valerian root, valerian, ashwagandha |
| `prenatal_pregnancy_support` | dha, folate, folic acid, methylfolate, 5-mthf, choline |
| `bone_health` | calcium, calcium citrate/carbonate, vitamin d3, cholecalciferol, vitamin k2, mk-7 |
| `immune_defense` | vitamin c, ascorbic acid, zinc, zinc picolinate/bisglycinate, elderberry, echinacea, vitamin d3, cholecalciferol |
| `iron_absorption` | iron |
| `cardiovascular_support` | coq10, ubiquinol, fish oil, omega-3, epa, dha |
| `omega_3_absorption_enhancement` | fish oil, krill oil, epa, dha, omega-3 |
| `omega3_niacin_lipid` | fish oil, epa, dha, omega-3, niacin |
| `blood_pressure_support` | beet root, hibiscus, coq10, magnesium |
| `liver_support` | milk thistle, silymarin, nac, tudca |
| `muscle_building_recovery` | creatine, whey protein, bcaa, leucine |
| `collagen_synthesis_support` | collagen peptides |
| `eye_health` | lutein, zeaxanthin, astaxanthin, bilberry |
| `curcumin_absorption` | curcumin phytosome, meriva, theracurmin, bcm-95, longvida |
| `hair_skin_nutrition` | biotin, keratin |
| `probiotic_and_gut_health` | lactobacillus, bifidobacterium, saccharomyces boulardii |
| `magnesium_nervous_system` | magnesium, magnesium bisglycinate, magnesium malate |

**Dose adequacy still required.** Single-ingredient match requires `meets_minimum=True` for the matched ingredient. Trace minerals (e.g. 17 mg magnesium in whey protein) remain correctly filtered — they will NOT trigger sleep_stack.

**Scoring isolation (important).** Single-ingredient cluster matches are **goal-matching-only**. The synergy-score bonus in `score_supplements.py` still requires `match_count >= 2` — solo matches do NOT inflate the product's quality score.

**New detail-blob field**: `synergy_detail.clusters[*].single_ingredient_match` (bool). True when the cluster qualified via the solo-primary path. Exposed for Flutter (see FLTR-21).

## 6.4 E1.19 — Enrichment cluster-match hardening `[x]` SHIPPED (2026-04-24)

Four surgical fixes to `_collect_synergy_data` in `enrich_supplements_v3.py` that eliminated whole classes of false positives / false negatives:

1. **Ingredient deduplication.** Prevents the same product ingredient from satisfying the synergy gate by matching multiple cluster variants. Example: "Magnesium 17 mg" used to match both `magnesium` and `magnesium glycinate` as TWO hits; it now counts once. Root cause of the Whey+ → Sleep false positive.
2. **Min-dose inheritance.** `magnesium glycinate` now inherits the 100 mg minimum from `magnesium` via longest-prefix lookup when not explicitly dosed in the cluster config. Closes the variant-naming bypass.
3. **Biochem abbreviation matching.** Short terms (`dha`, `epa`, `nac`, `mk7`) now match product ingredients via word-boundary regex. `"DHA (Docosahexaenoic Acid)"` now matches cluster ingredient `dha`. Word boundary (\b) prevents `EPA` from matching `HEPATIC`.
4. **Qty>0 gate.** Products listing nutrient names with `quantity=0` (unit `NP`) no longer pass dose adequacy when the cluster has no explicit min_dose. Killed the Soy Protein trace-mineral false positives.

## 6.5 E1.20 — Product-name fallback synthesizer `[x]` SHIPPED (2026-04-24)

**New method:** `SupplementEnricherV3._synthesize_ingredients_from_name`.

When `activeIngredients` is sparse (≤ 2 entries) AND the product name matches a strict biochem-nutrient + dose pattern, a synthetic ingredient is injected into the **cluster-matching path only**. Recovers products like "DHA 1,000 mg Lemon Flavor" where the parser extracted only DPA 75mg.

**Strict allowlist (17 patterns):** DHA, EPA, Magnesium, Calcium, Iron, Zinc, Vitamin C, Vitamin D3, Vitamin B12, CoQ10, Melatonin, Biotin, Creatine, Collagen, Ashwagandha, Turmeric, Curcumin. Product names ending in generic marketing terms (`Support`, `Complex`, `Blend`, `Formula`, `Boost`, `Matrix`, `System`, `Pack`, `Bundle`, `Kit`) are rejected.

**Audit trail:**
- Synthetic active ingredients carry `provenance: "product_name_fallback"` + `confidence: "inferred_high"` + `inferred_from: <full name>`
- Mirror entry in `display_ingredients` with `display_type: "inferred_from_name"` and `score_included: false`

**Scoring isolation.** Synthetic ingredients are NOT written back into `product["activeIngredients"]`. They only flow through the synergy-cluster + goal-matching path. The Section A ingredient-quality scorer still sees only the parser's real actives. This is the "avoid contaminating scoring blindly" rule from code review.

**Net catalog impact** (24-product canary, seed=42): goal-match rate 21% → **58–67%** depending on product mix. DHA → Prenatal now works. Magnesium → Sleep now works. Vitamin C → Immune now works. Fish oil → Cardio now works. Trace-mineral false positives (e.g. whey+magnesium → sleep) eliminated.

## 6.6 E1.21 — Score formula `max(score_full, score_required)` with MAX-of-required-weights `[x]` SHIPPED (2026-04-24)

**Problem discovered after the first full-catalog pipeline rebuild.** `GOAL_DIGESTIVE_HEALTH` matched only **10 out of 8,169** products (0.1%). `GOAL_FOCUS_MENTAL_CLARITY` (159) and `GOAL_MUSCLE_GROWTH_RECOVERY` (126) were similarly thin.

**Root cause.** For goals with multiple required_clusters (DIGESTIVE has 3: gut_barrier, probiotic_and_gut_health, digestive_enzymes), the score formula summed required weights: `score_required = matched_required_weight / SUM(required_weights)`. A pure probiotic product hitting one required cluster scored only 1.0 / 2.9 = 0.34 — below the 0.5 threshold.

**Fix.** Use `MAX(required_weights)` in the denominator so a product fully covering the highest-weight required cluster earns 1.0:
```
score_required = max(matched_required_weights) / max(all_required_weights)
score = max(score_full, score_required)
```

**Catalog impact** (simulated on 8169 blobs):
- `GOAL_DIGESTIVE_HEALTH`: 10 → **711** (70×)
- `GOAL_FOCUS_MENTAL_CLARITY`: 159 → **672** (4×)
- `GOAL_MUSCLE_GROWTH_RECOVERY`: 126 → **265** (2×)
- Overall match rate: **50.8% → 62.5%**

Flutter impact: none. Contract columns `goal_matches` / `goal_match_confidence` unchanged.

## 6.7 E1.22 — Synthesizer name-read fallback (the silent zero-fire bug) `[x]` SHIPPED (2026-04-24)

**Problem.** Despite E1.20 shipping Solution B (product-name synthesizer), the 8169-product dashboard snapshot had **zero** `display_type="inferred_from_name"` entries. DHA 1,000 mg still produced `goal_matches: []`. Synthesizer silently returned early on every single product.

**Root cause.** `_synthesize_ingredients_from_name` read `product.get('product_name')`. But `_collect_synergy_data` is called from the pipeline with the RAW `product` dict, which uses DSLD's native field names `productName` / `fullName`. The enricher renames `fullName → product_name` on a DIFFERENT (`enriched`) dict at line 12234. My direct canary tests happened to use `product_name` as the key and passed; the production pipeline was passing `productName` and hitting `if not name: return [], []`.

**Fix.** Fallback chain:
```python
name = (
    product.get('product_name')
    or product.get('fullName')
    or product.get('productName')
    or ''
).strip()
```

**Verified end-to-end on raw cleaned "DHA 1,000 mg Lemon Flavor":**
- synergy_clusters: 4 (cardio, omega_3_absorption, prenatal, omega3_niacin_lipid)
- display_ingredients: 1 `inferred_from_name` entry for DHA 1000 mg
- **goal_matches: `[GOAL_CARDIOVASCULAR_HEART_HEALTH, GOAL_PRENATAL_PREGNANCY]`**

**Catalog-wide projection** (scan of 13,236 cleaned products): **776 products (5.9%)** will gain synthesized actives after next rebuild. Top beneficiaries: CoQ10 (166), Vitamin C (115), Vitamin D3 (104), Biotin (87), Melatonin (72), Vitamin B12 (59), Calcium (43), Magnesium (37), Zinc (25), Iron (22), DHA (16), Curcumin (16), EPA (7).

Flutter impact: none for consumption (`goal_matches` works the same). FLTR-22 remains the open ticket for optional "inferred from label" badge UI.

## 6.8 E1.23 — Absorption-enhancer sub-threshold demotion (unlocks A6 for BioPerine-paired single-nutrient products) `[x]` SHIPPED (2026-04-24)

**Problem.** Single-ingredient ashwagandha / curcumin / resveratrol SKUs paired with a sub-therapeutic BioPerine 5 mg (standard bioavailability-aid dosing) were misclassified as `supplement_type: targeted` instead of `single_nutrient`. Two compounding effects:
1. **A1 bioavailability diluted**: BioPerine's IQM form_score (12) pulled the weighted average down. KSM-66 alone scored A1 = 11.67; KSM-66 + BioPerine scored 11.11.
2. **A6 single-ingredient efficiency bonus (+2.0 pts) blocked**: the `A6_single_ingredient_efficiency.single_types` gate accepts only `["single", "single_nutrient"]`, so `targeted` products miss it.

**Fix — Option A (approved design, per per-enhancer dose-threshold pattern):**

1. **Schema change.** `absorption_enhancers.json` v5.0.0 → v5.1.0 (additive). New OPTIONAL per-enhancer field:
   ```json
   "non_scorable_when_sub_threshold": {
     "threshold_mg": 10,
     "rationale": "Piperine ≤10 mg is bioavailability-aid dosing..."
   }
   ```
   Added to `ENHANCER_BLACK_PEPPER` only. Every other enhancer (Vitamin C, Vitamin D, MK7, amino acids, probiotics, garlic, etc.) intentionally NOT tagged — those have independent nutritional value and must stay scorable.

2. **Enricher method** `_apply_absorption_enhancer_demotion()` runs at end of `_collect_ingredient_quality_data()`. For each scorable row matched to a listed enhancer at or below threshold: flip `role_classification = recognized_non_scorable`, `score_included = false`, record `demotion_reason` / `demotion_ref` / `demotion_rationale` for audit. Row removed from `ingredients_scorable` but left in `product["activeIngredients"]`.

3. **Supplement type re-classified after IQD built** (previously ran before IQD). The classifier already skips `recognized_non_scorable` rows, so it naturally picks up the demotion and returns `single_nutrient`.

4. **Audit surfacing.** New field `ingredient_quality_data.demoted_absorption_enhancers: [...]` carries the demoted list for QA audit and potential Flutter chip rendering.

5. **Critical preservation.** Synergy-cluster matching still sees piperine (so curcumin+piperine synergy fires via `curcumin_absorption` cluster). Interaction-rule analysis still sees piperine (so piperine-CYP drug alerts fire). Only the A1/A6 scoring path is narrowed.

**KSM-66 600 mg measured delta:**
| Field | Before E1.23 | After E1.23 | Δ |
|---|---|---|---|
| supp_type | `targeted` | **`single_nutrient`** | flipped |
| A1 | 11.11 | **11.67** | **+0.56** |
| A6 | 0.00 | **2.00** | **+2.00** |
| score_80 | 48.30 | **50.90** | **+2.60** (+3.3%) |

**Catalog-wide projection**: **28 products** across 4 brands (Doctor's Best 11, Nutricost 10, Pure Encapsulations 4, Sports Research 3) will flip `targeted → single_nutrient` on next pipeline rebuild. Per-product gain: +1.5 to +2.8 points on score_80.

**Tests**: 8 new in `test_absorption_enhancer_demotion.py` — piperine ≤10mg demoted, >10mg stays scorable, exactly-10mg inclusive, activeIngredients preserved for cluster matching, supp_type flips correctly, Vitamin C never demoted, provenance recorded, empty demoted list when no enhancer present.

Flutter impact: none (no schema change at the contract layer). Could optionally render `demoted_absorption_enhancers` list as "Includes bioavailability aid: BioPerine 5 mg" info chip.

---

# 7. PRODUCT SMOKE TESTS

Use these after implementation.

## 15640 — Thorne Vitamin A
- ✅ No pregnancy warning for male user (FLTR-1)
- ✅ "Vitamin A Palmitate" label (FLTR-2)
- ⚠️ "Dose not evaluated" badge — intentional (FLTR-11 + E1.6 pipeline bug)
- ✅ "Discontinued · 2017-11-28" as neutral chip (FLTR-4)
- ✅ No green SAFE chip for discontinuation
- `[ ]` FLTR-19: humanized date + tappable → bottom sheet

## 69497 — GNC Women's Ultra Mega
- ✅ "Exceeds upper limit: Vitamin B3 (Niacin)" alert card (FLTR-5)
- ✅ Niacin badge: "High dose" (FLTR-11)
- `[ ]` FLTR-11a: if other ingredients at low nutritional doses, they should NOT fire caution/avoid warnings
- `[ ]` FLTR-18: kidney-disease warning (if present) goes in "Other precautions", not "Applies to you"

## 16012 — Thorne Vinpocetine
- ✅ BlockedProductView renders (FLTR-10)
- ✅ Substance name: "Vinpocetine" (not `banned_ingredient`)
- ✅ FDA-2019 statement in body
- ✅ "Look up on FDA" link at bottom

## 19055 — Spring Valley Fish Oil
- Confirm Section A score against actual blob before publishing smoke expectations

## 35491 — Plantizyme
- Confirm Section A score against actual blob
- `[ ]` FLTR-14: inactives not spammed as green chips

## 246324 — VitaFusion CBD
- ✅ Banned-substance handling via BlockedProductView
- `[ ]` FLTR-12: no duplicate warning cards

---

# 8. DATA CONTRACT NOTES

## Safe fallback expectations

- `display_label ?? standard_name ?? name ?? raw_source_text`
- `display_dose_label ?? "{quantity} {unit}" ?? "—"`
- `product_status == null` → hide chip
- no profile → suppress warnings remain hidden
- no UL profile data → fallback to `highest_ul`
- `skip_ul_check == true` → neutral, never overridden by UI

## Never do in Flutter

- infer dose from blend totals (use `display_dose_label`)
- invent badges (use pipeline's `display_badge` or fall through to FLTR-11 logic)
- compute probiotic adequacy independently
- promote `name` over `display_label`
- render `product_status` as safe/warning
- override `skip_ul_check=true` with a synthesized UL alert
- concatenate `warnings[]` + `warnings_profile_gated[]` without dedup (FLTR-12)
- show general precautions in the "Applies to you" section (FLTR-18)
- fabricate dose thresholds beyond the small explicit FLTR-11a list

---

# 9. OWNERSHIP TABLE

| ID         | Issue                                    | Owner    | Priority | Status |
| ---------- | ---------------------------------------- | -------- | -------- | ------ |
| FLTR-1     | Profile filter (ANY multi-tag match)     | Flutter  | High     | `[x]`  |
| FLTR-2     | Use display_label / display_dose_label   | Flutter  | High     | `[x]`  |
| FLTR-3     | Five-layer redesign                      | Flutter  | Medium   | `[~]`  |
| FLTR-4     | product_status chip                      | Flutter  | Medium   | `[x]`  |
| FLTR-5     | UL alert rendering                       | Flutter  | High     | `[x]`  |
| FLTR-6     | Inactive duplication cleanup             | Flutter  | Medium   | `[x]`  |
| FLTR-7     | Delete stale RDA file                    | Flutter  | Low      | `[~]`  |
| FLTR-8     | Warning grouping refinement              | Flutter  | Medium   | `[~]`  |
| FLTR-9     | Ingredient ordering                      | Flutter  | Low      | `[x]`  |
| FLTR-10    | BLOCKED mode override                    | Flutter  | High     | `[x]`  |
| FLTR-11    | Dose-vs-UL badge override                | Flutter  | High     | `[x]`  |
| FLTR-11a   | Temporary dose guardrail (pre-pipeline)  | Flutter  | High     | `[x]`  |
| FLTR-12    | Warning dedup (composite key)            | Flutter  | High     | `[x]`  |
| FLTR-13    | Wording rewrites (Additive/Relevant)     | Flutter  | High     | `[x]`  |
| FLTR-14    | Collapse safe-tier warnings              | Flutter  | High     | `[x]`  |
| FLTR-15    | Discontinued warning filter (defensive)  | Flutter  | Low      | `[~]`  |
| FLTR-16    | Stack safety gate                        | Flutter  | High     | `[x]`  |
| FLTR-17    | Banned/active name truncation            | Flutter  | Medium   | `[-]`  |
| FLTR-18    | Applies-to-you vs Other precautions      | Flutter  | High     | `[x]`  |
| FLTR-19    | Discontinued chip UX polish              | Flutter  | Medium   | `[x]`  |
| FLTR-20    | Merge Active Ingredients + Form (UI)     | Flutter  | Medium   | `[x]`  |
| FLTR-SEARCH| Multi-word search (baseline)             | Flutter  | High     | `[x]`  |
| FLTR-SEARCH Phase 2.5 | Typo tolerance + ranking      | Flutter+Pipeline | Medium | `[~]` |
| FitScore   | +3 badge on empty profile                | Flutter  | Medium   | `[~]`  |
| E1.6       | skip_ul_reason misfire (Vitamin A form)  | Pipeline | Medium   | `[P]`  |
| E1.7       | ingredient.form empty                    | Pipeline | Low      | `[P]`  |
| E1.8       | blocking_reason column enum              | Pipeline | Low      | `[P]`  |
| E1.9       | Duplicate DSLD listings                  | Pipeline | Medium   | `[P]`  |
| E1.10      | FTS index rebuild (trigram + ingredients)| Pipeline | Medium   | `[P]`  |
| E1.11      | Dose-aware warning severity              | Pipeline | **High** | `[P]`  |
| E1.12      | Warning dedup at pipeline level          | Pipeline | Medium   | `[P]`  |
| E1.13      | Pre-sorted profile buckets               | Pipeline | Low      | `[P]`  |
| E1.14      | Ingredient data model normalization      | Pipeline | Medium   | `[P]`  |
| E1.15      | banned_substance_detail.source_url       | Pipeline | Low      | `[P]`  |
| E1.16      | Goal-matching contract refactor (v6.0.0) | Pipeline | High     | `[x]`  |
| E1.17      | Cluster-ingredient alias map             | Pipeline | High     | `[x]`  |
| E1.18      | Synergy single-ingredient override       | Pipeline | High     | `[x]`  |
| E1.19      | Enrichment cluster-match hardening       | Pipeline | High     | `[x]`  |
| E1.20      | Product-name fallback synthesizer        | Pipeline | High     | `[x]`  |
| E1.21      | Score formula: MAX-of-required-weights   | Pipeline | High     | `[x]`  |
| E1.22      | Synthesizer name-read fallback (pipeline-site fix) | Pipeline | High | `[x]` |
| E1.23      | Absorption-enhancer sub-threshold demotion (unlocks A6) | Pipeline | High | `[x]` |
| FLTR-21    | "Solo ingredient" cluster badge          | Flutter  | Low      | `[ ]`  |
| FLTR-22    | "Inferred from label" actives disclosure | Flutter  | Low      | `[ ]`  |
| FLTR-23    | Optional: "Includes bioavailability aid" chip (E1.23 audit surface) | Flutter | Low | `[ ]` |

---

# 10. RELEASE SEQUENCE

## Release A `[x]` SHIPPED (6 commits)

- `2f857a5` FLTR-10 blocked mode base
- `94c326d` FLTR-16 stack safety gate
- `2f9176f` FLTR-11 v1 (superseded)
- `b66ac8f` FLTR-10 enrich (banned_substance_detail)
- `77410a2` FLTR-11 v2 schema fix (rda_ul_data + skip_ul_check)
- `5fda6c6` FLTR-10 FDA reference link

## Release B — Part 1 `[x]` SHIPPED (5 commits)

- `f555d45` FLTR-1 profile filter (plural arrays + ANY match)
- `ebb1c8f` FLTR-5 UL alert rendering
- `2c8e856` FLTR-4 product_status chip
- `457d95c` FLTR-2 display_label / display_dose_label
- `6679722` FLTR-SEARCH multi-word tokenize

## Release B — Part 2 `[x]` SHIPPED

All 6 Batch 1 tickets landed (each compounds on the previous):
1. **FLTR-12** dedup `[x]` — commit `5c72c19`
2. **FLTR-14** collapse safe-tier `[x]` — commit `7f9f8da`
3. **FLTR-13** wording rewrites `[x]` — commit `ff2d919`
4. **FLTR-19** discontinued UX polish `[x]` — commit `869f3e7`
5. **FLTR-18** Applies-to-you vs Other precautions split `[x]` — commit `53e4bd2`
6. **FLTR-11a** temporary dose guardrail `[x]` — commit `d360ec0`

## Release B — Part 3 (Phase 1 product-page refresh) `[x]` SHIPPED

Ingredients-side cleanup. FitScore/cluster sync bundle (commit `a1d0783`) pushed to `origin/main` alongside; everything below is post-push.

- **FLTR-20** merge Active Ingredients + Form & Absorption `[x]` — commit `7e99854`
  Unified tier vocabulary on _SafetyTag (Excellent/Good/Fair/Poor at 12/8/4). FormAbsorptionSection sliver unmounted; widget file preserved.
- **FLTR-9** active-ingredient display order `[x]` — commit `de343bb`
  Two-bucket sort (disclosed → undisclosed) with pipeline order preserved inside each bucket. Pure `sortActivesForDisplay` helper in new `ingredient_sort.dart`. 7 tests.
- **FLTR-6** dedupe inactive ingredients `[x]` — commit `daed364`
  Real blobs repeat excipients; UI dedupes at the parse boundary via `dedupeInactivesForDisplay` (first occurrence wins, whitespace-tolerant, fallback name → standard_name → raw_source_text). 7 tests.

## Release C `[~]` DEFERRED

FLTR-3 (5-layer architecture), FLTR-7 (delete stale RDA file), FLTR-8 (warning grouping refinement), FLTR-15 (discontinued warning filter), FitScore empty-profile suppress, FLTR-SEARCH Phase 2.5.

## Release D — Goal-matching contract `[x]` PIPELINE SHIPPED · `[ ]` FLUTTER OPEN (2026-04-24)

### Pipeline (shipped — rebuild required to populate columns across the catalog)

- **E1.16 — Goal-matching contract v6.0.0** — `compute_goal_matches` rewritten; reads from real path `formulation_data.synergy_clusters`; honors `required_clusters` / `blocked_by_clusters` / `min_match_score`; score = max(score_full, score_required); 18 canonical Flutter goal IDs enforced; 3 legacy IDs renamed.
- **E1.17 — Cluster-ingredient alias map** — new `scripts/data/cluster_ingredient_aliases.json` (v1.0.0, 25 canonical entries). Recovers ~200 catalog products via parser-spelling normalization (CoQ10 ↔ coenzyme q10, DHA ↔ docosahexaenoic acid, iron ↔ ferrous bisglycinate, etc.).
- **E1.18 — Single-ingredient override** — 17 synergy clusters now opt-in to `allow_single_ingredient: true` + `primary_ingredients[]`. Magnesium-only earns sleep_stack, DHA-only earns prenatal, calcium-only earns bone_health. Dose adequacy still required; synergy SCORE bonus still requires ≥ 2 ingredients (single-ingredient is goal-matching only).
- **E1.19 — Enrichment cluster-match hardening** — ingredient dedup + min-dose inheritance + biochem abbreviation word-boundary matching + qty>0 gate. Eliminated trace-mineral false positives (Whey+ → Sleep) and DHA/EPA abbreviation misses.
- **E1.20 — Product-name fallback synthesizer** — strict 17-pattern allowlist injects synthetic actives for sparse-parse products (e.g. "DHA 1,000 mg Lemon Flavor"). Provenance-tagged. Scoring-isolated (does NOT mutate `activeIngredients`).

**DB columns affected:** `products_core.goal_matches` and `products_core.goal_match_confidence` will populate correctly for all 13,236 products on next pipeline rebuild. Schema unchanged (columns predate this work). No migration.

**Flutter bundle assets synced** (byte-identical to pipeline):
- `assets/reference_data/user_goals_to_clusters.json` (v6.0.0)
- `assets/reference_data/synergy_cluster.json` (v5.1.0)
- `assets/reference_data/cluster_ingredient_aliases.json` (v1.0.0; pipeline-only, bundled for completeness)

**Flutter fallback patched:**
- `lib/services/fit_score/e2a_goal_calculator.dart` — rewrote to use v6.0.0 fields (`required_clusters`, `blocked_by_clusters`, `min_match_score`) with full algorithm parity to pipeline's `compute_goal_matches`. The legacy `anti_clusters` lookup is removed.

**Flutter UI tickets — open:**
- **FLTR-21** — "Solo ingredient" badge on synergy cluster cards (consumes `synergy_detail.clusters[*].single_ingredient_match`)
- **FLTR-22** — "Inferred from label" disclosure for synthetic actives (consumes `display_ingredients[*].display_type == "inferred_from_name"`)

### Verification status

| Suite | Status |
|---|---|
| `test_compute_goal_matches.py` (17 tests) | ✅ all pass |
| `test_goal_mapping_integrity.py` (14 tests) | ✅ all pass |
| `test_cluster_ingredient_aliases.py` (8 governance tests) | ✅ all pass |
| `test_pipeline_integrity.py` (25 tests) | ✅ all pass |
| `test_scoring_snapshot_v1.py` (32 tests, 12 re-frozen) | ✅ all pass after Sprint E1.3.x re-freeze |
| `db_integrity_sanity_check.py` | ✅ 0 findings |
| Canary delta (24 products): goal-match rate | 21% → **58–67%** |

### Deployment order

```bash
# 1. Re-build final DB (compute_goal_matches now actually populates fields)
python3 scripts/build_final_db.py <scored_input> <output>

# 2. Sync to Supabase (no migration needed)
python3 scripts/sync_to_supabase.py <build_output>

# 3. Flutter catalog bundle refresh
#    (3 reference assets already byte-identical with pipeline; sync via the
#    standard E1.5.X-4 catalog refresh procedure)
```

### What Flutter does NOT need to change

- Goal-matching consumption (`fit_score_provider.dart`, `fit_score_service.dart`) — already correctly intersects `userGoals ∩ goalMatches` with confidence weighting. No code change needed.
- Drift schema (`products_core_table.dart`) — `goalMatches TEXT` and `goalMatchConfidence REAL` already mirror pipeline columns.
- Synergy detail render (`synergy_detail_section.dart`) — reads existing fields; new `single_ingredient_match` field is read-tolerant (defaults `false`).

---

# 11. ENGINEERING GUARDRAILS (working agreement)

1. **Think before coding** — state assumptions, surface tradeoffs, push back when warranted. No silent interpretations.
2. **Simplicity first** — minimum code that solves the problem. No abstractions for single-use code. If 200 lines could be 50, rewrite.
3. **Surgical changes** — touch only what the task requires. Don't "improve" adjacent code, comments, or formatting.
4. **Goal-driven execution** — define success criteria (tests or observable behavior) before implementing. Loop until verified.
5. **Pipeline is the source of truth** — the UI interprets; it does not reinterpret. The only exception is the explicit FLTR-11a guardrail.

---

# 12. FINAL PRINCIPLE

> If the UI contradicts safety, the user will trust the UI — not the system.

The backend is correct. This doc ensures the UI does not break that trust.

---
