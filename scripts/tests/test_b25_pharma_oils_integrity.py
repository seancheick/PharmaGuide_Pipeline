"""Regression test: Batch 25 — pharmacological + plant oils + 7th category error.

Per IQM audit 2026-04-25 Step 4 Batch 25: 23 forms across 10 parents.
Six framework findings:

1. KONJAC GLUCOMANNAN = 7TH CATEGORY ERROR. González Canga 2004
   (PMID:14983741) — viscous soluble fiber luminal mechanism, NOT
   systemic absorption. 7th overall.

2. SDA OMEGA-3 INTERMEDIATE TIER — NEW. Whelan 2012 (PMID:22279143):
   SDA→EPA bioequivalence ~5:1 humans. Ahiflower SDA = 4× ALA but
   inferior to direct EPA/DHA.

3. VANADIUM FULL CLASS-EQUIVALENCE — Willsky 2013 (PMID:23982218):
   ALL vanadium forms F~1-3%. Chelate marketing unsupported.

4. LITHIUM SALT CLASS-EQUIVALENCE AT ABSORPTION LAYER — Pauzé 2007
   (PMID:18072162). Orotate vs carbonate same GI F.

5. GUARANA = PURE CAFFEINE F — Haller 2002 (PMID:12087345). Tannin
   delays Tmax only.

6. BUTTERBUR PETASIN — KEEP NULL: extensive first-pass; no human PK.

GHOST PMIDS / CITATIONS CAUGHT (5+):
  • Heyliger 1985 vanadyl — 0 PubMed hits
  • Setyawati 2011 V chelate — 0 PubMed hits
  • Lemke 2010 SDA — not found, use Whelan 22279143
  • Surette SDA — 0 PubMed hits
  • Goldfine 2000 V — conflated; correct = 11377693 (2001)
  • PMID:21055800 — dental ceramics (V abs query trap)
  • PMID:26869109 — goat milk biohydrogenation (SDA query trap)
  • PMID:22064208 — K-complex EEG (Lemke query trap)
  • PMID:10442214 — topical EPO (GLA query trap)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

IQM_PATH = Path(__file__).parent.parent / 'data' / 'ingredient_quality_map.json'


@pytest.fixture(scope='module')
def iqm():
    with IQM_PATH.open() as f:
        return json.load(f)


# (parent, form, vmin, vmax, basis)
B25_BANDS_VALUED = [
    # lithium — class-equiv
    ('lithium', 'lithium orotate',                                   0.95, 1.00, 'Pauzé 2007'),
    ('lithium', 'lithium (unspecified)',                             0.95, 1.00, 'Pauzé 2007'),
    # guarana — caffeine class
    ('guarana', 'guarana standardized extract',                      0.95, 1.00, 'Haller 2002'),
    ('guarana', 'guarana (unspecified)',                             0.95, 1.00, 'Haller 2002'),
    # ahiflower SDA intermediate
    ('ahiflower_seed_oil', 'cold-pressed ahiflower seed oil',        0.20, 0.25, 'Whelan 2012 SDA'),
    ('ahiflower_seed_oil', 'ahiflower seed oil (unspecified)',       0.20, 0.25, 'Whelan 2012'),
    # evening primrose GLA
    ('evening_primrose_oil', 'cold-pressed evening primrose oil',    0.85, 0.95, 'Belch 2000 GLA'),
    ('evening_primrose_oil', 'evening primrose oil (unspecified)',   0.85, 0.95, 'Belch 2000'),
    # vanadium — full class-equiv collapse
    ('vanadyl_sulfate', 'bis(picolinato)oxovanadium (BPOV)',         0.01, 0.03, 'Willsky 2013'),
    ('vanadyl_sulfate', 'vanadyl sulfate (unspecified)',             0.01, 0.03, 'Willsky 2013'),
    ('vanadyl_sulfate', 'vanadium aspartate',                        0.01, 0.03, 'Willsky 2013'),
    ('vanadyl_sulfate', 'vanadium citrate',                          0.01, 0.03, 'Willsky 2013'),
    # andrographis
    ('andrographis', 'ap-bio andrographis extract',                  0.10, 0.20, 'Panossian 2000'),
    ('andrographis', 'andrographis extract',                         0.10, 0.20, 'Panossian 2000'),
    ('andrographis', 'andrographis (unspecified)',                   0.10, 0.20, 'Panossian 2000'),
    # black seed
    ('black_seed_oil', 'black seed powder',                          0.05, 0.15, 'TQ class-poor'),
    ('black_seed_oil', 'black seed (unspecified)',                   0.05, 0.15, 'TQ class baseline'),
    # chlorophyll
    ('chlorophyll', 'copper chlorophyllin',                          0.05, 0.15, 'Egner 2000 CHL'),
    ('chlorophyll', 'sodium magnesium chlorophyllin',                0.03, 0.10, 'CHL class extension'),
]

B25_NULL_FORMS = [
    ('butterbur', 'PA-free butterbur extract (Petadolex)',           'no human PK'),
    ('butterbur', 'butterbur (unspecified)',                         'no human PK'),
    ('fiber', 'konjac glucomannan',                                  '7th category-error'),
    ('fiber', 'fiber (unspecified)',                                 '7th category-error'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B25_BANDS_VALUED)
def test_b25_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


@pytest.mark.parametrize('pid,fname,reason', B25_NULL_FORMS)
def test_b25_null_form(iqm, pid, fname, reason):
    """Each null form must have struct.value=null per its framework reason."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is None, (
        f'{pid}::{fname} value={val} must be null — reason: {reason}'
    )


