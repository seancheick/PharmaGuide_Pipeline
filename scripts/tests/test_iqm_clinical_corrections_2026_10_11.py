"""Source applicability and existing form-policy corrections without new calibration."""

import json
import os
from pathlib import Path

import pytest


def _data():
    return json.loads(Path(os.environ.get("PG_IQM_REGRESSION_INPUT", Path(__file__).parents[1] / "data/ingredient_quality_map.json")).read_text())


def test_same_35624_strain_has_one_form_and_no_species_fallback_alias():
    forms = _data()["bifidobacterium_longum"]["forms"]
    candidates = [(key, row) for key, row in forms.items() if "35624" in key]
    assert len(candidates) == 1
    key, row = candidates[0]
    assert key == "bifidobacterium longum 35624"
    aliases = {name.lower() for name in row["aliases"]}
    assert {"35624", "align", "b. infantis 35624", "b. longum 35624"} <= aliases
    assert not any("35624" in name for name in forms["bifidobacterium longum (unspecified)"]["aliases"])
    assert row["absorption_structured"]["value"] is None


def test_chitosan_is_not_exact_chitin_or_shrimp_chitin_identifier():
    parent = _data()["chitosan"]
    assert "chitin" not in parent["forms"]["chitosan (unspecified)"]["aliases"]
    assert parent.get("rxcui") != "1788955"
    assert parent.get("gsrs", {}).get("substance_name") != "CHITIN"


@pytest.mark.parametrize("parent,form,obsolete", [
    ("curcumin", "theracurmin", "30265004"),
    ("viscotoxin", "viscotoxin (unspecified)", "10535766"),
    ("rye_pollen", "rye pollen extract (unspecified)", "10604694"),
    ("dill", "dill (unspecified)", "24847471"),
    ("salacia", "salacia (unspecified)", "29656413"),
])
def test_wrong_topic_identifiers_do_not_support_current_form_notes(parent, form, obsolete):
    assert obsolete not in _data()[parent]["forms"][form]["notes"]


def test_serrapeptase_does_not_claim_local_digestive_absorption():
    row = _data()["serrapeptase"]["forms"]["serrapeptase"]
    assert "local action" not in row["absorption"]
    assert row["absorption_structured"]["value"] is None


def test_liposomal_taurine_without_comparison_does_not_get_form_premium():
    forms = _data()["taurine"]["forms"]
    assert forms["liposomal taurine"]["bio_score"] == 11
    # The authored powder is a specified chemical form, not nondisclosure.
    assert forms["free taurine"]["bio_score"] == 11


def test_vitamin_a_unknown_does_not_assign_all_carotenoids_or_fraction():
    form = _data()["vitamin_a"]["forms"]["vitamin a (unspecified)"]
    assert "carotenoids" not in {a.lower() for a in form["aliases"]}
    assert form["absorption_structured"]["value"] is None


def test_niacin_source_is_not_dismissed_as_nonexistent():
    data = _data()
    for parent in ["vitamin_b1_thiamine", "vitamin_b2_riboflavin", "vitamin_b3_niacin", "vitamin_b5_pantothenic"]:
        for form in data[parent]["forms"].values():
            assert '"Norris 2006" non-existent' not in form["notes"]


def test_nr_does_not_cite_erythroblast_paper_as_human_pk():
    forms = _data()["nad_precursors"]["forms"]
    assert not any("27720903" in row["notes"] for row in forms.values())


def test_creatine_ethyl_ester_does_not_claim_measured_near_zero_or_stomach_conversion():
    row = _data()["creatine_monohydrate"]["forms"]["creatine ethyl ester"]
    assert "near-zero" not in row["absorption"]
    assert "in the stomach" not in row["notes"]
    assert row["absorption_structured"]["value"] is None


def test_glycine_is_not_described_as_a_chiral_l_form():
    row = _data()["l_glycine"]["forms"]["l-glycine powder"]
    assert "free L-form" not in row["consumer_note"]
    assert "achiral" in row["consumer_note"]


def test_nitrosigine_single_arm_is_not_called_hcl_comparison():
    row = _data()["l_arginine"]["forms"]["nitrosigine (arginine silicate inositol)"]
    assert "Human RCT" not in row["notes"]
    assert "vs 1 hour for HCl" not in row["notes"]


def test_same_pure_theanine_identity_has_no_brand_only_score_premium():
    forms = _data()["l_theanine"]["forms"]
    assert forms["suntheanine (Taiyo)"]["bio_score"] == forms["l-theanine powder"]["bio_score"]


def test_malate_without_comparative_delivery_evidence_has_no_premium():
    forms = _data()["l_citrulline"]["forms"]
    assert forms["l-citrulline malate"]["bio_score"] == forms["l-citrulline powder"]["bio_score"]


@pytest.mark.parametrize("parent,form", [
    ("olive_leaf", "hydroxytyrosol (olive phenolic)"),
    ("melatonin", "oral spray melatonin"),
    ("chlorella", "broken cell wall chlorella"),
    ("turkey_tail", "turkey tail standardized extract"),
])
def test_relative_or_wrong_preparation_endpoint_is_not_absolute_fraction(parent, form):
    row = _data()[parent]["forms"][form]
    assert row["absorption_structured"]["value"] is None


def test_oral_psk_route_and_rat_msm_scope_are_preserved():
    data = _data()
    assert "oral" in data["turkey_tail"]["forms"]["turkey tail standardized extract"]["notes"].lower()
    assert "rat" in data["msm"]["forms"]["msm (methylsulfonylmethane) (unspecified)"]["notes"]


