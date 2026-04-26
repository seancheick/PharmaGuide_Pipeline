"""Regression test: Batch 31 — PK-rich Bucket B (12 forms, 6 parents).

Six framework findings:

1. **8TH CATEGORY ERROR — UC-II ORAL TOLERANCE PATTERN (NEW)**.
   Crowley 2009 (PMID:19847319): UC-II 40 mg/d works via oral
   tolerance / Treg induction in Peyer's patches. NOT systemic
   absorption. Set undenatured collagen null with category-error tag.

2. CASCARA cascarosides → anthrones pre-absorption hydrolysis (B23
   willow extension). Demarque 2018 (PMID:30321134), Liu 2012
   (PMID:22982073). Class baseline 0.20-0.40.

3. NAG class-equivalent to glucosamine sulfate. Talent & Gracy 1996
   (PMID:9001835): in vivo NAG → glucosamine conversion.

4. MANGOSTEEN whole fruit < pericarp. Chitchumroonchokchai 2012
   (PMID:22399525): α-mangostin 2% urinary recovery.

5. TART CHERRY anthocyanin <0.1% intact (González-Barrio 2010
   PMID:20218618). Class-equivalent to vitacherry sports (0.006).

6. CORDYCEPSPRIME Crominex relapse. Lee 2019 (PMID:31673018):
   cordycepin metabolite-only absorption applies to ALL forms; no
   branded PK premium.

GHOST PMIDS / CITATION CATCHES (4):
  • Bagchi 2002 UC-II — likely conflation with Crowley 2009
  • Borges 2010 anthocyanin — Borges is 2nd author; correct first =
    González-Barrio 2010
  • Tuli 2014 cordyceps — actually 2013 (year wrong)
  • Yang 2009 cordycepin — not verified; use Lee 2019
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


B31_BANDS = [
    ('collagen', 'collagen (unspecified)',                          0.70, 0.95, 'hydrolyzed peptides'),
    ('cascara_sagrada', 'cascara sagrada bark extract',             0.20, 0.40, 'pre-abs hydrolysis'),
    ('cascara_sagrada', 'cascara sagrada bark powder',              0.15, 0.35, 'cascara class'),
    ('glucosamine', 'n-acetyl glucosamine (NAG)',                   0.30, 0.40, 'Talent 1996 NAG→glu'),
    ('glucosamine', 'glucosamine (unspecified)',                    0.20, 0.40, 'glucosamine class'),
    ('mangosteen', 'whole fruit powder',                            0.02, 0.05, 'xanthone class-poor'),
    ('mangosteen', 'mangosteen (unspecified)',                      0.02, 0.07, 'xanthone class'),
    ('tart_cherry', 'tart cherry extract',                          0.005, 0.015, 'anthocyanin class-poor'),
    ('tart_cherry', 'tart cherry (unspecified)',                    0.003, 0.012, 'anthocyanin class'),
    ('cordyceps', 'cordyceps (unspecified)',                        0.10, 0.18, 'cordyceps class'),
    ('cordyceps', 'cordycepsprime extract',                         0.10, 0.20, 'Crominex relapse'),
]

B31_NULL_FORMS = [
    ('collagen', 'undenatured collagen',                            '8th category error: oral tolerance'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B31_BANDS)
def test_b31_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each form's struct.value must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


@pytest.mark.parametrize('pid,fname,reason', B31_NULL_FORMS)
def test_b31_null_form(iqm, pid, fname, reason):
    """Each null form must have struct.value=null per its framework reason."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is None, f'{pid}::{fname} should be null — {reason}'


def test_uc2_oral_tolerance_8th_category_error_documented(iqm):
    """UC-II must document 8th category-error oral-tolerance pattern."""
    form = iqm['collagen']['forms']['undenatured collagen']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text_lower = text.lower()
    flag_phrases = ('category error', 'category_error', '8th category',
                    'oral tolerance', 'peyer', 'treg', 'gut immune', 'galt',
                    '19847319', 'crowley 2009')
    assert any(p in text_lower for p in flag_phrases), (
        f'undenatured collagen must document 8th category-error / oral '
        f'tolerance mechanism (PMID:19847319). Text: {text[:300]}'
    )


def test_cascara_pre_absorption_hydrolysis_documented(iqm):
    """Cascara forms must document cascarosides → anthrones colonic
    hydrolysis pattern.
    """
    forms = iqm['cascara_sagrada']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text_lower = text.lower()
        flag_phrases = ('cascaroside', 'anthrone', 'emodin', 'pre-absorption',
                        'pre absorption', 'colonic hydrolysis', '30321134',
                        '22982073')
        assert any(p in text_lower for p in flag_phrases), (
            f'cascara_sagrada::{fname} must document cascaroside → anthrone '
            f'pre-absorption hydrolysis. Text: {text[:300]}'
        )


