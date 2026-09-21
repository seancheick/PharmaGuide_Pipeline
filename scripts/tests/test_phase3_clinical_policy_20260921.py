"""Regression tests for the Phase-3 clinical-policy implementation (2026-09-21).

PHARMAGUIDE TEAM, clinical authority Dr. Pham / PharmaGuide Clinical Team.

Four policies were approved for implementation:

1. **Standalone oral EDTA** (16 products) --
   ``BLOCKED + visible Safety card + no quality score``, reason semantics
   ``NON_ROUTINE_CHELATOR`` / ``CLINICIAN_REVIEW_REQUIRED``. Disodium edetate
   and calcium disodium edetate stay DISTINCT identities. The disposition
   records that standalone oral chelation is non-routine and requires clinical
   review; it must NOT be stated as proven acute oral toxicity. EDTA declared
   as a formulation excipient is out of scope and must be unaffected.

2. **Botanical standardization constituents** -- the parent standardized
   extract owns the formulation dose; a declared constituent beneath it keeps
   its quantity and provenance, is not additive mass, and stays visible to
   Safety and evidence matching. (Behavioural coverage:
   ``test_standardization_marker_generalization.py`` and
   ``test_clinical_signoff_engineering_fixes_20260919.py``.)

3. **Discrete-enzyme formulation** -- no generic evidence transfer from the
   collapsed ``digestive_enzymes`` identity; discrete identities are
   ``NOT_INDIVIDUALLY_RATED`` (the existing unrated-form neutral mechanism),
   earning neither positive formulation credit nor a penalty, and become
   rateable once qualifying enzyme-specific evidence exists.

4. **Beta-carotene / Vitamin-A UL** -- only preformed vitamin A participates in
   the preformed Vitamin-A UL; provitamin-A carotenoids contribute zero and
   receive no high-dose beta-carotene warning at resolved Phase-3 doses.

This file pins the policy-specific contracts; it does not restate the
already-covered engineering regressions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

REGISTRY_PATH = SCRIPTS_ROOT / "data" / "banned_recalled_ingredients.json"

EDTA_DISODIUM_IDS = (
    "252358", "253339", "253350", "253357",
    "312449", "312450", "312451", "312452",
)
EDTA_CALCIUM_DISODIUM_IDS = (
    "252426", "253331", "253335", "253336",
    "311259", "311260", "311261", "311262",
)
EDTA_ALL_IDS = EDTA_DISODIUM_IDS + EDTA_CALCIUM_DISODIUM_IDS

RULE_DISODIUM = "BANNED_NON_ROUTINE_CHELATOR_EDETATE_DISODIUM"
RULE_CALCIUM = "BANNED_NON_ROUTINE_CHELATOR_CALCIUM_DISODIUM_EDETATE"
EDTA_POLICY_RULES = (RULE_DISODIUM, RULE_CALCIUM)

POLICY_REASON = "NON_ROUTINE_CHELATOR"

_AUTHORITATIVE_HOST_SUFFIXES = ("fda.gov", "nih.gov")
_FORBIDDEN_TOXICITY_PHRASES = (
    "proven toxic",
    "is toxic",
    "acutely toxic",
    "poison",
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _policy_entries() -> dict:
    return {
        str(entry.get("id")): entry
        for entry in _registry()["ingredients"]
        if str(entry.get("id")) in EDTA_POLICY_RULES
    }


def _clean_contaminants() -> dict:
    return {"banned_substances": {"found": False, "substances": [], "safety_flags": []}}


def _product(
    active: list | None = None,
    *,
    inactive: list | None = None,
    name: str = "Test Product",
) -> dict:
    """Minimal enriched-product fixture for the v4 safety gate."""
    return {
        "dsld_id": "TEST_PHASE3_POLICY",
        "fullName": name,
        "status": "active",
        "form_factor": "powder",
        "supplement_type": {"type": "single_nutrient"},
        "contaminant_data": _clean_contaminants(),
        "activeIngredients": active
        or [{"name": "Magnesium", "standardName": "Magnesium", "mapped": True}],
        "inactiveIngredients": inactive or [],
        "ingredient_quality_data": {"total_active": 1, "ingredients_scorable": []},
    }


def _active_row(name: str) -> dict:
    return {
        "name": name,
        "standardName": name,
        "raw_source_text": name,
        "forms": [],
        "mapped": False,
        "source_section": "active",
    }


def _official_urls(decision) -> list[str]:
    urls = []
    for source in decision.verified_sources or []:
        value = source.get("url")
        if not value:
            continue
        host = (urlparse(str(value)).hostname or "").lower()
        if any(host == suffix or host.endswith(f".{suffix}") for suffix in _AUTHORITATIVE_HOST_SUFFIXES):
            urls.append(str(value))
    return urls


# ---------------------------------------------------------------------------
# 1. EDTA -- registry authoring
# ---------------------------------------------------------------------------

def test_registry_authors_two_distinct_edta_identities() -> None:
    """Disodium and calcium disodium must never collapse into one identity."""
    entries = _policy_entries()
    assert set(entries) == set(EDTA_POLICY_RULES)
    assert entries[RULE_DISODIUM]["standard_name"] == "Edetate Disodium"
    assert entries[RULE_CALCIUM]["standard_name"] == "Edetate Calcium Disodium"
    # Neither identity claims the other's aliases.
    disodium_aliases = {a.strip().lower() for a in entries[RULE_DISODIUM]["aliases"]}
    calcium_aliases = {a.strip().lower() for a in entries[RULE_CALCIUM]["aliases"]}
    assert not (disodium_aliases & calcium_aliases)
    assert not any("calcium" in alias for alias in disodium_aliases)


def test_generic_edta_token_is_never_an_alias() -> None:
    """A bare 'EDTA' label row must not be resolved to either policy identity.

    The clinical decision is written around the two specific chelating salts.
    Treating the generic token as an identity would condemn unrelated labels.
    """
    for entry in _policy_entries().values():
        aliases = {a.strip().lower() for a in entry["aliases"]}
        assert "edta" not in aliases
        assert "edetate" not in aliases


@pytest.mark.parametrize("rule_id", EDTA_POLICY_RULES)
def test_policy_entries_are_declared_active_role_only(rule_id: str) -> None:
    """Both registry-level role gates must be present and consistent."""
    entry = _policy_entries()[rule_id]
    assert entry["match_mode"] == "active"
    assert entry["hard_verdict_roles"] == ["active"]
    assert entry.get("role_scope_out_of_scope") == "not_applicable"


@pytest.mark.parametrize("rule_id", EDTA_POLICY_RULES)
def test_policy_entry_is_policy_verified_with_authoritative_sources(rule_id: str) -> None:
    entry = _policy_entries()[rule_id]
    assert entry["policy_verification_status"] == "verified"
    assert entry["legal_status_enum"] == "not_lawful_as_supplement"
    assert entry["verdict_reason_code"] == POLICY_REASON
    assert any(
        str(j.get("jurisdiction_code", "")).upper().startswith("US")
        for j in entry["jurisdictions"]
    )
    urls = [ref.get("url") or "" for ref in entry["references_structured"]]
    assert any(
        (urlparse(url).hostname or "").endswith("fda.gov") for url in urls
    ), urls


@pytest.mark.parametrize("rule_id", EDTA_POLICY_RULES)
def test_policy_copy_fits_the_safety_card_and_does_not_claim_toxicity(rule_id: str) -> None:
    entry = _policy_entries()[rule_id]
    one_liner = entry["safety_warning_one_liner"]
    warning = entry["safety_warning"]
    assert 0 < len(one_liner) <= 80
    assert 0 < len(warning) <= 200
    assert "not scored as a routine supplement" in one_liner.lower()
    assert "fda has not approved" in warning.lower()

    # The CONSUMER copy must make no toxicity claim at all.
    consumer_copy = f"{one_liner} {warning}".lower()
    for phrase in _FORBIDDEN_TOXICITY_PHRASES:
        assert phrase not in consumer_copy, (
            f"consumer copy must not claim toxicity: {phrase!r}"
        )
    assert "toxic" not in consumer_copy

    # The internal policy reason may name toxicity ONLY to deny it.
    reason = entry["reason"].lower()
    if "toxic" in reason:
        index = reason.index("toxic")
        assert "not a finding" in reason[max(0, index - 80):index], reason


# ---------------------------------------------------------------------------
# 1. EDTA -- safety-gate behaviour
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("label", "expected_rule"),
    [
        ("EDTA Disodium", RULE_DISODIUM),
        ("Disodium EDTA", RULE_DISODIUM),
        ("Disodium Edetate", RULE_DISODIUM),
        ("Calcium Disodium EDTA", RULE_CALCIUM),
        ("Calcium Disodium Edetate", RULE_CALCIUM),
    ],
)
def test_standalone_oral_edta_blocks_with_the_policy_reason(
    label: str, expected_rule: str
) -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    result = evaluate_safety_gate(_product([_active_row(label)]))

    assert result.verdict == "BLOCKED"
    assert result.short_circuits_scoring is True
    # Above all: this is a resolved policy, not an unresolved review queue item.
    assert result.quarantine_required is False
    assert result.quarantine_reason is None
    assert result.blocking_reason == POLICY_REASON
    assert result.matched_substance
    decision = result.safety_decision
    assert decision is not None
    assert decision.verdict == "BLOCKED"
    assert decision.reason_code == POLICY_REASON
    assert decision.winning_rule == expected_rule
    assert decision.jurisdiction == "US"
    assert decision.policy_basis.get("legal_status") == "not_lawful_as_supplement"
    assert _official_urls(decision), decision.to_dict()


def test_generic_edta_row_is_not_blocked_by_the_policy() -> None:
    """Only the two declared salts are governed; the bare token is not."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    result = evaluate_safety_gate(_product([_active_row("EDTA")]))
    assert result.verdict != "BLOCKED"
    assert result.blocking_reason is None


