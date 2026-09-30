"""Who may own a product's Evidence (evidence_zero_rootcause_20260929, lane 2).

A blend or marketing name, a descriptor, and a blend total lent to its first
child never own Evidence; the blend's disclosed active members do, with no
dose (Dose and Transparency charge the blend). Real DSLD labels:
- 212273 BP Manager: "Proprietary Herbal Blend 519 mg" (stevia, olive leaf,
  hawthorn, lycopene) lent its mass to stevia, and the blend name owned too.
- 251549 DIM-plus: "Protectamins Vegetable Blend" owned Evidence.
- 219048 Fiber Fusion: "Proprietary Fiber Blend" owned beside psyllium.
- 321604 Ultra Triple Action Joint Health: UC-II blend 401 mg, boron 5 mg,
  hyaluronic acid 3.3 mg.

Prominence (who the product is about, which the primary-evidence floor
needs) is the role owner's decision (classify_ingredient_roles), read against
the whole label; it is never inherited from, or recomputed out of, a blend's
mass.
"""

import json
import logging
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from enrich_supplements_v3 import SupplementEnricherV3  # noqa: E402
from evidence_resolver import evidence_owner_canonicals  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def enriched():
    from enhanced_normalizer import EnhancedDSLDNormalizer

    logging.disable(logging.INFO)
    enricher, normalizer = SupplementEnricherV3(), EnhancedDSLDNormalizer()
    out = {}
    for dsld_id in ("212273", "251549", "219048", "321604"):
        raw = json.loads((FIXTURES / f"evidence_subject_{dsld_id}_raw.json").read_text())
        out[dsld_id], _ = enricher.enrich_product(normalizer.normalize_product(raw))
    return out


def test_blend_members_own_evidence_not_the_sweetener_or_blend_name(enriched):
    owners = evidence_owner_canonicals(enriched["212273"])
    assert {"hawthorn", "lycopene"} <= owners
    assert "nha_stevia" not in owners
    assert "superfood_greens_herbal_blends" not in owners


def test_a_minted_blend_name_never_owns_evidence(enriched):
    owners = evidence_owner_canonicals(enriched["251549"])
    assert "diindolylmethane" in owners
    assert "protectamins_vegetable_blend" not in owners


def test_a_named_active_keeps_evidence_when_the_blend_name_leaves(enriched):
    """Psyllium, not "Proprietary Fiber Blend", owns Fiber Fusion's Evidence.
    Ownership grants no prominence: lane 2 leaves the primary-evidence floor as
    it was. (That floor still reads the blend header's mass for an undisclosed
    member, a pre-existing proxy that rewards withholding an amount; changing
    it is a prominence-policy decision, ledger R4.)"""
    owners = evidence_owner_canonicals(enriched["219048"])
    assert "psyllium" in owners
    assert "proprietary_fiber_blend" not in owners


def test_a_small_add_on_is_not_prominent_beside_an_undisclosed_blend(enriched):
    """Boron 5 mg beside a 401 mg blend is not what the product is about: the
    UC-II blend's member (collagen) owns Evidence alone; boron and hyaluronic
    acid do not. (The floor itself still reads the UC-II header's mass through
    the unchanged mass rules.)"""
    assert evidence_owner_canonicals(enriched["321604"]) == {"collagen"}


def test_lent_blend_mass_never_reaches_a_dose_reader(enriched):
    """Milligrams are never inherited: every row carrying a blend total lent to
    a child is invisible to Dose, including when it names an Evidence subject,
    and stevia (not assessable) is never a subject through it."""
    from scoring_input_contract import get_evidence_subject_rows, get_scoring_ingredients, is_lent_blend_mass
    from scoring_v4.modules.generic_helpers import has_usable_individual_dose

    for product in enriched.values():
        lent = [r for r in get_scoring_ingredients(product, strict=True).rows if is_lent_blend_mass(r)]
        assert not any(has_usable_individual_dose(r) for r in lent)
        subjects = get_evidence_subject_rows(product)
        assert not any(has_usable_individual_dose(r) for r in subjects if is_lent_blend_mass(r))
    assert "nha_stevia" not in {r.get("canonical_id") for r in get_evidence_subject_rows(enriched["212273"])}


def test_reviewed_form_members_inherit_their_blend_role(monkeypatch):
    """The cleaner expands forms[] only for exact reviewed blend headers.
    Once expanded, those real members follow the same Evidence ownership rule
    as nestedRows[] members."""
    import evidence_resolver as resolver

    subjects = [
        {"canonical_id": "spirulina", "raw_source_path": "ingredientRows[0].forms[0]"},
        {"canonical_id": "chlorella", "raw_source_path": "ingredientRows[0].forms[1]"},
    ]
    subject_roles = [{"role": "adjunct"}, {"role": "adjunct"}]
    headers = [{"canonical_id": "greens_blend", "raw_source_path": "ingredientRows[0]"}]
    header_roles = [{"role": "major"}]
    monkeypatch.setattr(
        resolver,
        "_evidence_subject_roles",
        lambda product, module: (subjects, subject_roles, headers, header_roles),
    )
    assert resolver.evidence_owner_canonicals({}) == {"spirulina", "chlorella"}


def test_expanded_member_keeps_a_title_named_parent_role():
    from scoring_input_contract import ROLE_CLAIM_PROMINENT, classify_ingredient_roles

    row = {
        "canonical_id": "spirulina",
        "name": "Spirulina",
        "parent_blend": "Super Greens Whole Food Blend",
        "raw_source_path": "ingredientRows[0].forms[0]",
        "source_section": "active",
        "score_eligible_by_cleaner": True,
        "scoreable_identity": True,
    }
    role = classify_ingredient_roles(
        {"product_name": "Super Greens"}, module="generic", rows=[row]
    )[0]
    assert role["role"] == ROLE_CLAIM_PROMINENT
    assert role["role_source"] == "product_name"


def test_a_nested_member_is_not_made_prominent_by_its_parent_name():
    """A nestedRows[] member keeps its header row, so the title role stays
    the header's (Evidence reads it through the blend tier); the shared role
    owner does not promote every member of a title-named blend."""
    from scoring_input_contract import ROLE_CLAIM_PROMINENT, classify_ingredient_roles

    row = {
        "canonical_id": "spirulina",
        "name": "Spirulina",
        "parent_blend": "Super Greens Whole Food Blend",
        "raw_source_path": "ingredientRows[0].nestedRows[0]",
        "source_section": "active",
        "score_eligible_by_cleaner": True,
        "scoreable_identity": True,
    }
    role = classify_ingredient_roles(
        {"product_name": "Super Greens"}, module="generic", rows=[row]
    )[0]
    assert role["role"] != ROLE_CLAIM_PROMINENT


@pytest.mark.parametrize("dsld_id", ["212273", "251549", "219048", "321604"])
def test_owners_are_the_same_inside_and_outside_the_scoring_scope(enriched, dsld_id):
    """The enricher asks outside a scoring pass, the scorer inside one: one
    provider must give both the same owners (rows are rebuilt per call outside
    the scope, so subjects are never matched by object identity)."""
    from scoring_input_contract import scoring_input_scope

    from evidence_resolver import _evidence_subject_roles

    def split(product):
        subjects, _, others, other_roles = _evidence_subject_roles(product, None)
        return (
            evidence_owner_canonicals(product),
            len(subjects),
            [(r.get("canonical_id"), r.get("raw_source_path"), x.get("role")) for r, x in zip(others, other_roles)],
        )

    product = enriched[dsld_id]
    outside = split(product)
    with scoring_input_scope(product):
        inside = split(product)
    assert outside == inside
