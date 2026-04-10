# Valyu Evidence Watchtower Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate, review-only Valyu evidence watchtower that scans clinical, IQM-gap, harmful-additive, and banned/recalled domains and emits readable review reports without mutating production source files.

**Architecture:** Keep the Valyu implementation separate from the production audit and scoring path. Refactor the existing Valyu script into a small CLI plus focused helpers for domain loading, query planning, report classification, and file output. Treat Valyu search results as supporting evidence only and enforce a hard no-write rule for canonical JSON.

**Tech Stack:** Python 3.9+, existing repo CLI patterns, `valyu` SDK, JSON/Markdown reports, `pytest`, `py_compile`

---

## File Map

### Create

- `scripts/api_audit/valyu_report_types.py`
  - Shared constants, enums, and report-row normalization helpers.
- `scripts/api_audit/valyu_domain_targets.py`
  - Canonical source-file loading and target selection for the four domains.
- `scripts/api_audit/valyu_query_planner.py`
  - Domain-specific search terms, source filters, and date-window selection.
- `scripts/api_audit/valyu_report_writer.py`
  - JSON and Markdown report generation.
- `scripts/tests/test_valyu_evidence_discovery.py`
  - CLI and end-to-end dry-run behavior with mocked Valyu client.
- `scripts/tests/test_valyu_domain_targets.py`
  - Domain filtering and junk-exclusion tests.
- `scripts/tests/test_valyu_report_writer.py`
  - Report schema and summary formatting tests.

### Modify

- `scripts/api_audit/valyu_evidence_discovery.py`
  - Replace the current prototype with the new review-only CLI.
- `scripts/PIPELINE_OPERATIONS_README.md`
  - Add a short section clarifying that Valyu is a review-only evidence watchtower, not a production scoring dependency.

### Reference

- `docs/superpowers/specs/2026-04-10-valyu-evidence-watchtower-design.md`
- `scripts/api_audit/discover_clinical_evidence.py`
- `scripts/data/backed_clinical_studies.json`
- `scripts/data/ingredient_quality_map.json`
- `scripts/data/harmful_additives.json`
- `scripts/data/banned_recalled_ingredients.json`

## Task 1: Define The Report Contract And Shared Constants

**Files:**
- Create: `scripts/api_audit/valyu_report_types.py`
- Test: `scripts/tests/test_valyu_report_writer.py`

- [ ] **Step 1: Write the failing schema test**

```python
from api_audit.valyu_report_types import normalize_signal_row


def test_normalize_signal_row_enforces_review_only_flags():
    row = normalize_signal_row(
        {
            "domain": "clinical_refresh",
            "entity_name": "Meriva Curcumin Phytosome",
            "signal_type": "possible_upgrade",
        }
    )

    assert row["requires_human_review"] is True
    assert row["auto_apply_allowed"] is False
    assert row["signal_type"] == "possible_upgrade"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_report_writer.py -k review_only_flags
```

Expected: fail because `valyu_report_types.py` and `normalize_signal_row` do not exist yet.

- [ ] **Step 3: Write minimal shared constants and row normalizer**

Implement:

- allowed domains
- allowed signal types
- default fixed flags
- normalization for optional fields like `candidate_sources`, `candidate_references`, and `supporting_summary`

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_report_writer.py -k review_only_flags
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/api_audit/valyu_report_types.py scripts/tests/test_valyu_report_writer.py
git commit -m "feat: add Valyu report schema helpers"
```

## Task 2: Build Domain Target Selection

**Files:**
- Create: `scripts/api_audit/valyu_domain_targets.py`
- Test: `scripts/tests/test_valyu_domain_targets.py`

- [ ] **Step 1: Write the failing domain-selection tests**

```python
from api_audit.valyu_domain_targets import load_iqm_gap_targets


def test_iqm_gap_targets_exclude_excipient_noise(tmp_path):
    iqm = {
        "ingredients": [
            {"standard_name": "Berberine", "category": "herb"},
            {"standard_name": "Silicon Dioxide", "category": "flow_agent_anticaking"},
        ]
    }
    clinical = {"backed_clinical_studies": []}

    targets = load_iqm_gap_targets(iqm, clinical)

    names = {row["entity_name"] for row in targets}
    assert "Berberine" in names
    assert "Silicon Dioxide" not in names
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_domain_targets.py -k excipient_noise
```

Expected: fail because target loader does not exist yet.

- [ ] **Step 3: Implement domain loaders**

Implement focused loaders for:

- `clinical-refresh`
- `iqm-gap-scan`
- `harmful-refresh`
- `recall-refresh`

Behavior requirements:

- `iqm-gap-scan` excludes excipients, coatings, capsule shells, colors, and known inactive-only categories
- all loaders attach `target_file`, `entity_type`, `entity_id`, and `entity_name`

- [ ] **Step 4: Add a no-unmapped-inactives regression test**

Add a second test proving the domain loader never uses old unmapped inactive-ingredient buckets.

- [ ] **Step 5: Run the domain target test file**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_domain_targets.py
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/api_audit/valyu_domain_targets.py scripts/tests/test_valyu_domain_targets.py
git commit -m "feat: add Valyu domain target loaders"
```

