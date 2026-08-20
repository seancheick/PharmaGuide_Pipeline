"""Clean-label policy registry, resolver overlay, and score projection.

The clean-label layer is a separate, jurisdiction-explicit registry. Active,
source-complete entries may INFORM + apply a small graduated penalty WITHOUT
forcing a safety verdict. Review-required inventory rows remain inert.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _clean_label_registry() -> dict:
    return json.loads(
        (SCRIPTS_ROOT / "data" / "clean_label_policy.json").read_text(
            encoding="utf-8"
        )
    )


def test_clean_label_registry_is_separate_and_fail_closed() -> None:
    registry = _clean_label_registry()
    policies = registry["policies"]
    active = [row for row in policies if row.get("policy_status") == "active"]
    candidates = [
        row for row in policies if row.get("policy_status") == "review_required"
    ]

    assert registry["_metadata"]["total_entries"] == len(policies)
    assert [row["id"] for row in active] == ["CL_TITANIUM_DIOXIDE_E171"]
    assert {
        "CL_CANDIDATE_ARTIFICIAL_COLORS",
        "CL_CANDIDATE_BHA_BHT",
        "CL_CANDIDATE_PARABENS",
        "CL_CANDIDATE_AZODICARBONAMIDE",
    } <= {row["id"] for row in candidates}
    for row in candidates:
        assert row.get("consumer_note") is None
        assert row.get("penalty_base") is None
        assert set(row.get("missing_requirements") or []) == {
            "jurisdiction",
            "authoritative_evidence",
            "penalty",
            "consumer_copy",
        }


def test_active_clean_label_policy_is_source_complete() -> None:
    policy = next(
        row
        for row in _clean_label_registry()["policies"]
        if row["id"] == "CL_TITANIUM_DIOXIDE_E171"
    )

    assert policy["jurisdiction"] == "EU"
    assert policy["jurisdiction_status"] == "banned_food_additive"
    assert policy["consumer_note"]
    assert policy["penalty_base"] > 0
    assert policy["penalty_rationale"]
    assert policy["policy_basis"]
    assert policy["authoritative_source"]["url"].startswith("https://eur-lex.europa.eu/")


def test_banned_registry_no_longer_owns_clean_label_policy() -> None:
    banned = json.loads(
        (SCRIPTS_ROOT / "data" / "banned_recalled_ingredients.json").read_text(
            encoding="utf-8"
        )
    )
    titanium = next(
        row for row in banned["ingredients"]
        if row["id"] == "BANNED_ADD_TITANIUM_DIOXIDE"
    )
    assert not any("clean_label" in row for row in banned["ingredients"])
    assert titanium["clean_label_policy_id"] == "CL_TITANIUM_DIOXIDE_E171"


def test_incomplete_active_policy_fails_closed(tmp_path: Path) -> None:
    from inactive_ingredient_resolver import InactiveIngredientResolver

    policy_path = tmp_path / "clean_label_policy.json"
    policy_path.write_text(json.dumps({
        "policies": [{
            "id": "CL_INCOMPLETE",
            "standard_name": "Microcrystalline Cellulose",
            "aliases": ["microcrystalline cellulose"],
            "policy_status": "active",
            "jurisdiction": "US",
            "jurisdiction_status": "reviewed",
            "policy_basis": "Missing source, copy, and penalty on purpose.",
            "tier": "informational",
        }],
    }), encoding="utf-8")

    result = InactiveIngredientResolver(
        clean_label_policy_path=policy_path,
    ).resolve("microcrystalline cellulose")
    assert result.is_clean_label_concern is False
    assert result.clean_label_policy_id is None


def test_titanium_dioxide_carries_clean_label_disposition() -> None:
    from inactive_ingredient_resolver import InactiveIngredientResolver

    res = InactiveIngredientResolver().resolve("titanium dioxide")
    assert res.is_clean_label_concern is True
    assert res.clean_label_tier == "elevated"
    assert res.clean_label_note and "EU" in res.clean_label_note
    assert res.clean_label_penalty_base == 2.0
    assert res.clean_label_policy_id == "CL_TITANIUM_DIOXIDE_E171"
    assert res.clean_label_jurisdiction == "EU"
    assert res.clean_label_jurisdiction_status == "banned_food_additive"
    assert "2022/63" in (res.clean_label_policy_basis or "")


def test_review_candidates_are_inert_until_policy_completion() -> None:
    from inactive_ingredient_resolver import InactiveIngredientResolver

    resolver = InactiveIngredientResolver()
    for label in ("BHA", "BHT", "propylparaben", "FD&C Yellow 6"):
        result = resolver.resolve(label)
        assert result.is_clean_label_concern is False, label
        assert result.clean_label_policy_id is None, label


def test_clean_label_is_orthogonal_to_safety_contract() -> None:
    # The disposition must not be created out of thin air for non-flagged entries,
    # and must not flip the safety contract for titanium dioxide (its excipient_
    # acceptable policy keeps the gate at "warning only" — no verdict change here).
    from inactive_ingredient_resolver import InactiveIngredientResolver

    r = InactiveIngredientResolver()
    # A banned entry WITHOUT a clean_label block → no clean-label disposition.
    cascara = r.resolve("cascara sagrada")
    assert cascara.is_clean_label_concern is False
    assert cascara.clean_label_tier is None


def test_default_resolution_has_no_clean_label() -> None:
    from inactive_ingredient_resolver import InactiveIngredientResolver

    res = InactiveIngredientResolver().resolve("microcrystalline cellulose")
    assert res.is_clean_label_concern is False
    assert res.clean_label_penalty_base is None


# ---------------------------------------------------------------------------
# STEP 2: the safety gate collects clean_label_hits WITHOUT touching the
# verdict. A clean-label additive (titanium dioxide coating) must surface a
# hit AND keep the verdict SAFE (no CAUTION). The clean-label lane and the
# safety-verdict lane are independent.
# ---------------------------------------------------------------------------


def test_gate_collects_titanium_dioxide_clean_label_hit() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "TEST",
        "fullName": "Coated tablet with titanium dioxide",
        "inactiveIngredients": [{"name": "titanium dioxide"}],
    }
    result = evaluate_safety_gate(product)
    hits = result.clean_label_hits
    assert hits, "titanium dioxide must surface as a clean-label hit"
    hit = next((h for h in hits if "titanium" in str(h.get("name", "")).lower()), None)
    assert hit is not None, f"no titanium hit in {hits!r}"
    assert hit["tier"] == "elevated"
    assert hit["penalty_base"] == 2.0
    assert hit["role"] == "inactive"
    assert hit.get("consumer_note") and "EU" in hit["consumer_note"]
    assert hit["policy_id"] == "CL_TITANIUM_DIOXIDE_E171"
    assert hit["jurisdiction"] == "EU"
    assert hit["jurisdiction_status"] == "banned_food_additive"
    assert "2022/63" in hit["policy_basis"]


def test_gate_clean_label_does_not_force_caution() -> None:
    # An excipient_acceptable coating must inform, never force CAUTION.
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "TEST",
        "fullName": "x",
        "inactiveIngredients": [{"name": "titanium dioxide"}],
    }
    result = evaluate_safety_gate(product)
    assert result.verdict != "CAUTION", "clean-label hit must not force CAUTION"
    assert result.short_circuits_scoring is False


def test_gate_no_clean_label_hit_when_absent() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "TEST",
        "fullName": "clean product",
        "inactiveIngredients": [{"name": "microcrystalline cellulose"}],
    }
    result = evaluate_safety_gate(product)
    assert result.clean_label_hits == []


def test_gate_eu_only_policy_stays_advisory_without_clean_label_hit() -> None:
    # Regional policy and clean-label policy are independent. An EU-only rule
    # is retained as an advisory and does not become a US CAUTION verdict.
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {
        "dsld_id": "TEST",
        "fullName": "x",
        "inactiveIngredients": [{"name": "propylparaben"}],
    }
    result = evaluate_safety_gate(product)
    assert result.verdict is None
    assert "B0_REGIONAL_ADVISORY" in result.safety_signals
    assert result.clean_label_hits == []


def test_safety_gate_breakdown_carries_clean_label_hits() -> None:
    """The v4 scorer must serialize clean_label_hits into the breakdown so
    the six-pillar quality_score can consume them."""
    from score_supplements_v4 import _safety_gate_breakdown
    from scoring_v4.gate_safety import evaluate_safety_gate

    result = evaluate_safety_gate({
        "dsld_id": "TEST", "fullName": "x",
        "inactiveIngredients": [{"name": "titanium dioxide"}],
    })
    bd = _safety_gate_breakdown(result)
    assert "clean_label_hits" in bd
    assert any("titanium" in str(h.get("name", "")).lower() for h in bd["clean_label_hits"])


# ---------------------------------------------------------------------------
# STEP 3a: quality_score applies a GRADUATED safety_hygiene penalty from
# clean_label_hits and emits clean_label_flags_v4. Raw is never touched.
# penalty = penalty_base (data) × role_multiplier (config), clamped.
# ---------------------------------------------------------------------------

TI_HIT = {
    "name": "Titanium Dioxide (E171)",
    "standard_name": "titanium dioxide",
    "role": "inactive",
    "tier": "elevated",
    "consumer_note": "Contains titanium dioxide (E171) — banned as a food additive in the EU.",
    "penalty_base": 2.0,
    "status": "high_risk",
    "policy_id": "CL_TITANIUM_DIOXIDE_E171",
    "jurisdiction": "EU",
    "jurisdiction_status": "banned_food_additive",
    "policy_basis": "Commission Regulation (EU) 2022/63 removed E171 from the permitted list.",
}


def _shadow_for_quality(clean_label_hits, *, hygiene=4, hygiene_max=4,
                        raw=70.0, verdict="SAFE", module="generic"):
    bd = {
        "dimensions": {
            "formulation": {"score": 18, "max": 30},
            "dose": {"score": 18, "max": 25},
            "evidence": {"score": 14, "max": 20},
            "transparency": {"score": 10, "max": 10},
        },
        "verification_bonus": {"score": 4, "max": 8},
        "manufacturer_trust": {"score": 3, "max": 5},
        "safety_hygiene_base": {"score": hygiene, "max": hygiene_max},
    }
    return {
        "raw_score_v4_100": raw,
        "v4_verdict": verdict,
        "v4_module": module,
        "v4_breakdown": {
            "module": bd,
            "safety_gate": {"clean_label_hits": list(clean_label_hits)},
        },
    }


def _expected_penalty(hit):
    from scoring_v4.quality_score import _config
    mult = _config()["clean_label_subscale"]["role_multiplier"]
    return round(hit["penalty_base"] * mult[hit["role"]], 1)


def test_quality_titanium_dioxide_penalizes_safety_hygiene() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    base = assemble_quality_score(_shadow_for_quality([]))
    pen = assemble_quality_score(_shadow_for_quality([TI_HIT]))
    b = base["quality_pillars_v4"]["safety_hygiene"]["score"]
    p = pen["quality_pillars_v4"]["safety_hygiene"]["score"]
    exp = _expected_penalty(TI_HIT)
    assert exp > 0, "titanium dioxide must carry a non-zero penalty"
    assert round(b - p, 1) == exp, f"expected −{exp} on safety_hygiene, got {b}→{p}"


def test_quality_clean_label_lowers_total_but_not_raw() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    base = assemble_quality_score(_shadow_for_quality([]))
    pen = assemble_quality_score(_shadow_for_quality([TI_HIT]))
    assert pen["quality_score_v4_100"] < base["quality_score_v4_100"]
    # raw is byte-identical
    assert pen["raw_score_v4_100"] == 70.0
    assert pen["raw_score_v4_100"] == 70.0


def test_quality_no_clean_label_hits_no_penalty_no_flags() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    out = assemble_quality_score(_shadow_for_quality([]))
    assert out["quality_pillars_v4"]["safety_hygiene"]["score"] == 10.0
    assert out.get("clean_label_flags_v4") in (None, [])


def test_quality_emits_clean_label_flags() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    out = assemble_quality_score(_shadow_for_quality([TI_HIT]))
    flags = out["clean_label_flags_v4"]
    assert flags, "expected a clean_label_flags_v4 list"
    f = flags[0]
    assert f["tier"] == "elevated"
    assert "titanium" in f["additive"].lower()
    assert f.get("consumer_note") and "EU" in f["consumer_note"]
    assert f["penalty_applied"] == _expected_penalty(TI_HIT)
    assert f["role"] == "inactive"
    assert f["policy_id"] == "CL_TITANIUM_DIOXIDE_E171"
    assert f["jurisdiction"] == "EU"
    assert f["jurisdiction_status"] == "banned_food_additive"
    assert "2022/63" in f["policy_basis"]


def test_quality_clean_label_role_active_penalizes_more() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    inactive = dict(TI_HIT, role="inactive")
    active = dict(TI_HIT, role="active")
    p_inact = assemble_quality_score(_shadow_for_quality([inactive]))["quality_pillars_v4"]["safety_hygiene"]["score"]
    p_act = assemble_quality_score(_shadow_for_quality([active]))["quality_pillars_v4"]["safety_hygiene"]["score"]
    assert p_act < p_inact, "an active flagged additive must be penalized harder than a coating"


def test_quality_clean_label_penalty_clamped_at_zero() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    huge = [dict(TI_HIT, penalty_base=50.0, role="active") for _ in range(5)]
    out = assemble_quality_score(_shadow_for_quality(huge))
    assert out["quality_pillars_v4"]["safety_hygiene"]["score"] >= 0.0


def test_quality_suppressed_safety_still_emits_clean_label_flags() -> None:
    """A hard safety verdict suppresses the quality score, but it should not drop
    the consumer-facing clean-label note. Suppression and "inform" are separate."""
    from scoring_v4.quality_score import assemble_quality_score

    out = assemble_quality_score(_shadow_for_quality([TI_HIT], raw=None, verdict="BLOCKED"))

    assert out["quality_score_status"] == "suppressed_safety"
    assert out["quality_score_v4_100"] is None
    assert out["clean_label_flags_v4"], "suppressed rows should still carry clean-label flags"
    assert out["clean_label_flags_v4"][0]["penalty_applied"] == _expected_penalty(TI_HIT)


# ---------------------------------------------------------------------------
# STEP 3b: the clean-label flag carries the STRUCTURED, clickable regulation
# citation (surfaced from the entry's already-verified references — no new
# claims), so the consumer "inform" half meets the clinical-citation rule.
# ---------------------------------------------------------------------------


def test_resolver_titanium_dioxide_carries_structured_citation() -> None:
    from inactive_ingredient_resolver import InactiveIngredientResolver

    res = InactiveIngredientResolver().resolve("titanium dioxide")
    assert res.clean_label_citation and "2022/63" in res.clean_label_citation
    assert res.clean_label_url and "eur-lex" in res.clean_label_url.lower()
    assert res.clean_label_eu_status  # short machine-readable status, e.g. "banned_food_additive"


def test_gate_clean_label_hit_carries_citation() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = {"dsld_id": "T", "fullName": "x",
               "inactiveIngredients": [{"name": "titanium dioxide"}]}
    hit = evaluate_safety_gate(product).clean_label_hits[0]
    assert "2022/63" in (hit.get("regulation_citation") or "")
    assert "eur-lex" in (hit.get("regulation_url") or "").lower()
    assert hit.get("eu_status")


def test_quality_flag_emits_structured_citation() -> None:
    from scoring_v4.quality_score import assemble_quality_score

    hit = dict(
        TI_HIT,
        regulation_citation="Commission Regulation (EU) 2022/63",
        regulation_url="https://eur-lex.europa.eu/eli/reg/2022/63/oj/eng",
        eu_status="banned_food_additive",
    )
    out = assemble_quality_score(_shadow_for_quality([hit]))
    f = out["clean_label_flags_v4"][0]
    assert "2022/63" in f["regulation_citation"]
    assert "eur-lex" in f["regulation_url"].lower()
    assert f["eu_status"] == "banned_food_additive"


def test_quality_flag_citation_null_when_absent() -> None:
    # A clean-label hit WITHOUT citation fields must still emit a flag, with
    # citation keys present but null (stable Flutter contract).
    from scoring_v4.quality_score import assemble_quality_score

    out = assemble_quality_score(_shadow_for_quality([TI_HIT]))  # TI_HIT has no citation
    f = out["clean_label_flags_v4"][0]
    assert "regulation_citation" in f and f["regulation_citation"] is None
    assert "regulation_url" in f and f["regulation_url"] is None
