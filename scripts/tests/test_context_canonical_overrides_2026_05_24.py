"""Cleaner-side product-name-context canonical_id override regression tests.

Locks the schema, loader, applier, and enricher-side consumption of
`scripts/data/curated_overrides/product_context_canonical_overrides.json`.

Spec: reports/not_scored_triage/cleaner_side_context_routing_spec.md (v2)

Three deferred cases this fixes:
  - Jarrow 265081 BioCell hydrolyzed collagen
  - Pure Encapsulations 317962 DAO Enzyme
  - Natures Way 259304 / 259306 Barley Grass

Each override is scoped to (dsld_id, raw_ingredient_text) AND guarded by
product_name_must_contain_any so DSLD-ID reassignment cannot silently
mis-route a different product. The enricher honors `set_preferred_iqm_form`
deterministically — if the form key is invalid, the override FAILS SAFE
back to normal matching rather than silently scoring with the wrong form.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
IQM_PATH = DATA_DIR / "ingredient_quality_map.json"
OVERRIDES_PATH = DATA_DIR / "curated_overrides" / "product_context_canonical_overrides.json"


# ---------------------------------------------------------------------------
# Tier 1: schema + data integrity (pass once the JSON file exists + is valid)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def overrides_doc():
    assert OVERRIDES_PATH.exists(), (
        f"override file missing: {OVERRIDES_PATH}. "
        f"Create per spec at reports/not_scored_triage/cleaner_side_context_routing_spec.md"
    )
    return json.loads(OVERRIDES_PATH.read_text())


@pytest.fixture(scope="module")
def iqm():
    return json.loads(IQM_PATH.read_text())


def test_overrides_file_has_required_metadata(overrides_doc):
    meta = overrides_doc.get("_metadata")
    assert meta is not None, "_metadata block required per project convention"
    assert meta.get("schema_version") == "1.0.0"
    assert isinstance(meta.get("description"), str) and meta["description"]
    assert isinstance(meta.get("review_policy"), str) and meta["review_policy"]
    assert isinstance(meta.get("verification_policy"), str) and meta["verification_policy"]
    assert meta.get("total_entries") == len(overrides_doc.get("overrides", {}))


def test_overrides_block_present_and_keyed_by_dsld_id(overrides_doc):
    overrides = overrides_doc.get("overrides")
    assert isinstance(overrides, dict) and overrides, "overrides block required"
    for key in overrides.keys():
        assert key.isdigit(), f"override key {key!r} must be a DSLD ID (digit string)"


REQUIRED_OVERRIDE_FIELDS = {
    "id",
    "brand",
    "product_name",
    "product_name_must_contain_any",
    "raw_ingredient_text",
    "set_canonical_id",
    "set_canonical_source_db",
    "rationale",
    "evidence_pmid_or_url",
    "reviewer",
    "review_date",
    "clinical_review_status",
    "review_scope",
}

# Reviewer / sign-off placeholders that MUST never ship. The override
# JSON is a clinical sign-off contract — any of these strings means the
# entry was never actually reviewed. Per PharmaGuide Clinician Team policy.
PLACEHOLDER_REVIEWER_TOKENS = {
    "",
    "(pending)",
    "pending",
    "todo",
    "tbd",
    "placeholder",
    "claude",
    "anthropic",
    "ai",
    "agent",
    "subagent",
    "auto",
    "automated",
    "none",
    "n/a",
    "unknown",
}


@pytest.mark.parametrize("dsld_id", ["265081", "317962", "259304", "259306"])
def test_required_override_entries_exist(overrides_doc, dsld_id):
    assert dsld_id in overrides_doc["overrides"], (
        f"DSLD {dsld_id} override missing — required by spec v2."
    )


@pytest.mark.parametrize("dsld_id", ["265081", "317962", "259304", "259306"])
def test_every_override_has_all_required_fields(overrides_doc, dsld_id):
    entry = overrides_doc["overrides"][dsld_id]
    missing = REQUIRED_OVERRIDE_FIELDS - set(entry.keys())
    assert not missing, f"DSLD {dsld_id} override missing required fields: {missing}"
    # form override: at least one of set_preferred_iqm_form OR set_match_text_for_iqm
    assert entry.get("set_preferred_iqm_form") or entry.get("set_match_text_for_iqm"), (
        f"DSLD {dsld_id}: must declare either set_preferred_iqm_form or set_match_text_for_iqm"
    )
    # product_name_must_contain_any must be a non-empty list of non-empty strings
    pnc = entry["product_name_must_contain_any"]
    assert isinstance(pnc, list) and pnc, (
        f"DSLD {dsld_id}: product_name_must_contain_any must be a non-empty list (safety guard)"
    )
    for item in pnc:
        assert isinstance(item, str) and item.strip(), (
            f"DSLD {dsld_id}: product_name_must_contain_any entries must be non-empty strings"
        )


@pytest.mark.parametrize("dsld_id", ["265081", "317962", "259304", "259306"])
def test_set_preferred_iqm_form_resolves_in_iqm(overrides_doc, iqm, dsld_id):
    """CRITICAL: every set_preferred_iqm_form key must exist under the
    set_canonical_id parent in ingredient_quality_map.json. Catches typos
    BEFORE rerun; without this guard a typo would cause silent fail-safe
    fallback to unspecified form and we'd never notice."""
    entry = overrides_doc["overrides"][dsld_id]
    preferred = entry.get("set_preferred_iqm_form")
    if not preferred:
        pytest.skip(f"DSLD {dsld_id} uses set_match_text_for_iqm, not preferred_form")
    parent_id = entry["set_canonical_id"]
    parent = iqm.get(parent_id)
    assert parent is not None, (
        f"DSLD {dsld_id}: set_canonical_id={parent_id!r} is not a top-level IQM key"
    )
    forms = parent.get("forms", {})
    assert preferred in forms, (
        f"DSLD {dsld_id}: set_preferred_iqm_form={preferred!r} not found under "
        f"IQM parent {parent_id!r}. Available forms: {list(forms.keys())[:6]}..."
    )


