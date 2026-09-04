# Reviewer workflow — one file out, one file back

Status: **draft/unratified, response contract 2.0.0; a new freeze is required.**
The clinical brief is not yet authorized for distribution. This engineering
repair does not assert clinical-owner approval, statistician ratification, or
a valid independent human benchmark. Weights, tier thresholds, and the fixed
three-reviewer design are unchanged.

Historical v6 files, original answers, and reviewer-provenance records remain
untouched. Never backfill a missing exposure declaration with `no` or rewrite
PHAM or another reviewer as independent. A legacy slotmap cannot be upgraded by
guessing a sequence from a randomized order.

## Build a draft document

After a separately authorized new freeze, use its explicit directory:

```bash
PYENV_VERSION=3.13.3 pyenv exec python scripts/audits/v4_reviewer_benchmark/build_review_doc.py \
    --freeze-dir /path/to/new-freeze \
    --slot 2 --reviewer-id REVIEWER_ID --out /path/to/new-document-directory
```

The output directory must not already exist. The builder writes
`REVIEW_<id>.md` and `.slotmap_<id>.json`, with the actual frozen product count.
Do not send the draft before clinical ratification. Fill in the return address
and deadline before distribution, then retain the exact sent copy.

The private slotmap binds freeze ID and hashes for the manifest, blinded
packet, randomized response template, analysis specification, and shared
analysis/validation implementation. It contains two separate values per
product: canonical `review_sequence` from the packet and `reviewer_order` from
the template. Neither is derived from the other.

Three header attestations are deliberately blank:

- `AI_ASSISTANCE_USED:`
- `PRIOR_AI_REVIEW_SEEN:`
- `ENGINE_OUTPUT_SEEN:`

The reviewer must answer each with `yes`, `no`, or `unknown`; the declaration
applies to the entire returned document. AI-assisted research, drafting or
rating counts as assistance. Exposure after starting the review must also be
declared. An explicit `yes` or `unknown` preserves the response as exploratory;
it does not qualify it for independent primary validation.

## Parse a complete return

```bash
PYENV_VERSION=3.13.3 pyenv exec python scripts/audits/v4_reviewer_benchmark/parse_review_doc.py \
    --freeze-dir /path/to/new-freeze \
    --doc /path/to/returned/REVIEW_REVIEWER_ID.md \
    --slotmap /path/to/new-document-directory/.slotmap_REVIEWER_ID.json \
    --out /path/to/new-response-directory
```

The parser computes the six-pillar sum and restores the frozen sequence, slot,
randomized order and initial review round. It calls the same canonical
validator used by locking and analysis; score limits, increments, tolerances
and enums come from the locked analysis specification.

`SOURCES:` accepts semicolon-separated PMID, DOI or HTTP(S) URL tokens and
becomes a JSON list in `source_citations_json`. This checks citation syntax,
not whether a source exists or supports the clinical claim; reviewers still
must verify source content. Rationale and sources are mandatory. Empty or
`none` `ODD:` means no deviation; actual compromise text is preserved, not
converted to `other`.

Missing attestations, malformed numbers/citations, missing scores/rationale,
invalid enums, duplicate/unknown blocks, partial product sets, or changed
freeze provenance produce no CSV. A legacy/missing slotmap fails clearly.
The answer file uses exclusive creation and cannot replace an existing
answer. Preserve the raw return; corrections must be appended with a new
`review_round` and `correction_reason` in a fresh combined response artifact.
Earlier exposure/deviation history continues to exclude the affected product.

## Lock all three reviewers, then analyze

Combine the validated returns using the exact ordered CSV header, retaining
all original and appended correction rows. Do not edit old returns in place.
After the registry is independently completed and verified:

```bash
PYENV_VERSION=3.13.3 pyenv exec python scripts/audits/v4_reviewer_benchmark_analysis.py lock-responses \
    --manifest /path/to/new-freeze/manifest.json \
    --analysis-spec /path/to/new-freeze/ANALYSIS_SPEC.json \
    --reviewer-packet /path/to/new-freeze/reviewer_packet.csv \
    --reviewer-template /path/to/new-freeze/reviewer_response_template.csv \
    --reviewer-registry /path/to/reviewer_registry.csv \
    --responses /path/to/all_responses.csv \
    --locked-on YYYY-MM-DD --output /path/to/new_response_lock.json

PYENV_VERSION=3.13.3 pyenv exec python scripts/audits/v4_reviewer_benchmark_analysis.py analyze-development \
    --manifest /path/to/new-freeze/manifest.json \
    --analysis-spec /path/to/new-freeze/ANALYSIS_SPEC.json \
    --reviewer-packet /path/to/new-freeze/reviewer_packet.csv \
    --reviewer-template /path/to/new-freeze/reviewer_response_template.csv \
    --reviewer-registry /path/to/reviewer_registry.csv \
    --responses /path/to/all_responses.csv \
    --response-lock /path/to/new_response_lock.json \
    --baseline-key /path/to/new-freeze/development_baseline_key.csv \
    --output /path/to/new_development_report.json
```

All products and all three registered reviewers are required for the lock.
Every full randomized order must be the frozen 1–N permutation. The lock
records and rechecks the packet and template hashes, not only the responses.
Stage analysis validates the complete frozen assignments first, then selects
its subset without renumbering sparse original orders.

If any reviewer reports exposure, `unknown`, or a protocol deviation, the
whole product is excluded from the independent complete-panel analysis and
retained in the explicitly exploratory all-locked report. The software never
drops one rater and calls a two-rater comparison the primary ICC(A,3).
If no independent complete-panel products remain, the report status is
`blocked_independent_primary_analysis`, primary metrics/ICC are absent, and
calibration remains ineligible. A content lock is not proof of independence.

Response locks and reports also require fresh output files. Do not open the
sealed holdout in this workflow: it remains separately approval-gated behind
the candidate lock and unchanged analysis hashes.

## Blinding and label-fact fidelity

The document/parser path reads only blinded packet/template content and
provenance metadata. It never opens a baseline key. No engine score, tier,
pillar result, split assignment or master sequence is printed in the reviewer
document. Third-party program dictionaries render the claimed name only, never
the engine's verification decision.

Constituent-form notes render the freeze's source-owned nesting annotation;
the document builder does not reconstruct relationships by summing unrelated
label rows. Daily servings still use the shared serving-frequency resolver,
including provenance checks. The existing DV reference is only an internal
label-consistency flag. Data-note counts are computed during document creation,
not manually copied.
