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
decision for every free-from claim group (`FREE_FROM_CLAIM_ALLERGENS`: gluten and
gluten_certified → wheat, rye, barley; dairy → milk; soy; nut → tree nuts and peanuts; peanut;
egg; shellfish → crustaceans and molluscs; sesame; yeast → none). An own-group source hit gives
`allergen_conflict`. An own-group cross-contact hit, or an unread may-contain sentence, gives
`may_contain_warning`. Gluten counts wheat, rye or barley as cross-contact (21 CFR 101.91(a)(1));
a rye or barley *ingredient* counts as a source while
`GLUTEN_GRAIN_INGREDIENT_CONTRADICTS_GLUTEN_FREE` is True (ledger D30). Readers:
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
- 2 products kept an unread-may-contain conflict at f6d876855: "(may contain trace amounts less
  than 20 ppm)" (273865, a gluten-free qualifier; no longer unread since the re-audit below) and a
  "may contain, soy, egg, …" list main's parser does not read (293779; #188 reads it).

**Disclosed, not changed.**
- 218190 keeps its B2 −2: a dairy-free claim and "produced in a facility that also handles dairy
  ingredients" is an own-group contradiction (the milk-facility + dairy-free control), so it does
  not go 13 → 15.
- 297644 and 274671 (barley grass ingredient, gluten-free claim): a wheat, rye or barley
  *ingredient* hit contradicts a gluten-free claim (`allergen_conflict`) while
  `scoring_input_contract.GLUTEN_GRAIN_INGREDIENT_CONTRADICTS_GLUTEN_FREE` is True. That
  reproduces main's B2 −2. Since the re-audit below, the compliance `gluten_free` flag (the badge),
  `claim_gluten_free_validated` and the claim evidence follow the same setting, so both products
  lose the badge. Whether processed grasses, wheat dextrin or malt may carry a gluten-free claim
  (21 CFR 101.91) is Sean's open question; his answer flips that one constant.

## Re-audit of #187 (H1, M1, L1, L4; head a69d80d86 on main 0826118d5)

- **H1.** An unread may-contain sentence now clears the compliance `gluten_free` flag (core
  `is_gluten_free`, the app's Gluten-Free badge) and `claim_gluten_free_validated`, not only B2.
  A sentence about gluten under 20 ppm is a gluten-free qualifier, not an unread allergen warning.
  293779 loses the badge; 273865 ("may contain trace amounts less than 20 ppm") keeps it and loses
  its B2 −2 (44.6 → 47.6).
- **M1.** B2's own-group match goes through `free_from_claim_contradiction` (`B2_CLAIM_GROUP_RULE`).
  The second group mapper (`_present_allergen_groups`) is deleted. Gluten-grain ingredient hits
  follow the one switch `GLUTEN_GRAIN_INGREDIENT_CONTRADICTS_GLUTEN_FREE` (see 297644 above).
- **L1.** `claim_allergen_free_validated` uses `free_from_claims_all_hold`: each claimed group must
  hold under the rule; an unknown claim key fails on any hit or unread warning.
- **L4.** A shellfish-free claim covers crustaceans and molluscs; a sesame-free claim covers sesame.

**Replay** (`~/pg_quality/lucidbanach_pr187_20261020/r2/`, same 784 frozen labels, `--full
--blob`, main 0826118d5 vs a69d80d86; an earlier run on main 2e80642ca at the lane root gave
identical counts):
- 541 records change; 0 allergen-hit changes; 0 status changes.
- 161 products gain 1.5–3.0 points, all B2 removed (+2.0 ×104, +3.0 ×40, +2.7 ×15, +1.5 ×2);
  26 tiers up, 0 down. Per product: `per_product_deltas.csv`.
- Gluten-Free badge (`gluten_free`) cleared on 3: 293779 (H1), 297644 and 274671 (M1). 364 regain
  `claim_gluten_free_validated`; 274671 loses it.
- 220 gain `claim_allergen_free_validated` (L1), 59 of them controls. Its only reader is the
  scorer's `claim_validations` metadata; no score moves from it.

## Low cleanups after #187/#188 (2026-10-20)

- A barley or rye **ingredient** (a source while `GLUTEN_GRAIN_INGREDIENT_CONTRADICTS_GLUTEN_FREE`)
  is recorded as "gluten-free claim conflicts with a gluten-grain source", and its claim evidence as
  `allergen_conflict:gluten grain detected`; "gluten-grain cross-contact" and "gluten/wheat
  detected" were wrong for it.
- The "< 20 ppm" exemption in the unread may-contain check covers only the qualifier clause; the
  rest of the sentence is still read ("May contain traces of grains processed on shared lines
  (tested below 20 ppm)" now voids the claim; 273865's qualifier alone does not).

Replay `~/pg_quality/lucidbanach_freefromcleanup_20261020/` (the #187 cohort, 784 labels, main
112bc904d vs the cleanup head): 2 records change, 297644 and 274671, in conflict wording and
evidence label only; 0 score, status, badge or allergen-hit changes. The ppm guard has no trigger
in this cohort.

## Gluten qualified by a ppm limit (2026-10-20, #211 audit dormant MEDIUM)

One helper, `enrich_supplements_v3._without_gluten_ppm_qualifier`, runs in the statement parser and
the unread may-contain check: a ppm **limit** (less than / below / under / <) and the gluten wording
attached to it, plus a gluten-free claim phrase in the same sentence, are the 21 CFR 101.91
qualifier; "May contain (milk and gluten below 20 ppm)." still names milk. Other allergens there still
read ("May contain milk and soy (gluten below 20 ppm)"), and a measured level ("Contains gluten
(40 ppm)") is not a limit. Before: "Gluten-free: may contain trace amounts of gluten below 20 ppm."
was an unread conflict, and "May contain less than 20 ppm gluten." / "May contain traces of gluten
(less than 20 parts per million)." parsed as wheat may-contain; each cleared the badge.

Replay `~/pg_quality/lucidbanach_ppmgluten_20261020/`: all 75 raw labels whose statements state a
ppm limit (273865 among them) + 150 controls, `--full --blob`: #211 head 879121a20 vs the first
fix, and (`r2/`) main ffc58287f vs the review-fixed head ef6e3f47f: 0 records change in both (a
dormant guard in today's corpus); 273865 keeps its badge.
