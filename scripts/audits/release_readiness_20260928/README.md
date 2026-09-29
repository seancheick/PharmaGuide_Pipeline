# Release-readiness forensic audit — 2026-09-28

Read-only audit of PharmaGuide `main` after the 2026-09-24 → 2026-09-28 window. Nothing under
`scripts/`, `scripts/data`, tests, docs or the Flutter repo is edited by this audit; this directory
and `~/pg_quality/rr_20260928/` are its only outputs. Committed 2026-09-29 at Sean's request, with the fixes it led to (`rr_correctness_20260928/`).

| Item | Value |
|---|---|
| Pipeline HEAD (release candidate under audit) | `391b87c5199527f3a3b157c0fed9d2003d7eb232` (local `main`, 2 ahead of `origin/main` `dde22dab`) |
| Flutter HEAD | `d71e47f56d8221abfc8e38a1820c6ceddd66432b` (`main` = `origin/main`) |
| Audit window | 2026-09-24 (last Thursday) → 2026-09-28; last pre-window commit `7b031050` |
| Commits on main in window | 413 (379 non-merge, 34 merges) |
| Plan | `~/.claude/plans/given-everything-we-ve-learned-hidden-eclipse.md` |

Layout: `LEDGER.md` (evidence: claim → command → output), `commits/` (B, M), `traces/` (E, D),
`reports/` (A–N, VALIDATION_MATRIX).
