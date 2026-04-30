"""
Regression tests for the W/M/L/C interaction rules batch (clinician-locked
2026-04-30) and the pregnancy/lactation hybrid gap-fill.

Locks:
- Each W/M/L/C rule exists at the clinician-specified severity
- Pregnancy/lactation 100% coverage with evidence_level field
- Pre-seeded pregnancy categories on Ginkgo, Dong Quai, Ginseng, Yohimbe,
  Goldenseal, Berberine

Deferred (no subject_ref): W10 bromelain, M2 tyramine — explicitly NOT
asserted; flag for next batch when subjects are introduced.
"""
from __future__ import annotations
import json
from pathlib import Path

import pytest

DATA_PATH = Path(__file__).parent.parent / "data" / "ingredient_interaction_rules.json"


@pytest.fixture(scope="module")
def rules() -> list:
    return json.loads(DATA_PATH.read_text())["interaction_rules"]


def find_drug_class_rule(rules, db, canonical_id, drug_class_id):
    for r in rules:
        sref = r.get("subject_ref") or {}
        if sref.get("db") != db or sref.get("canonical_id") != canonical_id:
            continue
        for dcr in r.get("drug_class_rules") or []:
            if dcr.get("drug_class_id") == drug_class_id:
                return dcr
    return None


# ---------------------------------------------------------------------------
# W (Warfarin / anticoagulants) — clinician-locked severities
# ---------------------------------------------------------------------------

W_FAMILY = [
    # (label, db, canonical_id, drug_class_id, expected_severity)
    ("W1",  "ingredient_quality_map", "vitamin_k",      "anticoagulants", "avoid"),
    ("W2",  "ingredient_quality_map", "ginkgo",         "anticoagulants", "avoid"),
    ("W3",  "ingredient_quality_map", "garlic",         "anticoagulants", "monitor"),
    ("W4",  "ingredient_quality_map", "fish_oil",       "anticoagulants", "caution"),
    ("W5a", "ingredient_quality_map", "turmeric",       "anticoagulants", "caution"),
    ("W5b", "ingredient_quality_map", "curcumin",       "anticoagulants", "caution"),
    ("W6",  "ingredient_quality_map", "st_johns_wort",  "anticoagulants", "contraindicated"),
    ("W7",  "ingredient_quality_map", "coq10",          "anticoagulants", "monitor"),
    ("W8",  "ingredient_quality_map", "dong_quai",      "anticoagulants", "avoid"),
    ("W9",  "ingredient_quality_map", "ginseng",        "anticoagulants", "caution"),
    ("W11", "ingredient_quality_map", "vitamin_e",      "anticoagulants", "caution"),
    ("W12", "ingredient_quality_map", "cranberry",      "anticoagulants", "monitor"),
]


@pytest.mark.parametrize("label,db,cid,drug_class,sev", W_FAMILY)
def test_w_family_rule_exists_at_locked_severity(rules, label, db, cid, drug_class, sev):
    dcr = find_drug_class_rule(rules, db, cid, drug_class)
    assert dcr is not None, f"{label}: missing rule {db}::{cid} × {drug_class}"
    assert dcr["severity"] == sev, (
        f"{label}: {cid} × {drug_class} severity={dcr['severity']!r}, expected {sev!r} "
        f"(clinician-locked 2026-04-30)"
    )


# ---------------------------------------------------------------------------
# M (MAO inhibitors)
# ---------------------------------------------------------------------------

M_FAMILY = [
    ("M1",  "ingredient_quality_map",        "phenylethylamine",  "mao_inhibitors", "contraindicated"),
    ("M3a", "ingredient_quality_map",        "5_htp",             "mao_inhibitors", "contraindicated"),
    ("M3b", "ingredient_quality_map",        "l_tryptophan",      "mao_inhibitors", "contraindicated"),
    ("M4",  "ingredient_quality_map",        "st_johns_wort",     "mao_inhibitors", "contraindicated"),
    ("M5",  "ingredient_quality_map",        "yohimbe",           "mao_inhibitors", "contraindicated"),
    ("M6",  "ingredient_quality_map",        "ginseng",           "mao_inhibitors", "caution"),
    ("M7",  "banned_recalled_ingredients",   "ADD_HORDENINE",     "mao_inhibitors", "contraindicated"),
    ("M8",  "ingredient_quality_map",        "same",              "mao_inhibitors", "avoid"),
]


@pytest.mark.parametrize("label,db,cid,drug_class,sev", M_FAMILY)
def test_m_family_rule_exists_at_locked_severity(rules, label, db, cid, drug_class, sev):
    dcr = find_drug_class_rule(rules, db, cid, drug_class)
    assert dcr is not None, f"{label}: missing rule {db}::{cid} × {drug_class}"
    assert dcr["severity"] == sev, (
        f"{label}: {cid} × {drug_class} severity={dcr['severity']!r}, expected {sev!r}"
    )


