# Submission review follow-up audit — 2026-09-12

Scope: pipeline commits `424c44e0`, `79600f9e`, and the privacy change that
landed as `0929639e` during this audit; app extraction-reader fix `8b8391c`.

## Confirmed defects and fixes

- Missing/malformed match ledgers reported 100% overall coverage despite being
  blocked. Unknown coverage now reports 0%, retaining the block.
- Older ledgers without `scorable_total` reported 100% for three mapped rows
  out of four. The fallback now uses the existing match-ledger owner's
  `EXCLUDED_FROM_SCORABLE` vocabulary; that case reports 75%. Optional
  manufacturer/bonus lookups remain excluded.
- Removing the reviewer's account ID changed the generated label hash and
  caused an unchanged approval to fail re-import. The importer accepts only
  the exact old serializer's account-ID removal, preserves promotion receipts,
  and recovers interruption between the label and receipt writes. Altered
  labels, approval doses, reviewer IDs, and receipt hashes still fail closed.
  This fix and its tests were included in `0929639e` while the audit was running.
- Removed the account-ID field from the four current committed submission
  labels, with matching local receipt hashes and promotion markers preserved.
  Exact object comparisons confirm no label facts changed. A corpus regression
  prevents the field returning to these files.

## Verification

- Coverage/importer focused suite: 115 passed; subsequent committed-label
  privacy regression: 1 passed.
- Coverage/match-ledger selection: 69 passed.
- Broad `scripts/test.sh fast`: 14,416 passed, 66 skipped, seven local HTTP
  cases hit sandbox permission errors (four failures, three setup errors).
  Rerunning both affected server-test files with local-server permissions:
  31 passed, zero failures. The subsequently added current-label privacy
  regression was also run explicitly and passed.
- Release pytest slice: 123 passed. IQM form evidence, public form-note
  validation (15,113 blobs), and functional-role coverage checks passed.
- Evidence reachability (15,416 products), strict artifact freshness, and
  Flutter source-of-truth parity passed. The release runner's first live
  lookup could not resolve RxNorm inside the sandbox; its retrying subprocess
  was stopped. All six existing live gates were then run in their original
  order with network access and exited successfully: drug-class RxNorm,
  depletion identifiers, timing/depletion PMIDs, reviewed citation content,
  IQM form evidence, and strict backed-study citations. The final citation
  gate's two lexical suspects already have reviewed exceptions; no clinical
  source data was edited or new exception added by this audit.
- Old-versus-new coverage comparison: 96 enriched files, 15,416 products,
  zero coverage changes and zero score-eligibility decision changes in the
  current corpus. The fixes affect malformed/legacy inputs, not today's scores.
- The app reader uses the signed-in reviewer's RPC client; its SQL authority
  checks the reviewer allowlist and returns only the requested revision's
  five latest drafts. No additional app implementation change was needed.

## Boundaries

Coverage is mapping coverage, not clinical certainty. This audit does not
approve pending products, change their scores, or deploy/release a catalog.
Removing IDs from current files does not erase historical Git objects or
previously generated intermediate artifacts. No history rewrite was performed.
Local import receipts remain private and ignored by Git.
