"""v4 Omega Trust dimension — P1.6.4 tests.

Locks the Testing & Trust sub-component math:

    b4a_certifications  /10   sku and curated product_line → 10 per cert.
                              needs_review, brand_only, claimed_only,
                              rejected → 0. Cap 10. No diminishing returns.
    b4b_gmp             /4    nsf_gmp → 4. fda_registered → 2.
                              self-attested only → 0.
    b4c_traceability    /1    has_coa OR has_batch_lookup → 1.

    Hard-clamped at 15.

POLICY LOCK (per Sean 2026-05-20):
  In omega module, sku and curated product_line IFOS score 10 each.
  needs_review and brand_only stay 0 — uncertainty is NOT credit.
  Resolution happens via P1.7 curated overrides, not partial scoring.

Per §13 architecture lock — no v3 imports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


# --- Component contract --------------------------------------------------


def test_returns_normalized_payload_shape() -> None:
    from scoring_v4.modules.omega_trust import score_trust

    payload = score_trust({})
    for key in ("score", "max", "components", "penalties", "metadata"):
        assert key in payload
    assert payload["max"] == 15.0
    assert payload["metadata"]["phase"] == "P1.6.4_omega_trust"


def test_empty_product_scores_zero() -> None:
    from scoring_v4.modules.omega_trust import score_trust

    assert score_trust({})["score"] == 0.0


def test_none_input_scores_zero_safely() -> None:
    from scoring_v4.modules.omega_trust import score_trust

    assert score_trust(None)["score"] == 0.0


# --- B4a verified certifications (POLICY LOCK) ---------------------------


def test_b4a_sku_scope_awards_10_pts() -> None:
    from scoring_v4.modules.omega_trust import score_trust

    product = {"verified_cert_programs": [{"program": "IFOS", "scope": "sku"}]}
    payload = score_trust(product)
    assert payload["components"]["b4a_verified_certifications"] == 10.0


def test_b4a_product_line_scope_awards_10_pts() -> None:
    """Curated product_line overrides (from P1.7.3) score full 10."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"verified_cert_programs": [{"program": "IFOS", "scope": "product_line"}]}
    payload = score_trust(product)
    assert payload["components"]["b4a_verified_certifications"] == 10.0


def test_b4a_needs_review_scope_scores_zero() -> None:
    """POLICY LOCK: needs_review IFOS does NOT score. Sports Research case
    (327776) has IFOS at needs_review and must produce Trust 0 until
    P1.7 curated overrides convert it to product_line."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"verified_cert_programs": [{"program": "IFOS", "scope": "needs_review"}]}
    payload = score_trust(product)
    assert "b4a_verified_certifications" not in payload["components"]
    # Audit trail explicitly records why it was skipped.
    skipped = payload["metadata"]["b4a"]["B4a_skipped_entries"]
    assert any(e["scope"] == "needs_review" for e in skipped)


def test_b4a_brand_only_scope_scores_zero() -> None:
    """POLICY LOCK: brand_only IFOS does NOT score. Nordic Naturals case
    (288740) has IFOS at brand_only. Brand-level signals belong to
    Manufacturer Trust D1, not product Trust."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"verified_cert_programs": [{"program": "IFOS", "scope": "brand_only"}]}
    payload = score_trust(product)
    assert "b4a_verified_certifications" not in payload["components"]


def test_b4a_claimed_only_scope_scores_zero() -> None:
    """POLICY LOCK: claimed_only (label text without registry verification)
    does NOT score. Same discipline as P0.1b enforced."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"verified_cert_programs": [{"program": "Friend of the Sea", "scope": "claimed_only"}]}
    payload = score_trust(product)
    assert "b4a_verified_certifications" not in payload["components"]


def test_b4a_rejected_scope_scores_zero() -> None:
    """POLICY LOCK: rejected scope (P1.7.2 auto-rejects) does NOT score."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"verified_cert_programs": [{"program": "IFOS", "scope": "rejected"}]}
    payload = score_trust(product)
    assert "b4a_verified_certifications" not in payload["components"]


def test_b4a_multiple_sku_certs_cap_at_10() -> None:
    """No diminishing returns: 2 SKU certs caps at 10, not 20."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"verified_cert_programs": [
        {"program": "IFOS", "scope": "sku"},
        {"program": "NSF Sport", "scope": "sku"},
    ]}
    payload = score_trust(product)
    assert payload["components"]["b4a_verified_certifications"] == 10.0
    assert payload["metadata"]["b4a"]["B4a_cap_applied"] is True


def test_b4a_scoring_blocked_reason_skips_entry() -> None:
    """A cert entry with `scoring_blocked_reason` (e.g. stale snapshot)
    is skipped even if scope is sku."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"verified_cert_programs": [{
        "program": "IFOS", "scope": "sku",
        "scoring_blocked_reason": "snapshot_stale",
    }]}
    payload = score_trust(product)
    assert "b4a_verified_certifications" not in payload["components"]


