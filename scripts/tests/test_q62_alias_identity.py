"""LEDGER Q62 (Sean 2026-10-02): shared hazard is not shared identity.

An alias must be the substance itself (synonym, salt or form, or a real label
name for it). Related compounds, other species, drug classes and marketing
phrases get their own rule or none.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="module")
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    return SupplementEnricherV3()


def _ids(enricher, name):
    result = enricher._check_banned_substances([{"name": name, "standardName": name}])
    return {s.get("banned_id") for s in result.get("substances", [])}


@pytest.mark.parametrize(
    "label, wrong_rule",
    [
        ("Valerophenone", "BANNED_DMHA"),
        ("2-Aminoheptane", "BANNED_DMHA"),
        ("2-Amino-5-methylhexane", "BANNED_DMHA"),
        ("Sida cordifolia", "BANNED_EPHEDRA"),
        ("Rauwolscine", "RISK_YOHIMBE"),
        ("Alpha-Yohimbine", "RISK_YOHIMBE"),
        ("Corynanthine", "RISK_YOHIMBE"),
        ("Fluoromodafinil", "NOOTROPIC_FLMODAFINIL"),
        ("Amanita pantherina", "SCHED_AMANITA_MUSCARIA"),
        ("PDE5 inhibitor", "SPIKE_SILDENAFIL"),
        ("GE Labs", "RECALLED_GE_LABS_YKARINE"),
        ("Eria jarensis", "ADD_N_PHENETHYL_DIMETHYLAMINE"),
        ("Mushroom Blend (shrooms)", "SCHED_PSILOCYBIN"),
        ("Hydroxypropyl Methylcellulose Phthalate", "BANNED_ADD_PHTHALATES"),
    ],
)
def test_a_different_substance_does_not_inherit_the_rule(enricher, label, wrong_rule):
    assert wrong_rule not in _ids(enricher, label)


@pytest.mark.parametrize(
    "label, rule",
    [
        ("DMHA", "BANNED_DMHA"), ("Octodrine", "BANNED_DMHA"), ("2-Amino-6-methylheptane", "BANNED_DMHA"),
        ("Ephedra", "BANNED_EPHEDRA"), ("Ma Huang", "BANNED_EPHEDRA"),
        ("Sida cordifolia", "BANNED_SIDA_CORDIFOLIA"),
        ("Yohimbine HCl", "RISK_YOHIMBE"), ("Yohimbe bark extract", "RISK_YOHIMBE"),
        ("Flmodafinil", "NOOTROPIC_FLMODAFINIL"), ("Amanita muscaria", "SCHED_AMANITA_MUSCARIA"),
        ("Sildenafil", "SPIKE_SILDENAFIL"), ("Psilocybin", "SCHED_PSILOCYBIN"),
        ("Diethyl Phthalate", "BANNED_ADD_PHTHALATES"),
    ],
)
def test_the_substance_itself_still_matches(enricher, label, rule):
    assert rule in _ids(enricher, label)


def test_sida_cordifolia_has_its_own_verified_rule():
    import json
    from identity.safety import SafetySignal
    from scoring_v4.gate_safety import _hard_policy_missing_requirements
    entry = next(e for e in json.loads((ROOT / "scripts/data/banned_recalled_ingredients.json").read_text())["ingredients"]
                 if e["id"] == "BANNED_SIDA_CORDIFOLIA")
    signal = SafetySignal(entry_id=entry["id"], source_db="banned_recalled_ingredients", status="banned", severity="critical",
                          subject_role="active", match_resolution="confirmed", match_confidence=1.0, policy_eligible=True,
                          review_required=False, inactive_policy="", evidence_text="Sida cordifolia")
    assert _hard_policy_missing_requirements(entry, signal) == []
