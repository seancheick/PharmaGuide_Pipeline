"""Form disclosure has one contract.

- A form the label does not disclose is worth the lowest *eligible* named
  bio_score minus 1 (scoring_reference_resolver.unknown_form_quality). The
  IQM owns eligibility (form field ``unknown_floor``): non-functional
  analogs, degradation products, wrong stereoisomers, different compounds and
  non-nutrient sources never set the floor. An authored unspecified form
  supplies the identity; its value may sit above the floor only with a
  reviewed override, which the integrity gate checks.
- With no authored unspecified form the result is identity-neutral: no
  form_id, so no named form's notes, evidence or copy can attach.
- A form the label names that IQM does not recognize is not nondisclosure:
  the row keeps its identity, gets no form quality, reads
  form_match_status 'unmapped', and the product is held until curated.
- The enricher is the only form matcher; scoring consumes its reading.
"""
import copy
import json
import logging
from pathlib import Path

import pytest

from scoring_reference_resolver import (
    unknown_floor,
    unknown_floor_override,
    unknown_form_quality,
)

FIXTURES = Path(__file__).parent / 'fixtures'
IQM = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'ingredient_quality_map.json').read_text())

# parent -> (lowest eligible named bio_score, the named form the old fallback invented)
DERIVED = {
    'hmb': (13, 'hmb calcium salt (hmb-ca)'),
    'l_leucine': (14, 'l-leucine powder'),
    'acacia_catechu': (9, 'acacia catechu wood and bark extract'),
    'chlorophyll': (3, 'natural chlorophyll'),
}


@pytest.fixture(scope='module')
def enricher():
    from enrich_supplements_v3 import SupplementEnricherV3
    logging.disable(logging.INFO)
    return SupplementEnricherV3()


def _enrich(enricher, label):
    from enhanced_normalizer import EnhancedDSLDNormalizer
    raw = json.loads((FIXTURES / label).read_text())
    enriched, _ = enricher.enrich_product(EnhancedDSLDNormalizer().normalize_product(raw))
    return enriched


# ── the unknown-form value ────────────────────────────────────────────────────

@pytest.mark.parametrize('parent', sorted(DERIVED))
def test_without_an_authored_unspecified_form_the_unknown_is_lowest_eligible_minus_one(parent):
    lowest, _ = DERIVED[parent]
    assert unknown_form_quality(IQM[parent]) == {
        'form_id': None, 'form': None, 'bio_score': lowest - 1.0,
        'basis': 'derived_lowest_eligible_minus_one'}


def test_an_authored_unspecified_form_is_capped_at_the_floor():
    # calcium (unspecified) was 6; the plainest eligible calcium form is the
    # oxide at 4, so nondisclosure is worth 3.
    unknown = unknown_form_quality(IQM['calcium'])
    assert (unknown['form_id'], unknown['bio_score']) == ('calcium (unspecified)', 3.0)
    assert unknown_floor(IQM['calcium']) == (3.0, 'calcium oxide')


def test_an_ineligible_form_never_sets_the_floor():
    # D-tyrosine (PubChem CID 71098, (2R)) is the enantiomer of L-tyrosine
    # (CID 6057, (2S); parent UNII 42HK56048U Tyrosine). Its typed
    # parent_relationship keeps it from defining what an undisclosed
    # L-tyrosine is worth (N-acetyl L-tyrosine 8 - 1), and a label naming it
    # is held for identity verification, never scored as L-tyrosine.
    tyrosine = IQM['l_tyrosine']
    assert tyrosine['forms']['d-tyrosine']['parent_relationship'] == 'wrong_stereoisomer'
    assert 'unknown_floor' not in tyrosine['forms']['d-tyrosine']
    assert unknown_floor(tyrosine) == (7.0, 'n-acetyl l-tyrosine')
    assert unknown_form_quality(tyrosine)['bio_score'] == 7.0


def test_the_derived_value_never_goes_below_zero():
    assert unknown_form_quality({'forms': {'x': {'bio_score': 0}}})['bio_score'] == 0.0


def test_a_source_preparation_is_not_an_eligible_named_form():
    parent = {'forms': {'plain': {'bio_score': 8},
                        'from shellfish': {'bio_score': 2, 'alias_identity_scope': 'source_preparation'}}}
    assert unknown_form_quality(parent)['bio_score'] == 7.0


def test_nondisclosure_is_never_worth_more_than_the_floor_without_an_override():
    parent = {'forms': {'plain': {'bio_score': 8},
                        'x (unspecified)': {'bio_score': 12}}}
    assert unknown_form_quality(parent)['bio_score'] == 7.0
    reviewed = copy.deepcopy(parent)
    reviewed['forms']['x (unspecified)']['unknown_floor'] = {
        'override': True, 'rationale': 'r', 'reviewed_by': 'b', 'reviewed_on': '2026-09-25'}
    assert unknown_form_quality(reviewed)['bio_score'] == 12.0
    incomplete = copy.deepcopy(reviewed)
    incomplete['forms']['x (unspecified)']['unknown_floor']['reviewed_by'] = ''
    assert unknown_form_quality(incomplete)['bio_score'] == 7.0


def test_every_shipped_override_is_documented_and_every_unspecified_form_is_at_or_below_its_floor():
    from scoring_reference_resolver import authored_unknown_form
    overrides = []
    for key, entry in IQM.items():
        if key == '_metadata' or not isinstance(entry, dict):
            continue
        authored, floor = authored_unknown_form(entry), unknown_floor(entry)
        if not authored or not floor:
            continue
        if unknown_floor_override(authored[1]):
            overrides.append(key)
        else:
            assert authored[1]['bio_score'] <= floor[0], (key, authored[1]['bio_score'], floor)
    assert sorted(overrides) == sorted([
        'magnesium', 'zinc', 'iron', 'vitamin_a', 'beta_carotene', 'bacillus_subtilis',
        'phosphatidylcholine', 'rhodiola', 'ginkgo', 'msm', 'phosphatidylserine',
        'acetyl_l_carnitine', 'creatine_monohydrate', 'vanadyl_sulfate', 'capsaicin',
        # These label-identity forms have no reviewed absorption premium over
        # their parent baseline. The override prevents disclosure alone from
        # manufacturing a quality advantage.
        'nickel', 'tin', 'yohimbe'])


def test_the_integrity_gate_rejects_an_undocumented_value_above_the_floor():
    from db_integrity_sanity_check import check_iqm
    mutated = copy.deepcopy(IQM)
    mutated['calcium']['forms']['calcium (unspecified)']['bio_score'] = 9
    del mutated['magnesium']['forms']['magnesium (unspecified)']['unknown_floor']['reviewed_by']
    findings = []
    check_iqm(findings, mutated, 'ingredient_quality_map.json')
    codes = {(f.path, f.issue) for f in findings if f.severity == 'error'}
    assert ('calcium.forms.calcium (unspecified).bio_score', 'unspecified_above_floor') in codes
    assert ('magnesium.forms.magnesium (unspecified).unknown_floor', 'invalid_unknown_floor') in codes


def test_the_integrity_gate_rejects_an_unknown_relationship_and_a_retired_floor_mark():
    from db_integrity_sanity_check import check_iqm
    mutated = copy.deepcopy(IQM)
    mutated['l_tyrosine']['forms']['d-tyrosine']['parent_relationship'] = 'enantiomer-ish'
    mutated['iron']['forms']['iron oxide']['unknown_floor'] = {'eligible': False, 'reason': 'not_a_nutrient_source'}
    findings = []
    check_iqm(findings, mutated, 'ingredient_quality_map.json')
    codes = {(f.path, f.issue) for f in findings if f.severity == 'error'}
    assert ('l_tyrosine.forms.d-tyrosine.parent_relationship', 'enum_value_not_supported') in codes
    assert ('iron.forms.iron oxide.unknown_floor', 'invalid_unknown_floor') in codes


def test_the_per_form_checks_run_on_every_form_not_only_the_last():
    # The floor check once sat between the per-form checks, so absorption,
    # notes and dosage_importance ran only on each parent's last form.
    from db_integrity_sanity_check import check_iqm
    mutated = copy.deepcopy(IQM)
    names = list(mutated['calcium']['forms'])
    for name in (names[0], names[-1]):
        mutated['calcium']['forms'][name]['notes'] = 5
    findings = []
    check_iqm(findings, mutated, 'ingredient_quality_map.json')
    flagged = {f.path for f in findings if f.issue == 'type_mismatch' and f.path.endswith('.notes')}
    assert flagged == {f'calcium.forms.{names[0]}.notes', f'calcium.forms.{names[-1]}.notes'}


# ── the enricher's reading ────────────────────────────────────────────────────

@pytest.mark.parametrize('parent', sorted(DERIVED))
@pytest.mark.parametrize('label', ['Zqx Blend', 'Zqx Powder'])
def test_the_enricher_fallback_names_no_form(enricher, parent, label):
    lowest, invented = DERIVED[parent]
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'],
                                        _form_extraction_attempt=True, preferred_parent=parent,
                                        cleaner_canonical_id=parent)
    assert match['match_tier'] == 'cleaner_canonical_parent'
    assert match['form_id'] is None and match['fallback_form_name'] is None
    assert match['form_name'] == 'unspecified' != invented
    assert (match['notes'], match['absorption']) == (None, None)
    assert match['bio_score'] == lowest - 1.0


@pytest.mark.parametrize('label', ['HMB', 'HMB Powder', 'beta-hydroxy beta-methylbutyrate'])
def test_a_bare_hmb_label_names_no_salt(enricher, label):
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'])
    assert (match['canonical_id'], match['form_id'], match['bio_score']) == ('hmb', None, 12.0)


def test_the_parents_generic_form_is_not_a_reading_of_a_named_token(enricher):
    # "taurine (generic)" is taurine's authored unspecified form; before, it was
    # accepted as the form "Magnesium Taurate" named.
    from enrich_supplements_v3 import SupplementEnricherV3
    quality_map = enricher.databases['ingredient_quality_map']
    default = enricher._match_quality_map('Zqx', 'Zqx', quality_map, _form_extraction_attempt=True,
                                          preferred_parent='taurine', cleaner_canonical_id='taurine')
    assert default['form_id'] == 'taurine (generic)'
    assert not SupplementEnricherV3._is_specific_form_match(default, quality_map)


@pytest.mark.parametrize('parent, label, token, form', [
    ('phosphorus', 'Phosphorus', 'Dicalcium Phosphate', 'dicalcium phosphate (as phosphorus source)'),
    ('magnesium', 'Magnesium', 'Magnesium Ascorbate', 'magnesium ascorbate (as magnesium source)'),
    ('zinc', 'Zinc', 'Zinc Ascorbate', 'zinc ascorbate (as zinc source)'),
    ('taurine', 'Taurine', 'Magnesium Taurate', 'magnesium taurate (as taurine source)'),
    # 2026-09-28 form curation, batch 3: a nutrient row naming another nutrient's salt.
    ('calcium', 'Calcium', 'Calcium Pantothenate', 'calcium pantothenate (as calcium source)'),
    ('vitamin_c', 'Vitamin C', 'Chromium Ascorbate', 'vitamin c from chromium ascorbate'),
    ('potassium', 'Potassium', 'Potassium Ascorbate', 'potassium ascorbate (as potassium source)'),
    ('calcium', 'Calcium', 'Ester-C Calcium Ascorbate', 'calcium ascorbate (as calcium source)'),
    ('calcium', 'Calcium', 'Ester-C', 'calcium ascorbate (as calcium source)'),
    ('phosphorus', 'Phosphorus', 'Magnesium Phosphate', 'phosphate salts'),
    ('phosphorus', 'Phosphorus', 'Dimagnesium Phosphate', 'phosphate salts'),
    ('potassium', 'Potassium', 'Potassium Iodide', 'potassium (unspecified)'),
    ('calcium', 'Calcium', 'Calcium Phosphate Dibasic', 'dicalcium phosphate'),
])
def test_a_compound_filed_under_another_parent_reads_as_this_parents_counter_ion_form(
        enricher, parent, label, token, form):
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'],
                                        cleaned_forms=[{'name': token}], cleaner_canonical_id=parent)
    assert (match['canonical_id'], match['form_id']) == (parent, form)
    assert not match.get('unmapped_forms')


