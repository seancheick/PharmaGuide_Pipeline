"""The EU "activity and attention in children" label belongs to six colours only.

Regulation (EC) No 1333/2008, Annex V (EUR-Lex, read 2026-10-02) requires the
statement on foods containing E110, E104, E122, E129, E102 or E124. Brilliant
Blue (E133) and indigo carmine (E132) are not on the list, yet ADD_BLUE1 and
ADD_BLUE2 said the label applied to them and carried a child warning built on
it (Sean approved the correction, 2026-10-02). E104, E122 and E124 have no
entry in this registry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ANNEX_V_ENTRIES = {"ADD_YELLOW5": "E102", "ADD_YELLOW6": "E110", "ADD_RED40": "E129"}
NOT_ANNEX_V = {"ADD_BLUE1": "E133", "ADD_BLUE2": "E132"}


def _entries() -> dict:
    data = json.loads((ROOT / "data" / "harmful_additives.json").read_text())
    return {e["id"]: e for e in data["harmful_additives"]}


@pytest.mark.parametrize("entry_id, e_number", sorted(ANNEX_V_ENTRIES.items()))
def test_annex_v_colours_state_the_eu_child_label(entry_id, e_number):
    eu = _entries()[entry_id]["regulatory_status"]["EU"]
    assert e_number in eu
    assert "activity and attention in children" in eu


@pytest.mark.parametrize("entry_id, e_number", sorted(NOT_ANNEX_V.items()))
def test_blue_dyes_carry_no_southampton_child_warning(entry_id, e_number):
    entry = _entries()[entry_id]
    eu = entry["regulatory_status"]["EU"]
    assert eu.startswith(f"{e_number} is approved in the EU")
    assert "not one of the six colours" in eu
    assert "Southampton" not in eu
    for warning in entry["population_warnings"]:
        assert not warning.startswith("Children"), warning
    copy = " ".join(str(entry.get(k) or "") for k in ("safety_warning", "safety_warning_one_liner",
                                                      "safety_summary", "safety_summary_one_liner"))
    assert "Southampton" not in copy and "hyperactiv" not in copy.lower()


@pytest.mark.parametrize("entry_id", sorted(NOT_ANNEX_V))
def test_blue_dyes_cite_the_annex_v_regulation(entry_id):
    urls = {r.get("url") for r in _entries()[entry_id]["references_structured"]}
    assert "https://eur-lex.europa.eu/eli/reg/2008/1333/oj" in urls


# LEDGER Q60 (Sean 2026-10-02): 4-MEI is a caramel-colour (E150c/d) contaminant,
# not a property of tartrazine or sunset yellow. EFSA 2009 kept tartrazine's ADI
# at 7.5 mg/kg bw/day (EFSA Journal 2009;7(11):1331); EFSA 2014 set sunset
# yellow's at 4 mg/kg bw/day, replacing the temporary 1 mg/kg of 2009
# (EFSA Journal 2014;12(7):3765).
def _without_review(entry: dict) -> str:
    return json.dumps({k: v for k, v in entry.items() if k != "review"})


@pytest.mark.parametrize("entry_id", ["ADD_YELLOW5", "ADD_YELLOW6"])
def test_yellow_dyes_carry_no_caramel_colour_4mei_claims(entry_id):
    text = _without_review(_entries()[entry_id]).lower()
    for gone in ("4-mei", "methylimidazole", "cola"):
        assert gone not in text, (entry_id, gone)


def test_caramel_colour_keeps_its_4mei_warning():
    assert "4-MEI" in _entries()["ADD_CARAMEL_COLOR"]["mechanism_of_harm"]


@pytest.mark.parametrize(
    "entry_id, gone",
    [
        ("ADD_YELLOW5", "reduced from 10"),
        ("ADD_YELLOW5", "2009:1330"),
        ("ADD_YELLOW6", "2.5 mg/kg"),
        ("ADD_YELLOW6", "group ADI"),
    ],
)
def test_yellow_dye_adi_history_matches_efsa(entry_id, gone):
    assert gone not in _without_review(_entries()[entry_id])
