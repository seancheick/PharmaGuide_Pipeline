"""Sean's exact October29 Dose decisions preserve material and clinical boundaries."""
from copy import deepcopy
import json
from pathlib import Path

import pytest


CASES = [
    ("yohimbe", "252787", "yohimbe", "yohimbe"),
    ("yohimbe", "5821", "yohimbe", "yohimbe"),
    ("yohimbe", "29242", "yohimbe", "yohimbe"),
    ("bamboo", "252349", "silica", "bamboo_stem_leaf_extract"),
    ("bamboo", "330290", "silica", "bamboo_stem_leaf_extract"),
    ("chaste", "330565", "chaste_tree", "chaste_tree"),
    ("ginkgo", "306223", "ginkgo_biloba", "ginkgo_biloba"),
    ("applewise", "231929", "apple_fruit", "applewise_fruit_skin_extract"),
    ("applewise", "232062", "apple_fruit", "applewise_fruit_skin_extract"),
    ('cascara', '18313', 'cascara_sagrada', 'cascara_sagrada'),
    ('cascara', '17149', 'cascara_sagrada', 'cascara_sagrada'),
    ('american_capsule', '1627', 'ginseng', 'american_ginseng_root_extract_capsule'),
    ('american_capsule', '68956', 'ginseng', 'american_ginseng_root_extract_capsule'),
    ('american_capsule', '74766', 'ginseng', 'american_ginseng_root_extract_capsule'),
    ('american_capsule', '74768', 'ginseng', 'american_ginseng_root_extract_capsule'),
    ('american_capsule', '316119', 'ginseng', 'american_ginseng_root_extract_capsule'),
    ('american_capsule', '214060', 'ginseng', 'american_ginseng_root_extract_capsule'),
    ('american_capsule', '216622', 'ginseng', 'american_ginseng_root_extract_capsule'),
    ('american_gummy', '205266', 'ginseng', 'american_ginseng_root_extract_gummy'),
    ('red_root', '269558', 'ginseng', 'red_panax_ginseng_root'),
    ('whiteoak', '79598', 'white_oak', 'white_oak'),
    ('ashwagandha_powder', '329949', 'ashwagandha', 'ashwagandha_root_powder'),
    ('ginkgo_powder', '329958', 'ginkgo', 'ginkgo_leaf_powder'),
    ('reishi_mycelia', '12869', 'reishi', 'reishi_mycelia_powder'),
]


# Sean's November1 decision: BulkSupplements American ginseng rhizome and root
# 4:1 extract powder (solvent and ginsenosides undeclared). The Health Canada
# monograph covers dry root only, in grams of dried root, with ethanol/water
# extracts; it sets no benchmark for this material.
AMERICAN_4TO1_POWDER = ["330196", "330197", "330198", "330199"]
AMERICAN_4TO1_OWNER = "american_ginseng_rhizome_root_extract_4to1_powder"


@pytest.fixture(scope="module")
def exact_scope_products():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    from enrich_supplements_v3 import SupplementEnricherV3
    normalizer, enricher = EnhancedDSLDNormalizer(), SupplementEnricherV3()
    folder = Path(__file__).parent / "fixtures"
    return {pid: enricher.enrich_product(normalizer.normalize_product(json.loads(
        (folder / f"raw_{family}_{pid}.json").read_text())))[0]
        for family, pid in [(family, pid) for family, pid, _, _ in CASES]
        + [("applewise", "231929")] + [("kelp", pid) for pid in ["252562","255054","255055","255057"]]
        + [("american_powder_4to1", pid) for pid in AMERICAN_4TO1_POWDER]}


def _source_pair(product, canonical):
    from dose_assessment import _source_dose_row
    from scoring_input_contract import _route_scoring_rows
    row = next(row for row in _route_scoring_rows(product)
               if str(row.get("canonical_id") or "").lower() == canonical)
    source = _source_dose_row(product, row)
    assert source is not None
    return row, source


