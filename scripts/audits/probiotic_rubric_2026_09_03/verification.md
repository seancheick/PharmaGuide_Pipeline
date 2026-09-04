# Probiotic scoring correctness and rubric review

Baseline: `bc98fe2d` on `codex/scoring-applicability-and-seed`.

## Execution boundary

User approved implementation, targeted/corpus comparisons, review, commits and branch push.
No operational full-corpus rebuild, release, Supabase write, Flutter import or publication.
Keep the six global pillar weights unchanged. Version category-rubric changes separately
from bug fixes and evidence-registry curation. No preferred product score.

## Checklist

- [x] Fix certification strength/variant identity with red/green regressions.
- [x] Remove marketing-word evidence points; retain separate claim-alignment metadata.
- [x] Normalize existing formula/strain applicability and dose provenance for scoring.
- [x] Audit and consolidate duplicate disclosure consequences; explain each retained deduction.
- [x] Review PMID 41750436, including cohort overlap and endpoint limits.
- [x] Compare six real products and adversarial cases, including all pillar/metadata changes.
- [x] Run manifest-owned corpus comparison and inspect all material change classes.
- [x] Run focused + fast tests; independently review; resolve findings.
- [x] Commit reviewed implementation batches and save the rebuild handoff.

## Verification record

An unchecked item is not complete. Generated audit reports do not replace the
subsequent operational rebuild and release gates.

Final fast backstop: **12,954 passed, zero failed, 42 skipped** in 393.94
seconds, using `scripts/test.sh fast` after the final corpus audit. No full
operational pipeline or concurrent corpus audit ran alongside it. Skips include
missing historical/generated-artifact canaries and intentionally exempt data
shapes; they are not counted as passes. Raw log:
`reports/probiotic_rubric_2026_09_03/fast_tests_final.log`.

`scripts/test.sh release` was invoked without bypasses. It correctly stopped
at freshness preflight (before running release tests): reference-data content
differs from all 38 enrichment manifests, and the existing dist/→Flutter bundle
timestamp check also reports drift. Exit 1 is an **open rebuild/release gate**,
not a passing release suite. Nothing was uploaded or imported. Raw log:
`reports/probiotic_rubric_2026_09_03/release_preflight.log`.

Log SHA-256 values:

- Fast: `84f96a71080b2f1f3def72231aa4b67fee9936e20e5388b638b52a7e833693e5`
- Release preflight: `96d64dd3212590710cc53051fbcce36ce811fef30be34068aa208ad2667fde34`

## Delivery

- `55d4cad2`: guarded certification identity and positive/negative regressions.
- `283d83c1`: source-owned probiotic applicability, disclosure consolidation,
  related-paper curation and scoring/config versioning.
- The following audit commit packages the reproducible runner, helper tests,
  complete material diff, comparator decompositions and review queues.

Delivery branch: `codex/scoring-applicability-and-seed`. This is source-code
delivery, not a merge to main or a production release. Git synchronization is
verified after pushing the audit commit.

The operator's next step is the full `enrich,score` rebuild with release skipped,
as shown in README.md. Then inspect the fresh snapshot, resolve release freshness
including the Flutter bundle, and rerun the release/full gates before publishing.
Do not bypass freshness to turn this source-only batch into a claimed release.

## Change classification

A — correctness: CFU strength shorthand, named variants and ambiguous certification
matches; source-owned CFU plus daily servings instead of stale copied doses; retained
blend source references instead of first-child positional indexes; supported vs
unfavorable vs unestablished evidence explanations.

B — versioned rubric: marketing wording is metadata only; Evidence separates
research support (/12) from reviewed dose applicability (/8); undisclosed-dose
strain records cannot accumulate full evidence by count; an assessed finished
formula owns the complete raw Dose scale; within Transparency, pure strain-allocation
opacity is counted once. Scoring 4.4.0 / config 1.1.0; global weights unchanged.

C — curation: one related mechanistic Seed publication, without stronger effect,
larger trial enrollment, independent-replication claim or publication-count points.
See research.md. The full backbone live citation gate passed: 202 entries, 448
distinct PMIDs, 463 PMID-entry claims; zero missing IDs, title mismatches or title
drift. Two existing suspects have documented registry dispositions. This gate is
not a claim that every study's efficacy or clinical applicability was re-reviewed.

## Audit findings closed during implementation

- Reviewer: Dose trusted copied `cfu_per_day` while Evidence re-proved the source.
  Both now consume source-owned measurements and explicit daily servings.
- Reviewer: certificate normalization over-rejected legitimate vitamin descriptors;
  ambiguity output lost provenance; curated overrides lost their matched target.
  Corrected with positive and negative identity controls.