def test_konjac_7th_category_error_documented(iqm):
    """Konjac glucomannan + fiber (unspecified) must document 7th category-
    error / luminal-mechanism per González Canga 2004 (PMID:14983741).
    """
    forms = [
        ('fiber', 'konjac glucomannan'),
        ('fiber', 'fiber (unspecified)'),
    ]
    for pid, fname in forms:
        form = iqm[pid]['forms'][fname]
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text_lower = text.lower()
        flag_phrases = ('category error', 'category_error', '7th category',
                        'viscous fiber', 'luminal mechanism', 'gel formation',
                        'gastric-emptying', '14983741', 'gonzález canga',
                        'gonzalez canga', 'soluble fiber')
        assert any(p in text_lower for p in flag_phrases), (
            f'{pid}::{fname} must document 7th category-error / luminal '
            f'mechanism. Text: {text[:300]}'
        )


def test_sda_intermediate_omega3_tier(iqm):
    """Ahiflower SDA forms must document SDA→EPA ~5:1 bioequivalence
    intermediate tier per Whelan 2012 (PMID:22279143).
    """
    forms = iqm['ahiflower_seed_oil']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text_lower = text.lower()
        flag_phrases = ('sda', 'stearidonic', '22279143', 'whelan 2012',
                        'bioequivalence', 'bioequiv', '5:1', 'intermediate')
        assert any(p in text_lower for p in flag_phrases), (
            f'ahiflower_seed_oil::{fname} must document SDA→EPA '
            f'intermediate tier (PMID:22279143). Text: {text[:300]}'
        )


def test_vanadium_class_equivalence_collapse(iqm):
    """All vanadium forms must cluster in 0.01-0.03 band per Willsky 2013
    (PMID:23982218) class-equivalence collapse — chelate marketing
    unsupported.
    """
    forms = iqm['vanadyl_sulfate']['forms']
    expected_v_forms = [
        'bis(picolinato)oxovanadium (BPOV)',
        'vanadyl sulfate (unspecified)',
        'vanadium aspartate',
        'vanadium citrate',
    ]
    for fname in expected_v_forms:
        form = forms.get(fname)
        assert form is not None, f'vanadyl_sulfate::{fname} missing'
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is not None and 0.01 <= v <= 0.03, (
            f'vanadyl_sulfate::{fname} value={v} outside V class band '
            f'[0.01, 0.03] per Willsky 2013 (PMID:23982218)'
        )


def test_lithium_orotate_class_equivalent_to_unspecified(iqm):
    """Lithium orotate must equal lithium (unspecified) within 0.05 per
    Pauzé 2007 (PMID:18072162) — salts class-equivalent at absorption layer.
    """
    forms = iqm['lithium']['forms']
    orotate = (forms['lithium orotate'].get('absorption_structured') or {}).get('value')
    unspec = (forms['lithium (unspecified)'].get('absorption_structured') or {}).get('value')
    assert orotate is not None and unspec is not None
    assert abs(orotate - unspec) <= 0.05, (
        f'lithium orotate ({orotate}) must equal unspecified ({unspec}) '
        f'within 0.05 — class-equivalent at absorption (PMID:18072162). '
        f'Tissue uptake differs (PMID:37356352) but GI F same.'
    )