def test_b4a_reads_certification_data_nested_path() -> None:
    """verified_cert_programs can live at root or under certification_data.
    Both shapes are accepted."""
    from scoring_v4.modules.omega_trust import score_trust

    # Nested-only shape
    product = {"certification_data": {"verified_cert_programs": [
        {"program": "IFOS", "scope": "sku"}
    ]}}
    payload = score_trust(product)
    assert payload["components"]["b4a_verified_certifications"] == 10.0


# --- B4b GMP -------------------------------------------------------------


def test_b4b_nsf_gmp_awards_4() -> None:
    """NSF/ANSI 173 audit → 4 pts (strongest GMP signal)."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"certification_data": {"gmp": {"nsf_gmp": True}}}
    payload = score_trust(product)
    assert payload["components"]["b4b_gmp"] == 4.0


def test_b4b_fda_registered_awards_2() -> None:
    """FDA registered facility → 2 pts (weaker than NSF/ANSI 173)."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"certification_data": {"gmp": {"fda_registered": True}}}
    payload = score_trust(product)
    assert payload["components"]["b4b_gmp"] == 2.0


def test_b4b_nsf_gmp_wins_over_fda_when_both_present() -> None:
    """When both flags are set, NSF/ANSI 173 takes precedence (higher tier)."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"certification_data": {"gmp": {"nsf_gmp": True, "fda_registered": True}}}
    payload = score_trust(product)
    assert payload["components"]["b4b_gmp"] == 4.0


def test_b4b_self_attested_only_scores_zero() -> None:
    """gmp.claimed=True without nsf_gmp/fda_registered → 0.
    This is STRICTER than generic_trust which credits gmp_level=certified.
    Omega rubric explicitly requires third-party-verified GMP."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"certification_data": {"gmp": {
        "claimed": True, "nsf_gmp": False, "fda_registered": False,
    }}}
    payload = score_trust(product)
    assert "b4b_gmp" not in payload["components"]
    assert payload["metadata"]["b4b"]["self_attested_only_no_credit"] is True


def test_b4b_no_gmp_data_scores_zero() -> None:
    from scoring_v4.modules.omega_trust import score_trust

    payload = score_trust({"certification_data": {}})
    assert "b4b_gmp" not in payload["components"]


# --- B4c Batch traceability ----------------------------------------------


def test_b4c_has_coa_awards_1() -> None:
    from scoring_v4.modules.omega_trust import score_trust

    product = {"certification_data": {"batch_traceability": {"has_coa": True}}}
    payload = score_trust(product)
    assert payload["components"]["b4c_batch_traceability"] == 1.0


def test_b4c_has_batch_lookup_awards_1() -> None:
    from scoring_v4.modules.omega_trust import score_trust

    product = {"certification_data": {"batch_traceability": {"has_batch_lookup": True}}}
    payload = score_trust(product)
    assert payload["components"]["b4c_batch_traceability"] == 1.0


def test_b4c_has_qr_code_counts_as_batch_lookup() -> None:
    """P1.8 nested rollup: has_qr_code counts as batch_lookup
    (the QR is the trace per the enricher hardening)."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"certification_data": {"batch_traceability": {"has_qr_code": True}}}
    payload = score_trust(product)
    assert payload["components"]["b4c_batch_traceability"] == 1.0


def test_b4c_top_level_has_coa_also_counts() -> None:
    """has_coa at root level (legacy enricher shape) also counts."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"has_coa": True}
    payload = score_trust(product)
    assert payload["components"]["b4c_batch_traceability"] == 1.0


