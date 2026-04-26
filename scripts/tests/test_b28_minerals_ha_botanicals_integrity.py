"""Regression test: Batch 28 — minerals + HA + bioflavonoids + botanicals.

Per IQM audit 2026-04-25 Step 4 Batch 28: 30 forms across 10 parents.
Six framework findings:

1. HYALURONIC ACID — keep null + reframe. Mannino 2024 (PMID:37081790)
   only animal data. No human oral PK. HMW HA fiber-like; vLMW mouse-only.

2. KELP IODINE = variable CONTENT not variable F. Teas 2004
   (PMID:15588380). Zimmermann 2004 (PMID:15220938) WHO avoid.

3. MOLECULAR IODINE (I2) ≠ IODIDE — distinct NIS-independent mechanism
   (Aranda 2013 PMID:22576883). Cannot assume KI-class F.

4. PECTIN + ALPHA-GOS = CATEGORY ERROR (extension of B22 inulin). Nyman
   2002 (PMID:12088514). **INCONSISTENCY**: companion FOS/GOS/XOS at
   0.65-0.90 reflect older nutrient-density framework — pending Dr Pham.

5. CITRUS BIOFLAVONOIDS — class-poor extension (B19).

6. TURMERIC FORMS — class-equiv to curcumin parent (B8). Piperine
   enhancement DEBUNKED.

GHOST PMIDS / CITATIONS CAUGHT (2):
  • "Oe 2014 HA labeled distribution" — fabricated, not in PubMed
  • "Kimura 2016 HA Caco-2"           — fabricated, not in PubMed
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


B28_BANDS_VALUED = [
    # iodine — only unspecified populated (kelp + I2 stay null)
    ('iodine', 'iodine (unspecified)',                      0.90, 0.99, 'iodide class'),
    # selenium
    ('selenium', 'selenium analogs (non-functional)',       0.00, 0.05, 'non-functional'),
    ('selenium', 'oxidized selenium',                       0.00, 0.10, 'oxidative degradation'),
    ('selenium', 'selenium (unspecified)',                  0.45, 0.85, 'Se class baseline'),
    # manganese
    ('manganese', 'manganese sulfate',                      0.03, 0.08, 'Mn class baseline'),
    ('manganese', 'manganese oxide',                        0.00, 0.05, 'oxide non-bioavail'),
    ('manganese', 'manganese (unspecified)',                0.03, 0.08, 'Mn class baseline'),
    # citrus_bioflavonoids
    ('citrus_bioflavonoids', 'citrus bioflavonoids complex', 0.05, 0.15, 'bioflav class-poor'),
    ('citrus_bioflavonoids', 'hesperidin',                   0.03, 0.12, 'hesperidin class-poor'),
    ('citrus_bioflavonoids', 'rutin',                        0.02, 0.10, 'rutin class-poor'),
    # turmeric
    ('turmeric', 'liposomal curcumin',                      0.03, 0.10, 'liposomal-thin + curcumin'),
    ('turmeric', 'curcumin with piperine',                  0.02, 0.08, 'piperine debunked'),
    ('turmeric', 'turmeric (unspecified)',                  0.01, 0.05, 'curcumin class-poor'),
    # black_cohosh
    ('black_cohosh', 'black cohosh standardized extract',   0.10, 0.30, 'Crominex pattern'),
    ('black_cohosh', 'black cohosh root powder',            0.05, 0.15, 'powder lower'),
    ('black_cohosh', 'black cohosh (unspecified)',          0.05, 0.20, 'class baseline'),
    # spearmint
    ('spearmint', 'neumentix spearmint extract',            0.10, 0.30, 'Neumentix Crominex'),
    ('spearmint', 'spearmint extract',                      0.10, 0.25, 'rosmarinic class-poor'),
    ('spearmint', 'spearmint (unspecified)',                0.05, 0.15, 'class baseline'),
    # sage
    ('sage', 'cognivia sage extract',                       0.10, 0.30, 'Cognivia Crominex'),
    ('sage', 'sage extract',                                0.10, 0.25, 'rosmarinic+carnosic'),
    ('sage', 'sage (unspecified)',                          0.05, 0.15, 'class baseline'),
]

B28_NULL_FORMS = [
    # HA — keep null with framework notes
    ('hyaluronic_acid', 'liposomal HA',                              'no human PK; liposomal-thin'),
    ('hyaluronic_acid', 'acetylated HA',                             'no human oral PK'),
    ('hyaluronic_acid', 'hyaluronic acid (unspecified)',             'no human PK; MW-dep'),
    # iodine — kelp + I2 null
    ('iodine', 'kelp iodine',                                        'variable content'),
    ('iodine', 'molecular iodine',                                   'NIS-independent distinct'),
    # prebiotics category-error extension (B22)
    ('prebiotics', 'pectin',                                         'category-error fiber'),
    ('prebiotics', 'alpha-glucooligosaccharides (alpha-GOS)',        'category-error alpha-GOS'),
    ('prebiotics', 'prebiotics (unspecified)',                       'category-error default'),
]


@pytest.mark.parametrize('pid,fname,vmin,vmax,basis', B28_BANDS_VALUED)
def test_b28_value_in_band(iqm, pid, fname, vmin, vmax, basis):
    """Each populated form must sit in evidence band."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is not None, f'{pid}::{fname} struct.value should be populated'
    assert vmin <= val <= vmax, (
        f'{pid}::{fname}: struct.value={val} outside band [{vmin}, {vmax}]. '
        f'Basis: {basis}'
    )


