# Display Ledger Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an additive `display_ingredients` ledger that preserves user-visible label rows while keeping scoring logic unchanged.

**Architecture:** The cleaner will emit a compact, provenance-preserving display ledger before suppressing summary/wrapper/structural rows from scoring-safe normalized arrays. The enricher will attach canonical references and display resolution metadata to the ledger, but scoring will continue to use the existing normalized ingredient flows. This keeps UI fidelity separate from scoring behavior.

**Tech Stack:** Python, JSON pipeline payloads, pytest

---

### Task 1: Add cleaner-side display ledger scaffolding

**Files:**
- Modify: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/enhanced_normalizer.py`
- Test: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/tests/test_pipeline_regressions.py`

**Step 1: Write the failing test**

Add a test that normalizing a product with:
- a summary row
- a wrapper row
- a structural parent

produces:
- unchanged `activeIngredients` / `inactiveIngredients`
- new `display_ingredients`

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest scripts/tests/test_pipeline_regressions.py -q -k 'display_ledger_scaffold'
```

Expected: FAIL because `display_ingredients` does not exist.

**Step 3: Write minimal implementation**

In `enhanced_normalizer.py`:
- add top-level `display_ingredients`
- populate it with compact display rows during active/inactive processing

**Step 4: Run test to verify it passes**

Run the same test command and confirm PASS.

**Step 5: Commit**

```bash
git add scripts/enhanced_normalizer.py scripts/tests/test_pipeline_regressions.py
git commit -m "feat: add cleaner display ledger scaffold"
```

### Task 2: Preserve suppressed parent rows in the display ledger

**Files:**
- Modify: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/enhanced_normalizer.py`
- Test: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/tests/test_pipeline_regressions.py`

**Step 1: Write the failing test**

Add tests for:
- `Other Omega-3's`
- `High Choline Lecithin`
- `Safflower/Sunflower Oil concentrate`

Expected:
- row absent from scoring arrays
- row present in `display_ingredients`
- `score_included=false`

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=scripts python3 -m pytest scripts/tests/test_pipeline_regressions.py -q -k 'display_ledger_wrapper_rows'
```

**Step 3: Write minimal implementation**

Add display-row capture before wrapper suppression.

**Step 4: Run test to verify it passes**

Run the same test command and confirm PASS.

**Step 5: Commit**

```bash
git add scripts/enhanced_normalizer.py scripts/tests/test_pipeline_regressions.py
git commit -m "feat: preserve suppressed parents in display ledger"
```

### Task 3: Preserve structural parent rows with children

**Files:**
- Modify: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/enhanced_normalizer.py`
- Test: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/tests/test_pipeline_regressions.py`

**Step 1: Write the failing test**

Use a product with:
- `Humectant`
- `Acidity Regulator`
- `Soft Gel Shell`

Expected:
- parent visible in `display_ingredients`
- child rows linked beneath parent
- parent omitted from scoring arrays

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=scripts python3 -m pytest scripts/tests/test_pipeline_regressions.py -q -k 'display_ledger_structural_rows'
```

**Step 3: Write minimal implementation**

Add cleaner-side parent/child display row generation for structural rows.

**Step 4: Run test to verify it passes**

Run the same test command and confirm PASS.

**Step 5: Commit**

```bash
git add scripts/enhanced_normalizer.py scripts/tests/test_pipeline_regressions.py
git commit -m "feat: preserve structural parents in display ledger"
```

### Task 4: Add display classification fields

**Files:**
- Modify: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/enhanced_normalizer.py`
- Test: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/tests/test_pipeline_regressions.py`

**Step 1: Write the failing test**

Add assertions for:
- `display_type`
- `resolution_type`
- `score_included`
- `source_section`

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=scripts python3 -m pytest scripts/tests/test_pipeline_regressions.py -q -k 'display_ledger_classification_fields'
```

**Step 3: Write minimal implementation**

Populate the display ledger classification fields with simple deterministic values.

**Step 4: Run test to verify it passes**

Run the same test command and confirm PASS.

**Step 5: Commit**

```bash
git add scripts/enhanced_normalizer.py scripts/tests/test_pipeline_regressions.py
git commit -m "feat: classify display ledger rows"
```

### Task 5: Enrich the display ledger with canonical references

**Files:**
- Modify: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/enrich_supplements_v3.py`
- Test: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/tests/test_provenance_invariants.py`
- Test: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/tests/test_pipeline_regressions.py`

