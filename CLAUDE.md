# PharmaGuide Pipeline — Claude Code

**Read `AGENTS.md` in this directory first.** It is the single source of truth for this repo:
commands, project structure, the v4 scoring contract, conventions, engineering principles, and
the non-negotiable data rules. This file carries only the Claude-Code-specific delta.

Why so short: this file used to be a near-duplicate of AGENTS.md (232 of 282 lines identical).
The copies silently diverged, and CLAUDE.md went on documenting the retired v3.4.0 / 80-point
scorer — and a `score_supplements.py` that no longer exists — for a month after AGENTS.md was
corrected. One canonical file, one delta file. Do not grow this back into a second copy.

## The one command to remember

```bash
scripts/test.sh fast          # dev loop (~3-5 min). NEVER raw pytest.
scripts/test.sh fast -k <kw>  # single topic
scripts/test.sh release       # release gates before a ship
```

Raw `python3 -m pytest` picks the wrong interpreter (macOS 3.9, not pyenv 3.13.3) **and** runs
every heavy test — ~1 hour instead of ~4 minutes. See the ⚠️ section in AGENTS.md.

## Claude-Code specifics

- **Project skills** live in `.claude/skills/` — e.g. `fda-weekly-sync`, `verify-data`, `diagnose`. (18 generic/stale ones incl. `v4-phase` archived to `~/claude-attic/2026-08-06/` in the 2026-08-06 de-noising.)
  (AGENTS.md's `.Codex/skills/` path is wrong; that directory does not exist.)
- **Web browsing:** use the built-in Browser pane tools (`mcp__Claude_Browser__*`), or
  WebFetch/WebSearch inside a subagent so only the summary returns. Never
  `mcp__claude-in-chrome__*`. The former gstack `/browse` skill was archived 2026-07-24 —
  every `/office-hours`, `/ship`, `/qa`, `/retro`, `/cso`, `/autoplan` reference in older docs
  is dead.
- **Skills for this work:** `/catalog-release` (the dsld_clean → Flutter release train, wraps
  `scripts/release_full.sh`) and `/data-fix` (one-entry-at-a-time curated-data corrections).
- **Memory** for this repo:
  `~/.claude/projects/-Users-seancheick-Downloads-dsld-clean/memory/` — check `MEMORY.md`
  before re-opening past work, and trust the memory *file* over its index line.
- **Never hand-copy counts into docs.** Entry counts, file counts, and schema versions drift
  within weeks. Read `_metadata.total_entries` from the data file, or `scripts/DATABASE_SCHEMA.md`.
