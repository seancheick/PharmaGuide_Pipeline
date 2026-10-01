"""Generic Evidence reads prominence from the shared role owner (Phase 2).

``scoring_input_contract.classify_ingredient_roles`` decides which label rows
the product is about; ``evidence_resolver.evidence_prominent_row_keys`` is the
same owner decision read per row. Generic Evidence consumes it for the primary
floor anchor, the nutrition-authority floor, ingredient-evidence recovery and
collagen recovery instead of choosing a primary by mass.

The primary floor keeps one relative-mass comparison, on purpose: records
without a studied minimum have no other amount judgment in Evidence, so that
comparison is the uncovered exposure stand-in required by the Evidence -> Dose
transfer invariant. It never decides which row is the purpose.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from tests.test_v4_generic_evidence_p133 import _ingredient, _match, _product


FIXTURES = Path(__file__).parent / "fixtures"


def _raw(fixture: str) -> dict:
    return json.loads((FIXTURES / fixture).read_text())


def _enrich(fixture) -> dict:
    """Clean -> Enrich a raw DSLD label (a fixture name or an edited raw dict)."""
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3

    logging.disable(logging.INFO)
    raw = _raw(fixture) if isinstance(fixture, str) else fixture
    return SupplementEnricherV3().enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))[0]


def _evidence(product: dict) -> dict:
    """The production Evidence dimension behind the public artifact."""
    from scoring_v4.scored_artifact import build_scored_artifact

    artifact = build_scored_artifact(product)
    return artifact["_v4_module_breakdown"]["dimensions"]["evidence"]


def _scored(product: dict) -> dict:
    from scoring_v4.modules.generic_evidence import score_evidence

    return score_evidence(product, apply_primary_floor=True, owner_scoped=True)


def _row(name, canonical_id, quantity, unit="mg", path=None, **extra):
    row = _ingredient(name=name, canonical_id=canonical_id, quantity=quantity, unit=unit)
    if path:
        row["raw_source_path"] = path
    row.update(extra)
    return row


# --- the owner decision, read per row ---------------------------------------

@pytest.mark.parametrize("leucine_mg", [1, 100, 10000])
def test_an_unrelated_ingredients_mass_never_changes_the_declared_purpose(leucine_mg):
    from evidence_resolver import evidence_owner_canonicals, evidence_prominent_row_keys

    product = _product(
        product_name="Sleep Melatonin",
        ingredients=[
            _row("Melatonin", "melatonin", 5, path="ingredientRows[0]"),
            _row("L-Leucine", "l_leucine", leucine_mg, path="ingredientRows[1]"),
        ],
        matches=[],
    )

    assert evidence_owner_canonicals(product) == {"melatonin"}
    assert evidence_prominent_row_keys(product) == {("ingredientRows[0]", "melatonin")}


def test_when_the_owner_names_no_purpose_the_previous_floors_stand_and_nothing_is_recovered():
    """Retain-everything fallback (real 315700, Trace Minerals): the role owner
    names no purpose row, so there is no prominence to read. The authority
    floor keeps its previous heaviest-essential rule and recovery has no
    identified purpose to borrow evidence for."""
    from evidence_resolver import evidence_prominent_row_keys
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches

    product = _enrich("prominence_owner_abstains_315700_raw.json")
    assert evidence_prominent_row_keys(product) == set()
    assert resolved_clinical_matches(product, owner_scoped=True)[1] == []
    evidence = _evidence(product)
    assert evidence["metadata"]["nutrition_authority_canonical"] == "manganese"
    assert evidence["components"]["primary_evidence_floor"] == 10.0


# --- the primary floor --------------------------------------------------------

def test_a_heavier_undeclared_adjunct_never_anchors_the_floor():
    product = _product(
        product_name="Melatonin 3 mg",
        ingredients=[_row("Melatonin", "melatonin", 3, path="ingredientRows[0]"),
                     _row("L-Theanine", "l_theanine", 200, path="ingredientRows[1]")],
        matches=[_match(id="INGR_L_THEANINE", ingredient="L-Theanine",
                        standard_name="L-Theanine", study_type="rct_multiple",
                        matched_source_row_refs=["ingredientRows[1]"])],
    )

    payload = _scored(product)

    assert payload["metadata"]["evidence_owner_canonicals"] == ["melatonin"]
    assert payload["metadata"]["primary_evidence_floor"] == 0.0


def test_the_retained_exposure_stand_in_still_blocks_a_trace_declared_anchor():
    """Both are declared, but 2.5 mcg of vitamin D beside 600 mg of calcium is
    not floored at the consensus tier: no owner judges that anchor's exposure
    yet (decision packet D26). Calcium, the heavier declared purpose, anchors."""
    product = _product(
        product_name="Calcium with Vitamin D3",
        ingredients=[_row("Calcium", "calcium", 600, path="ingredientRows[0]"),
                     _row("Vitamin D3", "vitamin_d", 2.5, unit="mcg", path="ingredientRows[1]")],
        matches=[
            _match(id="INGR_CALCIUM", ingredient="Calcium", standard_name="Calcium",
                   matched_source_row_refs=["ingredientRows[0]"]),
            _match(id="INGR_VITAMIN_D3", ingredient="Vitamin D3", standard_name="Vitamin D3",
                   matched_source_row_refs=["ingredientRows[1]"]),
        ],
    )

    payload = _scored(product)

    assert payload["metadata"]["primary_evidence_floor_canonical"] == "calcium"
    assert payload["metadata"]["primary_evidence_floor"] == 14.0


def test_the_retained_stand_in_reads_the_prominent_rows_own_amount():
    """The exposure stand-in measures the purpose row. A match that also
    references another identity's heavier row cannot pass on that row's mass."""
    product = _product(
        product_name="Melatonin",
        ingredients=[_row("Melatonin", "melatonin", 1, path="ingredientRows[0]"),
                     _row("L-Theanine", "l_theanine", 400, path="ingredientRows[1]")],
        matches=[_match(id="INGR_MELATONIN", ingredient="Melatonin", standard_name="Melatonin",
                        study_type="rct_multiple",
                        matched_source_row_refs=["ingredientRows[0]", "ingredientRows[1]"])],
    )

    assert _scored(product)["metadata"]["primary_evidence_floor"] == 0.0


def test_real_the_stand_in_keeps_reading_the_purposes_own_identity_rows():
    """Sambucus (204048): the title-named 250 mg extract carries a nested
    "Elderberries 16 g" source row of the same identity. Excluding only other
    identities keeps the previous stand-in result for this record."""
    evidence = _evidence(_enrich("prominence_source_equivalent_204048_raw.json"))
    assert evidence["metadata"]["primary_evidence_floor_canonical"] == "elderberry extract"


def test_clinical_dose_gate_still_blocks_a_declared_purpose():
    product = _product(
        product_name="Melatonin 0.5 mg",
        ingredients=[_row("Melatonin", "melatonin", 0.5, path="ingredientRows[0]")],
        matches=[_match(id="INGR_MELATONIN", ingredient="Melatonin", standard_name="Melatonin",
                        min_clinical_dose=1.0, dose_unit="mg",
                        matched_source_row_refs=["ingredientRows[0]"])],
    )

    payload = _scored(product)

    assert payload["metadata"]["primary_evidence_floor"] == 0.0
    assert "SUB_CLINICAL_DOSE_DETECTED" in payload["metadata"]["flags"]


# --- the nutrition-authority floor --------------------------------------------

@pytest.mark.parametrize("root_mg,authority", [(600, None), (5, "zinc")])
def test_authority_floor_keeps_the_heaviest_declared_owner_exposure_stand_in(root_mg, authority):
    """Both rows are named in the title, so both are the product's purpose. Being
    the heaviest declared owner is not prominence but the retained exposure
    stand-in (D26): only generic Dose judges DRI adequacy, sports and fiber Dose
    do not, and the transfer packet forbids a route-specific exception."""
    from scoring_v4.modules.generic_evidence import NUTRITION_AUTHORITY_FLOOR

    product = _product(
        product_name="Zinc + Novel Root",
        ingredients=[_row("Zinc", "zinc", 15, path="ingredientRows[0]"),
                     _row("Novel Root", "novel_root", root_mg, path="ingredientRows[1]")],
        matches=[],
    )

    payload = _scored(product)

    assert payload["metadata"]["nutrition_authority_canonical"] == authority
    if authority:
        assert payload["components"]["primary_evidence_floor"] == NUTRITION_AUTHORITY_FLOOR


def test_authority_floor_needs_a_disclosed_amount():
    product = _product(
        product_name="Zinc Blend",
        ingredients=[_row("Zinc Blend", "zinc_blend", 300, path="ingredientRows[0]",
                          is_proprietary_blend=True, cleaner_row_role="blend_header_total"),
                     _row("Zinc", "zinc", None, unit=None, path="ingredientRows[0].nestedRows[0]")],
        matches=[],
    )

    assert _scored(product)["metadata"]["nutrition_authority_canonical"] is None


# --- recovery ----------------------------------------------------------------

@pytest.mark.parametrize("nac_mg,recovered", [(400, False), (600, True)])
def test_ingredient_recovery_keeps_the_retained_exposure_stand_in(nac_mg, recovered):
    """The title declares NAC, so the role owner, not milk thistle, decides the
    purpose. Recovery still keeps the baseline half-heaviest comparison as the
    exposure stand-in (D26): 199 of 210 records carry no studied minimum."""
    product = _product(
        product_name="NAC with Milk Thistle",
        ingredients=[_row("N-Acetyl Cysteine", "nac", nac_mg, path="ingredientRows[0]",
                          standard_name="N-Acetylcysteine"),
                     _row("Milk Thistle", "milk_thistle", 1000, path="ingredientRows[1]")],
        matches=[],
    )

    assert ("INGR_NAC" in _scored(product)["metadata"]["recovered_matches"]) is recovered


def test_ingredient_recovery_never_serves_a_co_active_the_label_does_not_declare():
    product = _product(
        product_name="Milk Thistle Liver Support",
        ingredients=[_row("Milk Thistle", "milk_thistle", 1000, path="ingredientRows[0]"),
                     _row("N-Acetyl Cysteine", "nac", 600, path="ingredientRows[1]",
                          standard_name="N-Acetylcysteine")],
        matches=[],
    )

    assert "INGR_NAC" not in _scored(product)["metadata"]["recovered_matches"]


def test_collagen_recovery_follows_prominence():
    collagen = _row("Collagen Peptides", "collagen", 20, unit="Gram(s)", path="ingredientRows[0]",
                    standard_name="Collagen")
    declared = _product(product_name="Collagen Peptides", ingredients=[collagen], matches=[])
    assert _scored(declared)["metadata"]["recovered_matches"] == ["RECOVERED_COLLAGEN_PEPTIDES_V1"]

    token = _product(
        product_name="Biotin 5000 mcg",
        ingredients=[_row("Biotin", "vitamin_b7_biotin", 5000, unit="mcg", path="ingredientRows[0]"),
                     _row("Collagen Peptides", "collagen", 2, path="ingredientRows[1]",
                          standard_name="Collagen")],
        matches=[],
    )
    assert "RECOVERED_COLLAGEN_PEPTIDES_V1" not in _scored(token)["metadata"]["recovered_matches"]


def test_collagen_recovery_keeps_the_retained_exposure_stand_in():
    """Keep D26's existing half-of-heaviest recovery safeguard until its
    replacement is approved, even though the recovered minimum is now bound
    to the peptide row itself."""
    product = _product(
        product_name="Collagen Complex",
        ingredients=[
            _row("Bovine Hide Collagen", "collagen", 10, unit="g", path="ingredientRows[0]",
                 standard_name="Collagen"),
            _row("Hydrolyzed Collagen Peptides Type I & III", "collagen", 300,
                 path="ingredientRows[1]", standard_name="Collagen"),
        ],
        matches=[],
    )

    assert "RECOVERED_COLLAGEN_PEPTIDES_V1" not in _scored(product)["metadata"]["recovered_matches"]


# --- real DSLD labels through Clean -> Enrich -> Score ---------------------

def test_real_218600_a_lineage_owned_complex_never_demotes_the_active_it_supplies():
    """Solgar 218600 prints Phosphatidylserine 200 mg with its 1,000 mg
    supplying complex nested under it. The contract's competitor rule drops
    that complex (same mass counted twice), so the role owner's mass ratio must
    too (role test in test_v4_role_classification): PS stays the material
    purpose and keeps its floor."""
    from evidence_resolver import evidence_prominent_row_keys

    product = _enrich("prominence_lineage_218600_raw.json")
    assert ("ingredientRows[2]", "phosphatidylserine") in evidence_prominent_row_keys(product)
    evidence = _evidence(product)
    assert evidence["metadata"]["primary_evidence_floor_canonical"] == "phosphatidylserine"
    assert evidence["components"]["primary_evidence_floor"] == 14.0


def test_real_210555_disclosed_members_of_the_title_named_blend_anchor_the_floor():
    """GNC Test 1700: the title names the "Test 1700 Activator" blend, whose
    disclosed members (Testofen 600 mg, KSM-66 600 mg) are the purpose."""
    from evidence_resolver import evidence_prominent_row_keys

    product = _enrich("prominence_blend_members_210555_raw.json")
    keys = evidence_prominent_row_keys(product)
    assert ("ingredientRows[2].nestedRows[0]", "fenugreek") in keys
    assert ("ingredientRows[2].nestedRows[1]", "ashwagandha") in keys
    assert not {key for key in keys if key[1] in {"magnesium", "zinc"}}
    evidence = _evidence(product)
    assert evidence["metadata"]["primary_evidence_floor_canonical"] == "testofen fenugreek"
    assert evidence["components"]["primary_evidence_floor"] == 18.0


@pytest.mark.parametrize("fixture,member", [
    ("prominence_blend_total_328062_raw.json", "ashwagandha"),  # Sensoril in a 2-member 250 mg blend
    ("evidence_subject_219048_raw.json", "psyllium"),            # psyllium under a 3.1 g fiber blend
    ("blend_2219_raw.json", "creatine_monohydrate"),             # one of ten in a 3.1 g creatine module
])
def test_real_blend_total_never_becomes_an_undisclosed_members_floor(fixture, member):
    """The member stays an Evidence owner and keeps its research points, but its
    own amount is not on the label, so the blend total cannot anchor a floor."""
    evidence = _evidence(_enrich(fixture))
    assert member in evidence["metadata"]["evidence_owner_canonicals"]
    assert evidence["metadata"]["primary_evidence_floor"] == 0.0
    assert evidence["components"]["clinical_evidence_pipeline"] > 0


@pytest.mark.parametrize("fixture,floor_canonical,floor", [
    # "Relora 175 mg": the heading is the branded intervention itself
    ("prominence_branded_heading_293928_raw.json", "relora", 17.0),
    # "UC-II Proprietary Cartilage Blend 401 mg"
    ("evidence_subject_321604_raw.json", "uc ii undenatured type ii collagen", 18.0),
])
def test_real_heading_that_names_its_brand_anchors_that_brands_floor(fixture, floor_canonical, floor):
    """A blend heading's printed total is not a member's dose, but when the
    heading itself names a verified branded record, that total is the studied
    intervention's amount. The prominent label row keeps that record's floor."""
    evidence = _evidence(_enrich(fixture))
    assert evidence["metadata"]["primary_evidence_floor_canonical"] == floor_canonical
    assert evidence["components"]["primary_evidence_floor"] == floor


@pytest.mark.parametrize("fixture,recovered,evidence", [
    # title-named La-14 at 0.5 mg beside a 100 million CFU total: never "the clear primary"
    ("prominence_probiotic_species_236913_raw.json", [], 0.0),
    # Q53: BB536 cannot inherit the reference-only 35624/1714 species summary.
    ("prominence_probiotic_species_232059_raw.json", [], 0.0),
])
def test_real_probiotic_inputs_respect_reviewed_species_applicability(fixture, recovered, evidence):
    """Recovery cannot revive reference-only species credit after Q53.
    The native exact-strain owner determines Evidence independently."""
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches
    from scoring_v4.scored_artifact import build_scored_artifact

    _, found = resolved_clinical_matches(_enrich(fixture), assess_amount=False)
    assert [entry.get("id") for entry in found] == recovered
    assert build_scored_artifact(_enrich(fixture))["quality_pillars_v4"]["evidence"]["score"] == evidence


@pytest.mark.parametrize("fixture,record,floor_canonical", [
    # INGR_GARLIC already links the 1,000 mg powder and its Allicin/Alliin rows
    ("prominence_rerecovery_217818_raw.json", "INGR_GARLIC", "garlic extract"),
    # INGR_OMEGA3 already links EPA, DHA and ALA
    ("prominence_rerecovery_1838_raw.json", "INGR_OMEGA3", "omega 3 fatty acids"),
])
def test_real_recovery_never_restamps_a_record_onto_a_row_it_already_links(
    fixture, record, floor_canonical,
):
    """Recovery supplies evidence enrichment did not link. Re-stamping an
    existing record onto one of its own rows would only narrow its source
    references (to a 1.5 mg Allicin marker, or to plant ALA)."""
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches

    product = _enrich(fixture)
    matches, recovered = resolved_clinical_matches(product, owner_scoped=True)
    assert recovered == []
    entry = next(m for m in matches if m.get("id") == record)
    assert len(entry.get("matched_source_row_refs") or []) > 1
    assert _evidence(product)["metadata"]["primary_evidence_floor_canonical"] == floor_canonical


def test_real_bcaa_record_still_binds_to_its_disclosed_aggregate():
    """Essential Amino Complete (220827): "Branched-Chain Amino Acids 5 g" lists
    leucine 2.5 g, isoleucine 1.25 g and valine 1.25 g. The BCAA record is for the
    whole mixture, so recovery's existing aggregate exception binds it to the 5 g
    aggregate. The no-re-stamp rule (for markers and plant ALA) must not undo
    that designed binding."""
    evidence = _evidence(_enrich("prominence_bcaa_aggregate_220827_raw.json"))
    assert evidence["metadata"]["primary_evidence_floor_canonical"] == "bcaa"


@pytest.mark.parametrize("record,label_text,expected", [
    ("BRAND_UCII", "uc ii proprietary cartilage blend", True),
    ("BRAND_BCM95", "bcm 95 turmeric extract", True),
    ("BRAND_EGB761", "ginkgo biloba leaf extract egb 761", True),
    # a descriptive alias never names the brand
    ("BRAND_RELORA", "magnolia phellodendron extract", False),
])
def test_a_brand_identifier_matches_as_labels_spell_it(record, label_text, expected):
    """The brand's own identifier, spelled with a hyphen or space on the label
    (UC-II, BCM-95, EGb 761), names the branded record; descriptive aliases
    stay excluded."""
    from scoring_v4.modules.generic_evidence import (
        _verified_product_entry_matches_text,
        _verified_product_level_evidence_entries,
    )

    entry = next(e for e in _verified_product_level_evidence_entries() if e["id"] == record)
    assert _verified_product_entry_matches_text(entry, label_text) is expected


@pytest.mark.parametrize("fixture", [
    # the title-named "Epsom Salt" row carries the 3.4 g Remove blend total lent to it
    "prominence_lent_essential_273823_raw.json",
    # fiber route: 500 mg calcium is declared, 4 g fiber is the heaviest owner
    "prominence_authority_fiber_route_177088_raw.json",
    # "Calcium BHB": 233 mg calcium beside 1,238 mg BHB
    "prominence_authority_salt_title_311247_raw.json",
])
def test_real_authority_floor_needs_the_heaviest_owner_with_its_own_amount(fixture):
    assert _evidence(_enrich(fixture))["metadata"]["nutrition_authority_canonical"] is None


def test_real_authority_floor_reads_purpose_by_identity_not_by_row():
    """Calcium Ascorbate 1 g (306193): the title names the "Calcium Ascorbate"
    row, while the heaviest vitamin C row is the "Vitamin C 900 mg" line. The
    owner's purpose is vitamin C either way, so the authority floor stands."""
    evidence = _evidence(_enrich("prominence_authority_compound_row_306193_raw.json"))
    assert evidence["metadata"]["nutrition_authority_canonical"] == "vitamin_c"