def test_b4c_caps_at_1_when_both_coa_and_batch_present() -> None:
    """B4c caps at 1, not 2, even when both signals exist."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {"certification_data": {"batch_traceability": {
        "has_coa": True, "has_batch_lookup": True,
    }}}
    payload = score_trust(product)
    assert payload["components"]["b4c_batch_traceability"] == 1.0


def test_b4c_neither_signal_scores_zero() -> None:
    from scoring_v4.modules.omega_trust import score_trust

    product = {"certification_data": {"batch_traceability": {
        "has_coa": False, "has_batch_lookup": False, "has_qr_code": False,
    }}}
    payload = score_trust(product)
    assert "b4c_batch_traceability" not in payload["components"]


# --- Total cap + composition --------------------------------------------


def test_max_trust_score_is_15() -> None:
    """Maximum reachable: sku cert 10 + nsf_gmp 4 + coa 1 = 15."""
    from scoring_v4.modules.omega_trust import score_trust

    product = {
        "verified_cert_programs": [{"program": "IFOS", "scope": "sku"}],
        "certification_data": {
            "gmp": {"nsf_gmp": True},
            "batch_traceability": {"has_coa": True, "has_batch_lookup": True},
        },
    }
    payload = score_trust(product)
    assert payload["score"] == 15.0


def test_dimension_cap_constant() -> None:
    from scoring_v4.modules.omega_trust import score_trust, CAP_TRUST

    assert CAP_TRUST == 15.0


# --- Real-catalog canary lock -------------------------------------------


_CANARY_TRUST_IDS = {"327776", "326270", "288740", "273630", "239592", "182968"}
_CANARY_TRUST_EXPECTED = {
    # P1.7 curated IFOS overrides verified the Sports Research line.
    "327776": 10.0,
    "326270": 10.0,
    # Other anchor canaries still have only claimed_only/brand_only/unverified
    # marine cert signals and must not receive product Trust.
    "288740": 0.0,
    "273630": 0.0,
    "239592": 0.0,
    "182968": 0.0,
}
_canary_cache = None


def _load_canaries(ids):
    global _canary_cache
    if _canary_cache is not None:
        return {did: _canary_cache[did] for did in ids if did in _canary_cache}
    root = SCRIPTS_ROOT / "products"
    if not root.exists():
        _canary_cache = {}
        pytest.skip("no enriched products dir")
    found = {}
    target = _CANARY_TRUST_IDS
    for path in root.glob("output_*_enriched/enriched/enriched_cleaned_batch_*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        items = data if isinstance(data, list) else (data.get("products") or data.get("items") or [])
        for item in items:
            if not isinstance(item, dict):
                continue
            did = str(item.get("dsld_id") or item.get("id") or "")
            if did in target:
                found[did] = item
        if len(found) == len(target):
            break
    _canary_cache = found
    return {did: _canary_cache[did] for did in ids if did in _canary_cache}


@pytest.mark.parametrize("dsld_id", sorted(_CANARY_TRUST_IDS))
def test_canary_trust_matches_curated_override_state(dsld_id):
    """Anchor canary Trust reflects verified scopes only.

    P1.7 curated overrides intentionally moved Sports Research IFOS from
    needs_review to product_line. Brand-only / claimed-only marine cert
    signals still score 0; if a future triage batch verifies more rows,
    update this table deliberately.
    """
    from scoring_v4.modules.omega_trust import score_trust

    canaries = _load_canaries({dsld_id})
    if dsld_id not in canaries:
        pytest.skip(f"canary {dsld_id} not in catalog")

    payload = score_trust(canaries[dsld_id])
    expected = _CANARY_TRUST_EXPECTED[dsld_id]
    assert payload["score"] == expected, (
        f"canary {dsld_id} Trust {payload['score']} != {expected}. "
        f"Either omega rubric drifted OR P1.7 curated overrides changed. "
        f"If the latter, update _CANARY_TRUST_EXPECTED deliberately."
    )


# --- Orchestrator roll-forward ------------------------------------------


def test_omega_orchestrator_phase_rolls_forward_to_p164() -> None:
    from scoring_v4.modules.omega import score_omega

    breakdown = score_omega({"product_name": "Fish Oil",
                             "ingredient_quality_data": {"ingredients_scorable": [
                                 {"name": "EPA", "canonical_id": "epa",
                                  "quantity": 500, "unit": "mg"},
                                 {"name": "DHA", "canonical_id": "dha",
                                  "quantity": 300, "unit": "mg"},
                             ]}}).to_breakdown()
    assert breakdown["phase"].startswith("P1.6.")


def test_omega_trust_dimension_score_populated_in_breakdown() -> None:
    """After P1.6.4 lands, the trust dimension carries a numeric score."""
    from scoring_v4.modules.omega import score_omega

    product = {
        "product_name": "Fish Oil",
        "ingredient_quality_data": {"ingredients_scorable": [
            {"name": "EPA", "canonical_id": "epa", "quantity": 500, "unit": "mg"},
            {"name": "DHA", "canonical_id": "dha", "quantity": 300, "unit": "mg"},
        ]},
        "verified_cert_programs": [{"program": "IFOS", "scope": "sku"}],
    }
    breakdown = score_omega(product).to_breakdown()
    trust = breakdown["dimensions"]["trust"]
    assert trust["score"] is not None
    assert trust["score"] == 10.0


# --- Architecture lock --------------------------------------------------


def test_omega_trust_does_not_import_v3_scorer() -> None:
    import ast
    import scoring_v4.modules.omega_trust as ot

    tree = ast.parse(Path(ot.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith("score_supplements"), (
                f"v4→v3 import: from {module_name}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("score_supplements"), (
                    f"v4→v3 import: import {alias.name}"
                )


# --- Config-as-truth ----------------------------------------------------


def test_trust_policy_matches_rubric_config() -> None:
    """Code reads scope policy from omega_rubric.json — config is the
    source of truth. This test locks the precise policy values so any
    silent attempt to reintroduce partial credit for needs_review or
    brand_only fails loudly."""
    from scoring_v4.modules.omega_trust import _load_rubric

    rubric = _load_rubric()
    trust = rubric["trust"]
    policy = trust["b4a_scope_policy"]

    # POLICY LOCK — these values must never silently drift.
    assert policy["sku"] == 10
    assert policy["product_line"] == 10
    assert policy["needs_review"] == 0
    assert policy["brand_only"] == 0
    assert policy["claimed_only"] == 0
    assert policy["rejected"] == 0

    assert trust["b4a_cap"] == 10
    assert trust["dimension_cap"] == 15

    b4b = trust["b4b_gmp"]
    assert b4b["nsf_gmp"] == 4
    assert b4b["fda_registered"] == 2
    assert b4b["self_attested_only"] == 0
    assert b4b["cap"] == 4

    b4c = trust["b4c_traceability"]
    assert b4c["score_if_present"] == 1
    assert b4c["cap"] == 1
