# Gluten-free claim validation and cross-contact warnings (2026-10-19)

**Defect.** `enrich_supplements_v3` set `gluten_contradiction = has_may_contain or …`, so any
may-contain or facility warning, milk-only included, voided a gluten-free claim and removed the
blob's `gluten_free_validated` (the app's gluten-free badge). The scorer's fallback in
`generic_transparency._derive_claim_validations` carried the same rule.

**Fix.** One rule, `scoring_input_contract.gluten_free_claim_contradicted`, used by both. It is
contradicted by a detected gluten/wheat conflict (unchanged), or by cross-contact with a
gluten-containing grain, 21 CFR 101.91(a)(1): wheat (*Triticum*), rye (*Secale*), barley
(*Hordeum*) and crossbreeds such as triticale; oats are not one (eCFR, read 2026-10-19). A
may-contain signal that no parsed warning explains (the compliance text fallback "may contain" /
"shared equipment") still voids the claim. Ingredient-source handling, and the open question on
gluten-free claims for processed wheatgrass, wheat dextrin and malt, are unchanged (Sean's).

**Census** (stored corpus artifacts, current enricher, discovery only): 12,449 products claim
gluten-free; 259 regain validation (their cross-contact warnings name milk, soy, tree nuts,
crustaceans, fish, eggs, peanuts only); 110 stay void on unparsed may-contain text. None of the 259
has an unparsed sentence pairing a cross-contact cue with wheat, gluten, barley, rye, spelt or
triticale.

**Replay** (`~/pg_quality/gluten_claim_20261019/`): `freeze-raw` 560 labels (260 affected incl.
the 18 from PR #186 and the 204624 wheat control, plus 300 seeded controls), `--full --blob`, main
bd40d66ef vs b38e396a2. 259 products change, all `gluten_free_validated` False → True (blob,
enriched `claim_gluten_free_validated`, scorer claim_validations); 0 score or tier moves (a
gluten-free claim earns no Transparency points, `b3_gluten_free` 0.0; B2 is separate); 0 status
or allergen-hit changes; 0 controls change; 204624 stays void.

Tests: `scripts/tests/test_gluten_claim_cross_contact.py` (real labels 229974, 304605, 218190 fail
first; control 204624; rule cases incl. barley, rye, oats, unparsed text).

**Review follow-up (00ff06594).** A parsed non-gluten warning no longer explains a separate
"may contain"/"shared equipment" sentence: the enricher runs each such sentence through the
statement parser, and one that yields no allergen keeps the claim void. Re-count over the 259:
all 259 still regain validation (no unparsed sentence among them), so the replay above stands.

**Claim evidence (Sean's review, follow-up commit).** The gluten-free claim's evidence objects
(`compliance_data.evidence_based.allergen_free_claims`, shipped in the blob as `compliance_detail`;
no app or scorer reader) were made ineligible (`may_contain_warning`) by any may-contain signal,
and a wheat facility statement was labelled `allergen_conflict` as if wheat were an ingredient.
They now follow the same rule: wheat/gluten as an ingredient or "contains" is
`allergen_conflict`; gluten-grain cross-contact or an unparsed may-contain sentence is
`may_contain_warning`; a warning naming only other allergens leaves the evidence eligible.
Corpus census (stored artifacts, old vs new code): 257 gluten evidence objects become eligible,
230 change reason allergen_conflict → may_contain_warning, 0 non-gluten evidence objects change.
The compliance `gluten_free` flag (core DB `is_gluten_free`) is unchanged. Test: 326701 (fish-only
facility warning) keeps the validated claim and eligible evidence; 204624 (wheat facility) is
`may_contain_warning`.

## Per-group free-from rule (audit of #187; final head f6d876855)

**Rule.** `scoring_input_contract.free_from_claim_contradiction(group, hits, unparsed)` is the one
decision for every free-from claim group (`FREE_FROM_CLAIM_ALLERGENS`: gluten, dairy, soy, nut,
peanut, egg, shellfish, yeast). An own-group source hit gives `allergen_conflict`. An own-group
cross-contact hit, or an unread may-contain sentence, gives `may_contain_warning`. Gluten counts
wheat as a source and wheat, rye or barley as cross-contact (21 CFR 101.91(a)(1)). Readers:
- the compliance gates (`dairy_free`, `soy_free`, `gluten_free` → core `is_gluten_free`, the app's
  Gluten-Free badge; barley/rye cross-contact now clears it);
- the claim evidence (`evidence_based.allergen_free_claims`; dietary claims keep the global
  may-contain check);
- the `claim_gluten_free_validated` projection and the scorer fallback;
- B2, whose any-warning branch now fires only for a generic allergen-free claim.

An unread may-contain sentence is one with allergen wording (traces, grain, gluten, nut, allergen,
shared equipment, ...) from which the parser reads no allergen. It reaches the scorer as
`UNREAD_MAY_CONTAIN_CONFLICT` in `compliance_data.conflicts` and is penalized through B2's
existing conflict path. Blob `gluten_free_validated` has no app reader (deprecated, audit_contract_sync).

**Replay** (`~/pg_quality/free_from_rule_20261020/`): `freeze-raw` 784 labels (484 with a
free-from claim and a cross-contact signal, plus the named products and 300 seeded controls),
`--full --blob`, main 625e90425 vs f6d876855.
- 481 records change; 0 allergen-hit changes; 0 status changes; 3 controls change only claim
  evidence reasons (a real milk/soy facility hit relabels allergen_conflict → may_contain_warning).
- **160 products gain 1.5–3.0 points**, all from B2 removed where no claimed group was contradicted
  (+2.0 ×104, +3.0 ×39, +2.7 ×15, +1.5 ×2). 26 tier changes, all up: Needs improvement → Good 11,
  Poor → Needs improvement 6, Good → Very good 9. 0 scores go down. Per product:
  `per_product_deltas.csv`. Examples: 328751 Triple Action Thyroid 80.9 → 83.9 (may contain fish,
  crustaceans; gluten-free claim); Centrum Adults 200827 72.4 → 74.4 ("supplements may contain the
  same ingredient" no longer counts as an allergen warning).
- 364 products regain `claim_gluten_free_validated`. Claim evidence: 359 gluten, 12 yeast and
  smaller dairy/soy/egg counts become eligible; 92 gluten evidence objects relabel
  allergen_conflict → may_contain_warning (a wheat facility is cross-contact).
- 2 products keep an unread-may-contain conflict, both genuine: "(may contain trace amounts less
  than 20 ppm)" and a "may contain, soy, egg, …" list main's parser does not read (#188 reads it).

**Disclosed, not changed.**
- 218190 keeps its B2 −2: a dairy-free claim and "produced in a facility that also handles dairy
  ingredients" is an own-group contradiction (the milk-facility + dairy-free control), so it does
  not go 13 → 15.
- 297644 (barley grass juice ingredient, gluten-free claim): a barley or rye ingredient does not
  contradict a gluten-free claim, as on main. That is the open 21 CFR 101.91 question (processed
  grasses, wheat dextrin, malt) for Sean.