def test_265081_routes_to_collagen_hydrolyzed(overrides_doc):
    entry = overrides_doc["overrides"]["265081"]
    assert entry["set_canonical_id"] == "collagen"
    assert entry["set_canonical_source_db"] == "ingredient_quality_map"
    assert entry["set_preferred_iqm_form"] == "hydrolyzed collagen peptides"
    assert entry["raw_ingredient_text"] == "Chicken Sternum Collagen extract"
    # Product-name guard: BioCell or "Type II Bioavailable" required
    guards = [g.lower() for g in entry["product_name_must_contain_any"]]
    assert any("biocell" in g or "type ii bioavailable" in g for g in guards), (
        "BioCell override must require product_name to contain BioCell or Type II Bioavailable"
    )


def test_317962_routes_to_diamine_oxidase(overrides_doc):
    entry = overrides_doc["overrides"]["317962"]
    assert entry["set_canonical_id"] == "diamine_oxidase"
    assert entry["set_canonical_source_db"] == "ingredient_quality_map"
    assert entry["set_preferred_iqm_form"] == "diamine oxidase (unspecified)"
    assert entry["raw_ingredient_text"] == "Porcine Kidney Extract"
    guards = [g.lower() for g in entry["product_name_must_contain_any"]]
    assert any("dao" in g or "diamine oxidase" in g for g in guards)


@pytest.mark.parametrize("dsld_id", ["259304", "259306"])
def test_barley_grass_routes(overrides_doc, dsld_id):
    entry = overrides_doc["overrides"][dsld_id]
    assert entry["set_canonical_id"] == "barley_grass"
    assert entry["set_canonical_source_db"] == "ingredient_quality_map"
    assert entry["set_preferred_iqm_form"] == "barley grass (unspecified)"
    assert entry["raw_ingredient_text"] == "Barley"
    guards = [g.lower() for g in entry["product_name_must_contain_any"]]
    assert any("barley grass" in g for g in guards)


def test_no_override_aliases_a_bare_ambiguous_row_text_globally(overrides_doc):
    """Sanity: every override MUST carry a product_name guard. A bare
    (dsld_id, raw_text) match without a product_name guard would silently
    fire if the DSLD ID were ever reassigned to a different product. This
    test makes that contract structurally enforceable."""
    for dsld_id, entry in overrides_doc["overrides"].items():
        assert entry.get("product_name_must_contain_any"), (
            f"DSLD {dsld_id}: override lacks product_name_must_contain_any safety guard"
        )


def test_evidence_field_is_present_and_non_placeholder(overrides_doc):
    """No empty evidence strings. PMID citations must be verified via
    scripts/api_audit/verify_pubmed_references.py BEFORE commit."""
    for dsld_id, entry in overrides_doc["overrides"].items():
        ev = entry.get("evidence_pmid_or_url", "").strip()
        assert ev, f"DSLD {dsld_id}: evidence_pmid_or_url empty"
        assert ev.lower() not in {"tbd", "todo", "fixme", "n/a"}, (
            f"DSLD {dsld_id}: evidence is a placeholder ({ev!r})"
        )


def test_reviewer_is_never_a_placeholder(overrides_doc):
    """Per PharmaGuide Clinician Team sign-off contract: reviewer must
    be a named clinician/team, never a placeholder or generic AI handle.
    The list of forbidden tokens is comprehensive — this guards against
    reviewer='(pending)', 'TBD', 'Claude', 'Anthropic', empty string,
    'auto', etc. accidentally shipping past CI."""
    for dsld_id, entry in overrides_doc["overrides"].items():
        reviewer = (entry.get("reviewer") or "").strip()
        token = reviewer.lower()
        assert token not in PLACEHOLDER_REVIEWER_TOKENS, (
            f"DSLD {dsld_id}: reviewer={reviewer!r} is a placeholder. "
            f"Use a named team (e.g., 'PharmaGuide Clinician Team') or "
            f"individual clinician sign-off. Forbidden tokens: "
            f"{sorted(PLACEHOLDER_REVIEWER_TOKENS)}"
        )
        assert reviewer, f"DSLD {dsld_id}: reviewer empty"


