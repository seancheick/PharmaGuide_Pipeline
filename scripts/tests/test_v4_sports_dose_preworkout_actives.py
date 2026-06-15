"""Sports dose rubric — non-classic pre-workout / recovery actives.

A transparent, well-dosed pre-workout must not crater at dose=0 just because its
primary actives are alpha-GPC / ATP / caffeine / betaine / taurine or a disclosed
BCAA aggregate rather than the classic creatine/protein/BCAA-trio anchors.

Dose bands are source-verified (no invented numbers); evidence strength sets the
credit cap (strong=caffeine, moderate=alpha-GPC/betaine, weak=ATP/taurine, and
BCAA credited as a recovery aid, not an ergogenic):
  - alpha-GPC 600 mg  — Ziegenfuss 2008 (JISSN), moderate
  - ATP 400 mg/day    — PMID 34957398, weak-equivocal -> capped
  - caffeine 3-6 mg/kg ~ 200-400 mg — ISSN PMID 33388079, strong
  - betaine 2.5 g/day — PMC2915951, moderate
  - taurine 1-3 g (flat dose-response) — PMID 40852891, weak -> capped, no under-dose penalty
  - BCAA 5-10 g       — PMID 33586928, recovery not performance -> capped

Disclosed-dose-only: an undisclosed (NP / 0) active earns nothing, so opaque
proprietary blends correctly stay cratered (parity with the opaque-fish-oil omega
precedent and the B5 transparency penalty).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring_v4.modules.sports_dose import score_dose


def _row(canonical_id: str, quantity, unit: str, *, name: str | None = None) -> dict:
    return {
        "name": name or canonical_id.replace("_", " ").title(),
        "standard_name": name or canonical_id.replace("_", " ").title(),
        "canonical_id": canonical_id,
        "quantity": quantity,
        "unit": unit,
        "mapped": True,
        "mapped_identity": True,
        "scoreable_identity": True,
        "score_eligible_by_cleaner": True,
        "role_classification": "active_scorable",
        "cleaner_row_role": "active_scorable",
        "dose_class": "therapeutic_mass",
        "source_section": "activeIngredients",
        "raw_source_path": f"activeIngredients[{canonical_id}]",
    }


def _product(*rows: dict, name: str = "Pre-Workout Elite", primary_type: str = "pre_workout") -> dict:
    return {
        "fullName": name,
        "product_name": name,
        "primary_type": primary_type,
        "supplement_taxonomy": {"primary_type": primary_type},
        "ingredient_quality_data": {"ingredients_scorable": list(rows)},
    }


def _primary(product) -> tuple:
    res = score_dose(product)
    return res["components"]["sports_primary_active_dose"], res["metadata"]["dose_basis"]


# --- alpha-GPC (moderate) ---------------------------------------------------

def test_alpha_gpc_600mg_full_credit() -> None:
    assert _primary(_product(_row("alpha_gpc", 600, "mg"))) == (18.0, "alpha_gpc_at_least_600_mg")


def test_alpha_gpc_300mg_moderate_credit() -> None:
    assert _primary(_product(_row("alpha_gpc", 300, "mg"))) == (14.0, "alpha_gpc_300_to_600_mg")


# --- ATP (weak-equivocal -> capped at 12) -----------------------------------

def test_atp_400mg_capped_credit() -> None:
    assert _primary(_product(_row("adenosine_triphosphate", 450, "mg"))) == (12.0, "atp_at_least_400_mg")


# --- caffeine (strong) ------------------------------------------------------

def test_caffeine_200mg_full_credit() -> None:
    assert _primary(_product(_row("caffeine", 200, "mg"))) == (18.0, "caffeine_200_to_400_mg")


# --- betaine (moderate) -----------------------------------------------------

def test_betaine_2500mg_full_credit() -> None:
    assert _primary(_product(_row("betaine", 2500, "mg"))) == (16.0, "betaine_at_least_2_5_g")


# --- taurine (weak -> capped at 10, no under-dose penalty) -------------------

def test_taurine_1500mg_capped_credit() -> None:
    assert _primary(_product(_row("taurine", 1500, "mg"))) == (10.0, "taurine_at_least_1_g")


# --- BCAA aggregate (recovery aid -> capped) --------------------------------

def test_bcaa_aggregate_7g_recovery_credit() -> None:
    assert _primary(
        _product(_row("branched_chain_amino_acids", 7000, "mg"), primary_type="amino_acid")
    ) == (14.0, "bcaa_aggregate_at_least_5_g")


# --- disclosed-dose-only: opaque actives earn nothing -----------------------

def test_undisclosed_alpha_gpc_earns_no_dose_credit() -> None:
    primary, _basis = _primary(_product(_row("alpha_gpc", 0, "NP")))
    assert primary == 0.0


# --- off-list dominant active: generic dose proxy instead of crater ---------

def test_offlist_dominant_active_uses_generic_dose_proxy() -> None:
    # 67304 shape: L-carnitine 1 g (mass-dominant, no sports band) + a token BCAA.
    # The sports rubric must NOT discard the carnitine and crater to the token BCAA;
    # it falls back to the generic dose-adequacy proxy so the disclosed primary is
    # credited (proxy ~16, not the ~1 token-BCAA band).
    res = score_dose(
        _product(
            _row("l_carnitine", 1, "Gram(s)"),
            _row("branched_chain_amino_acids", 250, "mg"),
            name="Carnitine 1000 + BCAA",
            primary_type="amino_acid",
        )
    )
    assert res["score"] >= 12.0
    assert res["metadata"]["dose_basis"] == "generic_dose_proxy_for_offlist_primary"


def test_onlist_underdosed_active_is_not_rescued_by_proxy() -> None:
    # An under-dosed creatine (1 g, on-list) keeps its strict sports band (8.0); the
    # off-list proxy floor must NOT rescue it, because creatine has a sports band.
    res = score_dose(_product(_row("creatine_monohydrate", 1, "Gram(s)"), primary_type="general_supplement"))
    assert res["components"]["sports_primary_active_dose"] == 8.0
    assert res["metadata"]["dose_basis"] == "creatine_under_2_g"


# --- real Thorne Pre-Workout Elite shape: best disclosed primary wins -------

def test_thorne_preworkout_alpha_gpc_atp_takes_alpha_gpc_primary() -> None:
    # 323126: alpha-GPC 600 (-> 18) + ATP 450 (-> 12); best primary = alpha-GPC 18.
    primary, basis = _primary(
        _product(_row("alpha_gpc", 600, "mg"), _row("adenosine_triphosphate", 450, "mg"))
    )
    assert primary == 18.0
    assert basis == "alpha_gpc_at_least_600_mg"
