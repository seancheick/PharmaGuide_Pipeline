# Vinpocetine audit and fixes — 2026-09-11

The corrections were prepared in `codex/vinpocetine-audit-fixes` and integrated
with Claude's IQM changes. The project owner requested committing and pushing
the source changes, with the pipeline rerun deferred.

## Corrected findings

1. Removed the unsupported 5–13% absorption interval. Retained the sourced
   6.7% study estimate, disclosed the conflicting older estimate, and clarified
   that bio_score 6 is an ordinal calibration rather than a measured percentage.
2. Corrected DSI_ANTICOAG_VINPOCETINE's claim of regulatory-established evidence.
   Live review of the original warfarin study and the in-vitro paper supports
   uncertainty, not established clinical potentiation. The normalized evidence
   is now theoretical. Moderate severity and precautionary management remain;
   source-based wording review is complete. The project owner confirmed prior
   approval on 2026-09-11; no new clinician review is represented.
3. Removed false current-policy statements from the interaction backlog and
   canary history. Restored real single-active product 294063 as a scored/CAUTION
   canary. No invented standalone condition-interaction rule was added.
4. Fixed dose explanations when disclosed amounts get partial credit without a
   benchmark. The scorer no longer calls those amounts a clinically studied range.
   Scoring formulas and safety precedence are unchanged.

## Verification

- Four new regressions failed before corrections and passed afterwards.
- Final focused runner: **267 passed** across IQM identity, safety overlap,
  preparation identity, generic dose, and quality-score tests.
- All nine real labels were freshly cleaned, enriched, and scored with the
  corrected sources: numeric score plus CAUTION. Scores match Claude's affected
  brand outputs. See `real_products.json`.
- Vincamine, Vinca minor, Voacanga africana, and periwinkle do not acquire the
  vinpocetine identity; covered by regressions.
- Saved full-corpus dose comparison: 15,097 products with dose dimensions;
  1,777 explanations corrected, zero changes to other dose-pillar fields.
  See `dose_corpus_diff.json`. This is not a fresh full-pipeline release diff.
- Live PubChem, GSRS, UMLS, RxNorm identity checks passed. Study contents were
  reviewed individually; see `research.md`.
- Live interaction verifier including PubMed: 1 valid, 0 warnings, 0 errors.
  See `interaction_verification.json`.

## Remaining before release

Rebuild later with the final source/config fingerprints, compare the complete
corpus (including identities, safety, and numeric scores), then run the full test
backstop and release gates against the fresh candidate. The stopped rebuild predates
these corrections and cannot certify them. No additional clinician approval
is pending for this wording; the owner confirmed existing approval.

No production catalog or Flutter bundle was deployed by this audit.
