# Clinical projection reuse — November 6, 2026

Baseline `7ff36a45f`; runtime candidate `4bea5c1bf`. Behavioral performance change;
no intended scientific, scoring, source, safety or assessment-status change.

Owner: `scoring_input_contract::scoped_product_view`, consumed by
`clinical_applicability::_evidence_subject_refs/_resolved_identity_by_ref`.
Will NOT create: another cache/scorer/registry or a persisted field.

## Root cause and change

Repeated clinical study checks derived small reference sets and resolved identity maps
by repeatedly copying the complete Evidence-subject row structures. Reuse those two
small projections within the existing product/pass scope, keyed by every lineage
argument. Defensive copies of returned sets/nested maps remain. Changed inputs,
route-row overrides and calls outside the scope retain the uncached path.

Four-call profile (two actual enriched products, twice each): Evidence-subject reads
404→176; recursive deepcopy invocations4,425,962→2,321,316. These recursive calls are
not independent objects. Scoring-input builds remain30: this diff does not claim to
remove every remaining rebuild or recover October throughput. New builder counts
are8 reference derivations (distinct argument sets) and4 identity derivations.

## Frozen correctness and timing

All48 complete scored artifacts, detail blobs and core rows match. Only the replay
owner's established timestamp exclusions are normalized; core export receives that
same clock-normalized scored input and a fixed export timestamp. An initial raw
core comparison differed on scored_date and was not accepted as parity.
No warnings, identity, exposure, Dose, Evidence eligibility, completeness or public
score differences are accepted. See `receipt.json` for per-product hashes.

The36-product prior qualification cohort includes complex multivitamins, probiotics,
simple, missing-data and held products. In separate baseline/candidate processes,
three scoring passes per product give two warm observations: sum of warm medians
19.9185s→11.6506s (1.71×). Median per-product speedup1.26×; this is not a uniform gain.
Peak RSS354,041,856→355,221,504bytes. Timing excludes export; inputs are deep-copied
before timing. No corpus job or competing benchmark was running.

Additional same-input brand samples use the smallest, median-size and largest
serialized enriched products per brand (three each, not entire brand batches):

| Brand | Sum of baseline warm medians | Candidate | Speedup |
|---|---:|---:|---:|
| GNC |1.8012s|1.1126s|1.62×|
| Garden of Life |1.4594s|1.2094s|1.21×|
| Nature Made |0.6554s|0.3950s|1.66×|
| BulkSupplements |0.3323s|0.2133s|1.56×|

Brand-process peak RSS300,744,704→300,548,096bytes. The48-product parity processes
also construct exports and use607,092,736→606,732,288bytes. Neither is peak memory
for an entire production brand. Receipts are one sequential baseline/candidate
pair, not a repeated randomized experiment, full-catalog throughput or a promise
that enrichment/validation becomes equally faster. October comparisons use different
historical code/data and cannot prove restored performance.

Private frozen inputs, runner, profiles and full receipts are retained under
`~/pg_quality/catalog-release-20261105/performance-20261106/`. The original completed
38-dataset run and owned outputs are preserved. No catalog/app publication occurs.

## Regression protection and qualification

Three fail-first tests rejected redundant derivation before the fix; five final
cases pin work counts, all exercised lineage arguments, mutation isolation,
shallow-copy reuse, changed inputs during an active scope, cross-pass lifetime and
route-row bypass. Clinical/scoring-input owner files:723 passed; the two additional
boundary cases also pass. Independent review found no blocking defect.

Two existing scored-artifact scope regressions pass. Local checks pass with564
passed /24 declared optional skips and strict guard success (135.47s), explicitly
using the primary checkout's existing artifact directory. The initial isolated
run had550pass/38skips and failed the strict guard on14 missing-artifact skips;
it is retained as a failed configuration attempt, not a pass.

Full raw36 replay also passes with zero changes across Clean, Enrich, Score and
blob, source unchanged, same frozen manifest and byte-identical canonical snapshot.
Baseline reuse is explicit: the earlier c2 snapshot is runtime-equivalent to7ff
(the only intervening changes are3docs), not a newly rerun baseline. This covers
Enrich's own existing clinical scope as well as scoring. Exact-candidate whole-fast
CI still gates integration; its final state is recorded in the qualification PR. AGENTS.md and the PR checklist now require deterministic
work guards plus frozen correctness/timing/memory receipts on shared scoring changes.

## Release limits

This is a bounded performance repair, not completed scientific review or release
acceptance. The fresh completed-run census is8,480 complete /6,967 partial of15,447
products, from manifest-owned scored outputs. Export/catalog/alert/signature/device
qualification remains open. Inspect real stage fingerprints before recomputation;
do not restamp outputs or launch another normal corpus run merely for this receipt.
The shared clinical module is in all three transitive stage import closures, so all
three code fingerprints change. The current incremental selector conservatively
selects stage IDs on a code/runtime mismatch; unchanged output can stop downstream
propagation, but this is not proof of affected-only selection for every shared-code
edit. Preserve the completed baseline, finish planned output-changing work, then
inspect the actual plan instead of promising an unsupported Score-only rebuild.
