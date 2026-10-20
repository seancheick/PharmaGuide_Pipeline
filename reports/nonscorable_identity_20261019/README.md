# Non-scorable rows keep their identity, for interactions only (F2, option a) — October 20, 2026

Coordinator decision (option a): restore identity on non-scorable **rows** only. Blend headers wait
for a separate follow-up. Only score-eligible rows may route. Both independent audits are
addressed below: the first (B1, H1, M1, L-arginine, L1) and the delta (HIGH1, HIGH2, MED3, MED4,
Polydatin).

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
   - the identity came from a declared marker form (59766 "Sawasabi Wasabi powder", "Total
     Isothiocyanate"; 277367 "Glycosides", form Polydatin, resveratrol's glucoside);
   - a declared form names another substance (176044 "Arginine", form "Whey Protein Isolate");
   - any enclosing label row names another material (79397 "Arginine" in "Solae Soy Protein
     isolate"; 80495 "Arginine" in Amino Acids in Cilantro).

   A member of the identity's family still keeps it ("Lactobacillus": L. acidophilus …, via
   `INTERACTION_SUBJECT_FAMILY` or the IQM parent predicate). Data (`b1_data_batch.py`):
   - century_plant (Agave americana) loses the genus-only alias "agave extract", so 31062
     "Agave powder" (DSLD group "Agave") is no longer A. americana; the species stays unknown.
   - wasabi_root gains the printed "sawasabi wasabi powder". The label prints "Wasabi powder" in
     group "Japanese Horseradish"; the Sawasabi brand itself was not independently verified.
3. **M1, identity is not scorability.** Only this keep sets the marker
   (`NON_SCORING_IDENTITY_RATIONALE`). Non-scorable recognition that identifies the row itself
   clears it, as on main: 252567 coptis, 315814/33607 oat straw, 17226 oat, 62890 beetroot powder.
   - `scoring_input_contract.score_eligible_identity_view` / `_as_scored` blank only the identity
     fields of a marked row. Printed and standard names are left as they are, so nothing re-matches
     the row (40089 coffeeberry is never "coffee").
   - Applied at: the scorer entry (`score_product_v4`, `build_scored_artifact`), the enrich-time
     evidence matcher and route classification, and `derive_product_scoring_evidence`.
   - Such a row meets interaction rules but is invisible to scoring.
4. **Routing:** `_classify_botanical_owner_type` is main's, so the earlier lent-blend routing hunk
   is dropped. 327570 stays generic_iqm on main's function.
5. **H1:** `_named_in_title` is main's rule again. The derived-word restriction existed only
   because restored identities reached scoring (204521 "Fit Coffee"); M1 removes that path. A
   static census over all 122,516 enriched rows of the 15,414-label baseline found 250
   legitimate title matches it lost (Folate 400 / L-5-MTHF, Biotin / Vitamin B7):
   `h1_title_flips_rejected_rule.tsv`, `title_flip_census.py`.

## Measurement

1,540 labels (940 with identity erased on the 951a05415 capture, 600 seeded controls, plus the
audit's products). `replay.py snapshot --full --blob`, base main 92881c049 vs this branch.
Records: `~/pg_quality/lostsubj_pr196_20261020/` (`base3.jsonl`, `cand3.jsonl`, `compare3.json`).
Per product: `f2a_fulldiff.out`.

- **0 score moves, 0 product_safety_status changes, 0 rules removed.**
- **+56 interaction rules:**
  - probiotics immunocompromised 45;
  - yerba mate 6;
  - aloe vera 3;
  - L-arginine 1 (315814 Staminol's declared L-arginine);
  - lion's mane 1.
- **Scored artifacts equal main for 1,539 of 1,540.** The exception is 59766, where the printed
  "Sawasabi Wasabi powder" now maps to wasabi_root through the new data alias. wasabi_root joins
  its Evidence owners (broccoli, watercress) at an unchanged score, 41.4. Only 31062 and 59766
  change at Clean (the data fix).

## L-arginine

The 27 additions on the first candidate were not-printed constituents of whey, casein, soy-protein
or food amino profiles. B1 removes them, because forms or enclosing rows name the protein or food.
One remains: 315814 Staminol declares L-Arginine itself inside a proprietary blend. The rule's
sources (PMID 15133406 review; 16391217 VINTAGE MI at 3 g three times a day) set no dose
threshold, so a cutoff would be a new policy. The ~90 main products already carrying it are
unchanged.

## For Sean

- Cleaner identities with no rule today, so nothing fires: gamma-carotene → vitamin_a, calcium
  silicate → silicon.
- The lent-blend routing change (327570 class) is dropped from this PR. If it is still wanted, it
  needs its own PR with a corpus measurement (it moved 9 products: 18540, 2222/28978, 259883-5,
  28554/28559, 326692).