def test_cordycepsprime_crominex_relapse_documented(iqm):
    """Cordycepsprime must document Crominex relapse + Lee 2019 metabolite-
    only mechanism.
    """
    form = iqm['cordyceps']['forms']['cordycepsprime extract']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text_lower = text.lower()
    flag_phrases = ('crominex', 'no branded', 'no superior', 'no premium',
                    'class-equivalent', 'class equiv', 'no proprietary',
                    '31673018', 'lee 2019', 'metabolite-only', 'metabolite only')
    assert any(p in text_lower for p in flag_phrases), (
        f'cordycepsprime must document Crominex relapse / metabolite-only '
        f'mechanism. Text: {text[:300]}'
    )


def test_nag_class_equivalent_to_glucosamine_sulfate(iqm):
    """NAG must be class-equivalent (within 0.10) to glucosamine sulfate
    crystalline per Talent 1996 in vivo NAG→glucosamine conversion.
    """
    forms = iqm['glucosamine']['forms']
    nag = (forms['n-acetyl glucosamine (NAG)'].get('absorption_structured') or {}).get('value')
    sulfate = (forms['glucosamine sulfate (crystalline)'].get('absorption_structured') or {}).get('value')
    assert nag is not None and sulfate is not None
    assert abs(nag - sulfate) <= 0.10, (
        f'NAG ({nag}) must be class-equivalent to glucosamine sulfate '
        f'({sulfate}) within 0.10 — in vivo conversion (PMID:9001835).'
    )


def test_mangosteen_whole_fruit_below_pericarp(iqm):
    """Mangosteen whole fruit must rank below pericarp extract per
    Chitchumroonchokchai 2012 — pericarp = 99% of xanthone content.
    """
    forms = iqm['mangosteen']['forms']
    whole = (forms['whole fruit powder'].get('absorption_structured') or {}).get('value')
    pericarp = (forms['pericarp extract'].get('absorption_structured') or {}).get('value')
    assert whole is not None and pericarp is not None
    assert whole < pericarp, (
        f'mangosteen whole fruit ({whole}) should rank below pericarp '
        f'({pericarp}) — pericarp = 99% xanthone content (PMID:22399525).'
    )


def test_tart_cherry_extract_class_consistent_with_vitacherry(iqm):
    """Tart cherry extract must be class-consistent (within 0.01) with
    vitacherry sports per anthocyanin class-poor framework.
    """
    forms = iqm['tart_cherry']['forms']
    extract = (forms['tart cherry extract'].get('absorption_structured') or {}).get('value')
    vitacherry = (forms['vitacherry sports extract'].get('absorption_structured') or {}).get('value')
    assert extract is not None and vitacherry is not None
    assert abs(extract - vitacherry) <= 0.015, (
        f'tart cherry extract ({extract}) must be class-consistent with '
        f'vitacherry sports ({vitacherry}) within 0.015 — anthocyanin '
        f'class-poor (PMID:20218618).'
    )


def test_no_phantom_borges_2010_first_author(iqm):
    """The "Borges 2010" citation must not appear as live first-author
    citation — Borges is 2nd author; correct = González-Barrio 2010.
    """
    forms = iqm['tart_cherry']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        if 'Borges 2010' in text:
            assert any(neg in text.lower() for neg in
                       ('2nd author', 'second author', 'ghost', 'wrong',
                        'gonzález-barrio', 'gonzalez-barrio', 'co-author')), (
                f'tart_cherry::{fname} cites "Borges 2010" without '
                f'correction — Borges is 2nd author; correct first = '
                f'González-Barrio.'
            )


def test_class_authority_pmids_introduced_b31(iqm):
    """Verified class-authority PMIDs must each appear in IQM notes."""
    expected_pmids = {
        'PMID:19847319': 'Crowley 2009 UC-II',
        'PMID:30321134': 'Demarque 2018 cascarosides',
        'PMID:9001835':  'Talent 1996 NAG',
        'PMID:22399525': 'Chitchumroonchokchai 2012 mangosteen',
        'PMID:20218618': 'González-Barrio 2010 anthocyanin',
        'PMID:31673018': 'Lee 2019 cordycepin metabolite',
    }
    full_text = ''
    for pid in ('collagen', 'cascara_sagrada', 'glucosamine', 'mangosteen',
                'tart_cherry', 'cordyceps'):
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing: {missing}'
    )


def test_eighth_category_error_pattern(iqm):
    """Eight category-error parent groups now established (B18-B31)."""
    category_error_forms = [
        ('manuka_honey', 'umf 15+ / mgo 514+'),                           # B18 #1
        ('organ_extracts', 'grass-fed desiccated'),                       # B20 #2
        ('inulin', 'inulin (unspecified)'),                                # B22 #3
        ('slippery_elm', 'standardized extract (mucilage)'),               # B23 #4
        ('psyllium', 'psyllium seed'),                                     # B24 #5
        ('superoxide_dismutase', 'sod supplement'),                        # B24 #6
        ('fiber', 'konjac glucomannan'),                                   # B25 #7
        ('collagen', 'undenatured collagen'),                              # B31 #8 (NEW)
    ]
    for pid, fname in category_error_forms:
        form = iqm[pid]['forms'].get(fname)
        if form is None:
            continue
        v = (form.get('absorption_structured') or {}).get('value')
        assert v is None, (
            f'{pid}::{fname} value={v} should be null per category-error.'
        )
