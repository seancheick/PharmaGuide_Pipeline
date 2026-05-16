# Docs Staleness Audit — 2026-05-12

This audit catalogs every tracked markdown file in the repository (excluding agent skill files, per-condition data views, per-batch audit research, and `safety_copy_exemplars` working dirs) and classifies it into one of five buckets so future agents and humans know what to trust.

---

## Doc-truth priority (use this order when in doubt)

| Priority | Source                                                                                     | Why                                            |
| -------- | ------------------------------------------------------------------------------------------ | ---------------------------------------------- |
| **A**    | Current Python source — `scripts/*.py`                                                     | The pipeline is what the code does, full stop. |
| **B**    | Generated artifacts — `pharmaguide_core.db`, `detail_blobs/*.json`, `export_manifest.json` | What actually ships to Flutter.                |
| **C**    | Tests and audit reports — `scripts/tests/`, `reports/*.json`                               | Objective state snapshots.                     |
| **D**    | Schema docs — `FINAL_EXPORT_SCHEMA_V1.md`, `SCORING_ENGINE_SPEC.md`, etc.                  | Only after verifying claims against A–C.       |

**Never** use `docs/superpowers/*`, `docs/plans/*`, or top-level historical bug-fix logs as implementation truth. They are historical design conversations and completion records; the code has moved on.

---

## Summary

| Bucket                                      | Count | Action                             |
| ------------------------------------------- | ----- | ---------------------------------- |
| **KEEP** — current source-of-truth          | 12    | Maintain in lockstep with code     |
| **UPDATE** — relevant but stale             | 5     | Refresh against current code/blobs |
| **ARCHIVE** — historical value              | 46    | Move to `docs/archive/YYYY-MM/`    |
| **DELETE** — no value                       | 14    | Remove from repo                   |
| **IGNORE_BY_AGENTS** — agent reference only | 4     | Add agent-side guard rails         |

**Top-level rot:** 14 of 19 root-level `.md` files are stale bug-fix completion logs (2024 / early 2026) or v1.3.0-era status docs (now v1.6.0). These should be deleted or moved to archive.

---

## KEEP — 12 docs (current source-of-truth)

| File                                        | Note                                                       |
| ------------------------------------------- | ---------------------------------------------------------- |
| `CLAUDE.md`                                 | Root agent rules (this session)                            |
| `AGENTS.md`                                 | Sibling of CLAUDE.md for non-Claude agents — kept in sync  |
| `README.md`                                 | Top-level repo readme                                      |
| `scripts/FINAL_EXPORT_SCHEMA_V1.md`         | Frozen Flutter contract (bumped to v1.6.0 in this session) |
| `scripts/SCORING_ENGINE_SPEC.md`            | Scoring formula spec (touched 2026-05-05)                  |
| `scripts/SCORING_README.md`                 | Implementation guide for scorer (touched 2026-05-05)       |
| `scripts/DATABASE_SCHEMA.md`                | Master schema reference for 39 data files                  |
| `scripts/GLOSSARY.md`                       | IQM/scoring terminology — cross-referenced from CLAUDE.md  |
| `scripts/INTERACTION_RULE_SCHEMA_V6_ADR.md` | ADR for interaction rules v6 (touched 2026-05-05)          |
| `scripts/INTERACTION_RULE_AUTHORING_SOP.md` | SOP for adding interaction rules                           |
| `scripts/MATCHING_PRECEDENCE.md`            | Matching precedence spec — still current                   |
| `docs/RELEASES.md`                          | Release ledger — append-only history                       |

---

## UPDATE — 5 docs (relevant but stale)

| File                                    | What's stale                                                                        |
| --------------------------------------- | ----------------------------------------------------------------------------------- |
| `scripts/PIPELINE_ARCHITECTURE.md`      | Last touched 2026-04-18, predates v1.5.0 + v1.6.0                                   |
| `scripts/PIPELINE_OPERATIONS_README.md` | Modified in working tree (uncommitted); may need v1.6.0 mention                     |
| `scripts/CONTRACT_V150_FOLLOWUP.md`     | v1.5.0 follow-up plan — many items now delivered; mark each item delivered/deferred |
| `docs/PG_SCORE_EXPLAINED.md`            | User-facing scoring explainer; verify against current `scoring_config.json`         |
| `docs/INTERACTION_DB_SPEC.md`           | Interaction DB spec; verify against current schema                                  |

