# QUARANTINE — subagent screening drafts (Wave 1)

**Not evidence. Not a curation input. Never copy a quote out of these files.**

Two Sonnet subagents screened prepared PubMed records against `SCREENING_BRIEF.md`. Their
output is a draft triage layer only. Every record that reached an authored context in
`../wave1_contexts.json` was re-fetched live, re-read and re-quoted centrally, and each
quote is verified as a contiguous substring by `../validate_wave1_contexts.py`.

## Why this directory is quarantined

Live verification (`../verify_shortlist.py`, results in `../wave1_live_verification.json`)
found in these files:

* **25 quote fields** that joined two non-contiguous spans with an ellipsis;
* **28 quote fields** containing composed summaries rather than copied text
  (for example items joined with "/" across different sentences).

Both agents were corrected mid-run and the brief was tightened, but files written before
the correction still contain those fields. A quote that is not a contiguous span of the
source cannot support a clinical field.

## Rules

1. No script under `scripts/audits/evidence_expansion_2026_09/` may read this directory.
   `scripts/tests/test_evidence_expansion_inventory.py` enforces that.
2. Authored contexts take source spans only from the live source, re-extracted centrally.
3. What IS reusable here: the title triage, reject reason codes, handoff proposals and
   per-identity applicability caveats — a starting point for the next wave instead of
   re-screening ~4,800 records.