def test_a_title_naming_a_brand_never_lends_a_blend_total_to_that_member():
    """Only the heading row's own text can name the branded record: "Sensoril"
    in the product title does not make a 250 mg two-member blend Sensoril's dose."""
    raw = _raw("prominence_blend_total_328062_raw.json")
    raw["fullName"] = "Sensoril Sleep Tonight"
    evidence = _evidence(_enrich(raw))
    assert evidence["metadata"]["primary_evidence_floor"] == 0.0
    assert evidence["components"]["clinical_evidence_pipeline"] > 0


def test_recovery_never_reads_a_blend_total_lent_to_a_member():
    """fucoPROTEIN's 15 g blend total is lent to its first member, Milk Protein.
    Without enrichment's own whey link, recovery must not rebuild one from that
    lent total: none of the four members discloses an amount."""
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches

    product = _enrich("prominence_lent_protein_40581_raw.json")
    matches = product["evidence_data"]["clinical_matches"]
    product["evidence_data"]["clinical_matches"] = [
        m for m in matches if m.get("id") != "INGR_WHEY_PROTEIN"
    ]
    assert resolved_clinical_matches(product, owner_scoped=True)[1] == []


@pytest.mark.parametrize("heading", ["Sensoril", "Sensoril Sleep Blend"])
@pytest.mark.parametrize("same_canonical_preparations", [False, True])
def test_a_member_named_heading_does_not_own_the_multi_ingredient_total(heading, same_canonical_preparations):
    """Naming the heading after Sensoril cannot turn Sensoril + L-theanine's
    250 mg total into a disclosed Sensoril amount, for any scoring consumer."""
    from scoring_input_contract import get_scoring_ingredients, is_lent_blend_mass

    raw = _raw("prominence_blend_total_328062_raw.json")
    raw["fullName"] = "Sensoril Sleep Tonight"
    raw["ingredientRows"][1]["name"] = heading
    if same_canonical_preparations:
        member = raw["ingredientRows"][1]["nestedRows"][1]
        member.update(name="Ashwagandha Root Powder", ingredientGroup="Ashwagandha", category="botanical", forms=[])
    product = _enrich(raw)
    header = next(
        row for row in get_scoring_ingredients(product, strict=True).rows
        if row.get("raw_source_path") == "ingredientRows[1]"
        and row.get("evidence_type") == "blend_anchor_mass"
        and row.get("canonical_id") == "ashwagandha"
    )
    assert is_lent_blend_mass(header), "The shared contract must preserve member amount ownership"
    evidence = _evidence(product)
    assert evidence["metadata"]["primary_evidence_floor"] == 0.0
    assert evidence["components"]["clinical_evidence_pipeline"] > 0


