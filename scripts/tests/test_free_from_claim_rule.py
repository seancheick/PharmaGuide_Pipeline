"""A free-from claim is contradicted only by its own allergen group.

Audit of #187 (2026-10-20): Transparency B2
(generic_transparency._score_b2_false_allergen_claim_penalty, shared by the
probiotic, omega and multi/prenatal modules) took 2 points for any free-from
claim plus any may-contain warning, so 328751 (gluten-free, may contain fish
and crustaceans) and 326701 (dairy/gluten/soy-free, fish facility) were
penalized; claim evidence and the app's gluten-free flag (compliance
gluten_free -> core is_gluten_free) used the same global signal. One rule,
scoring_input_contract.free_from_claim_contradiction, now decides per claim
group: a source or cross-contact hit of that group, or a may-contain sentence
no parser read. Gluten cross-contact counts wheat, rye and barley (21 CFR
101.91(a)(1)). Whether a wheat, rye or barley ingredient contradicts a
gluten-free claim is the one switch
GLUTEN_GRAIN_INGREDIENT_CONTRADICTS_GLUTEN_FREE (True, main's B2 result; open
101.91 question for Sean).
"""

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def run():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    from scoring_v4.scored_artifact import build_scored_artifact
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()

    def _run(pid, extra_statements=(), replace=None):
        raw = json.loads((FIXTURES / f"gluten_claim_{pid}_raw.json").read_text(encoding="utf-8"))
        statements = list(raw.get("statements") or [])
        if replace:
            old, new = replace
            statements = [dict(s, notes=(s.get("notes") or "").replace(old, new)) for s in statements]
        raw["statements"] = statements + [{"type": "Precautions", "notes": t} for t in extra_statements]
        enriched, _ = enricher.enrich_product(normalizer.normalize_product(raw))
        transparency = build_scored_artifact(enriched)["_v4_module_breakdown"]["dimensions"]["transparency"]
        return enriched, transparency

    return _run


def _b2(transparency):
    return transparency["penalties"].get("B2_false_allergen_free_claim") or 0.0


def _evidence(enriched, group):
    return [ev for ev in enriched["compliance_data"]["evidence_based"]["allergen_free_claims"]
            if ev.get("dedupe_key") == f"allergen_free:{group}"]


def test_other_allergen_cross_contact_does_not_cost_b2(run):
    # 328751: gluten-free claim; "may contain" fish and crustaceans only.
    enriched, transparency = run("328751")
    assert _b2(transparency) == 0.0
    assert transparency["score"] == pytest.approx(10.0)


def test_fish_facility_keeps_a_dairy_free_claim(run):
    # 326701: dairy-, gluten- and soy-free claims; "facility that also processes fish".
    enriched, transparency = run("326701")
    assert _b2(transparency) == 0.0
    assert enriched["compliance_data"]["dairy_free"] is True
    assert all(ev["score_eligible"] for ev in _evidence(enriched, "dairy"))


def test_milk_facility_still_voids_a_dairy_free_claim(run):
    # 326701 with its fish facility statement changed to milk.
    enriched, transparency = run("326701", replace=("processes fish", "processes milk"))
    assert _b2(transparency) == -1.5  # milk, moderate
    assert enriched["compliance_data"]["dairy_free"] is False
    assert {ev.get("ineligibility_reason") for ev in _evidence(enriched, "dairy")} == {"may_contain_warning"}


def test_real_milk_facility_and_dairy_free_claim_keeps_its_penalty(run):
    # 218190: "produced in a facility that also handles dairy ingredients", claims Dairy Free.
    enriched, transparency = run("218190")
    assert _b2(transparency) == -1.5  # milk, moderate
    assert enriched["claim_gluten_free_validated"] is True


def test_may_contain_barley_clears_the_gluten_free_flag(run):
    enriched, _ = run("304605", extra_statements=("May contain barley.",))
    assert enriched["compliance_data"]["gluten_free"] is False
    assert enriched["claim_gluten_free_validated"] is False


def test_unread_may_contain_still_costs_b2(run):
    enriched, transparency = run("328751", extra_statements=("May contain traces of grain products.",))
    assert _b2(transparency) == -2.0
    assert enriched["claim_gluten_free_validated"] is False


def test_generic_allergen_free_claim_is_contradicted_by_any_warning():
    from scoring_v4.modules.generic_transparency import _score_b2_false_allergen_claim_penalty
    product = {
        "compliance_data": {"allergen_free_claims": ["allergen-free"], "has_may_contain_warning": True, "conflicts": []},
        "allergen_hits": [{"allergen_id": "ALLERGEN_FISH", "presence_type": "facility_warning", "severity_level": "moderate"}],
    }
    assert _score_b2_false_allergen_claim_penalty(product)[0] > 0