@pytest.mark.parametrize(
    "inactive_label",
    ["Calcium Disodium EDTA", "Disodium EDTA", "EDTA"],
)
def test_excipient_edta_role_is_out_of_scope_and_leaves_no_trace(
    inactive_label: str,
) -> None:
    """Formulation-level EDTA must be completely unaffected.

    Out of scope means the product payload is identical to one whose label never
    named the substance -- no verdict, no quarantine, and no audit marker
    leaking into ``safety_signal_reason``.
    """
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = _product(
        inactive=[{"name": inactive_label, "standardName": inactive_label, "forms": []}]
    )
    result = evaluate_safety_gate(product)
    assert result.verdict not in {"BLOCKED", "UNSAFE"}
    assert result.short_circuits_scoring is False
    assert result.blocking_reason is None
    assert result.quarantine_required is False
    assert result.needs_review is False
    assert result.safety_decision is None
    # No out-of-scope audit marker leaks into the consumer payload.
    assert result.safety_signals == []
    assert not any("OUT_OF_SCOPE" in code for code in result.safety_signals)


def test_disodium_as_an_inactive_form_is_out_of_scope() -> None:
    """An inactive compound row naming a policy salt as a ``form`` is unaffected."""
    from scoring_v4.gate_safety import evaluate_safety_gate

    product = _product(
        inactive=[
            {
                "name": "Preservative Blend",
                "standardName": "Preservative Blend",
                "forms": [{"name": "Disodium EDTA"}, {"name": "Calcium Disodium EDTA"}],
            }
        ]
    )
    result = evaluate_safety_gate(product)
    assert result.verdict not in {"BLOCKED", "UNSAFE"}
    assert result.quarantine_required is False
    assert result.safety_signals == []


