# Blend headers keep their identity, for interactions only (F2b) — October 20, 2026

Coordinator decision, quoted: "a header keeps its identity, and therefore its interaction rules through #185, while
routing and Dose read only score-eligible rows." Stacked on #196 after its delta audit fixes
(`claude/nonscorable-identity`, 31aa7f7b9).

## Change

1. `identity_integrity.resolve_identity`: the header exclusion is gone. A blend header keeps the
   identity its own cleaner standardName proves ("Caffeine Blend" → caffeine) on the same terms
   as a row: `NON_SCORING_IDENTITY_RATIONALE`, interaction-only. #196's
   `score_eligible_identity_view` keeps it out of the scorer, Evidence, routes and Dose.
2. **A header keeps only an identity its printed name or a member names** (audit fix).
   - A header's declared forms are its members.
   - It keeps an identity only when its printed name spells the identity's standard name, or a
     member resolves to it or spells it. When members resolve, one of them must name it.
   - The cleaner's standardName alone never names a header.
   - Refused: 204571/274389 "Organic Adrenal Blend" (schisandra, rhodiola, ashwagandha, eleuthero);
     33607 "Prostate Formula" (saw palmetto, beta-sitosterol, pumpkin seed, lycopene); 228823
     "Glutamic Acid" (members caseinate, whey, egg albumin, milk protein).
   - Kept: "Caffeine Blend" (member Anhydrous Caffeine), "Chondroitin Sulfate Complex", 1646
     probiotics, "Cinnamon bark powder".
   - 210718/59451 "Total Curcuminoids complex" now go unidentified: its one member resolves to
     volatile oils. That is main's behavior (no curcumin warning); **for Sean**.
3. The #181 export pin (`test_identity_label_named_over_group`) now states one row, one identity:
   1646's header exports the enricher's probiotics.

## Measurement

1,984 labels (the F2 cohort plus every product with an identified header). Base main d798be30b
(with #196), candidate this branch, `replay.py snapshot --full --blob`. Records:
`~/pg_quality/lostsubj_pr203_20261020/` (`base4.jsonl`, `cand4.jsonl`, `compare4.json`). Per
product: `f2b_fulldiff.out`.

- **0 score moves, 0 product_safety_status changes, 0 rules removed.** No scored artifact differs
  from main's.
- **+9 rules**, each on a header whose printed name or a member names the substance:
  - RULE_INGREDIENT_CAFFEINE: Ravage 1179, 12800, 28981.
  - RULE_IQM_CHONDROITIN: Flex-A-Min 17471, 17536, 17539.
  - RULE_IQM_CINNAMON_GLUCOSE: 74847, 78446.
  - RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED: 1646.

## Cleaner matcher: "adrenal" / "prostate"

Not fixed in data. The bare aliases cannot be removed without losing real glandular rows. The
cleaner strips "powder"/"concentrate" from aliases and descriptors ("Organic", "Blend", "Formula")
from labels. So "Adrenal powder" (200725, a glandular row) and "Organic Adrenal Blend" reach the
same key "adrenal", and "prostate concentrate" derives "prostate". The header rule above refuses
the formula headers. A context-aware fix (keep "blend"/"formula" for organ terms) belongs to the
cleaner lane.

## For Sean (not changed here)

`for_sean_main_header_scoring.tsv`, from the first F2b build, lists 25 products (16 up, 9 down).
They would move if routing and Dose also stopped reading the header identities main already
scores: Univestin, Sterols, Organic Turmeric Blend, Pancreatin, PureAlgaeOmega3, Fiber Blend.
Should a header's printed-name identity stay a scoring anchor? That is a policy decision.

"adrenal"/"prostate" → organ_extracts remain cleaner-matcher defects on headers (organ_extracts has
no rules). Listed for the cleaner lane.
