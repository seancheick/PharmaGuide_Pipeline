# Flutter Handoff — `functional_roles[]` on inactive ingredients

**Status as of 2026-04-30 (commit `af45574`):** field is wired through the pipeline and shipping in the blob, populated as `[]` for now. Backfill batches (Phase 3) will fill it in incrementally over the next few weeks.

---

## What's new in the blob

Every row inside `inactive_ingredients[]` in the Flutter export blob now carries one new field — and one old field is gone:

| | Before | After (commit `af45574`) |
|---|---|---|
| Added | — | `functional_roles: string[]` |
| Removed | `additive_type: string` | *(dropped — replaced by `functional_roles`)* |
| Unchanged | `name`, `category`, `is_additive`, `is_harmful`, `notes`, `common_uses`, `identifiers`, `severity_level`, `population_warnings`, `harmful_severity`, `harmful_notes`, `mechanism_of_harm` | same |

**Example row going forward:**

```jsonc
{
  "name": "Magnesium Stearate",
  "raw_source_text": "Magnesium Stearate",
  "category": "lubricant",
  "is_additive": true,
  "is_harmful": false,
  "functional_roles": ["lubricant", "anti_caking_agent"],   // NEW (multi-valued)
  "notes": "...",
  "common_uses": ["..."],
  "identifiers": {"unii": "70097M6I30", "cas": "557-04-0"}
}
```

**`functional_roles` will be `[]` for most rows in the next few pipeline runs** while we backfill. Don't error on empty arrays — render no chips for that row.

---

## How to render

**Step 1 — Bundle the vocab as a static asset (one-time setup).**

Copy `scripts/data/functional_roles_vocab.json` from the pipeline repo into the Flutter app under `assets/data/functional_roles_vocab.json` (or wherever you keep bundled JSON), and register it in `pubspec.yaml`. It's ~13 KB, 32 entries, locked at v1.0.0. Vocab updates are rare (regulatory taxonomy is stable) and ship via app release.

**Step 2 — Load once at app boot, cache for the session.**

```dart
final vocab = jsonDecode(await rootBundle.loadString(
    'assets/data/functional_roles_vocab.json'));
final byId = { for (var r in vocab['functional_roles']) r['id']: r };
// Cache `byId` in the model layer; it's read-only.
```

**Step 3 — Render chips per ingredient.**

```dart
for (final roleId in inactive['functional_roles']) {
  final role = byId[roleId];
  if (role == null) continue;        // unknown id → skip silently
  Chip(label: Text(role['name']))
}
```

**Step 4 — Tap modal shows the user-facing detail.**

Each role entry has exactly five fields; everything you need to render is in the vocab:

```jsonc
{
  "id": "lubricant",                                                 // stable, never shown to user
  "name": "Lubricant",                                               // chip label
  "notes": "Keeps powder from sticking to the tablet press during manufacturing. Used in trace amounts.",  // ≤200 char user-facing description (modal body)
  "regulatory_references": [
    {"jurisdiction": "FDA", "code": "21 CFR 170.3(o)(18)"}           // tappable "Learn more" link
  ],
  "examples": ["magnesium stearate", "stearic acid", "calcium stearate"]  // 1-5 ingredient names users might recognize
}
```

Modal layout suggestion:
- **Title:** `role.name`
- **Body:** `role.notes` (already char-capped at 200 — no need to truncate)
- **"Common examples":** chip list from `role.examples`
- **"Learn more":** tap-out links rendered from `role.regulatory_references` (e.g. `21 CFR 170.3(o)(18) →` deep-links to the eCFR page; EU codes link to `https://eur-lex.europa.eu`)

**Critical UX rule from the clinician:** show `name` + `notes` verbatim. Don't paraphrase, don't strip, don't auto-translate jargon — every line was reviewed for clinical accuracy and consumer framing (e.g., preservative says "*helps reduce* the growth," not "stops"; sugar alcohols mention bloating; artificial colorants say "Some users prefer to avoid these"). Reword and you reintroduce the bugs the clinician closed.

---

## Behavior over the next few weeks