def test_clinical_review_status_recognized_value(overrides_doc):
    """clinical_review_status must be an explicit, recognized value —
    not free-form. Currently the only accepted value is
    'identity_routing_reviewed' (clinician confirmed the row text +
    product-name pair maps to the right IQM identity, but did NOT
    re-verify the upstream bio_score or clinical evidence for the
    chosen IQM form). Extend this set only with explicit dev approval."""
    ACCEPTED_STATUSES = {"identity_routing_reviewed"}
    for dsld_id, entry in overrides_doc["overrides"].items():
        status = entry.get("clinical_review_status")
        assert status in ACCEPTED_STATUSES, (
            f"DSLD {dsld_id}: clinical_review_status={status!r} not in "
            f"accepted set {ACCEPTED_STATUSES}. New statuses require "
            f"dev review before extending this allowlist."
        )


def test_review_scope_recognized_value(overrides_doc):
    """review_scope must be an explicit, recognized value. Currently
    only 'context_identity_routing_only' is accepted — meaning the
    clinician reviewed the identity-routing decision only, NOT the
    full evidence chain or the bio_score of the chosen form."""
    ACCEPTED_SCOPES = {"context_identity_routing_only"}
    for dsld_id, entry in overrides_doc["overrides"].items():
        scope = entry.get("review_scope")
        assert scope in ACCEPTED_SCOPES, (
            f"DSLD {dsld_id}: review_scope={scope!r} not in accepted "
            f"set {ACCEPTED_SCOPES}. New scopes require dev review."
        )


# ---------------------------------------------------------------------------
# Tier 2: loader + applier unit tests (pass once enhanced_normalizer.py and
# enrich_supplements_v3.py implement _load_context_canonical_overrides and
# _apply_context_canonical_override + enricher-side consumption)
# ---------------------------------------------------------------------------


def test_enhanced_normalizer_exposes_context_override_loader():
    """The cleaner must load the override file via a public-ish method
    name (_load_context_canonical_overrides) so the contract is greppable."""
    from scripts import enhanced_normalizer  # type: ignore

    # Find any function named _load_context_canonical_overrides on the
    # EnhancedNormalizer class or as a module-level function.
    candidates = []
    for attr in dir(enhanced_normalizer):
        if "context" in attr.lower() and "override" in attr.lower():
            candidates.append(attr)
    # The class itself may carry the method
    cls = getattr(enhanced_normalizer, "EnhancedDSLDNormalizer", None)
    if cls is not None:
        for attr in dir(cls):
            if "context" in attr.lower() and "override" in attr.lower():
                candidates.append(f"EnhancedNormalizer.{attr}")
    assert candidates, (
        "enhanced_normalizer.py must expose a loader for the context override file "
        "(name pattern: *context*override*). See spec section 'Loader + applier design'."
    )


def test_apply_context_override_stamps_row_fields_when_all_conditions_match():
    """When dsld_id + raw_text + product_name guard ALL match, the applier
    must stamp the override fields onto the row."""
    from scripts import enhanced_normalizer  # type: ignore

    apply_fn = getattr(enhanced_normalizer, "_apply_context_canonical_override", None)
    if apply_fn is None:
        # Could be a method on the class
        cls = getattr(enhanced_normalizer, "EnhancedDSLDNormalizer", None)
        if cls is not None:
            apply_fn = getattr(cls, "_apply_context_canonical_override", None)
    assert apply_fn is not None, (
        "_apply_context_canonical_override must exist (module-level or "
        "EnhancedNormalizer method) per spec."
    )


@pytest.fixture(scope="module")
def normalizer():
    """Build one EnhancedDSLDNormalizer for all behavioral tests. __init__ is
    heavy (loads ~20 reference DBs) so this is module-scoped."""
    from scripts.enhanced_normalizer import EnhancedDSLDNormalizer  # type: ignore
    return EnhancedDSLDNormalizer()


def _make_row(name, canonical_id=None, canonical_source_db=None):
    return {
        "name": name,
        "raw_source_text": name,
        "canonical_id": canonical_id,
        "canonical_source_db": canonical_source_db,
    }


def test_positive_265081_biocell_override_fires(normalizer):
    """All three conditions met → stamps the override fields on the row."""
    row = _make_row("Chicken Sternum Collagen extract")
    out = normalizer._apply_context_canonical_override(
        product_id="265081",
        product_name="Type II Bioavailable Collagen Complex",
        row=row,
    )
    assert out.get("context_override_applied") is True
    assert out.get("context_override_id") == "jarrow_265081_biocell_hydrolyzed"
    assert out.get("cleaner_canonical_id_override") == "collagen"
    assert out.get("cleaner_canonical_source_db_override") == "ingredient_quality_map"
    assert out.get("cleaner_preferred_iqm_form_override") == "hydrolyzed collagen peptides"
    # Pre-override audit fields preserved (None in this fixture)
    assert "cleaner_canonical_id_pre_override" in out


