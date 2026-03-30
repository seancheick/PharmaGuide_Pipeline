# DSLD API Ingestion Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a DSLD API client and sync CLI that can fetch labels from the API, persist them in the same raw-file contract as existing manual downloads, and verify parity without changing the downstream clean -> enrich -> score -> build -> sync pipeline.

**Architecture:** Keep the implementation split into two files. `scripts/dsld_api_client.py` owns HTTP behavior, endpoint wrappers, retry/backoff, and response normalization helpers. `scripts/dsld_api_sync.py` owns the CLI, file persistence, snapshot behavior, probe/parity checks, and verification workflow. The cleaner and later pipeline stages remain untouched and source-agnostic.

**Tech Stack:** Python 3, `requests`, `argparse`, existing `env_loader.py`, existing `scripts/tests/` pytest patterns, JSON filesystem persistence.

---

## File Structure

### New files

- `scripts/dsld_api_client.py`
  - loads API configuration from `.env`
  - wraps DSLD endpoints
  - implements retry/backoff and rate-limit handling
  - normalizes endpoint envelopes into label objects
  - owns pagination/iteration helpers for discovery endpoints
- `scripts/dsld_api_sync.py`
  - provides CLI subcommands
  - persists normalized labels to raw JSON files
  - implements `--snapshot`
  - implements `probe` parity gate and `verify-db`
- `scripts/tests/test_dsld_api_client.py`
  - unit tests for config loading, retries, error handling, endpoint normalization
- `scripts/tests/test_dsld_api_sync.py`
  - unit tests for persistence rules, snapshot behavior, parity checks, verification diffs, CLI parsing

### Existing files to reference but not modify initially

- `scripts/env_loader.py`
- `scripts/batch_processor.py`
- `scripts/clean_dsld_data.py`
- `docs/superpowers/specs/2026-03-29-dsld-api-raw-adapter-contract-design.md`

### Optional doc follow-up after implementation

- `scripts/PIPELINE_ARCHITECTURE.md`

Only update the pipeline doc if implementation lands cleanly and the CLI contract is stable.

### Shared implementation boundaries

- `dsld_api_client.py` must not write files
- `dsld_api_sync.py` must not own raw HTTP request details beyond orchestration
- parity and persistence logic should be testable as pure functions where possible
- iterator/pagination logic belongs in `dsld_api_client.py`, not the CLI
- raw-contract field backfill belongs in `dsld_api_sync.py`, not the cleaner

---

### Task 1: Scaffold the DSLD API client

**Files:**
- Create: `scripts/dsld_api_client.py`
- Test: `scripts/tests/test_dsld_api_client.py`

- [ ] **Step 1: Write the failing config and request tests**

```python
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_load_dsld_api_config_reads_env(monkeypatch):
    monkeypatch.setenv("DSLD_API_KEY", "test-key")
    monkeypatch.setenv("DSLD_API_BASE_URL", "https://example.test")

    from dsld_api_client import load_dsld_api_config

    config = load_dsld_api_config()
    assert config.api_key == "test-key"
    assert config.base_url == "https://example.test"


def test_request_json_retries_http_429(monkeypatch):
    import dsld_api_client as client_mod

    calls = {"count": 0}

    class FakeResponse:
        def __init__(self, status_code, payload, headers=None):
            self.status_code = status_code
            self._payload = payload
            self.headers = headers or {}

        def raise_for_status(self):
            import requests
            if self.status_code >= 400:
                raise requests.HTTPError(response=self)

        def json(self):
            return self._payload

    def fake_request(method, url, params=None, timeout=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeResponse(429, {"error": "rate limited"}, {"Retry-After": "0"})
        return FakeResponse(200, {"ok": True})

    monkeypatch.setattr(client_mod.requests, "request", fake_request, raising=False)
    monkeypatch.setattr(client_mod.time, "sleep", lambda _: None)

    client = client_mod.DSLDAPIClient(api_key="k", base_url="https://example.test", rate_limit_delay=0.0)
    assert client.request_json("GET", "/v9/label/1") == {"ok": True}
    assert calls["count"] == 2
```