---

## ARCHIVE — 46 docs (historical value)

Move these to `docs/archive/YYYY-MM/` so they remain searchable but are no longer in the agent's default reading path.

**Sprint E1 era (April 2026):**

- `docs/SPRINT_E1_ACCURACY_ADDENDUM.md`
- `docs/SPRINT_E1_BUILD_BASELINE.md`
- `docs/SPRINT_E1_CHECKPOINT_PRE_E1_3.md`
- `docs/SPRINT_E1_RELEASE_CHECKPOINT.md`
- `docs/SPRINT_E1_STRAIN_VERIFICATION.md`

**Handoff notes (transient by nature):**

- `docs/HANDOFF_2026-04-18.md`
- `docs/HANDOFF_2026-04-20_PIPELINE_REFACTOR.md`
- `docs/HANDOFF_NEXT.md`
- `docs/FLUTTER_HANDOFF_E1_POST_RELEASE.md`
- `docs/flutter_handoff_enhanced_2.md`
- `HANDOFF_PIPELINE_SAFETY_DATA.md` (top-level)

**One-off audits / diffs:**

- `docs/COQ10_GABA_STACK_DIFF_2026-04-25.md`
- `docs/DR_PHAM_IQM_AUDIT_REVIEW_2026-04-25.md`
- `docs/MIGRATION_CATEGORY_ERROR_ENUM_2026-04-25.md`
- `docs/INTERACTION_RULE_GAP_AUDIT_2026-04-26.md`
- `docs/INTERACTION_TIER2_AND_BRIDGE_PLAN.md`
- `docs/DR_PHAM_AUTHORING_QUEUE.md`
- `docs/TEST_SUITE_CONSOLIDATION_PLAN.md`

**Roadmap snapshots (point-in-time):**

- `docs/ROADMAP_EXECUTIVE_SUMMARY.md`
- `docs/FINAL_IMPLEMENTATION_GUIDE.md`
- `docs/PROFILE_SETUP_VALIDATION_GUIDE.md`

**Old plans (mostly delivered or superseded):**

- `docs/plans/2026-04-09-category-gate-audit.md`
- `docs/plans/AGENT_PROMPT_DASHBOARD.md`
- `docs/plans/HANDOFF_2026_04_14.md`
- `docs/plans/HANDOFF_2026_04_14_SESSION2.md`
- `docs/plans/pipeline-dashboard-sprint-tracker.md`

**Duplicate-resolution archives:**

- `scripts/PIPELINE_MAINTENANCE_SCHEDULE.md` — duplicate of `docs/PIPELINE_MAINTENANCE_SCHEDULE.md`; archive scripts/ copy and keep `docs/` canonical
- `docs/PIPELINE_OPERATIONS_README.md` — duplicate of `scripts/PIPELINE_OPERATIONS_README.md`; archive `docs/` copy and keep `scripts/` canonical (closer to code)

**v1.3.0-era schema/contract docs (superseded by v1.6.0):**

- `scripts/EXPORT_SCHEMA_V1.3.0_CHANGELOG.md`
- `scripts/FLUTTER_V1.3.0_INTEGRATION_GUIDE.md`
- `IMPLEMENTATION_STATUS_V1.3.0.md` (top-level)
- `FINAL_SUMMARY_FOR_USER.md` (top-level v1.3.0 status)

**Old plans (`scripts/` plans):**

- `scripts/INTERACTION_ENHANCEMENT_PLAN.md`
- `scripts/SAFETY_DATA_PATH_C_PLAN.md`

**Audit prompt templates (move to `scripts/audits/prompts/`):** and update