We're populating `functional_roles[]` in **22 backfill batches**, ~40 entries each:
- 3 batches for `harmful_additives.json` (115 entries, B0/B1 safety penalty data)
- 17 batches for `other_ingredients.json` (673 entries, the bulk of inactive ingredients)
- 2 batches for `botanical_ingredients.json` (459 entries, mostly actives but some carry colorant/flavor roles)

Per-batch posture:
- Each batch lands as an atomic commit with regression tests pinning specific entries
- Pipeline reruns produce updated blobs with progressively more populated `functional_roles[]`
- Empty arrays stay `[]` — they never become `null` or get dropped

**Coverage milestones to expect:**

| Batch range | Ingredient | Coverage after |
|---|---|---|
| Batch 1 | harmful_additives 1-40 (most-common excipients) | ~35% of harmful_additives populated |
| Batch 4-7 | other_ingredients top 200 (oil_carrier, flavor_natural, emulsifier, sweetener_natural, colorant_natural — the daily drivers) | ~30% of other_ingredients populated, ~80% of *frequently-seen* ingredients populated |
| Batch 18 | All 3 files at ~95% coverage | most rendering edge cases gone |
| Phase 5 final gate | 100% | release allowed |

You'll see chip coverage grow from ~0% → ~80% within the first ~10 batches because the most-common excipients (magnesium stearate, microcrystalline cellulose, silicon dioxide, gelatin, hypromellose) are in the early batches. The long tail (rare branded complexes, single-occurrence categories) lands later.

---

## What's NOT changing

- `notes` field per ingredient row stays — it's the ingredient-specific note, distinct from the role's vocab `notes`. Don't conflate them.
- `category` field per ingredient row stays — it'll be canonicalized in Phase 4 cleanup but the field name and shape don't change.
- `is_harmful`, `severity_level`, `harmful_notes`, `mechanism_of_harm`, `population_warnings` — all the safety surfacing stays as it was.
- Allergen, banned, and warning rendering — all unchanged.

---

## Phase 4 heads-up (~4-6 weeks out)

After backfill is done, a follow-up cleanup will:

- **Drop `additive_type` from the source data files entirely** (already gone from the blob since this commit, so no Flutter impact)
- Canonicalize the per-row `category` enum (collapse 241 values → ~30 — this is *purely* server-side cleanup; the field name and value type stay the same)
- Move some entries currently in `other_ingredients.json` to the active-ingredient pipeline (branded complexes like BioCell Collagen, animal glandular tissue, Black Pepper Extract). Those rows will start appearing in `ingredients[]` instead of `inactive_ingredients[]`.

Heads up but no Flutter code changes required — the schemas Flutter reads stay stable.

---

## Phase V1.1 (post-V1 ship, separate spec)

A second non-blocking layer planned post-launch:

- **`attributes` object per ingredient row** — `is_branded_complex`, `caramel_class` (i/ii/iii/iv for 4-MEI), `e171_eu_concern`, `is_animal_derived`, `source_origin` (plant/animal/mineral/microbial/synthetic). Powers filter UX ("show me products without artificial colorants") and per-chip deeper-dive screens with safety context.
- **Per-chip deeper-dive screens** — each chip's neutral V1 definition gets a tap-through to a longer screen with FODMAP/IBS detail (sugar alcohols), EU-vs-FDA divergence (E171/TiO2), Class III/IV 4-MEI for caramel, magnesium stearate consumer-advocacy debate, etc.

That's a separate spec when V1 ships — flag if your team wants to start UX-prototyping the deeper-dive screens in parallel.

---

## Quick reference

| Asset | Path | Purpose |
|---|---|---|
| Vocab (LOCKED) | `scripts/data/functional_roles_vocab.json` | Bundle as Flutter asset; 32 roles, ~13 KB |
| Per-row field | `inactive_ingredients[].functional_roles: string[]` | Multi-valued; `[]` when not yet backfilled |
| Source of truth doc | `scripts/audits/functional_roles/CLINICIAN_REVIEW.md` | Clinician-signed locked decisions |
| Schema doc | `scripts/DATABASE_SCHEMA.md` § 13b | Vocab field contract |
| Implementation plan | `~/.claude/plans/golden-painting-umbrella.md` | Five-phase plan, V1.1 attributes spec |

Questions: ping the pipeline team. Ready when you are to integrate.