@pytest.mark.parametrize("family,pid,canonical,owner", CASES)
def test_original_exact_material_has_completed_dose_only_reference(
    exact_scope_products, family, pid, canonical, owner,
):
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose
    from dose_assessment import verified_reference_citations
    from evidence_resolver import _load_literature_evidence
    from clinical_applicability import assess_clinical_source_review
    product = exact_scope_products[pid]
    row, source = _source_pair(product, canonical)
    before = deepcopy(product)
    result = score_botanical_purpose_dose(product, row)
    assert result["metadata"]["benchmark"] == "absent"
    assert result["band"] == "disclosed_no_reference"
    record = _load_literature_evidence()[owner]
    assert record["reference_semantics"]["scope"] == "exact_preparation"
    assert record["reference_semantics"]["review_date"] == "2026-10-29"
    assert "Sean" in record["reference_semantics"]["rationale"]
    assert verified_reference_citations(record)
    assert not assess_clinical_source_review(record)["is_complete"]
    assert product == before
    assert source["quantity"] == row["quantity"]


@pytest.mark.parametrize("family,pid,canonical,owner", CASES)
@pytest.mark.parametrize("change", ["missing_source", "foreign_ref", "borrowed_notes", "wrong_material"])
def test_exact_dose_scope_cannot_borrow_another_material_or_enriched_fact(
    exact_scope_products, family, pid, canonical, owner, change,
):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    product = deepcopy(exact_scope_products[pid])
    row, source = _source_pair(product, canonical)
    if change == "missing_source":
        product["activeIngredients"] = []
    elif change == "foreign_ref":
        row["raw_source_path"] = "ingredientRows[999]"
    elif change == "borrowed_notes":
        row["notes"] = source.get("notes", "")
        source["notes"] = ""
        source["forms"] = []
        source["raw_taxonomy"] = {}
        source["plantPart"] = None
    else:
        source["raw_source_text"] = source["name"] = {
            "yohimbe": "Yohimbe whole bark powder", "bamboo": "Bamboo root powder",
            "chaste": "Chasteberry whole fruit powder", "applewise": "Apple fruit powder",
            "ginkgo": "Ginkgo whole leaf powder",
            "kelp": "Unspecified seaweed extract", "cascara": "Rhamnus davurica bark powder",
            "american_capsule": "American Ginseng leaf extract",
            "american_gummy": "American Ginseng rhizome extract",
            "red_root": "Korean Red Ginseng leaf and stem extract",
            "whiteoak": "Quercus robur bark", "ashwagandha_powder": "Ashwagandha leaf powder",
            "ginkgo_powder": "Ginkgo standardized extract", "reishi_mycelia": "Reishi fruiting body extract",
        }[family]
    assert _botanical_benchmark(row, product=product) == "unresolved"


@pytest.mark.parametrize("pid",["231929","232062"])
@pytest.mark.parametrize("change",["title_only","brand_only","wrong_quantity","foreign_row"])
def test_applewise_requires_exact_material_and_manufacturer_bridge(exact_scope_products,pid,change):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    product=deepcopy(exact_scope_products[pid]);row,source=_source_pair(product,"apple_fruit")
    assert "AppleWise" in product["product_name"]
    if change=="title_only": source["notes"]=source["notes"].split(" Note: Sole active source row")[0]
    elif change=="brand_only":
        source["notes"]="Sole active source row of manufacturer-linked AppleWise finished product item #01625"
        source["raw_taxonomy"]["forms"]=[];source["plantPart"]=None
    elif change=="wrong_quantity": source["quantity"]=300
    else: row["raw_source_path"]="ingredientRows[999]"
    assert _botanical_benchmark(row,product=product)=="unresolved"


@pytest.mark.parametrize("family,pid,canonical,owner", CASES)
@pytest.mark.parametrize("change", ["incomplete_proof", "stale_semantics", "pending_approval"])
def test_exact_dose_scopes_require_the_current_approved_content_bound_reference(
    exact_scope_products, monkeypatch, family, pid, canonical, owner, change,
):
    import evidence_resolver
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    records = deepcopy(evidence_resolver._load_literature_evidence())
    record = records[owner]
    if change == "incomplete_proof":
        record["verification_provenance"]["reference_citations"]["is_complete"] = False
    elif change == "stale_semantics":
        record["reference_semantics"]["review_date"] = "1900-01-01"
    else:
        record["reference_semantics"]["approval_status"] = "pending"
    monkeypatch.setattr(evidence_resolver, "_load_literature_evidence", lambda: records)
    product = exact_scope_products[pid]
    row, _ = _source_pair(product, canonical)
    assert _botanical_benchmark(row, product=product) == "unresolved"


