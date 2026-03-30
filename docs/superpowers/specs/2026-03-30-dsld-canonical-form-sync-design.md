# DSLD Canonical-By-Form Sync Design

Date: 2026-03-30
Owner: Sean Cheick Baradji
Status: Drafted for implementation

## Goal

Create a long-lived DSLD API sync model that stays accurate and easy to operate as the dataset grows over years.

The design must support:

- canonical raw storage that does not become messy over time
- targeted brand pulls
- targeted form/category pulls such as gummies, softgels, capsules, and powders
- new-only and changed-only syncs
- explicit market-status filtering:
  - `0` off market
  - `1` on market
  - `2` all
- continued downstream compatibility with the existing pipeline:

```text
raw DSLD label files
  -> clean_dsld_data.py
  -> enrich_supplements_v3.py
  -> score_supplements.py
  -> build_final_db.py / build_all_final_dbs.py
  -> sync_to_supabase.py
```

## Design Decision

The canonical raw corpus should be organized by supplement form, not by brand and not as one giant mixed folder.

This is the best long-term operating model because:

- there are far fewer forms than brands
- the corpus stays easier to browse and maintain
- broad discovery is naturally form-oriented
- brand pulls remain possible without creating hundreds of long-lived brand-owned corpora
- overlap between brand pulls and form pulls is expected and can be resolved centrally by `dsld_id`

Brand, ingredient, and date-window pulls should be treated as discovery and update methods, not as separate permanent sources of truth.

## Core Identity Rule

`dsld_id` is the only product identity key for raw-label sync.

Everything else is metadata:

- `brandName`
- `productVersionCode`
- `offMarket`
- `entryDate`
- `productType`
- `physicalState`

If a product is found through multiple pulls:

- form pull
- brand pull
- ingredient pull
- date-window pull

it is still one product if the `dsld_id` matches.

## Canonical Storage Model

Canonical raw storage should live under form-based directories:

```text
raw_data/forms/gummies/*.json
raw_data/forms/softgels/*.json
raw_data/forms/capsules/*.json
raw_data/forms/bars/*.json
raw_data/forms/powders/*.json
raw_data/forms/lozenges/*.json
raw_data/forms/tablets-pills/*.json
raw_data/forms/liquids/*.json
raw_data/forms/other/*.json
```

Each file remains:

```text
<dsld_id>.json
```

Examples:

```text
raw_data/forms/gummies/13418.json
raw_data/forms/softgels/241695.json
```

The adapter contract from the existing DSLD raw adapter spec still applies:

- one label per file
- canonical raw JSON shape
- `_source` provenance field allowed
- lowercase `otheringredients`

## Form Routing

Each fetched label must be routed into exactly one canonical form bucket.

Routing should use a deterministic precedence order derived from the DSLD label payload:

1. explicit `physicalState.langualCode` matched through the repo-owned form-code table
2. explicit `physicalState.langualCodeDescription` matched through repo-owned form-name heuristics
3. explicit `productType` only when the repo defines a safe product-type-to-form mapping
4. known DSLD `supplement_form` filter used to fetch the label
5. fallback bucket: `other`

Canonical bucket names should be stable repo-owned names, not raw API codes:

- `gummies`
- `softgels`
- `capsules`
- `bars`
- `powders`
- `lozenges`
- `tablets-pills`
- `liquids`
- `other`

The sync state should remember the assigned canonical form bucket for each `dsld_id`.

Important:

- brand pulls must not depend on the originating filter context to route correctly
- routing must be derivable from the label payload itself whenever possible
- the filter context is only a fallback when the label payload is incomplete or ambiguous

## Discovery Lanes

The sync tool should support multiple discovery lanes:

### Brand discovery

Examples:

```bash
sync-brand --brand "Thorne"
sync-brand --brand "Nordic Naturals"
sync-brand --brand "Pure Encapsulations"
```

Purpose:

- targeted brand refresh
- focused raw review
- brand-specific catch-up

### Form discovery

Examples:

```bash
sync-filter --supplement-form e0176
sync-filter --supplement-form e0161
sync-filter --supplement-form e0159
sync-filter --supplement-form e0162
```

Purpose:

- broad collection by stable category
- easier long-term maintenance than brand-owned corpora

### Ingredient discovery

Examples:

```bash
sync-filter --ingredient-name melatonin
sync-filter --ingredient-name berberine
sync-filter --ingredient-category botanical
```

Purpose:

- evidence gathering for ingredient-map expansion
- finding high-value products containing specific actives or additive classes

### Date-window discovery

Examples:

```bash
sync-filter --date-start 2026-01-01 --date-end 2026-03-30
```

Purpose:

- newly added labels
- coarse recent-ingest windows

Important:

- date windows are good for newly added labels
- they are not a complete substitute for change detection on existing labels

## Market Status Handling

The sync workflow must expose DSLD market-status options directly:

- `0` off market
- `1` on market
- `2` all

Recommended CLI behavior:

```bash
--status 0
--status 1
--status 2
```

Recommended default:

- `--status 2`

Reason:

- the product corpus should preserve both active and off-market labels
- the app needs off-market visibility when users scan discontinued products they still own

## Off-Market Product Policy

Off-market products should remain in the canonical raw corpus and continue through:

- cleaning
- enrichment
- scoring
- final DB build
- app distribution

They should not be deleted from the corpus merely because they are off market.

Off-market should be treated as product state, not product invalidation.

This preserves:

- scan coverage for discontinued products
- warning visibility in the app
- historical continuity
- auditability of past products

The only place off-market may be excluded is optional active-only discovery or merchandising views.

## Shared Global State

All sync methods must use one shared global state file keyed by `dsld_id`.

Each record should track at minimum:

- `id`
- `brand_name`
- `product_version_code`
- `off_market`
- `entry_date`
- `canonical_form`
- `payload_sha256`
- `last_seen_at`
- `last_sync_source`

`payload_sha256` must be computed from the canonical raw DSLD label payload only:

- include the normalized DSLD label fields that are written to the raw file contract
- exclude adapter-only metadata fields such as `_source`
- exclude sync bookkeeping fields from the state file
- serialize with stable sorted keys before hashing

This prevents no-op syncs from looking changed merely because adapter metadata or sync context changed.

Recommended additional fields:

- `current_raw_path`
- `first_seen_at`
- `last_status_filter`
- `last_query_context`

## Delta Sync Rules

The workflow should support changed-only and new-only sync behavior.

### New label

A label is new if:

- `dsld_id` is not present in the state file

### Changed label

A label is changed if any of these differ from state:

- `productVersionCode`
- `offMarket`
- canonical payload hash
- canonical form bucket assignment

### Seen but unchanged label

If the label is discovered again and the tracked state is unchanged:

- do not rewrite unnecessarily unless explicitly forced

### Missing from a pull

If a label is absent from a specific discovery run:

- do not delete it from canonical storage automatically
- absence from one pull is not proof of invalidity

This matters especially for:

- brand search inconsistencies
- form overlap
- API index lag

## Duplicate and Overlap Rules

Overlap is expected. For example:

- a softgel may also belong to a brand pull
- a gummy may appear in an ingredient pull for melatonin
- a product may appear in a date-window pull and a form pull

Required behavior:

1. dedupe by `dsld_id`
2. maintain one canonical stored raw file for that `dsld_id`
3. update the state record with the latest verified metadata
4. do not create multiple canonical copies of the same label across different permanent corpora

Working sets and reports may show the same `dsld_id` as discovered from multiple lanes, but canonical storage must not multiply it.

## Staging vs Canonical

The system should support staging output for investigation and temporary working sets, but staging should not be the default long-term truth.

Recommended directories:

