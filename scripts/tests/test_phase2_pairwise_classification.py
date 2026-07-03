#!/usr/bin/env python3
"""Phase 2 (smart-flagging rework) — lock the direction/materiality classification
on the pairwise curated_interactions files (curated_interactions_v1,
med_med_pairs_v1, batch_critical_2026_05).

Load-bearing invariant: `applies_to` is a SCOPE descriptor, not our suppressible
materiality. Warfarin + Vitamin K carries applies_to="dose_dependent" yet must be
harmful + presence (never dose-suppressed). These tests guard that a later edit
can't turn a serious interaction into a suppressible one.

Hermetic: reads the shipped JSON, no DB build, no network.
"""
import json
from pathlib import Path

BASE = Path(__file__).parent.parent / "data" / "curated_interactions"
FILES = ["curated_interactions_v1.json", "med_med_pairs_v1.json", "batch_critical_2026_05.json"]

DIRECTIONS = {"harmful", "beneficial", "neutral", "unknown"}
MATERIALITIES = {"presence", "dose_dependent"}
SUPP_TYPES = {"Med-Sup", "Sup-Sup", "Sup-Med"}


def _all_pairs():
    out = []
    for f in FILES:
        for e in json.loads((BASE / f).read_text())["interactions"]:
            out.append(e)
    return out


PAIRS = _all_pairs()
BY_ID = {e["id"]: e for e in PAIRS}


def test_every_pair_classified_with_valid_enums():
    assert len(PAIRS) == 149, f"expected 149 pairs, found {len(PAIRS)}"
    bad = []
    for e in PAIRS:
        d, m = e.get("direction"), e.get("materiality")
        if d not in DIRECTIONS or m not in MATERIALITIES:
            bad.append(f"{e['id']} direction={d!r} materiality={m!r}")
    assert not bad, f"invalid/missing classification: {bad[:10]}"


def test_major_and_contraindicated_never_dose_suppressed():
    """The never-suppress core: no serious interaction may be dose_dependent,
    regardless of its `applies_to` scope descriptor."""
    for e in PAIRS:
        if e.get("severity") in ("Major", "Contraindicated"):
            assert e.get("materiality") == "presence", \
                f"{e['id']} ({e.get('severity')}) must be presence, got {e.get('materiality')}"


def test_warfarin_vitamin_k_is_presence_despite_applies_to():
    """The canonical trap: applies_to='dose_dependent' but this is a Major
    never-suppress interaction."""
    e = BY_ID["DSI_WAR_VITK"]
    assert e.get("applies_to") == "dose_dependent"   # the scope descriptor
    assert e.get("direction") == "harmful"
    assert e.get("materiality") == "presence"         # our authored axis wins


def test_fishoil_vitamin_e_is_dose_dependent():
    """The named Phase-3 target: fish oil + high-dose vitamin E is a floorable
    additive-bleeding pair (the actual floor value is Phase-3 work)."""
    e = BY_ID["DSI_FISHOIL_VITE"]
    assert e.get("direction") == "harmful"
    assert e.get("materiality") == "dose_dependent"


def test_dose_dependent_only_on_supplement_additive_pairs():
    """A dose can only be floored where a supplement with a measurable dose
    exists and the effect is pharmacodynamically additive."""
    for e in PAIRS:
        if e.get("materiality") == "dose_dependent":
            assert e.get("type") in SUPP_TYPES, f"{e['id']} dose_dependent but type={e.get('type')}"
            assert e.get("interaction_effect_type") == "Additive", \
                f"{e['id']} dose_dependent but effect={e.get('interaction_effect_type')}"
            assert e.get("severity") in ("Moderate", "Minor"), \
                f"{e['id']} dose_dependent but severity={e.get('severity')}"


def test_narrow_ti_and_electrolyte_hazards_are_presence():
    """Adversarial-review carve-outs: Moderate/Additive pairs that are narrow-
    therapeutic-index (warfarin INR) or electrolyte/arrhythmia hazards must be
    presence (never dose-suppressed), not the default dose_dependent."""
    for rid in ("DSI_WAR_VITE", "DSI_CORTICO_LICORICE", "DSI_DIURETICS_POTASSIUM"):
        assert BY_ID[rid].get("materiality") == "presence", \
            f"{rid} must be presence (never dose-suppressed), got {BY_ID[rid].get('materiality')}"


def test_immunosuppressant_probiotics_is_harmful_not_neutral():
    """Tagged interaction_effect_type='Neutral' but the mechanism is sepsis risk
    in the immunocompromised — must be harmful, never demoted to neutral."""
    assert BY_ID["DSI_IMMUNOSUP_PROBIOTICS"].get("direction") == "harmful"


def test_neutral_direction_only_on_neutral_effect_rows():
    """Every neutral-direction row is a compatible/standard-co-therapy pair
    (effect_type='Neutral'); nothing else sneaks a benign label onto a risk."""
    for e in PAIRS:
        if e.get("direction") == "neutral":
            assert e.get("interaction_effect_type") == "Neutral", \
                f"{e['id']} neutral direction but effect={e.get('interaction_effect_type')}"


def test_coq10_statin_is_neutral():
    """CoQ10 offsets statin myopathy with no adverse PK interaction — the
    pairwise mirror of the ingredient-rule (coq10, statins) neutral tag."""
    assert BY_ID["DSI_STATINS_COQ10"].get("direction") == "neutral"
    assert BY_ID["DSI_STATINS_COQ10"].get("materiality") == "presence"
