"""Regression tests for profile-gated warning emission (schema v5.2).

Every warning in the detail blob must carry `display_mode_default`.
The blob also emits `warnings_profile_gated[]` — a subset that excludes
items with `display_mode_default == "suppress"`.

Rationale: without profile gating, the app surfaced scary-looking rules
(berberine + hypoglycemics) to every user regardless of whether they had
the triggering condition or medication. See scripts/SAFETY_DATA_PATH_C_PLAN.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from build_final_db import build_detail_blob  # noqa: E402

# Borrow the full fixture factory from the existing test module so we
# stay lock-step with any future enriched-shape changes.
sys.path.insert(0, str(SCRIPTS_DIR / "tests"))
from test_build_final_db import make_enriched, make_scored  # noqa: E402


def _fixture_with_interaction_severities(*severities: str) -> dict:
    """Build an enriched fixture with interaction rules at the given severities."""
    enriched = make_enriched()
    enriched["interaction_profile"] = {
        "ingredient_alerts": [
            {
                "ingredient_name": f"Test Ingredient {sev}",
                "condition_hits": [
                    {
                        "condition_id": "diabetes",
                        "severity": sev,
                        "mechanism": f"Severity={sev} mechanism.",
                        "action": f"Severity={sev} action.",
                        "sources": [],
                    }
                ],
                "drug_class_hits": [
                    {
                        "drug_class_id": "hypoglycemics",
                        "severity": sev,
                        "mechanism": f"Severity={sev} drug mechanism.",
                        "action": f"Severity={sev} drug action.",
                        "sources": [],
                    }
                ],
            }
            for sev in severities
        ]
    }
    return enriched


def _warnings_by_severity(blob: dict, severity: str, warn_type: str):
    return [
        w for w in blob["warnings"]
        if w.get("severity") == severity and w.get("type") == warn_type
    ]


def test_all_warnings_carry_display_mode_default():
    """Every warning emitted to the blob must declare its display mode."""
    enriched = make_enriched()
    enriched["status"] = "discontinued"
    enriched["discontinuedDate"] = "2025-12-31"
    enriched["contaminant_data"]["banned_substances"]["substances"] = [
        {
            "ingredient": "Vitamin A Palmitate",
            "banned_name": "Vitamin A Palmitate",
            "status": "banned",
            "match_type": "exact",
            "reason": "Regulatory ban.",
        }
    ]
    blob = build_detail_blob(enriched, make_scored())
    missing = [w for w in blob["warnings"] if "display_mode_default" not in w]
    assert not missing, (
        f"every warning must have display_mode_default; missing on "
        f"{[w.get('type') for w in missing]}"
    )


def test_warnings_profile_gated_present_in_blob():
    blob = build_detail_blob(make_enriched(), make_scored())
    assert "warnings_profile_gated" in blob, (
        "blob must emit warnings_profile_gated[] — the default-safe subset "
        "Flutter should render without a user profile"
    )
    assert isinstance(blob["warnings_profile_gated"], list)


def test_caution_severity_is_suppressed_from_profile_gated_subset():
    """Caution-severity interaction rules must not render without profile.

    This is the canonical berberine-scary bug: a caution-severity rule
    firing for every user regardless of declared conditions.
    """
    enriched = _fixture_with_interaction_severities("caution")
    blob = build_detail_blob(enriched, make_scored())

    caution_in_all = [
        w for w in blob["warnings"]
        if w.get("source") == "interaction_rules"
        and w.get("severity") == "caution"
    ]
    caution_in_gated = [
        w for w in blob["warnings_profile_gated"]
        if w.get("source") == "interaction_rules"
        and w.get("severity") == "caution"
    ]
    assert caution_in_all, "caution rule should still appear in superset"
    assert not caution_in_gated, (
        "caution interaction rule must be suppressed from profile-gated "
        "subset; otherwise 'scary-for-everyone' bug returns"
    )


def test_monitor_severity_is_suppressed_from_profile_gated_subset():
    enriched = _fixture_with_interaction_severities("monitor")
    blob = build_detail_blob(enriched, make_scored())
    monitor_in_gated = [
        w for w in blob["warnings_profile_gated"]
        if w.get("source") == "interaction_rules"
        and w.get("severity") == "monitor"
    ]
    assert not monitor_in_gated


def test_avoid_severity_is_downgraded_to_informational():
    """Avoid-severity rules render as informational without profile match.

    Severity_contextual gives Flutter the calmer tier to paint the pill
    when no profile match; severity stays 'avoid' so the alert tier can
    be promoted when the profile does match.
    """
    enriched = _fixture_with_interaction_severities("avoid")
    blob = build_detail_blob(enriched, make_scored())
    avoid_hits = [
        w for w in blob["warnings"]
        if w.get("source") == "interaction_rules"
        and w.get("severity") == "avoid"
    ]
    assert avoid_hits, "fixture should emit avoid-severity interaction warnings"
    for w in avoid_hits:
        assert w["display_mode_default"] == "informational", (
            f"avoid-severity rule must default to informational (not "
            f"suppress or critical); got {w['display_mode_default']}"
        )
        assert w["severity_contextual"] == "informational", (
            f"avoid-severity pill must downgrade to informational without "
            f"profile; got {w['severity_contextual']}"
        )

    # And the informational-tier warning IS in the profile-gated subset.
    avoid_in_gated = [
        w for w in blob["warnings_profile_gated"]
        if w.get("source") == "interaction_rules"
        and w.get("severity") == "avoid"
    ]
    assert avoid_in_gated, (
        "avoid rules default to informational and must render in the "
        "profile-gated subset as neutral notes"
    )


def test_contraindicated_severity_is_always_critical():
    """Contraindicated rules always show — profile irrelevant.

    These are substance-level hazards or absolute contraindications
    (e.g., 5-HTP + MAOI serotonin syndrome) that alarm regardless of
    declared profile.
    """
    enriched = _fixture_with_interaction_severities("contraindicated")
    blob = build_detail_blob(enriched, make_scored())
    contra_hits = [
        w for w in blob["warnings"]
        if w.get("source") == "interaction_rules"
        and w.get("severity") == "contraindicated"
    ]
    assert contra_hits
    for w in contra_hits:
        assert w["display_mode_default"] == "critical"
        assert w["severity_contextual"] == "contraindicated"


def test_banned_substance_is_always_critical():
    """Substance-level bans always render, profile irrelevant."""
    enriched = make_enriched()
    enriched["contaminant_data"]["banned_substances"]["substances"] = [
        {
            "ingredient": "DMAA",
            "banned_name": "DMAA",
            "status": "banned",
            "match_type": "exact",
            "reason": "FDA-banned stimulant.",
        }
    ]
    blob = build_detail_blob(enriched, make_scored())
    banned = [w for w in blob["warnings"] if w.get("type") == "banned_substance"]
    assert banned
    for w in banned:
        assert w["display_mode_default"] == "critical", (
            "substance-level bans must render regardless of profile"
        )
    # And present in the profile-gated subset.
    gated_banned = [
        w for w in blob["warnings_profile_gated"]
        if w.get("type") == "banned_substance"
    ]
    assert gated_banned, (
        "banned substance must be in profile-gated subset — it's a "
        "substance-level hazard, not a conditional rule"
    )


def test_harmful_additive_is_always_critical():
    blob = build_detail_blob(make_enriched(), make_scored())
    harmful = [w for w in blob["warnings"] if w.get("type") == "harmful_additive"]
    assert harmful
    for w in harmful:
        assert w["display_mode_default"] == "critical"


def test_allergen_defaults_informational_not_critical():
    """Allergens default to informational — only critical if user has that
    allergen in their profile. Flutter promotes on-device."""
    blob = build_detail_blob(make_enriched(), make_scored())
    allergens = [w for w in blob["warnings"] if w.get("type") == "allergen"]
    assert allergens
    for w in allergens:
        assert w["display_mode_default"] == "informational"


def test_pipeline_passes_through_authored_fields_when_present():
    """When enricher emits alert_headline/alert_body/informational_note,
    build_detail_blob must pass them through verbatim.

    This is the Phase 4 contract — once the safety team authors these
    fields, the blob must carry them to Flutter with no derivation.
    """
    enriched = make_enriched()
    enriched["interaction_profile"] = {
        "ingredient_alerts": [
            {
                "ingredient_name": "Berberine",
                "condition_hits": [],
                "drug_class_hits": [
                    {
                        "drug_class_id": "hypoglycemics",
                        "severity": "avoid",
                        "mechanism": "mech",
                        "action": "act",
                        "alert_headline": "May boost your diabetes medication",
                        "alert_body": (
                            "Berberine lowers blood sugar like metformin. "
                            "If you take a diabetes medication, monitor "
                            "glucose and talk to your prescriber."
                        ),
                        "informational_note": (
                            "Berberine has blood-sugar-lowering effects "
                            "relevant to people on diabetes medications."
                        ),
                    }
                ],
            }
        ]
    }
    blob = build_detail_blob(enriched, make_scored())
    matches = [
        w for w in blob["warnings"]
        if w.get("source") == "interaction_rules"
        and w.get("drug_class_id") == "hypoglycemics"
    ]
    assert matches
    w = matches[0]
    assert w["alert_headline"] == "May boost your diabetes medication"
    assert w["alert_body"].startswith("Berberine lowers blood sugar")
    assert "informational_note" in w and w["informational_note"] is not None