- [ ] **Step 2: Run the client tests to verify they fail**

Run: `pytest scripts/tests/test_dsld_api_client.py -q`

Expected: FAIL because `dsld_api_client.py` and its public API do not exist yet.

- [ ] **Step 3: Write the minimal client implementation**

Implement in `scripts/dsld_api_client.py`:

```python
#!/usr/bin/env python3

import os
import time
from dataclasses import dataclass

import requests
import env_loader  # noqa: F401


DEFAULT_BASE_URL = "https://dsldapi.od.nih.gov"


@dataclass(frozen=True)
class DSLDAPIConfig:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 30.0


def load_dsld_api_config():
    api_key = os.environ.get("DSLD_API_KEY") or os.environ.get("API_KEY")
    if not api_key:
        raise ValueError("DSLD_API_KEY environment variable is not set.")
    base_url = os.environ.get("DSLD_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    return DSLDAPIConfig(api_key=api_key, base_url=base_url)
```

Add:

- a `DSLDAPIClient` class
- `request_json(...)`
- retry/backoff on `429`, connection errors, and timeouts
- `Retry-After` support when present
- JSON decode failure with explicit exception text

- [ ] **Step 4: Add endpoint wrappers and response normalization helpers**

Implement these methods:

```python
class DSLDAPIClient:
    def get_version(self): ...
    def get_label(self, dsld_id): ...
    def get_brand_products(self, brand, page=1, page_size=100): ...
    def search_filter(self, **params): ...
    def iter_brand_products(self, brand, page_size=100): ...
    def iter_search_results(self, **params): ...
```

Also implement:

- `unwrap_label_payload(payload)` for `label/{id}`
- `extract_items(payload)` for paginated list endpoints

Keep wrappers thin and deterministic.

Paging contract:

- `get_brand_products(...)` and `search_filter(...)` fetch one page
- `iter_brand_products(...)` and `iter_search_results(...)` own pagination
- `dsld_api_sync.py` consumes iterators and must not reimplement page walking

- [ ] **Step 5: Run the client tests and expand coverage**

Run: `pytest scripts/tests/test_dsld_api_client.py -q`

Expected: PASS

Add more tests for:

- missing API key
- HTTP 404 / 500 surfacing useful errors
- malformed JSON
- rate-limit sleep path

- [ ] **Step 6: Commit**

```bash
git add scripts/dsld_api_client.py scripts/tests/test_dsld_api_client.py
git commit -m "feat: add dsld api client"
```

---

### Task 2: Build raw-file persistence helpers and CLI skeleton

**Files:**
- Create: `scripts/dsld_api_sync.py`
- Test: `scripts/tests/test_dsld_api_sync.py`

- [ ] **Step 1: Write failing persistence and parse-args tests**

```python
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_parse_args_supports_probe_and_sync_brand():
    from dsld_api_sync import build_parser

    parser = build_parser()
    args = parser.parse_args(["probe", "--reference-file", "sample.json", "--dsld-id", "241695"])
    assert args.command == "probe"
    assert args.reference_file == "sample.json"


def test_persist_label_writes_id_named_json(tmp_path):
    from dsld_api_sync import persist_label_record

    record = {"id": 241695, "fullName": "Test", "ingredientRows": [], "_source": "api"}
    path = persist_label_record(record, output_dir=tmp_path, snapshot=False)
    assert path.name == "241695.json"
```

- [ ] **Step 2: Run the sync tests to verify they fail**

Run: `pytest scripts/tests/test_dsld_api_sync.py -q`

Expected: FAIL because `dsld_api_sync.py` and helper functions do not exist yet.

- [ ] **Step 3: Write the CLI skeleton and pure persistence helpers**