def test_35624_historical_spellings_resolve_to_one_existing_class_rating():
    from enrich_supplements_v3 import SupplementEnricherV3

    enricher = SupplementEnricherV3()
    iqm = _data()
    readings = [enricher._match_quality_map(
        label, label, iqm, preferred_parent="bifidobacterium_longum",
        cleaner_canonical_id="bifidobacterium_longum",
    ) for label in [
        "B. infantis 35624",
        "B. longum 35624",
        "Bifidobacterium longum subsp. longum 35624™",
        "Align",
        "Bifantis",
    ]]
    assert {(row["canonical_id"], row["form_id"], row["bio_score"]) for row in readings} == {
        ("bifidobacterium_longum", "bifidobacterium longum 35624", 7)
    }

    printed_label = enricher._match_quality_map(
        "Bifidobacterium longum subsp. longum 35624™",
        "Bifidobacterium Longum",
        iqm,
        preferred_parent="bifidobacterium_longum",
        cleaner_canonical_id="bifidobacterium_longum",
    )
    assert (printed_label["form_id"], printed_label["bio_score"]) == (
        "bifidobacterium longum 35624",
        7,
    )


def test_alphawave_does_not_resolve_to_taiyo_preparation():
    from enrich_supplements_v3 import SupplementEnricherV3
    enricher = SupplementEnricherV3()
    iqm = _data()
    for label in ['AlphaWave', 'AlphaWave l-theanine']:
        row = enricher._match_quality_map(label, label, iqm, preferred_parent='l_theanine', cleaner_canonical_id='l_theanine')
        assert row['form_id'] != 'suntheanine (Taiyo)'
    row = enricher._match_quality_map('Suntheanine', 'Suntheanine', iqm, preferred_parent='l_theanine', cleaner_canonical_id='l_theanine')
    assert row['form_id'] == 'suntheanine (Taiyo)'


def test_unspecified_theanine_does_not_restore_unmeasured_fraction():
    forms = _data()['l_theanine']['forms']
    for row in forms.values():
        assert row['absorption_structured']['value'] is None
    assert '~70%' not in forms['l-theanine (unspecified)']['notes']
    assert [forms[k]['bio_score'] for k in ['suntheanine (Taiyo)', 'l-theanine powder', 'l-theanine (unspecified)']] == [10,10,9]


def test_theophylline_retains_margin_and_interaction_cautions():
    row = _data()['theophylline']['forms']['theophylline (unspecified)']
    assert 'narrow' in row['notes'].lower()
    assert 'concomitant medicines' in row['notes'].lower()
    assert 'toxicity risk' in row['notes'].lower()


def test_sage_description_does_not_restore_disclaimed_aromatherapy_evidence():
    description = _data()['sage']['description']
    assert 'Multiple RCTs support cognitive performance enhancement in healthy adults' not in description
    assert 'mixed aromatherapy' in description
    assert '10.1038/sj.ijo.0801322' not in description
    assert 'not oral sage or Cognivia in healthy adults' in description
    assert 'no oral sage/Cognivia efficacy credit' in description


@pytest.mark.parametrize("name", ["Hemp Oil (aerial plant parts) extract", "Hemp Oil extract", "Hemp oil", "Beta-Caryophyllene, Phytocannabinoids, Terpenes"])
def test_hemp_extract_never_gets_seed_form_credit(name):
    from enrich_supplements_v3 import SupplementEnricherV3
    enricher = SupplementEnricherV3()
    match = enricher._match_quality_map(name, "Hemp Seed Oil", enricher.databases["ingredient_quality_map"])
    assert match is None or match.get("canonical_id") != "hemp_seed_oil"


def test_hemp_seed_oil_does_not_promise_absent_cannabinoids():
    forms = _data()["hemp_seed_oil"]["forms"]
    assert "Contains no significant CBD or THC" not in str(forms)
    assert "trace" in forms["hemp seed oil (unspecified)"]["notes"].lower()


def test_all_hemp_form_notes_exclude_unrelated_batch_citations():
    forms = _data()["hemp_seed_oil"]["forms"]
    for row in forms.values():
        for unrelated in ("11120446", "12571654", "7491892", "Sea buckthorn", "Fenugreek", "Bioflavonoids"):
            assert unrelated.lower() not in row["notes"].lower()
    assert [row["bio_score"] for row in forms.values()] == [13, 12, 9, 8]


@pytest.mark.parametrize("parent,form", [
    ("hmb", "hmb free acid (hmb-fa)"),
    ("taurine", "magnesium taurate (as taurine source)"),
    ("l_arginine", "nitrosigine (arginine silicate inositol)"),
])
def test_approved_provisional_form_ceiling_is_not_clinical_calibration(parent, form):
    record = _data()[parent]["forms"][form]
    assert record["bio_score"] == 11
    assert "provisional" in record["notes"].lower()
    assert "clinical calibration" in record["notes"].lower()


def test_hmb_evidence_cannot_generalize_gel_exposure_to_all_free_acid_preparations():
    forms = _data()["hmb"]["forms"]
    for form in forms.values():
        rationale = form["form_evidence"]["rationale"]
        assert "gel" in rationale.lower()
        assert "capsule" in rationale.lower()
        assert "universal" in rationale.lower()
    assert forms["hmb free acid (hmb-fa)"]["form_evidence"]["score_supported"] is False