- Real comparator audit: nested-only allocation proof missed cleaner-flattened
  Ritual/Fortify labels. The existing flattened source ledger now proves owners.
- Real comparator audit: B5 sub-blend positions could point at a first child rather
  than the parent. Source references now survive collection/merge/B5 emission.
  The architecture backstop rejected a raw-active fallback in scoring; it is
  removed. Missing canonical owner references retain B5, even on old metadata.
- Consumer-blob rescoring is intentionally not a contract. Source-complete enriched
  inputs are scored; consumer blobs use stamped pillars. Missing owners cannot
  authorize a disclosure exception, including through compatibility aliases.
- Broader certification replay: embedded brand wording, caplet plurals, printed
  `Gummie(s)` / `Gummy(ies)`, and exact names erased by token filtering could
  reject legitimate matches. Source-backed positive cases now pass without
  relaxing strength/form/population or missing-qualifier checks.
- Final cross-brand review caught the opposite direction too: an extra named
  edition on the query could inherit a base SKU's certificate. Real Alpha,
  Ripped, Amplified, Burp-less and Super Strength labels now reject unrelated
  base-SKU mappings. Correct program-specific Alpha/Ripped records remain.
  Seventeen new negative regressions failed before the correction; the final
  certification slice passed 259 tests. Only explicit registry product-line
  authority can cover an otherwise unsupported named edition.
- Final requirements review: species-general research scope was present in
  ingredient details but lost in scored evidence/copy. The existing registry
  scope decision is now shared by presentation and assessment. The explanation
  explicitly describes the registry classification, not a universal assertion
  about all published strain research.
- First full-fast backstop: 52 failed, 12,845 passed, 42 skipped. Most failures
  were old fixtures authorizing credit from orphaned clinical rows, retired
  evidence component/version pins, and the ideal archetype's fabricated dose
  tier. They were corrected to prove real ownership and current rubric math;
  no production score was raised to satisfy an old fixture. The raw-active
  architecture failure above was a production fix, not a waived gate.

The initial `corpus_impact.json` and intermediate `corpus_impact_final.json`
under `reports/probiotic_rubric_2026_09_03/` are superseded. The reviewed replay
is `corpus_impact_reviewed.json`; its hash is bound into the tracked summary.

Final replay: 15,415 products / 355.6 seconds / zero errors. Every changed
producer lane was recomputed for all products; 217 canaries were fully
re-enriched from cleaned inputs. No input/code fingerprint drift occurred.
1,014 numeric score changes (477 probiotic, 537 other) and 1,015 material
records were inspected by change class. Route and score-status transitions are
zero. All 79 verdict changes are existing SAFE↔POOR quality thresholds;
Safety/Hygiene scores and hard safety verdicts do not change.

Non-probiotic pillar effects are Verification only, except ten omega records
whose existing certification-dependent Formulation/Transparency floors no
longer apply. These are not new formulation or weight rules. The retained
Verification review queue distinguishes missing identity proof from a claim
that a product is uncertified; uncredited aliases require individual review,
not a broad matcher exception. All six required comparator results remained
unchanged through the final certification correction.

Independent final read-only reviews found no remaining implementation blocker
in either the probiotic scope/provenance work or the corrected certification
resolver. The reviewer independently reproduced the Alpha/Ripped/Burp-less
rejections, explicit product-line handling, and real Jarrow explanation.
Its focused certification replay passed 23 tests (100 deselected). Separate
fixture/provenance checks passed 132 tests; applicability/architecture checks
passed 44. These focused runs complement, not replace, the final fast backstop.

## Clinical interpretation boundary

The native strain registry's industry CFU potency bands are not verified trial-dose
ranges. Research presence still receives contextual credit, but only curated
form/dose/population scope may earn dose-applicability points. An unreviewed range
is a curation limitation, not evidence that a strain or product is poor. No new
native clinical ranges were fabricated to lift comparator scores.

The formula dose result is formula-level: it never invents individual strain CFU
or converts AFU to CFU. Seed retains undisclosed-quantity transparency limitations.
Mixed prebiotic, botanical and unresolved blend penalties remain separate.

One existing registry limitation is explicit: missing Q1/type specificity
defaults to `species_general`, including LGG despite a separate strain-specific
backbone record. This batch retains that producer classification and scopes the
consumer sentence to "our registry currently"; it does not claim that all LGG
literature is species-only. A future native-evidence curation pass should
distinguish unresolved scope from affirmative species scope, and verify actual
strain/dose/outcome applicability together. It must not simply raise scores.