Implement in `scripts/dsld_api_sync.py`:

```python
def build_parser():
    parser = argparse.ArgumentParser(description="Sync and verify raw DSLD labels via the DSLD API.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    # probe, sync-brand, refresh-ids, verify-db, sync-query, check-version
    return parser


def normalize_label_for_storage(label, source):
    # Step 4 will expand this into the full raw-contract normalization path.
    return dict(label)


def persist_label_record(record, output_dir, snapshot=False):
    record_id = str(record["id"])
    path = Path(output_dir) / f"{record_id}.json"
    ...
```

Keep `persist_label_record(...)` independent from network code.

- [ ] **Step 4: Enforce the manual raw-file contract during normalization**

Implement explicit raw-contract field backfill in `normalize_label_for_storage(...)`.

```python
REQUIRED_TOP_LEVEL_DEFAULTS = {
    "fullName": None,
    "brandName": None,
    "productVersionCode": None,
    "entryDate": None,
    "offMarket": None,
    "claims": [],
    "events": [],
    "statements": [],
    "servingSizes": [],
    "targetGroups": [],
    "productType": None,
    "physicalState": None,
    "contacts": [],
    "upcSku": None,
}


def normalize_label_for_storage(label, source):
    stored = dict(label)
    if "otherIngredients" in stored and "otheringredients" not in stored:
        stored["otheringredients"] = stored["otherIngredients"]
    stored.pop("otherIngredients", None)
    stored.setdefault("ingredientRows", [])
    stored.setdefault("otheringredients", {"text": None, "ingredients": []})
    for key, default in REQUIRED_TOP_LEVEL_DEFAULTS.items():
        stored.setdefault(key, default)
    stored["_source"] = source
    return stored
```

Add tests for:

- missing contract fields get `null`/empty defaults
- `otherIngredients` maps to lowercase `otheringredients`
- `otherIngredients` is removed from stored output after normalization
- extra API fields are preserved
- transport-envelope keys are stripped when normalization owns that unwrap step
- missing `id` still fails

- [ ] **Step 5: Add snapshot routing and output-directory rules**

Implement helpers for:

- `resolve_output_dir(...)`
- `ensure_flat_output_dir(...)`
- refusing nested write conventions

Rules:

- default commands overwrite `<id>.json`
- `--snapshot` writes into a separate directory
- `verify-db` must always behave like snapshot mode even if `--snapshot` is omitted

- [ ] **Step 6: Run tests and expand persistence coverage**

Run: `pytest scripts/tests/test_dsld_api_sync.py -q`

Expected: PASS

Add tests for:

- lowercase `otheringredients` mapping
- `_source` insertion
- required/manual-contract field backfill
- overwrite behavior
- snapshot behavior
- invalid records missing `id`

- [ ] **Step 7: Commit**

```bash
git add scripts/dsld_api_sync.py scripts/tests/test_dsld_api_sync.py
git commit -m "feat: add dsld api sync cli skeleton"
```

---

### Task 3: Implement the probe parity gate

**Files:**
- Modify: `scripts/dsld_api_sync.py`
- Modify: `scripts/tests/test_dsld_api_sync.py`

- [ ] **Step 1: Write the failing parity-gate tests**

```python
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_probe_ignores_source_but_fails_on_missing_required_key(tmp_path):
    from dsld_api_sync import compare_parity

    reference = {"id": 241695, "ingredientRows": [], "otheringredients": {"ingredients": []}}
    candidate = {"id": 241695, "_source": "api"}

    result = compare_parity(reference, candidate)
    assert result["passed"] is False
    assert "ingredientRows" in result["missing_required_keys"]


def test_probe_allows_extra_api_fields():
    from dsld_api_sync import compare_parity

    reference = {"id": 241695, "ingredientRows": [], "otheringredients": {"ingredients": []}}
    candidate = {
        "id": 241695,
        "ingredientRows": [],
        "otheringredients": {"ingredients": []},
        "thumbnail": "https://example.test/thumb.jpg",
        "_source": "api",
    }

    result = compare_parity(reference, candidate)
    assert result["passed"] is True


def test_probe_fails_on_top_level_type_drift():
    from dsld_api_sync import compare_parity

    reference = {"id": 241695, "ingredientRows": [], "otheringredients": {"ingredients": []}, "claims": []}
    candidate = {"id": 241695, "ingredientRows": {}, "otheringredients": {"ingredients": []}, "claims": []}

    result = compare_parity(reference, candidate)
    assert result["passed"] is False
```

