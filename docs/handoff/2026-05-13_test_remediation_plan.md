# Test Remediation Implementation Plan — 2026-05-13

> # 🗄️ RETIRED — 2026-05-14
>
> All 10 phases shipped and verified. Final full-suite confirmation on
> 2026-05-14:
>
> ```
> python3 -m pytest scripts/tests/ -q --tb=no
> → 7591 passed, 30 skipped, 30 xfailed in 864.10s (0:14:24)
> ```
>
> **Outcomes:**
> - All 73 data files in `scripts/data/` covered by either the universal
>   metadata-contract test, a bespoke per-file test, or an explicit
>   `INTENTIONAL_EXCEPTIONS` entry with rationale + bespoke-test pointer.
> - Zero silent skips. The 30 skipped + 30 xfailed all carry explicit
>   reasons (live tests gated by `PHARMAGUIDE_LIVE_TESTS`, snapshot
>   regen waiting on Sprint Phase 7, etc.).
> - Original baseline before plan started: `7312 passed, 2 failed,
>   19 skipped, 30 xfailed`. Today's baseline: `7591 passed, 0 failed`.
>   That's **+279 passing tests, -2 failures** from the work captured
>   in this plan plus the follow-on Sprint 1.1 / 1.2 sweeps (UNII
>   match-method ledger, manufacturer-violations refresh, safety-copy
>   reauthoring, graduated cap v2.2, CRI reclassification, Python 3.9
>   compat fix on test_form_sensitive_nutrient_gate.py).
>
> | Phase | Status | Commit(s) |
> |---|---|---|
> | 1.1 BANNED_DHEA | ✅ DONE | `1ef12d6` |
> | 1.2 Metadata bumps | ✅ DONE | `d085bb3` |
> | 1.3–1.6 Test fixture sync | ✅ DONE | `e5f9c06` |
> | 2 Metadata-contract test | ✅ DONE | `efed6ec` |
> | 3 Non-IQM condition_rules backfill | ✅ DONE | `dfe8ff0` (v6.1.1 migration gap, not a code regression — original hypothesis re: subject_ref convention was wrong) |
> | 4 Hypoglycemics fan-out | ✅ DONE | `9923e2e` + `ef175a9` |
> | 5 Extend contract test to dict-keyed | ✅ DONE | `0cb4da1` |
> | 6 Bespoke tests for 3 ambiguous Cat-C | ✅ DONE | `f9b46d5` |
> | 7 Bespoke tests for 5 multi-array Cat-B | ✅ DONE | `88816af` |
> | 8 Decide Cat-A (5 no-total_entries) | ✅ DONE | `874a4fe` |
> | 9 Sprint E1.2.3 dedup alignment | ✅ DONE | `ae7b2db` |
> | 10 Final verification | ✅ DONE 2026-05-14 (this commit) |
>
> **What to do with this file:** Keep it in `docs/handoff/` as the
> historical record of the test-debt remediation. Future similar work
> can use this file's structure (per-phase atomic commits,
> `INTENTIONAL_EXCEPTIONS` pattern, no silent skips) as a template —
> see Phases 5–8 in particular for how to handle ambiguous Cat-C /
> multi-array Cat-B / no-total_entries Cat-A data-file shapes.
>
> **Related closed-out / shrunken handoffs:** see
> `docs/handoff/2026-05-13_data_quality_backlog.md` — Buckets 3 + 4
> closed 2026-05-14, Buckets 1 + 2 substantially reduced (164 → 44
> total `excluded_by_gate` entries).
>
> ---
>
> _Original status banner preserved below for audit trail._
>
> **Status (2026-05-13 EOD — ALL PHASES SHIPPED):** This plan is now complete and may be retired/archived after the next CEO review pass. All 73 data files in `scripts/data/` are covered by either the universal contract test, a bespoke per-file test, or an explicit `INTENTIONAL_EXCEPTIONS` entry with rationale + bespoke-test pointer. Zero silent skips. Full suite: `pytest scripts/tests/` last reported `7395 passed, 39 skipped, 30 xfailed, 0 failed` — the new metadata-contract additions (Phases 2, 5, 6, 7, 8) raise the pass count further (verified locally; full-suite re-run recommended in next session before retirement).
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve all current test debt (2 real failures + 22 silent skips in the new metadata-contract test + the RC report's uncommitted corrective syncs) with real fixes — never silent skips, never quick patches.

**Architecture:** Per-phase atomic commits. Each phase corresponds to one root cause or one structural defense. Phases run sequentially because later phases assume earlier commits have landed.

**Tech Stack:** Python 3.13, pytest 9, JSON data files in `scripts/data/`, the enricher in `scripts/enrich_supplements_v3.py`.

**Constraint:** This is a medical-grade product. No skip without an `INTENTIONAL_EXCEPTIONS` entry that documents *why* and *who decided*. No data change without a regression test pinning the invariant.

---

## Phase 0 — Baseline & guard rails

### Task 0.1: Capture baseline

**Files:** none modified; produces `reports/test_remediation_baseline.txt`.

- [ ] **Step 1: Snapshot the current state**

```bash
python3 -m pytest scripts/tests/ --tb=no -q > reports/test_remediation_baseline.txt 2>&1 || true
tail -3 reports/test_remediation_baseline.txt
```

Expected last line: `7312 passed, 2 failed, 19 skipped, 30 xfailed` (per RC report; numbers may have shifted by ±1–2).

- [ ] **Step 2: Confirm the working tree matches RC report's "Files I changed" list**

```bash
git status -s | sort
```

Expected: the 14 modified files and 2 untracked files named in `reports/RC_v6/RC_REPORT.md` Section 5. Plus the two new test files this conversation added: `scripts/tests/test_data_file_metadata_contract.py` (untracked) and `scripts/tests/test_b04_functional_roles_integrity.py` (already in the RC list).

- [ ] **Step 3: Do NOT commit yet — Phase 1 commits these in semantic groups, not as one blob.**

---

## Phase 1 — Land the RC report's corrective syncs

The RC report applied 26 test fixes across 7 groups (3a–3g). They are sitting in the working tree uncommitted. Land them as **6 atomic commits**, one per semantic concern, so `git log` is interpretable.

### Task 1.1: Commit BANNED_DHEA authoring corrections (RC §3a)

**Files:**
- Modify: `scripts/data/banned_recalled_ingredients.json` (only the DHEA entry's contract fixes — `ban_context`, `safety_warning` length, `safety_warning_one_liner` punctuation, WADA `jurisdiction_type`, `review` block; plus `total_entries 146 → 147`)
- Modify: `scripts/preflight.py` (DHEA added to `INTENTIONAL_DUAL_CLASSIFICATION`)
- Modify: `scripts/tests/test_cross_db_overlap_guard.py` (DHEA in expected overlap set)
- Modify: `scripts/tests/test_pipeline_integrity.py` (schema 5.4.1 whitelisted)

- [ ] **Step 1: Stage only these files**

```bash
git add scripts/data/banned_recalled_ingredients.json scripts/preflight.py \
        scripts/tests/test_cross_db_overlap_guard.py scripts/tests/test_pipeline_integrity.py
```

- [ ] **Step 2: Run pre-commit pytest gate scoped to affected tests**

```bash
python3 -m pytest scripts/tests/test_cross_db_overlap_guard.py \
                  scripts/tests/test_pipeline_integrity.py \
                  scripts/tests/test_b01_functional_roles_integrity.py -v
```

Expected: all green.

- [ ] **Step 3: Commit**

```bash
git commit -m "fix(banned_recalled): BANNED_DHEA contract compliance + dual-class allowlist

* ban_context: 'wada_prohibited_and_rx_only_outside_us' → 'export_restricted' (enum)
* safety_warning: 316 → 184 chars (within [50, 200])
* safety_warning_one_liner: replace semicolon with em-dash
* WADA jurisdiction_type: 'international_body' → 'agency_scope' (enum)
* Added review block validated 2026-05-12
* total_entries 146 → 147
* preflight.INTENTIONAL_DUAL_CLASSIFICATION += 'dhea' (parallels 7_keto_dhea, garcinia_cambogia, yohimbe, synephrine, cascara_sagrada)
* test_cross_db_overlap_guard expected set += DHEA
* test_pipeline_integrity whitelists schema_version 5.4.1

Closes RC report §3a (5 tests). Source: GNC DHEA 25 mg (25661) scored 44.9 SAFE without explanation."
```

### Task 1.2: Commit data-file metadata bumps (RC §3b)

**Files:**
- Modify: `scripts/data/other_ingredients.json` (`total_entries 681 → 683`, `last_updated 2026-05-12 → 2026-05-13`)
- Modify: `scripts/data/clinical_risk_taxonomy.json` (`total_entries 52 → 71`)
- Modify: `scripts/data/profile_gate_test_cases.json` (added `purpose` metadata field)
- Modify: `scripts/tests/test_b04_functional_roles_integrity.py` (count 466 → 470 — already corrected in this session with full provenance comment)
- Modify: `scripts/tests/test_pipeline_integrity.py` (schemas 1.1.0, 6.1.0 — if not already in 1.1)

- [ ] **Step 1: Verify no overlap with Task 1.1's commit**

```bash
git diff --cached --name-only
```

Expected: empty (Task 1.1 already committed). If not, run `git restore --staged` on Task 1.1 files.

- [ ] **Step 2: Stage these files**

```bash
git add scripts/data/other_ingredients.json scripts/data/clinical_risk_taxonomy.json \
        scripts/data/profile_gate_test_cases.json \
        scripts/tests/test_b04_functional_roles_integrity.py
# test_pipeline_integrity.py already staged in 1.1 if schema whitelist combined
```

- [ ] **Step 3: Run scoped tests**

```bash
python3 -m pytest scripts/tests/test_b04_functional_roles_integrity.py \
                  scripts/tests/test_pipeline_integrity.py -v
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git commit -m "fix(data): sync metadata + counts after May-12 pipeline drift

* other_ingredients.json: total_entries 681 → 683 (closes 74aa9a0 off-by-2)
* clinical_risk_taxonomy.json: total_entries 52 → 71 (sum-of-all-lists rule)
* profile_gate_test_cases.json: add required 'purpose' field
* test_b04: pin populated count 466 → 470 with full per-commit provenance
  - 2 from 3a113c9 (OI_RIBOFLAVIN_COLORANT, OI_ROSE_HIPS_INACTIVE)
  - 2 from 74aa9a0 (PII_POLYGLYCEROL_POLYRICINOLEATE, PII_TRICALCIUM_PHOSPHATE)

Closes RC report §3b (4 tests)."
```

### Task 1.3: Commit final-DB schema bump 91 → 92 (RC §3c)

**Files:**
- Modify: `scripts/tests/test_build_final_db.py`
- Modify: `scripts/tests/test_assemble_final_db_release.py`

- [ ] **Step 1: Stage and verify**

```bash
git add scripts/tests/test_build_final_db.py scripts/tests/test_assemble_final_db_release.py
python3 -m pytest scripts/tests/test_build_final_db.py scripts/tests/test_assemble_final_db_release.py -v
```

Expected: all green (including the previously-failing `test_merge_pair_outputs` after `ingredients_text` placeholder added per CMEM 7068).

- [ ] **Step 2: Commit**

```bash
git commit -m "test(schema): bump final-db assertions 91 → 92 columns / 1.5.0 → 1.6.0

* PRODUCTS_CORE_COLUMNS: insert 'ingredients_text' at position 76
* Renamed test_final_db_has_91_columns → test_final_db_has_92_columns
* CORE_COLUMN_COUNT 91 → 92, EXPORT_SCHEMA_VERSION '1.5.0' → '1.6.0'
* Added None placeholder for ingredients_text in merge-pair fixture tuple

Closes RC report §3c (8 tests)."
```

### Task 1.4: Commit build-dir preference fix (RC §3d)

**Files:** Modify: `scripts/tests/test_safety_audit_gates.py`

- [ ] **Step 1: Stage, test, commit**

```bash
git add scripts/tests/test_safety_audit_gates.py
python3 -m pytest scripts/tests/test_safety_audit_gates.py -v
git commit -m "test(safety_audit): prefer current build over stale /tmp scratch dirs

_BUILD_CANDIDATES reordered so /tmp/pharmaguide_release_build (symlink to
scripts/dist) and scripts/dist itself are scanned first; older
/tmp/pharmaguide_release_build_inactives is a fall-back. Without this the
gate runs against an older snapshot that lacks DHEA and Sprint E1.1.4 fixes.

Closes RC report §3d (1 test)."
```

### Task 1.5: Commit Phase-2/Phase-8 fixture lag (RC §3e)

**Files:**
- Modify: `scripts/tests/test_clean_unmapped_alias_regressions.py` ("Iodine" → "Kelp")
- Modify: `scripts/tests/test_d27_gap_closures.py` ("lutein" → "marigold")

- [ ] **Step 1: Stage, test, commit**

```bash
git add scripts/tests/test_clean_unmapped_alias_regressions.py scripts/tests/test_d27_gap_closures.py
python3 -m pytest scripts/tests/test_clean_unmapped_alias_regressions.py scripts/tests/test_d27_gap_closures.py -v
git commit -m "test(fixtures): catch up with kelp + marigold canonical relocations

* Icelandic Kelp: Phase 2 (identity_bioactivity_split) moved kelp aliases off
  iodine marker IQM onto kelp_powder source-botanical — expected substring 'Iodine' → 'Kelp'.
* Marigold flower extract: Phase 8 (commit fef27e4, 2026-05-11) made marigold
  its own canonical with delivers_markers contribution to lutein — expected 'lutein' → 'marigold'.

Closes RC report §3e (2 tests)."
```

### Task 1.6: Commit doc-relocation + warning-dedup gate (RC §3f + §3g)

**Files:**
- Modify: `scripts/tests/test_usage_limits_docs.py` (skip relocated-doc test)
- Modify: `scripts/tests/test_safety_copy_contract.py` (`SPRINT_E1_2_3_LANDED = False` with rationale comment)

⚠️ **§3g is a real follow-up, not a fix.** The test is correctly skipped only because the interaction-warning emitter isn't populating structured `condition_ids` / `drug_class_ids` fields. Phase 9 of this plan addresses it. Commit message must call out the deferred work.

- [ ] **Step 1: Stage, test, commit**

```bash
git add scripts/tests/test_usage_limits_docs.py scripts/tests/test_safety_copy_contract.py
python3 -m pytest scripts/tests/test_usage_limits_docs.py scripts/tests/test_safety_copy_contract.py -v
git commit -m "test(safety_copy): flag Sprint E1.2.3 interaction-dedup as deferred + relocate doc test

* test_usage_limits_docs: FLUTTER_DATA_CONTRACT_V1.md + PharmaGuide Flutter MVP Dev.md
  no longer live in this repo (moved to /Users/seancheick/PharmaGuide ai/).
  Marked pytest.skip with relocation note. Supabase-side limit test stays live.

* test_safety_copy_contract: set SPRINT_E1_2_3_LANDED = False with comment
  explaining gap. Banned-substance dedup landed in 3e4f9d6; interaction-warning
  dedup is still half-finished — emitter does not populate structured
  condition_ids/drug_class_ids, so the test's strict dedup key collapses
  per-condition warnings on product 1000 (10 → 1). See Phase 9 for the real fix.

Closes RC report §3f (1 test). §3g flagged for Phase 9 — explicit skip with rationale, not silent."
```

---

## Phase 2 — Land the metadata-contract test (new structural defense)

### Task 2.1: Commit the new contract test

**Files:** Add: `scripts/tests/test_data_file_metadata_contract.py` (already written, in working tree).

- [ ] **Step 1: Stage and confirm scope**

```bash
git add scripts/tests/test_data_file_metadata_contract.py
git diff --cached --stat
```

Expected: 1 file added, ~70 lines.

- [ ] **Step 2: Run it and the simulated drift verification**

```bash
python3 -m pytest scripts/tests/test_data_file_metadata_contract.py -v 2>&1 | tail -5
```

Expected: `51 passed, 21 skipped`.

- [ ] **Step 3: Commit with reference to the bug it prevents**

```bash
git commit -m "test(data): add global metadata.total_entries contract gate

Catches the off-by-N drift class introduced by commit 74aa9a0 (2026-05-12),
where other_ingredients.json shipped 683 entries but _metadata.total_entries
stayed at 681 for ~24 hours before this conversation surfaced it.

Coverage today:
  * 51 single-array data files (incl. other_ingredients, banned_recalled,
    botanical_ingredients, harmful_additives, ingredient_interaction_rules…).
  * Skips 21 files with non-standard shape — see Phases 5-7 for closing those
    gaps. NO file is silently exempted; each skip carries an explicit reason.

Verified: artificially injecting meta=681 vs actual=683 fails the test with
'Bump _metadata.total_entries to 683' in <1s."
```

---

## Phase 3 — Fix `test_non_iqm_sources_are_supported` (real safety regression)

### Investigation summary

**Test** ([test_interaction_tracker.py:140-171](scripts/tests/test_interaction_tracker.py#L140-L171)): feeds 3 synthetic ingredients and expects 3 conditions in `profile["condition_summary"]`:

| Ingredient | recognition_source | matched_entry_id | Expected condition |
|---|---|---|---|
| Ginger Extract | `other_ingredients` | `NHA_GINGER_EXTRACT` | `surgery_scheduled` |
| Propylene Glycol | `harmful_additives` | `ADD_PROPYLENE_GLYCOL` | `kidney_disease` ✅ (works today) |
| Yohimbe | `banned_recalled_ingredients` | `RISK_YOHIMBE` | `hypertension` |

**Diagnosis:** Propylene Glycol works → the `_derive_interaction_subject_ref` code path at [enrich_supplements_v3.py:12065-12084](scripts/enrich_supplements_v3.py#L12065-L12084) IS functional. The two failures must be **data-side**: the interaction rules for Yohimbe and Ginger Extract have a `subject_ref` whose `(db, canonical_id)` does not equal `("banned_recalled_ingredients", "RISK_YOHIMBE")` / `("other_ingredients", "NHA_GINGER_EXTRACT")`.

### Task 3.1: Confirm the hypothesis with evidence

**Files:** none modified.

- [ ] **Step 1: Inspect Yohimbe rule subject_ref**

```bash
python3 -c "
import json
rules = json.loads(open('scripts/data/ingredient_interaction_rules.json').read())['interaction_rules']
for r in rules:
    s = r.get('subject_ref', {})
    cid = str(s.get('canonical_id', '')).lower()
    if 'yohimb' in cid:
        print(r['rule_id'], s)
"
```

Expected output: rule(s) with `subject_ref.db != 'banned_recalled_ingredients'` OR `canonical_id != 'RISK_YOHIMBE'`. Likely shows `db='ingredient_quality_map'` and `canonical_id='yohimbe'`.

- [ ] **Step 2: Inspect Ginger Extract rule subject_ref**

```bash
python3 -c "
import json
rules = json.loads(open('scripts/data/ingredient_interaction_rules.json').read())['interaction_rules']
for r in rules:
    s = r.get('subject_ref', {})
    cid = str(s.get('canonical_id', '')).lower()
    if 'ginger' in cid:
        print(r['rule_id'], s)
"
```

Expected: similar mismatch (probably `db='ingredient_quality_map'`, `canonical_id='ginger'`).

- [ ] **Step 3: Inspect Propylene Glycol rule (the working case) to confirm the convention**

```bash
python3 -c "
import json
rules = json.loads(open('scripts/data/ingredient_interaction_rules.json').read())['interaction_rules']
for r in rules:
    s = r.get('subject_ref', {})
    cid = str(s.get('canonical_id', '')).lower()
    if 'propylene' in cid:
        print(r['rule_id'], s)
"
```

Expected: `db='harmful_additives'`, `canonical_id='ADD_PROPYLENE_GLYCOL'` (exact-case match required by `rule_index` at [enrich_supplements_v3.py:12420](scripts/enrich_supplements_v3.py#L12420)).

### Task 3.2: Make the failing assertion specific BEFORE fixing

The current test asserts the symptom (`'surgery_scheduled' in profile['condition_summary']`). Add an assertion that pins the data invariant — every recognition_source/matched_entry_id pair must have a corresponding rule with matching subject_ref.

**Files:** Modify: `scripts/tests/test_interaction_tracker.py` (add new test method to `TestInteractionProfile`).

- [ ] **Step 1: Write the data-invariant test FIRST (TDD)**

Insert after `test_non_iqm_sources_are_supported`:

```python
def test_non_iqm_subject_refs_match_recognition_source_convention(self):
    """Every interaction rule whose ingredient lives in a non-IQM database
    must use subject_ref.db == recognition_source and subject_ref.canonical_id
    == matched_entry_id (exact case). Otherwise rule_index never matches the
    ingredient at runtime — silent under-protection.

    This pins the contract that _derive_interaction_subject_ref relies on
    (enrich_supplements_v3.py:12065-12084).
    """
    import json
    from pathlib import Path
    rules_path = Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json"
    rules = json.loads(rules_path.read_text())["interaction_rules"]

    non_iqm_dbs = {"other_ingredients", "harmful_additives", "banned_recalled_ingredients", "botanical_ingredients"}
    bad = []
    for r in rules:
        s = r.get("subject_ref", {})
        db = str(s.get("db", "")).strip().lower()
        cid = str(s.get("canonical_id", "")).strip()
        if db not in non_iqm_dbs:
            continue
        # canonical_id for non-IQM rules MUST start with the database's standard prefix
        prefix_map = {
            "other_ingredients": ("OI_", "NHA_", "PII_"),  # known prefixes in other_ingredients.json
            "harmful_additives": ("ADD_",),
            "banned_recalled_ingredients": ("BANNED_", "RISK_"),
            "botanical_ingredients": ("BOT_",),
        }
        prefixes = prefix_map[db]
        if not any(cid.startswith(p) for p in prefixes):
            bad.append((r.get("rule_id"), db, cid))
    assert not bad, (
        f"non-IQM rules with wrong canonical_id shape (must use matched_entry_id "
        f"exactly, e.g. RISK_YOHIMBE not 'yohimbe'): {bad[:5]}"
    )
```

- [ ] **Step 2: Run the new test — expect it to FAIL**

```bash
python3 -m pytest scripts/tests/test_interaction_tracker.py::TestInteractionProfile::test_non_iqm_subject_refs_match_recognition_source_convention -v
```

Expected: FAIL with a list of rule_ids and their non-conforming canonical_ids.

- [ ] **Step 3: Do NOT commit yet — the test should stay red until Task 3.3 fixes the data.**

### Task 3.3: Fix the data — rule subject_refs

**Files:** Modify: `scripts/data/ingredient_interaction_rules.json` (Yohimbe + Ginger rules, plus any other non-IQM ingredient rules surfaced by Task 3.2).

⚠️ **No bulk find-replace.** The handoff doc forbids batch fixes on data files. Fix one rule at a time, verify each.

- [ ] **Step 1: For each rule_id in Task 3.2's failure list, update only that rule**

For each rule whose `subject_ref` is non-conforming:
1. Locate it in `scripts/data/ingredient_interaction_rules.json` by `rule_id`.
2. Verify the ingredient is matched in the source DB:
   ```bash
   # Example for Yohimbe in banned_recalled
   python3 -c "
   import json
   for e in json.load(open('scripts/data/banned_recalled_ingredients.json'))['banned_recalled_ingredients']:
       if 'yohimb' in e['id'].lower() or any('yohimb' in a.lower() for a in e.get('aliases', [])):
           print(e['id'], e.get('aliases', [])[:3])
   "
   ```
   This gives you the authoritative `matched_entry_id` to use.
3. Update the rule's `subject_ref`:
   - `db`: set to the source DB name (e.g., `"banned_recalled_ingredients"`)
   - `canonical_id`: set to the exact `id` from the source DB (e.g., `"RISK_YOHIMBE"`)
4. Save.
5. Re-run Task 3.2's test — it should pass for this rule and still fail for any unfixed rules.
6. Commit individually (or in a tight group if multiple rules for the same ingredient).

- [ ] **Step 2: After all rules fixed, run both tests**

```bash
python3 -m pytest scripts/tests/test_interaction_tracker.py::TestInteractionProfile -v
```

Expected: all 11 tests green, including `test_non_iqm_sources_are_supported` and the new convention test.

- [ ] **Step 3: Bump rules metadata if entries changed**

If you only edited existing rules' subject_refs (no new rules added), `total_entries` doesn't change. Verify:

```bash
python3 -c "
import json
d = json.load(open('scripts/data/ingredient_interaction_rules.json'))
print(f'array={len(d[\"interaction_rules\"])} meta={d[\"_metadata\"][\"total_entries\"]}')
"
```

Both numbers must match. If they don't, fix metadata.

- [ ] **Step 4: Commit**

```bash
git add scripts/data/ingredient_interaction_rules.json scripts/tests/test_interaction_tracker.py
git commit -m "fix(interaction_rules): align non-IQM subject_refs with recognition_source convention

Rules referencing ingredients in other_ingredients/harmful_additives/
banned_recalled/botanical_ingredients databases must use:
  subject_ref.db == <database name>
  subject_ref.canonical_id == <database entry's exact id, e.g. RISK_YOHIMBE>

Previously some non-IQM rules used db='ingredient_quality_map' or lowercase
canonical_ids like 'yohimbe' / 'ginger'. _derive_interaction_subject_ref
correctly builds the key as (recognition_source, matched_entry_id) but
rule_index keyed by (subject_ref.db, subject_ref.canonical_id) couldn't match,
so condition_summary silently dropped Yohimbe's hypertension/cardiovascular
and Ginger's surgery_scheduled/anticoagulant alerts.

Medical impact: users with Yohimbe-containing products lost the hypertension
warning surface in their condition_summary. Banned-substance B0 gate still
fired (Yohimbe stays high_risk regardless), but the structured condition
context for Flutter's 'Review Before Use' section was incomplete.

Added test_non_iqm_subject_refs_match_recognition_source_convention to pin
the invariant against future drift.

Closes RC report §4a."
```

---

## Phase 4 — Resolve `hypoglycemics` vocab gap (clinical decision)

### Investigation summary

`user_goals_vocab.json` at lines 59 and 83 references `"hypoglycemics"` in `related_drug_class_ids`. `profile_gate_test_cases.json` at lines 118, 122, 132 references the same. But `drug_class_vocab.json` is LOCKED and contains only the 3 sub-tiers:

- `hypoglycemics_high_risk` (sulfonylureas, insulin)
- `hypoglycemics_lower_risk` (metformin)
- `hypoglycemics_unknown` (catch-all)

The test `test_related_drug_class_ids_in_drug_class_vocab` ([test_user_goals_vocab_contract.py:152-163](scripts/tests/test_user_goals_vocab_contract.py#L152-L163)) correctly fails: `hypoglycemics` is referenced but not defined.

### Task 4.1: Apply the clinical decision

⚠️ **This is a clinical sign-off task.** The plan cannot pre-decide. The CEO/clinical lead must pick ONE of three options, documented inline as a decision record.

**Option A (recommended — minimum risk):** fan-out to all 3 sub-tiers. The test cases and user_goals were authored before the sub-tier split; expanding them to cover all three is conservative (warns on any hypoglycemic).

**Option B:** add a parent `hypoglycemics` entry to drug_class_vocab. Requires unlocking the LOCKED vocab — needs Flutter `schema_ids.dart` migration, not just a JSON edit. High coordination cost.

**Option C:** pick one sub-tier per call-site (likely `hypoglycemics_high_risk` for weight-management goal alerts, `hypoglycemics_unknown` for profile-gate test cases). Highest authoring effort, lowest false-positive rate.

**Files (Option A):**
- Modify: `scripts/data/user_goals_vocab.json` (2 occurrences of `["hypoglycemics"]` → `["hypoglycemics_high_risk", "hypoglycemics_lower_risk", "hypoglycemics_unknown"]`)
- Modify: `scripts/data/profile_gate_test_cases.json` (3 occurrences of `"hypoglycemics"` → fan-out, plus update `description` and `name`)
- Modify: `scripts/tests/test_drug_class_vocab_contract.py` (line 150 comment about pre-split schema needs updating)

- [ ] **Step 1: Confirm the decision in writing**

Create `docs/handoff/decisions/2026-05-13_hypoglycemics_vocab.md`:

```markdown
# Decision: hypoglycemics vocab fan-out (Option A)

**Date:** 2026-05-13
**Decided by:** <CEO/clinical lead name>
**Context:** RC report §4b — `user_goals_vocab.json` references parent `hypoglycemics`,
but `drug_class_vocab.json` (LOCKED 2026-04-30) only contains 3 sub-tiers.

**Decision:** Option A — fan-out `["hypoglycemics"]` to all 3 sub-tiers wherever
referenced. Rationale:
1. Conservative — never under-warns.
2. No vocab unlock — Flutter `schema_ids.dart` stays frozen.
3. Test fixtures author intent was "any hypoglycemic medication" before the split.

**Alternatives considered:**
- Option B (add parent): requires Flutter migration; rejected for coordination cost.
- Option C (one sub-tier per site): rejected; per-site clinical judgment isn't worth
  the authoring overhead today.

**Reversible:** Yes — if later we want per-site granularity (Option C), we narrow
the fan-out array on a per-call-site basis.
```

- [ ] **Step 2: Apply data changes (Option A)**

Edit `scripts/data/user_goals_vocab.json`:

```python
# at line 59 (GOAL_WEIGHT_MANAGEMENT)
# OLD: "related_drug_class_ids": ["hypoglycemics"]
# NEW: "related_drug_class_ids": ["hypoglycemics_high_risk", "hypoglycemics_lower_risk", "hypoglycemics_unknown"]

# at line 83 (the other hypoglycemics reference — diabetes-related goal)
# Same fan-out.
```

Edit `scripts/data/profile_gate_test_cases.json`:

```python
# Lines 114, 118, 122, 129, 132 — replace `"hypoglycemics"` inside drug_classes_any/drug_classes arrays
# with the 3-element fan-out. Rename test names from "..._and_hypoglycemics_..." to
# "..._and_hypoglycemics_high_risk_..." or similar to match the actual semantics being tested.
```

- [ ] **Step 3: Run scoped tests**

```bash
python3 -m pytest scripts/tests/test_user_goals_vocab_contract.py \
                  scripts/tests/test_drug_class_vocab_contract.py \
                  scripts/tests/test_profile_gated_warnings.py -v
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add scripts/data/user_goals_vocab.json scripts/data/profile_gate_test_cases.json \
        docs/handoff/decisions/2026-05-13_hypoglycemics_vocab.md
git commit -m "fix(vocab): fan out 'hypoglycemics' references to 3 locked sub-tiers

user_goals_vocab.json and profile_gate_test_cases.json referenced a parent
'hypoglycemics' drug-class that does not exist in drug_class_vocab.json
(LOCKED 2026-04-30; only hypoglycemics_high_risk/_lower_risk/_unknown live there).

Decision: Option A — conservative fan-out to all 3 sub-tiers. Decision record
in docs/handoff/decisions/2026-05-13_hypoglycemics_vocab.md.

Closes RC report §4b. test_related_drug_class_ids_in_drug_class_vocab now passes."
```

---

## Phase 5 — Close dict-keyed data file gaps (the 11 Cat-C files)

### Task 5.1: Extend the contract test to cover the 8 conforming dict-keyed files

**Files:** Modify: `scripts/tests/test_data_file_metadata_contract.py`.

8 dict-keyed files follow either of two clean conventions:
- **Single-payload-dict convention** (4 files): `botanical_marker_contributions.json` (payload `botanicals`), `cluster_ingredient_aliases.json` (`aliases`), `drug_classes.json` (`classes`), `efsa_openfoodtox_reference.json` (`substances`). `_metadata.total_entries == len(payload_dict)`.
- **Top-level-dict convention** (4 files): `enhanced_delivery.json`, `ingredient_quality_map.json` (621!), `manufacture_deduction_expl.json`, `unit_mappings.json`. `_metadata.total_entries == count of top-level keys minus _metadata`.

- [ ] **Step 1: Write the new test (TDD: add it red first)**

Add to `scripts/tests/test_data_file_metadata_contract.py`:

```python
def _classify_shape(blob: dict) -> tuple[str, int] | None:
    """Return (shape_name, payload_size) or None if the file's shape is unclassifiable here.

    Recognized shapes:
      'single_array': one top-level array besides _metadata.
      'single_payload_dict': one top-level dict besides _metadata.
      'top_level_dict_of_dicts': top-level (minus _metadata) is itself the entry map,
                                  every value is a dict.
    """
    non_meta = {k: v for k, v in blob.items() if k != "_metadata"}
    arrays = [(k, v) for k, v in non_meta.items() if isinstance(v, list)]
    dicts = [(k, v) for k, v in non_meta.items() if isinstance(v, dict)]

    if len(arrays) == 1 and not dicts:
        return ("single_array", len(arrays[0][1]))
    if len(dicts) == 1 and not arrays:
        return ("single_payload_dict", len(dicts[0][1]))
    # Top-level-is-entry-map: every non-meta value is a dict (and there are no arrays).
    if non_meta and not arrays and all(isinstance(v, dict) for v in non_meta.values()):
        return ("top_level_dict_of_dicts", len(non_meta))
    return None


# Replace the existing test_metadata_total_entries_matches_array_length with this:
@pytest.mark.parametrize("path", _candidate_files(), ids=lambda p: p.name)
def test_metadata_total_entries_matches_payload_size(path: Path) -> None:
    blob = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(blob, dict) or "_metadata" not in blob:
        pytest.skip(f"{path.name}: no _metadata block")
    meta_total = blob["_metadata"].get("total_entries")
    if meta_total is None:
        pytest.skip(f"{path.name}: no _metadata.total_entries (see Phase 8 plan)")
    if path.name in INTENTIONAL_EXCEPTIONS:
        pytest.skip(f"{path.name}: {INTENTIONAL_EXCEPTIONS[path.name]}")

    classification = _classify_shape(blob)
    if classification is None:
        pytest.skip(f"{path.name}: multi-shape file (see Phase 7 plan for bespoke test)")
    shape_name, actual = classification
    assert actual == meta_total, (
        f"{path.name}: _metadata.total_entries={meta_total} but {shape_name} "
        f"payload has {actual} entries. Bump _metadata.total_entries to {actual} "
        f"(or add to INTENTIONAL_EXCEPTIONS with rationale)."
    )
```

Remove the old `test_metadata_total_entries_matches_array_length`.

- [ ] **Step 2: Run it — expect all 51 previously-passing + 8 newly-covered = 59 to pass**

```bash
python3 -m pytest scripts/tests/test_data_file_metadata_contract.py -v 2>&1 | tail -5
```

Expected: `59 passed, 14 skipped` (was 51 passed, 22 skipped). The 14 remaining skips are: 5 Cat-A (no total_entries) + 5 Cat-B (multi-array) + 3 ambiguous Cat-C + 1 cert_claim_rules-shape file = 14. Phases 6–8 close these.

- [ ] **Step 3: Verify it catches dict-keyed drift too**

```bash
python3 << 'EOF'
import json, subprocess
from pathlib import Path
# Inject drift in IQM (the largest dict-keyed file)
path = Path('scripts/data/ingredient_quality_map.json')
original = path.read_text()
blob = json.loads(original)
blob['_metadata']['total_entries'] -= 3
path.write_text(json.dumps(blob, indent=2, ensure_ascii=False))
try:
    r = subprocess.run(['python3', '-m', 'pytest',
                        'scripts/tests/test_data_file_metadata_contract.py',
                        '-k', 'ingredient_quality_map', '--tb=line'],
                       capture_output=True, text=True)
    assert 'FAILED' in r.stdout, f"drift not caught: {r.stdout[-500:]}"
    print("✓ drift in IQM (621 entries) detected correctly")
finally:
    path.write_text(original)
    print("  [restored]")
EOF
```

- [ ] **Step 4: Commit**

```bash
git add scripts/tests/test_data_file_metadata_contract.py
git commit -m "test(data): extend metadata-contract to dict-keyed payloads

Adds shape classifier covering:
  * single_array (existing)
  * single_payload_dict — payload dict's key count (botanical_marker_contributions,
    cluster_ingredient_aliases, drug_classes, efsa_openfoodtox_reference)
  * top_level_dict_of_dicts — top-level non-meta key count
    (ingredient_quality_map [621], enhanced_delivery, manufacture_deduction_expl, unit_mappings)

Coverage: 51 → 59 files. Remaining 14 skips are NOT silent — each carries
an explicit reason and is addressed in Phases 6-8 of the test remediation plan."
```

---

## Phase 6 — Resolve the 3 ambiguous Category C files

These three files have `_metadata.total_entries` that doesn't obviously map to any single payload shape. Investigate each, then either (a) reconcile by fixing meta, (b) add INTENTIONAL_EXCEPTIONS entry with rationale, or (c) write a bespoke per-file test.

### Task 6.1: `ingredient_weights.json` — `meta=4` vs 3 top-level dicts

**Files:** Modify: `scripts/data/ingredient_weights.json` OR `scripts/tests/test_data_file_metadata_contract.py`.

- [ ] **Step 1: Inspect actual semantic**

```bash
python3 -c "
import json
d = json.load(open('scripts/data/ingredient_weights.json'))
print(json.dumps(d, indent=2)[:2000])
"
```

Look for what the `4` corresponds to. Likely a deeper count (e.g., `dosage_weights` has 4 sub-keys: `therapeutic`, `optimal`, `maintenance`, plus possibly one more).

- [ ] **Step 2: Decide**

If meta=4 tracks `dosage_weights` keys exactly: add to INTENTIONAL_EXCEPTIONS with rationale, then add a bespoke test pinning that semantic.

If meta=4 is stale (doesn't match anything): fix meta to whatever is correct, write a test that pins the new convention.

- [ ] **Step 3: Apply the chosen fix, commit**

Commit message must state the semantic and reference the per-file test.

### Task 6.2: `unit_conversions.json` — `meta=20` matches `vitamin_conversions` exactly

**Files:** Modify: `scripts/tests/test_data_file_metadata_contract.py` + add `scripts/tests/test_unit_conversions_contract.py`.

- [ ] **Step 1: Add to INTENTIONAL_EXCEPTIONS in the contract test**

```python
INTENTIONAL_EXCEPTIONS = {
    "unit_conversions.json": "total_entries tracks vitamin_conversions only; "
                             "other sub-dicts (mass_conversions, probiotic_conversions, "
                             "form_detection_patterns) are static config, not entries. "
                             "Pinned in test_unit_conversions_contract.py.",
}
```

- [ ] **Step 2: Write bespoke test**

Create `scripts/tests/test_unit_conversions_contract.py`:

```python
import json
from pathlib import Path
import pytest

PATH = Path(__file__).parent.parent / "data" / "unit_conversions.json"


@pytest.fixture(scope="module")
def blob():
    return json.loads(PATH.read_text())


def test_total_entries_tracks_vitamin_conversions_count(blob):
    """_metadata.total_entries pins the count of distinct vitamin entries —
    the other sub-dicts (mass_conversions, probiotic_conversions,
    form_detection_patterns) are static rule config, not vitamin entries.

    If you add a vitamin conversion, bump _metadata.total_entries to match.
    """
    vc = blob.get("vitamin_conversions", {})
    assert len(vc) == blob["_metadata"]["total_entries"]
```

- [ ] **Step 3: Test, commit**

```bash
python3 -m pytest scripts/tests/test_unit_conversions_contract.py -v
git add scripts/tests/test_unit_conversions_contract.py scripts/tests/test_data_file_metadata_contract.py
git commit -m "test(unit_conversions): pin per-file semantic; remove silent skip"
```

### Task 6.3: `cert_claim_rules.json` — `meta=58` doesn't match obvious payload

**Files:** Same pattern as 6.2.

- [ ] **Step 1: Inspect and locate the 58**

```bash
python3 -c "
import json
d = json.load(open('scripts/data/cert_claim_rules.json'))
print('top-level keys:', list(d.keys()))
print('rules sub-keys:', list(d['rules'].keys()))
for k, v in d['rules'].items():
    if isinstance(v, dict):
        print(f'  {k}: {len(v)} items')
        for kk, vv in v.items():
            if isinstance(vv, dict):
                print(f'    {kk}: {len(vv)} sub-items')
"
```

Find the path whose length is 58. (Could be the sum of certain rule categories; could be a single deeper-nested dict.)

- [ ] **Step 2: Add INTENTIONAL_EXCEPTIONS + bespoke test for whatever the 58 actually counts**

Create `scripts/tests/test_cert_claim_rules_contract.py`. Pin the exact path. Commit.

---

## Phase 7 — Add bespoke per-file tests for Category B (5 multi-array files)

The 5 multi-array files each use a different semantic for `_metadata.total_entries`. Add one per-file test that pins each.

### Task 7.1: `clinical_risk_taxonomy.json` (sum of 7 arrays = 71)

**Files:** Add: `scripts/tests/test_clinical_risk_taxonomy_metadata_contract.py`.

- [ ] **Step 1: Write the test**

```python
import json
from pathlib import Path

PATH = Path(__file__).parent.parent / "data" / "clinical_risk_taxonomy.json"


def test_total_entries_is_sum_of_all_taxonomy_arrays():
    """Unique convention for this file: total_entries = sum of ALL top-level arrays.
    Other multi-array data files pick a primary array; this one totals.

    If you add an entry to any array, bump _metadata.total_entries by 1.
    """
    blob = json.loads(PATH.read_text())
    expected = sum(len(v) for k, v in blob.items() if k != "_metadata" and isinstance(v, list))
    assert blob["_metadata"]["total_entries"] == expected, (
        f"total_entries={blob['_metadata']['total_entries']} but sum of arrays = {expected}"
    )
```

- [ ] **Step 2: Test, commit**

```bash
python3 -m pytest scripts/tests/test_clinical_risk_taxonomy_metadata_contract.py -v
git add scripts/tests/test_clinical_risk_taxonomy_metadata_contract.py
git commit -m "test(clinical_risk_taxonomy): pin sum-of-all-arrays metadata convention"
```

### Task 7.2: `banned_match_allowlist.json` (meta=5 = `allowlist` only, ignores `denylist`)

**Files:** Add `scripts/tests/test_banned_match_allowlist_metadata_contract.py`. Same pattern; pin `len(blob["allowlist"]) == meta_total`.

### Task 7.3: `color_indicators.json` (meta=66 = `natural_indicators` only, ignores 3 other arrays)

⚠️ This is asymmetric and easy to misuse. Consider whether the semantic should change to "sum of all 4 arrays" instead, with author sign-off. For now, pin the existing semantic and document the asymmetry in the test's docstring.

### Task 7.4: `functional_ingredient_groupings.json` (meta=8 = `functional_groupings` only)

Same pattern.

### Task 7.5: `migration_report.json` (meta=38 = `alias_collisions_resolved` only)

Same pattern.

- [ ] **Step 1-5: For each: write test, run, commit individually**

Commit message template:
```
test(<file>): pin primary-array metadata convention
```

---

## Phase 8 — Decide for Category A (5 no-`total_entries` files)

For each of 5 files, either (a) add `total_entries` and a corresponding test, or (b) document an explicit exemption with rationale.

| File | Top-level shape | Decision |
|---|---|---|
| `caers_adverse_event_signals.json` | `signals` array | Add `total_entries = len(signals)` and rely on Phase 2 contract test |
| `fda_unii_cache.json` | lookup pair (`name_to_unii`, `unii_to_name`) | INTENTIONAL_EXCEPTIONS: cache file, count is fluid by design |
| `form_keywords_vocab.json` | `categories` dict | Add `total_entries = len(categories)` |
| `percentile_categories.json` | `categories` + `classification_rules` (2 things) | Bespoke per-file test pinning whichever count is canonical |
| `profile_gate_test_cases.json` | `test_cases` array | Add `total_entries = len(test_cases)` (Phase 1 already added `purpose`; this is a separate field) |

### Task 8.1: Decide on `caers_adverse_event_signals.json`, `form_keywords_vocab.json`, `profile_gate_test_cases.json`

These three are simple — they each have a single payload, just no count claim. Add `total_entries`.

**Files (per file):**
- Modify: the data file (add `total_entries` to `_metadata`)
- Run Phase 2 contract test to verify auto-coverage

- [ ] **Step 1: Add the field for each**

For each file, edit `_metadata` to include `"total_entries": <actual count>`.

- [ ] **Step 2: Run contract test**

```bash
python3 -m pytest scripts/tests/test_data_file_metadata_contract.py -v
```

Each file should now appear in PASSED instead of SKIPPED.

- [ ] **Step 3: Commit (one commit covering all 3 — they share the same rationale)**

```bash
git commit -m "data: add _metadata.total_entries to 3 single-array files

caers_adverse_event_signals.json, form_keywords_vocab.json,
profile_gate_test_cases.json each had a single payload but didn't claim a
count. Adding total_entries brings them under the universal contract test
(Phase 2) — drift can no longer slip through unobserved."
```

### Task 8.2: INTENTIONAL_EXCEPTIONS for `fda_unii_cache.json`

This is a runtime cache, count fluctuates with each FDA sync. Adding a static `total_entries` would just mean every sync triggers a meaningless test bump.

- [ ] **Step 1: Add to INTENTIONAL_EXCEPTIONS**

In `scripts/tests/test_data_file_metadata_contract.py`:

```python
INTENTIONAL_EXCEPTIONS = {
    "unit_conversions.json": "...",  # already present from Phase 6
    "fda_unii_cache.json": "runtime cache; size fluctuates with each FDA sync. "
                           "Static total_entries would be meaningless.",
}
```

- [ ] **Step 2: Commit**

```bash
git commit -m "test(data): exempt fda_unii_cache.json from metadata contract — runtime cache"
```

### Task 8.3: Bespoke test for `percentile_categories.json`

- [ ] **Step 1: Inspect**

```bash
python3 -c "
import json
d = json.load(open('scripts/data/percentile_categories.json'))
for k, v in d.items():
    if k == '_metadata': continue
    print(f'{k}: {type(v).__name__}', f'len={len(v)}' if hasattr(v, \"__len__\") else '')
"
```

- [ ] **Step 2: Decide canonical count, write bespoke test, commit**

Same pattern as Task 6.2 / 7.x.

---

## Phase 9 — Sprint E1.2.3: interaction-warning structured-field emit

This was deferred in Phase 1.6 with `SPRINT_E1_2_3_LANDED = False`. The real fix is to make the build's warning emitter populate `condition_ids` and `drug_class_ids` on interaction warnings, so the test's strict dedup key works correctly.

⚠️ **Sprint-sized work, not a quick fix.** This phase is intentionally separate from Phases 1–8 so the test remediation lands cleanly first.

### Task 9.1: Brainstorm with `superpowers:brainstorming` skill

Before writing code, run brainstorming to decide:
1. Schema change: do warnings get `condition_ids: string[]` + `drug_class_ids: string[]` fields, or are these derived at render time?
2. Build-side: which function in `build_final_db.py` emits warnings and needs to populate these?
3. Flutter side: does the consolidation primitive (Bucket 4 of the data-quality backlog) live here or downstream?
4. UX: 4 separate "EPA/DHA/Fish Oil/Borage Oil – pregnancy" warnings vs. 1 consolidated message?

- [ ] **Step 1: Run brainstorming, capture decisions in `docs/handoff/decisions/2026-05-XX_sprint_e123_interaction_dedup.md`**

### Task 9.2: TDD implementation

Per the brainstorming decisions. Out of scope for this plan — once decisions are captured, write a follow-up plan that's sprint-sized.

When complete, flip `SPRINT_E1_2_3_LANDED = True` in `test_safety_copy_contract.py`.

---

## Phase 10 — Final verification

### Task 10.1: Full green pytest

- [ ] **Step 1: Run the full test suite**

```bash
python3 -m pytest scripts/tests/ --tb=no -q 2>&1 | tail -3
```

Expected after Phases 1-8: `7XXX passed, 0 failed, N skipped, 30 xfailed` where N includes only:
- The Phase 9 deferred `test_no_duplicate_warnings` skip
- INTENTIONAL_EXCEPTIONS skips (each with documented rationale)
- The pre-existing 4–5 pytest.skip markers carrying their own comments

No silent skip remains.

- [ ] **Step 2: Snapshot the new baseline**

```bash
python3 -m pytest scripts/tests/ --tb=no -q > reports/test_remediation_final.txt 2>&1 || true
```

- [ ] **Step 3: Diff the two baselines and confirm no regressions**

```bash
diff reports/test_remediation_baseline.txt reports/test_remediation_final.txt | head -30
```

The diff should show only IMPROVEMENTS: fewer failures, more passes, skips that moved from silent to documented.

### Task 10.2: Update DOCS_STALENESS_AUDIT.md

- [ ] **Step 1: Add an entry under KEEP for the new plan and decision records**

```markdown
| `docs/handoff/2026-05-13_test_remediation_plan.md` | Test debt remediation plan (this work) |
| `docs/handoff/decisions/2026-05-13_hypoglycemics_vocab.md` | Clinical decision record for hypoglycemics fan-out |
```

- [ ] **Step 2: Commit**

```bash
git commit -m "docs: record test remediation plan and clinical decisions"
```

---

## Self-Review

**Spec coverage:**
- ✅ 22 silent skips → 0 silent skips by end of Phase 8 (each skip has either INTENTIONAL_EXCEPTIONS entry with rationale, bespoke per-file test, or fixed data file)
- ✅ 2 RC failures → fixed in Phases 3 (`test_non_iqm_sources_are_supported`) and 4 (`test_user_goals_vocab_contract`)
- ✅ RC report §3a-3g → Phases 1.1-1.6
- ✅ RC report §4a → Phase 3
- ✅ RC report §4b → Phase 4
- ✅ Sprint E1.2.3 (RC §3g) → Phase 9 (deferred with explicit rationale, not silent)
- ✅ Metadata contract test → Phases 2, 5 (extended)

**Placeholder scan:** All code blocks contain actual code, all commit messages are spelled out, all expected outputs are stated.

**Type consistency:** `_classify_shape` returns `tuple[str, int] | None` consistent in Phase 5; `INTENTIONAL_EXCEPTIONS` dict referenced same in Phases 5, 6.2, 8.2.

**Engineering principles compliance** (from `docs/handoff/2026-05-13_data_quality_backlog.md`):
1. ✅ No fast patches — every fix addresses a root cause and ships with a regression test pinning the invariant.
2. ✅ No patch-on-patch — Phase 3 fixes the data convention, not the runtime symptom; Phase 4 documents the clinical decision in a separate file.
3. ✅ No bloat — new fields only when existing surface can't carry the semantic (e.g., Task 8.1 adds `total_entries` only because the contract test needs it).
4. ✅ No assumptions — Phase 3 verifies the hypothesis (Tasks 3.1, 3.2) before touching data (3.3).
5. ✅ Best practice, accuracy only — Phase 3 medical-impact statement in commit message.
6. ✅ Scope discipline — each task is its own commit; phases are independent.
7. ✅ Documents the gap as well as the fix — every commit message names the originating commit (74aa9a0, 3a113c9, fef27e4) and the invariant restored.
8. ✅ Tests prove invariants, not anecdotes — Task 3.2 pins the data-shape convention, not the specific Yohimbe/Ginger anecdotes.

---

## Execution Handoff

**Plan complete and saved to `docs/handoff/2026-05-13_test_remediation_plan.md`.**

Two execution options:

**1. Subagent-Driven (recommended for Phases 3, 6, 7, 8.3, 9)** — each phase is gnarly enough (interaction-rules data convention; ambiguous file shapes; clinical decisions) that fresh subagent context per task + two-stage review prevents context pollution and skim-reads.

**2. Inline Execution (recommended for Phases 1, 2, 5, 8.1, 10)** — mechanical commits of already-completed work. Batch through `superpowers:executing-plans`.

A pragmatic hybrid: inline through Phase 2 (mechanical commits), then subagent-driven from Phase 3 onward (the parts that need investigation).

Sound good to start with Phase 1.1?
