# Test triage — held-source closure batch (2026-10-28)

Scope: the 54 failures in `~/pg_quality/held_closure_20261028/tests3.log`, checked against the
current applied `scripts/data/backed_clinical_studies.json` (including the coordinator's two later
data changes: INGR_WHEY_PROTEIN made whey-only, INGR_OMEGA3 returned to held). Validation class:
tests-only. Production code and data were not edited. The table of every test and its class is in
the agent report. This file holds the class-B finding and data follow-ups.

## B1 — beta-alanine credit is rejected by an "energy" word that is not a beta-alanine claim (open)

- Tests: `test_clinical_applicability.py::test_raw_triphase_material_keeps_sports_identity_without_borrowing_monohydrate[Creatine Hydrochloride-False]`
  and `[Creatine Monohydrate-True]` (both fail at `assert "beta-alanine" in evidence["ingredient_points"]`).
  Left failing on purpose; the test is correct.
- Owner: `scripts/data/backed_clinical_studies.json::INGR_BETA_ALANINE.applicability.excluded_claim_terms`
  = `["energy", "focus", "pre-workout energy"]`, enforced by
  `scripts/clinical_applicability.py::_excluded_claim_matches`, which tests every product positioning
  text (`native_product_positioning_texts`), not the claim attached to the beta-alanine row.
- Probe (fixture `triphase_317610_raw.json`, Tri-Phase, 3.2 g beta-alanine per serving, 1 serving/day,
  with the label's own beta-alanine claim "increase a critical muscle fatigue-controlling factor"):
  - enrichment rejects `INGR_BETA_ALANINE` with `label_purpose_evidence_mismatch`;
  - the only "energy" match is the blend description "...uniquely designed blend to target the
    body's energy systems throughout your workout";
  - the Evidence pillar is `0.0` with `ingredient_points {}`. In a copy of the record with only
    `"energy"` removed from `excluded_claim_terms` (the dose floor of 2400 mg/day still applies), the result is
    `{'beta-alanine': 5.4}` and Evidence `15.6`.
- Why it is wrong: the ruling (fourth set) limits credit to repeated-use high-intensity protocols and
  says a *single small* pre-workout serving does not inherit it. The `minimum_daily_dose: 2400 mg`
  already encodes "small". A product delivering 3.2 g/day (inside the studied 2.4–6.4 g/day) is
  zeroed because the word "energy" appears anywhere on the label, here in a phrase about
  physiological energy systems. Nearly every pre-workout uses that word, so the term acts as a
  category ban the ruling did not make. The last row of the fifth ruling also says wellness words
  must not make an unrelated study *applicable*. It does not say such words should disqualify a
  study whose outcome, dose and population do match.
- Recommended minimal fix (data, closure lane): remove the bare `"energy"` term from
  `INGR_BETA_ALANINE.applicability.excluded_claim_terms`. Keep `"pre-workout energy"` and `"focus"`
  only if Dr. Pham wants explicit energy/focus marketing excluded. If the generic word should stay, the
  narrower code fix is to scope `_excluded_claim_matches` to the claims attributed to the matched
  row. That is a behavioral change and needs its own scoring-change measurement. In either case, re-run the two nodes
  above. Check also whether Dr. Pham means "repeated use" to be inferred from directions
  (servings/day plus container size). The current encoding cannot express it, and the dose floor is the
  only proxy.

## Resolved during triage (recorded for the ledger)

- Whey-only labels losing whey credit. With the first applied data
  (`required_form_terms: ["whey"]`), a product whose only declared protein source was
  "Whey Protein Isolate" was rejected `clinical_form_mismatch`. The form term was checked against the
  "Protein" macro row that the protein-source recovery binds to, so the real WheyBasics (294073) and
  100% Whey (42306) fixtures lost credit. The coordinator's data change (whey-only aliases, no
  `required_form_terms`) fixed this. Those tests now pass unchanged. Casein/soy/pea/milk protein
  no longer reaching INGR_WHEY_PROTEIN matches the whey-specific ruling. Those tests were updated
  (class A).
- Marine omega applicability tests pass again after INGR_OMEGA3 returned to held. The omega route
  (`evidence_resolver.resolve_omega_evidence_standard` via `INGR_OMEGA3.purpose_evidence`) passed
  its own tests throughout (`test_v4_omega_*`, `test_omega_epa_dha_amount_owner.py`: 92 passed).

## Data follow-ups (not test defects; for the closure lane)

1. `INGR_WHEY_PROTEIN.notes` still says "The reviewed sources include whey, casein, milk, soy, pea,
   and studied source blends", and `standard_name` is still "Protein Supplementation". This
   contradicts the whey-only aliases and applicability. The repo rule is that changing a structured
   value means fixing every free-text field that refers to it.
2. `INGR_CHONDROITIN_SULFATE.effect_direction_rationale` still reads "study_type=systematic_review_meta;
   evidence_level=ingredient-human". Both fields are now `reference`.
   `INGR_GLUCOSAMINE_SULFATE.effect_direction_rationale` still says the review is not completed. The
   third ruling also asks for identical rationale text in both records, and the two texts differ.
3. BRAND_THERACURMIN: the ruling says "Held. Name the exact remaining acceptance (memory 29246725)".
   The draft memory context was dropped from production (no pending contexts in data), and the
   held patch's `record_updates` are not applied. The remaining acceptance is now named only in the
   patch receipt. Production notes give only general "separate review dependencies".
4. INGR_DIGESTIVE_ENZYMES: the dropped draft context carried the unverified "Poolzyme Multi"
   identity, so dropping it is correct. The record now has no contexts, and its notes do not record
   the fifth-ruling remaining item (study-material identity and activities).
5. BRAND_RELORA keeps a 17-point primary Evidence floor under a "limited stress credit" ruling.
   Point bands are explicitly out of scope for this batch (calibration batch). Noted only.