```text
raw_data/forms/...                 # canonical
raw_data/staging/forms/...         # optional temporary pulls
raw_data/staging/ingredients/...   # optional temporary pulls
raw_data/staging/date_windows/...  # optional temporary pulls
```

Default recommended behavior:

- normal sync commands update canonical form folders
- optional `--snapshot` or `--staging-dir` creates separate temporary copies

## Recommended CLI Surface

Keep current commands:

- `probe`
- `sync-brand`
- `refresh-ids`
- `verify-db`
- `check-version`

Add:

- `sync-filter`
- `sync-delta`

### `sync-filter`

Should support combinations of:

- `--supplement-form`
- `--ingredient-name`
- `--ingredient-category`
- `--brand`
- `--status`
- `--date-start`
- `--date-end`
- `--limit`
- `--snapshot`
- `--staging-dir`
- `--canonical-root`
- `--state-file`

### `sync-delta`

Should support:

- `--supplement-form`
- `--brand`
- `--ingredient-name`
- `--ingredient-category`
- `--status`
- `--date-start`
- `--date-end`
- `--canonical-root`
- `--state-file`
- `--delta-output-dir`
- `--force-refetch`

Behavior:

- discover candidate IDs
- compare to state
- fetch only new or changed labels
- update canonical form folders
- write delta copies for downstream incremental pipeline runs when requested

Explicit `--delta-output-dir` behavior:

- if `--delta-output-dir` is provided:
  - write the changed/new labels into that directory as a flat, cleaner-ready delta set
  - this directory is intended to feed incremental clean -> enrich -> score runs
- if `--delta-output-dir` is omitted:
  - update canonical form folders and the shared state only
  - do not claim that a pipeline-ready delta artifact was produced

This distinction must be documented clearly in operator-facing docs and command help.

## Ingredient-Map Expansion Workflow

The DSLD API should support targeted pulls that help improve the ingredient databases.

Recommended usage:

1. run cleaning on a canonical or staged raw set
2. inspect:
   - `unmapped_active_ingredients.json`
   - `needs_verification_active_ingredients.json`
   - inactive equivalents as needed
3. choose high-occurrence unmapped entries
4. run ingredient-based DSLD pulls for those terms
5. inspect real label spellings and forms
6. add vetted canonical entries and aliases to:
   - `scripts/data/ingredient_quality_map.json`
   - other reference DBs when applicable
7. rerun cleaning and confirm unmapped counts drop

The API helps evidence gathering and alias validation. It should not auto-promote unmapped ingredients into reference databases without review.

## Recommended Form Codes

The implementation should maintain a repo-owned mapping for at least these commonly used DSLD supplement-form codes:

- `e0176` -> `gummies`
- `e0161` -> `softgels`
- `e0159` -> `capsules`
- `e0164` -> `bars`
- `e0162` -> `powders`
- `e0174` -> `lozenges`
- `e0155` -> `tablets-pills`
- `e0165` -> `liquids`
- `e0172` -> `other`
- `e0177` -> `other`

These should appear in operator-facing docs so form pulls are easy to run consistently.

The `other` mappings for `e0172` and `e0177` are intentional:

- `e0172` covers forms that do not belong in the stable major buckets
- `e0177` represents unknown form state

They should not be treated as unmapped routing errors.

## README Requirements

The operations README should be updated after implementation with:

- canonical-by-form folder layout
- `status 0/1/2` explanation
- form code table
- example brand sync commands
- example form sync commands
- example new-only / delta sync commands
- duplicate-handling explanation
- off-market retention policy
- ingredient-discovery examples

## Recommendation

Implement the DSLD sync system as:

1. canonical raw storage by form
2. shared global state keyed by `dsld_id`
3. brand, ingredient, date, and form pulls as discovery/update lanes
4. explicit market-status filtering with `0/1/2`
5. delta sync based on state comparison
6. off-market retention as a first-class rule

This is the most maintainable and accurate long-term operating model for the project.