@pytest.mark.parametrize("group,hits,unread,expected", [
    ("dairy", [("ALLERGEN_FISH", "facility_warning")], False, None),
    ("dairy", [("ALLERGEN_MILK", "facility_warning")], False, "may_contain_warning"),
    ("dairy", [("ALLERGEN_MILK", "contains")], False, "allergen_conflict"),
    ("gluten", [("ALLERGEN_BARLEY", "may_contain")], False, "may_contain_warning"),
    # GLUTEN_GRAIN_INGREDIENT_CONTRADICTS_GLUTEN_FREE (Sean's 101.91 question) keeps today's B2.
    ("gluten", [("ALLERGEN_BARLEY", "ingredient_list")], False, "allergen_conflict"),
    ("gluten", [("ALLERGEN_WHEAT", "ingredient_list")], False, "allergen_conflict"),
    ("gluten", [("ALLERGEN_OATS", "may_contain")], False, None),
    ("nut", [("ALLERGEN_PEANUTS", "facility_warning")], False, "may_contain_warning"),
    ("egg", [("ALLERGEN_EGGS", "contains")], False, "allergen_conflict"),
    ("soy", [], True, "may_contain_warning"),
    ("yeast", [("ALLERGEN_MILK", "may_contain")], False, None),
])
def test_free_from_claim_rule(group, hits, unread, expected):
    from scoring_input_contract import free_from_claim_contradiction
    hit_dicts = [{"allergen_id": a, "presence_type": p} for a, p in hits]
    assert free_from_claim_contradiction(group, hit_dicts, unparsed_may_contain=unread) == expected


@pytest.mark.parametrize("statement,unread", [
    ("May contain traces of grain products.", True),
    ("(May contain trace amounts less than 20 ppm).", False),  # 273865: a gluten-free qualifier
    ("Manufactured on shared equipment.", True),
    ("If taking other supplements, read label, since supplements may contain the same ingredient.", False),
    ("May contain vegetable glycerin.", False),
    ("May contain: silicon dioxide.", False),
    ("Contains: fish (anchovy and may contain sardine and mackerel).", False),
])
def test_only_allergen_wording_the_parser_cannot_resolve_is_unread(statement, unread):
    # Replay of #187: "may contain" also lists excipients or warns about doubling up;
    # those name no allergen and must not void a free-from claim.
    from enrich_supplements_v3 import SupplementEnricherV3
    product = {"statements": [{"notes": statement}]}
    assert SupplementEnricherV3()._has_unparsed_may_contain(product) is unread


# Re-audit of #187 (2026-10-20).
def test_h1_unread_may_contain_clears_the_gluten_free_badge(run):
    # 293779 OLLY Extra Strength Sleep: "may contain, soy, egg, ... wheat" (stray comma, unread on
    # main's parser). Badge, validation and B2 must give one answer.
    enriched, transparency = run("293779")
    assert enriched["compliance_data"]["gluten_free"] is False
    assert enriched["claim_gluten_free_validated"] is False
    assert _b2(transparency) == -1.5  # wheat facility warning, moderate (read since #188)


def test_h1_a_gluten_ppm_qualifier_is_not_an_unread_warning(run):
    # 273865 Daily Fiber: "Gluten-free. (may contain trace amounts less than 20 ppm)."
    enriched, _ = run("273865")
    assert enriched["compliance_data"]["gluten_free"] is True
    assert enriched["claim_gluten_free_validated"] is True


@pytest.mark.parametrize("pid", ["297644", "274671"])
def test_m1_gluten_grain_ingredient_answers_once(run, pid):
    # Barley/rye as an ingredient: B2 already penalizes it on main; validation and badge agree
    # through GLUTEN_GRAIN_INGREDIENT_CONTRADICTS_GLUTEN_FREE (Sean's open 21 CFR 101.91 question).
    from scoring_input_contract import GLUTEN_GRAIN_INGREDIENT_CONTRADICTS_GLUTEN_FREE
    assert GLUTEN_GRAIN_INGREDIENT_CONTRADICTS_GLUTEN_FREE is True
    enriched, transparency = run(pid)
    assert _b2(transparency) == -1.5  # moderate: barley (297644 also milk facility)
    assert enriched["claim_gluten_free_validated"] is False
    assert enriched["compliance_data"]["gluten_free"] is False


def test_l4_a_shellfish_free_claim_covers_molluscs():
    from scoring_input_contract import free_from_claim_contradiction
    hits = [{"allergen_id": "ALLERGEN_MOLLUSCS", "presence_type": "facility_warning"}]
    assert free_from_claim_contradiction("shellfish", hits) == "may_contain_warning"


def test_l1_allergen_free_validation_uses_the_same_rule(run):
    # 326701: dairy/gluten/soy-free claims, fish facility only: all claims hold.
    enriched, _ = run("326701")
    assert enriched["claim_allergen_free_validated"] is True
    enriched, _ = run("326701", replace=("processes fish", "processes milk"))
    assert enriched["claim_allergen_free_validated"] is False


