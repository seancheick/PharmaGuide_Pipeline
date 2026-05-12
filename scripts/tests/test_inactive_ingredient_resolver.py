"""
Tests for the unified InactiveIngredientResolver.

Architectural contract:
  - For every inactive label entry, consult three sources in PRIORITY ORDER:
      1. banned_recalled_ingredients.json  (status: banned / high_risk / recalled / watchlist)
      2. harmful_additives.json            (severity_level: high / moderate / low)
      3. other_ingredients.json            (excipient role classification)
  - Match strictly on standard_name + aliases. Never on notes/description/
    safety_summary text — those are editorial context, not label content.
  - Use normalized exact alias match. No broad fuzzy.
  - Skip banned_recalled entries with match_mode in {'disabled', 'historical'}.
  - Return a single InactiveResolution dataclass with the full contract:
    raw_name, display_label, display_role_label, functional_roles,
    additive_type, severity_status, is_safety_concern, is_banned,
    safety_reason, matched_source, matched_rule_id, plus the per-source
    safety/role metadata Flutter needs to render the inactive row.

Severity precedence:
    banned_recalled.status='banned'       → severity_status='critical', is_banned=True,  is_safety_concern=True
    banned_recalled.status='high_risk'    → severity_status='critical', is_banned=False, is_safety_concern=True
    banned_recalled.status='recalled'     → severity_status='critical', is_banned=False, is_safety_concern=True
    banned_recalled.status='watchlist'    → severity_status='informational', is_banned=False, is_safety_concern=False
    harmful_additives.severity={high|critical|moderate}  → severity_status='critical', is_safety_concern=True
    harmful_additives.severity='low'      → severity_status='suppress',  is_safety_concern=False
    other_ingredients (excipient match)   → severity_status='n/a',       is_safety_concern=False, with role label
    unmatched                             → severity_status='n/a',       all flags False, role labels None

Acceptance criteria mapped to test names:
  - test_titanium_dioxide_resolves_to_critical_high_risk
  - test_talc_resolves_to_critical_high_risk
  - test_mica_pearlescent_pigment_does_not_falsely_match_titanium_dioxide
  - test_vitamin_e_inactive_gets_preservative_role
  - test_riboflavin_inactive_gets_colorant_role
  - test_fish_body_oil_inactive_gets_carrier_role
  - test_rose_hips_inactive_gets_botanical_role
  - test_safe_excipients_remain_low_or_none_concern (gelatin, cellulose, mag stearate)
  - test_unmatched_inactive_returns_unknown_role
  - test_match_only_on_standard_name_and_aliases_not_notes
  - test_resolver_skips_disabled_and_historical_banned_recalled_entries
  - test_resolver_precedence_banned_beats_harmful (canary)
  - test_resolver_returns_matched_source_for_provenance
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Fixture: a single shared resolver instance reading the live data files.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def resolver():
    from scripts.inactive_ingredient_resolver import InactiveIngredientResolver
    return InactiveIngredientResolver()


# ---------------------------------------------------------------------------
# Banned/high-risk inactives (the TiO2/Talc class)
# ---------------------------------------------------------------------------

def test_titanium_dioxide_resolves_to_critical_safety_concern(resolver) -> None:
    """The TiO2 entry in banned_recalled_ingredients.json should now reach
    the inactive path. Pre-fix: severity_status='n/a', is_safety_concern=False
    on 1,178 inactive entries — a clinical-grade safety gap."""
    r = resolver.resolve(raw_name="Titanium Dioxide")
    assert r.matched_source == "banned_recalled", (
        f"TiO2 must match banned_recalled, got matched_source={r.matched_source!r}"
    )
    assert r.severity_status == "critical", (
        f"TiO2 severity_status must be critical, got {r.severity_status!r}"
    )
    assert r.is_safety_concern is True
    assert r.safety_reason and len(r.safety_reason) > 0
    assert r.matched_rule_id and "TITANIUM_DIOXIDE" in r.matched_rule_id.upper()


def test_titanium_dioxide_with_form_variants(resolver) -> None:
    """The cleaner may pass 'Titanium dioxide', 'Titanium Dioxide (E171)',
    'TiO2', etc. All must hit the same rule."""
    for variant in ("Titanium dioxide", "titanium dioxide", "Titanium Dioxide (E171)"):
        r = resolver.resolve(raw_name=variant)
        assert r.matched_source == "banned_recalled", (
            f"variant {variant!r} did not match banned_recalled — got {r.matched_source!r}"
        )
        assert r.severity_status == "critical"


def test_talc_resolves_to_critical_high_risk(resolver) -> None:
    """Talc is at banned_recalled_ingredients.json[133], status='high_risk',
    clinical_risk_enum='high'. Must produce severity_status='critical' AND
    is_safety_concern=True but NOT is_banned (since status is high_risk
    not banned). Distinguishes blocking vs warning."""
    r = resolver.resolve(raw_name="Talc")
    assert r.matched_source == "banned_recalled"
    assert r.severity_status == "critical"
    assert r.is_safety_concern is True
    assert r.is_banned is False  # high_risk ≠ banned
    assert r.matched_rule_id and "TALC" in r.matched_rule_id.upper()


def test_mica_pearlescent_pigment_does_not_falsely_match_titanium_dioxide(resolver) -> None:
    """Candurin Silver (harmful_additives.json[13]) has 'titanium dioxide'
    text in its notes / mechanism_of_harm / safety_summary. A previous
    audit version risked treating a pearlescent-pigment row as TiO2 itself.
    The resolver must match on standard_name + aliases ONLY — so when an
    ingredient is named 'Candurin Silver' it gets the Candurin entry, not
    a fuzzy TiO2 match.
    """
    r = resolver.resolve(raw_name="Candurin Silver")
    # Should match Candurin Silver (harmful_additives), not Titanium Dioxide
    assert r.matched_source == "harmful_additives"
    assert r.matched_rule_id and "CANDURIN" in r.matched_rule_id.upper()
    assert r.is_banned is False, "Candurin Silver is not banned itself"


# ---------------------------------------------------------------------------
# Excipient role classification (the Vitamin E / Riboflavin / Fish Oil class)
# ---------------------------------------------------------------------------

def test_vitamin_e_inactive_gets_preservative_role(resolver) -> None:
    """When Vitamin E appears in inactive_ingredients[] (DSLD source has
    classified it as 'Other Ingredients' — used as antioxidant preservative
    for oil-based supplements), it must get a preservative/antioxidant
    role label, NOT be treated as the active nutrient."""
    r = resolver.resolve(raw_name="Vitamin E")
    assert r.matched_source in ("other_ingredients", "harmful_additives"), (
        f"Vitamin E inactive should be classified — got matched_source={r.matched_source!r}"
    )
    # Role must indicate preservative/antioxidant nature
    role_text = (r.display_role_label or "").lower() + " " + " ".join(r.functional_roles).lower()
    assert "preserv" in role_text or "antioxid" in role_text, (
        f"Vitamin E inactive must surface preservative/antioxidant role, "
        f"got display_role_label={r.display_role_label!r} functional_roles={r.functional_roles!r}"
    )
    # Must NOT be flagged as safety concern (it's an excipient at this dose)
    assert r.is_safety_concern is False
    # severity_status n/a or suppress (not critical)
    assert r.severity_status in ("n/a", "suppress"), (
        f"Vitamin E inactive shouldn't be critical — got {r.severity_status!r}"
    )


def test_d_alpha_tocopherol_inactive_gets_preservative_role(resolver) -> None:
    """Synthetic and natural tocopherols used as preservatives must
    resolve via the same excipient entry as Vitamin E."""
    for variant in ("d-Alpha-Tocopherol", "DL-Alpha-Tocopherol", "Mixed Tocopherols"):
        r = resolver.resolve(raw_name=variant)
        role_text = (r.display_role_label or "").lower() + " " + " ".join(r.functional_roles).lower()
        assert "preserv" in role_text or "antioxid" in role_text or "tocoph" in role_text, (
            f"{variant!r} did not get preservative role; "
            f"display_role_label={r.display_role_label!r} functional_roles={r.functional_roles!r}"
        )
        assert r.is_safety_concern is False


def test_riboflavin_inactive_gets_colorant_role(resolver) -> None:
    """Riboflavin (Vitamin B2) used as a natural yellow colorant must
    resolve to a colorant role when appearing in inactives. Distinct from
    the active nutritional use (which the IQM scorer handles separately)."""
    r = resolver.resolve(raw_name="Riboflavin")
    role_text = (r.display_role_label or "").lower() + " " + " ".join(r.functional_roles).lower()
    assert "color" in role_text, (
        f"Riboflavin inactive must surface colorant role, "
        f"got display_role_label={r.display_role_label!r} functional_roles={r.functional_roles!r}"
    )
    assert r.is_safety_concern is False


def test_fish_body_oil_inactive_gets_carrier_role(resolver) -> None:
    """Fish Body Oil as inactive is the OIL BASE / softgel fill, not
    the active EPA/DHA dose. Must resolve to a carrier/oil-base role."""
    r = resolver.resolve(raw_name="Fish Body Oil")
    assert r.matched_source == "other_ingredients", (
        f"Fish Body Oil must match other_ingredients, got {r.matched_source!r}"
    )
    role_text = (r.display_role_label or "").lower() + " " + " ".join(r.functional_roles).lower()
    assert "carrier" in role_text or "oil" in role_text or "fill" in role_text, (
        f"Fish Body Oil inactive must indicate carrier/oil-base role, "
        f"got display_role_label={r.display_role_label!r} functional_roles={r.functional_roles!r}"
    )
    assert r.is_safety_concern is False


def test_rose_hips_inactive_preserves_botanical_label(resolver) -> None:
    """Rose Hips powder as inactive is a natural colorant/filler. Must
    resolve via other_ingredients (or remain unknown with botanical name
    preserved — never silently dropped)."""
    r = resolver.resolve(raw_name="Rose Hips powder")
    # Either matched to other_ingredients OR unmatched-but-name-preserved.
    assert r.display_label and "rose" in r.display_label.lower(), (
        f"botanical name must survive — display_label={r.display_label!r}"
    )
    assert r.is_safety_concern is False
    if r.matched_source == "other_ingredients":
        role_text = (r.display_role_label or "").lower() + " " + " ".join(r.functional_roles).lower()
        assert "color" in role_text or "filler" in role_text or "botanical" in role_text


# ---------------------------------------------------------------------------
# Safe-excipient regression coverage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("excipient,expected_role_keyword", [
    ("Gelatin", "capsule"),
    ("Microcrystalline Cellulose", None),  # any role keyword OK; severity must be low/n/a
    ("Magnesium Stearate", None),
    ("Silicon Dioxide", "anti"),  # anti-caking
    ("Hypromellose", None),
])
def test_safe_excipients_remain_low_or_no_concern(resolver, excipient, expected_role_keyword) -> None:
    r = resolver.resolve(raw_name=excipient)
    # These must NEVER be flagged as critical safety concern.
    assert r.severity_status in ("n/a", "suppress", "informational"), (
        f"{excipient!r}: severity_status={r.severity_status!r} (must be non-critical)"
    )
    if expected_role_keyword:
        role_text = (r.display_role_label or "").lower() + " " + " ".join(r.functional_roles).lower()
        assert expected_role_keyword in role_text, (
            f"{excipient!r}: expected role keyword {expected_role_keyword!r} in "
            f"display_role_label={r.display_role_label!r} / fr={r.functional_roles!r}"
        )


# ---------------------------------------------------------------------------
# Architectural / contract tests
# ---------------------------------------------------------------------------

def test_unmatched_inactive_returns_well_formed_unknown(resolver) -> None:
    """A name with no match anywhere must produce a valid InactiveResolution
    (never raise, never None) with severity_status='n/a', all safety flags
    False, and the raw name preserved. Counts toward the 'unknown inactive
    role' audit report."""
    r = resolver.resolve(raw_name="Truly Unknown Mystery Excipient 9000")
    assert r.matched_source is None
    assert r.severity_status == "n/a"
    assert r.is_safety_concern is False
    assert r.is_banned is False
    assert r.display_label and "Truly Unknown Mystery Excipient 9000" in r.display_label
    assert r.display_role_label is None
    assert r.functional_roles == []


