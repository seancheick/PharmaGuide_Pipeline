# Sprint E1 — Build Baseline Ledger

> **Status:** locked 2026-04-21 at E1.2.1 kickoff
> **Purpose:** frozen pre-E1-sprint detail blobs for shadow-diff after every E1.2+ subtask.
> **Source:** option C — local `scripts/dist/` build artifact (db_version `v2026.04.21.224445`, generated 2026-04-21T22:44:45Z, pre-sprint-E1-code-changes). No external API recharge.

## Why option C

We chose option C over rebuilding (option B) after the E1.0/E1.1 work shipped because:

1. The local `scripts/dist/` build already captured the pre-sprint state — 8,287 products, genuine pre-E1.1-validator state.
2. Zero external API cost (no UMLS / openFDA / PubMed requests).
3. Byte-identical comparability — same pipeline code that produced live Supabase v2026.04.21.164306 produced this dist (up to the cosmetic version label).
4. Shadow-diff after each E1.2+ subtask compares post-fix canary rebuild against these frozen blobs.

## Canary products

| Product | DSLD ID | Brand | Blob SHA256 | Why this one |
|---|---|---|---|---|
| Plantizyme | 35491 | Thorne Research | `4b581bc2b2984643b0c6655f6c4bc007781a46985d825acea62e0cc9287d1938` | Enzyme prop-blend parent-mass cascade (E1.2.1) + enzyme recognition credit (E1.3.4) |
| KSM-66 600 mg | 306237 | Nutricost | `c860481858b1e2f160b38ea9e7c24ffe2901838df737c9b69ce14301249f904d` | Branded-token preservation + standardization (E1.2.2 / E1.3.5) |
| CBD Mixed Berry | 246324 | vitafusion | `cdd4799acb3c41397e96c9fa42d6effb2c2a8b1bd376c5ce32786e0889862f12` | Warning dedup target (E1.2.3) + decision_highlights danger bucket (E1.1.1 validation) + banned_substance_detail (E1.1.4) |

## Baseline storage

- Path: `reports/baseline_v2026.04.21.224445/canaries/{dsld_id}.json`
- Files:
  - `reports/baseline_v2026.04.21.224445/canaries/35491.json` — Plantizyme
  - `reports/baseline_v2026.04.21.224445/canaries/306237.json` — KSM-66 600 mg
  - `reports/baseline_v2026.04.21.224445/canaries/246324.json` — CBD Mixed Berry
- Do NOT edit these files. They are the frozen reference.
- Integrity check: rerun `shasum -a 256 reports/baseline_v2026.04.21.224445/canaries/*.json` and confirm against the SHAs in the table above.

## Per-subtask shadow-diff procedure (E1.2+)

After implementing an E1.2+ subtask fix, for each canary:

1. Rebuild the canary's detail blob from the same enriched+scored inputs via `build_final_db.py` (one-product mode or full rebuild restricted to the canary's brand).
2. Diff:
   ```bash
   diff <(jq -S . reports/baseline_v2026.04.21.224445/canaries/35491.json) \
        <(jq -S . scripts/dist/detail_blobs/35491.json)
   ```
3. Classify every field change as **expected** (matches the subtask's DoD) or **unexpected**.
4. Unexpected delta → repair subtask (max 3 passes). Expected delta → record the field name + why in the commit message.
5. Eyeball step: open each blob, read the user-facing strings, ask: "does this mislead?"

## Phase-boundary full shadow-diff

At the end of Phases E1.2, E1.3, E1.4, rerun the scope-report generator against a full rebuild and cross-check against the baseline counts. The file-level delta view can grow — we accept the accumulation as long as each per-subtask delta was classified.

## Rollback

If a canary regresses in an unrecoverable way, revert the offending commit and rerun the per-subtask lifecycle. The baseline does not move.
