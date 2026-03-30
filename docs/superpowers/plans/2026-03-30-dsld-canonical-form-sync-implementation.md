# DSLD Canonical-By-Form Sync Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add canonical-by-form DSLD sync workflows with shared state, filtered pulls, and delta sync without breaking the existing raw-label contract or pipeline.

**Architecture:** Extend `scripts/dsld_api_client.py` with general DSLD search/filter helpers and form-code metadata. Extend `scripts/dsld_api_sync.py` with canonical form routing, shared state management, `sync-filter`, and `sync-delta`, while preserving current `sync-brand`, `refresh-ids`, `verify-db`, and `probe` behavior. Keep persistence compatible with existing raw DSLD files and update the operations README with the new operating model.

**Tech Stack:** Python 3, `requests`, `argparse`, `hashlib`, JSON state files, pytest.

---

## File Structure

- Modify: `scripts/dsld_api_client.py`
  - add generic DSLD filter search wrapper
  - add common supplement-form code mapping
- Modify: `scripts/dsld_api_sync.py`
  - add canonical form routing helpers
  - add shared state file helpers
  - add `sync-filter` and `sync-delta`
  - optionally allow existing sync flows to reuse canonical routing/state logic
- Modify: `scripts/tests/test_dsld_api_client.py`
  - cover new client helpers/constants
- Modify: `scripts/tests/test_dsld_api_sync.py`
  - cover routing, hashing, state comparison, parser support, and delta behavior
- Modify: `scripts/PIPELINE_OPERATIONS_README.md`
  - document canonical-by-form workflow, status handling, form codes, and delta commands

## Task 1: Add failing sync tests first

**Files:**
- Modify: `scripts/tests/test_dsld_api_sync.py`

- [ ] **Step 1: Add failing tests for canonical payload hashing**

Test:
- same DSLD payload with different `_source` values hashes identically
- sorted-key serialization is stable

- [ ] **Step 2: Add failing tests for form routing**

Test:
- `physicalState.langualCode == E0176` routes to `gummies`
- `physicalState.langualCode == E0161` routes to `softgels`
- `E0172` and `E0177` route to `other`
- missing payload form data falls back to supplied filter code

- [ ] **Step 3: Add failing tests for state diff classification**

Test:
- unseen label => `new`
- changed `productVersionCode` => `changed`
- changed `offMarket` => `changed`
- changed canonical payload hash => `changed`
- unchanged label => `unchanged`

- [ ] **Step 4: Add failing parser tests**

Test:
- `sync-filter` parses `--supplement-form`, `--status`, `--canonical-root`, `--state-file`
- `sync-delta` parses `--delta-output-dir`

- [ ] **Step 5: Run targeted tests to confirm failure**

Run:
```bash
pytest scripts/tests/test_dsld_api_sync.py -q
```

Expected:
- FAIL on missing helpers/subcommands

## Task 2: Extend the DSLD API client

**Files:**
- Modify: `scripts/dsld_api_client.py`
- Modify: `scripts/tests/test_dsld_api_client.py`

- [ ] **Step 1: Add supplement form code metadata**

Implement repo-owned mapping for:
- `e0176`
- `e0161`
- `e0159`
- `e0162`
- `e0155`
- `e0165`
- `e0172`
- `e0177`

- [ ] **Step 2: Add generic `search_filter(...)` wrapper**

Implement:
- pass-through filter params
- drop `None` values
- keep explicit `status`

- [ ] **Step 3: Add client tests for filter wrapper/constants**

Test:
- `search_filter` forwards params correctly
- form code mapping constants are present

- [ ] **Step 4: Run targeted client tests**

Run:
```bash
pytest scripts/tests/test_dsld_api_client.py -q
```

Expected:
- PASS

## Task 3: Implement canonical routing and shared state

**Files:**
- Modify: `scripts/dsld_api_sync.py`
- Modify: `scripts/tests/test_dsld_api_sync.py`

- [ ] **Step 1: Add canonical payload hashing helper**

Implement helper that:
- hashes canonical raw label fields only
- excludes `_source`
- uses sorted-key JSON serialization

- [ ] **Step 2: Add form routing helper**

Implement helper that:
- routes from `physicalState.langualCode`
- then `physicalState.langualCodeDescription`
- then optional filter code fallback
- finally `other`

