# Calibration decision packet (2026-09-28)

Decisions for Sean that follow the correctness batch (MEASUREMENT.md). Nothing here is applied;
`quality_score.json` is unchanged. Each item gives today's behavior, the conflict, the measured arm
and a recommendation.

Arms ran read-only over 365 frozen raw labels (the 143 sample plus 222 targeted) at the batch tip
`212e5a1b`, by in-memory patches: `~/pg_quality/rr_fix/arms.py`; report
`python3 ~/pg_quality/rr_fix/arms_report.py ~/pg_quality/rr_fix/arms.jsonl`. 344 are scored.
Tiers counted at 95/90/80/70/55.

## Already decided (recovered, no question)

- **B12 form scores (RR-02):** decided. IQM `_metadata` 5.6.1 `parent_relative_b12_recalibration`
  (2026-09-25): the six disclosed forms tie at 15 and unspecified is 14, based on Dr Pham's C2
  finding of no established absorption advantage (pinned in `test_b35_dr_pham_signoff_integrity`).
  RECONCILIATION C9 was stale and now says so. Vitamin C, calcium, folate and thiamine proposals
  still wait for team approval.

## 1. Form reference: runtime parent maximum or authored scale (RR-01, RECONCILIATION C1)

- **Today:** every form score is divided by the best eligible named form of its IQM parent at
  runtime (`scoring_reference_resolver.parent_relative_form_quality`, from dd2cf1ff, dda033c7,
  afb71c6c, 6a3ab83f; accepted by the 2026-09-25 archetype and contract-snapshot re-locks). IQM
  5.6.1 defines `bio_score` as a within-parent 0–15 scale, authored so far only for B12 and BCAA.
- **Conflict:** C1 says the reference must never be a dynamic maximum. With a runtime maximum,
  adding a better form to a parent silently lowers every product of that parent.
- **Arm A1 (raw `bio_score`, no runtime scaling):** 133 of 344 move, mean −0.82, 0 status changes,
  17 tier crossings, 2 verdict changes (275464 Fitbiotic 56.3 → 54.3 and 269317 BCAA 1000 mg
  56.5 → 54.2, both SAFE → POOR). Largest: PharmaGABA 336348 86.0 → 74.0, Beanaid 82372 −6.7,
  Riboflavin 5'-Phosphate 288632 −6.7, glucosamine sulfate 212455/252451 −5.4/−5.3, Spirulina 77257
  −4.7. By route: generic 55 (−2.64), multi 38 (−1.66), sports 26 (−2.13), omega 7, B-complex 5,
  fiber 2.
- **Recommendation:** keep the parent-relative meaning (it is what IQM 5.6.1 says and it stops a
  good form being judged against a theoretical maximum), but make the reference authored data, not
  a runtime maximum: per parent, author the 0–15 scale in IQM the way B12 and BCAA were, one topic
  batch at a time, and pin each parent's reference in a test so a new form cannot move old
  products. Until each parent is authored, ratify the runtime maximum as the interim rule and
  correct C1 to say so. Reverting to raw scores (A1) would drop single-form products such as
  PharmaGABA by 12 points for no label reason.

## 2. Adequacy basis: minimum or maximum directed use (RR-03)

- **Today:** `sports_dose` and `fiber_digestive_dose` declare
  `daily_interval_selection: maximum_directed_use`; generic Evidence, immune and joint also use the
  maximum (`generic_helpers.daily_serving_multiplier`); `botanical_profile` uses the minimum; omega
  scores min, mid and max bands. GLOSSARY "Adequacy exposure" says `per_day_min`.
- **Arm B (sports and fiber at the minimum):** 2 of 344 move: HMB 312819 74.5 → 65.2 and Guar Gum
  252542 63.8 → 59.0; 1 tier crossing, no verdict change.
- **Recommendation:** one rule for every route: benefit at the minimum directed use, risk (UL,
  interactions) at the maximum. It is what every user following the label gets, and it matches the
  glossary. Before adopting, run the same arm for the generic, immune and joint paths, which were
  not measured here.

## 3. Evidence for identities nobody has reviewed yet (RR-05)

- **Today:** 8 scored products get Evidence 0 while the pillar says `not_yet_reviewed`:
  Ravage Fruit Punch 1179 (40.6), Rampant 14168 (46.2), Healthy Hormone Formula 315089 (38.9),
  Golden Milk 243271 (39.1), Raw Organic Perfect Food 282638 (43.5), Raw Organic Fiber 299755
  (57.4), Sytrinol 54775 (42.8), Fitbiotic 275464 (56.3).
