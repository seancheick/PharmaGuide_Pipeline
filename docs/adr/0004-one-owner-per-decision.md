# ADR-0004 — One owner per decision: extend it, never build beside it

**Status:** ACCEPTED (owner directives 2026-09-16 and 2026-09-25)
**Date:** 2026-09-25
**Matrix concepts:** every entry in `scripts/contracts/source_of_truth_matrix.json`. Worked
examples: `probiotic_row_identity`, `prebiotic_identity`, `certification_evidence`.

## Decision

Every decision the pipeline makes has one owner module. Consumers (scorer, pillar copy, export,
app) call that owner; they never keep a copy of its logic. Before adding a field, state, status
value, module, normalizer, queue, registry, skill or file, run the Owner Check (AGENTS.md
"One brain") and extend the existing owner.

## Context

- 2026-09-16: copies of the verified-cert filter, brand matcher and GMP logic spread across five
  modules drifted apart (one omega matcher skipped the blocked-row check) while tests stayed green.
  They were consolidated into `scripts/scoring_v4/cert_evidence.py`.
- 2026-09-15 (cb678d43): duplicate probiotic predicates let Spirulina and Turmeric count as
  probiotic in routing while enrichment disagreed. They were consolidated into
  `scripts/probiotic_measurements.py`.
- 2026-09-25: new states, fields and a normalizer had been added beside existing owners and had to
  be unwound (099f4b5b, branch `v41-recovery`).

## Consequences

- The matrix records each owner, its consumers and what must not be recomputed.
  `audit_source_of_truth_contract.py matrix` gates it, and `REQUIRED_CONCEPTS` stops entries from
  silently disappearing.
- Apparent duplicates are classified before removal, using the three shapes in AGENTS.md: false
  dual brain, one policy with many consumers, two policies on one topic.
- A new semantic owner needs Sean's approval. Extending an existing owner does not.

## Rejected

Parallel "v2" fields or modules kept "for safety"; reconciling copies instead of routing callers to
one owner.

## Evidence V1 — finite review scope (Sean, November 10, 2026)

The existing Evidence resolver, clinical-applicability owner and 20-point pillar
remain authoritative. A finished assessment answers a bounded ingredient and
preparation question under the accepted rubric; it does not assert that every
publication or underlying participant dataset has been retrieved. A verified
limited noncredit transfer decision can finish that question while retaining
reported positive, null and mixed findings and explicit source-access limitations.
Missing research is never recast as demonstrated ineffectiveness or no human research.

Completion and numerical eligibility remain distinct. The clinical source-review
owner validates provenance and declared-source coverage for a fully noncredit
review, including an ingredient-human record. It preserves existing approved
reference scopes and rejects missing, malformed, unbound or unfinished contexts.
A specific clinical hold, material identity, preparation, amount, Dose or safety
dependency remains binding. Completed noncredit contexts supply neither points
nor replication, enrollment or dosing credit. Historical reviewer attribution and
signed decisions are retained; agent review is not described as clinician review.

Existing source IDs, reviewed scope/date and code/reference fingerprints identify
the qualified assessment version. Discovery of another citation alone does not
invalidate a finished review or append an unfinished context to production data.
New literature is triaged through the existing research/LEDGER workflow. Material
safety findings, retractions, verified errors or findings that change applicability
require prompt reassessment; other literature is handled in bounded maintenance
batches. No new tracker, registry, status, scale or automatic citation-discovery
completion gate is introduced. The beta freeze records a qualified source and
artifact version; it does not prevent correcting material scientific errors.

The narrow November 10 supersession of A114/A073 concerns only noncredit
numerical transfer from taurine PMIDs 32871172/41275513 and grape-seed PMID
34798267. It does not claim their unread Methods or trial membership were verified.
The glutamine PMID 34844156 numerical hold remains; PMID 30108163 keeps its
separately authorized interpretation and exact studied clinical scope.
