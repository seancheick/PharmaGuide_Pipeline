# QUARANTINE — subagent screening drafts (Wave 1)

**Not evidence. Not a curation input. Never copy a quote out of these files.**

Two Sonnet subagents screened prepared PubMed records against `SCREENING_BRIEF.md`. Their
output is a draft triage layer only. Every record that reached an authored context in
`../wave1_contexts.json` was re-fetched live, re-read and re-quoted centrally, and each
quote is verified as a contiguous substring by `../validate_wave1_contexts.py`.

## Why this directory is quarantined

Two passes measured these drafts.

**Shortlisted records, re-fetched live** (`../verify_shortlist.py`, results in
`../wave1_live_verification.json`): 25 quote fields joined two non-contiguous spans with
an ellipsis, and 28 contained composed summaries rather than copied text.

**Every kept record, against the retrieval it was screened from** (`../qa_screening_drafts.py`,
ledger in `QA_LEDGER.json`) — the pass the partition-2 agent died during, run deterministically
instead:

| measure | value |
|---|---:|
| quote fields verified as exact contiguous substrings | 3449 |
| rejected — ellipsis-joined | 119 |
| rejected — text absent from the source | 135 |
| PMIDs cited that are not in the retrieval set | **0** |
| shortlist entries not among kept records | 0 |
| identities whose self-reported counts disagree with their file | 9 |

About 7% of quote fields are unusable, concentrated in the pre-correction files
(isoflavones, dhea, ginkgo).

State the result precisely: **no source identifier and no shortlist record fell outside the
retrieved corpus, and 254 quote fields failed exact-source verification and were rejected.**
That is provenance, not accuracy — a retrieved source can still be mischaracterized by a
screener without any identifier being wrong. These drafts are therefore useful as triage,
never as clinical facts. The count mismatches are small self-reporting errors (off by one or
two), not missing work.

Both agents were corrected mid-run and the brief was tightened, but files written before
the correction still contain those fields. A quote that is not a contiguous span of the
source cannot support a clinical field.

## Rules

1. No script under `scripts/audits/evidence_expansion_2026_09/` may read this directory.
   `scripts/tests/test_evidence_expansion_inventory.py` enforces that.
2. Authored contexts take source spans only from the live source, re-extracted centrally.
3. What IS reusable here: the title triage, reject reason codes, handoff proposals and
   per-identity applicability caveats — a starting point for the next wave instead of
   re-screening ~4,800 records.

## Contents

39 identities screened (partition 2 was still running when this was captured; its remaining identities are not here).

| identity | screened | kept | shortlisted | handoffs |
|---|---:|---:|---:|---:|
| `OI_BEETROOT_POWDER` | 114 | 35 | 12 | 5 |
| `acai_berry` | 49 | 16 | 12 | 2 |
| `apple_cider_vinegar` | 37 | 18 | 12 | 6 |
| `blueberry` | 135 | 81 | 12 | 0 |
| `broccoli` | 117 | 53 | 12 | 3 |
| `butterbur` | 58 | 51 | 12 | 8 |
| `citrus_bioflavonoids` | 157 | 71 | 12 | 1 |
| `cla` | 159 | 48 | 12 | 5 |
| `d_ribose` | 44 | 24 | 10 | 3 |
| `dandelion` | 33 | 13 | 10 | 4 |
| `dhea` | 154 | 52 | 12 | 1 |
| `evening_primrose_oil` | 135 | 84 | 12 | 3 |
| `flaxseed` | 159 | 87 | 12 | 3 |
| `gamma_linolenic_acid` | 134 | 59 | 12 | 2 |
| `garcinia_cambogia` | 122 | 40 | 12 | 7 |
| `ginkgo` | 152 | 79 | 12 | 8 |
| `gotu_kola` | 18 | 8 | 3 | 2 |
| `horny_goat_weed` | 11 | 9 | 6 | 6 |
| `isoflavones` | 155 | 92 | 12 | 8 |
| `l_carnosine` | 146 | 47 | 12 | 7 |
| `l_glutamine` | 158 | 48 | 12 | 3 |
| `l_histidine` | 160 | 6 | 6 | 4 |
| `l_leucine` | 156 | 61 | 12 | 3 |
| `l_lysine` | 159 | 16 | 12 | 0 |
| `l_phenylalanine` | 159 | 6 | 6 | 0 |
| `l_tryptophan` | 160 | 38 | 12 | 6 |
| `l_tyrosine` | 160 | 24 | 12 | 0 |
| `l_valine` | 159 | 13 | 10 | 2 |
| `lecithin` | 127 | 29 | 12 | 1 |
| `linoleic_acid` | 160 | 23 | 12 | 3 |
| `lycopene` | 155 | 60 | 12 | 1 |
| `maca` | 59 | 33 | 12 | 5 |
| `mct_oil` | 158 | 61 | 12 | 1 |
| `methionine` | 158 | 11 | 11 | 2 |
| `nattokinase` | 37 | 23 | 12 | 6 |
| `olive_leaf` | 121 | 60 | 12 | 1 |
| `pomegranate` | 156 | 81 | 12 | 5 |
| `pumpkin` | 93 | 45 | 12 | 3 |
| `tribulus` | 78 | 64 | 12 | 9 |

Totals: 4662 records screened, 1669 kept, 434 shortlisted, 139 handoffs proposed.