def test_positive_317962_dao_override_fires(normalizer):
    row = _make_row("Porcine Kidney Extract",
                    canonical_id="PII_KIDNEY_TISSUE",
                    canonical_source_db="other_ingredients")
    out = normalizer._apply_context_canonical_override(
        product_id="317962",
        product_name="DAO Enzyme",
        row=row,
    )
    assert out.get("context_override_applied") is True
    assert out.get("cleaner_canonical_id_override") == "diamine_oxidase"
    assert out.get("cleaner_preferred_iqm_form_override") == "diamine oxidase (unspecified)"
    # Pre-override audit fields capture the original PII canonical_id
    assert out.get("cleaner_canonical_id_pre_override") == "PII_KIDNEY_TISSUE"
    assert out.get("cleaner_canonical_source_db_pre_override") == "other_ingredients"


@pytest.mark.parametrize("dsld_id,prod_name", [
    ("259304", "Barley Grass"),
    ("259306", "Barley Grass Powder"),
])
def test_positive_barley_grass_override_fires(normalizer, dsld_id, prod_name):
    row = _make_row("Barley")
    out = normalizer._apply_context_canonical_override(
        product_id=dsld_id,
        product_name=prod_name,
        row=row,
    )
    assert out.get("context_override_applied") is True
    assert out.get("cleaner_canonical_id_override") == "barley_grass"
    assert out.get("cleaner_preferred_iqm_form_override") == "barley grass (unspecified)"


def test_negative_dsld_id_mismatch_no_override_applied(normalizer):
    """Different dsld_id with the same row text and product_name pattern
    must NOT fire the override."""
    row = _make_row("Porcine Kidney Extract", canonical_id="PII_KIDNEY_TISSUE")
    # Some other DSLD ID that is NOT in the override file
    out = normalizer._apply_context_canonical_override(
        product_id="999999",
        product_name="DAO Enzyme",
        row=row,
    )
    assert out.get("context_override_applied") is None
    assert "cleaner_canonical_id_override" not in out
    # Row's original canonical_id untouched
    assert out["canonical_id"] == "PII_KIDNEY_TISSUE"


def test_negative_product_name_guard_blocks_override(normalizer):
    """Same dsld_id + row text but product_name lacks any guard substring
    → override skipped. Tests the DSLD-ID-reassignment defense."""
    row = _make_row("Porcine Kidney Extract", canonical_id="PII_KIDNEY_TISSUE")
    out = normalizer._apply_context_canonical_override(
        product_id="317962",
        product_name="Generic Porcine Kidney Glandular Capsules",  # no DAO/Diamine Oxidase
        row=row,
    )
    assert out.get("context_override_applied") is None
    assert "cleaner_canonical_id_override" not in out


def test_negative_uc_ii_product_does_not_fire_biocell_override(normalizer):
    """UC-II product with the same 'Chicken Sternum Collagen extract' row
    but product_name='Undenatured Type II Collagen' must NOT route to
    BioCell hydrolyzed (the override is BioCell-scoped via product_name)."""
    row = _make_row("Chicken Sternum Collagen extract")
    # DSLD 265081 is reserved for BioCell — UC-II products would have a
    # different DSLD ID, so this is the first defense. But to also test
    # the product_name guard, simulate an alternate world where 265081 is
    # somehow paired with a UC-II framing — guard should still block.
    out = normalizer._apply_context_canonical_override(
        product_id="265081",
        product_name="Undenatured Type II Collagen UC-II",
        row=row,
    )
    assert out.get("context_override_applied") is None
    assert "cleaner_canonical_id_override" not in out


def test_negative_row_text_mismatch_no_override_applied(normalizer):
    """Same dsld_id + matching product_name but a totally different row
    (e.g. a vitamin row in the same product) must NOT fire."""
    row = _make_row("Vitamin C")  # not the override's raw_ingredient_text
    out = normalizer._apply_context_canonical_override(
        product_id="265081",
        product_name="Type II Bioavailable Collagen Complex",
        row=row,
    )
    assert out.get("context_override_applied") is None


def test_case_insensitive_row_text_match(normalizer):
    """Row text match must be case-insensitive and whitespace-stripped
    so manufacturer label casing drift doesn't silently break overrides."""
    row = _make_row("  chicken sternum collagen extract  ")  # different case + whitespace
    out = normalizer._apply_context_canonical_override(
        product_id="265081",
        product_name="Type II Bioavailable Collagen Complex",
        row=row,
    )
    assert out.get("context_override_applied") is True
    assert out.get("cleaner_canonical_id_override") == "collagen"


def test_case_insensitive_product_name_guard(normalizer):
    """Product-name guard substring match must be case-insensitive."""
    row = _make_row("Chicken Sternum Collagen extract")
    out = normalizer._apply_context_canonical_override(
        product_id="265081",
        product_name="TYPE II BIOAVAILABLE COLLAGEN COMPLEX",  # all caps
        row=row,
    )
    assert out.get("context_override_applied") is True


