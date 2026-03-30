# DSLD API Raw Adapter Contract Design

Date: 2026-03-29
Owner: Sean Cheick Baradji
Status: Drafted for implementation

## Goal

Add DSLD API ingestion without creating a second raw-data format or a second downstream pipeline.

Both of these input modes must remain valid:

- manual JSON downloads
- API-fetched labels

Both must feed the same existing pipeline unchanged:

```text
raw DSLD label files
  -> clean_dsld_data.py
  -> enrich_supplements_v3.py
  -> score_supplements.py
  -> build_final_db.py / build_all_final_dbs.py
  -> sync_to_supabase.py
```

The API adapter is therefore an input compatibility layer, not a pipeline rewrite.

## Observed Current Contract

The current clean stage and batch loader define a simpler compatibility contract than the broader DSLD label model:

- `scripts/batch_processor.py` loads flat `*.json` files from one directory level only
- validation requires:
  - `id`
  - at least one of:
    - `ingredientRows`
    - `otherIngredients`
    - `otheringredients`
- current real raw files already use lowercase `otheringredients`

Observed sample raw file:

- `/Users/seancheick/Documents/DataSetDsld/Hum-2-17-26-L23/241695.json`

Observed top-level keys in that real file:

- `id`
- `fullName`
- `brandName`
- `productVersionCode`
- `entryDate`
- `offMarket`
- `ingredientRows`
- `otheringredients`
- `claims`
- `events`
- `statements`
- `servingSizes`
- `targetGroups`
- `productType`
- `physicalState`
- `contacts`
- `upcSku`
- plus other DSLD label metadata

This means the adapter does not need to invent a new raw schema. It needs to preserve the existing one.

## Design Decision

The canonical raw input contract remains the current downloaded-label JSON shape already accepted by the cleaner.

API ingestion must write files that are structurally equivalent to the current manual raw files before they are persisted to disk.

Downstream stages must not need to know whether the source was:

- manual download
- API sync

If the live DSLD API returns a slightly different representation, that normalization must happen in the adapter before file write.

## Raw File Contract

Each persisted raw file must represent one DSLD label and must be written as a single JSON object.

### Required compatibility rules

1. Preserve the product identifier as top-level `id`.
2. Preserve the current top-level key naming used by the existing raw files whenever possible.
3. Preserve lowercase `otheringredients` as the canonical stored key.
4. Preserve nested lists and objects in DSLD label form rather than flattening them.
5. Record ingest provenance as top-level `_source` with value:
   - `manual`
   - `api`
6. Preserve known keys even when empty or null if the manual raw export normally includes them.
7. Do not reduce the stored payload to only the fields currently used by the cleaner. Keep the broader label payload for future verification and reprocessing.

### Minimum persisted fields

At minimum, each stored file must include:

- `id`
- `fullName`
- `brandName`
- `productVersionCode`
- `entryDate`
- `offMarket`
- `ingredientRows` or `otheringredients`
- `claims`
- `events`
- `statements`
- `servingSizes`
- `targetGroups`
- `productType`
- `upcSku`

This is not the full preferred payload. It is the minimum compatibility floor.

### Canonical stored spelling

Use these exact stored keys when present:

- `ingredientRows`
- `otheringredients`
- `fullName`
- `brandName`
- `productVersionCode`
- `upcSku`

Do not write a second variant solely for stylistic reasons.

### Provenance field

The adapter should add:

```text
_source
```

Allowed values:

- `manual`
- `api`

Purpose:

- preserve ingest provenance for later verification and debugging
- allow future tooling to distinguish stored raw sources without changing downstream pipeline behavior

Constraint:

- `_source` is adapter metadata, not part of DSLD schema parity
- parity checks must explicitly ignore `_source`

## Filename Convention

Persist each label as:

```text
<dsld_id>.json
```

Example:

```text
241695.json
```

Rationale:

- this matches the current manually downloaded raw data
- the batch loader only cares about `*.json`
- stable ID-based filenames simplify refresh, overwrite, verification, and diffing

The adapter should overwrite the same `<id>.json` file on refresh unless the operator explicitly asks for snapshot/versioned storage.

### Snapshot mode

Snapshot mode should be a CLI flag:

```text
--snapshot
```

Default behavior:

- `sync-brand`
- `refresh-ids`
- `sync-query`
  overwrite `<id>.json` in the target directory

Snapshot behavior:

- persist fetched labels to a separate operator-specified directory
- never overwrite canonical raw files in place

Required rule:

- `verify-db` must always use snapshot-style fetch behavior
- `verify-db` must not overwrite canonical raw label files
- `verify-db` should fetch into a temporary or dedicated verification directory, diff, then report

## Directory Layout

Each sync target should write into one flat directory containing only raw label JSON files.

