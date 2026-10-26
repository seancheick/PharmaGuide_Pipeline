"""Regression locks for harmful_additives ghost-citation cleanup.

Identifiers in clinical-facing safety data must be content-verified. These
tests pin the July 2026 cleanup of broken/wrong-topic DOI references and the
mislabelled TBHQ PMC citation.
"""
import json
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "harmful_additives.json"


def _entries_by_id():
    data = json.loads(DATA_PATH.read_text())
    return {entry["id"]: entry for entry in data["harmful_additives"]}


def _entry_text(entry):
    return json.dumps(entry, sort_keys=True)


def test_dead_or_wrong_topic_harmful_additive_dois_are_removed():
    entries = _entries_by_id()
    combined = "\n".join(_entry_text(entries[eid]) for eid in (
        "ADD_ACESULFAME_K",
        "ADD_BHT",
        "ADD_SYNTHETIC_ANTIOXIDANTS",
        "ADD_TBHQ",
    ))

    assert "10.1002/tcp.10162" not in combined
    assert "10.1080/10408398.2019.1629524" not in combined
    assert "10.1016/j.fct.2005.05.012" not in combined


def test_harmful_additive_replacement_dois_are_content_specific():
    entries = _entries_by_id()

    bht = _entry_text(entries["ADD_BHT"])
    synthetic = _entry_text(entries["ADD_SYNTHETIC_ANTIOXIDANTS"])
    ace_k = _entry_text(entries["ADD_ACESULFAME_K"])
    tbhq = _entry_text(entries["ADD_TBHQ"])

    assert "10.1016/S0278-6915(99)00085-X" in bht
    assert "Safety Assessment of Butylated Hydroxyanisole and Butylated Hydroxytoluene" in bht
    assert "10.1016/S0278-6915(99)00085-X" in synthetic

    assert "10.1016/j.fct.2020.111375" in ace_k
    assert "Lack of potential carcinogenicity for acesulfame potassium" in ace_k

    assert "10.1016/0278-6915(86)90289-9" in tbhq
    assert "Toxicology of tert-butylhydroquinone (TBHQ)" in tbhq
    assert "10.1016/j.fct.2020.111595" in tbhq
    assert "Nrf2-dependent and -independent effects of tBHQ" in tbhq


def test_tbhq_pmc9147452_is_not_mislabelled_as_frontiers():
    tbhq = _entry_text(_entries_by_id()["ADD_TBHQ"])

    assert "PMC9147452" in tbhq
    assert "Life (Basel) 2022" in tbhq
    assert "Frontiers in Immunology" not in tbhq


def test_tbhq_specific_immunotoxicity_claims_are_cited_without_vaccine_overclaim():
    tbhq = _entry_text(_entries_by_id()["ADD_TBHQ"])

    assert "PMID 22250088" in tbhq
    assert "Th2 skewing by activation of Nrf2 in CD4" in tbhq
    assert "10.4049/jimmunol.1101712" in tbhq

    assert "PMID 40115160" in tbhq
    assert "The transcription factor Nrf2 links Th2-mediated experimental allergy to food preservatives" in tbhq
    assert "10.3389/fimmu.2024.1476480" in tbhq

    assert "vaccine efficacy" not in tbhq
    assert "vaccine suppression" not in tbhq


def test_synthetic_antioxidants_umbrella_defers_tbhq_immunotox_to_canonical_entry():
    synthetic = _entry_text(_entries_by_id()["ADD_SYNTHETIC_ANTIOXIDANTS"])

    assert "PMC9147452" not in synthetic
    assert "See ADD_TBHQ for immunotoxicity citations" in synthetic


def test_magnesium_stearate_efsa_reference_is_fatty_acid_salts_not_pest_report():
    entry = _entries_by_id()["ADD_MAGNESIUM_STEARATE"]
    refs = [r for r in entry["references_structured"] if r.get("authority") == "EFSA"]
    assert len(refs) == 1
    assert refs[0]["url"] == "https://doi.org/10.2903/j.efsa.2018.5180"
    assert "magnesium salts of fatty acids" in refs[0]["title"]
    assert "5765" not in _entry_text(entry)
    eu = [r for r in entry["jurisdictional_statuses"] if r["jurisdiction"] == "EU"]
    assert eu[0]["source_ref"] == refs[0]["url"]
    assert entry["severity_level"] == "low"


