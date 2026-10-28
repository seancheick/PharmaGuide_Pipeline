"""Phase 8 — primary-ingredient evidence floor (generic module).

The top-N additive evidence pipeline rewards ingredient COUNT: a focused single
clinically-validated ingredient (KSM-66) scored ~4.5/20 while two generic minerals
scored ~11.5/20. The floor lifts the dimension when the product's PROMINENT
active (the shared role owner's purpose, still holding half the heaviest active's
mass as the retained exposure stand-in) is strongly & positively evidenced at a
clinical dose — never a well-studied trace co-ingredient. Generic, sports and
fiber opt in; omega/probiotic/multi reuse this scorer and do not.
"""
from __future__ import annotations

from scoring_v4.modules.generic_evidence import (  # noqa: E402
    score_evidence, PRIMARY_FLOOR_STRONG, PRIMARY_FLOOR_MODERATE,
    PRIMARY_FLOOR_REPLICATED_STRONG, EFFECT_DIRECTION_MULTIPLIERS,
)


def _match(*, ingredient="Ashwagandha", standard_name=None, study_type="rct_multiple",
           effect_direction="positive_strong", evidence_level="ingredient-human",
           total_enrollment=500, **extra):
    # Explicit arithmetic fixture IDs cannot inherit a live ingredient hold.
    # Real held-source behavior is covered by the owner/consumer regressions.
    row = {"id": f"TEST_ELIGIBLE_{ingredient.upper()}", "ingredient": ingredient,
           "standard_name": standard_name or ingredient, "study_type": study_type,
           "evidence_level": evidence_level, "effect_direction": effect_direction,
           "total_enrollment": total_enrollment}
    row.update(extra)
    return row


def _ing(name="Ashwagandha", canonical_id="ashwagandha", quantity=600, unit="mg"):
    return {"name": name, "standard_name": name, "canonical_id": canonical_id,
            "mapped": True, "bio_score": 11, "quantity": quantity, "unit": unit}


def _product(ingredients, matches):
    return {"status": "active", "form_factor": "capsule",
            "supplement_type": {"type": "single_nutrient"},
            "ingredient_quality_data": {"ingredients_scorable": ingredients, "ingredients": ingredients},
            "evidence_data": {"clinical_matches": matches}}