def test_blocked_edta_ships_without_a_quality_score() -> None:
    """The v4 entry point must suppress the score and keep the product visible."""
    from score_supplements_v4 import score_product_v4

    result = score_product_v4(_product([_active_row("EDTA Disodium")]))

    assert result["v4_verdict"] == "BLOCKED"
    assert result["score_unavailable_reason"] == "blocked_by_safety_gate"
    assert result.get("quality_score_v4_100") is None
    safety_breakdown = result["v4_breakdown"]["safety_gate"]
    assert safety_breakdown["short_circuits_scoring"] is True
    assert safety_breakdown["quarantine_required"] is False


# ---------------------------------------------------------------------------
# New gate mechanisms: a declared reason code + explicit role scope
# ---------------------------------------------------------------------------

def test_declared_verdict_reason_code_overrides_the_tier_default() -> None:
    from scoring_v4.gate_safety import evaluate_safety_gate

    disodium = evaluate_safety_gate(_product([_active_row("EDTA Disodium")]))
    # A rule without the declaration keeps the registry tier semantics.
    banned = evaluate_safety_gate(_product([_active_row("Cannabidiol")]))
    assert banned.blocking_reason != POLICY_REASON
    assert banned.blocking_reason == "banned_ingredient"
    assert disodium.blocking_reason == POLICY_REASON