def test_returned_review_classifies_trial_and_opinions_without_changing_dye_identity():
    rows = _entries_by_id()
    for key in ['ADD_BLUE1', 'ADD_BLUE2']:
        ref = rows[key]['references_structured'][1]
        assert ref['type'] == 'clinical_trial'
        assert 'mixture' in ref['title'].lower()
        assert 'NOT included' in rows[key]['notes']
    for key, index in [('ADD_CALCIUM_ALUMINUM_PHOSPHATE', 1), ('ADD_PALM_OIL', 0),
                       ('ADD_SODIUM_TRIPOLYPHOSPHATE', 0)]:
        assert rows[key]['references_structured'][index]['type'] == 'efsa_opinion'
    assert rows['ADD_CALCIUM_ALUMINUM_PHOSPHATE']['references_structured'][1]['published_date'] == '2008-07-15'


def test_dye_mixture_evidence_does_not_become_isolated_dye_causation():
    for key in ['ADD_RED40', 'ADD_YELLOW5']:
        row = _entries_by_id()[key]
        assert 'mixture' in row['mechanism_of_harm'].lower()
        assert 'mixture' in row['safety_summary'].lower()
        assert 'mixture' in row['safety_summary_one_liner'].lower()
        assert 'hypersensitivity' in row['safety_summary'].lower()


def test_aluminium_opinion_does_not_invent_compound_absorption_or_one_endpoint():
    row = _entries_by_id()['ADD_CALCIUM_ALUMINUM_PHOSPHATE']
    assert 'combined' in row['mechanism_of_harm'].lower()
    assert 'developmental neurotoxicity as the critical endpoint' not in row['mechanism_of_harm']
    assert 'not established' in row['safety_summary'].lower()
    assert row['dose_thresholds'][0]['amount'] == 1
    assert any('renal impairment' in warning for warning in row['population_warnings'])


def test_corn_oil_carrier_is_not_a_proven_inflammatory_ratio_hazard():
    row = _entries_by_id()['ADD_CORN_OIL']
    text = ' '.join(row[k] for k in ['notes', 'mechanism_of_harm', 'safety_summary'])
    assert 'pro-inflammatory eicosanoid production' not in text
    assert 'can skew' not in text
    assert 'does not establish inflammatory harm' in text
    assert row['severity_level'] == 'low'


def test_caramel_animal_endpoint_is_not_liver_thyroid_tumors_or_human_trial():
    row = _entries_by_id()['ADD_CARAMEL_COLOR']
    assert 'lung, liver, and thyroid tumors' not in row['mechanism_of_harm']
    assert 'mice' in row['mechanism_of_harm']
    assert row['references_structured'][1]['type'] == 'primary_study'
    assert '4-methylimidazole' in row['safety_summary']


def test_unknown_colorant_keeps_identity_limit_without_borrowing_carmine_harm():
    row = _entries_by_id()['ADD_UNSPECIFIED_COLORS']
    assert not any('hyperactivity concern applies' in x for x in row['population_warnings'])
    assert 'Carmine-specific' in row['notes']
    assert '4288' in row['references_structured'][0]['url']


def test_e475_cannot_inherit_cmc_p80_mouse_effects():
    row = _entries_by_id()['ADD_FATTY_ACID_POLYGLYCEROL_ESTERS']
    assert 'not E475' in row['safety_summary']
    assert 'not E475-specific' in row['safety_summary_one_liner']
    assert 'not direct E475 evidence' in row['scientific_references'][0]
    assert not any('emulsifier class linked' in x for x in row['population_warnings'])
    assert 'background only' in _entries_by_id()['ADD_SOY_MONOGLYCERIDES']['scientific_references'][0]


def test_palm_source_identifies_2018_assessment_and_unmeasured_product_exposure():
    text = _entries_by_id()['ADD_PALM_OIL']['mechanism_of_harm']
    assert '2018 identified glycidyl esters' not in text
    assert '2016' in text
    assert 'does not establish contamination levels' in text


def test_phosphate_bioaccessibility_is_not_specific_absorption_or_product_safe_dose():
    rows = _entries_by_id()
    row = rows['ADD_SODIUM_HEXAMETAPHOSPHATE']
    assert 'absorbed at 90-100%' not in row['mechanism_of_harm']
    assert 'bioaccessible' in row['mechanism_of_harm']
    assert 'renal impairment' in row['dose_thresholds']['source']
    assert row['dose_thresholds']['value'] == 40
    row = rows['ADD_SODIUM_TRIPOLYPHOSPHATE']
    assert 'generally safe' not in row['notes']
    assert 'kidney function' in row['notes']


def test_folate_biomarker_reference_does_not_claim_all_synthetic_forms_are_harmful():
    text = _entries_by_id()['ADD_SYNTHETIC_B_VITAMINS']['scientific_references'][0]
    assert 'Synthetic vs natural forms' not in text
    assert 'biomarker study' in text
