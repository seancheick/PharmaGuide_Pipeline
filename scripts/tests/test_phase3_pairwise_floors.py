#!/usr/bin/env python3
"""Phase 3 — lock the structured dose_threshold floors on the pairwise
dose_dependent interactions (curated_interactions/).

Every dose_dependent pair must carry a well-formed, sourced floor; presence pairs
must carry none (a floor on a never-suppress pair would let the app hide it).
Hermetic: reads the shipped JSON, no network.
"""
import json
from pathlib import Path

BASE = Path(__file__).parent.parent / "data" / "curated_interactions"
FILES = ["curated_interactions_v1.json", "med_med_pairs_v1.json", "batch_critical_2026_05.json"]

PAIRS = [e for f in FILES for e in json.loads((BASE / f).read_text())["interactions"]]
BY_ID = {e["id"]: e for e in PAIRS}


def test_every_dose_dependent_pair_has_a_valid_floor():
    for e in PAIRS:
        if e.get("materiality") != "dose_dependent":
            continue
        dt = e.get("dose_threshold")
        assert isinstance(dt, dict), f"{e['id']} dose_dependent but no dose_threshold"
        assert dt.get("agent_canonical_id"), f"{e['id']} floor missing agent_canonical_id"
        assert isinstance(dt.get("value"), (int, float)) and dt["value"] > 0, f"{e['id']} bad floor value"
        assert dt.get("unit"), f"{e['id']} floor missing unit"
        assert dt.get("basis") in ("per_day", "per_serving"), f"{e['id']} bad basis {dt.get('basis')}"
        assert dt.get("confidence") in ("high", "medium", "low"), f"{e['id']} bad confidence"
        assert dt.get("confidence_basis"), f"{e['id']} floor missing confidence_basis"
        src = dt.get("source", "")
        assert isinstance(src, str) and src.startswith(("http://", "https://")), \
            f"{e['id']} floor source not an http(s) URL: {src!r}"
        assert dt.get("rationale"), f"{e['id']} floor missing rationale"


def test_presence_pairs_carry_no_floor():
    """A never-suppress (presence) pair must not carry a dose_threshold — that
    would give the app a floor to suppress a risk that should always fire."""
    for e in PAIRS:
        if e.get("materiality") == "presence":
            assert not e.get("dose_threshold"), f"{e['id']} presence pair wrongly floored"


def test_exactly_33_floored():
    floored = [e["id"] for e in PAIRS if e.get("dose_threshold")]
    dose_dep = [e["id"] for e in PAIRS if e.get("materiality") == "dose_dependent"]
    assert len(floored) == 33, f"expected 33 floors, found {len(floored)}"
    assert set(floored) == set(dose_dep), "floored set != dose_dependent set"


# Representative floors locked (value+unit) so a later edit can't silently move them.
EXPECTED = {
    "DSI_FISHOIL_VITE": (400, "IU"),        # vitamin E bleeding, reused floor
    "DSI_DM_CHROMIUM": (200, "mcg"),        # chromium glucose, reused
    "DSI_METFORMIN_ALA": (600, "mg"),       # ALA glucose, reused
    "DSI_WAR_GARLIC": (600, "mg"),          # garlic bleeding, reused
    "DSI_SSRI_GINKGO": (120, "mg"),         # ginkgo bleeding, reused
    "DSI_STATINS_NIACIN": (1000, "mg"),     # pharmacologic niacin / statin myopathy
    "DSI_OC_SOY": (100, "mg"),              # soy isoflavones, pair-stated
    "DSI_BENZO_MELATONIN": (5, "mg"),       # melatonin sedation, pair-stated
}


def test_representative_floors_locked():
    for rid, (value, unit) in EXPECTED.items():
        assert rid in BY_ID, f"{rid} missing"
        dt = BY_ID[rid].get("dose_threshold") or {}
        assert (dt.get("value"), dt.get("unit")) == (value, unit), \
            f"{rid} floor {(dt.get('value'), dt.get('unit'))} != {(value, unit)}"