- [ ] **Step 2: Run the targeted parity tests to verify they fail**

Run: `pytest scripts/tests/test_dsld_api_sync.py -q -k parity`

Expected: FAIL because parity comparison is not implemented yet.

- [ ] **Step 3: Implement structural parity comparison**

Add pure functions such as:

```python
IGNORED_PARITY_KEYS = {"_source"}


def compare_parity(reference_record, candidate_record):
    return {
        "passed": ...,
        "missing_required_keys": ...,
        "type_mismatches": ...,
        "missing_required_structures": ...,
        "extra_keys": ...,
    }
```

Requirements:

- require the same `id`
- allow extra API keys
- ignore `_source`
- compare nested structures for:
  - `ingredientRows[*]`
  - `otheringredients`
  - `otheringredients.ingredients[*]`
  - `claims[*]`
  - `events[*]`
  - `statements[*]`
  - `servingSizes[*]`

- [ ] **Step 4: Wire the `probe` subcommand**

Implement:

- `probe --reference-file <path> --dsld-id <id>`

Behavior:

- load the reference file
- fetch the same label from API
- normalize with `_source="api"`
- compare parity
- print structured JSON result
- exit non-zero on failure

Also add one test that a wrapped API label payload is unwrapped before parity comparison.

- [ ] **Step 5: Run tests and a dry probe smoke**

Run:

- `pytest scripts/tests/test_dsld_api_sync.py -q -k "parity or probe"`
- `python3 scripts/dsld_api_sync.py probe --help`

Expected:

- tests PASS
- help text shows `--reference-file`

- [ ] **Step 6: Run one real authenticated probe before continuing**

Run:

```bash
python3 scripts/dsld_api_sync.py probe \
  --id 13418 \
  --reference /Users/seancheick/Documents/DataSetDsld/Nordic-Naturals-2-17-26-L511/13418.json
```

Expected:

- JSON response, not HTML
- adapter normalization succeeds
- parity output is usable for next-step decisions

Blocking rule:

- do not start Task 4 until this real probe either passes or produces concrete response-shape evidence that the client/normalizer must be adjusted

- [ ] **Step 7: Commit**

```bash
git add scripts/dsld_api_sync.py scripts/tests/test_dsld_api_sync.py
git commit -m "feat: add dsld api parity probe"
```

---

### Task 4: Implement operational fetch commands

**Files:**
- Modify: `scripts/dsld_api_sync.py`
- Modify: `scripts/tests/test_dsld_api_sync.py`

- [ ] **Step 1: Write failing command tests for brand and ID refresh**

```python
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_sync_brand_persists_all_fetched_labels(tmp_path, monkeypatch):
    from dsld_api_sync import run_sync_brand

    class FakeClient:
        def iter_brand_products(self, brand):
            yield {"id": 1}
            yield {"id": 2}
        def get_label(self, dsld_id):
            return {"id": dsld_id, "ingredientRows": [], "otheringredients": {"ingredients": []}}

    result = run_sync_brand(FakeClient(), brand="Nordic Naturals", output_dir=tmp_path, snapshot=False)
    assert result["written_count"] == 2


def test_refresh_ids_overwrites_by_default(tmp_path):
    ...
```

- [ ] **Step 2: Run the command tests to verify they fail**

