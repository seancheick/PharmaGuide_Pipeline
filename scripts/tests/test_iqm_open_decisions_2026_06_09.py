"""Resolution of open IQM audit decisions surfaced after batch 6.

Decisions locked here:
- bio_score stays absorption/form-quality only; no clinical-utility exception
- black_cherry and sweet/dark-sweet cherry are separate species identities
- curcumin enhanced forms cannot outrank the signed curcumin ladder
- bovine-brain phosphatidylserine concern belongs in the safety lane
- choline is vitamin-like, not an amino acid
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


IQM_PATH = SCRIPTS / "data" / "ingredient_quality_map.json"
BANNED_PATH = SCRIPTS / "data" / "banned_recalled_ingredients.json"


def _iqm() -> dict:
    return json.loads(IQM_PATH.read_text())


def _banned_entries() -> list[dict]:
    data = json.loads(BANNED_PATH.read_text())
    return data["ingredients"]


def _form(iqm: dict, parent: str, form_name: str) -> dict:
    return iqm[parent]["forms"][form_name]


def _aliases(form: dict) -> set[str]:
    return {str(alias).lower().strip() for alias in form.get("aliases", [])}


def _assert_score_formula(form: dict) -> None:
    expected = min(18, form["bio_score"] + (3 if form.get("natural") else 0))
    assert form["score"] == expected


def test_coq10_crystal_free_has_no_clinical_utility_bio_score_exception() -> None:
    form = _form(_iqm(), "coq10", "ubiquinol crystal-free")
    assert form["bio_score"] == 13
    assert form["absorption_structured"]["value"] <= 0.10
    assert "no clinical-utility exception" in form["notes"].lower()
    _assert_score_formula(form)


def test_black_cherry_and_dark_sweet_cherry_are_separate_species_identities() -> None:
    iqm = _iqm()

    black = iqm["black_cherry"]
    black_form = _form(iqm, "black_cherry", "black cherry concentrate")
    assert black["cui"] == "C0330655"
    assert black["external_ids"]["unii"] == "A77056YJ4K"
    assert black["external_ids"]["cas"] == "84604-07-9"
    assert "prunus serotina" in black_form["notes"].lower()
    assert "prunus serotina" in _aliases(black_form)
    assert "prunus avium" not in _aliases(black_form)
    assert "sweet cherry extract" not in _aliases(black_form)

    sweet = iqm["dark_sweet_cherry"]
    sweet_form = _form(iqm, "dark_sweet_cherry", "dark sweet cherry powder")
    assert sweet["cui"] == "C0946748"
    assert sweet["rxcui"] == "901303"
    assert sweet["external_ids"]["unii"] == "93T4562ZI3"
    assert "prunus avium" in sweet_form["notes"].lower()
    assert {"sweet cherry powder", "prunus avium", "dark sweet cherry"} <= _aliases(sweet_form)
    _assert_score_formula(black_form)
    _assert_score_formula(sweet_form)


def test_curcumin_hydrocurc_and_bcm95_are_capped_to_signed_ladder() -> None:
    iqm = _iqm()
    hydrocurc = _form(iqm, "curcumin", "hydrocurc")
    bcm95 = _form(iqm, "curcumin", "bcm-95 curcumin")

    assert hydrocurc["bio_score"] == 9
    assert bcm95["bio_score"] == 8
    assert hydrocurc["bio_score"] <= _form(iqm, "curcumin", "novasol curcumin")["bio_score"]
    assert bcm95["bio_score"] <= hydrocurc["bio_score"]
    assert "signed curcumin ladder" in hydrocurc["notes"].lower()
    assert "signed curcumin ladder" in bcm95["notes"].lower()
    _assert_score_formula(hydrocurc)
    _assert_score_formula(bcm95)


def test_bovine_brain_phosphatidylserine_is_watchlist_safety_not_bio_penalty() -> None:
    iqm = _iqm()
    ps_form = _form(iqm, "phosphatidylserine", "bovine phosphatidylserine")
    assert ps_form["bio_score"] == 12
    assert "safety risk is not a bioavailability penalty" in ps_form["notes"].lower()

    entry = next(
        (item for item in _banned_entries() if item.get("id") == "WATCH_BOVINE_BRAIN_PHOSPHATIDYLSERINE"),
        None,
    )
    assert entry is not None
    assert entry["status"] == "watchlist"
    assert entry["match_mode"] == "active"
    assert "bovine brain phosphatidylserine" in {a.lower() for a in entry["aliases"]}

    from scoring_v4.gate_safety import evaluate_safety_gate

    result = evaluate_safety_gate({
        "activeIngredients": [
            {
                "name": "Bovine phosphatidylserine",
                "standardName": "Phosphatidylserine",
                "raw_source_text": "Bovine brain phosphatidylserine",
            }
        ],
        "inactiveIngredients": [],
    })
    assert result.verdict == "CAUTION"
    assert "B0_WATCHLIST_SUBSTANCE" in result.safety_signals
    assert result.short_circuits_scoring is False


def test_choline_category_is_vitamin_like_not_amino_acid() -> None:
    choline = _iqm()["choline"]
    assert choline["category"] == "vitamins"
    assert choline["category_enum"] == "vitamins"