def test_fail_safe_when_preferred_form_not_found_in_iqm():
    """Schema-level guard: if any override declares a set_preferred_iqm_form
    that doesn't resolve under set_canonical_id in IQM, the
    test_set_preferred_iqm_form_resolves_in_iqm pytest above fails BEFORE
    the rerun ships. That's the commit-time fail-safe.

    Additionally, the enricher-side consumer (to be wired in commit 1
    follow-up + tested via Tier 3 live-corpus) must NOT silently fall back
    to the unspecified form. It must either log an explicit warning AND
    fall back to normal matching, or refuse the override.

    For commit 1 (loader+applier only), the IQM-side guard is the
    structural defense. The runtime fail-safe is verified by Tier 3 after
    enricher consumption + rerun lands."""
    # No-op assertion: the structural guard runs in
    # test_set_preferred_iqm_form_resolves_in_iqm. This test exists so a
    # future engineer searching for "fail safe" finds the documentation.
    assert True


# ---------------------------------------------------------------------------
# Tier 2.5: enricher-side helper integration tests. Builds a real IQM-loaded
# enricher instance, calls _apply_context_canonical_override_match() with
# the same row shape the cleaner now stamps. Proves end-to-end:
#   cleaner stamps override → enricher consumes it → returns synthetic
#   match_result with the right canonical_id + form + bio_score.
# This closes the gap between "applier works in isolation" and "BioCell
# row actually scores as hydrolyzed collagen peptides".
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def enricher_with_iqm():
    """Build a SupplementEnricherV3 once. Heavy init — module-scoped."""
    import sys as _sys
    _sys.path.insert(0, str(REPO_ROOT))
    from enrich_supplements_v3 import SupplementEnricherV3  # type: ignore
    return SupplementEnricherV3()


def _stamped_row(name, parent, form, override_id):
    """Build the row shape that the cleaner now emits post-applier."""
    return {
        "name": name,
        "standardName": name,
        "canonical_id": parent,
        "canonical_source_db": "ingredient_quality_map",
        "cleaner_canonical_id_override": parent,
        "cleaner_canonical_source_db_override": "ingredient_quality_map",
        "cleaner_preferred_iqm_form_override": form,
        "cleaner_canonical_id_pre_override": None,
        "cleaner_canonical_source_db_pre_override": "unmapped",
        "context_override_applied": True,
        "context_override_id": override_id,
        "cleaner_match_method": "curated_context_override",
    }


def test_enricher_consumes_265081_biocell_override(enricher_with_iqm, iqm):
    row = _stamped_row(
        "Chicken Sternum Collagen extract",
        "collagen",
        "hydrolyzed collagen peptides",
        "jarrow_265081_biocell_hydrolyzed",
    )
    match_result = enricher_with_iqm._apply_context_canonical_override_match(row, iqm)
    assert match_result is not None
    assert match_result["canonical_id"] == "collagen"
    assert match_result["form_id"] == "hydrolyzed collagen peptides"
    assert match_result["form_name"] == "hydrolyzed collagen peptides"
    # Live BioCell form bio_score per IQM (verified earlier this session: 11)
    assert match_result["bio_score"] == 11
    assert match_result["match_tier"] == "curated_context_override"
    assert match_result["context_override_id"] == "jarrow_265081_biocell_hydrolyzed"
    assert match_result["context_override_applied"] is True


def test_enricher_consumes_317962_dao_override(enricher_with_iqm, iqm):
    row = _stamped_row(
        "Porcine Kidney Extract",
        "diamine_oxidase",
        "diamine oxidase (unspecified)",
        "pure_encap_317962_dao_enzyme",
    )
    match_result = enricher_with_iqm._apply_context_canonical_override_match(row, iqm)
    assert match_result is not None
    assert match_result["canonical_id"] == "diamine_oxidase"
    assert match_result["form_id"] == "diamine oxidase (unspecified)"
    assert match_result["bio_score"] == 5
    assert match_result["context_override_id"] == "pure_encap_317962_dao_enzyme"


@pytest.mark.parametrize("override_id", [
    "natures_way_259304_barley_grass",
    "natures_way_259306_barley_grass_powder",
])
def test_enricher_consumes_barley_grass_override(enricher_with_iqm, iqm, override_id):
    row = _stamped_row("Barley", "barley_grass", "barley grass (unspecified)", override_id)
    match_result = enricher_with_iqm._apply_context_canonical_override_match(row, iqm)
    assert match_result is not None
    assert match_result["canonical_id"] == "barley_grass"
    assert match_result["form_id"] == "barley grass (unspecified)"
    assert match_result["bio_score"] == 5
    assert match_result["context_override_id"] == override_id


def test_enricher_returns_none_when_override_not_applied(enricher_with_iqm, iqm):
    """Row without context_override_applied → helper returns None → caller
    falls through to normal _match_quality_map."""
    row = {
        "name": "Vitamin C",
        "standardName": "Vitamin C",
        "canonical_id": "vitamin_c",
        "canonical_source_db": "ingredient_quality_map",
        # no context_override_applied
    }
    match_result = enricher_with_iqm._apply_context_canonical_override_match(row, iqm)
    assert match_result is None


