"""Same-parent exact declarations outrank generated form-name variations."""
import pytest
from enhanced_normalizer import EnhancedDSLDNormalizer


@pytest.fixture(scope='module')
def normalizer():
    return EnhancedDSLDNormalizer()


@pytest.mark.parametrize('reverse', [False,True])
def test_literal_form_name_is_order_independent(normalizer,monkeypatch,reverse):
    forms=[('example nutrient',{'aliases':['named preparation']}),
           ('example nutrient (unspecified)',{'aliases':['example']})]
    if reverse:
        forms.reverse()
    monkeypatch.setattr(normalizer,'ingredient_map',{**normalizer.ingredient_map,'example':{'standard_name':'Example','forms':dict(forms)}})
    normalizer._build_enhanced_indices()
    assert normalizer.ingredient_alias_lookup['example nutrient']=='Example'
    assert normalizer.ingredient_forms_lookup['example nutrient']=='example nutrient'
    assert normalizer.ingredient_context_lookup['named preparation']['form_name']=='example nutrient'
    assert 'example nutrient' not in normalizer.ingredient_context_lookup


def test_alias_declarations_keep_last_writer_order(normalizer,monkeypatch):
    # Bare parent names declared as aliases of specific forms are not promoted.
    forms={'specific salt':{'aliases':['example']},'example (unspecified)':{'aliases':[]}}
    monkeypatch.setattr(normalizer,'ingredient_map',{**normalizer.ingredient_map,'example':{'standard_name':'Example','forms':forms}})
    normalizer._build_enhanced_indices()
    assert normalizer.ingredient_forms_lookup['example']=='example (unspecified)'


@pytest.mark.parametrize('reverse', [False,True])
def test_creatine_exact_form_survives_unspecified_variants(normalizer,monkeypatch,reverse):
    forms=[('creatine monohydrate',{'aliases':['micronized creatine monohydrate']}),
           ('creatine monohydrate ((unspecified))',{'aliases':['creatine','micronized creatine']})]
    if reverse:
        forms.reverse()
    monkeypatch.setattr(normalizer,'ingredient_map',{**normalizer.ingredient_map,'creatine_monohydrate':{'standard_name':'Creatine','forms':dict(forms)}})
    normalizer._build_enhanced_indices()
    assert normalizer.ingredient_forms_lookup['creatine monohydrate']=='creatine monohydrate'
    assert normalizer.ingredient_forms_lookup['micronized creatine']=='creatine monohydrate ((unspecified))'
    assert normalizer.ingredient_context_lookup['micronized creatine']['form_name']=='creatine monohydrate ((unspecified))'
    for key,context in normalizer.ingredient_context_lookup.items():
        if context['standard_name']=='Creatine':
            assert context['form_name']==normalizer.ingredient_forms_lookup[key]
