# Handoff — Post-Sprint D (Sprint E starting line)

> Sprint D is SHIPPED. Bundled catalog `v2026.04.21.164306` (schema 1.4.0,
> 8,288 products) is live on Supabase + bundled in the Flutter app.
> See [HANDOFF_2026-04-20_PIPELINE_REFACTOR.md](HANDOFF_2026-04-20_PIPELINE_REFACTOR.md)
> for the complete Sprint D record.

---

## Where things stand (entry conditions for next session)

### Pipeline
- Full test suite: **4,479 passed, 12 skipped, 0 failed**
- 20 brands end-to-end clean: **13,236 enriched → 13,236 scored → 8,288 unique**
- Deep accuracy audit v2: **silently-mapped=0, parser_artifacts=0, unmapped_scorable=0**
- All 11 known Sprint D follow-ups CLOSED (see handoff doc § Known follow-ups)
- Git main HEAD: `3fefd54` — snapshot refreeze for D5.2/D5.4 activation drift

### Supabase
- `export_manifest.is_current=true` on `v2026.04.21.164306` · 8,288 products · schema 1.4.0
- Storage: 8,288 unique detail blobs uploaded, 12,131 orphan blobs purged
- 4 public tables align with `scripts/sql/supabase_schema.sql` — no drift

### Flutter
- Git main HEAD: [`6e6a692`](https://github.com/seancheick/Pharmaguide.ai/commit/6e6a692) — bundled catalog refreshed via LFS
- `assets/db/pharmaguide_core.db` checksum matches pipeline manifest
- `assets/db/interaction_db.sqlite` at v1.0.0 (136 interactions, 28 drug classes)
- Schema version 1.4.0 = no Drift codegen needed
- Sprint D wiring live: B7 UL aggregation renderer, `warnings_profile_gated`, +10 Dr Pham fields on `InteractionWarning`

### Local disk state
- `~/Documents/DataSetDsld/builds/release_output/` — kept as rollback safety net (1 GB)
- `~/Documents/DataSetDsld/builds/pair_outputs/` — kept for incremental diffs (1 GB)
- `scripts/dist/` — CLEARED (was staging area; artifacts shipped)
- `/tmp/pharmaguide_release_build/` — CLEARED

---

## Medical-accuracy invariants (verified live)

| Invariant | Status |
|---|---|
| `rda_ul_data.collection_enabled=true` on every product | ✅ 13,236 / 13,236 |
| B7 OVER-UL safety_flags firing where applicable | ✅ 1,929 products (D4.3 teratogenicity protection LIVE) |
| Dr Pham `safety_warning` on every banned entry | ✅ 2,413 / 2,413 |
| Dr Pham `ban_context` on every banned entry | ✅ 2,413 / 2,413 |
| No silent mapping (mapped=True ⇒ canonical_id ≠ None) | ✅ D2.1 contract |
| No "from X" source-descriptor rows escaping as unmapped | ✅ D2.10 routing |
| Proprietary-blend rows routed to recognized_non_scorable | ✅ D2.7.1 |
| Every frozen snapshot matches current scored output | ✅ 30 / 30 |

---

## Sprint E candidates (pick one, two, or three)

Prioritized by ROI × operational value. Each has a crisp "Done" criterion.

### E1 — Release operations hardening (1 session)

**Why:** Right now a release is a 10-step manual recipe. One missed flag = stale
data in production. Automate the playbook.

**Done when:**
- `make release` runs steps 1→10 with a single human gate (post-sync canary yes/no)
- `build_all_final_dbs` + `release_catalog_artifact` + `release_interaction_artifact` chained with exit-code guards
- Post-sync verification reads Supabase `export_manifest` and confirms `is_current=true` matches local manifest
- Release manifest appended to a `docs/RELEASES.md` ledger automatically

**Files to touch:** `Makefile` (or new `scripts/release.sh`), `docs/RELEASES.md` (new)

### E2 — FDA weekly sync automation (0.5 session)

**Why:** `run_fda_sync.sh` exists and is reliable but runs manually. A week of
missed recalls = a week where the app's banned_recalled_ingredients.json
is stale.

**Done when:**
- GitHub Actions workflow runs `run_fda_sync.sh` weekly (Sundays 02:00 UTC)
- On new recalls, workflow opens a PR with the diff
- PR description summarizes: # new recalls, ingredient names, source URLs
- Human merge required (protocol rule #2 — no auto-commit of safety data)

**Files to touch:** `.github/workflows/fda-weekly-sync.yml` (new)

### E3 — Automated brand ingest CLI (1 session)

**Why:** Currently adding a new brand means: manually drop files in
staging/brands/, run pipeline, read coverage report, hand-check gaps. A CLI
makes this a 1-command flow with a human checkpoint.

**Done when:**
- `python3 scripts/ingest_brand.py <staging_dir>` runs: clean → enrich
- Prints coverage gap report + new canonical list
- Halts with a "human review required" prompt (protocol rule #2)
- After human approval, runs score + commits the new brand's output

**Files to touch:** `scripts/ingest_brand.py` (new), `scripts/tests/test_ingest_brand.py` (new)

### E4 — Clinical evidence freshness (0.5 session)

**Why:** PMIDs in `backed_clinical_studies.json` / `medication_depletions.json`
/ `curated_interactions.json` go stale. The user rule is: never ship
unverified claims. We need a quarterly drumbeat.

**Done when:**
- `scripts/api_audit/verify_all_citations_content.py` runs on schedule
- Flags any PMID where article title no longer matches claimed topic
- Produces a "clinical evidence drift report" PR quarterly

**Files to touch:** Extend existing `verify_all_citations_content.py`, add workflow.

### E5 — Sentry integration (0.5 session)

**Why:** Flutter `pubspec.yaml` already has `sentry_flutter: ^9.18.0` staged
(uncommitted in user's local workspace). Wiring it up catches prod crashes +
detail_blob_sha256 fetch failures before users complain.

**Done when:**
- Sentry DSN configured
- Crash reporting active on iOS + Android release builds
- Custom breadcrumbs on: product scan, detail blob fetch, interaction rule eval
- PII-sanitized (no user email / health profile in crash reports)

**Files to touch:** `main.dart` wrapper, `pubspec.yaml` commit, Sentry dashboard config.

### E6 — Phase 4.5 tiered offline architecture (Flutter, multi-session)

From `project_flutter_roadmap_v2` memory. Yuka-style tiered offline:
- Tier 1: always-available bundled ~2k most-scanned products
- Tier 2: on-demand Supabase fetch for long-tail
- Tier 3: AI-estimate fallback for unknowns

**Done when:** See roadmap memory. This is a multi-session Sprint, likely its own handoff.

---

## Non-blocking but worth doing

1. **Commit Sentry pubspec.yaml changes** the user had staged (uncommitted). If they don't want them yet, add to `.gitignore`.
2. **Prune `~/Documents/DataSetDsld/builds/`** older than 2 weeks. Current state: ~2 GB. Keep last 2 releases for rollback; delete older.
3. **Update `reference_supabase_project.md`** memory to reflect schema 1.4.0 + 8,288-product baseline (memory is 12 days stale as of this handoff).
4. **Dashboard / analytics wiring** — no mention of per-brand scan analytics anywhere. Without this, canary monitoring in Sprint E1 is blind.

---

## Canary checklist (do this before next sprint starts)

On your machine:

```bash
cd "/Users/seancheick/PharmaGuide ai"
flutter test test/release_gate/bundled_catalog_test.dart
```

Then open the app and spot-check 3 products where Sprint D was expected to move the needle:

| Product | Expected change | Dr Pham signal |
|---|---|---|
| Thorne Silybin Phytosome (dsld 16037) | Score close to ~52/80 (Phase 3 fix) | Evidence card shows milk_thistle canonical |
| Any multivitamin with 10k+ IU Vitamin A across multiple forms | B7 banner: "Vitamin A exceeds safe upper limit (X% UL) — summed across N forms" | D4.3 aggregation rendering |
| Any product with Titanium Dioxide | Layperson-facing banner: "EU-banned white pigment. Avoid when possible." — not technical jargon | D5.4 Dr Pham copy visible |

If all 3 check out, Sprint D ships cleanly. If any fails, file a bug and roll back the
Supabase manifest via `sync_to_supabase.py --force` on the previous version.

---

## Non-negotiable protocol rules (carry forward, do not break)

1. Every identifier (PMID, CUI, RXCUI) must be API-verified before shipping
2. Every new canonical or data-file entry requires human approval — no auto-commits of safety data
3. `mapped=True ⇒ canonical_id ≠ None` — enforced mechanically
4. The coverage gate's 99.5% threshold is the medical-safety floor; never bypass
5. Every code change ships with a regression test in `scripts/tests/`
6. Snapshot drifts require a changelog entry in `_manifest.json` + medically-reviewed justification

---

*This is the starting line for the next session. Sprint D is done.*
