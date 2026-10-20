# Blend headers keep their identity, for interactions only (F2b) — October 20, 2026

Coordinator decision, quoted: "a header keeps its identity, and therefore its interaction rules through #185, while
routing and Dose read only score-eligible rows." Stacked on #196 after its delta audit fixes
(`claude/nonscorable-identity`, 31aa7f7b9).

## Change

1. `identity_integrity.resolve_identity`: the header exclusion is gone. A blend header keeps the
   identity its own cleaner standardName proves ("Caffeine Blend" → caffeine) on the same terms
   as a row: `NON_SCORING_IDENTITY_RATIONALE`, interaction-only. #196's
   `score_eligible_identity_view` keeps it out of the scorer, Evidence, routes and Dose.
2. A header's declared forms are its other members, never a contradiction of its name. 28981
   "Caffeine Blend" lists Anhydrous Caffeine and Piperine; 17471 "Chondroitin Sulfate Complex"
   lists seven members. Headers keep only #196's form-derived-match rule.
3. The #181 export pin (`test_identity_label_named_over_group`) now states one row, one identity:
   1646's header exports the enricher's probiotics.

## Measurement

1,984 labels (the F2 cohort plus every product with an identified header). Base #196 31aa7f7b9,
candidate this branch, `replay.py snapshot --full --blob`. Records:
`~/pg_quality/lostsubj_pr203_20261020/` (`base2.jsonl`, `cand3.jsonl`, `compare3.json`). Per
product: `f2b_fulldiff.out`.

- **0 score moves, 0 product_safety_status changes, 0 rules removed.** No scored artifact differs
  from #196's (`compare3.json`). Header identities are interaction-only through #196's view.
- **+11 rules**, each on a header whose printed name is the substance:
  - RULE_INGREDIENT_CAFFEINE: Ravage 1179, 12800, 28981.
  - RULE_IQM_CHONDROITIN: Flex-A-Min 17471, 17536, 17539.
  - RULE_INGREDIENT_CURCUMIN: 210718, 59451.
  - RULE_IQM_CINNAMON_GLUCOSE: 74847, 78446.
  - RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED: 1646.

## For Sean (not changed here)

`for_sean_main_header_scoring.tsv`, from the first F2b build, lists 25 products (16 up, 9 down).
They would move if routing and Dose also stopped reading the header identities main already
scores: Univestin, Sterols, Organic Turmeric Blend, Pancreatin, PureAlgaeOmega3, Fiber Blend.
Should a header's printed-name identity stay a scoring anchor? That is a policy decision.

"adrenal"/"prostate" → organ_extracts remain cleaner-matcher defects on headers (organ_extracts has
no rules). Listed for the cleaner lane.
