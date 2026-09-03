# Submission dose and image integrity — 2026-09-03

## Correctness changes

- AFU label quantities are preserved as AFU measurements, with their original
  row references and serving basis. They are never silently converted to CFU,
  summed into a per-strain dose, or scored as a proven inadequate dose.
- No reviewed AFU-compatible dose reference exists in the current scoring
  configuration. Such products receive `NOT_SCORED`, with
  `probiotic_afu_reference_unavailable` at both the readiness and top-level
  operator-report boundaries. This is an assessment hold, not a safety verdict.
- Missing CFU assessment now says that adequacy could not be verified, rather
  than claiming the label has a clinically inadequate dose.
- Manual labels' `physicalState.name` feeds the same canonical form normalizer
  as DSLD descriptions. Supplied DSLD descriptions retain precedence.
- Manual submission IDs no longer receive invented DSLD PDF URLs. The release
  image probe and downloader share one eligible-target list, and check exact
  thumbnail bindings/files instead of unrelated image counts. A failed probe
  cannot silently skip extraction. Approved submission photos retain their own
  existing import path. An explicitly excluded product defers image copying;
  an unexplained missing catalog row still reports a failure.
- Scoring engine version: **4.3.1**. No weights, clinical reference data, or
  CFU scoring calculations were changed. Export schema remains **2.4.0**.

## Source and clinical limits

AFU is not a synonym or universal conversion for CFU. The measurement distinction
is described by [ISAPP](https://isappscience.org/alive-active-active-alive-flow-cytometry-arrived/).
The [FDA draft quantitative-labeling guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/draft-guidance-industry-policy-regarding-quantitative-labeling-dietary-supplements-containing-live)
does not supply a universal clinical AFU-to-CFU dose equivalence. Neither source
establishes that AFU-labeled products are unsafe, ineffective, or prohibited.

Releasing an AFU score requires separately reviewed, compatible dose evidence
and an implemented assessment contract. Do not lift the hold by inventing a
conversion, assigning neutral points, or changing a caller-authored status.

## Measured impact

- Inspected all **15,415** manifest-owned enriched input products. Only Seed
  carried AFU quantities; only the three manual submissions required the
  `physicalState.name` fallback.
- Recomputed all **15,412** other products from their enriched inputs against
  the new scorer before rewriting scored outputs: **zero** differences in
  numeric scores, pillars, routes, verdicts, statuses, or score-confidence bands.
  **12** dose explanations changed from an underdose claim to an explicit
  inability to verify adequacy.
- Rebuilt all three human-approved source labels through clean → enrich →
  score. Ritual remains **82 / SAFE** and Youtheory **77 / SAFE**. Seed's former
  **49 / POOR** is replaced by the AFU assessment hold; all **24** strains and
  **four** AFU label measurements remain in the QA data.
- The two newly imported raw labels are versioned alongside the existing
  approved Youtheory label. No label amounts were altered to improve scores.

## Verification ledger

RED → GREEN regression tests cover the real Seed label end to end, exact decimal
AFU scaling, duplicate projections, malformed measurements, source-form
precedence, PDF eligibility, and release-probe parity. Independent review found
three follow-ups (malformed AFU handling, image-probe drift, generic hold reason);
all were corrected and re-reviewed with no remaining findings.

- Full development suite: **12,440 passed, 42 skipped, zero failures**.
- Final image-hold follow-up: **75 focused tests passed** after that broad run;
  the independent reviewer found no remaining issues.
- All **37** native datasets completed a score-only refresh. Only the three
  submissions needed clean/enrich/score; native labels were not reprocessed.
- Candidate export, source-of-truth, row identity, RDA/UL, completeness,
  field-contract, form-note, and freshness gates passed. Candidate version
  **2026.09.03.205958** has **15,337** live products: **15,283 scored**, **54
  safety-suppressed**, and **78 exclusions** outside the live catalog. The
  additional exclusion is Seed's AFU assessment hold. There are no contract
  failures, no incomplete products inside the live catalog, and no blocking
  reasons attached to non-hard verdicts. Every scored product has mapping
  coverage exactly 1.0.
- The app import preflight accepted schema 2.4.0 / scoring 4.3.1 without writing
  any app files.
- The release test group passed **122 tests**; its one skip was the interaction
  DB test because this immutable candidate is catalog-only. The existing
  interaction artifact independently passed the same source-of-truth audit;
  the local staging step preserves it byte-for-byte and repeats that gate.
- Strict evidence-match reachability passed on all **15,415** inputs with zero
  stale native matches, zero unlinked recomputed matches, and zero recomputation
  errors.
- Immutable pre-image candidate DB SHA-256:
  `2c00218cac6a6065d7c783761aae15bfb9093266b3bdd3a4621043397ec27973`.

- The complete `scripts/test.sh release` command exited **0**, including live
  drug identity, depletion/timing PMID existence and reviewed-content checks,
  IQM form references, and the strict backed-studies citation gate. That last
  gate verified **445 distinct PMIDs**; its two lexical ghost-suspect flags have
  existing reviewed dispositions and no new unresolved identifier failure.
- Source fixes were committed as `4b870138` and fast-forward merged into `main`.
  The source tree is byte-identical to the tested branch.

## Local staging and handoff

- The release lock protected staging into `scripts/dist` and
  `scripts/final_db_output`; both catalog files and manifests are identical.
  Only generated local release outputs were replaced. Raw labels were retained;
  the immutable pre-image candidate remains available for comparison.
- Cached thumbnails were bound through the canonical image helpers. Ritual and
  Youtheory each have the expected nonempty image file. Their cached image hashes
  were verified, Seed's explicit hold was deferred, and image reconciliation
  reported **zero failures**. Every non-image core field exactly matches the
  release-tested candidate.
- Staged catalog SHA-256:
  `b3134964b70ad5b30043ac4fd786b2c77103e13322e8e4c01a167e2babc77e57`.
- Interaction DB 1.0.11 was preserved byte-for-byte, with SHA-256
  `cf3bab2f5736881562854ec2b9ba99a3fce517073789c13b8c2e145cc1299891`.
  Interaction parity, export, and freshness checks passed after staging. The
  previously skipped live-interaction test passed separately against these
  staged artifacts (**1 passed, zero skipped**).
- App import preflight passed again on the final image-bound staging output.
  **No Supabase upload, submission-status mutation, or Flutter bundle import**
  was performed. The phone and remote catalog still require the normal release.

Next operational step: `bash scripts/release_full.sh` from the pipeline repo.
Do not rerun all 37 brands. The release retains its normal freshness checks;
checkout timestamps on the two newly tracked labels may cause a small submission
refresh and catalog reassembly. No timestamps were overridden or gates disabled
to suppress that check. AFU-compatible clinical dose evidence remains a separate
review requirement before Seed can receive a numeric score.

Operational logs and the full replay result are under
`/tmp/pharmaguide-submission-integrity.IPdJnX/`. This report records the durable
conclusions; temporary paths are not release inputs.
