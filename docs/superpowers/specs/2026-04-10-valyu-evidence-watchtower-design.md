# Valyu Evidence Watchtower Design

**Date:** 2026-04-10  
**Status:** Proposed  
**Owner:** PharmaGuide pipeline

## Goal

Add a separate, review-only Valyu-based audit tool that helps PharmaGuide discover:

- newer clinical evidence
- missing clinical coverage for valid active compounds
- possible harmful-additive safety changes
- possible banned / recalled ingredient changes

The tool must never write directly into production source-of-truth files and must never affect scoring or exports automatically.

## Why This Exists

PharmaGuide already has direct-source audit tooling centered around:

- [discover_clinical_evidence.py](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/api_audit/discover_clinical_evidence.py)
- [backed_clinical_studies.json](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/data/backed_clinical_studies.json)
- [ingredient_quality_map.json](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/data/ingredient_quality_map.json)
- [harmful_additives.json](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/data/harmful_additives.json)
- [banned_recalled_ingredients.json](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/data/banned_recalled_ingredients.json)

Valyu should complement that system as a secondary discovery layer. It should not replace the direct-source workflow and should not act as a canonical evidence writer.

## Product Principles

- Deterministic production data comes only from reviewed canonical files.
- Valyu is a review assistant, not a scoring dependency.
- Citations and explicit reasons matter more than generated prose.
- Every finding must require human review.
- The tool must be easy to read, easy to run, and easy to ignore when signals are low quality.

## Scope

### In scope

- Separate CLI tool for Valyu-based review reports
- Multi-domain scanning across:
  - clinical evidence refresh
  - IQM clinical coverage gaps
  - harmful additive safety refresh
  - banned / recalled ingredient refresh
- Structured JSON reports
- Human-readable markdown summary
- Tests for schema, filtering, and no-write guarantees

### Out of scope

- Auto-applying updates into canonical JSON files
- Changing scoring directly
- Changing dashboard logic directly
- Replacing [discover_clinical_evidence.py](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/api_audit/discover_clinical_evidence.py)

## Tool Shape

The tool remains separate from the primary clinical discovery workflow.

Likely path:

- [valyu_evidence_discovery.py](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/api_audit/valyu_evidence_discovery.py)

CLI modes:

- `clinical-refresh`
- `iqm-gap-scan`
- `harmful-refresh`
- `recall-refresh`
- `all`

Example commands:

```bash
python3 scripts/api_audit/valyu_evidence_discovery.py clinical-refresh
python3 scripts/api_audit/valyu_evidence_discovery.py iqm-gap-scan
python3 scripts/api_audit/valyu_evidence_discovery.py harmful-refresh
python3 scripts/api_audit/valyu_evidence_discovery.py recall-refresh
python3 scripts/api_audit/valyu_evidence_discovery.py all
```

## Data Sources

### Clinical refresh

Inputs:

- [backed_clinical_studies.json](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/data/backed_clinical_studies.json)

Targets:

- existing clinical entries that may have newer evidence
- branded and high-impact ingredients first

Questions:

- Is there newer evidence?
- Is there a contradiction with the stored evidence framing?
- Is there a stronger meta-analysis or systematic review?

### IQM gap scan

Inputs:

- [ingredient_quality_map.json](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/data/ingredient_quality_map.json)
- [backed_clinical_studies.json](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/data/backed_clinical_studies.json)

Targets:

- valid active compounds that are in IQM but not in the clinical DB

Hard exclusions:

- excipients
- coatings
- capsule shells
- colors
- sweeteners unless explicitly treated as active compounds
- anything coming from unmapped inactive-ingredient buckets

Questions:

- Are there high-impact active compounds missing from the clinical DB?
- Are there recent human studies worth review?

### Harmful refresh

Inputs:

- [harmful_additives.json](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/data/harmful_additives.json)

Targets:

- existing harmful additive entries
- high-impact additives with recent regulatory or safety movement

Questions:

- Are there newer safety signals?
- Are there stronger regulatory references to add?
- Is an existing entry overstated or understated?

### Recall refresh

Inputs:

- [banned_recalled_ingredients.json](/Users/seancheick/.claude-worktrees/dsld_clean/peaceful-ritchie/scripts/data/banned_recalled_ingredients.json)

Targets:

- existing banned / recalled ingredient entries
- recent recall and enforcement entries

Questions:

- Is there a newer FDA or regulatory action?
- Is a status stale?
- Is a date, scope, or citation missing?

## API Usage Strategy

Primary Valyu call type:

- `search(...)`

Reason:

- returns raw result objects
- easier to audit than prose-only answers
- better fit for structured review queues

Optional secondary call:

- `answer(... structured_output=...)`

Use only for:

- short curator notes
- summarized rationale

Never use answer output alone to justify a source-of-truth update.

### Source filtering

Domain-specific included sources should be enforced.

Examples:

- clinical modes:
  - PubMed
  - ClinicalTrials
  - optionally ChEMBL for supporting context
- harmful / recall modes:
  - regulatory and safety-oriented sources

### Date windows

Default lookback should be bounded.

Recommended default:

- `24 months` for refresh modes

That keeps the reports actionable and reduces noisy legacy matches.

## Output Contract

Outputs should be written under:

- `scripts/api_audit/reports/valyu/`

For each run:

- `<timestamp>-raw-search-report.json`
- `<timestamp>-review-queue.json`
- `<timestamp>-summary.md`

### Report row schema

Each flagged row should include:

- `domain`
- `target_file`
- `entity_type`
- `entity_id`
- `entity_name`
- `signal_type`
- `signal_strength`
- `reason`
- `query_used`
- `date_window`
- `candidate_sources`
- `candidate_references`
- `suggested_action`
- `requires_human_review`
- `auto_apply_allowed`
- `supporting_summary`

Required fixed values:

- `requires_human_review: true`
- `auto_apply_allowed: false`

### Signal types

Allowed values:

- `possible_upgrade`
- `possible_contradiction`
- `missing_evidence`
- `possible_safety_change`
- `possible_recall_change`
- `low_confidence_noise`

## Reviewability Rules

- No production JSON file may be modified by this tool.
- No pipeline scoring config may be changed by this tool.
- Generated prose must be treated as support text only.
- Candidate references should carry URLs, titles, dates, and source names whenever available.
- Findings without usable citations should be downgraded to `low_confidence_noise`.

## UX / Readability Requirements

The tool should be simple for an operator to understand:

- clean CLI help
- obvious mode names
- obvious target files
- short summary markdown with counts and top-priority items first
- low-noise defaults

Summary markdown should answer:

- what was scanned
- how many items were flagged
- which findings are highest confidence
- what should a human review next

## Testing Requirements

Add tests for:

- CLI mode parsing
- report row schema
- exclusion of inactive / excipient junk from IQM gap mode
- no-write guarantee for canonical source files
- graceful behavior when `VALYU_API_KEY` or SDK is missing
- classification of findings into the approved signal types

## Rollout Plan

### Phase 1

- Refactor the Valyu tool into a clean report-only scanner
- Support the four target domains
- Produce report files only
- Add tests

### Phase 2

- Add review workflow documentation
- Define how approved findings are manually promoted into canonical files

### Phase 3

- Optionally add a thin wrapper command from other audit tooling
- Keep the implementation physically separate

## Success Criteria

The feature is successful if:

- it never mutates production files
- it produces useful review queues for the right domains
- it avoids inactive-ingredient noise
- it gives curators source-backed leads faster than manual searching
- it remains clearly separate from production scoring and export logic
