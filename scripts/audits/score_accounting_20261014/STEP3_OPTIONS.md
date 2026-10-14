# V4.1 Step 3: measured policy options (October 14, 2026)

Read-only. Nothing here changes a score; each option needs Sean's choice before Step 4.

## Method

- **Data.** The stored Stage-3 module breakdowns of all 15,123 scored products (config 1.23.0, scored October 14, before PR143's Formulation delivery change). Absolute numbers will shift slightly on delivery-affected products after the rebuild. The comparisons between options do not depend on that.
- **Harness.** Each option is a set of transforms applied in memory to a deep copy of each breakdown, for example removing a component or penalty, replacing a band value, or rebasing a reference.
  - The changed dimensions are recomputed with the module arithmetic the receipts replay. The result is re-assembled by the `claude/score-ledger` assembler.
  - Every option's receipts still reconcile: **0 errors in every run**, so the option arithmetic is self-consistent.
  - The harness and its result files are private receipts in `~/pg_quality/score_accounting_20261014/` (`step3_whatif.py`, `step3_*.json`), alongside the Step 2 reconciliation scripts. This report records every number they produced.
- **References.** When an option removes a component, the route's normalization reference is rebased to the maximum the retained components can reach. Otherwise every product on the route would drop for no new fact. Each rebased reference is listed with its transform.
- **Not simulated:**
  - A generic DRI product with a hidden amount: readiness already withholds a score when a required amount is missing.
  - Collagen, which is excluded from the hiding check.
  - B1 moving to the sixth pillar assumes a cap of 10 and keeps excluding low-severity excipients, as the current mirror does.

## Transforms

| Transform | What it does | References rebased |
|---|---|---|
| mirrors | Removes the B1 and B7 Safety mirrors (F1, F2). | — |
| b0_sixth | Removes Formulation B0; the sixth-pillar base stays the only owner (F4). | — |
| b0_none | b0_sixth, plus the base no longer zeroes for high-risk or watchlist matches (Codex's variant). | — |
| b0_formulation_owner | Keeps Formulation B0; the base no longer zeroes for high-risk or watchlist matches. | — |
| branded | Removes the branded-studied extra (+3) in Formulation; standardization stays (F13). | — |
| probiotic_gate | Probiotic Evidence certainty and replication earn nothing when applicability is 0 (F15). | — |
| count | Removes sports protein focus and route base, fiber focus, route base and practicality, B-complex focus purity, the sports single-only completion and stack support. | Formulation: sports protein 29→23, fiber 28→18, B-complex 23→20. Dose: sports 25→20. |
| blend | Transparency is the only owner of blend opacity. Removes the sports Dose −10 and the sports opaque-protein penalty; a blend alone no longer withholds the complete-disclosure bonus (F17). | — |
| disclosure | Removes points awarded only because something is printed: multi and B-complex disclosure structure, probiotic total CFU, sports protein dose and amino disclosure, fiber disclosure, botanical plant part and printed amount, collagen type, source and amount, fiber dose disclosure, probiotic per-strain CFU disclosure. Strain identity stays: it is the probiotic's form. | Formulation: botanical 15→12, collagen 15→8, multi 14→12, B-complex 20→18, probiotic 15→11, sports protein 23→15, fiber 18→12. Dose: probiotic 22→15, fiber 25→24. |
| neutral(N) | One public Dose value N wherever no benchmark applies, whether or not the amount is printed: botanical and collagen no-reference, blend and no-amount bands, and generic no-reference credit. | — |
| probiotic_floor | A disclosed strain dose never scores below the aggregate-CFU floor that an undisclosed one gets. | — |
| additive_sixth | B1 additive and sugar move entirely to the sixth pillar (cap 10, low-severity excluded); Formulation stops charging them. | — |

## Measured effect of each transform alone and of each option

| Scenario | Moved | Mean Δ | p5 / p95 | Tier changes | Errors |
|---|---:|---:|---|---:|---:|
| M:mirrors | 3,710 | +0.66 | +0.0 / +4.0 | 902 | 0 |
| M:b0_sixth | 332 | +0.21 | +0.0 / +0.0 | 80 | 0 |
| M:b0_none | 357 | +0.43 | +0.0 / +0.0 | 300 | 0 |
| M:b0_formulation_owner | 357 | +0.22 | +0.0 / +0.0 | 63 | 0 |
| M:branded | 56 | -0.01 | +0.0 / +0.0 | 21 | 0 |
| M:probiotic_gate | 103 | -0.07 | +0.0 / +0.0 | 42 | 0 |
| M:count | 1,118 | -0.01 | +0.0 / +0.0 | 177 | 0 |
| M:blend | 309 | +0.12 | +0.0 / +0.0 | 110 | 0 |
| M:disclosure | 7,027 | -0.41 | -2.8 / +1.8 | 1,307 | 0 |
| M:neutral_10 | 5,549 | -0.73 | -4.5 / +0.5 | 826 | 0 |
| M:neutral_11.4 | 3,776 | -0.22 | -3.1 / +1.9 | 684 | 0 |
| M:additive_sixth (with mirrors) | 7,693 | +1.63 | +0.0 / +7.2 | 2,185 | 0 |
| A: ownership (mirrors, b0_sixth, branded, probiotic_gate, count, blend) | 4,756 | +0.90 | +0.0 / +5.0 | 1,222 | 0 |
| B: A + disclosure + neutral 11.4 | 11,020 | +0.02 | -3.1 / +4.4 | 2,141 | 0 |
| B': B with b0_none | 11,021 | +0.25 | -3.1 / +5.1 | 2,372 | 0 |
| **B3: B, neutral only without a benchmark, probiotic floor** | 11,008 | +0.05 | -3.1 / +4.4 | 2,135 | 0 |
| C: A + disclosure + neutral 10 + additive_sixth | 12,552 | +0.71 | -4.5 / +8.1 | 3,949 | 0 |

Mean change by route:

| Option | b_complex | fiber | generic | multi/prenatal | omega | probiotic | sports |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | +1.90 | -0.11 | +0.65 | +2.06 | +0.44 | -1.50 | +3.18 |
| B | +1.48 | -1.88 | -0.22 | +1.36 | +0.44 | -4.92 | +2.82 |
| B3 | +1.48 | -1.88 | -0.22 | +1.36 | +0.44 | -3.83 | +2.71 |
| C | +3.29 | -1.25 | -0.12 | +4.42 | +1.02 | -3.27 | +4.27 |

## Invariant: hiding information must never raise the total

**This is the main Step 3 finding.**
- Today's disclosure credits in Dose are what keep the invariant true for sports and probiotics.
- Removing them (B, C) breaks it:
  - Hiding a sports primary amount scores a neutral above a verified low band (8 for low creatine or protein).
  - Hiding per-strain CFU earns the aggregate-CFU floor, which beats a verified-low strain dose (0).
- B3 restores it with two rules, and nothing else:
  1. The neutral applies only where **no benchmark exists**. When a benchmark exists and the amount is hidden, the dose cannot be assessed and gets no neutral uplift, as sports already work today.
  2. The probiotic aggregate floor is the minimum for disclosed strain doses too.
- Counterfactuals:
  - Botanical: the primary amount is removed, the Dose band becomes "no amount", the Formulation printed-amount credit and the Transparency complete-disclosure bonus are lost.
  - Sports: the primary amount is removed and the complete-disclosure bonus is lost.
  - Probiotic: per-strain CFU is removed but the total CFU stays printed.

| Option | Botanical | Sports | Probiotic |
|---|---|---|---|
| Today | 0 of 2,413 | 0 of 901 | 0 of 145 |
| A | 0 of 2,413 | 0 of 901 | 0 of 145 |
| B | 0 of 2,413 | 46 of 901 (max +9.0) | 39 of 145 (max +2.9) |
| C | 0 of 2,413 | 26 of 901 (max +7.6) | 39 of 145 (max +2.9) |
| B2: B with a sports neutral of 8 and the probiotic floor | 0 of 2,413 | 4 of 901 (max +5.6) | 0 of 145 |
| **B3** | 0 of 2,413 | 0 of 901 | 0 of 145 |

## Representative products

| Product | Today | A | B3 | C |
|---|---:|---:|---:|---:|
| 180213 Airborne Citrus | 45.7 | 51.7 | 50.8 | 56.8 |
| 240372 Airborne Elderberry | 67.9 | 70.9 | 69.9 | 73.6 |
| 64233 Airborne Everyday | 68.8 | 70.8 | 70.4 | 76.0 |
| 223147 Creatine HCl | 53.1 | 54.7 | 54.7 | 54.7 |
| 252349 Bamboo Extract (Meru-like) | 55.7 | 55.7 | 55.7 | 54.3 |
| 252413 Garcinia Cambogia Extract | 35.1 | 45.7 | 45.7 | 44.3 |
| 252461 Glycerol Monostearate | 57.5 | 57.5 | 54.4 | 53.0 |
| 252510 Grass-Fed Whey Protein Isolate | 80.8 | 81.0 | 83.6 | 83.6 |
| 252551 Inulin | 64.8 | 62.2 | 60.0 | 60.0 |
| 252686 Manganese Gluconate | 70.3 | 70.3 | 70.3 | 70.3 |
| 294458 Collagen Softgels | 51.2 | 51.2 | 57.4 | 56.0 |
| 310750 Magnesium Glycinate | 81.6 | 81.6 | 81.6 | 81.6 |
| 18174 Adult 50+ Probiotic | 42.6 | 32.6 | 32.3 | 29.4 |
| 64540 CVS Prenatal Gummy | 67.7 | 69.7 | 68.3 | 70.5 |
| 19028 Centrum Specialist Prenatal | 69.7 | 73.7 | 74.1 | 76.8 |
| 218073 Culturelle Advanced Care | 68.6 | 70.6 | 62.3 | 67.5 |
| 322633 Whey Protein French Vanilla | 67.9 | 69.9 | 72.9 | 72.9 |
| 306220 Folic Acid 1,200 mcg | 70.3 | 70.3 | 70.3 | 70.3 |
| 313920 Thorne Omega Superb | 72.2 | 72.2 | 72.2 | 72.2 |

**Tier changes.**
- **A:** Needs improvement → Good 546; Good → Very good 347; Poor → Needs improvement 178; Needs improvement → Poor 60; Very good → Excellent 51; Good → Needs improvement 12; Very good → Good 11; Excellent → Exceptional 9; Needs improvement → Very good 4; Excellent → Very good 3; Exceptional → Excellent 1.
- **B3:** Needs improvement → Good 521; Poor → Needs improvement 407; Needs improvement → Poor 376; Good → Needs improvement 298; Good → Very good 289; Very good → Good 163; Very good → Excellent 52; Excellent → Very good 21; Exceptional → Excellent 3; Excellent → Exceptional 3; Needs improvement → Very good 2.
- **C:** Needs improvement → Poor 1,238; Good → Very good 907; Needs improvement → Good 855; Good → Needs improvement 333; Poor → Needs improvement 296; Very good → Excellent 137; Very good → Good 112; Excellent → Exceptional 40; Needs improvement → Very good 13; Excellent → Very good 12; Poor → Good 5; Very good → Exceptional 1.

## Pillar-level detail of the largest movers

- **Restore Advance XR** (`caution`), A: 45.7 → 63.0. Formulation 2.7 → 20.0 once Formulation B0 is removed; its sixth pillar stays 0/10.
- **Resveratrol Plus+** (`caution`), A: 34.0 → 55.3. Formulation 2.7 → 18.0 (B0), and Transparency 5.3 → 11.3 because a blend alone no longer withholds the disclosure bonus.
- **Ravage Grape** (`caution`), A and B3: 22.0 → 31.4. Formulation 2.7 → 12.1 (B0 and the opaque-protein penalty removed). Dose stays 0 under B3: the amount is hidden while a benchmark exists.
- **Multi-Acidophilus Powder**, B3: 63.2 → 43.6.
  - Evidence 10 → 0: certainty without applicability.
  - Dose 9.1 → 2.7: the per-strain disclosure credit is gone and adequacy is low.
  - Formulation 11.1 → 7.9: the total-CFU disclosure credit is gone.
- **Culturelle Advanced Care**, B3: 68.6 → 62.3. The Formulation and Dose disclosure credits leave, and the Safety mirror gives back 2.

## Decisions for Sean

| # | Decision | Options measured | Recommendation |
|---|---|---|---|
| D1 | Safety mirrors (F1, F2) | Remove: 3,710 products up, mean +0.66, 902 tier changes | **Remove.** One fact, one numerical owner; the copy keeps every concern visible. |
| D2 | High-risk/watchlist owner (F4) | (a) Sixth pillar: 332 products up, mean +0.21, largest +17.3. (b) Formulation: 357 products +10, and their sixth pillar returns to 10/10 beside `caution`. (c) None (Codex): 357, mean +0.43, sixth pillar 10/10. | **(a) Sixth pillar.** (b) and (c) put a full screen beside a caution. With one owner, the quality consequence of a high-risk ingredient caps at 10 instead of up to about 23. The caution status and warnings stay. |
| D3 | Disclosure has one owner (F5) | With rebased references: 7,027 products move, mean −0.41. Probiotics are hit hardest (B3 route mean −3.83). | **Adopt, with B3's rules**, because without them the hiding invariant breaks. |
| D4 | Neutral value N for unknown adequacy (F7) | 11.4 (today's botanical value): 3,776 move, mean −0.22. 10: 5,549 move, mean −0.73, and Meru-like botanicals drop below the 55 tier line (C: 1,238 "Needs improvement → Poor"). | **N = 11.4**, applied only where no benchmark exists. Choose 10 only together with a tier review. |
| D5 | Probiotic floor as a minimum | Needed for the invariant once the per-strain disclosure credit leaves. | **Adopt** with D3. |
| D6 | B1 additive/sugar owner | Formulation (A, B3), or the sixth pillar with cap 10 (alone: 7,693 move, mean +1.63, 2,185 tier changes). Under the sixth pillar, low-severity excipients stop charging at all. | **Formulation.** Moving it is the largest single redistribution and weakens additive consequences for multis. Decide separately if wanted. |
| D7 | Probiotic certainty without applicability (F15) | Gate it: 103 products lose 10 Evidence. | **Gate.** "Applicability not established" then means the same on every route. |
| D8 | Count and route-base bonuses (F11) | Remove with rebased references: 1,118 move, mean −0.01. | **Remove.** |
| D9 | Blend opacity owner | Transparency only: 309 move, mean +0.12. | **Adopt.** |
| D10 | Branded studied double (F13) | Remove the +3: 56 move. | **Remove.** |
| D11 | Multi `panel_breadth` (open-ended count) | Not measured. | Keep as a category panel, or measure in Step 4; Sean decides. |

**Recommended option: B3** (A + D3 + D4 at 11.4 + D5).
- Mean effect +0.05; 11,008 products move; 2,135 tier changes.
- The hiding invariant holds in all three routes.
- Every concern has one numerical owner.
- Unchanged: Verification 6 and the six pillars and their weights.
- Tier thresholds are reviewed after this distribution exists (Stage 3 of the plan), not before.

## Step 4 change summary for B3 (not applied)

- **Config** (`quality_score.json`):
  - `safety_hygiene_subscale` mirror caps go to 0, or the mirror code is removed.
  - The rebased references listed above.
  - Botanical and collagen no-benchmark, blend and no-amount bands become one neutral entry (11.4 public).
  - Generic `no_reference_*` credits are expressed as the same neutral.
  - Sports and fiber route bases are removed.
- **Code owners:**
  - `generic_formulation` B0 is removed.
  - Profile components are removed from `botanical_profile` and `collagen_profile`.
  - Disclosure and count components are removed from `sports_formulation`, `fiber_digestive_formulation`, `b_complex`, `multi_prenatal_formulation`, `probiotic_formulation`, `probiotic_dose` and `fiber_digestive_dose`.
  - `sports_dose` loses its opaque penalty, single-only and stack components.
  - `probiotic_evidence` gates certainty on applicability; `probiotic_dose` applies the floor as a minimum.
  - `generic_transparency` no longer withholds the bonus for a blend alone.
- **Shared updates:** `penalty_registry` (`COMPONENT_KINDS` and the two dead keys), the copy, every affected test, the canary manifest changelog, and the delivery claim-subject fix (F12).
- **Validation:** `/pg-scoring-change`, a fail-first test per class, a raw-label replay by cause with controls, an independent review, then CI and the `local` rung.