@pytest.mark.parametrize("pid,canonical,change", [
    ("252787", "yohimbe", "negated_material"),
    ("29242", "yohimbe", "negated_material"),
    ("252787", "yohimbe", "negated_assay"),
    ("29242", "yohimbe", "negated_assay"),
    ("252787", "yohimbe", "earlier_positive"),
    ("252787", "yohimbe", "missing_assay"),
    ("330565", "chaste_tree", "different_der"),
    ("306223", "ginkgo_biloba", "different_marker"),
])
def test_compound_source_assertions_preserve_negation_and_marker_boundaries(
    exact_scope_products, pid, canonical, change,
):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    product = deepcopy(exact_scope_products[pid])
    row, source = _source_pair(product, canonical)
    notes = source["notes"]
    if change == "negated_material":
        source["notes"] = "No " + notes
    elif change == "negated_assay":
        source["notes"] = notes.replace("standardized to contain", "not standardized to contain")
    elif change == "earlier_positive":
        first = notes.split(";")[0]
        source["notes"] = first + "; unrelated statement; no " + notes
    elif change == "missing_assay":
        source["notes"] = notes.replace("2%", "3%")
    elif change == "different_der":
        source["notes"] = notes.replace("10:1", "4:1")
    else:
        source["notes"] = notes.replace("24%", "12%")
    assert _botanical_benchmark(row, product=product) == "unresolved"


@pytest.mark.parametrize("pid,approved_index", [("252349", 0), ("330290", 1)])
def test_bamboo_undeclared_der_and_thirty_to_one_are_separate_source_assertions(
    exact_scope_products, pid, approved_index,
):
    from dose_assessment import _dose_source_preparation_matches
    from evidence_resolver import _load_literature_evidence
    product = deepcopy(exact_scope_products[pid])
    row, source = _source_pair(product, "silica")
    record = deepcopy(_load_literature_evidence()["bamboo_stem_leaf_extract"])
    assertions = record["applicability"]["required_form_terms"]
    record["applicability"]["required_form_terms"] = [assertions[approved_index]]
    assert _dose_source_preparation_matches(product, row, record)
    record["applicability"]["required_form_terms"] = [assertions[1 - approved_index]]
    assert not _dose_source_preparation_matches(product, row, record)
    record["applicability"]["required_form_terms"] = assertions
    source["notes"] = source["notes"].replace("DER not declared on label", "DER20:1").replace("30:1", "20:1")
    assert not _dose_source_preparation_matches(product, row, record)


def test_overlapping_bamboo_alias_does_not_choose_a_generic_competing_record(exact_scope_products, monkeypatch):
    import evidence_resolver
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    records = deepcopy(evidence_resolver._load_literature_evidence())
    records["generic_bamboo"] = {"standard_name": "Bamboo extract"}
    monkeypatch.setattr(evidence_resolver, "_load_literature_evidence", lambda: records)
    product = exact_scope_products["252349"]
    row, _ = _source_pair(product, "silica")
    assert _botanical_benchmark(row, product=product) == "unresolved"


def test_exact_dose_delivery_constraint_uses_original_physical_state(exact_scope_products):
    from dose_assessment import _dose_source_preparation_matches
    from evidence_resolver import _load_literature_evidence
    product = deepcopy(exact_scope_products["5821"])
    row, _ = _source_pair(product, "yohimbe")
    record = deepcopy(_load_literature_evidence()["yohimbe"])
    record["applicability"]["dosage_forms"] = ["gummy"]
    assert not _dose_source_preparation_matches(product, row, record)
    record["applicability"]["dosage_forms"] = ["capsule"]
    assert _dose_source_preparation_matches(product, row, record)
    product["physicalState"] = {}
    product["form_factor_canonical"] = "capsule"
    product["product_name"] = "Yohimbe capsules"
    assert not _dose_source_preparation_matches(product, row, record)


@pytest.mark.parametrize("pid,canonical,notes,part", [
    ("306223", "ginkgo_biloba", "24% Ginkgo Flavone Glycosides; PlantPart: stem", "stem"),
    ("330565", "chaste_tree", "10:1; PlantPart: flower", "flower"),
])
def test_declared_part_conflict_cannot_borrow_a_name_or_marker(
    exact_scope_products, pid, canonical, notes, part,
):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    product = deepcopy(exact_scope_products[pid])
    row, source = _source_pair(product, canonical)
    source["notes"], source["plantPart"] = notes, part
    assert _botanical_benchmark(row, product=product) == "unresolved"