- `Harmful_additive_audit_prompt.md` (top-level)
- `Ingredient_Aliases_accuracy_audit.md` (top-level) let's update this so it works with current state
- `UNMAPPED_RESOLUTION_PROMPT.md` (top-level) let's update this too
  | `resume-optimizer-prompt.md` |
  | `scripts/IQM_AUDIT_MASTER_PROMPT.md` | Audit-prompt template; agents derive equivalents fresh per session | let's update this so it reflects the up to date state
  | `scripts/PROMPT_ADD_INTERACTION_RULES.md` | Authoring prompt; SOP doc supersedes it | let's update so it works with the current state

**One-off notes:**

- `cluster_fixup_goals_match.md` (top-level)

**Marketing / outreach artifacts (move to `docs/marketing/`):**

- `docs/infographic-pipeline-story.md`
- `docs/how-it-works-deep-dives.md`
- `docs/outreach-scripts.md`

---

## DELETE — 14 docs (no value)

| File                                     | Why delete                                                                                                         |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `CLEANING_SCRIPT_FINAL_FIXES.md`         | Bug-fix completion log Nov 2024                                                                                    |
| `CLEANING_SCRIPT_TINY_FIXES.md`          | Bug-fix completion log Nov 2024                                                                                    |
| `ENRICHMENT_ALL_BUGS_FIXED.md`           | Bug-fix completion log Nov 2024                                                                                    |
| `ENRICHMENT_FINAL_FIX_SUMMARY.md`        | Bug-fix completion log Nov 2024                                                                                    |
| `ENRICHMENT_LOGGING_BUG_FIX.md`          | Bug-fix completion log Nov 2024                                                                                    |
| `ENRICHMENT_SCHEMA_FIX_COMPLETE.md`      | Bug-fix completion log Nov 2024                                                                                    |
| `ENRICHMENT_SCRIPT_SCHEMA_ISSUES.md`     | Bug-fix completion log Nov 2024                                                                                    |
| `INGREDIENT_QUALITY_MAP_AUDIT_2024.md`   | Audit log Nov 2024 — info now baked into IQM data file metadata                                                    |
| `scripts/FLUTTER_DATA_CONTRACT_V1.md`    | Superseded by `scripts/FINAL_EXPORT_SCHEMA_V1.md` (v1.6.0)                                                         |
| `scripts/PharmaGuide Flutter MVP Dev.md` | Empty / no title; predates v1.5.0                                                                                  |
| `scripts/SUPABASE_SYNC_README.md`        | Verify briefly; sync is pure file-copy per code inspection — likely delete or fold into PIPELINE_OPERATIONS_README |

---

## Duplicates resolved, double check first to see what's in there, if they need to be combined, enhanced and update to reflect actual fact

| Filename                           | Canonical (KEEP)                                                                | Archive                                    |
| ---------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------ |
| `PIPELINE_MAINTENANCE_SCHEDULE.md` | `docs/PIPELINE_MAINTENANCE_SCHEDULE.md`                                         | `scripts/PIPELINE_MAINTENANCE_SCHEDULE.md` |
| `PIPELINE_OPERATIONS_README.md`    | `scripts/PIPELINE_OPERATIONS_README.md`                                         | `docs/PIPELINE_OPERATIONS_README.md`       |
| `README.md`                        | both legitimate — root readme vs `scripts/dashboard/README.md` (dashboard tool) | n/a                                        |

---

## Recommended `CLAUDE.md` patch

Add this paragraph to project-level `CLAUDE.md` so future agents follow priority order:

```markdown
## Documentation truth priority

When you need to know how the pipeline behaves, consult sources in this
order:

1. Python source files in `scripts/` — the code is the truth.
2. Generated artifacts in `scripts/final_db_output/` or
   `/tmp/pharmaguide_release_build/` — what actually ships.
3. Tests + audit reports under `scripts/tests/` and `reports/`.
4. Schema docs — only after cross-checking against 1–3.

Do NOT use `docs/superpowers/*`, `docs/plans/*`, or any top-level
historical bug-fix `.md` as implementation truth. Those are
conversational history, not specifications. If in doubt, run
`scripts/audit_contract_sync.py` and `scripts/audit_raw_to_final.py`
against a fresh `build_final_db.py` output to get an objective state
snapshot.
```