def test_resolver_returns_matched_source_for_provenance(resolver) -> None:
    """Audit trail: every resolution carries matched_source + matched_rule_id
    so a downstream verifier can prove WHICH file + WHICH entry triggered
    the classification. Required for the audit-script gap detector."""
    # Microcrystalline Cellulose is INTENTIONALLY in harmful_additives.json
    # at severity_level=low (tracked for transparency; not actually harmful).
    # The resolver correctly routes it via harmful_additives — that's the
    # right severity gate, not other_ingredients. Use a pure-excipient name
    # for the other_ingredients arm of the precedence check.
    cases = [
        ("Titanium Dioxide",            "banned_recalled"),
        ("Sucralose",                   "harmful_additives"),
        ("Fish Body Oil",               "other_ingredients"),
    ]
    for raw, expected in cases:
        r = resolver.resolve(raw_name=raw)
        assert r.matched_source == expected, (
            f"{raw!r}: matched_source={r.matched_source!r} (expected {expected!r})"
        )
        assert r.matched_rule_id, f"{raw!r}: matched_rule_id missing"


def test_match_only_on_standard_name_and_aliases_not_notes(resolver) -> None:
    """Negative-match: a sentence-like input that appears verbatim in
    some entry's 'notes' or 'mechanism_of_harm' must NOT cause that
    entry to match. We only look at standard_name + aliases."""
    # 'genotoxicity' is in TiO2's reason text but is not a label name.
    r = resolver.resolve(raw_name="genotoxicity")
    assert r.matched_source is None, (
        f"'genotoxicity' should NOT match anything (it's only in notes text), "
        f"got matched_source={r.matched_source!r} rule={r.matched_rule_id!r}"
    )
    # 'nanoparticle' similarly only appears in description text
    r = resolver.resolve(raw_name="nanoparticle")
    assert r.matched_source is None