@pytest.mark.parametrize("field,value", [("plantPart", "leaf"), ("genus", "Othergenus"), ("species", "other_species"), ("species", None)])
def test_explicit_policy_taxonomy_requires_the_original_typed_source_fact(exact_scope_products, field, value):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    product = deepcopy(exact_scope_products["5821"])
    row, source = _source_pair(product, "yohimbe")
    source[field] = value
    assert _botanical_benchmark(row, product=product) == "unresolved"


@pytest.mark.parametrize('pid,canonical',[('329949','ashwagandha'),('329958','ginkgo')])
def test_powder_daily_comparison_uses_explicit_once_daily_source(exact_scope_products,pid,canonical):
    from serving_frequency import resolve_daily_serving_range
    from scoring_v4.modules.botanical_profile import _mass_mg
    product=exact_scope_products[pid]
    row,source=_source_pair(product,canonical)
    lower,upper,defaulted=resolve_daily_serving_range(product)
    assert (lower,upper,defaulted)==(1,1,False)
    assert _mass_mg(source)==2000
    assert _mass_mg(row)*lower==_mass_mg(row)*upper==2000


@pytest.mark.parametrize('pid',['1627','68956','74766','74768','316119','214060','216622','205266'])
@pytest.mark.parametrize('change',['foreign_form','missing_form','ambiguous_form'])
def test_approved_american_delivery_groups_do_not_cross(exact_scope_products,pid,change):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    product=deepcopy(exact_scope_products[pid])
    row,_=_source_pair(product,'ginseng')
    if change=='foreign_form':
        product['physicalState']={'langualCode':'E0159','langualCodeDescription':'Capsule'} if pid=='205266' else {
            'langualCode':'E0176','langualCodeDescription':'Gummy or Jelly'}
    elif change=='missing_form':
        product['physicalState']={}
        product['form_factor_canonical']='gummy' if pid=='205266' else 'capsule'
    else:
        product['physicalState']={'langualCode':'E0159','langualCodeDescription':'Gummy or Jelly'}
    assert _botanical_benchmark(row,product=product)=='unresolved'


def test_culinary_kombu_keeps_the_original_source_approval():
    from evidence_resolver import _load_literature_evidence
    from dose_assessment import reference_semantics_sha256,verified_reference_citations
    from scripts.tests.test_v4_botanical_profile import _botanical_ingredient,_botanical_product
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    record=_load_literature_evidence()['kombu']
    assert reference_semantics_sha256(record['reference_semantics'])=='63f0bfd253ecc35653fba4bd4b6b9526042795bbc2aab3c11a972db0645980d4'
    assert record['reference_semantics']['review_date']=='2026-10-27'
    assert verified_reference_citations(record)
    row=_botanical_ingredient(name='Kombu',standard_name='Kombu',canonical_id='kombu',form='whole edible kelp',
                              raw_source_text='Kombu',raw_source_path='ingredientRows[0]')
    product=_botanical_product(row,standardized=False)
    product['activeIngredients']=[deepcopy(row)]
    assert _botanical_benchmark(row,product=product)=='absent'


@pytest.mark.parametrize('pid',['252562','255054','255055','255057'])
def test_exact_kelp_extracts_reuse_the_existing_explicit_preparation_scope(exact_scope_products,pid):
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose
    from evidence_resolver import _load_literature_evidence
    from dose_assessment import reference_semantics_sha256,verified_reference_citations
    product=exact_scope_products[pid]
    row,source=_source_pair(product,'kombu')
    assert 'Laminaria japonica' in source['notes']
    assert source['plantPart']=='whole grass'
    result=score_botanical_purpose_dose(product,row)
    assert result['metadata']['benchmark']=='absent'
    record=_load_literature_evidence()['kombu']
    assert record['reference_semantics']['preparation']=='Source-labeled preparations: Kelp Thallus Extract; Kelp Whole Grass Extract'
    assert reference_semantics_sha256(record['reference_semantics'])=='63f0bfd253ecc35653fba4bd4b6b9526042795bbc2aab3c11a972db0645980d4'
    assert verified_reference_citations(record)

@pytest.mark.parametrize('ratio',['8:1','20:1'])
def test_bamboo_undeclared_der_branch_cannot_ignore_new_ratio(exact_scope_products,ratio):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    product=deepcopy(exact_scope_products['252349']);row,source=_source_pair(product,'silica')
    assert 'DER not declared' in source['notes']
    source['notes']+='; DER '+ratio
    assert _botanical_benchmark(row,product=product)=='unresolved'


