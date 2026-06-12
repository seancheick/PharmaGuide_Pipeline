"""Regression contract for the 2026-06 vitamin/mineral IQM audit.

Encodes the corrected state for findings verified against:
  - the file's own scoring_contract_note / honesty_rule (bio_score = absorption
    for systemic actives; do not inflate for coenzyme status / sourcing / branding),
  - the file's own Batch-12 CLASS-FINDING (FMN/FAD/TPP/pantethine systemic F == parent F),
  - independently content-verified PK (PMIDs 6120218, 4056044, 23351578, 23140417,
    12899840; PubChem CID 61833, 5280791).

Invariant relied on throughout: score == bio_score + 3*natural (capped 18).
"""
import json
import os

import pytest

IQM_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ingredient_quality_map.json")


@pytest.fixture(scope="module")
def iqm():
    with open(IQM_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _form(iqm, parent, form):
    return iqm[parent]["forms"][form]


def _aliases_lower(iqm, parent, form):
    return {a.lower() for a in _form(iqm, parent, form).get("aliases", [])}


# ── 1. Active-coenzyme / poor-bioavailability bio_score corrections ──────────
# (parent, form, expected_bio_score, rationale)
SCORE_TARGETS = [
    ("vitamin_b2_riboflavin", "riboflavin-5-phosphate", 10),          # FMN -> riboflavin F
    ("vitamin_b2_riboflavin", "flavin adenine dinucleotide (FAD)", 10),
    ("vitamin_b6_pyridoxine", "pyridoxal-5-phosphate (P5P)", 10),     # PLP -> pyridoxal F
    ("vitamin_b5_pantothenic", "pantethine", 12),                     # -> Ca-pantothenate band
    ("vitamin_b3_niacin", "inositol hexanicotinate", 5),              # Keenan 2013: no bioavailability
    ("vitamin_k", "menaquinone-4 (MK-4)", 7),                         # undetectable serum at nutritional dose
    ("vitamin_e", "tocotrienols", 9),                                 # poor a-TTP retention
    ("vitamin_d", "micellized D3", 12),                               # no proven premium over standard D3
    ("vitamin_d", "liposomal D3", 12),
]


@pytest.mark.parametrize("parent,form,expected", SCORE_TARGETS)
def test_bio_score_corrected(iqm, parent, form, expected):
    assert _form(iqm, parent, form)["bio_score"] == expected


@pytest.mark.parametrize("parent,form,_", SCORE_TARGETS)
def test_score_invariant_holds(iqm, parent, form, _):
    f = _form(iqm, parent, form)
    expected = min(18, f["bio_score"] + (3 if f.get("natural") else 0))
    assert f["score"] == expected, f"{parent}::{form} score must equal bio_score+3*natural"


# ── 2. natural-source bonus misapplied to synthetic/inorganic forms ─────────
def test_phosphate_salts_not_natural(iqm):
    f = _form(iqm, "phosphorus", "phosphate salts")
    assert f["natural"] is False
    assert f["score"] == f["bio_score"]


def test_generic_d_biotin_not_natural(iqm):
    # commercial d-biotin is synthetic; natural bonus stays available via
    # `biotin from yeast` / `protein_bound_biotin`.
    f = _form(iqm, "vitamin_b7_biotin", "d-biotin")
    assert f["natural"] is False
    assert f["score"] == f["bio_score"]
    assert _form(iqm, "vitamin_b7_biotin", "biotin from yeast")["natural"] is True


# ── 3. Alias identity errors removed (fall through to conservative match) ────
def test_gamma_carotene_not_betacarotene(iqm):
    assert "gamma-carotene" not in _aliases_lower(iqm, "vitamin_a", "beta-carotene from mixed carotenoids")


def test_bare_dunaliella_source_removed(iqm):
    al = _aliases_lower(iqm, "vitamin_a", "beta-carotene from mixed carotenoids")
    for bare in ["dunaliella salina", "dunaliella", "d. salina", "dunaliella salina extract"]:
        assert bare not in al, f"{bare} is a source organism, not the beta-carotene compound"
    # explicit beta-carotene source labels are kept
    assert "dunaliella beta-carotene" in al


def test_dolomite_not_calcium_carbonate(iqm):
    assert "dolomite" not in _aliases_lower(iqm, "calcium", "calcium carbonate")  # CaMg(CO3)2, not CaCO3


# ── 4. Marketing / over-broad aliases removed from premium forms ────────────
def test_pantethine_marketing_aliases_removed(iqm):
    al = _aliases_lower(iqm, "vitamin_b5_pantothenic", "pantethine")
    for m in ["active b5", "coenzyme a precursor", "lipid-supporting b5"]:
        assert m not in al


def test_ester_c_generic_ester_removed(iqm):
    al = _aliases_lower(iqm, "vitamin_c", "ester-C (calcium ascorbate)")
    for m in ["vitamin c ester", "vit c ester"]:
        assert m not in al


# ── 5. Alias re-routing to the correct form ─────────────────────────────────
def test_b3_combination_labels_to_unspecified(iqm):
    nia = _aliases_lower(iqm, "vitamin_b3_niacin", "niacinamide")
    uns = _aliases_lower(iqm, "vitamin_b3_niacin", "vitamin b3 (unspecified)")
    for combo in ["niacin & niacinamide", "niacin and niacinamide", "niacinamide & niacin"]:
        assert combo not in nia
        assert combo in uns


def test_b3_fermented_niacinamide_to_niacinamide(iqm):
    nia = _aliases_lower(iqm, "vitamin_b3_niacin", "niacinamide")
    uns = _aliases_lower(iqm, "vitamin_b3_niacin", "vitamin b3 (unspecified)")
    for a in ["poten-zyme niacinamide", "poten zyme niacinamide", "fermented niacinamide"]:
        assert a in nia
        assert a not in uns


def test_activated_b6_to_p5p(iqm):
    p5p = _aliases_lower(iqm, "vitamin_b6_pyridoxine", "pyridoxal-5-phosphate (P5P)")
    uns = _aliases_lower(iqm, "vitamin_b6_pyridoxine", "vitamin b6 (unspecified)")
    for a in ["activated vitamin b6", "vitamin b6, activated", "vitamin b6 activated"]:
        assert a in p5p
        assert a not in uns


def test_methylated_folate_routes_to_5mthf(iqm):
    assert "methylated folate" not in {a.lower() for a in iqm["vitamin_b9_folate"].get("aliases", [])}
    assert "methylated folate" in _aliases_lower(iqm, "vitamin_b9_folate", "5-methyltetrahydrofolate (5-MTHF)")


def test_k2vital_delta_routes_to_mk7_alltrans(iqm):
    parent = {a.lower() for a in iqm["vitamin_k"].get("aliases", [])}
    mk7 = _aliases_lower(iqm, "vitamin_k", "menaquinone-7 all-trans")
    for a in ["k2 vital delta", "k2vital delta"]:
        assert a not in parent
        assert a in mk7


def test_hydroxyapatite_routes_to_calcium(iqm):
    phos = _aliases_lower(iqm, "phosphorus", "phosphate salts")
    cal = _aliases_lower(iqm, "calcium", "calcium hydroxyapatite")
    cal_reachable = cal | {"calcium hydroxyapatite"}  # form name is indexed too
    for a in ["hydroxyapatite", "microcrystalline hydroxyapatite", "calcium hydroxyapatite"]:
        assert a not in phos
        assert a in cal_reachable
    # explicit phosphorus-context label stays
    assert "phosphorus from hydroxyapatite" in phos


def test_injectable_b12_removed_from_hydroxocobalamin(iqm):
    assert "injectable b12" not in _aliases_lower(iqm, "vitamin_b12_cobalamin", "hydroxocobalamin")


# ── 6. Note text no longer contradicts the corrected score ──────────────────
def test_notes_drop_direct_use_marketing(iqm):
    r5p = _form(iqm, "vitamin_b2_riboflavin", "riboflavin-5-phosphate")["notes"].lower()
    assert "uses this form directly" not in r5p
    p5p = _form(iqm, "vitamin_b6_pyridoxine", "pyridoxal-5-phosphate (P5P)")["notes"].lower()
    assert "uses p5p directly" not in p5p
    pan = _form(iqm, "vitamin_b5_pantothenic", "pantethine")["notes"].lower()
    assert "superior to standard pantothenic acid" not in pan