**Step 1: Write the failing test**

Add enrichment tests asserting:
- display rows keep `raw_source_text`
- mapped display rows receive `mapped_to`
- suppressed rows remain `score_included=false`

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=scripts python3 -m pytest scripts/tests/test_provenance_invariants.py scripts/tests/test_pipeline_regressions.py -q -k 'display_ledger_enrichment'
```

**Step 3: Write minimal implementation**

In `enrich_supplements_v3.py`:
- pass `display_ingredients` through enrichment
- attach canonical references where available
- do not feed display-only rows into scoring

**Step 4: Run test to verify it passes**

Run the same test command and confirm PASS.

**Step 5: Commit**

```bash
git add scripts/enrich_supplements_v3.py scripts/tests/test_provenance_invariants.py scripts/tests/test_pipeline_regressions.py
git commit -m "feat: enrich display ledger references"
```

### Task 6: Add contract validation and compatibility coverage

**Files:**
- Modify: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/tests/test_contract_validation.py`
- Modify: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/tests/test_db_integrity.py`
- Test: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/tests/test_pipeline_regressions.py`

**Step 1: Write the failing test**

Add tests ensuring:
- `display_ingredients` is optional but valid when present
- it cannot mutate scoring arrays
- required display fields are present

**Step 2: Run test to verify it fails**

```bash
PYTHONPATH=scripts python3 -m pytest scripts/tests/test_contract_validation.py scripts/tests/test_pipeline_regressions.py -q -k 'display_ledger_contract'
```

**Step 3: Write minimal implementation**

Update validation logic for additive compatibility only.

**Step 4: Run test to verify it passes**

Run the same test command and confirm PASS.

**Step 5: Commit**

```bash
git add scripts/tests/test_contract_validation.py scripts/tests/test_pipeline_regressions.py
git commit -m "test: validate display ledger contract"
```

### Task 7: Shadow-run real products and verify UI-facing fidelity

**Files:**
- Use existing pipeline scripts
- Optional notes update: `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/docs/plans/2026-03-09-display-ledger-design.md`

**Step 1: Prepare a mixed raw slice**

Use products covering:
- summary row (`Other Omega-3's`)
- wrapper row (`High Choline Lecithin`)
- structural parent (`Humectant`)
- proprietary blend nested child (`Omega-3 Cod Liver Oil`)

**Step 2: Run the cleaner shadow slice**

From `/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts`:

```bash
python3 clean_dsld_data.py --input-dir /tmp/display_ledger_shadow_raw --output-dir /tmp/display_ledger_shadow_out --config config/cleaning_config.json
```

**Step 3: Run the enrichment shadow slice**

```bash
python3 enrich_supplements_v3.py --input-dir /tmp/display_ledger_shadow_out/cleaned --output-dir /tmp/display_ledger_shadow_enriched --config config/enrichment_config.json
```

**Step 4: Verify output**

Confirm:
- display rows include exact label strings
- suppressed parents remain visible in the display ledger
- scoring arrays remain unchanged

**Step 5: Commit**

```bash
git add docs/plans/2026-03-09-display-ledger-design.md
git commit -m "docs: record display ledger verification notes"
```

### Task 8: Final verification

**Files:**
- No new files required

**Step 1: Run integrity and regression commands**

```bash
python3 scripts/db_integrity_sanity_check.py --strict
PYTHONPATH=scripts python3 -m pytest scripts/tests/test_pipeline_regressions.py scripts/tests/test_clean_unmapped_alias_regressions.py scripts/tests/test_provenance_invariants.py scripts/tests/test_contract_validation.py scripts/tests/test_db_integrity.py -q
```

**Step 2: Verify results**

Expected:
- DB integrity clean
- all display-ledger tests pass
- no regression in clean unmapped or existing provenance guarantees

**Step 3: Commit**

```bash
git add .
git commit -m "feat: add user-facing display ledger for label fidelity"
```

Plan complete and saved to `docs/plans/2026-03-09-display-ledger-plan.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?
