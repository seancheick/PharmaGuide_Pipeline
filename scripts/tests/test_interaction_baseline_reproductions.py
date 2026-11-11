"""Interaction audit, Stage 1: reproductions of verified source-data findings.

Each test states the intended behaviour and fails on today's data. They are
marked ``xfail(strict=True)``: this stage does not change behaviour, and when
the Stage 2/3 fix lands the test passes unexpectedly, which fails the run until
the marker is removed. Plan: interaction audit 2026-11-11 (Stage 1).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"

# The app's only class crosswalk today
# (PharmaGuide ai lib/services/medications/medication_class_bridge.dart
# `_profileGateClassOverrides`); every other `class:x` id reaches rule id `x`.
APP_PROFILE_GATE_OVERRIDES = {"class:antiplatelet_agents": "antiplatelets"}

DIGOXIN = "3407"
CLOBAZAM = "21241"
VALPROIC_ACID = "11118"
VENLAFAXINE = "39786"
DULOXETINE = "72625"


def _load(name: str):
    return json.loads((DATA / name).read_text())


def _classes() -> dict:
    return _load("drug_classes.json")["classes"]


def _rules() -> list:
    return _load("ingredient_interaction_rules.json")["interaction_rules"]


def _profile_ids(class_id: str) -> str:
    return APP_PROFILE_GATE_OVERRIDES.get(class_id, class_id.removeprefix("class:"))


def _profile_ids_for_rxcui(rxcui: str) -> set[str]:
    return {
        _profile_ids(cid)
        for cid, c in _classes().items()
        if rxcui in c.get("member_rxcuis", [])
    }


def _rule(rule_id: str) -> dict:
    return next(r for r in _rules() if r["id"] == rule_id)


def _gate_ids(sub_rule: dict) -> set[str]:
    """Ids the app matches: the authored drug_classes_any plus the rule class."""
    requires = (sub_rule.get("profile_gate") or {}).get("requires") or {}
    return {sub_rule["drug_class_id"], *(requires.get("drug_classes_any") or [])}


def _unreachable() -> list[tuple[str, str]]:
    reachable = {_profile_ids(cid) for cid in _classes()}
    return sorted(
        (r["id"], d["drug_class_id"])
        for r in _rules()
        for d in r.get("drug_class_rules") or []
        if not _gate_ids(d) & reachable
    )


@pytest.mark.xfail(
    strict=True,
    reason="79 drug-class sub-rules gate on ids no medication class reaches (Stage 2 crosswalk)",
)
def test_every_rule_drug_class_is_reachable_from_a_medication_class():
    unreachable = _unreachable()
    assert unreachable == [], f"{len(unreachable)} unreachable: {unreachable}"


def test_unreachable_rule_count_is_the_audited_baseline():
    """Pins the audited size so a silent change in either file is noticed."""
    assert len(_unreachable()) == 79


@pytest.mark.xfail(
    strict=True,
    reason="digoxin is in no medication class; senna/cascara/aloe ferox/ginseng rules never fire",
)
def test_digoxin_reaches_the_cardiac_glycoside_rules():
    targets = {
        r["id"]
        for r in _rules()
        for d in r.get("drug_class_rules") or []
        if d["drug_class_id"] == "cardiac_glycosides"
    }
    assert targets == {
        "RULE_IQM_SENNA_PREGNANCY",
        "RULE_IQM_CASCARA_SAGRADA_PREGNANCY",
        "RULE_IQM_ALOE_FEROX",
        "RULE_INGREDIENT_GINSENG",
    }
    assert "cardiac_glycosides" in _profile_ids_for_rxcui(DIGOXIN)
    # Live RxNav (2026-11-11) gives digoxin ATC "Digitalis glycosides", so the
    # app's runtime slug is digitalis_glycosides, which matches no rule either.


@pytest.mark.xfail(
    strict=True,
    reason="clobazam sits only in benzodiazepines and valproate in its own class; the CBD rule targets anticonvulsants",
)
@pytest.mark.parametrize("rxcui", [CLOBAZAM, VALPROIC_ACID], ids=["clobazam", "valproic_acid"])
def test_cbd_antiseizure_rule_reaches_clobazam_and_valproate(rxcui):
    cbd_ids = set().union(
        *(_gate_ids(d) for d in _rule("RULE_BANNED_CBD_INTERACTIONS")["drug_class_rules"])
    )
    assert _profile_ids_for_rxcui(rxcui) & cbd_ids


@pytest.mark.xfail(
    strict=True,
    reason="SNRIs are in no medication class; the St. John's wort serotonergic rule never reaches them",
)
@pytest.mark.parametrize("rxcui", [VENLAFAXINE, DULOXETINE], ids=["venlafaxine", "duloxetine"])
def test_st_johns_wort_antidepressant_rule_reaches_snris(rxcui):
    sub_rule = next(
        d
        for d in _rule("RULE_INGREDIENT_ST_JOHNS_WORT")["drug_class_rules"]
        if d["drug_class_id"] == "antidepressants_ssri_snri"
    )
    assert _profile_ids_for_rxcui(rxcui) & _gate_ids(sub_rule)


HELD_INTERVALS = [
    # (timing rule held for an unsupported interval, curated pair publishing it)
    ("timing_iron_calcium_separate", "SSI_IRON_CALCIUM"),
    ("timing_thyroid_med_magnesium_separate", "DSI_LEVOTHYROXINE_MAGNESIUM"),
]


def _curated(pair_id: str) -> dict:
    for path in sorted((DATA / "curated_interactions").glob("*.json")):
        doc = json.loads(path.read_text())
        items = doc.get("interactions") if isinstance(doc, dict) else doc
        for item in items or []:
            if item.get("id") == pair_id:
                return item
    raise AssertionError(f"{pair_id} not found")


def _hours(text: str) -> set[str]:
    return set(re.findall(r"(\d+)\s*hours?", text or ""))


@pytest.mark.xfail(
    strict=True,
    reason="a held timing interval still ships in curated pair management text (Stage 3 gate)",
)
@pytest.mark.parametrize("timing_id,pair_id", HELD_INTERVALS, ids=[p for _, p in HELD_INTERVALS])
def test_held_timing_interval_is_not_published_elsewhere(timing_id, pair_id):
    timing = next(
        r for r in _load("timing_rules.json")["timing_rules"] if r["id"] == timing_id
    )
    assert timing["review_status"] != "verified"
    assert "interval_not_supported_by_cited_source" in json.dumps(timing.get("review_blockers"))
    held = _hours(timing["advice"])
    assert held, "the held rule states an interval"
    assert not (held & _hours(_curated(pair_id).get("management"))), (
        f"{pair_id} management publishes the held {sorted(held)} h interval"
    )