@pytest.mark.parametrize("with_constituent", [False, True])
def test_a_single_branded_intervention_nested_under_its_own_heading_keeps_its_floor(with_constituent):
    from copy import deepcopy
    from scoring_input_contract import get_scoring_ingredients, is_lent_blend_mass

    raw = _raw("prominence_blend_total_328062_raw.json")
    raw["fullName"] = "Sensoril Sleep Tonight"
    raw["ingredientRows"][1]["name"] = "Sensoril"
    raw["ingredientRows"][1]["nestedRows"] = raw["ingredientRows"][1]["nestedRows"][:1]
    if with_constituent:
        member = raw["ingredientRows"][1]["nestedRows"][0]
        constituent = deepcopy(member)
        constituent.update(name="Withanolides", ingredientGroup="Withanolides", category="other", forms=[], nestedRows=[])
        constituent["quantity"][0].update(quantity=1.25, unit="mg")
        member["nestedRows"] = [constituent]
    product = _enrich(raw)
    header = next(row for row in get_scoring_ingredients(product, strict=True).rows
                  if row.get("raw_source_path") == "ingredientRows[1]"
                  and row.get("evidence_type") == "blend_anchor_mass")
    assert not is_lent_blend_mass(header), "A constituent is not another blend member"
    evidence = _evidence(product)
    # With the constituent, current enrichment links the records only to the
    # marker's 1.25 mg row and the existing source guard grants no floor. Keep
    # that baseline behavior; this correction must not invent another join.
    assert evidence["metadata"]["primary_evidence_floor"] == (0.0 if with_constituent else 18.0)


