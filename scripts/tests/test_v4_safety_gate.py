"""v4 Layer 1 — Safety Gate tests (P1.1).

Locks the contract for `scoring_v4.gate_safety.evaluate_safety_gate`:

Verdict precedence (per SCORING_V4_PROPOSAL.md §4 Layer 1):
  BLOCKED > UNSAFE > CAUTION > None

Inputs read from the enriched product (same contract v3 reads):
  - contaminant_data.banned_substances.substances (status: banned /
    recalled / high_risk / watchlist)
  - has_banned_substance / has_recalled_ingredient (top-level enricher
    fallback flags)
  - has_disease_claims (top-level enricher flag)

BLOCKED + UNSAFE short-circuit scoring (score=None, anchored remains
False until canary-membership lookup lands). CAUTION does NOT short-circuit — scoring still runs;
CAUTION overrides POOR/SAFE in the final verdict resolution layer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


COMPLETE_GENERIC_PRODUCT = {
    "status": "active",
    "form_factor": "capsule",
    "supplement_type": {"type": "single_nutrient"},
    "ingredient_quality_data": {
        "total_active": 1,
        "ingredients_scorable": [
            {
                "name": "Magnesium",
                "canonical_id": "magnesium",
                "mapped": True,
                "dose": 200,
                "unit": "mg",
            }
        ],
    },
}


# --- Direct gate contract -------------------------------------------------


def test_banned_substance_in_contaminant_data_returns_blocked() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {
                        "banned_name": "Vinpocetine",
                        "status": "banned",
                        "match_type": "exact",
                    }
                ]
            }
        }
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "BLOCKED"
    assert result.short_circuits_scoring is True
    assert result.blocking_reason == "banned_ingredient"
    assert "Vinpocetine" in (result.matched_substance or "")


def test_canonical_safety_flag_returns_blocked() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "contaminant_data": {
            "banned_substances": {
                "substances": [],
                "safety_flags": [
                    {
                        "entry_id": "BANNED_VINPOCETINE",
                        "source_db": "banned_recalled_ingredients",
                        "status": "banned",
                        "severity": "critical",
                        "match_type": "exact",
                        "matched_variant": "Vinpocetine",
                        "evidence_text": "Vinpocetine",
                        "confidence": "high",
                    }
                ],
            }
        }
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "BLOCKED"
    assert result.short_circuits_scoring is True
    assert result.blocking_reason == "banned_ingredient"
    assert "Vinpocetine" in (result.matched_substance or "")


def test_canonical_token_bounded_safety_flag_caution_review_not_blocked() -> None:
    """A likely-banned hit (token_bounded → resolution 'likely') must force
    CAUTION + needs_review — NEVER a hard BLOCK, and NEVER allowed to score SAFE.

    Behavior change (2026-05-30, authorized): previously likely-banned yielded
    verdict=None (review-only), which let products like Red Yeast Rice (banned
    monacolin-K source matched via token_bounded) score SAFE — a shipped safety
    downgrade vs v3 CAUTION. Now likely-banned forces CAUTION. Hard BLOCK still
    requires a CONFIRMED match (exact/alias).
    """
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "contaminant_data": {
            "banned_substances": {
                "substances": [],
                "safety_flags": [
                    {
                        "entry_id": "BANNED_TEST",
                        "source_db": "banned_recalled_ingredients",
                        "status": "banned",
                        "severity": "critical",
                        "match_type": "token_bounded",
                        "matched_variant": "Test",
                        "evidence_text": "Test",
                        "confidence": "medium",
                    }
                ],
            }
        }
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "CAUTION"          # forced — must not score SAFE
    assert result.verdict != "BLOCKED"          # likely ≠ confirmed; no hard block
    assert result.short_circuits_scoring is False
    assert result.needs_review is True
    assert "B0_LIKELY_BANNED_REVIEW" in result.safety_signals


def test_recalled_ingredient_returns_unsafe() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {
                        "banned_name": "DMAA",
                        "status": "recalled",
                        "match_type": "exact",
                    }
                ]
            }
        }
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "UNSAFE"
    assert result.short_circuits_scoring is True
    assert result.blocking_reason == "recalled_ingredient"


def test_high_risk_substance_returns_caution() -> None:
    """high_risk substances (e.g., yohimbine) → CAUTION verdict but
    scoring still runs (does NOT short-circuit per §4 Layer 1)."""
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"name": "Yohimbine", "status": "high_risk", "match_type": "exact"}
                ]
            }
        }
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "CAUTION"
    assert result.short_circuits_scoring is False
    assert "B0_HIGH_RISK_SUBSTANCE" in result.safety_signals


def test_watchlist_substance_returns_caution() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"name": "Some Watchlist", "status": "watchlist", "match_type": "exact"}
                ]
            }
        }
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "CAUTION"
    assert result.short_circuits_scoring is False
    assert "B0_WATCHLIST_SUBSTANCE" in result.safety_signals


def test_disease_claims_alone_returns_caution() -> None:
    """has_disease_claims on the enriched product alone → CAUTION.
    Marketing penalty (Layer 1 §4 row 'Opacity with risk' adjacent;
    disease claims are CAUTION-equivalent for verdict purposes)."""
    from scoring_v4.gate_safety import evaluate_safety_gate
    result = evaluate_safety_gate({"has_disease_claims": True})
    assert result.verdict == "CAUTION"
    assert result.short_circuits_scoring is False
    assert "DISEASE_CLAIM_DETECTED" in result.safety_signals


def test_caffeine_at_or_below_200_mg_does_not_change_safety_verdict() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "activeIngredients": [
            {"name": "Caffeine", "canonical_id": "caffeine", "quantity": 200, "unit": "mg"}
        ]
    }

    result = evaluate_safety_gate(product)

    assert result.verdict is None
    assert "STIMULANT_CAFFEINE_MODERATE_DOSE" in result.safety_signals


def test_high_caffeine_over_400_mg_forces_caution_without_short_circuit() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "activeIngredients": [
            {"name": "Caffeine Anhydrous", "canonical_id": "caffeine", "quantity": 425, "unit": "mg"}
        ]
    }

    result = evaluate_safety_gate(product)

    assert result.verdict == "CAUTION"
    assert result.short_circuits_scoring is False
    assert "STIMULANT_CAFFEINE_HIGH_DOSE" in result.safety_signals


def test_caffeine_300_to_400_mg_surfaces_signal_without_global_caution() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "activeIngredients": [
            {"name": "Caffeine", "canonical_id": "caffeine", "quantity": 325, "unit": "mg"}
        ]
    }

    result = evaluate_safety_gate(product)

    assert result.verdict is None
    assert "STIMULANT_CAFFEINE_ELEVATED_DOSE" in result.safety_signals


def test_hidden_caffeine_in_preworkout_blend_forces_caution_and_review() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "product_name": "Explosive Pre-Workout",
        "primary_type": "pre_workout",
        "activeIngredients": [
            {"name": "Caffeine Anhydrous", "canonical_id": "caffeine", "quantity": None, "unit": None}
        ],
        "proprietary_blends": [
            {"name": "Energy Matrix", "disclosure_level": "partial"}
        ],
    }

    result = evaluate_safety_gate(product)

    assert result.verdict == "CAUTION"
    assert result.short_circuits_scoring is False
    assert result.needs_review is True
    assert "STIMULANT_CAFFEINE_UNDISCLOSED_PREWORKOUT" in result.safety_signals


def test_undosed_green_tea_caffeine_outside_stimulant_context_is_review_signal_only() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "product_name": "Green Tea Extract",
        "primary_type": "botanical",
        "activeIngredients": [
            {"name": "Caffeine", "canonical_id": "caffeine", "quantity": None, "unit": None}
        ],
    }

    result = evaluate_safety_gate(product)

    assert result.verdict is None
    assert result.needs_review is True
    assert "STIMULANT_CAFFEINE_UNDISCLOSED_REVIEW" in result.safety_signals


def test_clean_product_returns_none() -> None:
    """No safety triggers → verdict=None, scoring continues normally."""
    from scoring_v4.gate_safety import evaluate_safety_gate
    result = evaluate_safety_gate({"contaminant_data": {}})
    assert result.verdict is None
    assert result.short_circuits_scoring is False
    assert result.blocking_reason is None
    assert result.safety_signals == []


# --- Precedence -----------------------------------------------------------


def test_blocked_beats_unsafe() -> None:
    """A product with BOTH banned + recalled hits → BLOCKED wins."""
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"name": "X", "status": "recalled", "match_type": "exact"},
                    {"name": "Y", "status": "banned", "match_type": "exact"},
                ]
            }
        }
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "BLOCKED"


def test_unsafe_beats_caution() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"name": "X", "status": "high_risk", "match_type": "exact"},
                    {"name": "Y", "status": "recalled", "match_type": "exact"},
                ]
            }
        }
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "UNSAFE"


def test_caution_beats_none() -> None:
    """Disease claim + high_risk → both CAUTION sources; verdict=CAUTION
    with both signals reported for explainability."""
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "has_disease_claims": True,
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"name": "X", "status": "watchlist", "match_type": "exact"}
                ]
            }
        },
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "CAUTION"
    assert "B0_WATCHLIST_SUBSTANCE" in result.safety_signals
    assert "DISEASE_CLAIM_DETECTED" in result.safety_signals


# --- Match-type discipline (matches v3 _evaluate_safety_gate behavior) ----


def test_non_exact_match_does_not_trigger_verdict_change() -> None:
    """v3 contract: only exact/alias matches change verdict; other
    match_types route to review-only. v4 mirrors this to avoid false
    BLOCKED on fuzzy hits."""
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"name": "Vinpocetine", "status": "banned", "match_type": "fuzzy"}
                ]
            }
        }
    }
    result = evaluate_safety_gate(product)
    assert result.verdict is None, (
        "fuzzy match should not auto-BLOCK; only exact/alias matches do"
    )
    assert result.needs_review is True


def test_alias_match_does_trigger_blocked() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"name": "Vinca minor extract", "status": "banned", "match_type": "alias"}
                ]
            }
        }
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "BLOCKED"


# --- Top-level fallback signals -------------------------------------------


def test_top_level_has_banned_substance_flag_returns_blocked() -> None:
    """Defense in depth: if contaminant_data is missing but the enricher
    set the top-level boolean, still produce BLOCKED."""
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {"has_banned_substance": True}
    result = evaluate_safety_gate(product)
    assert result.verdict == "BLOCKED"


def test_top_level_has_recalled_ingredient_flag_returns_unsafe() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    product = {"has_recalled_ingredient": True}
    result = evaluate_safety_gate(product)
    assert result.verdict == "UNSAFE"


@pytest.mark.parametrize(
    ("inactive_name", "expected_name"),
    [
        ("Brominated Vegetable Oil", "Brominated Vegetable Oil"),
        ("FD&C Red #3", "FD&C Red No. 3"),
    ],
)
def test_inactive_banned_resolver_hits_return_blocked(
    inactive_name: str,
    expected_name: str,
) -> None:
    """v4 must honor the canonical inactive resolver path used by v3/final DB.

    Real release audit caught v3 BLOCKED products becoming v4 SAFE because
    contaminant_data.banned_substances was empty while the banned inactive
    lived in inactiveIngredients. The v4 safety gate must read that canonical
    resolver signal directly instead of relying only on contaminant_data.
    """
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "contaminant_data": {
            "banned_substances": {"found": False, "substances": []}
        },
        "inactiveIngredients": [
            {
                "name": inactive_name,
                "raw_source_text": inactive_name,
                "standardName": inactive_name,
            }
        ],
    }
    result = evaluate_safety_gate(product)
    assert result.verdict == "BLOCKED"
    assert result.short_circuits_scoring is True
    assert result.blocking_reason == "banned_ingredient"
    assert expected_name in (result.matched_substance or "")


# --- Robustness -----------------------------------------------------------


def test_empty_product_returns_none_no_crash() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate
    result = evaluate_safety_gate({})
    assert result.verdict is None


def test_malformed_contaminant_data_does_not_crash() -> None:
    """Resilient to garbage shapes — never raise."""
    from scoring_v4.gate_safety import evaluate_safety_gate
    for bad in [
        {"contaminant_data": None},
        {"contaminant_data": "not a dict"},
        {"contaminant_data": {"banned_substances": None}},
        {"contaminant_data": {"banned_substances": {"substances": None}}},
        {"contaminant_data": {"banned_substances": {"substances": [None, "not a dict"]}}},
    ]:
        result = evaluate_safety_gate(bad)
        assert result.verdict is None


# --- Shadow entry-point integration ---------------------------------------


def test_shadow_entry_point_short_circuits_on_blocked() -> None:
    """When safety gate returns BLOCKED, the shadow scorer emits:
      shadow_score_v4_verdict     = 'BLOCKED'
      shadow_score_v4_100         = None
      shadow_score_v4_confidence  = 'blocked_by_safety_gate'
      shadow_score_v4_anchored    = False   (anchored is canary-set
                                             membership per §14, NOT
                                             safety-gate finality)
    No scoring math runs.

    Safety-gate finality lives in the breakdown:
      shadow_score_v4_breakdown.safety_gate.short_circuits_scoring = True"""
    from score_supplements_v4_shadow import score_product_v4_shadow
    product = {
        "supplement_type": {"type": "single_nutrient"},
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"name": "Vinpocetine", "status": "banned", "match_type": "exact"}
                ]
            }
        },
    }
    out = score_product_v4_shadow(product)
    assert out["shadow_score_v4_verdict"] == "BLOCKED"
    assert out["shadow_score_v4_100"] is None
    assert out["shadow_score_v4_confidence"] == "blocked_by_safety_gate"
    assert out["shadow_score_v4_anchored"] is False, (
        "anchored is reserved for canary-set membership per §14; "
        "safety-gate finality belongs in the breakdown"
    )
    bd = out["shadow_score_v4_breakdown"]
    assert "safety_gate" in bd
    assert bd["safety_gate"]["verdict"] == "BLOCKED"
    assert bd["safety_gate"]["short_circuits_scoring"] is True


def test_shadow_entry_point_short_circuits_on_unsafe() -> None:
    """Same anchored=False rule as BLOCKED — safety-gate finality is
    represented by confidence='blocked_by_safety_gate' + breakdown
    short_circuits_scoring=True, not by anchored."""
    from score_supplements_v4_shadow import score_product_v4_shadow
    product = {
        "supplement_type": {"type": "single_nutrient"},
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"name": "DMAA", "status": "recalled", "match_type": "exact"}
                ]
            }
        },
    }
    out = score_product_v4_shadow(product)
    assert out["shadow_score_v4_verdict"] == "UNSAFE"
    assert out["shadow_score_v4_100"] is None
    assert out["shadow_score_v4_anchored"] is False
    assert out["shadow_score_v4_confidence"] == "blocked_by_safety_gate"
    assert out["shadow_score_v4_breakdown"]["safety_gate"]["short_circuits_scoring"] is True


def test_anchored_stays_false_until_canary_membership_lands() -> None:
    """Regression for Codex's P1.1 review catch: `shadow_score_v4_anchored`
    is canary-set membership per §14, NOT safety-gate finality. Until the
    canary-lookup slice lands, every product (clean, CAUTION, UNSAFE,
    BLOCKED) emits anchored=False. The flag flips to True only when the
    product matches the §12 canary set."""
    from score_supplements_v4_shadow import score_product_v4_shadow
    cases = [
        {"supplement_type": {"type": "single_nutrient"}},  # clean
        {
            "supplement_type": {"type": "single_nutrient"},
            "contaminant_data": {
                "banned_substances": {
                    "substances": [
                        {"name": "Yohimbine", "status": "high_risk", "match_type": "exact"}
                    ]
                }
            },
        },  # CAUTION
        {
            "supplement_type": {"type": "single_nutrient"},
            "contaminant_data": {
                "banned_substances": {
                    "substances": [
                        {"name": "DMAA", "status": "recalled", "match_type": "exact"}
                    ]
                }
            },
        },  # UNSAFE
        {
            "supplement_type": {"type": "single_nutrient"},
            "contaminant_data": {
                "banned_substances": {
                    "substances": [
                        {"name": "Vinpocetine", "status": "banned", "match_type": "exact"}
                    ]
                }
            },
        },  # BLOCKED
    ]
    for p in cases:
        out = score_product_v4_shadow(p)
        assert out["shadow_score_v4_anchored"] is False, (
            f"anchored should be False (not in canary set yet) — "
            f"got True on {p}"
        )


def test_shadow_caution_continues_to_next_layer() -> None:
    """CAUTION sets the verdict but does NOT short-circuit. With a
    complete product at P1.3.6, score math runs and the CAUTION verdict
    is carried forward over the score band."""
    from score_supplements_v4_shadow import score_product_v4_shadow
    product = {
        **COMPLETE_GENERIC_PRODUCT,
        "contaminant_data": {
            "banned_substances": {
                "substances": [
                    {"name": "Yohimbine", "status": "high_risk", "match_type": "exact"}
                ]
            }
        },
    }
    out = score_product_v4_shadow(product)
    assert out["shadow_score_v4_verdict"] == "CAUTION"
    assert out["shadow_score_v4_anchored"] is False
    assert out["shadow_score_v4_confidence"] in {"high", "moderate", "low"}
    assert out["shadow_score_v4_breakdown"]["confidence"]["band"] == out["shadow_score_v4_confidence"]
    assert out["shadow_score_v4_100"] is not None


def test_shadow_clean_product_gets_score_band_verdict() -> None:
    """A clean, complete product with no safety trigger gets SAFE/POOR
    from the P1.3.6 score-band reconciliation."""
    from score_supplements_v4_shadow import score_product_v4_shadow
    out = score_product_v4_shadow(COMPLETE_GENERIC_PRODUCT)
    assert out["shadow_score_v4_verdict"] in {"SAFE", "POOR"}
    assert out["shadow_score_v4_anchored"] is False
    assert out["shadow_score_v4_confidence"] in {"high", "moderate", "low"}
    assert out["shadow_score_v4_breakdown"]["confidence"]["band"] == out["shadow_score_v4_confidence"]


# --- Architecture lock (extends the P1.0 invariant) -----------------------


def test_gate_safety_does_not_import_v3_scorer() -> None:
    """v4 must not couple to v3's _evaluate_safety_gate. Different
    policy layers — drift risk requires independence."""
    import importlib
    mod = importlib.import_module("scoring_v4.gate_safety")
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from score_supplements " not in source
    assert "import score_supplements\n" not in source