# ---------------------------------------------------------------------------
# L (Lithium)
# ---------------------------------------------------------------------------

L_FAMILY = [
    ("L1",  "ingredient_quality_map", "caffeine",  "lithium", "caution"),
    ("L2",  "ingredient_quality_map", "psyllium",  "lithium", "monitor"),
    ("L3",  "ingredient_quality_map", "sodium",    "lithium", "monitor"),
    ("L4a", "ingredient_quality_map", "turmeric",  "lithium", "monitor"),
    ("L4b", "ingredient_quality_map", "curcumin",  "lithium", "monitor"),
    ("L5",  "ingredient_quality_map", "magnesium", "lithium", "monitor"),
    ("L6",  "ingredient_quality_map", "iodine",    "lithium", "caution"),
    ("L7",  "ingredient_quality_map", "dandelion", "lithium", "monitor"),
]


@pytest.mark.parametrize("label,db,cid,drug_class,sev", L_FAMILY)
def test_l_family_rule_exists_at_locked_severity(rules, label, db, cid, drug_class, sev):
    dcr = find_drug_class_rule(rules, db, cid, drug_class)
    assert dcr is not None, f"{label}: missing rule {db}::{cid} × {drug_class}"
    assert dcr["severity"] == sev, (
        f"{label}: {cid} × {drug_class} severity={dcr['severity']!r}, expected {sev!r}"
    )


# ---------------------------------------------------------------------------
# C (CYP3A4 / grapefruit)
# ---------------------------------------------------------------------------

C_FAMILY = [
    ("C1",  "ingredient_quality_map",   "citrus_bergamot",      "statins",                 "avoid"),
    ("C2",  "ingredient_quality_map",   "citrus_bergamot",      "calcium_channel_blockers","avoid"),
    ("C3",  "ingredient_quality_map",   "citrus_bergamot",      "immunosuppressants",      "contraindicated"),
    ("C4a", "ingredient_quality_map",   "st_johns_wort",        "immunosuppressants",      "contraindicated"),
    ("C4b", "ingredient_quality_map",   "st_johns_wort",        "oral_contraceptives",     "contraindicated"),
    ("C5",  "ingredient_quality_map",   "goldenseal",           "cyp3a4_substrates",       "avoid"),
    ("C6",  "botanical_ingredients",    "schisandra_berry",     "cyp3a4_substrates",       "caution"),
    ("C7",  "ingredient_quality_map",   "berberine_supplement", "cyp3a4_substrates",       "caution"),
    ("C8",  "ingredient_quality_map",   "citrus_bergamot",      "antiarrhythmics",         "avoid"),
    ("C9",  "ingredient_quality_map",   "citrus_bergamot",      "anticoagulants",          "caution"),
    ("C10", "ingredient_quality_map",   "citrus_bergamot",      "oral_contraceptives",     "monitor"),
]


@pytest.mark.parametrize("label,db,cid,drug_class,sev", C_FAMILY)
def test_c_family_rule_exists_at_locked_severity(rules, label, db, cid, drug_class, sev):
    dcr = find_drug_class_rule(rules, db, cid, drug_class)
    assert dcr is not None, f"{label}: missing rule {db}::{cid} × {drug_class}"
    assert dcr["severity"] == sev, (
        f"{label}: {cid} × {drug_class} severity={dcr['severity']!r}, expected {sev!r}"
    )


# ---------------------------------------------------------------------------
# Schema invariants — every drug_class_rule has the required clinical payload
# ---------------------------------------------------------------------------

REQUIRED_DCR_FIELDS = {"severity", "evidence_level", "mechanism", "action",
                       "alert_headline", "alert_body", "informational_note", "sources"}


@pytest.mark.parametrize("label,db,cid,drug_class,_", W_FAMILY + M_FAMILY + L_FAMILY + C_FAMILY)
def test_w_m_l_c_rules_carry_full_payload(rules, label, db, cid, drug_class, _):
    dcr = find_drug_class_rule(rules, db, cid, drug_class)
    assert dcr is not None
    missing = REQUIRED_DCR_FIELDS - set(dcr.keys())
    assert not missing, f"{label}: missing fields {missing}"
    assert dcr["mechanism"], f"{label}: empty mechanism"
    assert dcr["alert_headline"], f"{label}: empty alert_headline"
    assert dcr["alert_body"], f"{label}: empty alert_body"


# ---------------------------------------------------------------------------
# Pregnancy/lactation gap-fill — 100% coverage
# ---------------------------------------------------------------------------


