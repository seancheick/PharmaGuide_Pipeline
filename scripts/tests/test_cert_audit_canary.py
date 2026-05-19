"""Smoke test for the P0.1a cert audit pipeline.

End-to-end check:
  1. Registry loads (cert_registry.json exists and parses)
  2. Resolver behaves on the 3 catalog-anchored canary products
  3. Audit-report column shape is consistent
  4. The cert overcredit bug is detected (at least some products demote
     under v4 — proves the audit is producing actionable signal)

Skipped if the registry hasn't been populated yet (CI-safe).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from cert_resolver import CertRegistry, resolve  # noqa: E402

REGISTRY_PATH = SCRIPTS_ROOT / "data" / "cert_registry.json"
CORE_DB = SCRIPTS_ROOT / "final_db_output" / "pharmaguide_core.db"


def _registry_has_data() -> bool:
    if not REGISTRY_PATH.exists():
        return False
    with open(REGISTRY_PATH) as f:
        d = json.load(f)
    return d.get("_metadata", {}).get("total_verified_records", 0) > 0


pytestmark = pytest.mark.skipif(
    not _registry_has_data(),
    reason="cert_registry.json not populated. Run scripts/api_audit/verify_certifications.py first.",
)


@pytest.fixture(scope="module")
def registry() -> CertRegistry:
    return CertRegistry.load()


# --- Registry shape ---------------------------------------------------------


def test_registry_has_nsf_sport_records(registry: CertRegistry) -> None:
    assert "NSF Sport" in registry.records_by_program
    assert len(registry.records_by_program["NSF Sport"]) > 0


def test_registry_metadata_complete(registry: CertRegistry) -> None:
    md = registry.metadata
    assert md.get("schema_version") == "6.0.0"
    assert md.get("total_verified_records", 0) > 0
    sources = md.get("registry_sources", [])
    assert any(s.get("program") == "NSF Sport" for s in sources)


# --- Canary anchors ---------------------------------------------------------


def test_canary_thorne_mg_resolves_to_sku(registry: CertRegistry) -> None:
    """Thorne Magnesium Bisglycinate MUST resolve NSF Sport to sku scope —
    this is the cert-fix anchor canary."""
    out = resolve("Thorne", "Magnesium Bisglycinate", ["NSF Certified for Sport"], registry)
    assert len(out) == 1
    assert out[0].scope == "sku", f"expected sku, got {out[0].scope}"
    assert out[0].match_confidence is not None
    assert out[0].match_confidence >= 0.92


def test_canary_thorne_mg_usp_resolves_claimed_only(registry: CertRegistry) -> None:
    """Thorne Mg claims NSF Sport + NSF Certified + USP Verified. NSF Sport
    and NSF Certified (NSF/ANSI 173) are in our registry; USP isn't. USP must
    resolve to claimed_only (we never falsely SKU-credit a program we haven't
    loaded). This is the conservative-first contract."""
    out = resolve(
        "Thorne",
        "Magnesium Bisglycinate",
        ["NSF Certified for Sport", "NSF Certified", "USP Verified"],
        registry,
    )
    scope_map = {r.program: r.scope for r in out}
    # NSF Sport and NSF Certified should both verify (both registries loaded)
    assert scope_map["NSF Sport"] == "sku"
    # USP must remain claimed_only — that registry isn't loaded
    assert scope_map["USP Verified"] == "claimed_only"


def test_canary_thorne_mg_multi_program_sku_when_both_registries_loaded(registry: CertRegistry) -> None:
    """When both NSF Sport AND NSF/ANSI 173 registries are loaded, Thorne Mg
    should resolve BOTH programs to sku (it's listed in both)."""
    # This test depends on having NSF/ANSI 173 records in the registry.
    if "NSF Certified" not in registry.records_by_program:
        pytest.skip("NSF/ANSI 173 not loaded — run verify_certifications --source live-nsf-173")
    out = resolve(
        "Thorne",
        "Magnesium Bisglycinate",
        ["NSF Certified for Sport", "NSF Certified"],
        registry,
    )
    scope_map = {r.program: r.scope for r in out}
    assert scope_map["NSF Sport"] == "sku"
    assert scope_map["NSF Certified"] == "sku"
    # Both must be fresh (live snapshots taken today)
    for r in out:
        assert r.recency_status == "fresh", f"{r.program} unexpectedly stale"


def test_canary_thorne_brand_only_for_unlisted_sku(registry: CertRegistry) -> None:
    """A Thorne product NOT in the NSF Sport list must demote to brand_only
    (not falsely SKU-credit the manufacturer). This was the production bug."""
    out = resolve(
        "Thorne",
        "Niacin Extended Release 500 mg",  # not in DS-ABS PDF
        ["NSF Sport"],
        registry,
    )
    assert len(out) == 1
    assert out[0].scope in ("brand_only", "needs_review", "claimed_only")
    assert out[0].scope != "sku"  # the bug we're catching


def test_canary_unknown_brand_claimed_only(registry: CertRegistry) -> None:
    out = resolve("Acme Bogus Brand Co.", "Definitely Not Real", ["NSF Sport"], registry)
    assert len(out) == 1
    assert out[0].scope == "claimed_only"


# --- End-to-end audit detection ---------------------------------------------


@pytest.mark.skipif(not CORE_DB.exists(), reason="pharmaguide_core.db not present")
def test_audit_detects_cert_overcredit_at_scale(registry: CertRegistry) -> None:
    """Sample 50 products that v3 currently credits with 3+ claimed certs;
    confirm at least one is demoted under v4. If zero are demoted, the
    audit isn't generating signal."""
    con = sqlite3.connect(CORE_DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute(
        """
        SELECT dsld_id, brand_name, product_name, cert_programs
        FROM products_core
        WHERE cert_programs IS NOT NULL
          AND cert_programs != '[]'
          AND product_status = 'active'
        ORDER BY (LENGTH(cert_programs) - LENGTH(REPLACE(cert_programs, '"', '')))/2 DESC
        LIMIT 50
        """
    ).fetchall()
    con.close()

    assert len(rows) > 0, "no products with claimed certs in catalog"

    demoted = 0
    sku_verified = 0
    for r in rows:
        try:
            claimed = json.loads(r["cert_programs"]) if r["cert_programs"] else []
        except json.JSONDecodeError:
            continue
        if not claimed:
            continue
        resolutions = resolve(r["brand_name"] or "", r["product_name"] or "", claimed, registry)
        scopes = {res.scope for res in resolutions}
        if "sku" in scopes or "product_line" in scopes:
            sku_verified += 1
        elif scopes & {"brand_only", "claimed_only"}:
            demoted += 1

    # Sanity: at least SOME products should be SKU-verified (proves resolver
    # is matching real entries), and at least SOME should demote (proves the
    # audit is catching the overcredit bug).
    assert sku_verified > 0, "no products resolved to sku/product_line — resolver broken?"
    assert demoted > 0, "no products demoted — audit isn't detecting overcredit"


# --- Multi-source registry contract ----------------------------------------


def test_registry_supports_multiple_programs(registry: CertRegistry) -> None:
    """The registry holds records from NSF Sport AND NSF/ANSI 173 in one file.
    Each carries its own program tag and own snapshot recency."""
    programs = set(registry.records_by_program.keys())
    # NSF Sport must be present (it's the primary cert program we audit)
    assert "NSF Sport" in programs
    # When NSF/ANSI 173 is loaded, both programs must have separate recency.
    if "NSF Certified" in programs:
        sport_recency = registry.recency_for("NSF Sport")
        nsf173_recency = registry.recency_for("NSF Certified")
        assert sport_recency.get("status") in ("fresh", "warn", "scoring_blocked", "unknown")
        assert nsf173_recency.get("status") in ("fresh", "warn", "scoring_blocked", "unknown")


# --- Audit report schema (needs_review_queue + scoring_blocked_queue) ------


def test_audit_report_emits_top_level_queues(tmp_path: Path, registry: CertRegistry) -> None:
    """The audit report MUST emit needs_review_queue and scoring_blocked_queue
    as top-level arrays (not buried inside `records`). Reviewers triage from
    these queues directly."""
    from api_audit.cert_audit_report import audit_row, write_outputs

    # Build minimal audit_records from real catalog rows that have claimed certs.
    if not CORE_DB.exists():
        pytest.skip("pharmaguide_core.db not present")
    con = sqlite3.connect(CORE_DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT dsld_id, brand_name, product_name, score_100_equivalent,
               cert_programs, primary_category, supplement_type
        FROM products_core
        WHERE cert_programs IS NOT NULL
          AND cert_programs != '[]'
          AND product_status = 'active'
        LIMIT 30
        """
    ).fetchall()
    con.close()
    audit_records = [audit_row(dict(r) | {"_audit_bucket": "smoke"}, registry) for r in rows]

    paths = write_outputs(audit_records, tmp_path, "smoketest")
    payload = json.loads(Path(paths["json"]).read_text())

    # Schema lock — these top-level keys must exist
    assert "needs_review_queue" in payload, "needs_review_queue must be top-level for reviewer workflow"
    assert "scoring_blocked_queue" in payload, "scoring_blocked_queue must be top-level"
    assert isinstance(payload["needs_review_queue"], list)
    assert isinstance(payload["scoring_blocked_queue"], list)

    # Each needs_review entry has reviewer-ready fields
    for q in payload["needs_review_queue"]:
        for key in (
            "dsld_id",
            "brand",
            "product",
            "program",
            "match_confidence",
            "matched_brand_in_registry",
            "matched_product_in_registry",
            "override_template",
        ):
            assert key in q, f"needs_review entry missing {key}"
        # Override template must include the schema reviewers will fill in
        tmpl = q["override_template"]
        assert tmpl["status"] == "verified | rejected | pending_review"
        assert "scope" in tmpl

    # Each scoring_blocked entry must explain why it can't score
    for q in payload["scoring_blocked_queue"]:
        assert q.get("scoring_blocked_reason"), "scoring_blocked entry missing reason"
        assert q.get("recency_status") in ("scoring_blocked", "unknown")


def test_audit_report_recency_gated_b4a_does_not_credit_stale(tmp_path: Path) -> None:
    """If the registry is fully stale (recency_status=scoring_blocked), every
    claimed-cert product gets proposed_b4a_v4=0 even if resolver matches.
    This is the recency safety net."""
    from cert_resolver import CertResolution
    from api_audit.cert_audit_report import _propose_b4a

    # Two SKU resolutions, but both are scoring_blocked
    blocked = [
        CertResolution(
            program="NSF Sport",
            scope="sku",
            match_confidence=1.0,
            recency_status="scoring_blocked",
            scoring_blocked_reason="snapshot 1977d old",
        ),
        CertResolution(
            program="NSF Certified",
            scope="sku",
            match_confidence=1.0,
            recency_status="scoring_blocked",
            scoring_blocked_reason="snapshot 1977d old",
        ),
    ]
    assert _propose_b4a(blocked) == 0.0

    # Same shape but fresh → should grant points
    fresh = [
        CertResolution(
            program="NSF Sport",
            scope="sku",
            match_confidence=1.0,
            recency_status="fresh",
        ),
        CertResolution(
            program="NSF Certified",
            scope="sku",
            match_confidence=1.0,
            recency_status="fresh",
        ),
    ]
    assert _propose_b4a(fresh) > 0.0
