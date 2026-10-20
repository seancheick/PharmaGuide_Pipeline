# Non-scorable rows keep their identity, for interactions only (F2, option a) — October 20, 2026

Coordinator decision (option a): restore identity on non-scorable **rows** only. Blend headers wait
for a separate follow-up. Fix the botanical-routing leak in the same PR: only score-eligible rows
may route. Independent audit (B1, H1, M1, L-arginine, L1) addressed below.

## Change

1. **Kept identity** (`identity_integrity.resolve_identity`, `retained_unscoreable_canonical`). A
   non-scorable row keeps its supplied identity when the cleaner's `standardName` for the row is
   an exact registry name or alias of it. Other conditions:
   - the label names no other identity;
   - it is not a blend header;
   - it is not a role or catch-all record.

   It carries `NON_SCORING_IDENTITY_RATIONALE`.
2. **B1, contradictions refuse the keep.** The cleaner stamps the standardName of the id it
   mapped, so that check proves nothing a declared form contradicts. The keep is refused when:
   - the cleaner took the identity from one declared form and the row lists several (288699,
     327963, 334431 "Bifidobacterium", forms B. bifidum + B. animalis lactis);
   - the identity came from a plant's marker form (59766 "Sawasabi Wasabi powder", "Total
     Isothiocyanate");
   - a declared form names another substance (176044 "Arginine", form "Whey Protein Isolate");
   - the parent row names another material (79397 "Arginine" in "Solae Soy Protein isolate").

   A member of the identity's family still keeps it ("Lactobacillus": L. acidophilus …, via
   `INTERACTION_SUBJECT_FAMILY` or the IQM parent predicate). Data (`b1_data_batch.py`):
   - century_plant (Agave americana) loses the genus-only alias "agave extract", so 31062
     "Agave powder" (DSLD group "Agave") is no longer A. americana; the species stays unknown.
   - wasabi_root gains the printed "sawasabi wasabi powder". The label prints "Wasabi powder" in
     group "Japanese Horseradish"; the Sawasabi brand itself was not independently verified.
3. **M1, identity is not scorability.** `scoring_input_contract.score_eligible_identity_view`
   hides a kept identity from:
   - the scorer (`score_product_v4`, `build_scored_artifact`);
   - the enrich-time evidence matcher (`evidence_data`) and route classification
     (`product_scoring_classification`);
   - `derive_product_scoring_evidence`.

   Such a row meets interaction rules but owns no Evidence and feeds no Dose or route. A later
   owner that re-identifies the row (62890 "organic Beet" → Beetroot Powder, as on main) ends the
   interaction-only status.
4. **Routing** (`_classify_botanical_owner_type`): a blend total lent to a member
   (`is_lent_blend_mass`) cannot outrank non-botanical actives that carry their own label amounts
   (327570 Methyl B12: "Beet" borrowing a 242 mg Food Blend beside B12, B6, folate).
5. **H1:** `_named_in_title` is main's rule again. The derived-word restriction existed only
   because restored identities reached scoring (204521 "Fit Coffee"); M1 removes that path. A
   static census over all 122,516 enriched rows of the 15,414-label baseline found 250
   legitimate title matches it lost (Folate 400 / L-5-MTHF, Biotin / Vitamin B7):
   `h1_title_flips_rejected_rule.tsv`, `title_flip_census.py`.

## Measurement

1,540 labels (940 with identity erased on the 951a05415 capture, 600 seeded controls, plus the
audit's products). `replay.py snapshot --full --blob`, base main 2e80642ca vs this branch.
Records: `~/pg_quality/lostsubj_pr196_20261020/` (`base.jsonl`, `cand2.jsonl`). Per product:
`f2a_fulldiff.out` (`fulldiff.py`).

- **+57 interaction rules, 0 removed, 0 product_safety_status changes:**
  - probiotics immunocompromised 45;
  - yerba mate 6;
  - aloe vera 3;
  - L-arginine 2;
  - lion's mane 1.
- **9 score moves, all routing class.** Each one returns to main's score when only main's
  `_classify_botanical_owner_type` is swapped in:
  - 18540 Muscle Igniter;
  - 2222/28978 Re-Forge;
  - 259883-5 Aloe Gorgeous;
  - 28554/28559 Daily;
  - 326692 Beets Gummies (debatable, **for Sean**).

  No move from identity or title.
- The audit's leak products match main: 274777, 334429, 317030 (probiotic Evidence), 297685/6
  (gamma-carotene), 40089/278416 (flavor title), 178728 (iron Dose), 204521 (Fit Coffee).

## L-arginine

The 27 additions on the first candidate were not-printed constituents of whey/casein amino
profiles. B1 removes them, because their forms or parent name the protein. Two remain:
- 315814 Staminol declares L-Arginine itself inside a proprietary blend: a real supplemental
  source. It keeps the rule.
- 80495 Alive! Multi-Vitamin lists Arginine under "Amino Acids" inside Cilantro, a whole-food
  composition two levels up. The identity owner does not see that ancestor. **For Sean.**

The rule's sources (PMID 15133406 review; 16391217 VINTAGE MI at 3 g three times a day) set no dose
threshold, so a cutoff would be a new policy. The ~90 main products already carrying it are
unchanged.

## For Sean

- 326692 Beets Gummies route change (above).
- 80495 cilantro-composition arginine (above).
- Evidence for 259714 Essential Amino Complete is unchanged from main.