def test_all_rules_have_pregnancy_category(rules):
    """Every rule has a populated pregnancy_category (no empty/None)."""
    empties = [r["id"] for r in rules
               if (r.get("pregnancy_lactation") or {}).get("pregnancy_category") in (None, "")]
    assert not empties, f"Rules with empty pregnancy_category: {empties}"


def test_all_rules_have_lactation_category(rules):
    empties = [r["id"] for r in rules
               if (r.get("pregnancy_lactation") or {}).get("lactation_category") in (None, "")]
    assert not empties, f"Rules with empty lactation_category: {empties}"


def test_all_rules_have_evidence_level(rules):
    empties = [r["id"] for r in rules
               if (r.get("pregnancy_lactation") or {}).get("evidence_level") in (None, "")]
    assert not empties, f"Rules without evidence_level: {empties}"


def test_evidence_level_is_canonical(rules):
    """evidence_level must be one of the clinician-locked enum values."""
    canonical = {"no_data", "limited", "moderate", "strong",
                 # legacy values from earlier curation — accepted but flagged
                 "established", "probable", "theoretical"}
    bad = []
    for r in rules:
        ev = (r.get("pregnancy_lactation") or {}).get("evidence_level")
        if ev not in canonical:
            bad.append((r["id"], ev))
    assert not bad, f"Non-canonical evidence_level values: {bad}"


def test_banned_subjects_default_contraindicated_in_pregnancy(rules):
    """Option B: banned_recalled subjects default to contraindicated/avoid in pregnancy.
    Pre-existing curated `avoid` (e.g. CBD) is acceptable — both express
    'do not use'; the clinician's intent is no banned subject ships with
    a permissive pregnancy category.
    """
    acceptable = {"contraindicated", "avoid"}
    bad = []
    for r in rules:
        sref = r.get("subject_ref") or {}
        if sref.get("db") != "banned_recalled_ingredients":
            continue
        pc = (r.get("pregnancy_lactation") or {}).get("pregnancy_category")
        if pc not in acceptable:
            bad.append((r["id"], pc))
    assert not bad, (
        f"Banned subjects with permissive pregnancy category: {bad}. "
        f"Banned/recalled subjects must be contraindicated or avoid in pregnancy."
    )


# ---------------------------------------------------------------------------
# Pre-seeded pregnancy categories from clinician notes
# ---------------------------------------------------------------------------

PREG_PRE_SEEDS = [
    # (canonical_id, expected pregnancy_category)
    ("ginkgo",                 "caution"),
    ("dong_quai",              "avoid"),
    ("ginseng",                "caution"),
    ("yohimbe",                ("avoid", "contraindicated")),  # accept either
    ("goldenseal",             "avoid"),
    ("berberine_supplement",   ("caution", "avoid")),
]


@pytest.mark.parametrize("cid,expected", PREG_PRE_SEEDS)
def test_pregnancy_pre_seed_locked(rules, cid, expected):
    target = None
    for r in rules:
        if r.get("subject_ref", {}).get("canonical_id") == cid:
            target = r
            break
    assert target, f"No rule for canonical_id={cid}"
    pc = (target.get("pregnancy_lactation") or {}).get("pregnancy_category")
    if isinstance(expected, tuple):
        assert pc in expected, f"{cid} pregnancy_category={pc}, expected one of {expected}"
    else:
        assert pc == expected, f"{cid} pregnancy_category={pc}, expected {expected}"


# ---------------------------------------------------------------------------
# Section 6 open severity calls — locked to Position A (clinician table)
# ---------------------------------------------------------------------------


def test_section6_yohimbe_mao_locked_contraindicated(rules):
    """M5 Yohimbe × MAOIs locked to Position A: contraindicated."""
    dcr = find_drug_class_rule(rules, "ingredient_quality_map", "yohimbe", "mao_inhibitors")
    assert dcr is not None
    assert dcr["severity"] == "contraindicated", (
        "Section 6 open call M5: clinician locked Position A (contraindicated). "
        "Mechanism stacking (α-2 antagonism + MAOI) is hypertensive-crisis territory."
    )


def test_section6_turmeric_lithium_locked_monitor(rules):
    """L4 Turmeric/curcumin × Lithium locked to Position A: monitor (conservative)."""
    dcr = find_drug_class_rule(rules, "ingredient_quality_map", "turmeric", "lithium")
    assert dcr is not None
    assert dcr["severity"] == "monitor", (
        "Section 6 open call L4: clinician locked Position A (monitor). "
        "Conservative posture given lithium's narrow therapeutic index."
    )
    # Notes field must capture the conservative-posture rationale
    mech = dcr.get("mechanism", "").lower()
    assert "theoretical" in mech or "conservative" in mech, (
        "L4 mechanism field must document conservative-posture rationale "
        "(clinical evidence absent for curcumin specifically)"
    )