def test_real_nested_enzyme_member_has_one_physical_source_link():
    from scoring_input_contract import get_scoring_ingredients, is_lent_blend_mass

    product = _enrich("prominence_nested_enzyme_242529_raw.json")
    header = next(row for row in get_scoring_ingredients(product, strict=True).rows
                  if row.get("raw_source_path") == "ingredientRows[30]"
                  and row.get("evidence_type") == "blend_anchor_mass")
    assert not is_lent_blend_mass(header), "The enzyme preparation is not a named individual member"
    assert len(header["linked_rows"]) == len(set(header["linked_rows"]))
    _evidence(product)  # exercise the production artifact, not only the adapter


@pytest.mark.parametrize("pid", ["231868", "284197"])
def test_a_named_whole_preparation_is_not_its_mapped_component(pid):
    from scoring_input_contract import get_scoring_ingredients, is_lent_blend_mass

    product = _enrich(f"prominence_preparation_{pid}_raw.json")
    headers = [row for row in get_scoring_ingredients(product, strict=True).rows
               if row.get("reason") == "identity_bearing_blend_header_mass"]
    assert headers, "A named preparation must retain its own blend-level amount"
    assert not any(is_lent_blend_mass(row) for row in headers)
    assert _evidence(product)["metadata"]["primary_evidence_floor"] == 14.0


