# Restore per-view scoring reuse — November 6, 2026

Baseline `7ff36a45f`; runtime candidate `b42612f94`. Behavioral performance change,
with no intended scientific, source, scoring, safety or completion difference.
The exact final CI and integration record is [PR404](https://github.com/seancheick/PharmaGuide_Pipeline/pull/404).

Owner: `scoring_input_contract::scoped_product_view/scoring_input_scope`, clinical
applicability's source-reference/identity projections, and the existing scored-artifact
constructor. Will NOT create: another cache/scorer/registry, public field or policy.

## Root causes and repair

Repeated study checks copied complete Evidence-subject structures just to derive
small reference sets and identity maps. Memoize those projections through the
existing per-pass scope, keyed by every lineage argument, retaining isolated copies.

Final assembly correctly reads original source identities, while scoring may use
a filtered identity view. Assembly previously ran under the other view's scope and
rebuilt its inputs repeatedly. Give each distinct whole-product view its own scope;
keep the one-scope fast path when projection returns the original product.

Nested scopes retain the existing October probiotic optimization: field-qualified
facts reuse an enclosing owner ONLY when the declared input objects are identical.
Full-product caches stay separate. Changed rows, route overrides, returned-value
mutation and exception cleanup remain guarded. No whole-cache sharing or parallel
cache framework is introduced. A discarded intermediate scope change lost probiotic
reuse; that regression was caught and fixed before qualification.

## Work counts (four actual scoring calls)

Two enriched products328119/327944, twice each, same source/input experiment:

| Work | Baseline | Candidate |
|---|---:|---:|
| Scoring-input derivations |30|6|
| Evidence-subject provider calls |404|176|
| Recursive deepcopy invocations |4,425,962|2,457,186|
| Primitive deepcopy calls |3,354|752|

Recursive invocations are not independent objects. Reference getters still receive180
requests and identity getters60, but now derive only8 and4 times respectively, per
valid input/argument set. Six input builds represent the genuinely distinct original
and projected views, not six redundant builds of one view. Profiler times are not
used as ordinary elapsed-time benchmarks.

## Frozen correctness and controlled timing

All48 complete scored artifacts, detail blobs and core rows match. Only established
replay timestamps are normalized; core export receives the same clock-normalized
scored input plus a fixed export timestamp. No warning, identity, exposure, Dose,
Evidence, completion or public-score difference is accepted. Initial raw-clock core
hashes were rejected, not silently called equivalent. Per-product hashes and input/
source bindings are in `receipt.json`; private runner checks source bytes before/after.

Full raw36 replay also has zero changes across Clean, Enrich, Score and blob, with
source unchanged and identical frozen manifest/canonical snapshot. Its earlier c2
baseline is explicitly reused: c2→7ff changes only3docs, no runtime/data. This is not
a freshly rerun7ff baseline or whole-catalog replay. It covers Enrich's existing
clinical scope as well as scoring.

Separate baseline/candidate processes score identical captured Enrich inputs three
times per product; median of the two warm observations excludes the first. Inputs
are deep-copied before timing. Export is outside timed scoring. No corpus job or
competing benchmark was running during these measurements.

The36-product qualification cohort includes complex multivitamins, probiotics,
simple, missing-data and held products. Sum of warm medians20.1129→11.2311seconds
(1.79×). Additional brand samples select the smallest, median-size and largest
serialized Enrich products per brand (three each, not entire brand batches):

| Brand | Baseline warm medians | Candidate | Speedup |
|---|---:|---:|---:|
| GNC |1.8562s|1.0759s|1.73×|
| Garden of Life |1.5108s|0.8001s|1.89×|
| Nature Made |0.6346s|0.3973s|1.60×|
| BulkSupplements |0.3442s|0.2164s|1.59×|

Median individual speedup across48 is1.24×; gains are not uniform. No measured product
regressed by both20% and20ms. A dedicated five-pass boundary comparison shows184792
probiotic61.35→51.84ms,3279631.1900→1.1860s,328119 multivitamin1.2266→0.5555s,
with exact scored/export parity. Peak RSS for the48-input processes (including export)
606,552,064→572,473,344bytes. These are samples from one sequential pair, not a
randomized repeated experiment, whole-brand memory/throughput, a promise about
Enrich/validation time, or evidence that October30 performance has been restored.

Private inputs, runner, profiles and receipts are retained under
`~/pg_quality/catalog-release-20261105/performance-20261106/`.

## Permanent guards and qualification

Fail-first projection and assembly tests rejected repeated derivation. Nested-scope
regressions require one shared field derivation but separate whole-product derivations;
changed inputs, current/ancestor route overrides, copy isolation and failure restoration
are pinned. Existing October strain work-count/declared-field tests remain enforced.

Named owner/consumer slice:767passed29.47s. Final local:564passed/24declared optional
skips146.36s, strict skip guard passed, with existing artifact directory explicitly
selected. The initial isolated run lacked that directory (550pass/38skips) and failed
the guard on14missing-artifact skips; it remains a failed configuration attempt.
No assertion or skip policy was weakened. Independent review found no blocker.

AGENTS.md and PR checklist now require deterministic work guards plus frozen
correctness/timing/memory receipts for shared scoring changes. Exact-candidate
whole-fast CI must pass before merge. The early330ad run was superseded and cancelled,
never counted as a pass. See PR404 for the completed candidate's checks and merge.

## Release limits and next owner

The completed run's manifest-bound baseline count is8,480 complete/6,967 partial of
15,447, with two recorded input holds and zero producer errors. It is a scored-output
count, not new-main exported catalog/device qualification. Recorded Evidence blockers
affect6,481 products (6,154 have Evidence as their sole recorded blocker); counts
from multiple blocker types overlap. No complete product has recorded release blockers;
that internal consistency check is not individual scientific verification.

All3 transitive code fingerprints change because the clinical module is imported
across stages. The existing incremental selector conservatively widens stage IDs for
code/runtime changes; unchanged outputs can stop downstream propagation, but that is
not proof of affected-only selection for every code edit. Do not restamp old outputs
or promise a Score-only rebuild. Preserve the completed run, finish the separately
owned scientific/infrastructure batches, inspect the actual plan, then coordinate
one necessary nonpublishing build. No ordinary pipeline, catalog or app publication
is performed by this optimization.