@pytest.mark.parametrize("pid", AMERICAN_4TO1_POWDER)
def test_american_4to1_rhizome_root_powder_completes_dose_with_the_shared_neutral(exact_scope_products, pid):
    from clinical_applicability import assess_clinical_source_review
    from dose_assessment import verified_reference_citations
    from evidence_resolver import _load_literature_evidence
    from scoring_v4.modules.botanical_profile import score_botanical_purpose_dose
    from scoring_v4.scored_artifact import build_scored_artifact, unfinished_source_assessment
    product = exact_scope_products[pid]
    row, source = _source_pair(product, "ginseng")
    assert (source["notes"], source["plantPart"]) == ("4:1", "rhizome and root")
    result = score_botanical_purpose_dose(product, row)
    assert result["metadata"]["benchmark"] == "absent"
    assert result["band"] == "disclosed_no_reference"
    record = _load_literature_evidence()[AMERICAN_4TO1_OWNER]
    assert record["reference_semantics"]["scope"] == "exact_preparation"
    assert record["reference_semantics"]["review_date"] == "2026-11-01"
    assert "Sean" in record["reference_semantics"]["rationale"]
    assert verified_reference_citations(record)
    assert not assess_clinical_source_review(record)["is_complete"]
    scored = build_scored_artifact(deepcopy(product))
    assert unfinished_source_assessment(product, scored["_v4_module_breakdown"]) is None
    assert scored["quality_score_status"] == "scored"
    assert scored["assessment_readiness"]["release_assessment"]["is_complete"] is True
    # The completed Dose scope adds no clearance: the ginseng precautions stay.
    from build_final_db import build_detail_blob, validate_export_contract
    assert validate_export_contract(product, scored) == []
    assert scored["product_safety_status"] == "no_known_catalog_concern"
    blob = build_detail_blob(product, scored)
    subjects = {w["title"].rsplit(" / ", 1)[1]
                for w in blob["warnings"] + (blob.get("warnings_profile_gated") or [])
                if w.get("source_rule_id") == "RULE_INGREDIENT_GINSENG"}
    assert {"diabetes", "anticoagulants", "hypoglycemics_high_risk", "pregnancy"} <= subjects


@pytest.mark.parametrize("change", [
    "other_ratio", "no_ratio", "capsule_delivery", "root_only", "leaf_part", "incomplete_proof", "pending_approval",
])
def test_american_4to1_powder_scope_stays_with_that_exact_material(exact_scope_products, monkeypatch, change):
    import evidence_resolver
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    product = deepcopy(exact_scope_products["330196"])
    row, source = _source_pair(product, "ginseng")
    records = deepcopy(evidence_resolver._load_literature_evidence())
    record = records[AMERICAN_4TO1_OWNER]
    if change == "other_ratio":
        source["notes"] = "10:1"
    elif change == "no_ratio":
        source["notes"] = ""
    elif change == "capsule_delivery":
        product["physicalState"] = {"langualCode": "E0159", "langualCodeDescription": "Capsule"}
    elif change == "root_only":
        source["plantPart"] = "root"
    elif change == "leaf_part":
        source["raw_source_text"] = source["name"] = "American Ginseng Leaf, Root Extract"
    elif change == "incomplete_proof":
        record["verification_provenance"]["reference_citations"]["is_complete"] = False
    else:
        record["reference_semantics"]["approval_status"] = "pending"
    monkeypatch.setattr(evidence_resolver, "_load_literature_evidence", lambda: records)
    assert _botanical_benchmark(row, product=product) == "unresolved"


@pytest.mark.parametrize("notes", [
    # Another or a second ratio is not the one 4:1 the record names.
    "4:1.5", "4:1 to 10:1", "10:1 and 4:1",
    # The no-benchmark rationale rests on no stated potency or solvent.
    "4:1; standardized to 5% ginsenosides", "4:1 ethanol extract", "4:1 water extract",
])
def test_american_4to1_powder_scope_needs_the_one_unstandardized_ratio(exact_scope_products, notes):
    from scoring_v4.modules.botanical_profile import _botanical_benchmark
    product = deepcopy(exact_scope_products["330196"])
    row, source = _source_pair(product, "ginseng")
    assert _botanical_benchmark(row, product=product) != "unresolved"
    source["notes"] = notes
    assert _botanical_benchmark(row, product=product) == "unresolved"