def test_enricher_fail_safe_when_override_parent_missing_from_iqm(enricher_with_iqm, iqm):
    """If cleaner_canonical_id_override points to a parent not in
    quality_map, helper returns None (fail-safe to normal matching).
    Defends against IQM parent renames / typos in override JSON that
    pre-test guard didn't catch."""
    row = _stamped_row(
        "Some Row", "this_iqm_parent_does_not_exist", "any form", "test_typo_override"
    )
    match_result = enricher_with_iqm._apply_context_canonical_override_match(row, iqm)
    assert match_result is None


def test_enricher_fail_safe_when_override_form_missing_from_iqm_parent(enricher_with_iqm, iqm):
    """If parent exists but cleaner_preferred_iqm_form_override does NOT
    resolve under the parent (form typo / IQM drift), helper returns None.
    CRITICAL: must NOT silently fall back to unspecified form, because the
    whole point of the override is to force a SPECIFIC form choice."""
    row = _stamped_row(
        "Chicken Sternum Collagen extract",
        "collagen",
        "hydrolyzed collagen peptides TYPO",  # form name does NOT exist
        "test_typo_override",
    )
    match_result = enricher_with_iqm._apply_context_canonical_override_match(row, iqm)
    assert match_result is None, (
        "FAIL-SAFE BREACH: helper returned a match_result even though the "
        "preferred form key does not exist under the parent. Would silently "
        "score with the wrong form. Helper must return None and let normal "
        "matching run with a logged warning."
    )


def test_enricher_returns_none_when_override_is_parent_only(enricher_with_iqm, iqm):
    """If the override declares set_canonical_id but no
    set_preferred_iqm_form (parent-only override), the helper returns
    None — letting normal _match_quality_map run with the cleaner's
    overridden canonical_id as Phase 3 authority. The Phase 3 path will
    naturally pick a form under the parent."""
    row = {
        "name": "Some Generic Row",
        "canonical_id": "barley_grass",
        "canonical_source_db": "ingredient_quality_map",
        "context_override_applied": True,
        "context_override_id": "parent_only_test",
        "cleaner_canonical_id_override": "barley_grass",
        "cleaner_canonical_source_db_override": "ingredient_quality_map",
        # NO cleaner_preferred_iqm_form_override
    }
    match_result = enricher_with_iqm._apply_context_canonical_override_match(row, iqm)
    assert match_result is None


# ---------------------------------------------------------------------------
# Tier 3: live raw DSLD JSON → cleaner → enricher integration tests.
# Loads the actual raw DSLD product JSONs from the local staging dataset
# and runs them through the real cleaner + enricher. Skips when the
# staging dataset is not mounted (CI environments without /Users/...).
# Verified locally 2026-05-24 via /tmp/verify_context_routing_live.py;
# these tests lock the same behavior in pytest CI when the dataset is
# available.
# ---------------------------------------------------------------------------


RAW_DSLD_STAGING_ROOT = Path("/Users/seancheick/Documents/DataSetDsld/staging/brands")


def _load_raw_dsld(brand: str, dsld_id: str):
    """Load raw DSLD JSON for a specific (brand, dsld_id). Returns None if
    the staging dataset is not mounted (CI / fresh checkout)."""
    if not RAW_DSLD_STAGING_ROOT.exists():
        return None
    p = RAW_DSLD_STAGING_ROOT / brand / f"{dsld_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


@pytest.mark.parametrize("brand,dsld_id,row_name,override_id,canonical,form,bio_score", [
    ("Jarrow_Formulas",     "265081", "Chicken Sternum Collagen extract",
     "jarrow_265081_biocell_hydrolyzed",       "collagen",        "hydrolyzed collagen peptides", 11),
    ("Pure_Encapsulations", "317962", "Porcine Kidney Extract",
     "pure_encap_317962_dao_enzyme",            "diamine_oxidase", "diamine oxidase (unspecified)", 5),
    ("Natures_Way",         "259304", "Barley",
     "natures_way_259304_barley_grass",         "barley_grass",    "barley grass (unspecified)",    5),
    ("Natures_Way",         "259306", "Barley",
     "natures_way_259306_barley_grass_powder",  "barley_grass",    "barley grass (unspecified)",    5),
])
def test_live_raw_dsld_through_cleaner_and_enricher(
    normalizer, enricher_with_iqm, iqm,
    brand, dsld_id, row_name, override_id, canonical, form, bio_score,
):
    """End-to-end behavioral test: load actual raw DSLD JSON, run through
    cleaner.normalize_product, find the target row, verify the cleaner
    stamped the override; then feed to enricher's
    _apply_context_canonical_override_match and verify the synthetic
    match_result emits the expected canonical_id + form + bio_score +
    override_id. Skip when the staging dataset is not mounted."""
    raw = _load_raw_dsld(brand, dsld_id)
    if raw is None:
        pytest.skip(
            f"raw DSLD staging dataset not mounted at {RAW_DSLD_STAGING_ROOT} "
            f"or {brand}/{dsld_id}.json missing"
        )

    cleaned = normalizer.normalize_product(raw)

    # Locate the target active-ingredient row
    target_row = None
    for r in cleaned.get("activeIngredients") or []:
        if (r.get("name") or "").strip().lower() == row_name.strip().lower():
            target_row = r
            break
    assert target_row is not None, (
        f"DSLD {dsld_id}: no active row named {row_name!r}. "
        f"Active row names: {[r.get('name') for r in (cleaned.get('activeIngredients') or [])]}"
    )

    # Cleaner stamps
    assert target_row.get("context_override_applied") is True, (
        f"DSLD {dsld_id}: cleaner did NOT stamp context_override_applied"
    )
    assert target_row.get("context_override_id") == override_id
    assert target_row.get("cleaner_canonical_id_override") == canonical
    assert target_row.get("cleaner_preferred_iqm_form_override") == form
    # Applier overwrites the row's canonical_id so Phase 3 authority sees it
    assert target_row.get("canonical_id") == canonical

    # Enricher consumption
    match_result = enricher_with_iqm._apply_context_canonical_override_match(
        target_row, iqm
    )
    assert match_result is not None, (
        f"DSLD {dsld_id}: enricher helper returned None despite stamped override"
    )
    assert match_result["canonical_id"] == canonical
    assert match_result["form_id"] == form
    assert match_result["bio_score"] == bio_score
    assert match_result["match_tier"] == "curated_context_override"
    assert match_result["context_override_id"] == override_id


