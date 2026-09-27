# Known Test Failures — active tracking

**Created:** 2026-05-14 (during Sprint 1.1)
**Owner:** Sean Cheick
**Purpose:** Track active test failures that need attention but don't
yet have a fix landed. Each entry must cite an origin commit, describe
the failure, document why it's not blocking the current work, and state
an acceptance criterion for resolution.

This file is a contract: **do not casually dismiss a test failure.** If a
new failure surfaces, EITHER fix it OR add an entry here with full
provenance before continuing.

## How to use this file

1. Run the suite. If it fails:
   - Check if the failure is listed below. If yes → confirm the diff and
     scope hasn't changed; proceed only if true.
   - If no → STOP. Either fix the test, or add an entry here first.
2. The file is reviewed at the start of every sprint. Stale entries
   (origin commit ≥30 days old, no movement) escalate.
3. Resolved entries are archived to `docs/archive/` with a dated
   filename so this active doc stays lean. The full audit trail lives
   in the archive, not here.

## Test-suite issues tracked

**Active:** 0 — all entries currently resolved.

**Latest broader-suite count after the 2026-05-14 sweep:** all
strict-validator tests green (`test_safety_copy_production` 4/4 +
`test_validate_safety_copy` 55/55), `test_safety_copy_contract` suite
green, `test_form_sensitive_nutrient_gate.py` now collects + passes all
23 tests on Python 3.9. Full suite: **7591 passed, 30 skipped (all
intentional), 30 xfailed (all intentional), 0 failed**.

## Active issues (0)

_None at this time._

## Resolution archive

Entries that have been resolved are archived to keep this file lean:

- `docs/archive/KNOWN_FAILURES_resolved_2026_05_14.md` — 6 entries
  resolved 2026-05-14 (strict-validator phrasing on 2026-05-13
  banned_recalled + manufacturer_violations sweeps; IQM Sprint 2-prep
  rollback; Python 3.9 syntax fix in test_form_sensitive_nutrient_gate.py).

If a previously-resolved failure resurfaces, **do not edit the archive
file** — start a fresh entry below with a new number and a pointer to
the archive entry for context.

---

## How to add an entry

```
### N. `<test_path>::<test_name>`

**Origin:** <commit_sha> — <short commit message>

**Failure detail:** <one-paragraph description of what the assertion checks
and why it currently fails>

**Why not blocking <current sprint>:** <one sentence>

**Acceptance criterion to resolve:** <concrete steps>

**ETA:** <sprint or date or "TBD">
```