- **Arm C:** half credit (+10) gives 48.9–67.4 and moves one product across 55 (Rampant 14168
  46.2 → 56.2, POOR → SAFE); excluding the pillar and rescaling to 100 gives 48.6–71.8 with the same
  single crossing (14168 → 57.8). Five of the six POOR products stay POOR either way.
- **Recommendation:** keep 0 and the honest label; close the gap with evidence curation for the
  identities behind these 8 (a data batch, not a formula). A neutral grant would reward a missing
  review, which Codex also ruled out.

## 4. Omega Evidence floor (376 mg EPA+DHA/day)

- **Arm D (250 mg):** 1 of 344 moves: 29341 Dual Spectrum Lutein with Zeaxanthin 46.0 → 56.4,
  POOR → SAFE.
- **Finding:** 29341 is lutein 20 mg, zeaxanthin 2 mg and fish oil 430 mg. It routes `omega`
  (`omega_evidence`, primary type `omega_3`), so the lutein earns no Evidence at all. The floor is
  not the problem; the route is.
- **Recommendation:** keep 376 (no source was offered for a lower floor). Add mixed
  carotenoid-plus-fish-oil routing to the D12 mixed-purpose ownership item.

## 5. Chloride (register D22)

- **Today:** two rules for one nutrient. An unsourced Chloride row is now an active row (RR-10) and
  enters the multivitamin `rda_ul_data` panel and form average; a sourced Chloride row (67309) never
  reaches `analyzed_ingredients`. `constants.EXCLUDED_NUTRITION_FACTS` lists chloride and sodium
  (not potassium).
- **Measured:** −0.2 to +0.1 on 3 multivitamins (69770, whose panel goes from 30 to 31 nutrients;
  63367; 9711).
- **Recommendation:** score chloride nowhere, like sodium: it stays an accounted label row
  (`excluded_nutrition_fact`) and the multivitamin panel honors the same exclusion. Replay the 369
  dosed Chloride labels after the change.

## 6. Sports Dose from off-list nutrients

- **Today:** Ravage 2219, a pre-workout whose "Creatine Module" discloses no creatine amount, still
  earns 19.1 Dose from calcium and niacin adequacy through the generic off-list proxy.
- **Recommendation:** sports Dose credits only sports actives; a product whose sports actives are
  all undisclosed gets the disclosure-based Dose, not vitamin adequacy. Needs its own arm before a
  decision (scope: sports route products with an undosed sports blend).

## 7. Safety lookup failure (RR-08 follow-ups)

- **Today (5207bb47):** a resolver failure with no BLOCKED/UNSAFE verdict makes the product
  `NOT_SCORED` (`safety_assessment_incomplete`) and `build_final_db.py` keeps `not_scored` rows out
  of the live catalog. BLOCKED and UNSAFE still ship with their reason.
- **Open points:**
  1. A CAUTION product whose resolver also failed is withheld, so its caution does not ship.
  2. If a resolver fails for every product (a missing data file), the whole non-hard catalog
     silently disappears; no release gate counts `safety_assessment_incomplete` today
     (`rg safety_assessment_incomplete scripts/preflight.py scripts/release_full.sh` finds nothing).
- **Recommendation:** the release preflight refuses any build with a
  `safety_assessment_incomplete` product (a resolver failure is a bug to fix before shipping, never
  a catalog to publish). With that gate, point 1 cannot reach users, so no new status is needed.

## 8. D12 scoring-policy items (unchanged by this batch)

Product-level penalties at equal public points in every rubric; sugar gram thresholds and basis;
B1 active-row charges absent from `inactive_penalty_details`; one B0 charge per rule across rows;
shared Dose/Formulation fiber-type classifier (moves 34 products); 9 never-emitted
FIBER_CANONICALS; mixed-purpose ownership (now with item 4's routing case). RR-07 fixed the fiber
*domain* (fiber vs herb) in the classification contract; the fiber-*type* classifier in D12 is a
separate question and was not touched. Each D12 item still needs its own arm; none is measured
here.

## Order after the decisions

1. Apply the approved choices in `quality_score.json` and their owning modules only.
2. One corpus pass from the clean stage, then `scripts/test.sh release`.
3. Delta review against the live catalog, app contract check, then publication approval.
