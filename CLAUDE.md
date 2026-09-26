@AGENTS.md

# Claude Code delta

AGENTS.md above is imported on purpose. This repo has a CLAUDE.md, so Claude Code's default
instruction mode (`claude-md-or-agents-md`) would otherwise skip AGENTS.md. Put shared rules in
AGENTS.md; this file holds only Claude-specific material. Don't grow it into a second copy.

## Session flow

- **Starting a session on existing work:** the SessionStart hook prints the branch, HEAD and
  handoff age. If a handoff exists, run `/pg-resume` before editing anything.
- **At a phase boundary** (audit → implement → review → release, or after two wrong architecture
  assumptions): run `/handoff`, then recommend a fresh session to Sean over continuing a
  compacted one.
- **Reviews of important changes** go to a fresh-context subagent (or Codex). It gets only the
  requirement, the matrix owners and the diff, never the builder's reasoning.

## Skills for this repo

| Skill | Use |
|---|---|
| `/catalog-release` | the release train; wraps `scripts/release_full.sh` |
| `/data-fix` | curated-data corrections, one entry at a time |
| `/pg-scoring-change` | any change that can move a score, pillar, route or verdict |
| `/verify-data` | live-API identifier verification |
| `/fda-weekly-sync` | FDA recall/ban sync |
| `/prepare-product-submissions` | submission extraction queue |
| `/handoff`, `/pg-resume` | save and recover worktree state |

Path rules in `.claude/rules/` load on their own when you touch `scripts/data/`,
`scripts/scoring_v4/`, or the release chain.

## Environment

- **Test runner:** `scripts/test.sh` (see AGENTS.md). The Bash tool is zsh: brace variables before
  `:`, and split word lists with `${=VAR}`.
- **Web:** use the Browser pane tools (`mcp__Claude_Browser__*`) or WebFetch/WebSearch. Never use
  `mcp__claude-in-chrome__*`.
- **Memory:** `~/.claude/projects/-Users-seancheick-Downloads-dsld-clean/memory/` holds stable
  preferences and corrections only (see AGENTS.md "Knowledge placement").