- [ ] **Step 3: Add state-file load/save helpers**

Implement:
- load missing file as empty state
- persist sorted JSON

- [ ] **Step 4: Add state classification helper**

Implement classification:
- `new`
- `changed`
- `unchanged`

- [ ] **Step 5: Run sync tests**

Run:
```bash
pytest scripts/tests/test_dsld_api_sync.py -q
```

Expected:
- PASS on routing/state/hash tests

## Task 4: Add `sync-filter`

**Files:**
- Modify: `scripts/dsld_api_sync.py`
- Modify: `scripts/tests/test_dsld_api_sync.py`

- [ ] **Step 1: Add CLI subparser**

Support:
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

- [ ] **Step 2: Add sync handler**

Behavior:
- discover IDs through `search_filter`
- fetch labels
- route to canonical form bucket when `--canonical-root` is provided
- otherwise require `--output-dir` or `--staging-dir`
- update state when `--state-file` is provided

- [ ] **Step 3: Add tests for non-network handler paths**

Test:
- handler writes routed files into canonical form directories
- state file updates

- [ ] **Step 4: Run targeted sync tests**

Run:
```bash
pytest scripts/tests/test_dsld_api_sync.py -q
```

Expected:
- PASS

## Task 5: Add `sync-delta`

**Files:**
- Modify: `scripts/dsld_api_sync.py`
- Modify: `scripts/tests/test_dsld_api_sync.py`

- [ ] **Step 1: Add CLI subparser**

Support:
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

- [ ] **Step 2: Add delta handler**

Behavior:
- discover candidate IDs
- fetch only new/changed labels unless forced
- always update canonical/state
- write flat delta set only when `--delta-output-dir` is provided

- [ ] **Step 3: Add tests**

Test:
- unchanged labels are skipped
- changed labels update canonical files
- delta dir contains only changed/new labels
- omitted `--delta-output-dir` does not create delta output

- [ ] **Step 4: Run targeted sync tests**

Run:
```bash
pytest scripts/tests/test_dsld_api_sync.py -q
```

Expected:
- PASS

## Task 6: Update README

**Files:**
- Modify: `scripts/PIPELINE_OPERATIONS_README.md`

- [ ] **Step 1: Document canonical-by-form layout**

- [ ] **Step 2: Add form code table**

- [ ] **Step 3: Add `status 0/1/2` explanation**

- [ ] **Step 4: Add examples**

Include:
- form sync
- brand sync into canonical form corpus
- new/changed delta sync
- ingredient discovery
- note on off-market retention
- note on overlap/dedup by `dsld_id`

- [ ] **Step 5: Run diff check**

Run:
```bash
git diff --check -- scripts/PIPELINE_OPERATIONS_README.md
```

Expected:
- PASS

## Task 7: Verification

**Files:**
- Modify: none

- [ ] **Step 1: Run targeted tests**

```bash
pytest scripts/tests/test_dsld_api_client.py scripts/tests/test_dsld_api_sync.py -q
```

- [ ] **Step 2: Run broader regression set**

```bash
pytest scripts/tests/test_build_final_db.py scripts/tests/test_build_all_final_dbs.py scripts/tests/test_sync_to_supabase.py scripts/tests/test_supabase_client.py scripts/tests/test_assemble_final_db_release.py scripts/tests/test_generate_pair_change_journal.py scripts/tests/test_dsld_api_client.py scripts/tests/test_dsld_api_sync.py -q
```

- [ ] **Step 3: Run syntax checks**

```bash
python3 -m py_compile scripts/dsld_api_client.py scripts/dsld_api_sync.py
```

- [ ] **Step 4: Run diff checks**

```bash
git diff --check
```

- [ ] **Step 5: Optional live smoke once unit tests pass**

Examples:
```bash
python3 scripts/dsld_api_sync.py sync-filter --supplement-form e0176 --status 2 --canonical-root raw_data/forms --state-file /tmp/dsld_state.json --limit 10
python3 scripts/dsld_api_sync.py sync-delta --brand "Olly" --status 2 --canonical-root raw_data/forms --state-file /tmp/dsld_state.json --delta-output-dir /tmp/dsld_delta_olly
```

Plan complete and saved to `docs/superpowers/plans/2026-03-30-dsld-canonical-form-sync-implementation.md`. Ready to execute?
