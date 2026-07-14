"""Shared schema-version contract for top-level reference-data artifacts."""

from __future__ import annotations

import re
from typing import Any


_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

# Version 1 owns vocabularies and small control artifacts. Version 6 owns the
# interaction/certification/goal contracts. All other top-level reference
# databases remain in the enrichment schema namespace (version 5).
_SCHEMA_V1_FILES = frozenset(
    {
        "botanical_marker_contributions.json",
        "branded_blend_anchor_overrides.json",
        "caers_adverse_event_signals.json",
        "canary_products.json",
        "canonical_equivalences.json",
        "cluster_ingredient_aliases.json",
        "daily_values.json",
        "drug_classes.json",
        "fda_unii_cache.json",
        "interaction_orphan_allowlist.json",
        "medication_profile_gate_rules.json",
        "omega_rubric.json",
        "profile_gate_test_cases.json",
        "unii_exoneration_allowlist.json",
    }
)
_SCHEMA_V6_FILES = frozenset(
    {
        "cert_registry.json",
        "high_dose_rule_exemptions.json",
        "ingredient_interaction_rules.json",
        "user_goals_to_clusters.json",
    }
)


def expected_reference_schema_major(filename: str) -> int:
    """Return the governed schema namespace for a top-level data artifact."""
    if filename.endswith("_vocab.json") or filename in _SCHEMA_V1_FILES:
        return 1
    if filename in _SCHEMA_V6_FILES:
        return 6
    return 5


def validate_reference_schema_version(filename: str, version: Any) -> str | None:
    """Return an actionable issue string, or ``None`` when valid."""
    if not isinstance(version, str) or not version:
        return f"{filename}: schema_version not declared"
    match = _SEMVER_RE.fullmatch(version)
    if match is None:
        return f"{filename}: schema_version={version!r} is not major.minor.patch"
    actual_major = int(match.group(1))
    expected_major = expected_reference_schema_major(filename)
    if actual_major != expected_major:
        return (
            f"{filename}: schema_version={version!r} belongs to namespace "
            f"{actual_major}, expected {expected_major}.x"
        )
    return None
