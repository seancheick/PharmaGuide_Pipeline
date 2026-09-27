---
name: catalog-release
description: Run the dsld_clean → PharmaGuide ai catalog/interaction-DB release train. Use when the user wants to ship a catalog, rebuild + bundle the DB, cut an interaction-DB release, repin clinical-db, or says "release the catalog", "rebuild and bundle", "ship the pipeline data". Wraps scripts/release_full.sh — never reimplement its steps.
---

# Catalog release train

Two repos:
- **A (pipeline)** = `/Users/seancheick/Downloads/dsld_clean`
- **B (app)** = `/Users/seancheick/PharmaGuide ai`

`scripts/release_full.sh` in A already orchestrates the whole chain and auto-skips
fresh steps. **Do not hand-run its internals** — that is how gates get bypassed.
A release is Sean's decision (AGENTS.md); run it only when asked.

## 1. Pre-flight (always, in A)

```bash
cd /Users/seancheick/Downloads/dsld_clean && git status -s && git log --oneline -3
```

Stop and ask if the tree is dirty in `scripts/` — a release off uncommitted data is unreproducible.

```bash
bash scripts/test.sh release
```

Runs the stage freshness check (every brand's clean, enrich and score output must come from the
current `scripts/data` and pipeline code), release-profile pytest and the release artifact gates,
including the three citation verifiers (backed studies `--strict`, interaction rules
`--strict`, all citations `--baseline`). **Must be green before proceeding.** A stale corpus
means one corpus pass first, from the stage the preflight names (`SKIP_RELEASE=1 bash
batch_run_all_datasets.sh --stages …`: every brand plus Product Submissions, no publish).

## 2. Run the train

```bash
bash scripts/release_full.sh --flutter-repo "/Users/seancheick/PharmaGuide ai"
```

Useful flags: `--force` (ignore freshness skips), `--supabase-dry-run`,
`--skip-supabase`, `--skip-flutter`, `--skip-product-images`.

For a first pass on an unfamiliar change, prefer `--supabase-dry-run` and read the diff before the real run.

Internally (for diagnosis only): `rebuild_dashboard_snapshot.sh` (source-of-truth
gates → `release_catalog_artifact.py` → `stamp-manifest` → `promote_release_artifacts.py`)
→ `extract_product_images.py` → `rebuild_interaction_db.sh` (`verify_interactions.py`
→ `build_interaction_db.py` → `release_interaction_artifact.py`) → preflight gates
→ `release_interaction_artifact.py --publish-flutter-pin` → `sync_to_supabase.py`
→ B's `scripts/import_catalog_artifact.sh` → B's `tool/fetch_interaction_db.sh` gate
→ prune + commit + `cleanup_old_versions.py`.

## 3. Verify in B before committing

```bash
cd "/Users/seancheick/PharmaGuide ai" && make verify-bundle && make check
```

The interaction DB is **hydrated at build time, not committed**: `tool/interaction_db.release.json`
holds the pin (repo `seancheick/PharmaGuide_Pipeline`, tag, sha256, URL) and
`tool/fetch_interaction_db.sh` fetches it, refusing when pin and staged manifest disagree.
When the interaction DB changed, the train publishes the next `clinical-db-YYYY.MM.DD.N`
GitHub Release asset (a public action; reused when a release already carries the digest),
verifies the download and moves the pin into the bundle commit. Outside the train, repin
with `$PG_PYTHON scripts/release_interaction_artifact.py --output-dir scripts/dist
--publish-flutter-pin "/Users/seancheick/PharmaGuide ai"`, never by hand.
`assets/db/pharmaguide_core.db` and `export_manifest.json` ARE committed files.

## 4. Spot-checks every release

- **evidence_level** — `build_interaction_db.py` derives it (`derive_evidence_level`); NULL
  renders as "Theoretical" in-app. Confirm the built DB has zero NULL `evidence_level`.
- **UL verdicts** — only typed elemental evidence may drive them (compound masses are
  gate-ineligible, `test_ul_gate_eligibility.py`); prose `warnings[]` never drive a UL verdict.
- **mapped_coverage** — safety-critical; `scoring_v4/scored_artifact.py` takes it from the
  scoring input contract. Never ship a bundle where it regressed.
- **Score movement** — `scripts/api_audit/score_delta_report.py --before <previous release>
  --after <candidate>`; every BLOCKED/UNSAFE change and every large move has a named cause.

## 5. Report

State plainly: gates green/red (with output), catalog + interaction versions shipped,
which files the bundle commit touched, and anything skipped. Never claim a release is
done without `make verify-bundle` output.
