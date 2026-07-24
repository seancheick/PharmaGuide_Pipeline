"""Drug-class membership completeness — 2026-07-24 audit (Codex point 6).

Most classes were already ATC-comprehensive; the sweep + live RxNorm verification
found a handful of CURRENT, commonly-prescribed members missing from otherwise-
complete classes, where the class's rule applies UNIFORMLY to the new member (so
adding it closes a real missed-warning without creating a wrong one). Each rxcui
was live-verified Active + correct entity before insertion.

Deliberately EXCLUDED (documented in the audit report), NOT oversights:
  - valproate / gabapentin / pregabalin → anticonvulsants  (Section 3: calcium &
    vitamin K rules on the broad class are enzyme-inducer-specific; adding a
    non-inducer AED fires wrong warnings until attribution is fixed)
  - norgestimate / norgestrel → oral_contraceptives  (Section 4: all 7 rules are
    estrogen-mechanism; norgestrel is now an OTC progestin-only pill)
  - pamidronate → bisphosphonates  (IV-only; the rule is oral-bioavailability
    chelation — a wrong warning for an IV drug)
"""

import json
from pathlib import Path

_CLASSES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "drug_classes.json").read_text()
)

# (class_id, rxcui, member_name) — every one live-verified on 2026-07-24.
_ADDED = [
    ("class:proton_pump_inhibitors", "816346", "dexlansoprazole"),
    ("class:acid_suppressants", "816346", "dexlansoprazole"),
    ("class:fluoroquinolones", "1927663", "delafloxacin"),
    ("class:fluoroquinolones", "138099", "gemifloxacin"),
    ("class:antiplatelet_agents", "3521", "dipyridamole"),
    ("class:insulins", "1605101", "insulin isophane"),
    ("class:hiv_protease_inhibitors", "195088", "lopinavir"),
]


def _pairs(class_id):
    c = _CLASSES["classes"][class_id]
    return list(zip(c["member_rxcuis"], c["member_names"]))


def test_added_members_present_and_aligned():
    for cid, rx, name in _ADDED:
        pairs = _pairs(cid)
        assert (rx, name) in pairs, f"{cid} missing aligned ({rx}, {name})"


def test_no_duplicate_rxcuis_in_touched_classes():
    for cid in {c for c, _, _ in _ADDED}:
        rxcuis = _CLASSES["classes"][cid]["member_rxcuis"]
        assert len(rxcuis) == len(set(rxcuis)), f"{cid} has duplicate rxcuis"


def test_total_members_metadata_consistent():
    computed = sum(len(c["member_rxcuis"]) for c in _CLASSES["classes"].values())
    assert _CLASSES["_metadata"]["total_members"] == computed


def test_excluded_entanglements_not_added():
    # Guard against a future well-meaning "completeness" pass adding these before
    # their section resolves the attribution/structural issue.
    anticonv = dict(_pairs("class:anticonvulsants"))
    assert "11118" not in anticonv, "valproate must NOT be in broad anticonvulsants (Section 3)"
    assert "25480" not in anticonv, "gabapentin must NOT be in broad anticonvulsants (Section 3)"
    bis = dict(_pairs("class:bisphosphonates"))
    assert "11473" not in bis, "pamidronate is IV — must NOT be in bisphosphonates (oral-timing rule)"