@pytest.mark.parametrize('parent, label, token, form', [
    ('l_arginine', 'Arginine AKG', 'L-Arginine-Alpha-Ketoglutarate', 'l-arginine akG'),
    ('nickel', 'Nickel', 'Nickel Sulfate', 'nickel sulfate'),
    ('tin', 'Tin', 'Stannous Chloride', 'stannous chloride'),
    ('silicon', 'Silicon', 'Silicon Dioxide', 'silicon dioxide (as silicon source)'),
    ('vanadium', 'Vanadium', 'Bis-Glycinato OxoVanadium', 'bis-glycinato oxovanadium'),
    ('yohimbe', 'Yohimbe Bark Extract', 'Yohimbine Alkaloids',
     'yohimbe extract standardized to yohimbine alkaloids'),
    # 2026-09-28 form curation, batch 1: phosphate salts (Emergen-C).
    ('phosphorus', 'Phosphorus', 'Monobasic Sodium Phosphate', 'phosphate salts'),
    ('phosphorus', 'Phosphorus', 'Monobasic Potassium Phosphate', 'phosphate salts'),
    ('phosphorus', 'Phosphorus', 'Monobasic Calcium Phosphate', 'phosphate salts'),
    ('phosphorus', 'Phosphorus', 'sodium phosphate', 'phosphate salts'),
    ('phosphorus', 'Phosphorus', 'Potassium Phosphate', 'phosphate salts'),
    ('phosphorus', 'Phosphorus', 'Dipotassium Phosphate', 'phosphate salts'),
    ('potassium', 'Potassium', 'Monobasic Potassium Phosphate', 'potassium phosphate'),
    ('calcium', 'Calcium', 'Monobasic Calcium Phosphate', 'monocalcium phosphate'),
    # 2026-09-28 form curation, batch 2: amino-acid chelates, glycinates, salt hydrates.
    ('chromium', 'Chromium', 'Chromium Glutamate', 'chromium (unspecified)'),
    ('chromium', 'Chromium', 'Chromium Chelate', 'chromium (unspecified)'),
    ('chromium', 'Chromium', 'fermented Chromium Glycinate', 'chromium (unspecified)'),
    ('chromium', 'Chromium', 'Chromium Glycinate', 'chromium (unspecified)'),
    ('chromium', 'Chromium', 'hydrolyzed Protein Chromium Chelate', 'chromium (unspecified)'),
    ('chromium', 'Chromium', 'Chromium Hydrolyzed Chelate Protein', 'chromium (unspecified)'),
    ('chromium', 'Chromium', 'Chromium Hydrolyzed Protein Chelate', 'chromium (unspecified)'),
    ('chromium', 'Chromium', 'Chromium Nicotinate Amino Acid Chelate', 'chromium (unspecified)'),
    ('manganese', 'Manganese', 'fermented Manganese Bisglycinate', 'manganese bisglycinate'),
    ('manganese', 'Manganese', 'Manganese Bisglycinate, Fermented', 'manganese bisglycinate'),
    ('manganese', 'Manganese', 'Manganese Glycinate Amino Acid Chelate', 'manganese bisglycinate'),
    ('manganese', 'Manganese', 'Manganese Glycinate Chelate', 'manganese bisglycinate'),
    ('manganese', 'Manganese', 'Manganese Citrate Chelate', 'manganese citrate'),
    ('molybdenum', 'Molybdenum', 'fermented Molybdenum Bisglycinate', 'molybdenum glycinate'),
    ('molybdenum', 'Molybdenum', 'Molybdenum Bisglycinate, Fermented', 'molybdenum glycinate'),
    ('molybdenum', 'Molybdenum', 'Molybdenum Glycinate Amino Acid Chelate', 'molybdenum glycinate'),
    ('molybdenum', 'Molybdenum', 'Molybdenum Hydrolyzed Rice Protein Chelate', 'molybdenum brown rice chelate'),
    ('boron', 'Boron', 'fermented Boron Triglycinate', 'boron glycinate'),
    ('boron', 'Boron', 'Boron Bisglycinate, Fermented', 'boron glycinate'),
    ('boron', 'Boron', 'Boron Triglycinate', 'boron glycinate'),
    ('boron', 'Boron', 'Boron Glycinate Chelate', 'boron glycinate'),
    ('boron', 'Boron', 'Boron Hydrolyzed Rice Protein Chelate', 'boron brown rice chelate'),
    ('boron', 'Boron', 'Boron Amino Acid Complex', 'boron (unspecified)'),
    ('iodine', 'Iodine', 'fermented Iodine Glycinate', 'iodine (unspecified)'),
    ('iodine', 'Iodine', 'Iodine Glycinate', 'iodine (unspecified)'),
    ('iodine', 'Iodine', 'Iodine Glycinate, Fermented', 'iodine (unspecified)'),
    ('copper', 'Copper', 'Copper Glycinate Amino Acid Chelate', 'copper bisglycinate'),
    ('copper', 'Copper', 'Albion Copper Glycinate Amino Acid Chelate', 'copper bisglycinate'),
    ('copper', 'Copper', 'Copper Bisglycinate, Fermented', 'copper bisglycinate'),
    ('copper', 'Copper', 'Copper Citrate Chelate', 'copper citrate'),
    ('magnesium', 'Magnesium', 'Magnesium Glycinate Amino Acid Chelate', 'magnesium glycinate'),
    ('magnesium', 'Magnesium', 'TRAACS Magnesium Bis-Glycinate Chelate', 'magnesium glycinate'),
    ('magnesium', 'Magnesium', 'Trimagnesium Dicitrate', 'magnesium citrate'),
    ('potassium', 'Potassium', 'Potassium Glycinate Amino Acid Complex', 'potassium glycinate'),
    ('potassium', 'Potassium', 'Potassium Glycinate complex', 'potassium glycinate'),
    ('potassium', 'Potassium', 'Potassium Glycine Complex', 'potassium glycinate'),
    ('potassium', 'Potassium', 'Potassium Amino Acid Complex', 'potassium (unspecified)'),
    ('zinc', 'Zinc', 'Zinc Glycinate Amino Acid Chelate', 'zinc bisglycinate'),
    ('zinc', 'Zinc', 'Zinc Bisglycinate, Fermented', 'zinc bisglycinate'),
    ('zinc', 'Zinc', 'Zinc Histidinate Chelate', 'zinc amino acid chelate'),
    ('zinc', 'Zinc', 'Zinc Hydrolyzed Vegetable Protein Chelate', 'zinc amino acid chelate'),
    ('zinc', 'Zinc', 'Zinc Citrate Dihydrate', 'zinc citrate'),
    ('zinc', 'Zinc', 'Trizinc Citrate', 'zinc citrate'),
    ('calcium', 'Calcium', 'Calcium Glycinate Amino Acid Chelate', 'calcium bis-glycinate'),
    ('calcium', 'Calcium', 'Calcium Citrate Tetrahydrate', 'calcium citrate'),
    ('selenium', 'Selenium', 'fermented Selenium Glycinate', 'selenium glycinate'),
    ('selenium', 'Selenium', 'Selenium Glycinate, Fermented', 'selenium glycinate'),
    ('iron', 'Iron', 'Iron Bisglycinate, Fermented', 'iron bisglycinate'),
    ('iron', 'Iron', 'Iron Bisglycinate Amino Acid Chelate', 'iron bisglycinate'),
    ('iron', 'Iron', 'Ferrous Bis-Glycinate', 'iron bisglycinate'),
    ('iron', 'Iron', 'Iron Hydrolyzed Protein Chelate', 'iron amino acid chelate'),
    ('iron', 'Iron', 'Iron Hydrolyzed Vegetable Protein Chelate', 'iron amino acid chelate'),
    ('iron', 'Iron', 'Soy Protein Iron Chelate, Hydrolyzed', 'iron amino acid chelate'),
    # 2026-09-28 form curation, batch 5: parent-scoped clues and exact spellings.
    ('alpha_linolenic_acid', 'Alpha-Linolenic Acid', 'ALA', 'alpha-linolenic acid (unspecified)'),
    ('digestive_enzymes', 'Enzyme Blend', 'Lactase', 'specific enzymes'),
    ('glucosamine', 'D-Glucosamine HCl', 'hydrochloride', 'glucosamine hydrochloride'),
    ('zinc', 'Zinc', 'OptiZinc Zinc Monomethionine', 'zinc monomethionine'),
    ('zinc', 'Zinc', 'Zinc L-Methionine Sulfate', 'zinc monomethionine'),
    ('coq10', 'Coenzyme Q10', 'Ubiquinone 10', 'ubiquinone standard'),
    ('vitamin_b6_pyridoxine', 'Vitamin B6', 'Pyridoxal-5-Phosphate', 'pyridoxal-5-phosphate (P5P)'),
    ('choline', 'Choline', 'DL-Choline Bitartrate', 'choline bitartrate'),
    ('choline', 'Choline', 'Choline L(+) Bitartrate', 'choline bitartrate'),
    ('selenium', 'Selenium', 'Se-Methyl L- Selenocysteine', 'selenium-methyl L-selenocysteine'),
    ('vitamin_b2_riboflavin', 'Vitamin B2', 'Riboflavin-5 Phosphate', 'riboflavin-5-phosphate'),
    ('beta_glucan', 'Beta Glucan', 'Beta 1-3 Glucan', 'beta-glucan'),
    ('l_carnitine', 'L-Carnitine', 'L-Carnitine L- Tartrate', 'l-carnitine tartrate (lclt)'),
    ('prebiotics', 'Prebiotic', 'Short-Chain Fructooligosaccharides', 'fructooligosaccharides (FOS)'),
    ('vitamin_e', 'Vitamin E', 'Alpha-Tocotrienol', 'tocotrienols'),
    ('vitamin_e', 'Vitamin E', 'Beta-Tocotrienol', 'tocotrienols'),
    ('feverfew', 'Feverfew', 'Parthenolides', 'feverfew extract (parthenolide)'),
    ('gotu_kola', 'Gotu Kola', 'Asiaticosides', 'gotu kola aerial extract'),
])
def test_real_dsld_disclosures_reach_their_reviewed_parent_scoped_form(
        enricher, parent, label, token, form):
    """Frozen scoring labels stay held until each disclosed form is curated."""
    match = enricher._match_quality_map(
        label,
        label,
        enricher.databases['ingredient_quality_map'],
        cleaned_forms=[{'name': token}],
        cleaner_canonical_id=parent,
    )
    assert (match['canonical_id'], match['form_id']) == (parent, form)
    assert match.get('form_match_status') != 'unmapped'
    assert not match.get('unmapped_forms')


@pytest.fixture(scope='module')
def normalizer():
    from enhanced_normalizer import EnhancedDSLDNormalizer
    return EnhancedDSLDNormalizer()


@pytest.mark.parametrize('name, identity', [
    ('Potassium Phosphate', ('potassium', 'ingredient_quality_map')),
    ('Dipotassium Phosphate', ('potassium', 'ingredient_quality_map')),
    ('Sodium Phosphate', ('PII_SODIUM_PHOSPHATE_GENERIC', 'other_ingredients')),
    ('Monosodium Phosphate', ('phosphorus', 'ingredient_quality_map')),
    ('Calcium Phosphate', ('calcium', 'ingredient_quality_map')),
    ('Calcium Pantothenate', ('vitamin_b5_pantothenic', 'ingredient_quality_map')),
    ('Chromium Ascorbate', ('chromium', 'ingredient_quality_map')),
    ('Potassium Ascorbate', ('vitamin_c', 'ingredient_quality_map')),
    ('Potassium Iodide', ('iodine', 'ingredient_quality_map')),
    ('Ester-C', ('vitamin_c', 'ingredient_quality_map')),
    ('Magnesium Phosphate', ('magnesium', 'ingredient_quality_map')),
    ('Calcium Phosphate Dibasic', ('dicalcium_phosphate', 'ingredient_quality_map')),
    ('ALA', ('alpha_lipoic_acid', 'ingredient_quality_map')),
    ('Lactase', ('lactase', 'ingredient_quality_map')),
    ('Hydrochloride', (None, None)),
    # Batch 7 reads it only under a vitamin A row: a standalone carotenoid row stays its own.
    ('Gamma-Carotene', (None, None)),
])
def test_curated_source_forms_leave_standalone_identities_alone(normalizer, name, identity):
    """Salt names curated as forms of another parent go in source_form_aliases,
    which the cleaner's identity index never reads: a row that is only
    "Sodium Phosphate" stays the excipient it was."""
    assert normalizer._resolve_canonical_identity(name, raw_name=name) == identity


_B = 'botanical'
_M = 'non-nutrient/non-botanical'


@pytest.mark.parametrize('parent, label, form', [
    # 2026-09-28 form curation, batch 4: DSLD form tags copied from real cleaned
    # labels. A plant a compound is taken from, or a standardization marker,
    # names no form of the row's parent.
    ('isoflavones', 'Soy Isoflavones', {'name': 'Glycine max', 'category': _B, 'ingredientGroup': 'Soy'}),
    ('inulin', 'Inulin', {'name': 'Chicory root extract', 'category': _B, 'ingredientGroup': 'chicory'}),
    ('huperzine_a', 'Huperzine A', {'name': 'Huperzia serrata', 'category': _B, 'ingredientGroup': 'Chinese Club Moss'}),
    ('resveratrol', 'Resveratrol', {'name': 'Polygonum cuspidatum', 'category': _B, 'ingredientGroup': 'Hu Zhang'}),
    ('iodine', 'Iodine', {'name': 'Kelp', 'category': 'other', 'prefix': 'as', 'ingredientGroup': 'Kelp'}),
    ('fiber', 'Galactomannan', {'name': 'Fenugreek', 'category': _B, 'ingredientGroup': 'Fenugreek'}),
    ('citrus_bioflavonoids', 'Citrus Bioflavonoids', {'name': 'Orange', 'category': _B, 'ingredientGroup': 'Orange (unspecified)'}),
    ('citrus_bioflavonoids', 'Citrus Bioflavonoids', {'name': 'Lemon', 'category': _B, 'ingredientGroup': 'Lemon'}),
    ('citrus_bioflavonoids', 'Citrus Bioflavonoids', {'name': 'Lime', 'category': _B, 'ingredientGroup': 'Lime'}),
    ('citrus_bioflavonoids', 'Citrus Bioflavonoids', {'name': 'Grapefruit', 'category': _B, 'ingredientGroup': 'Grapefruit'}),
    ('citrus_bioflavonoids', 'Citrus Bioflavonoids', {'name': 'Tangerine', 'category': _B, 'ingredientGroup': 'Tangerine'}),
    ('caffeine', 'Caffeine', {'name': 'Green Tea', 'category': _B, 'ingredientGroup': 'Green Tea'}),
    ('zeaxanthin', 'Zeaxanthin', {'name': 'Marigold Flower Extract', 'category': _B, 'ingredientGroup': 'Marigold (unspecified)'}),
    ('rhodiola', 'Rhodiola', {'name': 'Total Rosavins', 'category': _M, 'ingredientGroup': 'Rosavin'}),
    ('rhodiola', 'Rhodiola', {'name': 'Salidrosides', 'category': _M, 'ingredientGroup': 'Salidroside'}),
    ('saw_palmetto', 'Saw Palmetto', {'name': 'Total Fatty Acids', 'category': 'fatty acid', 'prefix': 'std. to 85%-', 'ingredientGroup': 'Fatty Acid (unspecified)'}),
    ('cayenne_pepper', 'Cayenne Pepper', {'name': 'Capsaicinoids', 'category': _M, 'prefix': 'standardized for', 'ingredientGroup': 'Capsaicinoid'}),
    # Batch 7: marigold, palm, chlorella; krill, Calanus and safflower oil carrying astaxanthin.
    ('lutein', 'Lutein', {'name': 'Tagetes erecta', 'category': _B, 'ingredientGroup': 'Tagetes'}),
    ('zeaxanthin', 'Zeaxanthin', {'name': 'Marigold', 'category': _B, 'ingredientGroup': 'Marigold (unspecified)'}),
    ('zeaxanthin', 'Zeaxanthin', {'name': 'Marigold Petal Extract', 'category': _B, 'ingredientGroup': 'Tagetes'}),
    ('zeaxanthin', 'Zeaxanthin Carotenoid', {'name': 'Aztec Marigold Flower Extract', 'category': _B, 'ingredientGroup': 'Tagetes'}),
    ('zeaxanthin', 'Zeaxanthin', {'name': 'Marigold flower ext.,', 'category': _B, 'ingredientGroup': 'Tagetes'}),
    ('astaxanthin', 'natural Astaxanthin', {'name': 'Safflower Oil', 'category': 'fat', 'prefix': 'in', 'ingredientGroup': 'Safflower Oil'}),
    ('astaxanthin', 'Astaxanthin', {'name': 'Krill Oil', 'category': 'fat', 'ingredientGroup': 'Krill Oil'}),
    ('astaxanthin', 'Astaxanthin', {'name': 'Calanus Oil', 'category': 'fat', 'ingredientGroup': 'Calanus finmarchicus Oil'}),
    ('alpha_carotene', 'Alpha-Carotene', {'name': 'Palm', 'category': _B, 'ingredientGroup': 'Oil Palm'}),
    ('vitamin_a', 'Carotenoids', {'name': 'Chlorella', 'category': 'other', 'ingredientGroup': 'Chlorella'}),
    ('chlorophyll', 'Chlorophyll', {'name': 'Chlorella', 'category': 'other', 'ingredientGroup': 'Chlorella'}),
    # Batch 8: Aquamin and Lithothamnion algae, rice bran, a multivitamin's fermented blends.
    ('magnesium', 'Magnesium', {'name': 'Aquamin calcified mineral source Red Algae', 'category': 'blend', 'prefix': 'and from', 'ingredientGroup': 'Proprietary Blend'}),
    ('magnesium', 'Magnesium', {'name': 'Aquamin', 'category': 'blend', 'ingredientGroup': 'Proprietary Blend'}),
    ('strontium', 'Strontium', {'name': 'Aquamin', 'category': 'blend', 'ingredientGroup': 'Proprietary Blend'}),
    ('silicon', 'Silicon', {'name': 'L. calcareum', 'category': 'other', 'prefix': 'and', 'ingredientGroup': 'Lithothamnion'}),
    ('calcium', 'Calcium', {'name': 'Rice Bran', 'category': 'fiber', 'ingredientGroup': 'Rice Bran'}),
    ('zinc', 'Zinc', {'name': 'Fermented Mineral Blend', 'category': 'blend', 'prefix': '& from', 'ingredientGroup': 'Blend (Mineral)'}),
    ('vitamin_c', 'Vitamin C', {'name': 'fermented Vitamin Blend', 'category': 'blend', 'prefix': '& from', 'ingredientGroup': 'Blend (Vitamin)'}),
])
def test_a_source_plant_or_standardization_marker_names_no_form(enricher, parent, label, form):
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'],
                                        cleaned_forms=[form], cleaner_canonical_id=parent)
    assert match['canonical_id'] == parent
    assert not match.get('unmapped_forms')