## Task 3: Build Query Planning And Source Filters

**Files:**
- Create: `scripts/api_audit/valyu_query_planner.py`
- Test: `scripts/tests/test_valyu_evidence_discovery.py`

- [ ] **Step 1: Write failing query-planning tests**

```python
from api_audit.valyu_query_planner import build_search_plan


def test_clinical_refresh_uses_clinical_sources_and_date_window():
    plan = build_search_plan(
        domain="clinical_refresh",
        entity_name="Meriva Curcumin Phytosome",
        months_back=24,
    )

    assert "pubmed" in " ".join(plan["included_sources"]).lower()
    assert plan["start_date"]
    assert plan["end_date"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_evidence_discovery.py -k clinical_sources
```

Expected: fail because query planner does not exist yet.

- [ ] **Step 3: Implement query planner**

Implement:

- domain-specific source filters
- default `24`-month window
- explicit query strings per domain
- clean operator-facing stored `query_used`

Keep the initial implementation to Valyu `search(...)` planning only. Do not add secondary `answer(...)` calls in the first pass.

- [ ] **Step 4: Add harmful/recall source filter tests**

Verify harmful and recall modes do not inherit the clinical source set by mistake.

- [ ] **Step 5: Run the query-related tests**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_evidence_discovery.py -k "clinical_sources or harmful"
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/api_audit/valyu_query_planner.py scripts/tests/test_valyu_evidence_discovery.py
git commit -m "feat: add Valyu query planning"
```

## Task 4: Refactor The Valyu CLI Into A Review-Only Tool

**Files:**
- Modify: `scripts/api_audit/valyu_evidence_discovery.py`
- Test: `scripts/tests/test_valyu_evidence_discovery.py`

- [ ] **Step 1: Write the failing CLI tests**

Add tests for:

- supported modes: `clinical-refresh`, `iqm-gap-scan`, `harmful-refresh`, `recall-refresh`, `all`
- missing API key behavior
- missing SDK behavior
- no `--apply` flag exists

Example:

```python
def test_cli_rejects_unknown_mode(capsys):
    with pytest.raises(SystemExit):
        main(["unknown-mode"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_evidence_discovery.py -k "cli or api_key"
```

Expected: fail against the current prototype behavior.

- [ ] **Step 3: Replace the prototype CLI**

Implementation requirements:

- no writes to source-of-truth JSON
- no quarantine auto-apply behavior
- explicit mode help text
- clear failure messaging if SDK or API key is missing
- easy-to-read summary printed to stderr/stdout

- [ ] **Step 4: Mock the Valyu client in tests**

Use a fake client that returns predictable search hits so tests do not require live API access.

- [ ] **Step 5: Run the CLI test file**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_evidence_discovery.py
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/api_audit/valyu_evidence_discovery.py scripts/tests/test_valyu_evidence_discovery.py
git commit -m "feat: refactor Valyu audit CLI to review-only modes"
```

## Task 5: Add Report Writing And Summary Markdown

**Files:**
- Create: `scripts/api_audit/valyu_report_writer.py`
- Test: `scripts/tests/test_valyu_report_writer.py`

- [ ] **Step 1: Write the failing report output tests**

Add tests for:

- timestamped output paths under `scripts/api_audit/reports/valyu/`
- `raw-search-report.json`
- `review-queue.json`
- `summary.md`
- summary ordering puts highest-confidence items first

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_report_writer.py -k "summary or output"
```

Expected: fail because writer module does not exist yet.

- [ ] **Step 3: Implement the report writer**

Implementation requirements:

- `raw-search-report.json` stores unfiltered Valyu response fragments plus metadata
- `review-queue.json` stores normalized review rows only
- `summary.md` explains:
  - what was scanned
  - how many rows were flagged
  - which findings are highest confidence
  - what to review next

- [ ] **Step 4: Ensure report rows stay readable**

Trim overly long summaries and keep markdown flat and scannable.

- [ ] **Step 5: Run report writer tests**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_report_writer.py
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/api_audit/valyu_report_writer.py scripts/tests/test_valyu_report_writer.py
git commit -m "feat: add Valyu report writers"
```

## Task 6: Add Finding Classification

**Files:**
- Modify: `scripts/api_audit/valyu_evidence_discovery.py`
- Modify: `scripts/api_audit/valyu_report_types.py`
- Test: `scripts/tests/test_valyu_evidence_discovery.py`

- [ ] **Step 1: Write failing classification tests**

Add tests for:

- `possible_upgrade`
- `possible_contradiction`
- `missing_evidence`
- `possible_safety_change`
- `possible_recall_change`
- `low_confidence_noise`

Make the tests use controlled fake result payloads instead of real Valyu calls.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_evidence_discovery.py -k classification
```

Expected: fail until classifier logic exists.

- [ ] **Step 3: Implement conservative classification**

Rules:

- missing citations or weak/noisy matches downgrade to `low_confidence_noise`
- stale clinical entries with newer strong references become `possible_upgrade`
- explicit mismatch against current framing can become `possible_contradiction`
- harmful and recall domains use dedicated signal types

Keep the logic conservative. When unsure, downgrade.

- [ ] **Step 4: Run classification tests**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_evidence_discovery.py -k classification
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/api_audit/valyu_evidence_discovery.py scripts/api_audit/valyu_report_types.py scripts/tests/test_valyu_evidence_discovery.py
git commit -m "feat: add conservative Valyu finding classification"
```

## Task 7: Enforce No-Write Guarantees

**Files:**
- Test: `scripts/tests/test_valyu_evidence_discovery.py`

- [ ] **Step 1: Write failing no-write tests**

Add tests that snapshot these files before and after a mocked run:

- `scripts/data/backed_clinical_studies.json`
- `scripts/data/ingredient_quality_map.json`
- `scripts/data/harmful_additives.json`
- `scripts/data/banned_recalled_ingredients.json`

Assert that their contents do not change.

- [ ] **Step 2: Run test to verify it fails if any accidental write exists**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_evidence_discovery.py -k no_write
```

Expected: PASS only when the CLI performs no canonical file writes.

- [ ] **Step 3: Remove any write-capable leftovers from the prototype**

Delete old quarantine/update-writing logic if still present.

- [ ] **Step 4: Re-run the no-write tests**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_evidence_discovery.py -k no_write
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/api_audit/valyu_evidence_discovery.py scripts/tests/test_valyu_evidence_discovery.py
git commit -m "test: enforce Valyu no-write guarantees"
```

## Task 8: Document Operator Usage

**Files:**
- Modify: `scripts/PIPELINE_OPERATIONS_README.md`

- [ ] **Step 1: Add a short operator section**

Document:

- what the Valyu watchtower is
- what it is not
- example commands
- where reports are written
- review-only guardrail

- [ ] **Step 2: Keep docs brief and explicit**

This should be a short operations note, not a long essay.

- [ ] **Step 3: Verify doc references match the actual CLI**

Make sure the mode names and report paths exactly match implementation.

- [ ] **Step 4: Commit**

```bash
git add scripts/PIPELINE_OPERATIONS_README.md
git commit -m "docs: add Valyu evidence watchtower ops notes"
```

## Task 9: Run The Full Verification Pass

**Files:**
- Test: `scripts/tests/test_valyu_evidence_discovery.py`
- Test: `scripts/tests/test_valyu_domain_targets.py`
- Test: `scripts/tests/test_valyu_report_writer.py`

- [ ] **Step 1: Run targeted tests**

Run:

```bash
.venv/bin/python -m pytest -q scripts/tests/test_valyu_evidence_discovery.py scripts/tests/test_valyu_domain_targets.py scripts/tests/test_valyu_report_writer.py
```

Expected: all pass

- [ ] **Step 2: Run compile check**

Run:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache .venv/bin/python -m py_compile \
  scripts/api_audit/valyu_evidence_discovery.py \
  scripts/api_audit/valyu_report_types.py \
  scripts/api_audit/valyu_domain_targets.py \
  scripts/api_audit/valyu_query_planner.py \
  scripts/api_audit/valyu_report_writer.py
```

Expected: no output, exit code `0`

- [ ] **Step 3: Run one mocked CLI smoke path**

Run a test-backed smoke path rather than a live API call. Live API execution depends on local SDK and credentials and should be optional after the code is stable.

- [ ] **Step 4: Commit the finished implementation**

```bash
git add scripts/api_audit/valyu_evidence_discovery.py \
  scripts/api_audit/valyu_report_types.py \
  scripts/api_audit/valyu_domain_targets.py \
  scripts/api_audit/valyu_query_planner.py \
  scripts/api_audit/valyu_report_writer.py \
  scripts/tests/test_valyu_evidence_discovery.py \
  scripts/tests/test_valyu_domain_targets.py \
  scripts/tests/test_valyu_report_writer.py \
  scripts/PIPELINE_OPERATIONS_README.md
git commit -m "feat: add review-only Valyu evidence watchtower"
```

## Notes For The Implementer

- Follow the existing CLI style from [discover_clinical_evidence.py](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/api_audit/discover_clinical_evidence.py) where useful, but do not share write-capable code paths.
- Do not add `--apply`.
- Do not let the new tool read from old unmapped inactive-ingredient outputs.
- Keep modules focused and small.
- Prefer mocked tests over live network tests.
- If a signal cannot be justified cleanly, downgrade it instead of inventing certainty.