@pytest.mark.parametrize('pid,fname,reason', B28_NULL_FORMS)
def test_b28_null_form(iqm, pid, fname, reason):
    """Each null form must have struct.value=null per its framework reason."""
    form = iqm[pid]['forms'].get(fname)
    assert form is not None, f'{pid}::{fname} missing'
    val = (form.get('absorption_structured') or {}).get('value')
    assert val is None, (
        f'{pid}::{fname} value={val} must be null — reason: {reason}'
    )


def test_pectin_alpha_gos_category_error_documented(iqm):
    """Pectin + alpha-GOS notes must document category-error / B22 extension."""
    forms = [
        ('prebiotics', 'pectin'),
        ('prebiotics', 'alpha-glucooligosaccharides (alpha-GOS)'),
        ('prebiotics', 'prebiotics (unspecified)'),
    ]
    for pid, fname in forms:
        form = iqm[pid]['forms'][fname]
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        text_lower = text.lower()
        flag_phrases = ('category error', 'category_error', 'fermentation', 'scfa',
                        'b22', 'batch 22', 'inulin framework', '12088514', 'nyman 2002')
        assert any(p in text_lower for p in flag_phrases), (
            f'{pid}::{fname} must document category-error / B22 extension. '
            f'Text: {text[:300]}'
        )


def test_kelp_variable_content_not_F_documented(iqm):
    """Kelp iodine notes must document variable CONTENT not variable F."""
    form = iqm['iodine']['forms']['kelp iodine']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    flag_phrases = ('variable content', 'content not f', 'variable iodine',
                    '15588380', 'teas 2004', '15220938', 'zimmermann',
                    'dose unpredictability', 'avoid kelp')
    assert any(p in text_lower for p in flag_phrases), (
        f'kelp iodine must document variable content not F (PMID:15588380). '
        f'Text: {text[:300]}'
    )


def test_molecular_iodine_distinct_mechanism_documented(iqm):
    """Molecular I2 notes must document NIS-independent mechanism."""
    form = iqm['iodine']['forms']['molecular iodine']
    text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
    text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
    text_lower = text.lower()
    flag_phrases = ('nis-independent', 'nis independent', 'distinct', 'aranda 2013',
                    '22576883', '23607319', 'aceves', 'extrathyroidal')
    assert any(p in text_lower for p in flag_phrases), (
        f'molecular iodine must document NIS-independent mechanism. '
        f'Text: {text[:300]}'
    )


def test_no_phantom_oe_kimura_HA(iqm):
    """The non-existent "Oe 2014" / "Kimura 2016" HA citations must not
    appear as live citations.
    """
    forms = iqm['hyaluronic_acid']['forms']
    for fname, form in forms.items():
        text = (form.get('notes') or '') + ' ' + (form.get('absorption') or '')
        text += ' ' + ((form.get('absorption_structured') or {}).get('notes') or '')
        if 'Oe 2014' in text:
            assert any(neg in text.lower() for neg in
                       ('ghost', 'fabricated', 'not in pubmed', 'not found')), (
                f'HA::{fname} cites "Oe 2014" without ghost-trap qualification.'
            )
        if 'Kimura 2016' in text:
            assert any(neg in text.lower() for neg in
                       ('ghost', 'fabricated', 'not in pubmed', 'not found')), (
                f'HA::{fname} cites "Kimura 2016" without ghost-trap qualification.'
            )


def test_class_authority_pmids_introduced_b28(iqm):
    """Verified class-authority PMIDs must each appear in IQM notes."""
    expected_pmids = {
        'PMID:37081790': 'Mannino 2024 vLMW HA mouse',
        'PMID:15588380': 'Teas 2004 kelp variability',
        'PMID:22576883': 'Aranda 2013 I2 NIS-indep',
        'PMID:12088514': 'Nyman 2002 pectin SCFA',
    }
    full_text = ''
    for pid in ('hyaluronic_acid', 'iodine', 'prebiotics'):
        for form in iqm[pid]['forms'].values():
            full_text += (form.get('notes') or '') + ' '
            full_text += (form.get('absorption') or '') + ' '
            full_text += ((form.get('absorption_structured') or {}).get('notes') or '') + ' '
    missing = [pmid for pmid in expected_pmids if pmid not in full_text]
    assert not missing, (
        f'Verified class-authority PMIDs missing: {missing}'
    )


def test_iron_calcium_iodine_parents_fully_populated_or_categorically_null(iqm):
    """After B28, iodine + selenium + manganese + citrus_bioflavonoids +
    turmeric + black_cohosh + spearmint + sage parents should have ZERO
    null forms (HA + prebiotics still have intentional null framework forms).
    """
    fully_populated_parents = [
        'iodine', 'selenium', 'manganese', 'citrus_bioflavonoids',
        'turmeric', 'black_cohosh', 'spearmint', 'sage',
    ]
    for pid in fully_populated_parents:
        forms = iqm[pid]['forms']
        # iodine has 2 intentionally-null forms (kelp + I2)
        if pid == 'iodine':
            null_forms = [
                fn for fn, f in forms.items()
                if (f.get('absorption_structured') or {}).get('value') is None
                and fn not in ('kelp iodine', 'molecular iodine')
            ]
        else:
            null_forms = [
                fn for fn, f in forms.items()
                if (f.get('absorption_structured') or {}).get('value') is None
            ]
        assert not null_forms, (
            f'{pid} should have ZERO unintentional null forms after B28; '
            f'still null: {null_forms}'
        )
