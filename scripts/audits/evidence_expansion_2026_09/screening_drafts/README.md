# Subagent screening drafts (Wave 1)

**These are DRAFTS, not evidence.** Two Sonnet subagents screened the prepared PubMed
records (`discover_literature.py` output) against `SCREENING_BRIEF.md`. They do not
decide anything: every record that reached an authored context in `../wave1_contexts.json`
was re-fetched live, re-read and re-quoted centrally.

Known defects in these files, found by `../verify_shortlist.py` and corrected mid-run:

* 25 quote fields joined two non-contiguous spans with an ellipsis;
* 28 quote fields contained composed summaries rather than copied text
  (e.g. items joined with "/" across different sentences).

Both agents were corrected during the run and the brief was tightened, but the files
written before that correction still contain those fields. **Never lift a quote from
these files into a context.** Re-extract from the source.

They are kept because they carry the reusable part: the title triage, the
reject reason codes, the handoff proposals and the applicability caveats per identity,
which the next wave can start from instead of re-screening ~4,800 records.