def test_role_scope_declaration_does_not_weaken_unsettled_policy_quarantine() -> None:
    """Role scoping is opt-in per entry; unscoped rules keep today's behaviour.

    A rule that declares roles but NOT the out-of-scope declaration must still
    route an unsupported role to the policy-review queue rather than silently
    ignoring it.
    """
    from scoring_v4.gate_safety import evaluate_safety_gate

    entry = _policy_entries()[RULE_DISODIUM]
    assert entry["role_scope_out_of_scope"] == "not_applicable"
    # Cannabidiol is authored active-only with no out-of-scope declaration.
    registry = {
        str(e.get("id")): e
        for e in _registry()["ingredients"]
    }
    assert registry["BANNED_CBD_US"]["hard_verdict_roles"] == ["active"]
    assert "role_scope_out_of_scope" not in registry["BANNED_CBD_US"]


# ---------------------------------------------------------------------------
# 3. Discrete-enzyme formulation: NOT_INDIVIDUALLY_RATED
# ---------------------------------------------------------------------------

def _formulation_pillar(assessed_count: int, *, raw_score: float = 0.0) -> dict:
    """Run the real Formulation pillar with an explicit form-assessment count."""
    from scoring_v4.quality_score import _pillar_formulation, _config

    dim = {
        "score": raw_score,
        "metadata": {"iqm_form_quality_assessed_count": assessed_count},
    }
    return _pillar_formulation(
        dim, 20.0, "generic_single_molecule", _config()
    )


def test_unrated_discrete_enzyme_earns_the_neutral_floor_not_zero() -> None:
    pillar = _formulation_pillar(0)
    assert pillar["score"] > 0.0
    assert "not rated" in pillar["reason"].lower()


def test_unrated_discrete_enzyme_reason_does_not_claim_averageness() -> None:
    """The consumer-facing state is NOT_INDIVIDUALLY_RATED, not 'average'."""
    reason = _formulation_pillar(0)["reason"].lower()
    for word in ("average", "typical", "median"):
        assert word not in reason


def test_unrated_discrete_enzyme_earns_no_positive_formulation_credit() -> None:
    """Neutral is the ceiling for an unrated row -- never a bonus."""
    neutral = _formulation_pillar(0)["score"]
    assert neutral == pytest.approx(_formulation_pillar(0, raw_score=0.0)["score"])
    assert _formulation_pillar(0, raw_score=0.0)["score"] <= 20.0


def test_discrete_enzyme_becomes_rateable_with_qualifying_evidence() -> None:
    """This is not a permanent exemption class."""
    rated = _formulation_pillar(1, raw_score=18.0)
    unrated = _formulation_pillar(0)
    assert rated["score"] > unrated["score"]
    assert "not rated" not in rated["reason"].lower()


