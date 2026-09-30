---
paths:
  - "batch_run_all_datasets.sh"
  - "scripts/release_full.sh"
  - "scripts/rebuild_dashboard_snapshot.sh"
  - "scripts/build_final_db.py"
  - "scripts/sync_to_supabase.py"
  - "scripts/sweep_quarantine.py"
---

# Release and export rules (loaded when working on the release chain)

- **Ship through the `/catalog-release` skill.** It wraps `scripts/release_full.sh`; never
  reimplement its steps. Design rationale: `docs/adr/0001-release-pipeline-safety.md`.
- **Publishing is outward-facing.** A full `batch_run_all_datasets.sh` continues into Supabase and
  the Flutter bundle unless you pass `--pipeline-only` (details in AGENTS.md "Operations safety").
- **Any `scripts/data` or pipeline-code edit trips the release freshness gate**
  (`FRESHNESS_STAGE_INPUT_MISMATCH`, and the `scripts/test.sh release` preflight) until every
  brand is rebuilt from the earliest stale stage; the preflight prints the command. Every stage
  manifest records the reference data and the code it ran (`scripts/pipeline_freshness.py`), and
  cleaning reads the ingredient map, so a data edit reruns cleaning too. A `--targets` run, or a
  corpus built across several code revisions, isn't enough before a release build.
- **Never infer "the build didn't run" from timestamps.** `rebuild_dashboard_snapshot.sh` builds
  into `scripts/.final_db_output.candidate.<PID>` and swaps into place only at the end. Until then
  `dist/` carries the previous run's mtime. Check running processes before starting a second build.
- **Publishing runs refuse stale manufacturer penalties.** `release_full.sh` runs
  `fda_manufacturer_violations_sync.py --check` against today and stops only when a stored deduction
  would change (same-day reruns pass). Fix: `--recalculate-only` in its own commit, then rebuild.
- **Banned/recalled products always ship.** Any export or release hold must be unable to fire on a
  BLOCKED/UNSAFE `suppressed_safety` product. A check that protects a score protects nothing on a
  product that ships no score.
- **Orphan blob cleanup goes only through the gated `scripts/sweep_quarantine.py`.** An ungated
  purge once deleted blobs the bundled catalog still referenced.
- **A gate only protects you if something runs it.** When you add or rename a gate, wire it into
  `release_full.sh` or `scripts/test.sh release` and show that it ran.
- The full test suite runs as a backstop *after* the pipeline, never alongside it.
