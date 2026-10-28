# Condition-scope rule: measurement (October 28, 2026)

- **Candidate:** `claude/brave-fermi-d56dfd`, rebased onto main (code at `b4af90025`).
- **Base:** `main` at `b1f44d3ee` (#273 and #277 merged). The result is identical, line for line, to the pass
  against `4bba11a51`; receipts are `base_main.jsonl` and `cand_main.jsonl`.
- **Earlier pass:** against `6256ce42e` / `37a52de5b`. It gave the same 47 movers with identical deltas after
  the rebase; the outcome-level commit `6a3b5cfeb` added one mover.
- **Receipts:** `~/pg_quality/condition_scope_20261028/`. These cover the frozen raw labels, `base2.jsonl`,
  `base_r.jsonl`, `cand_o.jsonl`, `movement_final.txt`, the `gated/` cohort and the fail-first logs.
- **Method:** `replay.py freeze-raw`, then `snapshot` (clean → enrich → score with each checkout's own code).

## Cohorts

- **Main, 460 labels.**
  - The evidence-calibration lane's 205: the original twenty, floor drivers, strata, contradictory-trial
    records, exact-preparation cases and module controls.
  - Up to two labels per record and stratum for every record with an approved condition scope and for ten
    probiotic strains: 110 explicit-claim, 97 claim-free and 48 population-targeted labels.
- **Gated, 40 labels.** Single-ingredient (two or fewer actives), non-multivitamin labels for the eight
  formerly gated records. Final snapshot `gated/cand_o.jsonl` at `6a3b5cfeb`.

## Result (main cohort)

- **48 of 460 moved: 23 up, 25 down.** Only the Evidence pillar changed.
- **Unchanged everywhere:** Formulation, Dose, Transparency, Verification, Safety/Hygiene, status, route
  and safety status.
- **By stratum:**

| Stratum | Up | Down | Unchanged |
|---|---|---|---|
| Calibration | 5 | 14 | 186 |
| Explicit claim | 8 | 7 | 95 |
| Claim-free | 6 | 4 | 87 |
| Population-targeted | 4 | 0 | 44 |

- **Multi/prenatal and B-complex labels never move.** Their Evidence comes from the nutrient-panel
  authority, not from clinical matches.

## Result (gated cohort, 40 labels)

20 of 40 moved: 18 up, 2 down. No pillar other than Evidence moved. Claim-free single-ingredient labels
now earn their scoped credit:

| Record | Labels that gained | Evidence |
|---|---|---|
| Cranberry | 4 of 6 | 0 or 11.1 → 15.6 |
| Ginger | 3 of 6 | 0 → 15.6, adult chemotherapy-nausea context only |
| Inositol | 4 of 6 | 0 → 7.3, very-low-certainty PCOS cycle evidence |
| Selenium | 3 of 6 | 11.1 → 15.6 |
| Riboflavin | 2 of 6 | 11.1 → 15.6 |

- **Unchanged labels:** these carry an unrelated or ambiguous claim or a signed exclusion. Examples are
  "Liver Focus" inositol and "Mood | Stress" rhodiola (which is also signed-excluded), "Turmeric Ginger"
  gummies, and vitamin C labels that stay on the nutrition-authority floor.
- **Quercetin Phytosome ×2, 10.4 → 7.3:** the label says "Respiratory support". The blood-pressure
  INGR_QUERCETIN meta-analysis no longer credits it; only the phytosome's seasonal-allergy RCT applies.

## Movement by cause (main cohort)

| Cause | Direction | Examples |
|---|---|---|
| No claim required: an approved native strain context reaches a claim-free or aligned probiotic | Up, 0 → 12–16 (or +1.5 / +3 where credit existed) | BB-12, LGG, 299v, IS-2, NCFM, GBI-30, LactoSpore; 16 labels |
| Infant/child-targeted probiotic reaches pediatric contexts | Up | "Kids Probiotic" 297603, "Grow + Thrive" 246008, LGG chewables 250912, inulin kids 273844; 4 labels |
| No claim required: formerly gated generic record reaches a claim-free multi-ingredient label | Up | Electrolytes 311724 (vitamin C, selenium), Super Green 267303 (vitamin C, ginger) |
| Precaution or mechanism text no longer read as a signed exclusion | Up | GNC CoQ-10 3520, 0 → 15.6 ("heart's energy producing system") |
| Unrelated product claim (signed scope elsewhere) | Down | Suntheanine "Mood support / relaxation" (focus scope) ×3; KSM-66 "Energy Xtra" (stress scope); Shoden stress research on "Rest & Renew … for refreshing sleep" 328650 (sleep is now its own outcome; melatonin is not an Evidence owner there); berberine "GI/Immune support" and "cardiovascular health" (glucose scope); ubiquinol "Mitochondrial Support" (heart-failure scope); potassium and magnesium blood-pressure research on cleanses and sleep labels |
| Pre-workout positioned for focus, energy or pumps | Down, 20 → 0 | LIT ×4: creatine, beta-alanine, citrulline and potassium research marked unrelated; see the limits below |
| Recognized claim no category places, resolved conservatively | Down | "Lovin' Libido" sexual-function claims (KSM-66), CarbCrave "carbohydrate intake and appetite" (Sensoril, Relora), NitroVasc "nitric oxide production", fucoPROTEIN "healthy metabolism" (whey) |
| Restored BRAND_UCII scope binds UC-II to its own row | Down | TriFlex 76848, 15.6 → 0. The base credited UC-II research through the leucine owner by loose name matching. UC-II is not an Evidence owner on this label, which is a pre-existing owner-policy question |

Full table: `movement_final.txt` in the receipts folder.

## Corrections the replay forced (each fixed fail-first)

- **Formulation leak.** Branded-form credit read *accepted* Evidence matches, so a purpose rejection cut
  Formulation (KSM-66 and Zynamite labels, raw 12 → 8.8 / 7.2). It now reads preparation-verified matches.
- **"Predominantly men"** was treated as a sex restriction. A women's creatine label lost credit.
- **Signed exclusions too narrow:** a three-word claim window let "help boost … cellular energy" escape
  CoQ10's energy exclusion, so heart-failure research credited the Re-Forge pre-workout.
- **Misread label text:**
  - "Contents are sold by weight" was read as a weight claim, costing plain creatine and bilberry their credit.
  - "lean muscle", bare "muscle", "cardiometabolic", "vascular" and "blood flow" claims were not recognized.
  - "gastrointestinal", "intestinal", "lactose" and "infection" outcomes were not recognized. As a result an
    aligned probiotic claim earned less than silence.
- **Exclusion sentences** ("Pregnant participants were excluded") were read as the studied population.

## Outcome-level purposes (Sean, October 28, PR #278)

Without a signed `supported_outcomes` scope (native strain contexts), a context's purposes come only
from qualifying outcomes:
- Qualifying means positive, with hierarchy primary or not_reported (not_reported is kept distinct and
  never relabelled as primary).
- A surrogate names only itself.
- These never name a purpose: null, mixed or unfavorable results, secondaries, post-hoc, within-group,
  companion and ranking-only outcomes.
- An unresolved outcome holds the claim (ambiguous).
- A context with no positive outcome lets its null findings say what it evaluated, so the finding is
  shown as an evaluated null and earns no credit.
- Sleep is its own family, apart from stress.
- Fail-first log: `fail_first_round5.log`.

## Limits and open decisions

1. **Probiotic positioning weight (decision for Sean).** `probiotic_evidence.alignment_weights` pays
   direct 1.0, broad 0.5 and none 0, so an aligned 299v label earns 16 and a claim-free one 13.
   - D3 says there is no bonus for claiming. D1 says preserve category formulas.
   - Left unchanged.
2. **Pre-workout false-negative risk.** Unattributed positioning such as "focus, power and pumps" places
   only *focus*. Ingredient research for muscle outcomes is then unrelated. This follows the rulings
   (unattributed and partly unclassified claims resolve conservatively). Recognizing "power" or
   "pumps" would be a new clinical-relationship decision.
3. **Record-level study strength.** `generic_evidence._entry_raw_points` scores a record's study_type and
   effect, not those of the qualifying context. A general ginger label qualifies only through the
   chemotherapy RCT but is scored with the record's meta-analysis strength. Only INGR_GINGER has two
   approved contexts with different designs today. Follow-up.
4. **Legacy path unchanged.** Records with a policy but no approved context (INGR_VITAMIN_D3, INGR_INULIN,
   INGR_OMEGA3) keep preparation-only credit. Readiness flags them. Field one-brain #278 owns the
   no-prose rule there.
5. **Role promotion reads the same categorizer.** More function claims now name an ingredient's purpose
   (for example "Glucosamine supports joint comfort"). No owner-driven score change appeared in either
   cohort.
6. **Probiotic credit eligibility (not purpose).** `_qualifying_outcomes` requires hierarchy "primary", so
   pooled not_reported outcomes do not yet earn probiotic credit under the October 28 outcome ruling.
   Named follow-up.
7. **Evidence owner selection.** UC-II on TriFlex 76848 and melatonin on Rest & Renew 328650 are not
   Evidence owners on those labels. This is pre-existing owner policy.
8. **Not run:** whole-corpus replay, raw canaries, release rung and app check. Merging waits for PR #273
   and Sean's go-ahead.