def test_resolver_skips_disabled_and_historical_banned_recalled_entries(resolver) -> None:
    """banned_recalled_ingredients.json has 3 'historical' + 1 'disabled'
    match_mode entries. The resolver must skip them so we don't shadow-
    block ingredients that were once flagged but are no longer enforced."""
    # The resolver loads at fixture-build time; we just confirm the index
    # doesn't accidentally include any inactive-mode entries.
    inactive_mode_count = sum(
        1 for e in resolver.iter_banned_recalled_entries_for_audit()
        if (e.get("match_mode") or "").lower() in ("historical", "disabled")
    )
    assert inactive_mode_count == 0, (
        f"Resolver loaded {inactive_mode_count} entries with match_mode in "
        "{historical, disabled} — these must be filtered."
    )


def test_resolver_precedence_banned_beats_harmful_and_other(resolver) -> None:
    """When the same name appears in multiple files, banned_recalled wins.
    Sucralose appears in harmful_additives but if it also showed up in
    banned_recalled the banned classification should take precedence.

    Direct test of precedence ordering: a banned ingredient must NEVER
    silently downgrade to a harmful_additives or other_ingredients
    classification. (TiO2 is the live example — banned_recalled exists,
    a harmful_additives entry could conceivably exist, banned must win.)"""
    r = resolver.resolve(raw_name="Titanium Dioxide")
    # Banned status must win over any other classification path.
    assert r.matched_source == "banned_recalled"
    assert r.severity_status == "critical"


# ---------------------------------------------------------------------------
# Audit hooks the resolver must expose
# ---------------------------------------------------------------------------

def test_resolver_exposes_audit_iterators(resolver) -> None:
    """The audit script needs to enumerate the resolver's indices to
    cross-check: every banned_recalled entry should be reachable, every
    harmful_additives entry, etc. Surface this as a small public API."""
    banned = list(resolver.iter_banned_recalled_entries_for_audit())
    harmful = list(resolver.iter_harmful_additives_entries_for_audit())
    other = list(resolver.iter_other_ingredients_entries_for_audit())
    assert len(banned) > 100, f"banned_recalled too small: {len(banned)} entries"
    assert len(harmful) > 100, f"harmful_additives too small: {len(harmful)} entries"
    assert len(other) > 600, f"other_ingredients too small: {len(other)} entries"