@pytest.mark.parametrize("peptide_quantity,peptide_unit", [(2, "g"), (2000, "mg")])
def test_recovered_peptide_minimum_never_borrows_other_collagen_amount(peptide_quantity, peptide_unit):
    product = _product(
        product_name="Collagen Complex",
        ingredients=[
            _row("Bovine Hide Collagen", "collagen", 3, unit="g", path="ingredientRows[0]", standard_name="Collagen"),
            _row("Hydrolyzed Collagen Peptides Type I & III", "collagen", peptide_quantity,
                 unit=peptide_unit, path="ingredientRows[1]", standard_name="Collagen"),
        ], matches=[],
    )
    result = _evidence(product)
    assert "SUB_CLINICAL_DOSE_DETECTED" in result["metadata"]["flags"]
    assert result["metadata"]["primary_evidence_floor"] == 0.0
    assert result["metadata"]["ingredient_points"].get("collagen", 0.0) == 0.0


@pytest.mark.parametrize("reverse_rows", [False, True])
def test_recovered_peptide_match_preserves_its_actual_source_row(reverse_rows):
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches
    rows = [
        _row("Bovine Hide Collagen", "collagen", 5, unit="g", path="ingredientRows[0]", standard_name="Collagen"),
        _row("Hydrolyzed Collagen Peptides Type I & III", "collagen", 3, unit="g", path="ingredientRows[1]", standard_name="Collagen"),
    ]
    if reverse_rows:
        rows.reverse()
    product = _product(product_name="Collagen Complex", ingredients=rows, matches=[])
    _, recovered = resolved_clinical_matches(product, owner_scoped=True)
    entry = next(e for e in recovered if e["id"] == "RECOVERED_COLLAGEN_PEPTIDES_V1")
    assert entry["matched_source_row_refs"] == ["ingredientRows[1]"]
    assert _evidence(product)["score"] > 0