@pytest.mark.parametrize('parent, label, form', [
    # 2026-09-28 form curation, batch 9: one real held row per source plant or
    # standardization marker (enrich_supplements_v3._SOURCE_MATERIAL_TERMS,
    # _STANDARDIZATION_MARKER_TERMS). Some parents are botanical-database rows,
    # so only an IQM parent is passed as the cleaner's canonical.
    # The label the matcher sees once the cleaner's canonical is applied (329902, 62818).
    ('activated_charcoal', 'Activated Charcoal', {'name': 'Coconut', 'category': _B, 'ingredientGroup': 'Coconut'}),
    ('algae_oil', "life'sDHA Oil", {'name': 'plant based Algae', 'category': 'other', 'prefix': 'derived from a', 'ingredientGroup': 'Algae (unspecified)'}),
    ('algae_oil', 'Algal Oil', {'name': 'Schizochytrium spp.', 'category': 'other', 'ingredientGroup': 'Schizochytrium'}),
    ('alpha_linolenic_acid', 'Alpha-Linolenic Acid', {'name': 'Ahiflower', 'category': _B, 'ingredientGroup': 'Buglossoides arvensis'}),
    ('andrographis', 'Paractin (Bioactive 14-Neo-Andro Compound) Andrographis extract', {'name': '14-Deoxyandrographolides', 'category': _M, 'ingredientGroup': 'Deoxyandrographolides'}),
    ('andrographis', 'Paractin (Bioactive 14-Neo-Andro Compound) Andrographis extract', {'name': 'Neoandrographolides', 'category': _M, 'prefix': 'and', 'ingredientGroup': 'Neoandrographolides'}),
    ('beta_caryophyllene', 'Beta-Caryophyllene', {'name': 'Piper nigrum Berry Extract'}),
    ('blood_orange_extract', 'Morosil', {'name': 'Flavanones', 'category': _M, 'ingredientGroup': 'Flavanones'}),
    ('blood_orange_extract', 'Morosil', {'name': 'Hydroxycinammic acids', 'category': _M, 'ingredientGroup': 'Hydroxycinnamic acid'}),
    ('blueberry', 'Wild Blueberry', {'name': 'Phenolics', 'category': _M, 'prefix': 'providing naturally occurring', 'ingredientGroup': 'Phenolics (unspecified)'}),
    ('boswellia', 'ApresFlex Boswellia serrata gum extract', {'name': '3-0-Acetyl-11-Keto Beta Boswellic Acid', 'category': _M, 'ingredientGroup': '11-keto-beta-boswellic acid'}),
    ('boswellia', 'ApresFlex Boswellia serrata gum extract', {'name': 'Alpha-Keto-Boswellic Acids', 'category': _M, 'ingredientGroup': 'Alpha-keto-boswellic acid'}),
    ('boswellia', 'standardized Boswellia extract', {'name': 'Boswelic Acid', 'category': _M, 'ingredientGroup': 'Boswellic Acid'}),
    ('brown_kelp', 'Brown Seaweed Extract', {'name': 'Fucoxanthin', 'category': _M, 'ingredientGroup': 'Fucoxanthin'}),
    ('brown_kelp', 'Brown Seaweed Extract', {'name': 'Laminaria japonica Extract', 'category': _B, 'ingredientGroup': 'Laminaria'}),
    ('brown_kelp', 'Brown Seaweed Extract', {'name': 'Undaria pinnatifida Extract', 'category': 'other', 'ingredientGroup': 'Wakame'}),
    ('caffeine', 'Caffeine', {'name': 'Coffee bean extract', 'category': _B, 'prefix': 'as', 'ingredientGroup': 'Coffee'}),
    ('caffeine', 'Caffeine', {'name': 'Green Coffee', 'category': _B, 'ingredientGroup': 'Green Coffee'}),
    ('caffeine', 'Caffeine', {'name': 'Green Tea extract', 'category': _B, 'ingredientGroup': 'Green Tea'}),
    ('caffeine', 'Caffeine', {'name': 'Guarana extract', 'category': _B, 'ingredientGroup': 'Guarana '}),
    ('caffeine', 'Caffeine', {'name': 'Yerba Mate extract', 'category': _B, 'ingredientGroup': 'Mate'}),
    ('caffeine', 'Caffeine, Natural', {'name': 'Camellia sinensis', 'category': _B, 'ingredientGroup': 'Camellia sinensis'}),
    ('capsaicin', 'Capsifen', {'name': 'Capsaicinoid', 'category': _M, 'ingredientGroup': 'Capsaicinoids'}),
    ('cascara_sagrada', 'Cascara Sagrada', {'name': 'Cascarosides', 'category': _M, 'prefix': 'providing', 'ingredientGroup': 'Cascaroside'}),
    ('casein_hydrolysate', 'Casein Decapeptide', {'name': 'Milk Peptides', 'category': 'protein', 'prefix': 'bioactive', 'ingredientGroup': 'Milk Protein'}),
    ('casein_hydrolysate', 'Casein Decapeptide', {'name': 'bioactive Milk Peptides', 'category': 'protein', 'ingredientGroup': 'Casein Peptides'}),
    ('ceramides', 'Ceramosides', {'name': 'Wheat Seed Oil', 'category': _B, 'ingredientGroup': 'Wheat'}),
    ('ceramides', 'Lipowheat Wheat (Triticum vulgare) oil extract', {'name': 'Glycolipids', 'category': _M, 'prefix': 'providing', 'ingredientGroup': 'Glycolipids'}),
    ('ceramides', 'Lipowheat Wheat (Triticum vulgare) oil extract', {'name': 'Glycosylceramides', 'category': _M, 'prefix': 'and', 'ingredientGroup': 'Glycosylceramides'}),
    ('ceramides', 'Phytoceramides', {'name': 'Wheat Oil Extract', 'category': _B, 'ingredientGroup': 'Wheat'}),
    ('chanca_piedra', 'standardized Phyllanthus amarus extract', {'name': 'Bitter Principles', 'category': _M, 'ingredientGroup': 'Bitter Principles'}),
    ('chlorophyll', 'Chlorophyll', {'name': 'Morus alba, Powder', 'category': _B, 'ingredientGroup': 'White Mulberry'}),
    ('citrus_bergamot', 'Citrus bergamia Risso fruit extract', {'name': 'Polyphenolic flavanones', 'category': _M, 'prefix': '150 mg', 'ingredientGroup': 'Polyphenol (unspecified)'}),
    ('citrus_bioflavonoids', 'Citrus Bioflavonoid Complex', {'name': 'Citrus limon', 'category': _B, 'ingredientGroup': 'Lemon'}),
    ('citrus_bioflavonoids', 'Citrus Bioflavonoids', {'name': 'Citrus paradisi', 'category': _B, 'ingredientGroup': 'Grapefruit'}),
    ('citrus_bioflavonoids', 'Citrus Bioflavonoids', {'name': 'Citrus sinensis', 'category': _B, 'ingredientGroup': 'Sweet Orange'}),
    ('citrus_bioflavonoids', 'Citrus Bioflavonoids', {'name': 'Citrus spp.', 'category': _B, 'ingredientGroup': 'Citrus (unspecified)'}),
    ('citrus_bioflavonoids', 'Rutin', {'name': 'Saphora japonica', 'category': _B, 'ingredientGroup': 'Pagoda Tree'}),
    ('citrus_bioflavonoids', 'Rutin', {'name': 'Sophora japonica', 'category': _B, 'ingredientGroup': 'Pagoda Tree'}),
    ('citrus_bioflavonoids', 'Rutoside Trihydrate', {'name': 'Sophora japonica Extract, Dried, Purified', 'category': _B, 'ingredientGroup': 'Pagoda Tree'}),
    ('coffee_fruit', 'NeuroFactor Coffee fruit concentrate', {'name': '5-Caffeoylquinic Acid', 'category': _M, 'ingredientGroup': 'caffeoylquinic acids'}),
    ('collagen', 'Collagen, Hydrolyzed', {'name': 'Collagen Type I, Hydrolyzed', 'category': 'protein', 'ingredientGroup': 'Collagen'}),
    ('collagen', 'Collagen, Hydrolyzed', {'name': 'Collagen Type III, Hydrolyzed', 'category': 'protein', 'ingredientGroup': 'Collagen'}),
    ('collagen', 'Naticol', {'name': 'Collagen Type I', 'category': 'protein', 'ingredientGroup': 'Collagen'}),
    ('collagen', 'Verisol Bioactive Collagen Peptides', {'name': 'Type I Collagen', 'category': 'protein', 'ingredientGroup': 'Collagen'}),
    ('collagen', 'Verisol Bioactive Collagen Peptides', {'name': 'Type III Collagen', 'category': 'protein', 'ingredientGroup': 'Collagen'}),
    ('collagen', 'Verisol Bioactive Collagen', {'name': 'Collagen Type III', 'category': 'protein', 'ingredientGroup': 'Collagen'}),
    ('colostrum', 'Bovine Colostrum', {'name': 'IgG', 'category': _M, 'ingredientGroup': 'immunoglobulin'}),
    ('colostrum', 'Bovine Colostrum', {'name': 'Immunoglobulin G', 'category': _M, 'ingredientGroup': 'immunoglobulin'}),
    ('colostrum', 'Colostrinin', {'name': 'Proline-Rich Peptide Complex', 'category': 'protein', 'ingredientGroup': 'proline rich peptides'}),
    ('colostrum', 'Colostrum', {'name': 'Immunoglobulin G1 + G2', 'category': _M, 'prefix': 'min', 'ingredientGroup': 'immunoglobulin'}),
    ('cyanidin_3_glucoside', 'Cyanidin-3-Glucoside', {'name': 'European Black Currant Fruit Extract', 'category': _B, 'ingredientGroup': 'Black Currant'}),
    ('d_limonene', 'D-Limonene', {'name': 'Orange Oil', 'category': _B, 'prefix': 'from cold-pressed', 'ingredientGroup': 'Orange (unspecified)'}),
    ('dha', 'DHA', {'name': 'from Algae of Schizochytrium sp.', 'category': 'other', 'ingredientGroup': 'Schizochytrium'}),
    ('dihydromyricetin', 'Dihydromyricetin', {'name': 'Ampelopsis grossedentata', 'category': _B, 'ingredientGroup': 'Ampelopsis'}),
    ('ecdysterones', 'Ajuga turkest Whole Herb Extract', {'name': 'Ajuga L. Whole Herb Extract', 'category': _B, 'ingredientGroup': 'Ajuga turkestanica'}),
    ('echinacea', 'Echinacea purpurea root extract', {'name': 'Chicoric Acid', 'category': _M, 'ingredientGroup': 'Chicoric acid'}),
    ('egcg', 'Epigallocatechin Gallate', {'name': 'Green Tea leaf extract', 'category': _B, 'ingredientGroup': 'Green Tea'}),
    ('elderberry', 'Black Elderberry Extract', {'name': 'Anthocyanin', 'category': _M, 'ingredientGroup': 'anthocyanin'}),
    ('ellagic_acid', 'Ellagic Acid', {'name': 'Pomegranate Hull Extract', 'category': _B, 'ingredientGroup': 'Pomegranate'}),
    ('ellagic_acid', 'Ellagic Acid', {'name': 'Strawberry Fruit Extract', 'category': _B, 'ingredientGroup': 'Strawberry'}),
    ('ellagic_acid', 'Ellagic Acid', {'name': 'Strawberry extract', 'category': _B, 'prefix': 'and', 'ingredientGroup': 'Strawberry'}),
    ('english_ivy', 'English Ivy Leaf Extract', {'name': 'Hederacoside C', 'category': _M, 'ingredientGroup': 'Hederacoside'}),
    ('fisetin', 'Fisetin', {'name': 'Wax Tree Stem Extract', 'category': _B, 'ingredientGroup': 'Japanese Waxtree'}),
    ('fish_oil', 'Shark Liver Oil', {'name': 'Alkoxyglycerols', 'category': _M, 'ingredientGroup': 'Alkoxyglycerols'}),
    ('flavonoids', 'Flavonoids', {'name': 'Anthocyanidins', 'category': _M, 'ingredientGroup': 'Anthocyanidins (unspecified)'}),
    ('flavonoids', 'Flavonoids', {'name': 'Flavonols', 'category': _M, 'ingredientGroup': 'Flavonols'}),
    ('flavonoids', 'Flavonoids', {'name': 'Hyperoside', 'category': _M, 'prefix': 'and', 'ingredientGroup': 'Hyperoside'}),
    ('flavonoids', 'Flavonoids', {'name': 'Phenolic Acids', 'category': _M, 'prefix': 'and', 'ingredientGroup': 'Phenolic Acid'}),
    ('flower_pollen', 'Graminex(R) Flower Pollen Extract(TM)', {'name': 'Secale cereale', 'category': _B, 'ingredientGroup': 'Rye'}),
    ('ginkgo', 'Ginkgo biloba Leaf Extract', {'name': 'Ginkgoheterosides', 'category': _M, 'ingredientGroup': 'Ginkgoheteroside'}),
    ('ginkgo', 'Ginkgo biloba extract', {'name': 'Ginkgoflavoglycosides', 'category': _M, 'ingredientGroup': 'Ginkgo flavones'}),
    ('ginkgo', 'Ginkgo biloba extract', {'name': 'Ginkgolic Acid', 'category': _M, 'prefix': 'and <1ppm', 'ingredientGroup': 'Ginkgolic acid'}),
    ('ginkgo', 'Ginkgo extract', {'name': 'Flavonol Glycosides', 'category': _M, 'prefix': 'providing minimum', 'ingredientGroup': 'Flavonoid (mixture)'}),
    ('grape_seed_extract', 'Grape seed extract', {'name': 'other active Polyphenols', 'category': 'blend', 'prefix': 'and', 'ingredientGroup': 'Blend (non-nutrient/non-botanical)'}),
    ('green_coffee_bean', 'Green Coffee Bean Extract', {'name': 'Coffea arabica', 'category': _B, 'prefix': '&', 'ingredientGroup': 'Coffee'}),
    ('green_tea_extract', 'Green Tea (Camellia sinensis) extract', {'name': 'Epigallocatechin', 'category': _M, 'prefix': 'and', 'ingredientGroup': 'EGCG'}),
    ('green_tea_extract', 'Green Tea extract', {'name': 'ECGC', 'category': _M, 'ingredientGroup': 'EGCG'}),
    ('gypenosides', 'Gynostemma Leaf, Stem Extract', {'name': 'Gynostemma pentaphyllum Stem Extract', 'category': _B, 'ingredientGroup': 'Jiaogulan'}),
    ('huperzine_a', 'Huperzine A', {'name': 'Huperzia serrata Whole Plant Extract', 'category': _B, 'ingredientGroup': 'Toothed Clubmoss'}),
    ('huperzine_a', 'Huperzine A', {'name': 'Toothed Clubmoss Whole Herb Extract', 'category': _B, 'ingredientGroup': 'Toothed Clubmoss'}),
    ('inulin', 'Inulin', {'name': 'Chicory', 'category': _B, 'ingredientGroup': 'chicory'}),
    ('inulin', 'Inulin', {'name': 'Jerusalem Artichoke', 'category': _B, 'ingredientGroup': 'Jerusalem Artichoke'}),
    ('isoflavones', 'Isoflavones', {'name': 'Soybeans', 'category': _B, 'prefix': 'and', 'ingredientGroup': 'Soy'}),
    ('lecithin', 'Sunflower Lecithin', {'name': 'Helianthus annuus', 'category': _B, 'ingredientGroup': 'sunflower'}),
    ('lemon_balm', 'Lemon Balm Aerial Parts Extract', {'name': 'Hydroxycinnamic Acid', 'category': _M, 'ingredientGroup': 'Hydroxycinammic acid'}),
    ('lignans', 'HMRLignan', {'name': 'Soy Isoflavones Concentrate', 'category': _B, 'ingredientGroup': 'Soy'}),
    ('lignans', 'HMRlignan', {'name': 'Picea abies', 'category': _B, 'ingredientGroup': 'Hemlock spruce'}),
    ('lignans', 'HMRlignan', {'name': 'Norway Spruce Knotwood Extract', 'category': _B, 'ingredientGroup': 'Hemlock spruce'}),
    ('luteolin', 'Luteolin Phytosome', {'name': 'Chrysanthemum morifolium', 'category': _B, 'ingredientGroup': 'Mum'}),
    ('luteolin', 'Luteolin', {'name': 'Japanese Sophora Flower Extract', 'category': _B, 'ingredientGroup': 'Sophora (unspecified)'}),
    ('mct_oil', 'Medium Chain Triglyceride', {'name': 'Coconut Cream', 'category': 'blend', 'ingredientGroup': 'Blend'}),
    ('mesembrine', 'Zembrin', {'name': 'Sceletium tortuosum Aerial Parts Extract', 'category': _B, 'ingredientGroup': 'Sceletium'}),
    ('mucuna_pruriens', 'Mucuna pruriens Seed Extract', {'name': 'L-Dihydroxyphenylalanine', 'category': _M, 'ingredientGroup': 'L-DOPA'}),
    ('naringin', 'Naringin', {'name': 'Citrus hongheensis Fruit Extract', 'category': _B, 'ingredientGroup': 'Citrus '}),
    ('naringin', 'Naringin', {'name': 'Citrus', 'category': _B, 'ingredientGroup': 'Citrus (unspecified)'}),
    ('nobiletin', 'Nobiletin', {'name': 'Citrus fruit', 'category': _B, 'prefix': 'from young', 'ingredientGroup': 'Citrus (unspecified)'}),
    ('olive_leaf', 'Olive leaf extract', {'name': 'Maslinic Acid', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Maslinic Acid'}),
    ('opc', 'Oligomeric Proanthocyanidins', {'name': 'Hawthorn Fruit, Flower, Stem Extract', 'category': _B, 'ingredientGroup': 'Hawthorn'}),
    ('opc', 'Oligomeric proanthocyanidins', {'name': 'Hawthorn extract', 'category': _B, 'prefix': 'from standardized', 'ingredientGroup': 'Hawthorn'}),
    ('phosphatidylserine', 'Phosphatidylserine', {'name': 'Soy', 'category': _B, 'ingredientGroup': 'Soy'}),
    ('phytosterols', 'Beta-Sitosterol', {'name': 'Pine', 'category': _B, 'ingredientGroup': 'Pine'}),
    ('picrorhiza', 'Picrorhiza kurroa root extract', {'name': 'Apocynin', 'category': _M, 'ingredientGroup': 'Apocynin'}),
    ('picrorhiza', 'Picrorhiza kurroa root extract', {'name': 'Picroside I & II', 'category': _M, 'ingredientGroup': 'Picroside'}),
    ('picrorhiza', 'Picrorhiza kurrooa root extract', {'name': 'Picroside II', 'category': _M, 'ingredientGroup': 'Picroside'}),
    ('piperine', 'Black Pepper fruit extract', {'name': '50% Piperine', 'category': _M, 'ingredientGroup': 'Piperine'}),
    ('polyphenols', 'Polyphenols', {'name': 'Cranberry (Vaccinium macrocarpon) extract', 'category': _B, 'prefix': 'and', 'ingredientGroup': 'cranberry'}),
    ('polyphenols', 'Polyphenols', {'name': 'Grape Seed Extract', 'category': _B, 'prefix': 'and', 'ingredientGroup': 'Grape '}),
    ('pterostilbene', 'Trans-Pterostilbene', {'name': 'Pterocarpus marsupium', 'category': _B, 'ingredientGroup': 'Indian Kinotree'}),
    ('purple_corn_extract', 'Purple Corn extract', {'name': 'total Phenols', 'category': _M, 'ingredientGroup': 'Phenolic (unspecified)'}),
    ('quercetin', 'Quercetin', {'name': 'Sophorae japonica', 'category': _B, 'ingredientGroup': 'Pagoda Tree'}),
    ('red_clover', 'standardized Red Clover extract', {'name': 'Biochanins', 'category': _M, 'ingredientGroup': 'biochanin'}),
    ('red_wine_extract', 'Red Wine Complex', {'name': 'Grape Extract', 'category': _B, 'ingredientGroup': 'Grape '}),
    ('red_wine_extract', 'Red Wine Complex', {'name': 'Grapeseed extract', 'category': _B, 'ingredientGroup': 'Grape '}),
    ('red_wine_extract', 'Red Wine Extract', {'name': 'Vitis vinifera Extract', 'category': _B, 'ingredientGroup': 'Grape '}),
    ('red_wine_extract', 'Red Wine extract', {'name': 'Vitis vinifera', 'category': _B, 'ingredientGroup': 'Grape '}),
    ('reishi', 'Reishi Mushroom', {'name': 'Purple Corn optimized biomass', 'category': 'blend', 'ingredientGroup': 'Blend (Combination)'}),
    ('reishi', 'Reishi Mushroom', {'name': 'Purple Kculli Corn optimized biomass', 'category': _B, 'ingredientGroup': 'Corn'}),
    ('reishi', 'Reishi Mushroom', {'name': 'Purple Kculli Corn', 'category': _B, 'ingredientGroup': 'Corn'}),
    ('resveratrol', 'Resveratrol Complex', {'name': 'Grapeseed', 'category': _B, 'ingredientGroup': 'Grape '}),
    ('resveratrol', 'Resveratrol Complex', {'name': 'Grapeskin extract', 'category': _B, 'prefix': 'and', 'ingredientGroup': 'Grape '}),
    ('resveratrol', 'Resveratrol', {'name': 'Fallopia japonica', 'category': _B, 'ingredientGroup': 'Hu Zhang'}),
    ('resveratrol', 'Resveratrol', {'name': 'Tiger Cane', 'category': _B, 'ingredientGroup': 'Hu Zhang'}),
    ('resveratrol', 'Trans-Resveratrol', {'name': 'Glycosides', 'category': _M, 'prefix': 'also supplying', 'ingredientGroup': 'Glycoside (unspecified)'}),
    ('resveratrol', 'Trans-Resveratrol', {'name': 'Grape fruit extract', 'category': _B, 'ingredientGroup': 'Grape '}),
    ('resveratrol', 'Trans-Resveratrol', {'name': 'Red Grape (fruit) extract', 'category': _B, 'prefix': 'and', 'ingredientGroup': 'Grape '}),
    ('resveratrol', 'Trans-Resveratrol', {'name': 'Red Grape extracts', 'category': _B, 'prefix': 'and whole', 'ingredientGroup': 'Grape '}),
    ('resveratrol', 'Trans-Resveratrol', {'name': 'whole Red Grape extract', 'category': _B, 'prefix': 'and', 'ingredientGroup': 'Grape '}),
    ('rosemary', 'Rosemary Leaf Extract', {'name': 'Diterpenic Compounds', 'category': _M, 'ingredientGroup': 'Diterpene (unspecified)'}),
    ('rosemary', 'Rosemary extract', {'name': 'Carnosic Acid/Carnosol', 'category': 'blend', 'prefix': 'providing', 'ingredientGroup': 'Blend (non-nutrient/non-botanical)'}),
    ('saw_palmetto', 'standardized Saw Palmetto extract', {'name': 'free Fatty Acids', 'category': 'blend', 'ingredientGroup': 'Blend (Fatty Acid or Fat/Oil Supplement)'}),
    ('serrapeptase', 'Serrapeptase', {'name': 'Serratia sp.', 'category': 'bacteria', 'ingredientGroup': 'TBD'}),
    ('siberian_ginseng', 'Siberian root & rhizome powder', {'name': 'Eleuthrosides', 'category': _M, 'ingredientGroup': 'Eleutheroside'}),
    ('siberian_ginseng', 'standardized Eleuthero extract', {'name': 'Eleutherosides E and B', 'category': _M, 'ingredientGroup': 'Eleutheroside'}),
    ('soybean', 'Soybean extract', {'name': 'Genistein', 'category': _M, 'prefix': 'providing', 'ingredientGroup': 'Genistein'}),
    ('st_johns_wort', "St. John's Wort extract", {'name': 'Dianthrones', 'category': _M, 'ingredientGroup': 'Dianthrone (unspecified)'}),
    ('stinging_nettle', 'standardized Nettles extract', {'name': 'Silicic Acid', 'category': 'mineral', 'prefix': '[0.75 mg]', 'ingredientGroup': 'Silicon'}),
    ('sulforaphane', 'Sulforaphane Glucosinate', {'name': 'Kale', 'category': _B, 'ingredientGroup': 'Kale'}),
    ('sulforaphane', 'Sulforaphane Glucosinolate', {'name': 'Broccoli seed extract', 'category': _B, 'ingredientGroup': 'Broccoli'}),
    ('threonic_acid', 'Threonic Acid', {'name': 'Ester-C', 'category': 'blend', 'ingredientGroup': 'Proprietary Blend'}),
    ('tongkat_ali', 'LJ100 Eurycoma longifolia extract', {'name': 'Bioactive Eurypeptides', 'category': 'protein', 'ingredientGroup': 'Eurypeptides'}),
    ('tongkat_ali', 'LJ100 Eurycoma longifolia extract', {'name': 'Glyco Saponins', 'category': _M, 'ingredientGroup': 'Glycosaponin (unspecified)'}),
    ('ursolic_acid', 'Ursolic Acid', {'name': 'Holy Basil leaf extract', 'category': _B, 'ingredientGroup': 'Holy Basil'}),
    ('winged_treebine', 'Cissus quadrangularis Root Extract', {'name': 'Ketosterones', 'category': _M, 'ingredientGroup': 'Ketosterones (unspecified)'}),
    ('yohimbe', 'Yohimbe bark extract', {'name': 'Yohimbe Alkaloid', 'category': _M, 'ingredientGroup': 'Yohimbine'}),
    ('yohimbe', 'Yohimbe bark extract', {'name': 'Yohimbe Alkaloids', 'category': _M, 'ingredientGroup': 'Yohimbine'}),
])
def test_a_held_source_or_marker_token_leaves_the_row_unheld(enricher, parent, label, form):
    iqm = enricher.databases['ingredient_quality_map']
    match = enricher._match_quality_map(label, label, iqm, cleaned_forms=[form],
                                        cleaner_canonical_id=parent if parent in iqm else None) or {}
    assert match.get('match_status') != 'FORM_DISCLOSED_UNMAPPED'
    assert not match.get('unmapped_forms')

@pytest.mark.parametrize('parent, label, form, expected', [
    # 2026-09-28 form curation, batch 6: DSLD tags copied from the held labels, including
    # the two approved submissions (Quatrefolic folate; EPA/DHA ethyl ester).
    ('beta_carotene', 'Mixed Carotenoids', {'name': 'Alpha-Carotene', 'category': 'non-nutrient/non-botanical', 'ingredientGroup': 'Alpha-carotene'}, 'natural beta-carotene (from dunaliella salina)'),
    ('chlorophyll', 'Chlorophyll', {'name': 'Chlorophyllin Copper Complex', 'category': 'non-nutrient/non-botanical', 'ingredientGroup': 'Chlorophyllin'}, 'copper chlorophyllin'),
    ('copper', 'Copper', {'name': 'Chlorophyllin Copper Complex Sodium', 'category': 'non-nutrient/non-botanical', 'ingredientGroup': 'Chlorophyllin'}, 'copper (unspecified)'),
    ('vitamin_e', 'Vitamin E', {'name': 'D-Beta-Tocopherol', 'category': 'vitamin', 'ingredientGroup': 'Vitamin E'}, 'mixed tocopherols'),
    ('vitamin_e', 'Vitamin E', {'name': 'D-Delta-Tocopherol', 'category': 'vitamin', 'ingredientGroup': 'Vitamin E'}, 'mixed tocopherols'),
    ('epa', 'KD-Pur EPA', {'name': 'Ethyl Ester', 'category': 'non-nutrient/non-botanical', 'prefix': 'as', 'ingredientGroup': 'Ethyl Ester'}, 'EPA fish oil ethyl ester'),
    ('chamomile', 'Chamomile Flower Extract', {'name': 'Matricaria chamomilla Flower Extract', 'category': 'botanical', 'ingredientGroup': 'German Chamomile '}, 'chamomile extract'),
    ('beta_carotene', 'Vitamin A', {'name': 'Mixed Carotenoids', 'category': 'non-nutrient/non-botanical', 'prefix': 'with', 'ingredientGroup': 'carotenoids'}, 'natural beta-carotene (from dunaliella salina)'),
    ('vitamin_b9_folate', 'Folate', {'name': '6S-5-Methyltetrahydrofolate (glucosamine salt)'}, 'quatrefolic'),
    ('shilajit', 'ElevATP', {'name': 'Apple Extract', 'category': 'botanical'}, 'fulvic acid'),
    ('shilajit', 'ElevATP', {'name': 'Ancient Peat extract', 'category': 'other'}, 'fulvic acid'),
    # Batch 7 (carotenoids). FloraGLO's brand still decides its form; the generic
    # "Lutein Carotenoid" alias reads unspecified lutein under a plain Lutein row.
    ('lutein', 'FloraGLO', {'name': 'Lutein Carotenoid', 'category': _M, 'ingredientGroup': 'Lutein'}, 'free lutein (floraglo / lutemax, marigold)'),
    ('lutein', 'Lutein', {'name': 'Lutein Carotenoid', 'category': _M, 'ingredientGroup': 'Lutein'}, 'lutein (unspecified)'),
    ('beta_carotene', 'Vitamin A', {'name': 'Alpha Carotene', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Alpha-carotene'}, 'natural beta-carotene (from dunaliella salina)'),
    ('beta_carotene', 'Mixed Carotenoids', {'name': 'Cryptoxanthin', 'category': _M, 'ingredientGroup': 'Cryptoxanthin'}, 'natural beta-carotene (from dunaliella salina)'),
    ('vitamin_a', 'Mixed Carotenoids', {'name': 'Alpha-Carotene', 'category': _M, 'ingredientGroup': 'Alpha-carotene'}, 'alpha-carotene (provitamin A activity)'),
    ('vitamin_a', 'Mixed Carotenoids', {'name': 'Cryptoxanthin', 'category': _M, 'ingredientGroup': 'Cryptoxanthin'}, 'beta-cryptoxanthin (provitamin A activity)'),
    ('vitamin_a', 'Carotenoid Blend', {'name': 'Gamma-Carotene', 'category': _M, 'ingredientGroup': 'Gamma-carotene'}, 'vitamin a (unspecified)'),
    ('vitamin_a', 'Vitamin A', {'name': 'RETINYL PALMIATE', 'category': 'vitamin', 'ingredientGroup': 'Vitamin A (retinyl palmitate)'}, 'retinyl palmitate'),
    ('zeaxanthin', 'Zeaxanthin', {'name': 'Lutemax 2020', 'category': _B, 'ingredientGroup': 'Tagetes'}, 'zeaxanthin (unspecified)'),
    ('zeaxanthin', 'Zeaxanthin Isomers', {'name': 'Lutemax 2020 Aztec Marigold extract', 'category': _B, 'ingredientGroup': 'Tagetes'}, 'zeaxanthin (unspecified)'),
    ('zeaxanthin', 'Zeaxanthin Isomers', {'name': 'Lutemax 2020 Marigold flower extract', 'category': _B, 'ingredientGroup': 'Marigold (unspecified)'}, 'zeaxanthin (unspecified)'),
    ('zeaxanthin', 'Zeaxanthin', {'name': 'Lute-Gen', 'category': _B, 'ingredientGroup': 'Marigold (unspecified)'}, 'zeaxanthin (unspecified)'),
    ('zeaxanthin', 'Zeaxanthin', {'name': 'Mesozeaxanthin', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Zeaxanthin'}, 'zeaxanthin (unspecified)'),
    ('zeaxanthin', 'Zeaxanthin', {'name': 'RR Xeaxanthin', 'category': _M, 'prefix': 'and', 'ingredientGroup': 'Zeaxanthin'}, 'zeaxanthin (unspecified)'),
    ('astaxanthin', 'Astaxanthin', {'name': 'Haematococcus pluvialis microalgae', 'category': 'other', 'prefix': 'solvent-free extract from', 'ingredientGroup': 'Haematococcus pluvialis'}, 'natural astaxanthin (haematococcus pluvialis)'),
    # Batch 8 (minerals): spellings, hydrates and brands of held forms; salts the map does not
    # characterize read as the parent's unspecified form, as calcium aspartate already does.
    ('calcium', 'Calcium', {'name': 'Calcium L-Aspartate', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Calcium'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium Krebs Cycle Chelates', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium Laurate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium Caprylate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium Undecylenate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium Stearate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium Silicate', 'category': 'other', 'ingredientGroup': 'Calcium Silicate'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium Magnesium Phytate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium-Magnesium Inositol Hexaphosphate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium Beta-Hydroxy-Beta-Methylbutyrate Monohydrate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium Beta-Hydroxy-Beta-Methylbutyrate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium Beta-Hydroxybutyrate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium Pyruvate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium (unspecified)'),
    ('calcium', 'Calcium', {'name': 'Calcium Lactate Pentahydrate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium lactate'),
    ('calcium', 'Calcium', {'name': 'Albion Dicalcium Malate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium malate'),
    ('calcium', 'Calcium', {'name': 'Albion DimaCal', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium malate'),
    ('calcium', 'Calcium', {'name': 'Calcium Hydrolyzed Vegetable Protein', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium amino acid chelate'),
    ('calcium', 'Calcium', {'name': 'KoACT Calcium Collagen Chelate', 'category': _M, 'prefix': 'and', 'ingredientGroup': 'Calcium'}, 'calcium amino acid chelate'),
    ('calcium', 'Calcium', {'name': 'Microcrystalline Hydroxyapatite Calcium', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium hydroxyapatite'),
    ('calcium', 'Calcium', {'name': 'Calcium Magnesium Citrate', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Calcium Magnesium Citrate'}, 'calcium citrate'),
    ('calcium', 'Calcium', {'name': 'Calcium Bisglycinate, Fermented', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium bis-glycinate'),
    ('magnesium', 'Magnesium', {'name': 'ZumXR Magnesium Oxide', 'category': 'mineral', 'prefix': 'as', 'ingredientGroup': 'Magnesium'}, 'magnesium oxide'),
    ('magnesium', 'Magnesium', {'name': 'magneisum carbonate', 'category': 'mineral', 'ingredientGroup': 'Magnesium'}, 'magnesium carbonate'),
    ('magnesium', 'Magnesium', {'name': 'Calcium Magnesium Citrate', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Calcium Magnesium Citrate'}, 'magnesium citrate'),
    ('magnesium', 'ATA Mg', {'name': 'Magnesium Acetyl Taurinate', 'category': 'mineral', 'ingredientGroup': 'Magnesiium'}, 'magnesium acetyl-taurate'),
    ('magnesium', 'Magnesium', {'name': 'Magnesium Bisglycinate, Fermented', 'category': 'mineral', 'ingredientGroup': 'Magnesium'}, 'magnesium glycinate'),
    ('magnesium', 'Magnesium', {'name': 'Magnesium Hydrolyzed Vegetable Protein Chelate', 'category': 'mineral', 'ingredientGroup': 'Magnesium'}, 'magnesium amino acid chelate'),
    ('magnesium', 'Magnesium', {'name': 'Magnesium Lysinate', 'category': 'mineral', 'ingredientGroup': 'Magnesium'}, 'magnesium amino acid chelate'),
    ('magnesium', 'Magnesium', {'name': 'Calcium Magnesium Phytate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'magnesium (unspecified)'),
    ('magnesium', 'Magnesium', {'name': 'Magnesium D-Aspartate', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Magnesium'}, 'magnesium (unspecified)'),
    ('zinc', 'Zinc', {'name': 'OptiZinc(R) Brand MonoMethionine-bound Zinc', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Zinc'}, 'zinc monomethionine'),
    ('zinc', 'Zinc', {'name': 'L-Monomethionine', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Zinc'}, 'zinc monomethionine'),
    ('zinc', 'Zinc', {'name': 'Zinc Krebs Cycle Chelates', 'category': 'mineral', 'ingredientGroup': 'Zinc'}, 'zinc (unspecified)'),
    ('zinc', 'Zinc', {'name': 'Zinc Caprylate', 'category': 'mineral', 'ingredientGroup': 'Zinc'}, 'zinc (unspecified)'),
    ('zinc', 'Zinc', {'name': 'Zinc Quercetin', 'category': 'mineral', 'ingredientGroup': 'Zinc'}, 'zinc (unspecified)'),
    ('iron', 'Iron', {'name': 'Iron Aspartate', 'category': 'mineral', 'ingredientGroup': 'Iron'}, 'iron (unspecified)'),
    ('iron', 'Iron', {'name': 'Ferrous Succinate', 'category': 'mineral', 'ingredientGroup': 'Iron'}, 'iron (unspecified)'),
    ('iron', 'Iron', {'name': 'Ferric Glycinate', 'category': 'mineral', 'ingredientGroup': 'Iron'}, 'ferric iron'),
    ('copper', 'Copper', {'name': 'Copper Hydrolyzed Vegetable Protein', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Copper'}, 'copper amino acid chelate'),
    ('copper', 'Copper', {'name': 'Copper Chlorophyllin', 'category': 'mineral', 'ingredientGroup': 'Copper'}, 'copper (unspecified)'),
    ('copper', 'Copper', {'name': 'Copper Complex', 'category': 'blend', 'prefix': 'as', 'ingredientGroup': 'Blend (Combination)'}, 'copper (unspecified)'),
    ('manganese', 'Manganese, Powder', {'name': 'Manganese Gluconate, Powder', 'category': 'mineral', 'ingredientGroup': 'Manganese'}, 'manganese gluconate'),
    ('manganese', 'Manganese', {'name': 'Manganese Hydrolyzed Vegetable Protein', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Manganese'}, 'manganese amino acid chelate'),
    ('manganese', 'Manganese', {'name': 'Manganese Complex', 'category': 'mineral', 'prefix': 'as', 'ingredientGroup': 'Manganese'}, 'manganese (unspecified)'),
    ('molybdenum', 'Molybdenum', {'name': 'Sodium Molybdenate', 'category': 'mineral', 'ingredientGroup': 'Sodium'}, 'sodium molybdate'),
    ('molybdenum', 'Molybdenum', {'name': 'Sodium Molybdenum', 'category': 'mineral', 'ingredientGroup': 'Sodium'}, 'sodium molybdate'),
    ('molybdenum', 'Molybdenum', {'name': 'Molybdenum Hydrolyzed Vegetable Protein', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Molybdenum'}, 'molybdenum (unspecified)'),
    ('selenium', 'Selenium', {'name': 'Sodium Selenite Anhydrous', 'category': 'mineral', 'ingredientGroup': 'Selenium'}, 'sodium selenite'),
    ('selenium', 'Selenium', {'name': 'Selenium Selenite', 'category': 'mineral', 'prefix': 'as', 'ingredientGroup': 'Selenium'}, 'sodium selenite'),
    ('selenium', 'Selenium', {'name': 'hydrolyzed Protein Selenium Chelate', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Selenium'}, 'selenium (unspecified)'),
    ('selenium', 'Selenium', {'name': 'Selenium Hydrolyzed Vegetable Protein', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Selenium'}, 'selenium (unspecified)'),
    ('selenium', 'Selenium', {'name': 'Selenium Hydrolyzed Vegetable Protein Chelate', 'category': 'mineral', 'ingredientGroup': 'Selenium'}, 'selenium (unspecified)'),
    ('selenium', 'Selenium', {'name': 'Selenium Malate', 'category': 'mineral', 'ingredientGroup': 'Selenium'}, 'selenium (unspecified)'),
    ('selenium', 'Selenium', {'name': 'Selenium Asparate', 'category': _M, 'ingredientGroup': 'Selenium'}, 'selenium (unspecified)'),
    ('nickel', 'Nickel', {'name': 'Nickelous Sulfate', 'category': 'other', 'prefix': 'as', 'ingredientGroup': 'Nickel Sulfate'}, 'nickel sulfate'),
    ('tin', 'Tin', {'name': 'Tin Chloride', 'category': 'other', 'prefix': 'as', 'ingredientGroup': 'Tin'}, 'tin (unspecified)'),
    ('boron', 'Boron', {'name': 'Sodium Tetraborate', 'category': 'mineral', 'ingredientGroup': 'Sodium'}, 'boron (unspecified)'),
    ('boron', 'Boron', {'name': 'Sodium Tetraborate Decahydrate', 'category': 'mineral', 'ingredientGroup': 'Sodium'}, 'boron (unspecified)'),
    ('boron', 'Boron', {'name': 'Sodium Boron', 'category': 'mineral', 'ingredientGroup': 'Sodium'}, 'boron (unspecified)'),
    ('boron', 'Boron', {'name': 'Boron Krebs Cycle Complex', 'category': _M, 'ingredientGroup': 'Boron'}, 'boron (unspecified)'),
    ('boron', 'Boron', {'name': 'Krebs Cycle Intermediate Blend', 'category': _M, 'ingredientGroup': 'Boron'}, 'boron (unspecified)'),
    ('boron', 'Boron Complex', {'name': 'Citric Acid', 'category': _M, 'ingredientGroup': 'Citric Acid'}, 'boron citrate'),
    ('boron', 'Boron', {'name': 'Citric Acid complex', 'category': _M, 'ingredientGroup': 'Citric Acid'}, 'boron citrate'),
    ('boron', 'Boron', {'name': 'Citric Acid Blend', 'category': _M, 'prefix': 'and', 'ingredientGroup': 'Citric Acid'}, 'boron citrate'),
    ('chromium', 'Chromium', {'name': 'Chromium Yeast', 'category': 'other', 'prefix': 'as', 'ingredientGroup': 'Yeast (unspecified)'}, 'chromium GTF'),
    ('chromium', 'Chromium', {'name': 'Chromium Hydrolyzed Vegetable Protein', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Chromium'}, 'chromium (unspecified)'),
    ('chromium', 'Chromium', {'name': 'Chromium Complex', 'category': _M, 'ingredientGroup': 'Chromium'}, 'chromium (unspecified)'),
    ('chromium', 'GTF Chromium', {'name': 'Chromium Glutamate, Fermented', 'category': 'mineral', 'ingredientGroup': 'Chromium'}, 'chromium GTF'),
    ('chromium', 'Chromium', {'name': 'Chromium Hydrolyzed Rice Protein Chelate', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Chromium'}, 'chromium brown rice chelate'),
    ('chromium', 'GTF Chromium', {'name': 'Chromium Nicotinate, Fermented', 'category': 'mineral', 'ingredientGroup': 'Chromium'}, 'chromium polynicotinate'),
    ('chromium', 'Chromium', {'name': 'Chromium Dinicotinate Glycinate', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Chromium dinicotinate'}, 'chromium nicotinate glycinate'),
    ('chromium', 'Chromium', {'name': 'Chromium Nicotinoglycinate', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Chromium'}, 'chromium nicotinate glycinate'),
    ('chromium', 'Chromium', {'name': 'Niacin Amino Acid Chelate', 'category': 'mineral', 'prefix': 'as', 'ingredientGroup': 'Niacin (Vitamin B3)'}, 'chromium nicotinate glycinate'),
    ('phosphorus', 'Phosphorus', {'name': 'Calcium Potassium Phosphate Citrate', 'category': _M, 'ingredientGroup': 'Calcium Potassium Phosphate Citrate'}, 'phosphate salts'),
    ('phosphorus', 'Phosphorus', {'name': 'Microcrystalline Hydroxyapatite Calcium', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'phosphate salts'),
    ('phosphorus', 'Phosphorus', {'name': 'MCH-Cal', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'phosphate salts'),
    ('phosphorus', 'Phosphorus', {'name': 'Dibasic Calcium Phosphate Dihydrate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'dicalcium phosphate (as phosphorus source)'),
    ('phosphorus', 'Phosphorus', {'name': 'Calcium Magnesium Phytate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'phosphorus (unspecified)'),
    ('potassium', 'Potassium', {'name': 'Glucosamine Sulfate Potassium Chloride', 'category': _M, 'ingredientGroup': 'Glucosamine Sulfate'}, 'potassium chloride'),
    ('potassium', 'Potassium', {'name': 'Glucosamine Sulfate Potassium Chloride Salt', 'category': _M, 'ingredientGroup': 'Glucosamine Sulfate'}, 'potassium chloride'),
    ('potassium', 'Potassium', {'name': 'GreenGrown Glucosamine Sulfate 2KCl', 'category': _M, 'ingredientGroup': 'Glucosamine Sulfate'}, 'potassium chloride'),
    ('potassium', 'Potassium', {'name': 'Glucosamine Hydrochloride Potassium Sulfate', 'category': _M, 'ingredientGroup': 'Glucosamine Sulfate'}, 'potassium (unspecified)'),
    ('potassium', 'Potassium', {'name': 'Calcium Potassium Phosphate Citrate', 'category': _M, 'ingredientGroup': 'Calcium Potassium Phosphate Citrate'}, 'potassium (unspecified)'),
    ('potassium', 'Potassium', {'name': 'Potassium Hydroxycitrate', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Potassium hydroxycitrate'}, 'potassium (unspecified)'),
    # Batch 10: vitamin, amino-acid and botanical spellings, phytosomes and blend members. When
    # the token reads the unspecified form, the row label decides (psyllium husk powder,
    # tart cherry extract, the BCAA label's existing 2:1:1 alias).
    ('caffeine', 'Caffeine', {'name': 'extended-release Caffeine', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Caffeine'}, 'caffeine anhydrous'),
    ('caffeine', 'Caffeine', {'name': 'extended release Caffeine', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Caffeine'}, 'caffeine anhydrous'),
    ('inulin', 'Inulin', {'name': 'Fructooligosaccharides', 'category': 'fiber', 'ingredientGroup': 'Fructo-Oligosaccharides (FOS)'}, 'inulin (unspecified)'),
    ('vitamin_b2_riboflavin', 'Riboflavin', {'name': 'Vitamin B2, Activated', 'category': 'vitamin', 'ingredientGroup': 'Riboflavin'}, 'riboflavin-5-phosphate'),
    ('alpha_lipoic_acid', 'R-Lipoic Acid', {'name': 'Na-RALA Sodium R-Lipoate', 'category': _M, 'prefix': 'as microencapsulated Bio-Enhanced stabilized', 'ingredientGroup': 'Alpha-Lipoic Acid'}, 'sodium r-lipoate'),
    ('alpha_lipoic_acid', 'R-Lipoic Acid', {'name': 'Bio-Enhanced Na-RALA', 'category': _M, 'ingredientGroup': 'Alpha Lipoic Acid'}, 'sodium r-lipoate'),
    ('vitamin_d', 'Vitamin D3', {'name': 'Cholecalciferol, Fermented', 'category': 'vitamin', 'ingredientGroup': 'Vitamin D'}, 'cholecalciferol (D3)'),
    ('vitamin_k2', 'Vitamin K2', {'name': 'trans-Menaquinone-7', 'category': 'vitamin', 'ingredientGroup': 'Vitamin K'}, 'menaquinone-7 all-trans'),
    ('vitamin_k2', 'Vitamin K2', {'name': 'Menaquinone-7, Natural', 'category': 'vitamin', 'ingredientGroup': 'Vitamin K'}, 'menaquinone-7 (MK-7)'),
    ('vitamin_k', 'Vitamin K', {'name': 'K2', 'category': 'vitamin', 'prefix': 'as', 'ingredientGroup': 'Vitamin K (menaquinone)'}, 'vitamin k (unspecified)'),
    ('hyaluronic_acid', 'Hyaluronic Acid', {'name': 'Sodium Hyaluronic Acid', 'category': _M, 'prefix': 'as'}, 'hyaluronic acid (unspecified)'),
    ('hyaluronic_acid', 'Hyaluronic Acid', {'name': 'Sodium', 'category': 'mineral', 'ingredientGroup': 'Sodium'}, 'hyaluronic acid (unspecified)'),
    ('vitamin_b7_biotin', 'Biotin', {'name': 'Biotin Triturate', 'category': 'vitamin', 'prefix': 'as', 'ingredientGroup': 'Vitamin B7 (biotin)'}, 'd-biotin'),
    ('vitamin_e', 'Vitamin E', {'name': 'D-Beta Tocopherol', 'category': 'vitamin', 'ingredientGroup': 'Vitamin E (beta tocopherol)'}, 'mixed tocopherols'),
    ('vitamin_e', 'Vitamin E', {'name': 'Alpha-Tocopherol Acetate', 'category': 'vitamin', 'ingredientGroup': 'Vitamin E'}, 'vitamin e (unspecified)'),
    ('l_arginine', 'L-Arginine', {'name': 'L-Arginine Monohydrochloride', 'category': 'amino acid', 'ingredientGroup': 'Arginine'}, 'l-arginine hcl'),
    ('l_arginine', 'L-Arginine', {'name': 'L-Arginine Monohydrate', 'category': 'amino acid', 'ingredientGroup': 'Arginine'}, 'l-arginine base'),
    ('l_carnitine', 'L-Carnitine', {'name': 'L-Canitine Fumarate', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'L-Carnitine'}, 'l-carnitine fumarate'),
    ('l_ornithine', 'L-Ornithine', {'name': 'L-Ornithine Monohydrochloride', 'category': 'amino acid', 'ingredientGroup': 'Ornithine'}, 'l-ornithine standard'),
    ('l_ornithine', 'L-Ornithine', {'name': 'L-Ornithine Hydrochloride', 'category': 'amino acid', 'ingredientGroup': 'Ornithine'}, 'l-ornithine standard'),
    ('same', 'SAM-e', {'name': 'S-Adenosyl-L-Methionine Disulfate P-Toluenesulfonate', 'category': _M, 'ingredientGroup': 'SAMe'}, 'same supplement'),
    ('dmae', 'Dimethylethanolamine', {'name': 'Dimethylethanolamine Bitartrate', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Deanol'}, 'dmae bitartrate'),
    ('dmae', 'DMAE', {'name': '2-Dimethylaminoethanol Bitartrate', 'category': _M, 'ingredientGroup': 'Deanol'}, 'dmae bitartrate'),
    ('fish_oil', 'Omega-3 Fatty Acids', {'name': 'Omega-3 Fatty Acid Triglycerides', 'category': 'fatty acid', 'ingredientGroup': 'Omega-3'}, 'natural triglyceride'),
    ('coq10', 'Coenzyme Q10 complex', {'name': 'Microactive Q10-Cyclodextrin', 'category': _M, 'prefix': 'and as from sustained-release', 'ingredientGroup': 'Coenzyme Q-10'}, 'ubiquinone crystal-dispersed'),
    ('coq10', 'CoQ10', {'name': 'sustained-release MicroActive Q10-Cyclodextrin Complex', 'category': _M, 'prefix': 'and as', 'ingredientGroup': 'Coenzyme Q-10'}, 'ubiquinone crystal-dispersed'),
    ('coq10', 'Coenzyme Q-10', {'name': 'Ubiquinone-10', 'category': _M, 'ingredientGroup': 'Coenzyme Q-10'}, 'ubiquinone standard'),
    ('nattokinase', 'Nattokinase', {'name': 'Fibrinase', 'category': 'enzyme', 'ingredientGroup': 'Fibrinase'}, 'nattokinase standard'),
    ('vitamin_c', 'Vitamin C', {'name': 'Q-C', 'category': 'vitamin', 'ingredientGroup': 'Vitamin C (ascorbic acid) '}, 'ascorbic acid'),
    ('lactoferrin', 'Lactoferrin', {'name': 'Apolactoferrin', 'category': 'protein', 'ingredientGroup': 'Lactoferrin'}, 'lactoferrin (unspecified)'),
    ('d_beta_hydroxybutyrate_bhb', 'goBHB', {'name': '4-In-1 Ketone Salt Blend', 'category': 'blend', 'ingredientGroup': 'Blend'}, 'd beta hydroxybutyrate bhb (standard)'),
    ('beta_glucan', 'Beta-1,3-1,6-Glucan', {'name': 'Saccharomyces cerevisiae', 'category': _B, 'ingredientGroup': 'Saccharomyces cerevisae'}, 'beta-glucan'),
    ('beta_glucan', "Wellmune Baker's Yeast Beta Glucans", {'name': 'Yeast Beta 1,3/1,6 glucan', 'category': 'fiber', 'ingredientGroup': 'Beta-Glucans'}, 'beta-glucan'),
    ('beta_glucan', 'Beta Glucans', {'name': 'Beta 1-6 Glucans', 'category': 'fiber', 'ingredientGroup': 'Beta-Glucans'}, 'beta-glucan'),
    ('beta_glucan', 'BetaVia', {'name': '1,3 Beta Glucan', 'category': 'fiber', 'ingredientGroup': 'Beta-Glucans'}, 'beta-glucan'),
    ('beta_glucan', 'Barley Beta-Glucan', {'name': 'Glucagel', 'category': 'fiber', 'prefix': 'as', 'ingredientGroup': 'Beta-Glucans'}, 'beta-glucan'),
    ('beta_glucan', 'Mushroom Beta Glucan', {'name': 'Reishi Mycelia Extract', 'category': _B, 'ingredientGroup': 'Reishi mushroom'}, 'beta-glucan'),
    ('glucosamine', 'D-Glucosamine Sulfate', {'name': 'D-Glucosamine Sulfate 2KCl', 'category': _M, 'ingredientGroup': 'Glucosamine Sulfate'}, 'glucosamine sulfate (crystalline)'),
    ('glucosamine', 'Glucosamine Sulfate 2KCl', {'name': 'GreenGrown Glucosamine Sulfate 2KCl', 'category': _M, 'ingredientGroup': 'Glucosamine Sulfate'}, 'glucosamine sulfate (crystalline)'),
    ('7_keto_dhea', '7-Keto DHEA', {'name': '7-Oxo-Dehydroepiandrosterone-3 Beta-Acetate', 'category': _M, 'ingredientGroup': '7-KETO-DHEA'}, '7-keto dhea (unspecified)'),
    ('7_keto_dhea', '7-Keto Dehydroepiandrosterone', {'name': '7-oxo-Dehydroepiandrosterone Acetate', 'category': _M, 'ingredientGroup': '7-KETO-DHEA'}, '7-keto dhea (unspecified)'),
    ('choline', 'Choline', {'name': 'Alpha-Glycerylphosphorylcholine', 'category': _M, 'ingredientGroup': 'Alpha-GPC'}, 'alpha-GPC'),
    ('choline', 'Citicoline', {'name': 'Citicoline Monosodium Salt', 'category': _M, 'ingredientGroup': 'Citicoline'}, 'CDP-choline (citicoline)'),
    ('vitamin_b6_pyridoxine', 'Vitamin B6', {'name': 'Pyridoxide HCl', 'category': 'vitamin', 'prefix': 'as', 'ingredientGroup': 'Vitamin B6 (Pyridoxine HCl)'}, 'pyridoxine hydrochloride'),
    ('vitamin_b6_pyridoxine', 'Vitamin B6', {'name': 'Pyridoxyl 5-Phosphate', 'category': 'vitamin', 'prefix': '&', 'ingredientGroup': 'Vitamin B6 (pyridoxal 5-phosphate)'}, 'pyridoxal-5-phosphate (P5P)'),
    ('vitamin_b12_cobalamin', 'Vitamin B12', {'name': 'Hydroxocobalamin Hydrochloride', 'category': 'vitamin', 'prefix': 'and', 'ingredientGroup': 'Vitamin B12'}, 'hydroxocobalamin'),
    ('hmb', 'Calcium HMB', {'name': 'Calcium Beta-Hydroxy Beta-Methylbutyric Acid', 'category': _M, 'ingredientGroup': 'Calcium hydroxymethylbutyrate'}, 'hmb calcium salt (hmb-ca)'),
    ('hmb', 'Calcium HMB', {'name': 'Calcium Beta-hydroxyBeta-Methylbutyrate Monohydrate', 'category': _M, 'prefix': 'as', 'ingredientGroup': 'Calcium hydroxymethylbutyrate'}, 'hmb calcium salt (hmb-ca)'),
    ('shilajit', 'PrimaVie', {'name': 'Shilajit Fulvic Acid Complex', 'category': 'other', 'ingredientGroup': 'Shilajit'}, 'primavie shilajit'),
    ('shilajit', 'Shilajit', {'name': 'Peat'}, 'fulvic acid'),
    ('shilajit', 'Shilajit', {'name': 'Apple Fruit Extract'}, 'fulvic acid'),
    ('celadrin', 'Celadrin', {'name': 'Esterified Fatty Acid Carbons', 'category': 'blend', 'ingredientGroup': 'Blend'}, 'celadrin (unspecified)'),
    ('collagen', 'hydrolyzed Type I and Type III Collagen', {'name': 'Porcine Collagen Peptides', 'category': 'protein', 'prefix': 'as', 'ingredientGroup': 'Collagen Peptides'}, 'hydrolyzed collagen peptides'),
    ('collagen', 'Collagen Peptide Complex, Hydrolyzed', {'name': 'Chicken Collagen, Hydrolyzed', 'category': 'protein', 'ingredientGroup': 'Collagen'}, 'hydrolyzed collagen peptides'),
    ('psyllium', 'Psyllium Husk, Powder', {'name': 'Plantago ovata, Powder', 'category': _B, 'ingredientGroup': 'Blond Psyllium'}, 'psyllium husk powder'),
    ('aloe_vera', 'Aloe vera, Dehydrate, Powder', {'name': 'Aloe barbadensis, Dehydrate, Powder', 'category': _B, 'ingredientGroup': 'Aloe'}, 'aloe vera (unspecified)'),
    ('aloe_vera', 'Aloe vera Leaf Extract', {'name': 'Aloe barbadensis leaf extract', 'category': _B, 'ingredientGroup': 'Aloe'}, 'aloe vera (unspecified)'),
    ('rose_hips', 'Rosehip Fruit Extract', {'name': 'Rosae canina Fruit Extract', 'category': _B, 'ingredientGroup': 'Dog Rose'}, 'rose hips extract'),
    ('rose_hips', 'Rose Hip Fruit Extract', {'name': 'Rosa canina Fruit Extract', 'category': _B, 'ingredientGroup': 'Rose Hip'}, 'rose hips extract'),
    ('corn_silk', 'Corn Silk, Powder', {'name': 'Zea mays, Powder', 'category': _B, 'ingredientGroup': 'Corn'}, 'corn silk extract'),
    ('perilla_oil', 'Perilla Seed Extract', {'name': 'Perilla frutescens Seed Extract', 'category': _B, 'ingredientGroup': 'perilla'}, 'perilla seed oil'),
    ('horse_chestnut_seed', 'Horse Chestnut Seed Extract', {'name': 'Aesculus hippocastanum Seed Extract', 'category': _B, 'ingredientGroup': 'Horse Chestnut'}, 'horse chestnut seed (unspecified)'),
    ('chamomile', 'Chamomile Flower Extract', {'name': 'Matricaria recutita Flower Extract', 'category': _B, 'ingredientGroup': 'German Chamomile '}, 'chamomile extract'),
    ('chamomile', 'Chamomile Flowering Top Extract', {'name': 'Matricaria recutita Flowering Top Extract', 'category': _B, 'ingredientGroup': 'German Chamomile '}, 'chamomile extract'),
    ('cayenne_pepper', 'Capsimax', {'name': 'Capsicum annuum Fruit Extract', 'category': _B, 'ingredientGroup': 'Capsicum'}, 'cayenne pepper (unspecified)'),
    ('cayenne_pepper', 'Capsicum Seed Extract', {'name': 'Capsicum annuum Seed Extract', 'category': _B, 'ingredientGroup': 'Capsicum'}, 'cayenne pepper (unspecified)'),
    ('cayenne_pepper', 'Capsimax', {'name': 'Capsicum extract', 'category': _B, 'ingredientGroup': 'Capsicum'}, 'cayenne pepper (unspecified)'),
    ('cayenne_pepper', 'Capsimax', {'name': 'Capsicum Fruit Extract', 'category': _B, 'ingredientGroup': 'Capsicum'}, 'cayenne pepper (unspecified)'),
    ('ginseng', 'American Ginseng Rhizome Extract', {'name': 'Panax quinquefolium L. Rhizome Extract', 'category': _B, 'ingredientGroup': 'American Ginseng'}, 'american ginseng (panax quinquefolius)'),
    ('ginseng', 'Asian Ginseng Aerial Part & Root Extract', {'name': 'Panax ginseng Aerial Part Extract', 'category': _B, 'ingredientGroup': 'Panax Ginseng'}, 'ginseng (unspecified)'),
    ('ginseng', 'Asian Ginseng Aerial Parts, Root Extract', {'name': 'Panax ginseng Aerial Parts Extract', 'category': _B, 'ingredientGroup': 'Oriental Ginseng'}, 'ginseng (unspecified)'),
    ('ginseng', 'Ginseng, Powder', {'name': 'Panax ginseng, Powder', 'category': _B, 'ingredientGroup': 'Oriental Ginseng'}, 'ginseng (unspecified)'),
    ('cinnamon', 'Cinnamon Bark Extract', {'name': 'Cinnamomum aromaticum Bark Extract', 'category': _B, 'ingredientGroup': 'Cinnamomum (unspecified)'}, 'cinnamon extract'),
    ('cinnamon', 'Cinnamon', {'name': 'Cinnamomum spp.', 'category': _B, 'ingredientGroup': 'Cinnamomum (unspecified)'}, 'cinnamon extract'),
    ('cinnamon', 'Cinnamon', {'name': 'Cinnamomum burmannii', 'category': _B, 'ingredientGroup': 'Cinnamomum burmanii'}, 'cinnamon extract'),
    ('cinnamon', 'Cinnamon Bark Extract', {'name': 'Cinnamomum Bark Extract', 'category': _B, 'ingredientGroup': 'Ceylon cinnamon'}, 'cinnamon extract'),
    ('tart_cherry', 'Sour Cherry fruit concentrate', {'name': 'Montmorency Tart Cherry variety', 'category': _B, 'ingredientGroup': 'Sour Cherry'}, 'tart cherry (unspecified)'),
    ('tart_cherry', 'Tart Cherry Fruit Extract', {'name': 'Cerasus vulgaris Mill Fruit Extract', 'category': _B, 'ingredientGroup': 'Sour Cherry'}, 'tart cherry extract'),
    ('quercetin', 'Quercetin Phytosome', {'name': 'Phospholipid Complex', 'category': 'blend', 'ingredientGroup': 'Blend'}, 'quercetin phytosome'),
    ('quercetin', 'Quercetin Phytosome Complex', {'name': 'Phospholipid', 'category': 'fat', 'ingredientGroup': 'Phospholipid (unspecified)'}, 'quercetin phytosome'),
    ('quercetin', 'Quercetin Phytosome Complex', {'name': 'Phospholipids', 'category': 'blend', 'ingredientGroup': 'Blend'}, 'quercetin phytosome'),
    ('curcumin', 'Curcumin Phytosome', {'name': 'Phospholipid Complex', 'category': 'blend', 'ingredientGroup': 'Blend'}, 'meriva curcumin'),
    ('curcumin', 'Curcumin Phytosome', {'name': 'Phosphatidylcholine', 'category': 'fat', 'ingredientGroup': 'phosphatidylcholine'}, 'meriva curcumin'),
    ('curcumin', 'Curcumin Phytosome', {'name': 'Phosphatidylcholine Complex', 'category': 'fat', 'ingredientGroup': 'phosphatidylcholine'}, 'meriva curcumin'),
    ('grape_seed_extract', 'Grape seed phytosome', {'name': 'Phosphatidylcholine Complex', 'category': 'fat', 'ingredientGroup': 'phosphatidylcholine'}, 'grape seed phytosome'),
    ('green_tea_extract', 'TeaSlender Green Tea Phytosome', {'name': 'Green Tea Phytosome decaffeinated extract', 'category': _B, 'ingredientGroup': 'Green Tea'}, 'green tea phytosome'),
    ('citrus_bioflavonoids', 'Rutin', {'name': 'Quercetin Rutinoside', 'category': _M, 'ingredientGroup': 'Quercetin'}, 'rutin'),
    ('pterostilbene', 'trans-Pterostilbene', {'name': 'Dimethylresveratrol', 'category': _M, 'ingredientGroup': 'Dimethylresveratrol'}, 'trans-pterostilbene'),
    ('branched_chain_amino_acids', 'Branched-Chain Amino Acids', {'name': 'L-Leucine', 'category': 'amino acid', 'ingredientGroup': 'Leucine'}, 'bcaa 2:1:1'),
    ('branched_chain_amino_acids', 'Branched-Chain Amino Acids', {'name': 'L-Isoleucine', 'category': 'amino acid', 'ingredientGroup': 'Isoleucine'}, 'bcaa 2:1:1'),
    ('branched_chain_amino_acids', 'Branched-Chain Amino Acids', {'name': 'L-Valine', 'category': 'amino acid', 'ingredientGroup': 'Valine'}, 'bcaa 2:1:1'),
    ('branched_chain_amino_acids', 'BCAA Complex', {'name': 'L-Leucine, Micronized', 'category': 'amino acid', 'ingredientGroup': 'Leucine'}, 'branched chain amino acids (unspecified)'),
    ('branched_chain_amino_acids', 'BCAA Complex', {'name': 'L-Isoleucine, Micronized', 'category': 'amino acid', 'ingredientGroup': 'Isoleucine'}, 'branched chain amino acids (unspecified)'),
    ('branched_chain_amino_acids', 'BCAA Complex', {'name': 'L-Valine, Micronized', 'category': 'amino acid', 'ingredientGroup': 'Valine'}, 'branched chain amino acids (unspecified)'),
    ('digestive_enzymes', 'Digestive Enzymes', {'name': 'Protease'}, 'specific enzymes'),
    ('digestive_enzymes', 'Digestive Enzymes', {'name': 'Peptidase'}, 'specific enzymes'),
    ('digestive_enzymes', 'Enzyme Blend', {'name': 'Amylase', 'category': 'enzyme', 'ingredientGroup': 'Amylase'}, 'specific enzymes'),
    ('digestive_enzymes', 'Enzyme Blend', {'name': 'Acid Protease', 'category': 'enzyme', 'ingredientGroup': 'Proteolytic Enzymes (Proteases)'}, 'specific enzymes'),
    ('digestive_enzymes', 'Enzyme Blend', {'name': 'Alkaline Proteases', 'category': 'enzyme', 'prefix': 'and', 'ingredientGroup': 'Proteolytic Enzymes (Proteases)'}, 'specific enzymes'),
    ('digestive_enzymes', 'Enzyme Blend', {'name': 'Cellulase', 'category': 'enzyme', 'ingredientGroup': 'Cellulase'}, 'specific enzymes'),
    ('digestive_enzymes', 'Enzyme Blend', {'name': 'Lipase', 'category': 'enzyme', 'ingredientGroup': 'Lipase'}, 'specific enzymes'),
    ('pancreatin', 'Pancreatin', {'name': 'Amylase', 'category': 'enzyme', 'ingredientGroup': 'Amylase'}, 'pancreatin (porcine/bovine)'),
    ('pancreatin', 'Pancreatin', {'name': 'Lipase', 'category': 'enzyme', 'ingredientGroup': 'Lipase'}, 'pancreatin (porcine/bovine)'),
    ('pancreatin', 'Pancreatin', {'name': 'Protease', 'category': 'enzyme', 'ingredientGroup': 'Proteolytic Enzymes (Proteases)'}, 'pancreatin (porcine/bovine)'),
    # Batch 11: seaweed iodine is the map's kelp iodine form (batch 4's bare Kelp included), the
    # parent plant's own binomial or variety, and blend spellings.
    ('iodine', 'Iodine', {'name': 'Kelp', 'category': 'other', 'prefix': 'as', 'ingredientGroup': 'Kelp'}, 'kelp iodine'),
    ('iodine', 'Iodine', {'name': 'organic Sea Kelp', 'category': 'other', 'ingredientGroup': 'Kelp'}, 'kelp iodine'),
    ('iodine', 'Iodine', {'name': 'Bladderwrack', 'category': 'other', 'prefix': 'and', 'ingredientGroup': 'Bladderwrack'}, 'kelp iodine'),
    ('iodine', 'Iodine', {'name': 'Kelp (whole thallus) powder', 'category': 'other', 'prefix': 'as', 'ingredientGroup': 'Kelp'}, 'kelp iodine'),
    ('iodine', 'Iodine', {'name': 'Kelp powder', 'category': 'other', 'prefix': 'and from', 'ingredientGroup': 'Kelp'}, 'kelp iodine'),
    ('iodine', 'Iodine', {'name': 'Ascophyllum nodosum', 'category': 'other', 'prefix': 'typical value naturally occurring from', 'ingredientGroup': 'Ascophyllum nodosum'}, 'kelp iodine'),
    ('iodine', 'Iodine', {'name': 'Fucus vesiculosus', 'category': 'other', 'prefix': 'and', 'ingredientGroup': 'Bladderwrack'}, 'kelp iodine'),
    ('inositol_hexaphosphate', 'Inositol Hexaphosphate', {'name': 'Calcium Magnesium Phytate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'IP6 (unspecified)'),
    ('phytosterols', 'Phytosterols', {'name': 'Beta-Sisterol', 'category': 'fat', 'ingredientGroup': 'Beta Sitosterol'}, 'beta-sitosterol'),
    ('phytosterols', 'Phytosterols', {'name': 'Campestrol', 'category': 'fat', 'ingredientGroup': 'Campesterol'}, 'campesterol'),
    ('fiber', 'Glucomannan', {'name': 'Konjac Root Extract', 'category': _B, 'ingredientGroup': 'Konjac'}, 'konjac glucomannan'),
    ('fiber', 'Glucomannan', {'name': 'Konjac Extract', 'category': _B, 'ingredientGroup': 'Konjac'}, 'konjac glucomannan'),
    ('fiber', 'Glucomannan', {'name': 'Umbrella Arum', 'category': _B, 'ingredientGroup': 'Konjac'}, 'konjac glucomannan'),
    ('fiber', 'Konjac Root Extract', {'name': 'Amorphophallus konjac Root Extract', 'category': _B, 'ingredientGroup': 'Konjac'}, 'konjac glucomannan'),
    ('prebiotics', 'Pectin', {'name': 'Apple', 'category': _B, 'ingredientGroup': 'Apple'}, 'pectin'),
    ('algae_oil', 'PureAlgaeOmega3', {'name': 'Triglyceride Algal Oil', 'category': 'fatty acid', 'ingredientGroup': 'Triglycerides'}, 'algae oil (dha)'),
    ('casein_hydrolysate', 'Lactium Casein, Hydrolysate', {'name': 'Decapeptide', 'category': 'protein', 'ingredientGroup': 'Casein Peptides'}, 'casein hydrolysate (unspecified)'),
    ('luteolin', 'Luteolin Phytosome', {'name': 'Phospholipid Complex', 'category': 'blend', 'ingredientGroup': 'Blend'}, 'luteolin (unspecified)'),
    ('vitamin_c', 'Vitamin C', {'name': 'Calcium L-Ascorbate', 'category': 'mineral', 'ingredientGroup': 'Calcium'}, 'calcium ascorbate'),
    ('protease', 'Protease, Bacterial', {'name': 'Alkaline Protease, Bacterial', 'category': 'enzyme', 'ingredientGroup': 'Proteolytic Enzymes (Proteases)'}, 'protease (fungal/bacterial)'),
    ('elderberry', 'ElderCraft', {'name': 'European Black Elderberry Extract', 'category': _B, 'ingredientGroup': 'European Elder'}, 'elderberry extract (sambucol)'),
    ('goji_berry', 'Goji Berry Fruit Juice, Powder', {'name': 'Lycium barbarum Fruit Juice, Powder', 'category': _B, 'ingredientGroup': 'Goji'}, 'goji berry (unspecified)'),
    ('blood_orange_extract', 'Sicilian Blood Orange Fruit, Peel Extract', {'name': 'Citrus sinensis var. Moro Fruit Extract', 'category': _B, 'ingredientGroup': 'Sweet Orange'}, 'blood orange extract (unspecified)'),
    ('blood_orange_extract', 'Sicilian Blood Orange Fruit, Peel Extract', {'name': 'Citrus sinensis var. Moro Peel Extract', 'category': _B, 'ingredientGroup': 'Sweet Orange'}, 'blood orange extract (unspecified)'),
    ('blood_orange_extract', 'Morosil', {'name': 'Blood Orange Fruit Extract', 'category': _B, 'ingredientGroup': 'Sweet Orange'}, 'blood orange extract (unspecified)'),
    ('oat_straw', 'Oats Straw', {'name': 'Avena sativa', 'category': _B, 'ingredientGroup': 'Oats'}, 'oat straw extract (unspecified)'),
    ('argan_oil', 'Argan Oil', {'name': 'Argania spinosa', 'category': _B, 'ingredientGroup': 'Argan tree'}, 'argan oil'),
    ('coffee_fruit', 'CoffeeBerry Coffee', {'name': 'Coffea arabica Whole Fruit Extract', 'category': _B, 'ingredientGroup': 'Coffee'}, 'coffee fruit extract (unspecified)'),
    ('common_bean_extract', 'White Kidney Bean seed extract', {'name': 'Phaseolus vulgaris', 'category': _B, 'prefix': 'as', 'ingredientGroup': 'Bean'}, 'white kidney bean extract'),
    ('common_bean_extract', 'White Kidney Bean Seed Extract', {'name': 'Phaseolus vulgaris Seed Extract', 'category': _B, 'ingredientGroup': 'Bean'}, 'white kidney bean extract'),
    ('magnolia_bark', 'Magnolia Bark Extract, Powder', {'name': 'Magnolia officinalis Bark Extract, Powder', 'category': _B, 'ingredientGroup': 'Magnolia '}, 'magnolia bark extract'),
    ('evening_primrose_oil', 'Evening Primrose Oil', {'name': 'Oenothera biennis', 'category': _B, 'ingredientGroup': 'Evening Primrose'}, 'evening primrose oil (unspecified)'),
    ('flaxseed', 'Flaxseed Oil', {'name': 'Linum usitatissimum Oil', 'category': _B, 'ingredientGroup': 'Flax'}, 'flaxseed oil'),
    ('black_seed_oil', 'ThymoQuin', {'name': 'Black Cumin Seed Oil', 'category': 'fat', 'ingredientGroup': 'Black Seed Oil'}, 'black seed oil'),
    ('epa', 'Eicosapentaenoic Acid', {'name': 'Omega-3', 'category': 'fatty acid', 'ingredientGroup': 'Omega-3'}, 'epa (unspecified)'),
    ('dha', 'Docosahexaenoic Acid', {'name': 'Omega-3', 'category': 'fatty acid', 'ingredientGroup': 'Omega-3'}, 'dha (unspecified)'),
    ('chlorella', 'Chlorella powder', {'name': 'Green Micro-Algae', 'category': 'other', 'prefix': 'from dried and milled', 'ingredientGroup': 'green algae (unspecified)'}, 'chlorella powder'),
    ('dimethyl_glycine', 'N,N-Dimethylglycine HCl', {'name': 'hydrochloride'}, 'dimethyl glycine (unspecified)'),
])
def test_a_held_label_spelling_reaches_the_form_it_names(enricher, parent, label, form, expected):
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'],
                                        cleaned_forms=[form], cleaner_canonical_id=parent)
    assert (match['canonical_id'], match['form_id']) == (parent, expected)
    assert not match.get('unmapped_forms')


@pytest.mark.parametrize('label, std_name, form, parent', [
    # Real held rows whose cleaner canonical came from standardized_botanicals or
    # botanical_ingredients, so the matcher got no IQM parent from the cleaner.
    ('Maca Root Extract', 'Maca', {'name': 'Lepidium meyenii Root Extract', 'category': _B, 'ingredientGroup': 'Maca'}, 'maca'),
    ('Sea Buckthorn, Powder', 'Sea Buckthorn', {'name': 'Hippophae rhamnoides, Powder', 'category': _B, 'ingredientGroup': 'Sea Buckthorn'}, 'sea_buckthorn'),
    ('Gotu Kola Whole Herb Extract', 'Gotu Kola', {'name': 'Centella asiatica Whole Herb Extract', 'category': _B, 'ingredientGroup': 'Gotu Kola'}, 'gotu_kola'),
])
def test_form_tokens_are_judged_under_the_parent_the_row_is_scored_as(enricher, label, std_name, form, parent):
    """The row is scored under the IQM parent its name resolves to; its form
    tokens are judged under that parent too, even when the cleaner's canonical
    came from a botanical database (the plant's binomial restates it)."""
    match = enricher._match_quality_map(label, std_name, enricher.databases['ingredient_quality_map'],
                                        cleaned_forms=[form])
    assert match['canonical_id'] == parent
    assert match.get('match_status') != 'FORM_DISCLOSED_UNMAPPED'
    assert not match.get('unmapped_forms')


@pytest.mark.parametrize('label, std_name, form, cleaner_canonical_id', [
    # D21: a different species under the row's parent waits for Sean's call.
    ('Acai Berry Fruit Extract', 'Acai Berry', {'name': 'Euterpe badiocarpa Fruit Extract', 'category': _B, 'ingredientGroup': 'Acai'}, None),
    ('Acai Berry Extract', 'Acai Berry', {'name': 'Euterpe badiocarpa Berry Extract', 'category': _B, 'ingredientGroup': 'Acai'}, 'acai_berry'),
    ('Sarsaparilla Root Extract', 'Sarsaparilla', {'name': 'Smilax china Root Extract', 'category': _B, 'ingredientGroup': 'Chinese Smilax'}, 'sarsaparilla'),
    ('Pine Bark Extract', 'Pine Bark Extract', {'name': 'Pinus massoniana Bark Extract', 'category': _B, 'ingredientGroup': 'Masson Pine'}, 'pine_bark_extract'),
])
def test_a_different_species_under_the_row_parent_stays_held_for_review(enricher, label, std_name, form,
                                                                       cleaner_canonical_id):
    match = enricher._match_quality_map(label, std_name, enricher.databases['ingredient_quality_map'],
                                        cleaned_forms=[form], cleaner_canonical_id=cleaner_canonical_id)
    assert match.get('unmapped_forms') == [form['name']]


@pytest.mark.parametrize('label, form', [
    ('Galactomannan', {'name': 'Fenugreek', 'category': _B, 'ingredientGroup': 'Fenugreek'}),
    ('Galactomannans', {'name': 'Fenugreek', 'category': _B, 'prefix': 'from', 'ingredientGroup': 'Fenugreek'}),
])
def test_fenugreek_galactomannan_is_not_konjac_glucomannan(enricher, label, form):
    """Galactomannan (fenugreek, guar) and glucomannan (konjac) are different
    polysaccharides; Life Extension's fenugreek galactomannan rows (232925,
    325831) read the fiber parent's unspecified form, not the konjac form."""
    match = enricher._match_quality_map(label, 'Galactomannan', enricher.databases['ingredient_quality_map'],
                                        cleaned_forms=[form], cleaner_canonical_id='fiber')
    assert (match['canonical_id'], match['form_id']) == ('fiber', 'fiber (unspecified)')


def test_5_mthf_beside_its_glucosamine_salt_reads_quatrefolic(enricher):
    """60812 "Folate (as (6S)-5-Methyltetrahydrofolic Acid, Glucosamine Salt)" is
    one compound, Quatrefolic: the combined label text reads it. Aliasing either
    token alone makes the row two forms (5-MTHF + Quatrefolic), so the held
    folate salt labels wait for the matcher to read a salt beside its compound."""
    match = enricher._match_quality_map(
        'Folate', 'Folate', enricher.databases['ingredient_quality_map'],
        cleaned_forms=[{'name': '(6S)-5-Methyltetrahydrofolic Acid', 'prefix': 'as'},
                       {'name': 'Glucosamine Salt'}],
        cleaner_canonical_id='vitamin_b9_folate')
    assert match['form_id'] == 'quatrefolic'
    assert [m['form_key'] for m in match.get('matched_forms') or []] in ([], ['quatrefolic'])


def test_bitter_orange_under_citrus_bioflavonoids_stays_held_for_review(enricher):
    """Bitter orange carries its own safety owner (synephrine); it is not
    folded into the generic citrus-source list without a review."""
    match = enricher._match_quality_map(
        'Citrus Bioflavonoids', 'Citrus Bioflavonoids', enricher.databases['ingredient_quality_map'],
        cleaned_forms=[{'name': 'Bitter Orange', 'category': _B, 'ingredientGroup': 'Bitter orange'}],
        cleaner_canonical_id='citrus_bioflavonoids')
    assert match.get('unmapped_forms') == ['Bitter Orange']


def test_generic_tocopherol_is_curated_without_claiming_a_specific_isomer(enricher):
    match = enricher._match_quality_map(
        'Vitamin E',
        'Vitamin E',
        enricher.databases['ingredient_quality_map'],
        cleaned_forms=[
            {'name': 'D-Alpha-Tocopherol Succinate'},
            {'name': 'Tocopherol'},
        ],
        cleaner_canonical_id='vitamin_e',
    )
    assert match['canonical_id'] == 'vitamin_e'
    assert match['form_id'] == 'd-alpha-tocopheryl succinate'
    assert match.get('unmapped_forms') == []
    assert [m['form_key'] for m in match['matched_forms']] == [
        'd-alpha-tocopheryl succinate'
    ]
    assert match['unmatched_percent_total'] == 0.5
    assert match['final_form_bio_score'] == 7.5


def test_a_disclosed_form_the_iqm_lacks_is_unmapped_and_held(enricher):
    # 59086 "L-Glutamine (as L-Glutamine Alpha-Ketoglutarate)": the identity is
    # L-glutamine, the salt is not in the IQM. It once shipped as
    # l-glutamine powder, bio 11, mapped, form_unmapped false.
    from score_supplements_v4 import score_product_v4
    enriched = _enrich(enricher, 'form_association_59086_raw.json')
    row = next(r for r in enriched['ingredient_quality_data']['ingredients'] if r['name'] == 'L-Glutamine')
    assert (row['canonical_id'], row['mapped']) == ('l_glutamine', True)
    assert (row['form_id'], row['matched_form'], row['bio_score']) == (None, None, None)
    assert row['form_match_status'] == 'unmapped'
    assert row['unmapped_forms'] == ['L-Glutamine Alpha-Ketoglutarate']
    assert row['identity_decision_reason'] == 'disclosed_form_unmapped'
    readiness = score_product_v4(enriched)['v4_breakdown']['assessment_readiness']
    assert readiness['is_live_ready'] is False
    assert readiness['identity']['blocking_contract_findings'] == ['disclosed_form_unmapped']


@pytest.mark.parametrize('token', ['L-Glutamine HCl', 'L-Glutamine Hydrochloride'])
def test_glutamine_hydrochloride_is_not_free_glutamine(enricher, token):
    # PubChem: the hydrochloride is its own salt (CID 57364844, C5H11ClN2O3);
    # free L-glutamine is CID 5961. No GSRS UNII and no bio_score evidence,
    # so it is a disclosed unmapped form until curated.
    match = enricher._match_quality_map('L-Glutamine', 'L-Glutamine', enricher.databases['ingredient_quality_map'],
                                        cleaned_forms=[{'name': token}], cleaner_canonical_id='l_glutamine')
    assert (match['canonical_id'], match['form_id'], match['bio_score']) == ('l_glutamine', None, None)
    assert match['match_status'] == 'FORM_DISCLOSED_UNMAPPED'
    assert match['unmapped_forms'] == [token]


@pytest.mark.parametrize('label', ['L-Glutamine', 'L-Glutamine Powder', 'Glutamine'])
def test_plain_glutamine_is_the_free_form(enricher, label):
    # Plain L-glutamine and its powder are one identity (GSRS 0RH81L854J).
    match = enricher._match_quality_map(label, label, enricher.databases['ingredient_quality_map'])
    assert (match['canonical_id'], match['form_id'], match['bio_score']) == ('l_glutamine', 'l-glutamine powder', 11)


@pytest.mark.parametrize('label, parent, form', [
    ('D-Tyrosine', 'l_tyrosine', 'd-tyrosine'),
    ('D-Carnitine', 'l_carnitine', 'd-carnitine'),
    ('Hydroxyproline', 'l_proline', 'hydroxyproline'),
])
def test_a_form_that_is_not_the_parents_identity_never_inherits_its_scoring(enricher, label, parent, form):
    from scoring_reference_resolver import IDENTITY_MISMATCH_RELATIONSHIPS, parent_relationship
    assert parent_relationship(IQM[parent]['forms'][form]) in IDENTITY_MISMATCH_RELATIONSHIPS
    row = {'canonical_id': parent, 'form_id': form, 'matched_forms': []}
    assert enricher._identity_mismatch_forms(row) == [form]


def test_a_same_nutrient_degraded_form_is_not_an_identity_mismatch(enricher):
    # Iron oxide is iron, poorly delivered: its own low bio_score, not a hold.
    assert enricher._identity_mismatch_forms({'canonical_id': 'iron', 'form_id': 'iron oxide'}) == []


def test_a_packaging_word_never_picks_a_form_the_label_does_not_state(enricher):
    # "Ginseng, Powder" once took 'siberian ginseng (eleuthero)' because an
    # eleuthero alias contains "powder".
    quality_map = enricher.databases['ingredient_quality_map']
    match = enricher._match_quality_map('Ginseng, Powder', 'Ginseng, Powder', quality_map,
                                        cleaner_canonical_id='ginseng')
    assert (match['canonical_id'], match['form_id']) == ('ginseng', 'ginseng (unspecified)')


def test_the_contradictory_wild_cherry_label_is_held(enricher):
    # 311881 "Wild Cherry Fruit Extract" (black cherry, Prunus serotina) as
    # "Cerasus avium Fruit Extract" (sweet cherry): out of scoring until the
    # identity is resolved.
    from score_supplements_v4 import score_product_v4
    enriched = _enrich(enricher, 'form_association_311881_raw.json')
    readiness = score_product_v4(enriched)['v4_breakdown']['assessment_readiness']
    assert readiness['is_live_ready'] is False
    assert readiness['identity']['blocking_contract_findings'] == ['disclosed_form_unmapped']
    unmapped = [r['unmapped_forms'] for r in enriched['ingredient_quality_data']['ingredients']
                if r.get('form_match_status') == 'unmapped']
    unmapped += [e['unmapped_forms'] for e in enriched['product_scoring_evidence']
                 if e.get('form_match_status') == 'unmapped']
    assert unmapped == [['Cerasus avium Fruit Extract']]


def test_a_disclosed_form_is_read_not_replaced_by_a_default(enricher):
    # 318107 "L-Tyrosine (as N-Acetyl-L-Tyrosine)", UNII DA8G610ZO5 (GSRS:
    # Acetyl L-tyrosine). NALT is 8.
    enriched = _enrich(enricher, 'form_association_318107_raw.json')
    row = next(r for r in enriched['ingredient_quality_data']['ingredients'] if r.get('name') == 'L-Tyrosine')
    assert [m['form_key'] for m in row['matched_forms']] == ['n-acetyl l-tyrosine']
    assert row['bio_score'] == 8.0 and row['form_match_status'] == 'mapped'


@pytest.mark.parametrize('token, parent, form', [('N-Acetyl-L-Tyrosine', 'l_tyrosine', 'n-acetyl l-tyrosine'),
                                                 ('N-Acetyl-L-Cysteine', 'nac', 'nac powder')])
def test_hyphenated_acetyl_forms_resolve_by_alias(enricher, token, parent, form):
    match = enricher._match_quality_map(token, token, enricher.databases['ingredient_quality_map'],
                                        _form_extraction_attempt=True, preferred_parent=parent,
                                        cleaner_canonical_id=parent)
    assert (match['form_id'], match['match_tier']) == (form, 'exact')


# ── one matcher: scoring and export consume the reading ───────────────────────

def test_the_scoring_contract_has_no_form_matcher():
    import scoring_input_contract
    assert not hasattr(scoring_input_contract, '_form_quality_from_iqm')
    assert 'iqm_reference_index' not in vars(scoring_input_contract)


@pytest.mark.parametrize('parent', sorted(DERIVED))
def test_the_export_attaches_no_form_copy_to_a_derived_unknown(parent):
    from build_final_db import _derive_form_evidence, _derive_form_note
    lowest, _ = DERIVED[parent]
    row = {'canonical_id': parent, 'matched_form': 'unspecified', 'matched_forms': [],
           'bio_score': lowest - 1.0}
    iqm_index = {k: v for k, v in IQM.items() if k != '_metadata'}
    assert _derive_form_note(row, iqm_index) == (None, None)
    assert _derive_form_evidence(row, iqm_index) is None
