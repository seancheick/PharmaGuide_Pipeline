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
