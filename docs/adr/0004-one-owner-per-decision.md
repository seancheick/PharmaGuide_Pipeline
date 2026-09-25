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
