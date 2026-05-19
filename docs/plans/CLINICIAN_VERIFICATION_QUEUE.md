# Clinician Verification Queue

**Status:** ACTIVE — async, never blocks production
**Started:** 2026-05-18
**Last triaged:** 2026-05-18
**Companion spec:** [SCORING_V4_PROPOSAL.md](SCORING_V4_PROPOSAL.md) §11 Anchor methodology

This file is the asynchronous verification queue for cases the v4 scoring
pipeline cannot resolve to high confidence on its own. Production ships
the conservative default; entries here are reviewed offline and feed
back as curated overrides + regression tests.

**Per Sean (2026-05-18):** production never blocks on this queue. The
AI panel (Claude + ChatGPT) + authoritative APIs (NIH ODS, NCCIH,
PubMed content-verified, FDA, NSF/USP registries) handle every case
synchronously with a conservative default when models disagree. This
queue captures judgment calls for later clinician review.

---

## How items land here

1. **AI panel disagreement** (> 1 band difference between Claude and
   ChatGPT on a canary or sampled product). Conservative score ships;
   case logged.
2. **API contradiction** — an authoritative API value conflicts with a
   model's confident output. The API value is used; the model's error
   is logged for review.
3. **Class-rubric tuning calls** with no clean API ground truth and
   ambiguous web-research consensus. Conservative score ships; case
   logged for clinician judgment.
4. **Edge cases flagged by enrichment** — novel ingredient not in IQM,
   unusual life-stage claim, ambiguous form classification.
5. **Web research subagent returns "insufficient reliable sources"** —
   indicates a class-tuning call that needs human clinical judgment.

---

## How items leave here

A clinician reviewer (Sean's external network, contracted reviewer, or
direct subject-matter expert input) takes an entry, applies clinical
judgment, and produces:

1. **A curated override** in `scripts/data/curated_overrides/clinician_corrections.json`
2. **A regression test** in `scripts/tests/test_clinician_corrections.py`
   that asserts the correction holds in future scoring runs
3. **A decision-log entry** in [SCORING_V4_PROPOSAL.md](SCORING_V4_PROPOSAL.md) §20
   capturing the correction and its rationale

The queue entry is then marked **RESOLVED** in this file with a
back-link to the decision-log line. Resolved entries are kept for
audit history; they don't get deleted.

---

## Entry template

```markdown
### YYYY-MM-DD — <short descriptive title>

**Status:** PENDING | RESOLVED | DEFERRED
**Routing reason:** ai_panel_disagreement | api_contradiction | class_tuning | edge_case | insufficient_sources
**Product / context:** <DSLD ID or brand+product or class+dimension>
**Conservative default applied:** <what shipped to production>
**AI panel output:**
- Claude: <band/score + 1-line rationale>
- ChatGPT: <band/score + 1-line rationale>
**API ground truth (if applicable):**
- Source: <NIH ODS | NCCIH | PubMed PMID:XXXXX | FDA | NSF | USP | etc>
- Value: <what the API said>
- Content-verified: yes/no (per `critical_no_hallucinated_citations`)
**Web research findings (if applicable):**
- Sources cited: <list>
- Consensus / range / "insufficient"
**Question for clinician:**
<the specific clinical judgment call we need>
**Resolution (filled when clinician responds):**
- Date:
- Correction applied:
- Override file: scripts/data/curated_overrides/clinician_corrections.json#<key>
- Regression test: scripts/tests/test_clinician_corrections.py::<test_name>
- Decision log entry: [link]
```

---

## Triage rules

- Items pending > 30 days: flagged in the shadow report's queue-age
  distribution (per §15 item 10)
- Items pending > 90 days: auto-flagged for escalation; if still
  unresolved at 90 days, the conservative default becomes a locked
  curated override pending future revisit
- Items resolved → regression test must land in the same commit as
  the override; the doc decision log captures the why

---

## Counts

| State | Count |
|---|---:|
| PENDING | 0 |
| RESOLVED | 0 |
| DEFERRED | 0 |

(Updated by `scripts/scoring_v4/audit/ai_panel_runner.py` on each
shadow run.)

---

## Entries

_(No entries yet. The queue is initialized but empty until the AI panel
runs in P4.)_