Valid examples:

```text
raw_data/Nordic-Naturals-2026-03-29/*.json
raw_data/query-vitamin-d-2026-03-29/*.json
raw_data/refresh-ids-2026-03-29/*.json
```

Invalid example for the current cleaner contract:

```text
raw_data/Nordic/2026/03/*.json
```

Rationale:

- `batch_processor.py` does not recursively scan nested directories
- a flat directory keeps the current cleaner contract unchanged

## API-to-Raw Adapter Rules

If API responses differ from the current manual raw files, the adapter must normalize before write.

### Required adapter behavior

1. If the API response is wrapped:
   - unwrap to the label object before persisting
2. If the API omits lowercase `otheringredients` but provides an equivalent field:
   - map it to stored `otheringredients`
3. If the API returns additional metadata:
   - keep it unless it breaks compatibility or is obviously request-envelope noise
4. If the API omits fields present in manual raw files:
   - preserve the field with `null` or empty structure when that keeps parity and avoids downstream ambiguity
5. If the API response contains transport-specific envelope keys:
   - do not persist them unless they are part of the label record itself

### Explicit non-goals

The adapter must not:

- write a second raw schema optimized for the cleaner
- flatten ingredient structures
- rename keys to a new style
- split one label across multiple files
- make enrichment-specific decisions at raw-write time

## Probe and Parity Check

Before depending on API ingestion operationally, the first implementation task must be a probe that compares:

- one known-good manual raw file
- one API-fetched label for the same DSLD ID

The probe should verify:

1. same top-level product ID
2. all required top-level keys present after adapter normalization
3. same nested shape for:
   - `ingredientRows`
   - `otheringredients`
   - `claims`
   - `events`
   - `statements`
   - `servingSizes`
4. no unexpected missing required keys after adapter normalization
5. no missing fields that the cleaner or later verification flow depends on
6. transport envelope removed correctly

If parity is not exact enough, the adapter must transform the API payload before save until parity is achieved.

### Concrete parity gate

The probe must be implemented as a pass/fail structural comparison, not a manual eyeball check.

Recommended baseline:

- accept a probe reference path via CLI:
  - `--reference-file <path>`
- choose one known manual file such as:
  - `/Users/seancheick/Documents/DataSetDsld/Hum-2-17-26-L23/241695.json`
- fetch the same DSLD ID from the API
- normalize the API payload into adapter output form
- compare:
  - required top-level key presence
  - JSON value types for top-level keys
  - nested key sets and JSON value types for:
    - `ingredientRows[*]`
    - `otheringredients`
    - `otheringredients.ingredients[*]`
    - `claims[*]`
    - `events[*]`
    - `statements[*]`
    - `servingSizes[*]`

Allowed exclusions:

- `_source`
- other explicitly documented adapter-only metadata fields if added later

Allowed additions:

- API-only fields not present in older manual raw files are allowed
- such fields should be preserved unless they are transport-envelope noise
- these extra fields must not cause the parity gate to fail by themselves

Pass condition:

- all required keys present after normalization
- no unexpected missing required keys
- no unexpected type differences on required compared structures
- zero unexpected type differences
- zero missing required nested structures

Fail condition:

- any missing required key after normalization
- any nested type drift in required structures
- any missing required structure after normalization

## Source Modes

The raw layer should support two source modes:

- manual source mode
- API source mode

Both source modes must end in the same persisted raw-file contract on disk.

This means:

- the operator can continue using manual downloads whenever desired
- the operator can also fetch via API for targeted syncs, refreshes, and verification
- all later pipeline stages remain source-agnostic

## Recommended Commands

The future API sync CLI should operate on top of this contract.

Recommended early commands:

- `probe`
- `sync-brand`
- `refresh-ids`
- `verify-db`
- `sync-query`
- `check-version`

Every command that persists raw files must emit the same on-disk contract described here.

## Risks

### Runtime API response shape is still unverified from the operator machine

In a separate environment, requests to the DSLD host returned Swagger HTML instead of the expected JSON payload. That means the first live step must still be a real authenticated probe from the operator machine using the configured API key.

### Silent format drift is the main failure mode

The dangerous outcome is not a loud crash. It is writing API payloads that look close enough to work but drift structurally from the manual raw files and later create silent cleaning or verification inconsistencies.

The adapter should therefore fail fast when required parity checks do not pass.

## Recommendation

Implement the API path as:

1. `dsld_api_client.py`
2. `dsld_api_sync.py`
3. probe/parity check against one known manual raw file
4. persist API-fetched labels using this raw adapter contract
5. run the unchanged existing pipeline afterward

This keeps manual downloads available, adds API-powered discovery and refresh, and avoids downstream pipeline branching.
