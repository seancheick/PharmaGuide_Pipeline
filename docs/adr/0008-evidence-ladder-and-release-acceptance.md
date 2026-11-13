# ADR-0008 — Evidence ladder and release acceptance

**Status:** Ladder decisions accepted by Sean, November 13, 2026; replacement release acceptance remains proposed, not enabled.
**Owners:** Existing owners from ADR-0007: `generic_evidence.py::score_evidence`,
`quality_score.json::evidence_magnitudes` / `evidence_subscale`,
`clinical_applicability.py::assess_clinical_source_review`,
`evidence_resolver.py::_resolve_evidence_for_row`, and assessment readiness.

## Accepted scope

Sean selected 20 Established, 15 Supported, 10 Limited, 5 Preliminary and 0 No qualifying support.
An unresolved review is Pending, never an inferred zero. His explicit November 13 choice assigns
weak applicable research to 5. An all-essential nutritional purpose receives full Evidence credit;
a mixed formula retains the existing nutrition-authority floor. Labels and brand names alone do not
establish authority. Reviewed preparation, population, limitations and specific holds still govern.

The shared generic, sports, immune and fiber adapters use reference20 so approved floor values
are not inflated during conversion. The existing immune category cap17 remains separate. A single
ingredient supported only by weak efficacy findings, exposure-only findings, or both cannot exceed5.
The remaining multi-ingredient aggregation and native omega/probiotic systems are deferred as stated
in the Close Evidence plan; this change does not claim every product now has a five-step total.
The specifically signed glutamine context interpretation remains unchanged.

The blend completion change removes inherited materiality from unamounted blend members. When no
required owner otherwise exists, the existing all-owner fallback remains. Identity, safety-relevant
amounts, clinical holds and unresolved source obligations still hold the product.

Every held ingredient must receive a review. The ranked150 queue is the first batch, not a launch
cutoff. A finished review may genuinely conclude zero; no record is made zero merely to release a
product. Source-level no-credit decisions do not imply whole-ingredient zero decisions.

## Completion audit and limits

The combined PR474–476 state has no observed unfinished-context case that would be released by a
new same-use exception. A generic string-based exception is therefore not implemented. Overlapping
uses cannot safely be treated as unrelated merely because their stored names differ.

Positive literature records lack the completed clinical contexts required by the current credit
owner. Their matching, source review and preparation applicability must be consolidated per record;
globally enabling the positive literature path would create unsupported credit. Routine agent
reviews retain actual authorship and independent checks. Specific unresolved clinician holds require
their actual owner.

The FDA psyllium monograph is retained as a scoped, noncredit source reference. It does not yet grant
20 or prove that a particular retail product satisfies the monograph.

## Release acceptance — decision still outstanding

ADR-0007's99% executable gate remains in force. Stale estimates identify245 intentional omega
amount holds in15447 products, exceeding the154 incomplete products that gate allows. These are
estimates, not a current release census. Do not change the denominator or forge completed reviews.

Proposed replacement for Sean to assess after the fresh census: all assessable ingredient reviews
finished, every remaining product hold attributed to a verified identity, amount, source or explicit
clinical limitation, with existing partial-state rendering verified in the app. The exact acceptance
rule and publication require Sean's approval. This proposal does not activate a bypass.

## Qualification

Bounded frozen-input comparison, independent review, controlled performance measurement, local
checks and exact-candidate CI precede integration. After all output-changing review batches are
integrated, inspect stage fingerprints and perform one necessary corpus rebuild. Release checks,
Core/Blob parity, fresh completion census and real app scans remain mandatory. See the existing
pending-items LEDGER and `scripts/audits/evidence_close_20261113/research.md` for measured progress.

Owner Check: existing owners above; evidence: owner/caller search and source comparison on
November13. Will NOT create: a second scorer, review registry, public field or status.
