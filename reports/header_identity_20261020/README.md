# Blend headers keep their identity for interactions (F2b) — October 20, 2026

Coordinator decision after F2 option (a), quoted: "a header keeps its identity, and therefore its
interaction rules through #185, while routing and Dose read only score-eligible rows. Measure first
whether that alone takes the 46 moves to zero."

Stacked on #196 (F2a, `claude/nonscorable-identity`).

## Change

1. `identity_integrity.resolve_identity`: the F2a header exclusion is gone. A blend header now keeps
   the identity its own cleaner standardName proves ("Caffeine Blend" → caffeine), under the same
   guards as a row (no role/catch-all record, no stale id the label never named). When that
   standardName is the **only** proof, the decision's rationale is
   `HEADER_INTERACTION_ONLY_RATIONALE`.
2. `scoring_input_contract`: a header carrying that rationale is read exactly as main reads it: no
   canonical, the printed heading as a structural anchor (`derive_product_scoring_evidence`,
   `_verified_anchor_canonical`). Header identities main already proves from the label itself
   (Univestin, Pancreatin, Sterols, "Organic Turmeric Blend") are untouched.

## Measurement

Cohort: the F2 cohort plus every product with an identified header (1,984 labels). `replay.py
snapshot --full --blob`; base #196 8cd35efe2, candidate this branch. Per product: `f2b_fulldiff.out`
(`fulldiff.py`).

- **0 score moves, 0 product_safety_status changes, 0 rules removed.**
- **+11 rules**, each on a header whose printed name is the substance:
  - RULE_INGREDIENT_CAFFEINE: Ravage 1179, 12800, 28981 ("Caffeine Blend"). This closes the open
    caffeine item from F2a.
  - RULE_IQM_CHONDROITIN: Flex-A-Min 17471, 17536, 17539 ("Chondroitin Sulfate Complex").
  - RULE_INGREDIENT_CURCUMIN: 210718, 59451 ("Total Curcuminoids complex").
  - RULE_IQM_CINNAMON_GLUCOSE: 74847, 78446 ("Cinnamon bark powder").
  - RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED: 1646 ("Probiotic Complex Blend").
- Raw canary check (`freeze_contract_snapshots.py --check`): 33 checked, 0 failed.
- An earlier candidate that stripped **every** taxonomy-only header from scoring moved 25 products. On
  #196 those headers already score through identities their printed names prove. That variant was
  not shipped; see below.

## For Sean (not changed here)

`for_sean_main_header_scoring.tsv` lists 25 products (16 up, 9 down). They would move if routing and
Dose also stopped reading the header identities main already uses:

- Univestin headers that earn blend-total-only botanical Dose and Formulation (243676 57.1→31.0,
  45114).
- Sterols/Sterolins headers owning Evidence (Moducare 182620, 291789).
- "Organic Turmeric Blend" headers (274426, 327412, 327767: Evidence 0→15.6).
- Pancreatin/enzyme headers (298024, 298029, 321966, 328828).
- PureAlgaeOmega3 (297604, 321375).
- Fiber Blend (40581, 40595).
- Others: Diindolylmethane Complex 246078, the Omega-Zyme enzyme blends and 70066 (full list in the
  TSV).

Is a header's printed-name identity an acceptable scoring anchor, or should routing and Dose read
only score-eligible rows for every header? That is a scoring-policy decision.

## Still open from F2a

"adrenal"/"prostate" → organ_extracts are cleaner-matcher defects on headers. organ_extracts has no
rules, so this branch adds none. Listed for the cleaner lane.