Run: `pytest scripts/tests/test_dsld_api_sync.py -q -k "sync_brand or refresh_ids"`

Expected: FAIL

- [ ] **Step 3: Implement command runners**

Implement command handlers:

- `run_sync_brand(...)`
- `run_refresh_ids(...)`
- `run_sync_query(...)`
- `run_check_version(...)`

Behavior:

- `sync-brand`:
  - discover product IDs via brand endpoint
  - fetch full labels via `get_label`
  - persist normalized files
- `refresh-ids`:
  - fetch explicit IDs and overwrite or snapshot
- `sync-query`:
  - use search-filter endpoint for discovery
- `check-version`:
  - print API version payload without file writes

- [ ] **Step 4: Add CLI wiring and structured command output**

All command handlers should return structured JSON-friendly summaries like:

```python
{
    "command": "sync-brand",
    "written_count": 42,
    "output_dir": "...",
    "dsld_ids": ["1", "2", "3"],
}
```

- [ ] **Step 5: Run tests and CLI smoke**

Run:

- `pytest scripts/tests/test_dsld_api_sync.py -q -k "sync_brand or refresh_ids or sync_query or check_version"`
- `python3 scripts/dsld_api_sync.py --help`

Expected: PASS and CLI subcommands visible.

- [ ] **Step 6: Commit**

```bash
git add scripts/dsld_api_sync.py scripts/tests/test_dsld_api_sync.py
git commit -m "feat: add dsld api fetch commands"
```

---

### Task 5: Implement verify-db as read-only snapshot verification

**Files:**
- Modify: `scripts/dsld_api_sync.py`
- Modify: `scripts/tests/test_dsld_api_sync.py`

- [ ] **Step 1: Write failing verification tests**

```python
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_verify_db_fetches_into_snapshot_location(tmp_path):
    from dsld_api_sync import run_verify_db

    class FakeClient:
        def get_label(self, dsld_id):
            return {"id": dsld_id, "ingredientRows": [], "otheringredients": {"ingredients": []}, "offMarket": False}

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "241695.json").write_text('{"id": 241695, "ingredientRows": [], "otheringredients": {"ingredients": []}, "_source": "manual"}')

    result = run_verify_db(FakeClient(), input_dir=raw_dir, snapshot_dir=tmp_path / "verify")
    assert result["verified_count"] == 1
    assert (tmp_path / "verify" / "241695.json").exists()


def test_verify_db_reports_drift_without_overwriting_source(tmp_path):
    ...
```

- [ ] **Step 2: Run verification tests to verify they fail**

Run: `pytest scripts/tests/test_dsld_api_sync.py -q -k verify_db`

Expected: FAIL

- [ ] **Step 3: Implement verification workflow**

Implement `run_verify_db(...)`:

- scan a flat raw input directory
- load local raw files
- fetch current API label by `id`
- normalize fetched label with `_source="api"`
- persist fetched copy to verification snapshot directory
- reuse `compare_parity(...)` from Task 3 as the compatibility baseline
- compare selected fields/structures for human-readable drift reporting on top of that baseline
- emit a diff report JSON

The report should at minimum include:

```python
{
    "verified_count": 1,
    "drift_count": 1,
    "items": [
        {
            "id": "241695",
            "field_differences": ["offMarket", "productVersionCode"],
        }
    ],
}
```

- [ ] **Step 4: Ensure verify-db never mutates canonical raw data**

Guardrails:

- never write into `input_dir`
- always require or derive a separate verification directory
- fail loudly if snapshot directory resolves to the same path as canonical input

Snapshot directory contract:

- if `--snapshot-dir` is provided, use it
- otherwise derive a temp or timestamped verification directory outside `input_dir`
- always print the effective verification directory in command output

- [ ] **Step 5: Run tests and a help smoke**

Run:

- `pytest scripts/tests/test_dsld_api_sync.py -q -k verify_db`
- `python3 scripts/dsld_api_sync.py verify-db --help`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/dsld_api_sync.py scripts/tests/test_dsld_api_sync.py
git commit -m "feat: add dsld api verification mode"
```

---

### Task 6: Final verification and docs touch-up

**Files:**
- Modify: `scripts/PIPELINE_ARCHITECTURE.md` (only if the command contract is stable)
- Modify: `docs/superpowers/specs/2026-03-29-dsld-api-raw-adapter-contract-design.md` (only if implementation exposed spec drift)

- [ ] **Step 1: Run the full new test set**

Run:

```bash
pytest scripts/tests/test_dsld_api_client.py scripts/tests/test_dsld_api_sync.py -q
```

Expected: PASS

- [ ] **Step 2: Add a raw-compatibility acceptance test**

Add one acceptance test to `scripts/tests/test_dsld_api_sync.py` proving the unchanged loader contract accepts an API-normalized file.

Example shape:

```python
def test_api_normalized_raw_file_is_accepted_by_existing_loader_contract(tmp_path):
    import json

    from dsld_api_sync import normalize_label_for_storage
    from batch_processor import validate_input_file

    record = normalize_label_for_storage({"id": 241695, "ingredientRows": []}, source="api")
    path = tmp_path / "241695.json"
    path.write_text(json.dumps(record), encoding="utf-8")

    assert validate_input_file(path) is True
```

If the existing validation helper is not exported as a top-level function, adapt the test to the existing public validation entry point actually used by `batch_processor.py`. The requirement is to prove that an API-normalized raw file is accepted by the unchanged current loader/validator path.

- [ ] **Step 3: Add a narrow unchanged clean-stage smoke**

Create one API-normalized raw file fixture and run it through the unchanged clean stage.

Run:

```bash
python3 scripts/clean_dsld_data.py \
  --input-dir /tmp/dsld_api_smoke_raw \
  --output-dir /tmp/dsld_api_smoke_cleaned \
  --config scripts/config/cleaning_config.json
```

Expected:

- clean stage completes successfully
- one cleaned output file is produced
- no structural failure caused by API-normalized raw shape

- [ ] **Step 4: Run static verification**

Run:

```bash
python3 -m py_compile scripts/dsld_api_client.py scripts/dsld_api_sync.py
git diff --check
```

Expected:

- no syntax errors
- no diff formatting errors

- [ ] **Step 5: Run CLI help verification**

Run:

```bash
python3 scripts/dsld_api_sync.py --help
python3 scripts/dsld_api_sync.py probe --help
python3 scripts/dsld_api_sync.py sync-brand --help
python3 scripts/dsld_api_sync.py verify-db --help
```

Expected: all help commands render successfully.

- [ ] **Step 6: Optionally update pipeline docs**

If implementation is stable, add one short section to `scripts/PIPELINE_ARCHITECTURE.md` describing:

- manual vs API raw sources
- unchanged downstream pipeline
- new scripts and their role

Do not add this doc update until the command surface is final.

- [ ] **Step 7: Commit**

```bash
git add scripts/dsld_api_client.py scripts/dsld_api_sync.py scripts/tests/test_dsld_api_client.py scripts/tests/test_dsld_api_sync.py scripts/PIPELINE_ARCHITECTURE.md
git commit -m "feat: add dsld api ingestion tooling"
```

---

## Notes For Implementation

- Prefer `requests` for DSLD because response/header handling and retry ergonomics are cleaner here.
- Keep the client thin. Do not bury file-system or CLI logic in `dsld_api_client.py`.
- Keep parity comparison pure and deterministic so tests do not need network access.
- Do not change `clean_dsld_data.py` or `batch_processor.py` as part of the first implementation pass.
- Use the real probe against the operator machine only after unit tests pass.
- If the live API returns Swagger HTML instead of JSON, stop and fix probe/auth/request shape first before implementing broader commands.