def test_mass_primary_strong_floors_to_14():
    p = _product([_ing()], [_match(study_type="rct_multiple")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["score"] >= PRIMARY_FLOOR_STRONG == 14.0
    assert out["metadata"]["primary_evidence_floor"] == 14.0
    assert out["metadata"]["primary_evidence_floor_canonical"] == "ashwagandha"


def test_floor_not_applied_without_opt_in():
    # omega/probiotic/multi reuse this scorer WITHOUT the floor flag (default).
    p = _product([_ing()], [_match(study_type="rct_multiple")])
    out = score_evidence(p)  # apply_primary_floor defaults False
    assert out["metadata"]["primary_evidence_floor"] == 0.0
    assert out["score"] < 14.0


def test_trace_strong_ingredient_does_not_floor():
    # selenium (trace, 0.05 mg) has a strong match; magnesium (primary, 1000 mg)
    # does not. The trace ingredient must NOT anchor the CLINICAL floor (14).
    # P5: magnesium (mass-dominant essential) earns the nutrition-authority floor
    # (10); the selenium trace match still does not push it to the clinical tier.
    ings = [_ing("Magnesium", "magnesium", 1000, "mg"),
            _ing("Selenium", "selenium", 50, "mcg")]
    matches = [_match(ingredient="Selenium", standard_name="Selenium", study_type="rct_multiple")]
    out = score_evidence(_product(ings, matches), apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 10.0
    assert out["metadata"]["nutrition_authority_canonical"] == "magnesium"


def test_weak_effect_floors_below_strong_effect():
    """A weak-effect meta must floor below a positive_strong one.

    Pre-lock that was 14 * 0.85 = 11.9; direction_ceiling now caps a non-strong
    direction at the MODERATE base weighted by its multiplier. The invariant the
    test exists for — weak sits below strong — is unchanged.
    """
    p = _product([_ing()], [_match(study_type="rct_multiple", effect_direction="positive_weak")])
    out = score_evidence(p, apply_primary_floor=True)

    ceiling = round(PRIMARY_FLOOR_MODERATE * EFFECT_DIRECTION_MULTIPLIERS["positive_weak"], 4)
    assert out["metadata"]["primary_evidence_floor"] == ceiling
    assert ceiling < PRIMARY_FLOOR_STRONG


def test_moderate_study_floors_to_11():
    p = _product([_ing()], [_match(study_type="rct_single")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == PRIMARY_FLOOR_MODERATE == 11.0
    assert out["score"] >= 11.0


def test_negative_effect_does_not_floor():
    p = _product([_ing()], [_match(study_type="rct_multiple", effect_direction="negative")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 0.0


def test_weak_study_type_does_not_floor():
    p = _product([_ing()], [_match(study_type="observational")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 0.0


# --- Replicated-body tier (Dr Pham framework, October 28, 2026) ------------
# The near-perfect floor once followed a brand marker or an ingredient allowlist.
# One or two small manufacturer-supplied trials could reach 20/20 that way. It now
# follows the reviewed evidence body: clinician-approved contexts of the record
# must show at least three consistent, independent RCT families for one
# condition, with no contradictory family. A brand or ingredient name earns nothing.

_REVIEW = {"reviewer": "Test clinician", "reviewed_at": "2026-10-01",
           "scope": "identity_dose_outcome_applicability"}


def _context(family, *, direction="positive", condition="perceived_stress",
             role="direct_rct", review_status="clinician_approved", scope="branded_material"):
    return {"context_id": family, "trial_family": family, "condition": condition,
            "evidence_role": role, "review_status": review_status, "identity_scope": scope,
            "scoring_eligible": True, "clinical_review": dict(_REVIEW),
            "outcomes": [{"name": "Perceived stress", "direction": direction,
                          "hierarchy": "primary", "kind": "patient_important"}]}


def _replicated(*families, **kwargs):
    return [_context(family, **kwargs) for family in families or ("a", "b", "c")]


def _registered(monkeypatch, *matches, claims=None):
    """Register SYNTHETIC records: replication is read from the registry, never
    the match. Each record states a synthetic supported outcome (mood category);
    ``claims`` sets the label's declared purposes per ingredient."""
    import clinical_applicability
    import evidence_resolver
    registry = {**clinical_applicability.reviewed_entries(),
                **{m["id"]: {"primary_outcome": "Reduce Stress/Anxiety", **m} for m in matches}}
    monkeypatch.setattr(clinical_applicability, "reviewed_entries", lambda: registry)
    if claims is not None:
        monkeypatch.setattr(evidence_resolver, "_evidence_claim_purposes", lambda product, module=None: claims)
    return list(matches)


def test_branded_record_without_replicated_body_is_strong_not_exceptional():
    """BRAND_ASTAREAL/KSM-66 shape: a branded multi-RCT record with no approved
    replicated body floors at the ordinary strong base, 14 (15.6/20), not 18 (20/20)."""
    p = _product([_ing()], [_match(study_type="rct_multiple", evidence_level="branded-rct")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == PRIMARY_FLOOR_STRONG == 14.0


def test_single_branded_rct_is_moderate():
    """One branded trial is a moderate floor (11 = 12.2/20), never 17 (18.9/20)."""
    p = _product([_ing()], [_match(study_type="rct_single", evidence_level="branded-rct")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == PRIMARY_FLOOR_MODERATE == 11.0


def test_brand_id_prefix_no_longer_elevates():
    p = _product(
        [_ing("BioCell Collagen", "collagen", 1000, "mg")],
        [_match(id="BRAND_BIOCELL", ingredient="BioCell", standard_name="BioCell Collagen",
                study_type="rct_multiple", evidence_level="product-human")],
    )
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 14.0


def test_replicated_body_reaches_exceptional_floor(monkeypatch):
    p = _product([_ing()], _registered(monkeypatch, _match(study_type="rct_multiple",
                                                         study_contexts=_replicated())))
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == PRIMARY_FLOOR_REPLICATED_STRONG == 18.0


def test_replication_needs_three_families_for_one_condition(monkeypatch):
    two = _replicated("a", "b")
    split = [_context("a"), _context("b"), _context("c", condition="sleep")]
    for contexts in (two, split):
        p = _product([_ing()], _registered(monkeypatch, _match(study_type="rct_multiple",
                                                             study_contexts=contexts)))
        assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 14.0


def test_contradictory_family_blocks_exceptional_floor(monkeypatch):
    contexts = _replicated() + [_context("d", direction="null")]
    p = _product([_ing()], _registered(monkeypatch, _match(study_type="rct_multiple",
                                                         study_contexts=contexts)))
    assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 14.0


def test_indirect_pooled_or_unapproved_contexts_are_not_replication(monkeypatch):
    """A meta-analysis is not linked to its independent trials, a context still
    pending clinical review authorizes nothing (context_accepted_for_scoring),
    and a combination formula's result is not this ingredient's (directness)."""
    pooled = _replicated("a", "b", "c", role="meta_analysis")
    pending = _replicated(review_status="source_verified_pending_clinical_review")
    combination = _replicated(scope="combination")
    unscoped = _replicated(scope=None)
    for contexts in (pooled, pending, combination, unscoped):
        p = _product([_ing()], _registered(monkeypatch, _match(study_type="systematic_review_meta",
                                                             study_contexts=contexts)))
        assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 14.0


def test_replication_must_match_the_declared_purpose(monkeypatch):
    """Per-context purpose: replicated stress trials support a mood purpose, not
    a cognitive claim the same record also covers (supported outcomes mood and
    cognition). Without a declared claim the record's reviewed outcomes decide."""
    record = dict(study_type="rct_multiple", study_contexts=_replicated(),
                  primary_outcome="Stress and memory", key_endpoints=["cognition"])
    for claims, floor in (({"ashwagandha": {"mood"}}, 18.0),
                          ({"ashwagandha": {"cognitive_neurological"}}, 14.0),
                          ({}, 18.0)):
        p = _product([_ing()], _registered(monkeypatch, _match(**record), claims=claims))
        assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == floor, claims


def test_filtered_contradictory_family_still_blocks(monkeypatch):
    """A null trial for the same condition blocks replication even when its own
    outcome falls outside the declared purpose or its scope is combination or
    unstated: the filters choose supporting trials, never hide contradictions."""
    def null_family(**overrides):
        context = _context("d", direction="null", condition="healthy_adults", **overrides)
        context["outcomes"][0]["name"] = "PSQI global score"
        return context
    positives = _replicated(condition="healthy_adults")
    for context in positives:
        context["outcomes"][0]["name"] = "Sleep quality"
    for contradiction in (null_family(), null_family(scope="combination"), null_family(scope=None)):
        p = _product([_ing()], _registered(monkeypatch, _match(study_type="rct_multiple",
                     study_contexts=positives + [contradiction]), claims={"ashwagandha": {"mood"}}))
        assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 14.0


def test_population_restricted_body_does_not_transfer(monkeypatch):
    """Replicated trials restricted to pregnancy apply only to a prenatal label
    (the shared native population restriction)."""
    contexts = _replicated()
    for context in contexts:
        context["population"] = {"age_group": "adult", "description": "Pregnant women in the third trimester"}
    general = _product([_ing()], _registered(monkeypatch, _match(study_type="rct_multiple", study_contexts=contexts)))
    assert score_evidence(general, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 14.0
    prenatal = {**general, "product_name": "Prenatal Ashwagandha"}
    assert score_evidence(prenatal, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 18.0


def test_label_function_claim_selects_the_replicated_purpose(monkeypatch):
    """End to end through the role owner: a printed "Ashwagandha supports
    memory" claim declares a cognitive purpose, which stress trials cannot
    replicate; a printed stress claim can."""
    record = dict(study_type="rct_multiple", study_contexts=_replicated(),
                  primary_outcome="Stress and memory", key_endpoints=["cognition"])
    for claim, floor in (("Ashwagandha supports memory and focus.", 14.0),
                         ("Ashwagandha supports stress management.", 18.0)):
        p = _product([_ing()], _registered(monkeypatch, _match(**record)))
        p["statements"] = [{"type": "Formula re: Contains", "notes": claim}]
        assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == floor, claim


def test_uncategorized_replicated_condition_is_held(monkeypatch):
    """The shared categorizer has no joint category yet, so knee trials cannot
    establish purpose-matched replication: held, never borrowed."""
    contexts = _replicated(condition="knee_osteoarthritis")
    for context in contexts:
        context["outcomes"][0]["name"] = "WOMAC"
    p = _product([_ing()], _registered(monkeypatch, _match(study_type="rct_multiple", study_contexts=contexts)))
    assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 14.0


def test_combination_contexts_count_only_for_the_assessed_exact_formula(monkeypatch):
    """A whole-formula trial is direct evidence for that exact formula (studied
    formula owner), never independent replication for one component."""
    from scoring_v4.modules.generic_evidence import _replicated_evidence_body
    record = _registered(monkeypatch, _match(study_contexts=_replicated(scope="combination")))[0]
    exact = {**record, "evidence_origin": "verified_formula_contract",
             "applicability_assessment": {"status": "assessed_studied_formula"}}
    product = _product([_ing()], [record])
    assert _replicated_evidence_body(exact, product, {"ashwagandha"}) is True
    assert _replicated_evidence_body(record, product, {"ashwagandha"}) is False


def test_real_registry_records_without_replicated_bodies_stay_below_exceptional():
    """Real controls, each blocked for its own recorded reason: Magtein (mixed
    and null trials plus a multi-active formula), creatine (one pooled
    meta-analysis), magnesium bisglycinate (two approved trials for different
    conditions) and OptiMSM/MSM (one shared trial family under two records)."""
    from clinical_applicability import reviewed_entries
    from scoring_v4.modules.generic_evidence import _replicated_evidence_body
    from collections import Counter
    from probiotic_measurements import context_accepted_for_scoring
    registry = reviewed_entries()

    def approved(record_id):
        return [c for c in registry[record_id].get("study_contexts") or [] if context_accepted_for_scoring(c)]

    def directions(context):
        return {o.get("direction") for o in context.get("outcomes") or [] if o.get("hierarchy") == "primary"}

    # The recorded reasons, checked on the live records.
    assert any(directions(c) & {"null", "mixed"} for c in approved("BRAND_MAGTEIN"))
    assert {c.get("evidence_role") for c in approved("INGR_CREATINE_MONOHYDRATE")} == {"meta_analysis"}
    assert max(Counter(c.get("condition") for c in approved("INGR_MAG_GLYCINATE")).values()) == 1
    assert ({c.get("trial_family") for c in approved("BRAND_OPTIMSM")}
            == {c.get("trial_family") for c in approved("INGR_MSM")})
    product = _product([_ing()], [])
    for record_id in ("BRAND_MAGTEIN", "INGR_CREATINE_MONOHYDRATE", "INGR_MAG_GLYCINATE",
                      "BRAND_OPTIMSM", "INGR_MSM"):
        assert _replicated_evidence_body(registry[record_id], product, set()) is False, record_id


def test_unregistered_match_cannot_supply_its_own_replication():
    """Contexts carried on a match that is not a registry record (or that differ
    from its record) never broaden reviewed scope."""
    p = _product([_ing()], [_match(study_type="rct_multiple", study_contexts=_replicated())])
    assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 14.0


def test_replicated_single_rct_record_stays_moderate(monkeypatch):
    p = _product([_ing()], _registered(monkeypatch, _match(study_type="rct_single",
                                                         study_contexts=_replicated())))
    assert score_evidence(p, apply_primary_floor=True)["metadata"]["primary_evidence_floor"] == 11.0


def test_weak_effect_cannot_ride_the_replicated_strong_base(monkeypatch):
    """direction_ceiling (locked 2026-09-18): only positive_strong anchors a strong
    base; weaker directions cap at the MODERATE base times their multiplier."""
    p = _product([_ing()], _registered(monkeypatch, _match(
        study_type="rct_multiple", effect_direction="positive_weak", study_contexts=_replicated())))
    out = score_evidence(p, apply_primary_floor=True)
    ceiling = round(PRIMARY_FLOOR_MODERATE * EFFECT_DIRECTION_MULTIPLIERS["positive_weak"], 4)
    assert out["metadata"]["primary_evidence_floor"] == ceiling


def test_retired_ingredient_allowlist_no_longer_elevates():
    """Psyllium, vitamin D, folate and creatine reach the exceptional floor only
    through a replicated reviewed body, like every other record."""
    p = _product([_ing("Psyllium", "psyllium", 5000, "mg")],
                 [_match(ingredient="Psyllium", standard_name="Psyllium",
                         canonical_id="psyllium", study_type="rct_multiple",
                         evidence_level="ingredient-human")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 14.0
    assert out["metadata"]["primary_evidence_floor_canonical"] == "psyllium"


def test_studied_amount_does_not_gate_evidence_floor(monkeypatch):
    p = _product([_ing(quantity=50)],
                 _registered(monkeypatch, _match(study_type="rct_multiple", min_clinical_dose=300.0,
                                                 study_contexts=_replicated())))
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 18.0


def test_branded_trace_ingredient_does_not_float_product():
    """A branded strong match on a TRACE co-ingredient (not mass-dominant) must
    not float the product to a clinical floor. P5: magnesium (the
    mass-dominant essential) earns the nutrition-authority floor 10 — the trace
    branded ashwagandha does NOT lift it to 18."""
    ings = [_ing("Magnesium", "magnesium", 1000, "mg"),
            _ing("Sensoril Ashwagandha", "ashwagandha", 50, "mg")]
    matches = [_match(ingredient="Sensoril Ashwagandha", standard_name="Sensoril Ashwagandha",
                      study_type="rct_multiple", evidence_level="branded-rct")]
    out = score_evidence(_product(ings, matches), apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 10.0
    assert out["metadata"]["nutrition_authority_canonical"] == "magnesium"


# --- P5 nutrition-authority floor (DRI-essential nutrients) 2026-06 ----------

def test_essential_nutrient_authority_floor_lifts_copper():
    """P5: copper (essential DRI mineral) with no strong RCT match still has
    evidence of necessity -> nutrition-authority floor 10 (below the 14 clinical
    tier). Was evidence 0 -> POOR."""
    p = _product([_ing("Copper", "copper", 2, "mg")], [])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["score"] >= 10.0
    assert out["metadata"]["nutrition_authority_floor_applied"] is True
    assert out["metadata"]["nutrition_authority_canonical"] == "copper"


def test_non_essential_gets_no_authority_floor():
    """Guard: boron (UL only, no RDA) is NOT DRI-essential -> no authority floor,
    stays evidence-light."""
    p = _product([_ing("Boron", "boron", 3, "mg")], [])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["nutrition_authority_floor_applied"] is False
    assert out["score"] < 10.0


def test_authority_floor_never_lowers_stronger_floor():
    """Authority is a floor, never a cap: an essential nutrient with a strong
    clinical record keeps that higher floor (vitamin D strong = 14 > authority 10)."""
    p = _product([_ing("Vitamin D", "vitamin_d", 25, "mcg")],
                 [_match(ingredient="Vitamin D", standard_name="Vitamin D",
                         canonical_id="vitamin_d", study_type="rct_multiple",
                         evidence_level="ingredient-human")])
    out = score_evidence(p, apply_primary_floor=True)
    assert out["metadata"]["primary_evidence_floor"] == 14.0


def test_authority_floor_is_generic_opt_in_only():
    """omega/probiotic/multi reuse this scorer without the floor flag -> no
    authority floor (they have their own evidence logic)."""
    p = _product([_ing("Copper", "copper", 2, "mg")], [])
    out = score_evidence(p)  # default apply_primary_floor=False
    assert out["metadata"]["nutrition_authority_floor_applied"] is False
    assert out["score"] < 10.0


# --- Public bands (Dr Pham, October 28, 2026; editorial ranges, not GRADE) ---

def test_each_floor_lands_in_its_public_band():
    """On the 18-point generic reference, each automatic floor's public /20 value
    sits inside its band: exceptional 19-20, strong 15-18, moderate 11-14,
    essential-nutrient nutrition 10-12 (between limited and moderate) and
    limited 6-10 for weak or mixed directions."""
    from scoring_v4.quality_score import _pillar_evidence
    from scoring_v4.quality_score_config import config
    from scoring_v4.modules.generic_evidence import NUTRITION_AUTHORITY_FLOOR

    def public(raw):
        return _pillar_evidence({"score": raw, "metadata": {"evidence_result_state": "evaluated_applicable"}},
                                20.0, "generic_single_molecule", config())["score"]

    assert 19 <= public(PRIMARY_FLOOR_REPLICATED_STRONG) <= 20
    assert 15 <= public(PRIMARY_FLOOR_STRONG) <= 18
    assert 11 <= public(PRIMARY_FLOOR_MODERATE) <= 14
    assert 10 <= public(NUTRITION_AUTHORITY_FLOOR) <= 12
    for direction in ("positive_weak", "mixed"):
        assert 6 <= public(PRIMARY_FLOOR_MODERATE * EFFECT_DIRECTION_MULTIPLIERS[direction]) <= 11