def test_guarana_class_equivalent_to_caffeine(iqm):
    """Guarana forms must reflect caffeine class F (~99%) per Haller 2002
    (PMID:12087345).
    """
    forms = iqm['guarana']['forms']
    for fname, form in forms.items():
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is not None and v >= 0.95, (
            f'guarana::{fname} value={v} should be ≥0.95 — caffeine class '
            f'baseline (PMID:12087345)'
        )


def test_butterbur_no_human_pk_documented(iqm):
    """Butterbur null forms must document absence of human PK / first-pass."""
    forms = iqm['butterbur']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text_lower = text.lower()
        flag_phrases = ('no human pk', 'first-pass', 'first pass',
                        'no published', 'unknown', 'extensive', '29341029',
                        'disch')
        assert any(p in text_lower for p in flag_phrases), (
            f'butterbur::{fname} must qualify absence of human PK / '
            f'first-pass. Text: {text[:300]}'
        )


def test_andrographis_ap_bio_class_equivalent_to_generic(iqm):
    """AP-Bio andrographis must NOT exceed generic extract — no peer-
    reviewed comparison exists per Panossian 2000 (PMID:11081986).
    """
    forms = iqm['andrographis']['forms']
    ap_bio = (forms['ap-bio andrographis extract'].get('absorption_structured') or {}).get('value')
    generic = (forms['andrographis extract'].get('absorption_structured') or {}).get('value')
    assert ap_bio is not None and generic is not None
    assert ap_bio <= generic + 0.02, (
        f'AP-Bio andrographis ({ap_bio}) should be ≤ generic ({generic}) '
        f'+ 0.02 — no peer-reviewed differential PK exists (PMID:11081986).'
    )


def test_chlorophyllin_better_than_natural_chlorophyll(iqm):
    """Copper chlorophyllin must rank higher than natural chlorophyll —
    water-soluble vs fat-soluble per Egner 2000 (PMID:10995263).
    """
    forms = iqm['chlorophyll']['forms']
    cu_chl = (forms['copper chlorophyllin'].get('absorption_structured') or {}).get('value')
    natural = (forms['natural chlorophyll'].get('absorption_structured') or {}).get('value')
    assert cu_chl is not None and natural is not None
    assert cu_chl > natural, (
        f'copper chlorophyllin ({cu_chl}) must exceed natural chlorophyll '
        f'({natural}) — water-soluble form better absorbed (PMID:10995263)'
    )


def test_class_authority_pmids_introduced_b25(iqm):
    """Verified class-authority PMIDs must each appear in IQM notes."""
    expected_pmids = {
        'PMID:18072162': 'Pauzé 2007 lithium',
        'PMID:12087345': 'Haller 2002 guarana caffeine',
        'PMID:22279143': 'Whelan 2012 SDA',
        'PMID:10617996': 'Belch 2000 GLA',
        'PMID:23982218': 'Willsky 2013 V human',
        'PMID:11081986': 'Panossian 2000 andrographolide',
        'PMID:14983741': 'González Canga 2004 glucomannan',
        'PMID:10995263': 'Egner 2000 chlorophyllin',
        'PMID:29341029': 'Disch 2018 petasin',
    }
    full_text = ''
    for pid in ('lithium', 'guarana', 'butterbur', 'ahiflower_seed_oil',
                'evening_primrose_oil', 'vanadyl_sulfate', 'andrographis',
                'black_seed_oil', 'chlorophyll', 'fiber'):
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing: {missing}'
    )


def test_seventh_category_error_pattern(iqm):
    """Seven category-error parent groups now established: manuka (B18),
    organ extracts (B20), prebiotics (B22), slippery elm (B23), psyllium
    (B24), SOD (B24), konjac glucomannan (B25).
    """
    category_error_forms = [
        ('manuka_honey', 'umf 15+ / mgo 514+'),
        ('organ_extracts', 'grass-fed desiccated'),
        ('inulin', 'inulin (unspecified)'),
        ('larch_arabinogalactan', 'larch arabinogalactan powder'),
        ('slippery_elm', 'standardized extract (mucilage)'),
        ('psyllium', 'psyllium seed'),
        ('superoxide_dismutase', 'sod supplement'),
        ('fiber', 'konjac glucomannan'),
        ('fiber', 'fiber (unspecified)'),
    ]
    for pid, fname in category_error_forms:
        form = iqm[pid]['forms'].get(fname)
        if form is None:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is None, (
            f'{pid}::{fname} value={v} should be null per category-error.'
        )