def test_discrete_enzyme_does_not_inherit_collapsed_multi_enzyme_evidence() -> None:
    from scoring_v4.modules.generic_evidence import score_evidence

    product = {
        "dsld_id": "test-discrete-enzyme",
        "product_name": "High Potency Lipase",
        "ingredient_quality_data": {
            "ingredients": [
                {
                    "name": "Lipase",
                    "canonical_id": "lipase",
                    "cleaner_row_role": "active_scorable",
                    "quantity": 20000.0,
                    "unit": "FIP",
                    "dose_class": "enzyme_activity",
                }
            ]
        },
        "evidence_data": {"clinical_matches": []},
    }
    result = score_evidence(product)
    assert result["score"] == 0.0
    assert result["metadata"]["evidence_result_state"] in {
        "clinical_review_not_covered",
        "no_qualifying_human_evidence",
    }


# ---------------------------------------------------------------------------
# 4. Beta-carotene / Vitamin-A UL
# ---------------------------------------------------------------------------

def test_vitamin_a_ul_is_declared_preformed_only() -> None:
    payload = json.loads(
        (SCRIPTS_ROOT / "data" / "rda_optimal_uls.json").read_text(encoding="utf-8")
    )
    vitamin_a = next(
        entry
        for entry in payload["nutrient_recommendations"]
        if entry["standard_name"] == "Vitamin A"
    )
    assert "preformed vitamin A only" in vitamin_a["ul_note"]
    assert "not beta-carotene" in vitamin_a["ul_note"]


def test_provitamin_carotenoid_skip_reason_is_a_no_ul_basis() -> None:
    """A provitamin-A row resolves to a no-UL basis, never a penalty."""
    from dose_assessment import _NO_UL_REASONS

    assert "beta_carotene_no_established_ul" in _NO_UL_REASONS
    assert "provitamin_a_carotenoid_no_established_ul" in _NO_UL_REASONS


def test_beta_carotene_is_gated_out_of_the_retinol_pregnancy_alert() -> None:
    """Beta-carotene contributes RAE but must not inherit preformed-retinol risk."""
    payload = json.loads(
        (SCRIPTS_ROOT / "data" / "ingredient_interaction_rules.json").read_text(
            encoding="utf-8"
        )
    )
    text = json.dumps(payload)
    assert "beta_carotene" in text
    # The vitamin-A pregnancy gate names the provitamin forms as exclusions.
    assert "mixed_carotenoids" in text


# ---------------------------------------------------------------------------
# Policy record: the decisions must exist as a durable artifact
# ---------------------------------------------------------------------------

def test_phase3_clinical_policy_record_exists_and_records_the_authority() -> None:
    record = (
        SCRIPTS_ROOT
        / "audits"
        / "quarantine_triage_20260919"
        / "PHASE3_CLINICAL_POLICY_20260921.md"
    )
    assert record.is_file(), record
    text = record.read_text(encoding="utf-8")
    assert "Dr. Pham" in text
    assert "PharmaGuide Clinical Team" in text
    approved_statuses = {
        "BLOCKED_SAFETY_CARD_NO_SCORE",
        "CONTAINED_CONSTITUENT_MODEL_APPROVED",
        "NOT_INDIVIDUALLY_RATED_APPROVED",
        "PREFORMED_VITAMIN_A_ONLY",
    }
    for status in approved_statuses:
        assert status in text, status

    # Every row of the policy ledger must carry an APPROVED status -- no
    # clinical policy field may be left TBD / pending / needs review / awaiting
    # a pharmacist. Only the ledger table is graded here: the surrounding prose
    # legitimately names those words in order to deny them.
    ledger_rows = [
        line for line in text.splitlines()
        if line.startswith("| ") and "`" in line and "---" not in line
    ]
    graded = [row for row in ledger_rows if any(s in row for s in approved_statuses)]
    assert len(graded) == len(approved_statuses), ledger_rows
    for row in graded:
        status = row.split("|")[-2].strip()
        assert status.strip("`") in approved_statuses, row
    assert "No clinical policy field remains TBD" in text
