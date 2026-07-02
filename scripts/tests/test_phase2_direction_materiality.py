#!/usr/bin/env python3
"""Phase 2 (smart-flagging rework) — lock the direction/materiality classification
authored across every sub-rule of ingredient_interaction_rules.json.

Guards the two-axis warning model so a later edit can't:
  - leave a sub-rule unclassified (would read as legacy-untagged),
  - dose-suppress a benefit or a presence-matters risk (materiality drift),
  - silently flip a benefit-vs-warning call (e.g. milk-thistle/liver,
    folate/pregnancy, biotin diagnostic-interference).

Hermetic: reads the shipped data file, no network. Companion to
test_phase3_dose_floors.py (which locks the dose_dependent floored set).
"""
import json
from pathlib import Path

DOC = json.loads(
    (Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json").read_text()
)
RULES = DOC["interaction_rules"]

DIRECTIONS = {"harmful", "beneficial", "neutral", "unknown"}
MATERIALITIES = {"presence", "dose_dependent"}  # 'unknown' unused — every rule is authored


def _sub_rules(rule):
    """(kind, key, sub_rule) for every classifiable sub-rule of a rule."""
    out = []
    for x in (rule.get("condition_rules") or []):
        out.append(("condition", x.get("condition_id"), x))
    for x in (rule.get("drug_class_rules") or []):
        out.append(("drug", x.get("drug_class_id"), x))
    pl = rule.get("pregnancy_lactation")
    if isinstance(pl, dict):
        out.append(("preg_lact", "pregnancy_lactation", pl))
    return out


def _all():
    for r in RULES:
        canon = (r.get("subject_ref") or {}).get("canonical_id", "")
        for kind, key, x in _sub_rules(r):
            yield canon, kind, key, x


def _find_all(canon, key):
    """All sub-rule dicts for (canonical_id, sub-rule key). Some canonical_ids
    carry two rows under one key (e.g. fish_oil/pregnancy_lactation has both a
    'Continue omega-3' beneficial row and a 'Limited safety data' unknown row)."""
    return [x for c, _kind, k, x in _all() if c == canon and k == key]


def test_every_subrule_classified_with_valid_enums():
    """No sub-rule may be left untagged, and both axes must be in-vocabulary."""
    missing, bad = [], []
    for canon, _kind, key, x in _all():
        d, m = x.get("direction"), x.get("materiality")
        if not d or not m:
            missing.append(f"{canon}/{key}")
        else:
            if d not in DIRECTIONS:
                bad.append(f"{canon}/{key} direction={d!r}")
            if m not in MATERIALITIES:
                bad.append(f"{canon}/{key} materiality={m!r}")
    assert not missing, f"unclassified sub-rules: {missing[:10]} (+{len(missing)-10} more)" if len(missing) > 10 else f"unclassified: {missing}"
    assert not bad, f"out-of-vocabulary: {bad[:10]}"


def test_materiality_is_dose_dependent_iff_floored():
    """A floor (min_effective_dose) is the ONLY thing that makes a rule
    dose_dependent; everything else is presence (never dose-suppressed)."""
    for canon, _kind, key, x in _all():
        floored = bool(x.get("min_effective_dose"))
        mat = x.get("materiality")
        if floored:
            assert mat == "dose_dependent", f"{canon}/{key} floored but materiality={mat}"
        else:
            assert mat == "presence", f"{canon}/{key} no floor but materiality={mat}"


def test_presence_rules_carry_no_floor():
    """Inverse guard: a presence rule must never carry a floor (would be a
    dose-suppressible risk mislabeled as always-fire)."""
    for canon, _kind, key, x in _all():
        if x.get("materiality") == "presence":
            assert not x.get("min_effective_dose"), f"{canon}/{key} presence rule wrongly floored"


def test_never_suppress_buckets_are_presence():
    """Pregnancy/lactation/ttc and MAOI contraindications must be presence —
    they fire at any dose and can never be dose-suppressed."""
    for canon, kind, key, x in _all():
        if key in ("pregnancy", "lactation", "ttc", "pregnancy_lactation") or key == "maois":
            assert x.get("materiality") == "presence", f"{canon}/{key} must be presence, got {x.get('materiality')}"


def test_vitamin_k_warfarin_never_suppressed():
    """The canonical never-suppress interaction: vitamin K vs anticoagulants
    stays harmful + presence (intake consistency matters at any dose)."""
    hits = [x for c, _k, key, x in _all() if c == "vitamin_k" and key == "anticoagulants"]
    assert hits, "vitamin_k/anticoagulants rule missing"
    for x in hits:
        assert x.get("direction") == "harmful"
        assert x.get("materiality") == "presence"


def test_no_drug_class_rule_is_beneficial():
    """Drug<->supplement interactions are never a 'benefit' — the only neutral
    drug-class rule is coq10/statins (no adverse PK interaction)."""
    for canon, kind, key, x in _all():
        if kind == "drug":
            assert x.get("direction") != "beneficial", f"{canon}/{key} drug interaction tagged beneficial"


# (canonical_id, sub-rule key) -> expected direction. Representative locks of the
# benefit-vs-warning calls the rework exists to get right.
BENEFICIAL_LOCK = {
    ("milk_thistle", "liver_disease"),
    ("coq10", "heart_disease"),
    ("berberine_supplement", "high_cholesterol"),
    ("garlic", "high_cholesterol"),
    ("citrus_bergamot", "high_cholesterol"),
    ("fish_oil", "pregnancy_lactation"),         # the "Continue omega-3" row
    ("inositol", "pregnancy_lactation"),
    ("vitamin_b12_cobalamin", "ttc"),
    ("vitamin_b9_folate", "ttc"),
    ("coq10", "ttc"),
    ("vitamin_d", "ttc"),
}

NEUTRAL_LOCK = {
    ("vitamin_b7_biotin", "heart_disease"),      # troponin assay interference
    ("vitamin_b7_biotin", "thyroid_disorder"),   # TSH/T4 assay interference
    ("coq10", "statins"),                        # no adverse PK interaction
    ("calcium", "pregnancy_lactation"),          # generally-compatible standard nutrient
    ("selenium", "thyroid_disorder"),
}

HARMFUL_LOCK = {
    ("st_johns_wort", "maois"),                  # serotonin syndrome
    ("aloe_vera", "pregnancy"),                  # oral aloe unsafe
    ("vitamin_a", "pregnancy"),                  # teratogenic preformed retinol
    ("iodine", "pregnancy"),                     # excess disrupts fetal thyroid
    ("red_clover", "thyroid_disorder"),          # TPO inhibition
    ("potassium", "potassium_sparing_diuretics"),  # hyperkalemia
}


def test_beneficial_classifications_locked():
    for canon, key in BENEFICIAL_LOCK:
        rows = _find_all(canon, key)
        assert rows, f"missing rule {canon}/{key}"
        beneficial = [x for x in rows if x.get("direction") == "beneficial"]
        assert beneficial, f"{canon}/{key} has no beneficial row: {[x.get('direction') for x in rows]}"
        # a beneficial rule must never be dose-suppressible
        for x in beneficial:
            assert x.get("materiality") == "presence", f"{canon}/{key} beneficial but not presence"


def test_neutral_classifications_locked():
    for canon, key in NEUTRAL_LOCK:
        rows = _find_all(canon, key)
        assert rows, f"missing rule {canon}/{key}"
        assert any(x.get("direction") == "neutral" for x in rows), \
            f"{canon}/{key} has no neutral row: {[x.get('direction') for x in rows]}"


def test_harmful_classifications_locked():
    for canon, key in HARMFUL_LOCK:
        rows = _find_all(canon, key)
        assert rows, f"missing rule {canon}/{key}"
        assert any(x.get("direction") == "harmful" for x in rows), \
            f"{canon}/{key} has no harmful row: {[x.get('direction') for x in rows]}"


def test_biotin_never_harmful_and_diagnostic_contexts_neutral():
    """Biotin's only real interaction is lab-assay interference: it is neutral in
    the diagnostic contexts (heart/thyroid troponin+TSH assays) and NEVER harmful
    anywhere (a pregnancy 'limited data' row is legitimately unknown, not harmful)."""
    diagnostic_neutral = {"heart_disease", "thyroid_disorder"}
    for canon, _kind, key, x in _all():
        if canon != "vitamin_b7_biotin":
            continue
        assert x.get("direction") != "harmful", f"biotin/{key} must never be harmful"
        if key in diagnostic_neutral:
            assert x.get("direction") == "neutral", f"biotin/{key} should be neutral, got {x.get('direction')}"