# ---------------------------------------------------------------------------
# Tier 3.5: skip-path regression. Reproduces the actual full-rerun bug
# where DSLD 317962 DAO Enzyme landed in ingredients_skipped because
# _should_skip_from_scoring matched "Porcine Kidney Extract" against
# PII_KIDNEY_TISSUE (category="active_pending_relocation") by NAME and
# returned SKIP_REASON_RECOGNIZED_NON_SCORABLE — completely ignoring the
# cleaner-stamped context_override_applied flag. Tests below lock the
# fix: when context_override_applied=True, the skip-decision functions
# must return None so the override-consumption helper at line 2748+ can
# actually run.
#
# Without these tests, the original Tier 2.5/3 tests passed because they
# called the helper directly, never going through _should_skip_from_scoring.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def botanicals_db():
    """Load botanical_ingredients.json for _should_skip_from_scoring."""
    bot_path = REPO_ROOT / "data" / "botanical_ingredients.json"
    return json.loads(bot_path.read_text())


def test_should_skip_from_scoring_bypasses_when_override_applied(
    enricher_with_iqm, iqm, botanicals_db
):
    """REGRESSION: synthesize the exact row shape the cleaner emits for
    DSLD 317962 DAO Enzyme post-override. _should_skip_from_scoring must
    return None (scorable). Without the bypass it returns
    SKIP_REASON_RECOGNIZED_NON_SCORABLE because 'Porcine Kidney Extract'
    matches PII_KIDNEY_TISSUE.category='active_pending_relocation'."""
    row_with_override = {
        "name": "Porcine Kidney Extract",
        "standardName": "Kidney Tissue",
        "canonical_id": "diamine_oxidase",  # override applied
        "canonical_source_db": "ingredient_quality_map",
        "context_override_applied": True,
        "context_override_id": "pure_encap_317962_dao_enzyme",
        "cleaner_canonical_id_override": "diamine_oxidase",
        "cleaner_preferred_iqm_form_override": "diamine oxidase (unspecified)",
        "score_eligible_by_cleaner": True,
        "cleaner_row_role": "active_scorable",
        "quantity": 4.2,
        "unit": "mg",
    }
    # Use the actual loaded DBs (iqm fixture + botanicals_db)
    quality_map = enricher_with_iqm.databases.get("ingredient_quality_map", {})
    skip_reason = enricher_with_iqm._should_skip_from_scoring(
        row_with_override, quality_map, botanicals_db
    )
    assert skip_reason is None, (
        f"_should_skip_from_scoring returned {skip_reason!r} for a row with "
        f"context_override_applied=True. The bypass at the top of the function "
        f"is missing or broken — row will be shunted to ingredients_skipped "
        f"and never reach the override-consumption helper."
    )


def test_should_skip_from_scoring_still_skips_when_no_override(
    enricher_with_iqm, iqm, botanicals_db
):
    """NEGATIVE: the same row WITHOUT the override stamp must still be
    skipped (proves the bypass is scoped to overridden rows only, doesn't
    accidentally let unrelated Porcine Kidney Extract rows through)."""
    row_without_override = {
        "name": "Porcine Kidney Extract",
        "standardName": "Kidney Tissue",
        "canonical_id": "PII_KIDNEY_TISSUE",
        "canonical_source_db": "other_ingredients",
        # NO context_override_applied
        "score_eligible_by_cleaner": True,
        "cleaner_row_role": "active_scorable",
        "quantity": 100.0,
        "unit": "mg",
    }
    quality_map = enricher_with_iqm.databases.get("ingredient_quality_map", {})
    skip_reason = enricher_with_iqm._should_skip_from_scoring(
        row_without_override, quality_map, botanicals_db
    )
    assert skip_reason is not None, (
        "A bare 'Porcine Kidney Extract' row (no override) must still be "
        "skipped via the PII_KIDNEY_TISSUE recognition path. If this passes "
        "with skip_reason=None, the bypass is too broad — it lets all "
        "kidney-glandular rows through, which would falsely promote them "
        "to score as DAO enzyme."
    )


