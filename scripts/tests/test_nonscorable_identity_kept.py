"""A row the enricher will not score keeps the identity the label names.

Non-scorability is a row role, not evidence against the substance. The
enricher re-validated the cleaner's identity on non-scorable rows only by an
exact literal, structured or taxonomy match, so a row the cleaner identified
through its descriptor preprocessing ("Caffeine Blend", "Lactobacillus",
"Arginine" under a whey blend, the last proved by UNII 94ZLA3W45F) lost its
identity, and with it every interaction rule (951a05415 capture: 90 rows). The
row stays unscored; only a label that names a different substance, or a role
record (a proprietary blend), keeps it from the supplied identity.

Blend headers are left out for now: a header identity would carry the blend
total into scoring routes ("Caffeine Blend" stays unresolved, so Ravage keeps
main's caffeine warning gap until the header follow-up). Restoring a row's
identity must not route a product either: a blend total lent to an identified
member is not that member's amount (327570).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from identity_integrity import build_canonical_identity_registry, resolve_identity  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def enrich():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    cache = {}

    def run(dsld_id: int) -> dict:
        if dsld_id not in cache:
            raw = json.loads((FIXTURES / f"nonscorable_identity_{dsld_id}_raw.json").read_text())
            cache[dsld_id], _ = enricher.enrich_product(normalizer.normalize_product(raw))
        return cache[dsld_id]

    return run


@pytest.mark.parametrize(
    "dsld_id,label,canonical_id,rule_id",
    [
        # Perfect Food Green Superfood: "Lactobacillus" in a probiotic blend.
        (233668, "Lactobacillus", "probiotics", "RULE_IQM_PROBIOTICS_IMMUNOCOMPROMISED"),
        # Amplified Wheybolic Extreme 60: "Arginine" in the amino acid profile.
        (176044, "Arginine", "l_arginine", "RULE_IQM_L_ARGININE_HYPERTENSION"),
    ],
)
def test_non_scorable_row_keeps_its_identity_and_meets_its_rules(enrich, dsld_id, label, canonical_id, rule_id):
    enriched = enrich(dsld_id)
    iqd = enriched["ingredient_quality_data"]
    rows = [r for r in iqd["ingredients"] + iqd["ingredients_skipped"] if r.get("raw_source_text") == label]
    assert rows and {r["canonical_id"] for r in rows} == {canonical_id}
    assert all(r["identity_disposition"] == "taxonomy_only" and r["scoreable_identity"] is False for r in rows)
    alerts = [a for a in enriched["interaction_profile"]["ingredient_alerts"] if a["rule_id"] == rule_id]
    assert label in {a["ingredient_name"] for a in alerts}


def test_blend_header_is_not_restored_yet(enrich):
    """1179 "Caffeine Blend" is a weight-only blend header: out of this batch."""
    iqd = enrich(1179)["ingredient_quality_data"]
    rows = [r for r in iqd["ingredients"] if r.get("raw_source_text") == "Caffeine Blend"]
    assert rows and {r["canonical_id"] for r in rows} == {None}


def test_identified_food_blend_member_does_not_route_a_vitamin_product(enrich):
    """327570 Methyl B12: the restored "Beet" inside a 242 mg Food Blend borrows the
    blend's mass; it cannot make the B12/B6/folate product botanical-owned."""
    from scoring_v4.scored_artifact import build_scored_artifact

    enriched = enrich(327570)
    iqd = enriched["ingredient_quality_data"]
    assert {r["canonical_id"] for r in iqd["ingredients"] if r.get("raw_source_text") == "Beet"} == {"beetroot"}
    dims = build_scored_artifact(enriched)["_v4_module_breakdown"]["dimensions"]
    assert dims["formulation"]["metadata"]["formulation_profile"] == "generic_iqm"
    assert dims["dose"]["metadata"]["method"] != "botanical_clinical_dose_v1"


_REGISTRY = {
    "ingredient_quality_map": {
        "caffeine": {"standard_name": "Caffeine", "aliases": []},
        "guarana": {"standard_name": "Guarana", "aliases": []},
    },
    "proprietary_blends": {"proprietary_blend_concerns": [
        {"id": "BLEND_SUPERFOOD", "standard_name": "Superfood Blend", "blend_terms": []},
    ]},
}


def _decide(label: str, supplied: str, standard_name: str, **row):
    return resolve_identity(
        row={"raw_source_text": label, "standardName": standard_name, **row},
        supplied_canonical_id=supplied,
        resolve_candidate=lambda value: "guarana" if "guarana" in value.casefold() else None,
        allow_unscoreable_taxonomy_only=True,
        canonical_registry=build_canonical_identity_registry(_REGISTRY),
    )


def test_uncontradicted_supplied_identity_is_kept_unscored():
    decision = _decide("Caffeine Blend", "caffeine", "Caffeine")
    assert (decision.disposition, decision.canonical_id, decision.scoreable_identity) == (
        "taxonomy_only", "caffeine", False,
    )


def test_label_naming_another_substance_still_wins():
    assert _decide("Guarana seed extract", "caffeine", "Caffeine").canonical_id is None


def test_stale_id_the_row_never_named_is_not_kept():
    """The cleaner's standardName for "Antimony" is not caffeine."""
    assert _decide("Antimony", "caffeine", "Antimony").canonical_id is None


def test_blend_header_row_is_not_kept():
    assert _decide("Caffeine Blend", "caffeine", "Caffeine", cleaner_row_role="blend_header_total").canonical_id is None


def test_role_record_is_not_kept_as_a_substance():
    assert _decide("Raw Certified Organic Superfood Blend", "BLEND_SUPERFOOD", "Superfood Blend").canonical_id is None
