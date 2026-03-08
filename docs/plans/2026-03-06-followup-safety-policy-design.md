# Follow-Up Safety Policy Design

**Goal:** Extend the pipeline with safer banned-substance modeling, user-friendly magnesium handling, and stable goal-to-cluster mappings without breaking existing enrichment or scoring consumers.

**Scope:** DMSA canonicalization, magnesium UL scoring policy, additional banned substances, iodine evidence alignment, and `user_goals_to_clusters` migration to stable IDs with UI-friendly labels.

## Recommended Approach

Use a compatibility-first migration:

- Keep medically accurate nutrient data. Do not alter the magnesium UL.
- Change only scoring and user-facing messaging for magnesium so supplemental magnesium above UL is treated as a caution path rather than a generic excessive/toxic path.
- Canonicalize DMSA into one banned entity and dedupe banned matches by canonical identity so row duplication cannot inflate results.
- Add missing banned substances using conservative aliases and source-backed notes.
- Migrate `user_goals_to_clusters` to stable cluster IDs while preserving current human-readable labels for app display.

This minimizes breakage because:

- Existing callers still receive `over_ul` for magnesium.
- Existing UI can still show friendly cluster names.
- Existing banned-substance scoring does not need a new concept beyond canonical dedupe.

## Alternatives Considered

### 1. Raise magnesium UL in the data

Rejected. It would diverge from NIH/IOM guidance and hide a real supplement-specific caution behind altered reference data.

### 2. Leave DMSA as duplicate rows and patch scoring only

Rejected. It keeps the enrichment payload internally inconsistent and makes downstream reasoning harder.

### 3. Fully refactor goal mapping to IDs only in one step

Rejected. It risks breaking current user-facing consumers that may expect label strings.

## Design

### DMSA Canonicalization

- Replace split DMSA dosage rows with one canonical banned entry.
- Preserve dosage examples in notes/aliases instead of separate IDs.
- Add a banned-match dedupe pass keyed by canonical identity so future overlap mistakes do not duplicate hits.

### Magnesium Scoring Policy

- Keep `over_ul=true` and the true UL in adequacy results.
- Add a magnesium-specific note explaining that the UL applies to supplemental magnesium and may sit below the RDA.
- Change scoring/point recommendation so magnesium above the supplemental UL is treated as cautionary instead of automatically mapping to the harshest generic band.

### Missing Banned Substances

Add:

- Yellow oleander / Thevetia peruviana / Nuez de la India substitution
- 2,4-Dinitrophenol (DNP)
- Usnic acid
- Aconite / aconitum / aconitine
- Clenbuterol

Use conservative aliases, negative terms only where precision requires them, and include source-backed regulatory/clinical rationale in the entry notes.

### Iodine Evidence

- Keep iodine as human-evidence-backed.
- Align `published_studies` and `study_type` with actual adult RCT/public-health intervention evidence rather than downgrading it to a weaker label.

### Goal Mapping Migration

- Update `user_goals_to_clusters.json` so primary/secondary mappings point to stable `cluster_id`s.
- Add display labels alongside IDs where useful for app/phone rendering.
- Add compatibility resolution that accepts legacy annotated labels during migration.

## Error Handling

- All migration logic should be additive or backward-compatible.
- Legacy goal labels should resolve to cluster IDs rather than fail closed.
- Banned-match dedupe must preserve the strongest evidence payload when duplicates collide.

## Testing Strategy

- Failing regression for DMSA single-hit behavior.
- Failing regression for magnesium “caution not toxic-overdose” scoring behavior while preserving `over_ul`.
- Failing regression for the newly added banned substances.
- Failing regression for iodine evidence alignment.
- Failing regression for goal mappings resolving by ID and legacy label.

## Approval State

Approved in-thread on 2026-03-06.