@pytest.mark.parametrize("dsld_id,row_name,override_id,canonical,form,bio_score", [
    ("265081", "Chicken Sternum Collagen extract", "jarrow_265081_biocell_hydrolyzed",      "collagen",        "hydrolyzed collagen peptides", 11),
    ("317962", "Porcine Kidney Extract",           "pure_encap_317962_dao_enzyme",          "diamine_oxidase", "diamine oxidase (unspecified)", 5),
    ("259304", "Barley",                           "natures_way_259304_barley_grass",        "barley_grass",    "barley grass (unspecified)",    5),
    ("259306", "Barley",                           "natures_way_259306_barley_grass_powder", "barley_grass",    "barley grass (unspecified)",    5),
])
def test_skip_path_bypassed_for_all_4_overridden_rows(
    enricher_with_iqm, iqm, botanicals_db,
    dsld_id, row_name, override_id, canonical, form, bio_score,
):
    """Parametrized regression: all 4 reviewer-signed overrides must pass
    _should_skip_from_scoring (return None) so they actually reach the
    enricher's match path. Locks the call-site bypass and the in-function
    bypass simultaneously."""
    row = {
        "name": row_name,
        "standardName": row_name,
        "canonical_id": canonical,
        "canonical_source_db": "ingredient_quality_map",
        "context_override_applied": True,
        "context_override_id": override_id,
        "cleaner_canonical_id_override": canonical,
        "cleaner_preferred_iqm_form_override": form,
        "score_eligible_by_cleaner": True,
        "cleaner_row_role": "active_scorable",
        "quantity": 100.0,
        "unit": "mg",
    }
    quality_map = enricher_with_iqm.databases.get("ingredient_quality_map", {})
    skip_reason = enricher_with_iqm._should_skip_from_scoring(
        row, quality_map, botanicals_db
    )
    assert skip_reason is None, (
        f"DSLD {dsld_id} ({override_id}): _should_skip_from_scoring returned "
        f"{skip_reason!r}. Override row would be shunted to ingredients_skipped."
    )


def test_live_dsld_317962_reaches_ingredients_scorable_not_skipped(
    normalizer, enricher_with_iqm, iqm, botanicals_db
):
    """END-TO-END REGRESSION: load the actual Pure Encapsulations 317962
    DAO Enzyme raw JSON, run through cleaner + the enricher's full
    per-product code path, assert the DAO row appears in the
    ingredient_quality_data.ingredients_scorable list (not _skipped) AND
    carries the override-tagged identity_decision_reason.

    This is the test the user said was missing — it exercises the actual
    skip-then-promote path, not just the helper in isolation."""
    raw = _load_raw_dsld("Pure_Encapsulations", "317962")
    if raw is None:
        pytest.skip(
            f"raw DSLD staging dataset not mounted at {RAW_DSLD_STAGING_ROOT}"
        )

    cleaned = normalizer.normalize_product(raw)

    # Run the cleaned product through enricher.enrich_product (the real
    # entry point). enrich_product returns (enriched_product, issues_list).
    enriched, _issues = enricher_with_iqm.enrich_product(cleaned)
    iqd = enriched.get("ingredient_quality_data") or {}
    scorable = iqd.get("ingredients_scorable") or []
    skipped = iqd.get("ingredients_skipped") or []

    # Locate the DAO row in scorable (NOT in skipped)
    dao_in_scorable = None
    for ing in scorable:
        if (ing.get("name") or "").strip().lower() == "porcine kidney extract":
            dao_in_scorable = ing
            break

    dao_in_skipped = None
    for ing in skipped:
        if (ing.get("name") or "").strip().lower() == "porcine kidney extract":
            dao_in_skipped = ing
            break

    assert dao_in_scorable is not None, (
        f"DAO row 'Porcine Kidney Extract' should be in ingredients_scorable. "
        f"Found in skipped: {bool(dao_in_skipped)}. "
        f"Scorable names: {[i.get('name') for i in scorable]}"
    )
    assert dao_in_skipped is None, (
        f"DAO row 'Porcine Kidney Extract' must NOT be in ingredients_skipped "
        f"once the context override fires. Skip reason was: "
        f"{(dao_in_skipped or {}).get('skip_reason')}"
    )

    # Verify the scorable row carries override tagging
    assert dao_in_scorable.get("canonical_id") == "diamine_oxidase"
    assert dao_in_scorable.get("matched_form") == "diamine oxidase (unspecified)"
    assert dao_in_scorable.get("bio_score") == 5
    assert (
        dao_in_scorable.get("identity_decision_reason")
        == "curated_context_canonical_override"
    )
    assert (
        dao_in_scorable.get("context_override_id")
        == "pure_encap_317962_dao_enzyme"
    )