# The 21 CFR 101.91 "< 20 ppm" exemption covers the qualifier clause only, not
# the whole sentence around it.
@pytest.mark.parametrize("statement,badge", [
    # the qualifier alone (273865's shape) is not an unread warning
    ("(may contain trace amounts less than 20 ppm)", True),
    # an unread may-contain warning next to a ppm note still voids the claim
    ("May contain traces of grains processed on shared lines (tested below 20 ppm).", False),
    # a read may-contain list next to a ppm note still names wheat
    ("May contain soy, egg, milk and wheat (less than 20 ppm gluten).", False),
])
def test_ppm_exemption_is_scoped_to_its_clause(run, statement, badge):
    enriched, _ = run("328751", extra_statements=(statement,))
    assert enriched["compliance_data"]["gluten_free"] is badge
    assert enriched["claim_gluten_free_validated"] is badge


@pytest.mark.parametrize("pid", ["297644", "274671"])
def test_a_barley_ingredient_is_named_a_gluten_grain_source(run, pid):
    enriched, _ = run(pid)
    conflicts = enriched["compliance_data"]["conflicts"]
    assert "gluten-free claim conflicts with a gluten-grain source" in conflicts
    assert not any("cross-contact" in c for c in conflicts)
    assert {ev.get("ineligibility_reason") for ev in _evidence(enriched, "gluten")} == {
        "allergen_conflict:gluten grain detected"}


# B2 magnitude follows the contradicting allergen's severity
# (quality_score.json b2_severity_points: high 2.0, moderate 1.5, low 1.0).
# Since hits carry canonical ids (ALLERGEN_MILK), seen.get(group) never
# matched a group name and every contradiction took the 2.0 cap.
def test_b2_dairy_contradiction_costs_milk_severity(run):
    # 218190: dairy-free claim; "produced in a facility that also handles dairy" (milk, moderate).
    enriched, transparency = run("218190")
    assert _b2(transparency) == -1.5


def test_b2_soy_contradiction_costs_soy_severity(run):
    # 326701 (soy-free claim) with its fish facility statement changed to soy (low).
    enriched, transparency = run("326701", replace=("processes fish", "processes soy"))
    assert _b2(transparency) == -1.0


def test_b2_takes_the_highest_severity_across_contradicted_groups(run):
    # 326701 claims dairy- and soy-free: milk (1.5) and soy (1.0) both contradicted.
    enriched, transparency = run("326701", replace=("processes fish", "processes milk and soy"))
    assert _b2(transparency) == -1.5


def test_b2_high_severity_and_conflict_only_fallback_keep_the_cap():
    from scoring_v4.modules.generic_transparency import _score_b2_false_allergen_claim_penalty
    shellfish = {"compliance_data": {"allergen_free_claims": ["shellfish"]},
                 "contaminant_data": {"allergens": {"allergens": [
                     {"allergen_id": "ALLERGEN_CRUSTACEANS", "presence_type": "facility_warning", "severity_level": "high"}]}}}
    assert _score_b2_false_allergen_claim_penalty(shellfish)[0] == 2.0
    conflict_only = {"compliance_data": {"allergen_free_claims": ["gluten"],
                                         "conflicts": ["gluten-free claim conflicts with detected gluten/wheat"]}}
    assert _score_b2_false_allergen_claim_penalty(conflict_only)[0] == 2.0


# "nut" is a whole word in a claim: "peanut-free" / "no peanuts" is not a
# tree-nut-free claim, so a tree-nut facility does not contradict it.
@pytest.mark.parametrize("text,matches", [
    ("peanut-free", False), ("contains no peanuts", False),
    ("contains no artificial colors. rich in nutrients", False),
    ("nut-free", True), ("tree nut free", True), ("contains no tree nuts", True),
])
def test_nut_free_claim_pattern_is_whole_word(text, matches):
    import re
    from constants import ALLERGEN_FREE_PATTERNS
    assert bool(re.search(ALLERGEN_FREE_PATTERNS["nut"], text, re.I)) is matches


@pytest.mark.parametrize("claim,groups", [
    ("peanut", {"peanut"}), ("Peanut-Free", {"peanut"}),
    ("nut", {"tree_nut"}), ("Nut-Free", {"tree_nut"}),
])
def test_b2_claim_group_reads_nut_as_a_whole_word(claim, groups):
    from scoring_v4.modules.generic_transparency import _allergen_groups_from_text
    assert _allergen_groups_from_text(claim) == groups


def test_tree_nut_facility_does_not_contradict_a_peanut_free_claim(run):
    # 75073: "No dairy, no peanuts, gluten-free."; "Processed in a facility with
    # products that contain egg, fish, shellfish, soy and tree nuts."
    enriched, transparency = run("75073")
    assert _b2(transparency) == 0.0