@pytest.mark.parametrize("peptide_ref", [None, "   ", "\t"])
def test_ambiguous_unreferenced_peptide_recovery_cannot_borrow_a_shared_name(peptide_ref):
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches
    product = _product(product_name="Collagen Complex", ingredients=[
        _row("Collagen", "collagen", 3, unit="g", path="ingredientRows[0]"),
        _row("Collagen", "collagen", 2, unit="g", path=peptide_ref, collagen_subtype="peptides_i_iii"),
    ], matches=[])
    _, recovered = resolved_clinical_matches(product, owner_scoped=True)
    assert not any(e["id"] == "RECOVERED_COLLAGEN_PEPTIDES_V1" for e in recovered)
    assert _evidence(product)["metadata"]["primary_evidence_floor"] == 0.0


@pytest.mark.parametrize("reverse_rows", [False, True])
def test_equal_peptide_amounts_prefer_available_source_lineage(reverse_rows):
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches
    rows = [
        _row("Collagen", "collagen", 3, unit="g", collagen_subtype="peptides_i_iii"),
        _row("Collagen", "collagen", 3, unit="g", path="ingredientRows[1]",
             collagen_subtype="peptides_i_iii"),
    ]
    if reverse_rows:
        rows.reverse()
    product = _product(product_name="Collagen Complex", ingredients=rows, matches=[])
    _, recovered = resolved_clinical_matches(product, owner_scoped=True)
    entry = next(e for e in recovered if e["id"] == "RECOVERED_COLLAGEN_PEPTIDES_V1")
    assert entry["matched_source_row_refs"] == ["ingredientRows[1]"]
    assert _evidence(product)["score"] > 0


def test_same_named_peptide_preparation_links_its_separate_declarations():
    from scoring_v4.modules.generic_evidence import resolved_clinical_matches
    rows = [
        _row("Hydrolyzed Collagen Type 1 & 3", "collagen", 6, unit="g",
             path="ingredientRows[1].forms[0]"),
        _row("Hydrolyzed Collagen Type 1 & 3", "collagen", 6.6, unit="g",
             path="ingredientRows[2]"),
    ]
    product = _product(product_name="Pure Collagen Types 1 and 3 Powder", ingredients=rows, matches=[])
    _, recovered = resolved_clinical_matches(product, owner_scoped=True)
    entry = next(e for e in recovered if e["id"] == "RECOVERED_COLLAGEN_PEPTIDES_V1")
    assert set(entry["matched_source_row_refs"]) == {"ingredientRows[1].forms[0]", "ingredientRows[2]"}
    from assessment_readiness import evaluate_assessment_readiness
    readiness = evaluate_assessment_readiness(product, module="generic")
    assert readiness["evidence"]["readiness"] == "complete"
