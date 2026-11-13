# Unread declared sources: 13 no-credit decisions (2026-11-13)

Receipts: one context per PMID in `source_finish_contexts.py`; applied by `apply_source_finish.py`.

| Record | PMID | Disposition | Main reason |
|---|---|---|---|
| BRAND_SETRIA | 24791752 | no credit | Glutathione body stores (exposure biomarker); Setria not named |
| BRAND_BIOCELL | 22486722 | no credit transferred | One positive OA trial; full text unread |
| BRAND_BIOCELL | 31221944 | no credit | Cosmetic skin endpoints in healthy women |
| INGR_LION_MANE | 18844328 | no credit transferred | 30-person MCI trial; benefit faded after stopping |
| INGR_INULIN | 35833477 | no credit | Microbiome surrogate; pooled preparations |
| PRECLIN_ASTAXANTHIN_GENERIC | 32755613 | no credit | Mostly null biomarkers; small or subgroup-only positives |
| PRECLIN_ASTAXANTHIN_GENERIC | 35091276 | no credit | Oxidative/inflammation biomarkers only |
| PRECLIN_ASTAXANTHIN_GENERIC | 38243785 | no credit | Fatigue rests on two studies; cognition not significant; exercise gains need training |
| INGR_BLACK_SEED_OIL | 21675032 | no credit | Seed capsules, no stated placebo, type 2 diabetes adjunct |
| INGR_BLACK_SEED_OIL | 37341696 | no credit | Small BP reductions; I² 84.7% / 97.3% |
| INGR_BLACK_SEED_OIL | 40210172 | no credit | Type 2 diabetes adjunct; several null outcomes |
| INGR_SEA_BUCKTHORN | 20554904 | no credit transferred | One dry-eye trial; mixed significance across ITT/PP |
| INGR_SEA_BUCKTHORN | 36043374 | no credit | Lipid effects only in abnormal-lipid subgroup; high heterogeneity |

## Method and checks

- No PMC full text exists for any of the 13 (PubMed ID converter, 2026-11-13). Each decision was read
  from the live PubMed abstract and states only abstract facts; claims from the record's earlier
  2026-11-08 inulin review are labelled as such.
- Independent check: a fresh-context Claude agent re-fetched all 13 abstracts. It confirmed every
  number, record assignment and no-credit disposition, and asked for seven wording/provenance fixes
  (unsupported "sponsor-associated" and "contract research organization", "seed-powder", an earlier-review
  claim worded as abstract fact, omitted SOD/isoprostane and "marginally significant" findings). All were
  applied; a final self-review also changed "cognition is null" to "not significant".
- Agent review, not clinician review (review delegation, AGENTS.md, Sean 2026-11-06).

## Effect

- `assess_clinical_source_review` is now complete for all seven records.
- Products: 0 status or score changes in a 309-product main-vs-branch replay (249 held + 60 controls).
  The resolver treats an all-noncredit record as a hold unless it is reference-only
  (`evidence_resolver.py` noncontributing_complete, the 2026-10-28 register). Releasing these products
  needs a credit tier on the Evidence ladder or a decision to finish the record as reference-only (zero).
- Out of scope, held on purpose by a signed parent `scoring_eligible: false`: BRAND_THERACURMIN,
  PRECLIN_PQQ, INGR_LACTOFERRIN, INGR_COLLAGEN_PEPTIDES.
