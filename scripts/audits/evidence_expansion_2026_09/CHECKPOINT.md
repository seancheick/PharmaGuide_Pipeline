# Evidence expansion — Phase 1 checkpoint (2026-09-17)

**STOP POINT.** No production evidence was written, no score moved, no scoring rule or weight changed, no catalog rebuild, no release. Every authored context is pending owner review.

## Headline

- **4045** non-probiotic products ship Evidence 0 (27.8% of 14561 scored).
- **3549** (87.7%) are blocked by missing evidence curation — this project's target.
- **496** (12.3%) are blocked elsewhere; more papers cannot move them (see BLOCKER_ROUTING.md).
- **No scorer-defect bucket**: 0 products have an accepted, point-carrying match yet Evidence 0.
- **10 identities deeply curated** into **29 pending contexts**; **0 are class A** (the current scorer could apply them safely) and **10 are class B** (valid evidence the scorer is too coarse to apply).

## What the deeply authored identities cover

| measure | value |
|---|---:|
| identities deeply authored | 10 |
| their product-active slots | 585 (0.8% of mapped slots) |
| their products | 550 |
| their Evidence=0 products | 281 |
| identities searched (bounded, logged) | 40 |
| their product-active slots | 4141 (6.0% of mapped slots) |

## Projected coverage if the owner approved the proposals

| outcome | Evidence=0 products affected |
|---|---:|
| would gain evidence under the CURRENT scorer (class A approvals) | 0 |
| held back because the current scorer is too coarse (class B) | 281 |

Every Wave 1 identity landed in class B. The curated evidence is real; the generic scorer cannot yet apply it without overgeneralising. That is the bridge to Phase 2, and it is measured rather than assumed.

## Top generic-scorer limitations exposed by real curated evidence

| limitation | evidence that exposed it | consequence |
|---|---|---|
| No population gate | isoflavones (all positive results in peri/postmenopausal women); DHEA (IVF with diminished ovarian reserve, adrenal insufficiency) | `clinical_applicability.py` validates and carries a `studied_population` string (line 241) but never compares it to anything, and the product's `target_population` is read only by the probiotic lane. Approving these records would transfer menopause/fertility-clinic evidence to every consumer product. |
| No material scoping from enricher-resolved forms | butterbur (PA-free Petadolex vs unspecified) | `required_form_terms` matches PRINTED label text; the resolved form identity lives on a different row, so the studied branded material cannot be selected. Probe: 61929 returned `clinical_form_mismatch` at exactly the studied 150 mg/day. |
| Multi-row identities silently fail to link | butterbur 328579 and 293376 (two butterbur rows each) | `_linked_rows` returns nothing when more than one canonical candidate row exists, so applicability cannot be assessed at all. |
| No exposure-basis concept | linoleic acid (whole-diet substitution trials at 7.5-20 g/day vs a 362 mg capsule) | Dietary-substitution evidence would become capsule efficacy across a 20-40x dose gap. |
| Dose floor cannot express 'positive only far above label' | gotu kola (12 g challenge positive, 1,000 mg null; label median 60 mg) | A record would credit label servings with evidence from doses they never deliver. |
| Null direction manufactures affirmative credit | 4 legacy null records | See GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW.md. |

## Null-evidence exposure (current behaviour, unchanged)

- 4 legacy records carry `effect_direction: null`; the generic scorer keeps 25% of their points.
- 2,423 scored products match at least one null record; for 249 of them the ONLY point-carrying evidence is a null record.
- No Wave 1 null-only record is proposed for approval until that semantic is decided separately.

## Source verification (subagent screening is a draft, never the record)

| measure | value |
|---|---:|
| records screened by subagents | 1554 |
| kept after screening | 668 |
| rejected with a reason code | 879 |
| shortlisted for central reading | 159 |
| handoffs proposed to other owners | 66 |
| shortlist PMIDs re-fetched live by Claude | 65 |
| PMIDs not found live | 0 |
| stored-vs-live title drift | 0 |
| integrity flags (erratum) | 2 |
| human status ambiguous (fails closed) | 16 |
| **quote rejected — ellipsis-joined fragments** | 25 |
| **quote rejected — composed, not in source** | 28 |

Every rejected quote was caught before authoring: Claude re-extracts each quote from the abstract itself, and `validate_wave1_contexts.py` re-checks each one as a substring. The authored contexts contain 0 unverified quotes. The screening brief was tightened mid-run and both agents were corrected.

## Coverage (see COVERAGE.md for the full tables)

| measure | value |
|---|---:|
| unique mapped identities | 773 |
| product-active slots | 69575 |
| identities covering 80% of slots | 66 |
| identities covering 90% | 143 |
| identities covering 95% | 248 |
| identities with a legacy record (review state NOT established) | 175 |
| identities with no record at all | 598 |
| identities with a completed review | 0 |

## Blocked outside evidence curation (routed, not fixed here)

| class | products | owner |
|---|---:|---|
| C | 86 | identity normalization / applicability owner |
| E | 2 | clinical evidence registry owner (legacy backfill) |
| H | 408 | ingredient role / identity classification owner |

## Legacy 202 backfill queue

All 202 legacy records lack study contexts; 195 carry no dose policy and 194 no applicability scope. Grandfathered means temporarily preserved, not permanently exempt — see LEGACY_BACKFILL.md.

## Artefacts

| file | contents |
|---|---|
| `COVERAGE.md` | coverage, category rollup, A–H taxonomy |
| `QUEUE.md` / `queue.json` | gap and exposure queues over 773 identities |
| `BLOCKER_ROUTING.md` | the products curation cannot fix, by owner |
| `LEGACY_BACKFILL.md` | the grandfathered 202, by catalog exposure |
| `GENERIC_EVIDENCE_NULL_DIRECTION_REVIEW.md` | measured null-direction exposure |
| `wave1_search_log.json` | exact queries, counts, truncation per identity |
| `wave1_contexts.json` | authored pending contexts + proposals |
| `wave1_live_verification.json` | live re-fetch findings |
| `docs/plans/EVIDENCE_EXPANSION_WAVE1_REVIEW_PACKET_2026-09.md` | the owner decision packet |

## Next wave, by leverage

Discovery already covers 40 identities; contexts were authored for the 10 with the best evidence clarity, not to a quota. The gap queue orders what remains.

