# Study amendment — false total-vs-forms notes in the v6 reviewer packets

Raised 2026-08-07. Software defect **fixed**; study treatment **open**, and it is
a protocol decision for the statistician and clinical owner, not a code change.

`build_review_doc.py` inferred "X is the TOTAL; do NOT add the entries after it"
from arithmetic coincidence — whether the next 2–3 amounts happened to sum to the
current one — with no identity evidence of any kind. A 2:1:1 BCAA ratio
*guarantees* `Leucine == Isoleucine + Valine`, so every BCAA product tripped it.

Thirty such notes reached each of the three reviewers. **23 were false.**

## Exact accounting

| | count |
|---|---:|
| notes sent, per reviewer | 30 |
| retracted (no relationship exists) | 22 |
| retained, but a different correct roll-up | 1 |
| retained unchanged (was correct) | 7 |
| **false claims distributed** | **23** |

The single `retained_changed` product reconciles the two figures that otherwise
look contradictory: 23 *claims* were false, but only 22 products lose their note
outright — MediClear's false `beta-carotene == Vitamin A + Vitamin C` is replaced
by a genuine `Vitamin E 80.6 == 73.9 + 6.7`.

## Artifacts

| file | sha256 (first 16) | what |
|---|---|---|
| `CONTAMINATION_v6_rollup_notes.csv` | `a432a356f17f07d0` | 90 rows = 30 products × 3 reviewers |
| `AUDIT_PHAM_citation_pairs.csv` | `d09a9b9aeda624d0` | 160 citation→product pairs, live-verified |
| `AUDIT_PHAM_findings.csv` | `fe33f17ad05e3e43` | structural findings (empty — none found) |

Regenerate with `build_contamination_manifest.py` and
`audit_reviewer_responses.py`. Both are deterministic; neither opens
`development_baseline_key.csv` or `SEALED_HOLDOUT_KEY.csv`, and neither edits a
response. They join on product name + brand, which the packet carries in the
clear — blinding covers engine scores, not product identity.

## Which returned data is affected

Only PHAM has returned (120 rows, round 1). **23 of those rows were exposed to a
false note.** `contamination_class` splits them:

| class | n |
|---|---:|
| `false_total_instruction` | 20 |
| `mixed_unit_false_rollup` | 1 |
| `phantom_zero_row_rollup` | 1 |
| `corrected_to_different_rollup` | 1 |

`likely_direction_of_bias` separates risk from noise: **11 are
`dose_total_at_risk`** (all BCAA — the one family a reviewer conventionally sums
into a single total, so "do not add these" would halve it) and **12 are
`inert_no_conventional_total`** (nobody aggregates taurine into beta-alanine, or
biotin into folate, so the instruction has nothing to deflate).

## Evidence the notes were not acted on

`reviewer_rationale_evidence` records what PHAM's own free text says. Of the 23,
seven contain a checkable total, and **all seven state the correctly-summed
figure** — "total BCAA is 3 g", "A 1 g total BCAA dose", "The 10 g 2:1:1 BCAA
dose". Zero state the deflated parent-only figure. On MediClear, PHAM
independently flagged that "total/component entries are internally duplicated"
and dropped confidence to low.

**This is supporting evidence, not proof.** Free text is not the score; 16 of the
23 contain no checkable figure; and KEVIN and REVIEWER3 have not returned.

## Recommended treatment (for the owners to ratify)

The contamination is in the *packet*, identical across all three reviewers, so
any exclusion should apply to all three — not to PHAM alone — to keep a common
product set.

1. **Primary:** pre-specify the treatment of the 23 before any agreement
   statistic is computed. Excluding them across all reviewers is the
   conservative default.
2. **Sensitivity:** repeat including all 120 and report whether conclusions move.
   Given the evidence above, they probably do not — which is worth stating.
3. **If corrected human judgments are wanted:** a formal round-2 on the affected
   products only, preserving round-1 values exactly and marking round 2 as
   adjudication rather than independent first-pass. Do not overwrite round 1.

Do not let these rows enter the calibration regression unmarked.

## Independent audit of the returned response

Because the benchmark is the oracle, PHAM's file was itself checked
(`audit_reviewer_responses.py`). Clinical judgment was deliberately not
second-guessed — only objectively checkable claims.

- pillar arithmetic: **120/120** correct; no out-of-bounds, no blank fields, no
  protocol deviations
- cited PMIDs: **38/38 resolve on PubMed** — no fabricated identifiers
- citation→product topicality: **156/160 on-topic** once blends and inactives are
  included
- in-text "Verification N.N =" assertions: **106/106** match the scored pillar
- the protocol's "assume 1 serving" rule: used on **0** products whose labelled
  frequency was not actually broken

**One finding, low severity.** PMID 34743773 (a betaine meta-analysis) is cited
on 14 products; 10 contain betaine, and 4 — the `PRE Pre-Workout Complex`
flavours — do not. Those rationales make no betaine claim and no score depends on
it, so this is citation over-inclusion across a product family, not a ghost
citation and not a scoring error. Worth a note to the reviewer; not grounds to
exclude anything.
